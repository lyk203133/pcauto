use std::collections::{HashMap, HashSet};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;
use tokio::task::JoinHandle;
use tokio::time::{sleep, Duration};

use crate::browser::BrowserExecutor;
use crate::callback::send_callback;
use crate::config::load_config;
use crate::models::{AppConfig, AppState, TaskData};

/// 掃單結果事件，由 poller 發送給 UI
#[derive(Debug)]
#[allow(dead_code)]
pub enum PollEvent {
    Log(String),
    TaskStarted(String),           // order_no
    TaskDone(String, bool),        // order_no, success
    Countdown(u64),                // 距下次掃單剩餘秒數（0=正在掃單）
    ActiveCount(usize),            // 當前活躍任務數
}

pub struct Poller {
    pub stop_flag: Arc<AtomicBool>,
    handle: Option<JoinHandle<()>>,
}

impl Poller {
    /// 啟動掃單循環，返回 Poller 句柄
    pub fn start(
        event_tx: mpsc::UnboundedSender<PollEvent>,
        state: Arc<std::sync::Mutex<AppState>>,
    ) -> Self {
        let stop_flag = Arc::new(AtomicBool::new(false));
        let stop_flag_clone = Arc::clone(&stop_flag);

        let handle = tokio::spawn(poll_loop(event_tx, state, stop_flag_clone));

        Poller {
            stop_flag,
            handle: Some(handle),
        }
    }

    /// 停止掃單
    pub fn stop(&self) {
        self.stop_flag.store(true, Ordering::Relaxed);
        if let Some(ref h) = self.handle {
            h.abort();
        }
    }
}

async fn poll_loop(
    event_tx: mpsc::UnboundedSender<PollEvent>,
    _state: Arc<std::sync::Mutex<AppState>>,
    stop_flag: Arc<AtomicBool>,
) {
    let log = |msg: &str| {
        let _ = event_tx.send(PollEvent::Log(msg.to_string()));
    };

    log("🔄 掃單服務已啟動");

    // 活躍任務：order_no -> JoinHandle
    let mut active_tasks: HashMap<String, JoinHandle<()>> = HashMap::new();
    // 正在運行的 order_no 集合
    let active_set: Arc<std::sync::Mutex<HashSet<String>>> =
        Arc::new(std::sync::Mutex::new(HashSet::new()));

    let http_client = reqwest::Client::new();

    loop {
        if stop_flag.load(Ordering::Relaxed) {
            break;
        }

        // 清理已完成的任務
        active_tasks.retain(|_, h| !h.is_finished());
        {
            let active_set_guard = active_set.lock().unwrap();
            let _ = event_tx.send(PollEvent::ActiveCount(active_set_guard.len()));
        }

        // 執行一次掃單
        let cfg = load_config();
        poll_once(
            &http_client,
            &cfg,
            &event_tx,
            &mut active_tasks,
            &active_set,
            &stop_flag,
        )
        .await;

        let interval = cfg.poll_interval;
        // 倒計時
        for remaining in (1..=interval).rev() {
            if stop_flag.load(Ordering::Relaxed) {
                break;
            }
            let _ = event_tx.send(PollEvent::Countdown(remaining));
            sleep(Duration::from_secs(1)).await;
        }
        if !stop_flag.load(Ordering::Relaxed) {
            let _ = event_tx.send(PollEvent::Countdown(0));
        }
    }

    // 停止所有活躍任務
    for (_, h) in active_tasks.drain() {
        h.abort();
    }

    log("⏹ 掃單服務已停止");
}

async fn poll_once(
    client: &reqwest::Client,
    cfg: &AppConfig,
    event_tx: &mpsc::UnboundedSender<PollEvent>,
    active_tasks: &mut HashMap<String, JoinHandle<()>>,
    active_set: &Arc<std::sync::Mutex<HashSet<String>>>,
    stop_flag: &Arc<AtomicBool>,
) {
    let log = |msg: String| {
        let _ = event_tx.send(PollEvent::Log(msg));
    };

    let server_url = cfg.server_url.trim_end_matches('/');
    if server_url.is_empty() || cfg.api_key.is_empty() {
        return;
    }

    let poll_url = format!("{server_url}/api/pcauto/pending-tasks");
    log(format!(">> 掃單 {poll_url}"));

    let t0 = std::time::Instant::now();
    let result = client
        .get(&poll_url)
        .header("X-Pcauto-Key", &cfg.api_key)
        .timeout(Duration::from_secs(10))
        .send()
        .await;

    let elapsed = t0.elapsed().as_secs_f64();

    match result {
        Err(e) if e.is_connect() || e.is_timeout() => {
            log(format!("❌ 無法連線後端（{elapsed:.2}s）：{poll_url}"));
        }
        Err(e) => {
            log(format!("❌ 掃單失敗（{elapsed:.2}s）: {e}"));
        }
        Ok(resp) => {
            let status = resp.status();
            if !status.is_success() {
                log(format!(
                    "⚠️ HTTP {status}（{elapsed:.2}s）—— 請確認 API Key 和後端 URL"
                ));
                return;
            }

            match resp.json::<crate::models::PendingTasksResponse>().await {
                Err(e) => {
                    log(format!("❌ 解析響應失敗: {e}"));
                }
                Ok(data) => {
                    let tasks = data.tasks;
                    if tasks.is_empty() {
                        log(format!("🔍 無待處理任務（{elapsed:.2}s）"));
                    } else {
                        log(format!("📋 發現 {} 個待處理任務（{elapsed:.2}s）", tasks.len()));
                    }

                    for task in tasks {
                        start_task(
                            client,
                            cfg,
                            task,
                            event_tx,
                            active_tasks,
                            active_set,
                            stop_flag,
                        )
                        .await;
                    }
                }
            }
        }
    }
}

async fn start_task(
    client: &reqwest::Client,
    cfg: &AppConfig,
    task: TaskData,
    event_tx: &mpsc::UnboundedSender<PollEvent>,
    active_tasks: &mut HashMap<String, JoinHandle<()>>,
    active_set: &Arc<std::sync::Mutex<HashSet<String>>>,
    global_stop: &Arc<AtomicBool>,
) {
    let order_no = task.order_no.clone();
    let task_id = task.task_id;

    // 避免重複啟動同一訂單
    {
        let guard = active_set.lock().unwrap();
        if guard.contains(&order_no) {
            return;
        }
    }
    // 如果舊 handle 還在跑也跳過
    if let Some(h) = active_tasks.get(&order_no) {
        if !h.is_finished() {
            return;
        }
    }

    let max_concurrent = cfg.max_concurrent_tasks.max(1);

    // 標記為活躍；如果已達並發上限，本輪暫不啟動新任務
    {
        let mut guard = active_set.lock().unwrap();
        if guard.len() >= max_concurrent {
            let _ = event_tx.send(PollEvent::Log(format!(
                "⏸ 已達並發上限 {max_concurrent}，暫不啟動任務: {order_no}"
            )));
            return;
        }
        guard.insert(order_no.clone());
    }

    let cfg_clone = cfg.clone();
    let event_tx_clone = event_tx.clone();
    let active_set_clone = Arc::clone(active_set);
    let global_stop_clone = Arc::clone(global_stop);
    let client_clone = client.clone();

    let _ = event_tx.send(PollEvent::Log(format!("🚀 已啟動任務: {order_no}")));
    let _ = event_tx.send(PollEvent::TaskStarted(order_no.clone()));

    let order_no_key = order_no.clone();

    let handle = tokio::spawn(async move {
        let log_tx_inner = {
            let (tx, mut rx) = mpsc::unbounded_channel::<String>();
            let evt_tx = event_tx_clone.clone();
            tokio::spawn(async move {
                while let Some(msg) = rx.recv().await {
                    let _ = evt_tx.send(PollEvent::Log(msg));
                }
            });
            tx
        };

        let task_stop = Arc::new(AtomicBool::new(false));
        // 同步 global stop 到 task stop
        let task_stop_clone = Arc::clone(&task_stop);
        let gs = Arc::clone(&global_stop_clone);
        tokio::spawn(async move {
            loop {
                if gs.load(Ordering::Relaxed) {
                    task_stop_clone.store(true, Ordering::Relaxed);
                    break;
                }
                tokio::time::sleep(Duration::from_millis(200)).await;
            }
        });

        let executor = BrowserExecutor::new(cfg_clone.clone(), task, log_tx_inner, task_stop);
        let success = executor.run().await;

        // 發送最終回調
        let status = if success { 2 } else { 3 };
        let cb_result = send_callback(&client_clone, &cfg_clone, task_id, &order_no, status).await;
        if let Err(e) = cb_result {
            let _ = event_tx_clone.send(PollEvent::Log(format!("❌ 回調失敗: {e}")));
        }

        // 從活躍集合移除
        {
            let mut guard = active_set_clone.lock().unwrap();
            guard.remove(&order_no);
        }

        let _ = event_tx_clone.send(PollEvent::TaskDone(order_no, success));
        let _ = event_tx_clone.send(PollEvent::ActiveCount(
            active_set_clone.lock().unwrap().len(),
        ));
    });

    active_tasks.insert(order_no_key, handle);
}
