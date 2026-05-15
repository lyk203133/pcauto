use anyhow::{anyhow, Result};
use chromiumoxide::browser::{Browser, BrowserConfig};
use chromiumoxide::page::Page;
use futures::StreamExt;
use std::collections::HashMap;
use std::path::PathBuf;
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use tokio::sync::mpsc;
use tokio::time::{sleep, timeout, Duration};

use crate::callback::{poll_ga, request_captcha, request_ga, send_step_callback};
use crate::models::{AppConfig, StepAction, TaskData};
use crate::template::{render, render_opt};

const STEP_RETRY_DELAY_SECS: u64 = 5;
const DEFAULT_STEP_MAX_RETRIES: u64 = 3;

#[derive(Debug, Clone)]
pub struct TaskFailure {
    pub reason: String,
    pub failure_image_data: Option<String>,
}

impl TaskFailure {
    fn new(reason: impl Into<String>) -> Self {
        Self {
            reason: reason.into(),
            failure_image_data: None,
        }
    }
}

/// 搜尋本機已安裝的 Chrome / Chromium 執行檔路徑
pub fn find_system_chrome() -> Option<String> {
    let candidates: Vec<String> = {
        #[cfg(target_os = "windows")]
        {
            let pf =
                std::env::var("ProgramFiles").unwrap_or_else(|_| "C:\\Program Files".to_string());
            let pf86 = std::env::var("ProgramFiles(x86)")
                .unwrap_or_else(|_| "C:\\Program Files (x86)".to_string());
            let local = std::env::var("LOCALAPPDATA").unwrap_or_default();
            vec![
                format!("{pf}\\Google\\Chrome\\Application\\chrome.exe"),
                format!("{pf}\\Chromium\\Application\\chrome.exe"),
                format!("{pf86}\\Google\\Chrome\\Application\\chrome.exe"),
                format!("{pf86}\\Chromium\\Application\\chrome.exe"),
                format!("{local}\\Google\\Chrome\\Application\\chrome.exe"),
            ]
        }
        #[cfg(target_os = "macos")]
        {
            let home = std::env::var("HOME").unwrap_or_default();
            vec![
                "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome".to_string(),
                "/Applications/Chromium.app/Contents/MacOS/Chromium".to_string(),
                format!("{home}/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
            ]
        }
        #[cfg(target_os = "linux")]
        {
            vec![
                "/usr/bin/google-chrome".to_string(),
                "/usr/bin/google-chrome-stable".to_string(),
                "/usr/bin/chromium-browser".to_string(),
                "/usr/bin/chromium".to_string(),
                "/snap/bin/chromium".to_string(),
            ]
        }
        #[cfg(not(any(target_os = "windows", target_os = "macos", target_os = "linux")))]
        {
            vec![]
        }
    };

    candidates
        .into_iter()
        .find(|p| std::path::Path::new(p).exists())
}

/// 驗證碼 selector 列表
const CAPTCHA_SELECTORS: &[&str] = &[
    ".g-recaptcha",
    "[data-sitekey]",
    ".cf-turnstile",
    "#hcaptcha",
    ".h-captcha",
    "#captcha",
    ".captcha-container",
    "iframe[src*='captcha']",
    ".challenge-form",
];

/// 瀏覽器自動化執行器
pub struct BrowserExecutor {
    pub cfg: AppConfig,
    pub task: TaskData,
    pub log_tx: mpsc::UnboundedSender<String>,
    pub should_stop: Arc<AtomicBool>,
    pub http_client: reqwest::Client,
}

impl BrowserExecutor {
    pub fn new(
        cfg: AppConfig,
        task: TaskData,
        log_tx: mpsc::UnboundedSender<String>,
        should_stop: Arc<AtomicBool>,
    ) -> Self {
        BrowserExecutor {
            cfg,
            task,
            log_tx,
            should_stop,
            http_client: reqwest::Client::new(),
        }
    }

    fn log(&self, msg: impl Into<String>) {
        let _ = self.log_tx.send(msg.into());
    }

    /// 主執行入口
    pub async fn run(self) -> std::result::Result<bool, TaskFailure> {
        let order_no = self.task.order_no.clone();
        self.log(format!("▶ 開始執行任務 {order_no}"));

        let result = self.run_inner().await;
        match result {
            Ok(true) => {
                self.log(format!("✅ 任務完成: {order_no}"));
                Ok(true)
            }
            Ok(false) => {
                self.log(format!("⏹ 任務已停止: {order_no}"));
                Ok(false)
            }
            Err(e) => {
                self.log(format!("❌ 任務失敗: {order_no} — {}", e.reason));
                Err(e)
            }
        }
    }

    async fn run_inner(&self) -> std::result::Result<bool, TaskFailure> {
        let (mut browser, page, profile_dir) = self
            .init_browser()
            .await
            .map_err(|e| TaskFailure::new(e.to_string()))?;

        let result = self.execute_steps(&page).await;

        let _ = page.close().await;

        let close_result = timeout(Duration::from_secs(5), browser.close()).await;
        if !matches!(close_result, Ok(Ok(_))) {
            self.log("⚠️ Chrome 關閉超時，嘗試強制結束");
            let _ = browser.kill().await;
        }

        if timeout(Duration::from_secs(5), browser.wait())
            .await
            .is_err()
        {
            self.log("⚠️ 等待 Chrome 退出超時，嘗試強制結束");
            let _ = browser.kill().await;
            let _ = browser.wait().await;
        }

        let _ = std::fs::remove_dir_all(&profile_dir);
        result
    }

    async fn init_browser(&self) -> Result<(Browser, Page, PathBuf)> {
        self.log("🌐 正在啟動瀏覽器...");

        let chrome_path = find_system_chrome();
        if let Some(ref p) = chrome_path {
            self.log(format!("✅ 使用系統 Chrome：{p}"));
        } else {
            self.log("⚠️ 未找到系統 Chrome，嘗試使用默認路徑");
        }

        let profile_dir = browser_profile_dir(&self.task);
        std::fs::create_dir_all(&profile_dir)?;

        let mut builder = BrowserConfig::builder()
            .no_sandbox()
            .user_data_dir(&profile_dir)
            .arg("--disable-blink-features=AutomationControlled")
            .arg("--no-first-run")
            .arg("--no-default-browser-check")
            .arg("--start-maximized")
            .window_size(1366, 900);

        if self.cfg.show_browser {
            self.log("🪟 瀏覽器顯示模式");
            builder = builder.with_head();
        } else {
            self.log("🕶 無頭瀏覽器模式");
        }

        if let Some(path) = chrome_path {
            builder = builder.chrome_executable(path);
        }

        if let Some(ref proxy) = self.cfg.proxy {
            if !proxy.is_empty() {
                builder = builder.arg(format!("--proxy-server={proxy}"));
            }
        }

        let config = builder
            .build()
            .map_err(|e| anyhow!("BrowserConfig error: {e}"))?;

        // 重試最多 3 次
        let mut last_err = anyhow!("未知錯誤");
        for attempt in 1..=3u32 {
            match Browser::launch(config.clone()).await {
                Ok((mut browser, mut handler)) => {
                    // 啟動 CDP 消息處理 handler
                    tokio::spawn(async move { while let Some(_event) = handler.next().await {} });

                    match browser.new_page("about:blank").await {
                        Ok(page) => {
                            // 禁用 webdriver 特徵
                            let _ = page.evaluate(
                                "Object.defineProperty(navigator,'webdriver',{get:()=>undefined});"
                            ).await;
                            self.log("✅ Chrome 啟動成功");
                            return Ok((browser, page, profile_dir));
                        }
                        Err(e) => {
                            last_err = anyhow!("{e}");
                            let _ = browser.kill().await;
                        }
                    }
                }
                Err(e) => {
                    last_err = anyhow!("{e}");
                    if attempt < 3 {
                        self.log(format!("啟動失敗，重試 ({attempt}/3): {e}"));
                        sleep(Duration::from_secs(2)).await;
                    }
                }
            }
        }
        Err(last_err)
    }

    async fn execute_steps(&self, page: &Page) -> std::result::Result<bool, TaskFailure> {
        let steps = &self.task.steps;
        let total = steps.len();
        let ctx = self.task.template_context();
        // 用 Mutex 保護 ctx 以允許 wait_ga 寫入 ga_code
        let ctx = std::sync::Arc::new(std::sync::Mutex::new(ctx));

        self.log(format!(
            "▶ 開始執行任務 {}，共 {total} 步",
            self.task.order_no
        ));
        self.log("-".repeat(40));

        for (idx, step) in steps.iter().enumerate() {
            let action = &step.action;
            let max_retries = step_max_retries(step);
            let mut attempt = 0;

            loop {
                if self.should_stop.load(Ordering::Relaxed) {
                    self.log("⏹ 用戶已停止");
                    return Ok(false);
                }

                attempt += 1;

                let ctx_snapshot = ctx.lock().unwrap().clone();
                let step_name = step_callback_name(step, idx + 1);
                let description = describe_step(step, idx + 1, total, &ctx_snapshot);
                self.log(format!(
                    "步驟 {}/{total}: {action}（第 {attempt}/{max_retries} 次）",
                    idx + 1
                ));

                // 步驟開始回調
                send_step_callback(
                    &self.http_client,
                    &self.cfg,
                    self.task.task_id,
                    &self.task.order_no,
                    &format!("step_{}_{action}", idx + 1),
                    &step_name,
                    action,
                    attempt,
                    max_retries,
                    "running",
                    &format!("{description}；第 {attempt}/{max_retries} 次執行"),
                    None,
                )
                .await;

                // 驗證碼檢測
                if self.check_captcha(page).await {
                    self.handle_captcha(page).await;
                }

                match self.execute_step(page, step, &ctx).await {
                    Ok(()) => {
                        self.log(format!("  ✅ 步驟 {} 完成", idx + 1));
                        send_step_callback(
                            &self.http_client,
                            &self.cfg,
                            self.task.task_id,
                            &self.task.order_no,
                            &format!("step_{}_{action}", idx + 1),
                            &step_name,
                            action,
                            attempt,
                            max_retries,
                            "success",
                            &format!("{description}；第 {attempt}/{max_retries} 次；結果：完成"),
                            None,
                        )
                        .await;
                        break;
                    }
                    Err(reason) => {
                        if self.should_stop.load(Ordering::Relaxed) {
                            self.log("⏹ 用戶已停止");
                            return Ok(false);
                        }

                        if attempt >= max_retries {
                            let final_reason = format!(
                                "步驟 {}/{}「{}」連續失敗 {}/{} 次，最後原因：{}",
                                idx + 1,
                                total,
                                step_name,
                                attempt,
                                max_retries,
                                reason
                            );
                            self.log(format!("  ❌ {final_reason}；中斷任務並回報失敗"));
                            send_step_callback(
                                &self.http_client,
                                &self.cfg,
                                self.task.task_id,
                                &self.task.order_no,
                                &format!("step_{}_{action}", idx + 1),
                                &step_name,
                                action,
                                attempt,
                                max_retries,
                                "failed",
                                &format!(
                                    "{description}；第 {attempt}/{max_retries} 次；結果：已達最大重試次數，中斷任務"
                                ),
                                Some(&final_reason),
                            )
                            .await;
                            let failure_image_data =
                                self.capture_failure_screenshot(page, &step_name).await;
                            return Err(TaskFailure {
                                reason: final_reason,
                                failure_image_data,
                            });
                        }

                        self.log(format!(
                            "  ⏸ 步驟 {} 第 {attempt}/{max_retries} 次異常，原因：{reason}；{STEP_RETRY_DELAY_SECS}s 後重試",
                            idx + 1,
                        ));
                        send_step_callback(
                            &self.http_client,
                            &self.cfg,
                            self.task.task_id,
                            &self.task.order_no,
                            &format!("step_{}_{action}", idx + 1),
                            &step_name,
                            action,
                            attempt,
                            max_retries,
                            "failed",
                            &format!(
                                "{description}；第 {attempt}/{max_retries} 次；結果：異常，等待 {STEP_RETRY_DELAY_SECS}s 後重試"
                            ),
                            Some(&reason),
                        )
                        .await;

                        for _ in 0..STEP_RETRY_DELAY_SECS {
                            if self.should_stop.load(Ordering::Relaxed) {
                                self.log("⏹ 用戶已停止");
                                return Ok(false);
                            }
                            sleep(Duration::from_secs(1)).await;
                        }
                    }
                }
            }

            // 步驟間隨機等待 0.5~1.2s
            let delay_ms = 500 + (rand_ms() % 700);
            sleep(Duration::from_millis(delay_ms)).await;
        }

        self.log("-".repeat(40));
        self.log("✅ 任務完成");
        Ok(true)
    }

    /// 執行單個步驟
    async fn execute_step(
        &self,
        page: &Page,
        step: &StepAction,
        ctx_lock: &std::sync::Arc<std::sync::Mutex<HashMap<String, String>>>,
    ) -> std::result::Result<(), String> {
        if self.should_stop.load(Ordering::Relaxed) {
            return Err("stopped".to_string());
        }

        let ctx = ctx_lock.lock().unwrap().clone();
        let action = step.action.as_str();
        let selector = render_opt(step.selector.as_deref(), &ctx);
        let mut value = render_opt(step.value.as_deref(), &ctx);
        let url = render_opt(step.url.as_deref(), &ctx);
        let expected = render_opt(step.expected.as_deref(), &ctx);
        let timeout_sec = step.timeout.unwrap_or(15);

        let result: Result<()> = async {
            match action {
                "navigate" => {
                    self.log(format!("  → navigate {url}"));
                    page.goto(url.as_str()).await.map_err(|e| anyhow!("{e}"))?;
                    page.wait_for_navigation().await.map_err(|e| anyhow!("{e}"))?;
                }

                "click" => {
                    if selector.is_empty() {
                        return Err(anyhow!("click 缺少 selector"));
                    }
                    self.log(format!("  → click {selector}"));
                    let elem = page
                        .find_element(selector.as_str())
                        .await
                        .map_err(|e| anyhow!("click find_element: {e}"))?;
                    elem.click().await.map_err(|e| anyhow!("click: {e}"))?;
                }

                "input" => {
                    if selector.is_empty() {
                        return Err(anyhow!("input 缺少 selector"));
                    }

                    if let Some(variable) = unresolved_single_placeholder(step.value.as_deref(), &value) {
                        request_ga(
                            &self.http_client,
                            &self.cfg,
                            self.task.task_id,
                            &self.task.order_no,
                            &variable,
                        )
                        .await;
                        self.log(format!("  🔐 等待用戶輸入 {{{{{variable}}}}}..."));

                        let timeout_s = step.timeout.unwrap_or(120);
                        let code = poll_ga(
                            &self.http_client,
                            &self.cfg,
                            self.task.task_id,
                            timeout_s,
                            &self.should_stop,
                        )
                        .await;

                        if code.is_empty() {
                            return Err(anyhow!("等待 {{{{{variable}}}}} 超時"));
                        }

                        {
                            let mut guard = ctx_lock.lock().unwrap();
                            guard.insert(variable.clone(), code.clone());
                            guard.insert("code".to_string(), code.clone());
                            guard.insert("ga_code".to_string(), code.clone());
                        }
                        value = code;
                    }

                    let disp = preview(&value, 20);
                    self.log(format!("  → input {selector} = {disp}"));
                    if !self.fill_with_verify(page, &selector, &value, "輸入值", 3, timeout_sec).await {
                        return Err(anyhow!("fill_with_verify 失敗"));
                    }
                }

                "type" => {
                    if selector.is_empty() {
                        return Err(anyhow!("type 缺少 selector"));
                    }
                    self.log(format!("  → type {selector}"));
                    // 先清空
                    let elem = page
                        .find_element(selector.as_str())
                        .await
                        .map_err(|e| anyhow!("type find_element: {e}"))?;
                    elem.click().await.map_err(|e| anyhow!("type click: {e}"))?;

                    // 用 evaluate 模擬逐字輸入
                    let js = format!(
                        r#"(function() {{
                            var el = document.querySelector({sel});
                            if (!el) return false;
                            el.focus();
                            el.value = '';
                            var val = {val};
                            for (var i = 0; i < val.length; i++) {{
                                el.value += val[i];
                                el.dispatchEvent(new Event('input', {{bubbles: true}}));
                            }}
                            el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }})()"#,
                        sel = serde_json::to_string(&selector).unwrap_or_default(),
                        val = serde_json::to_string(&value).unwrap_or_default(),
                    );
                    page.evaluate(js.as_str()).await.map_err(|e| anyhow!("type evaluate: {e}"))?;

                    // 驗證
                    let actual = self.read_input_value(page, &selector).await;
                    if actual.as_deref() != Some(value.as_str()) {
                        self.log("  ⚠️ type 後值不一致，改用 fill 重試");
                        if !self.fill_with_verify(page, &selector, &value, "輸入值", 3, timeout_sec).await {
                            return Err(anyhow!("type fallback fill_with_verify 失敗"));
                        }
                    }
                }

                "select" => {
                    if selector.is_empty() {
                        return Err(anyhow!("select 缺少 selector"));
                    }
                    self.log(format!("  → select {selector} = {value}"));
                    let js = format!(
                        r#"(function() {{
                            var el = document.querySelector({sel});
                            if (!el) return false;
                            el.value = {val};
                            el.dispatchEvent(new Event('change', {{bubbles: true}}));
                            return true;
                        }})()"#,
                        sel = serde_json::to_string(&selector).unwrap_or_default(),
                        val = serde_json::to_string(&value).unwrap_or_default(),
                    );
                    page.evaluate(js.as_str()).await.map_err(|e| anyhow!("select evaluate: {e}"))?;
                }

                "wait" => {
                    let seconds = step
                        .seconds
                        .or_else(|| step.ms.map(|ms| ms as f64 / 1000.0))
                        .or_else(|| value.parse::<f64>().ok())
                        .unwrap_or(1.0);
                    self.log(format!("  → wait {seconds}s"));
                    let total_ms = (seconds * 1000.0) as u64;
                    let chunk_ms = 100u64;
                    let mut elapsed = 0u64;
                    while elapsed < total_ms {
                        if self.should_stop.load(Ordering::Relaxed) {
                            return Err(anyhow!("stopped"));
                        }
                        let chunk = chunk_ms.min(total_ms - elapsed);
                        sleep(Duration::from_millis(chunk)).await;
                        elapsed += chunk;
                    }
                }

                "wait_text" => {
                    if selector.is_empty() {
                        return Err(anyhow!("wait_text 缺少 selector"));
                    }
                    if expected.is_empty() {
                        self.log(format!("  → wait_text {selector}: 等待元素出現"));
                        if !self.wait_for_selector(page, &selector, timeout_sec).await? {
                            return Err(anyhow!("wait_text timeout: {selector}"));
                        }
                    } else {
                        self.log(format!("  → wait_text {selector} = \"{expected}\""));
                        let wait_js = format!(
                            r#"new Promise((resolve) => {{
                                var deadline = Date.now() + {ms};
                                function isVisible(el) {{
                                    return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                                }}
                                function check() {{
                                    var el = document.querySelector({sel});
                                    var text = isVisible(el) ? (el.innerText || el.textContent || '') : '';
                                    if (text.indexOf({expected}) !== -1) {{ resolve({{ found: true, text: text }}); return; }}
                                    if (Date.now() > deadline) {{ resolve({{ found: false, text: text }}); return; }}
                                    setTimeout(check, 200);
                                }}
                                check();
                            }})"#,
                            ms = timeout_sec * 1000,
                            sel = serde_json::to_string(&selector).unwrap_or_default(),
                            expected = serde_json::to_string(&expected).unwrap_or_default(),
                        );
                        let result = page
                            .evaluate(wait_js.as_str())
                            .await
                            .map_err(|e| anyhow!("wait_text: {e}"))?;
                        let value = result.into_value::<serde_json::Value>().unwrap_or_default();
                        let found = value.get("found").and_then(|v| v.as_bool()).unwrap_or(false);
                        if !found {
                            let text = value.get("text").and_then(|v| v.as_str()).unwrap_or("");
                            self.log(format!(
                                "  ⚠️ 期望文字 \"{expected}\" 未找到，實際: \"{}\"",
                                preview(text, 50)
                            ));
                            return Err(anyhow!("wait_text 未找到期望文字"));
                        }
                    }
                }

                "wait_selector" => {
                    if selector.is_empty() {
                        return Err(anyhow!("wait_selector 缺少 selector，請在規則中配置"));
                    }
                    self.log(format!("  → wait_selector {selector}"));
                    if !self.wait_for_selector(page, &selector, timeout_sec).await? {
                        return Err(anyhow!("wait_selector timeout: {selector}"));
                    }
                }

                "wait_ga" => {
                    let variable = render_opt(
                        step.variable
                            .as_deref()
                            .or(step.name.as_deref())
                            .or(Some("code")),
                        &ctx,
                    );
                    // 通知後端需要 GA 碼
                    request_ga(
                        &self.http_client,
                        &self.cfg,
                        self.task.task_id,
                        &self.task.order_no,
                        &variable,
                    )
                    .await;
                    self.log("  🔐 已通知用戶輸入 GA 碼，等待中...");

                    let timeout_s = step.timeout.unwrap_or(120);
                    let ga_code = poll_ga(
                        &self.http_client,
                        &self.cfg,
                        self.task.task_id,
                        timeout_s,
                        &self.should_stop,
                    )
                    .await;

                    if ga_code.is_empty() {
                        self.log("  ❌ GA 等待超時");
                        return Err(anyhow!("GA 等待超時"));
                    }

                    {
                        let mut guard = ctx_lock.lock().unwrap();
                        guard.insert(variable.clone(), ga_code.clone());
                        guard.insert("code".to_string(), ga_code.clone());
                        guard.insert("ga_code".to_string(), ga_code.clone());
                    }

                    if selector.is_empty() {
                        return Err(anyhow!(
                            "wait_ga 缺少 selector，已保存 {{{{{variable}}}}}；請在規則中配置要填入的驗證碼輸入框"
                        ));
                    }

                    self.log(format!("  → wait_ga: 填入 GA 碼至 {selector}"));
                    if !self
                        .fill_with_verify(page, &selector, &ga_code, "GA 碼", 3, timeout_sec)
                        .await
                    {
                        return Err(anyhow!("GA 碼填入失敗"));
                    }
                }

                "captcha_image" | "request_captcha" | "captcha" => {
                    if selector.is_empty() {
                        return Err(anyhow!("captcha_image 缺少 selector"));
                    }
                    let variable = render_opt(
                        step.variable
                            .as_deref()
                            .or(step.name.as_deref())
                            .or(Some("code")),
                        &ctx,
                    );
                    self.log(format!("  → captcha_image: 截圖 {selector}，等待 {{{{{variable}}}}}"));

                    if !self.wait_for_selector(page, &selector, timeout_sec).await? {
                        return Err(anyhow!("captcha_image timeout: {selector}"));
                    }

                    let elem = page
                        .find_element(selector.as_str())
                        .await
                        .map_err(|e| anyhow!("captcha_image find_element: {e}"))?;
                    let png = elem
                        .screenshot(chromiumoxide::cdp::browser_protocol::page::CaptureScreenshotFormat::Png)
                        .await
                        .map_err(|e| anyhow!("captcha_image screenshot: {e}"))?;

                    use base64::Engine as _;
                    let image_data = format!(
                        "data:image/png;base64,{}",
                        base64::engine::general_purpose::STANDARD.encode(png)
                    );

                    if !request_captcha(
                        &self.http_client,
                        &self.cfg,
                        self.task.task_id,
                        &self.task.order_no,
                        &image_data,
                        &variable,
                    )
                    .await
                    {
                        return Err(anyhow!("captcha_image 回傳後端失敗"));
                    }

                    self.log("  🔐 已回傳圖形驗證碼，等待用戶輸入...");
                    let timeout_s = step.timeout.unwrap_or(120);
                    let code = poll_ga(
                        &self.http_client,
                        &self.cfg,
                        self.task.task_id,
                        timeout_s,
                        &self.should_stop,
                    )
                    .await;

                    if code.is_empty() {
                        return Err(anyhow!("圖形驗證碼等待超時"));
                    }

                    let mut guard = ctx_lock.lock().unwrap();
                    guard.insert(variable.clone(), code.clone());
                    guard.insert("code".to_string(), code.clone());
                    guard.insert("ga_code".to_string(), code);
                }

                "screenshot" => {
                    let name = step
                        .name
                        .as_deref()
                        .unwrap_or("screenshot");
                    let ts = chrono::Local::now().format("%H%M%S");
                    let path = format!("{name}_{ts}.png");
                    self.log(format!("  → screenshot → {path}"));
                    page.save_screenshot(
                        chromiumoxide::page::ScreenshotParams::builder()
                            .format(chromiumoxide::cdp::browser_protocol::page::CaptureScreenshotFormat::Png)
                            .build(),
                        &path,
                    )
                    .await
                    .map_err(|e| anyhow!("screenshot: {e}"))?;
                }

                "js" => {
                    let code = render(step.code.as_deref().unwrap_or(""), &ctx);
                    self.log("  → js executed");
                    page.evaluate(code.as_str())
                        .await
                        .map_err(|e| anyhow!("js evaluate: {e}"))?;
                }

                "scroll" => {
                    let amount = step.amount.unwrap_or(500);
                    self.log(format!("  → scroll {amount}px"));
                    let js = format!("window.scrollBy(0, {amount});");
                    page.evaluate(js.as_str())
                        .await
                        .map_err(|e| anyhow!("scroll: {e}"))?;
                }

                other => {
                    self.log(format!("  ⚠️ 未知 action: {other}，跳過"));
                }
            }
            Ok(())
        }
        .await;

        match result {
            Ok(()) => Ok(()),
            Err(e) => {
                if self.should_stop.load(Ordering::Relaxed) {
                    return Err("stopped".to_string());
                }
                self.log(format!("  ❌ 步驟執行失敗: {e}"));
                Err(e.to_string())
            }
        }
    }

    async fn capture_failure_screenshot(&self, page: &Page, step_name: &str) -> Option<String> {
        let params = chromiumoxide::page::ScreenshotParams::builder()
            .format(chromiumoxide::cdp::browser_protocol::page::CaptureScreenshotFormat::Png)
            .build();

        match timeout(Duration::from_secs(5), page.screenshot(params)).await {
            Ok(Ok(png)) => {
                use base64::Engine as _;
                self.log(format!("  📷 已截取失敗畫面：{step_name}"));
                Some(format!(
                    "data:image/png;base64,{}",
                    base64::engine::general_purpose::STANDARD.encode(png)
                ))
            }
            Ok(Err(e)) => {
                self.log(format!("  ⚠️ 失敗畫面截圖失敗：{e}"));
                None
            }
            Err(_) => {
                self.log("  ⚠️ 失敗畫面截圖超時");
                None
            }
        }
    }

    /// 回讀 input 元素的值
    async fn read_input_value(&self, page: &Page, selector: &str) -> Option<String> {
        let js = format!(
            r#"(function() {{
                var el = document.querySelector({sel});
                return el ? el.value : null;
            }})()"#,
            sel = serde_json::to_string(selector).unwrap_or_default(),
        );
        page.evaluate(js.as_str())
            .await
            .ok()
            .and_then(|v| v.into_value::<Option<String>>().ok())
            .flatten()
    }

    async fn wait_for_any_selector(
        &self,
        page: &Page,
        selectors: &[&str],
        timeout_sec: u64,
    ) -> Result<Option<String>> {
        let selectors_json = serde_json::to_string(selectors).unwrap_or_default();
        let check_js = format!(
            r#"(function() {{
                var selectors = {selectors_json};
                function isVisible(el) {{
                    return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
                }}
                for (var i = 0; i < selectors.length; i++) {{
                    try {{
                        var el = document.querySelector(selectors[i]);
                        if (isVisible(el)) {{ return selectors[i]; }}
                    }} catch (e) {{}}
                }}
                return null;
            }})()"#,
        );

        let deadline = std::time::Instant::now() + Duration::from_secs(timeout_sec);
        loop {
            if self.should_stop.load(Ordering::Relaxed) {
                return Ok(None);
            }

            match page.evaluate(check_js.as_str()).await {
                Ok(result) => {
                    if let Some(found) = result.into_value::<Option<String>>().unwrap_or(None) {
                        return Ok(Some(found));
                    }
                }
                Err(e) => {
                    tracing::debug!("wait_for_any_selector retry after evaluate error: {e}");
                }
            }

            if std::time::Instant::now() >= deadline {
                return Ok(None);
            }
            sleep(Duration::from_millis(200)).await;
        }
    }

    async fn wait_for_selector(
        &self,
        page: &Page,
        selector: &str,
        timeout_sec: u64,
    ) -> Result<bool> {
        Ok(self
            .wait_for_any_selector(page, &[selector], timeout_sec)
            .await?
            .is_some())
    }

    /// 填入值 + 回讀驗證，最多重試 max_retries 次
    async fn fill_with_verify(
        &self,
        page: &Page,
        selector: &str,
        value: &str,
        label: &str,
        max_retries: u32,
        _timeout_sec: u64,
    ) -> bool {
        for attempt in 1..=max_retries {
            // 用 JS 填入（兼容 React/Vue 等框架的 controlled components）
            let fill_js = format!(
                r#"(function() {{
                    var el = document.querySelector({sel});
                    if (!el) return false;
                    var nativeInputValueSetter = Object.getOwnPropertyDescriptor(
                        window.HTMLInputElement.prototype, 'value'
                    ).set;
                    if (nativeInputValueSetter) {{
                        nativeInputValueSetter.call(el, {val});
                    }} else {{
                        el.value = {val};
                    }}
                    el.dispatchEvent(new Event('input', {{bubbles: true}}));
                    el.dispatchEvent(new Event('change', {{bubbles: true}}));
                    return true;
                }})()"#,
                sel = serde_json::to_string(selector).unwrap_or_default(),
                val = serde_json::to_string(value).unwrap_or_default(),
            );

            match page.evaluate(fill_js.as_str()).await {
                Err(e) => {
                    self.log(format!("  ❌ {label}填入失敗（第{attempt}次）: {e}"));
                    if attempt < max_retries {
                        sleep(Duration::from_millis(500)).await;
                    }
                    continue;
                }
                Ok(ret) => {
                    // 檢查是否返回 false（元素未找到）
                    if ret.into_value::<bool>().unwrap_or(true) == false {
                        self.log(format!(
                            "  ❌ {label}：元素未找到 {selector}（第{attempt}次）"
                        ));
                        if attempt < max_retries {
                            sleep(Duration::from_millis(500)).await;
                        }
                        continue;
                    }
                }
            }

            // 回讀驗證
            let actual = self.read_input_value(page, selector).await;
            match actual {
                Some(ref v) if v == value => {
                    self.log(format!("  ✔ {label}驗證通過（第{attempt}次）"));
                    return true;
                }
                Some(ref v) => {
                    let disp_exp = preview(value, 20);
                    let disp_act = preview(v, 20);
                    self.log(format!(
                        "  ⚠️ {label}不一致（第{attempt}次）  期望={disp_exp:?}  實際={disp_act:?}"
                    ));
                    if attempt < max_retries {
                        self.log("  🔄 清空後重新填入...");
                        // 清空
                        let clear_js = format!(
                            r#"(function() {{
                                var el = document.querySelector({sel});
                                if (el) {{ el.value = ''; el.dispatchEvent(new Event('input', {{bubbles:true}})); }}
                            }})()"#,
                            sel = serde_json::to_string(selector).unwrap_or_default(),
                        );
                        let _ = page.evaluate(clear_js.as_str()).await;
                        sleep(Duration::from_millis(500)).await;
                    }
                }
                None => {
                    // 元素不支持 value 屬性，視為通過
                    self.log(format!("  ✔ {label}（無法回讀，視為通過）"));
                    return true;
                }
            }
        }

        self.log(format!(
            "  ❌ {label}重試 {max_retries} 次仍不一致，步驟失敗"
        ));
        false
    }

    /// 檢測頁面上是否有驗證碼
    async fn check_captcha(&self, page: &Page) -> bool {
        for sel in CAPTCHA_SELECTORS {
            let js = format!(
                r#"(function() {{
                    var el = document.querySelector({sel});
                    return el ? (el.offsetWidth > 0 && el.offsetHeight > 0) : false;
                }})()"#,
                sel = serde_json::to_string(sel).unwrap_or_default(),
            );
            if let Ok(v) = page.evaluate(js.as_str()).await {
                if v.into_value::<bool>().unwrap_or(false) {
                    return true;
                }
            }
        }
        false
    }

    /// 等待驗證碼被手動處理
    async fn handle_captcha(&self, page: &Page) {
        self.log("⚠️ 檢測到驗證碼，等待人工處理...");
        loop {
            if self.should_stop.load(Ordering::Relaxed) {
                return;
            }
            sleep(Duration::from_secs(1)).await;
            if !self.check_captcha(page).await {
                break;
            }
        }
        self.log("✅ 驗證碼已解決");
    }
}

/// 簡單的偽隨機數（避免引入 rand crate）
fn rand_ms() -> u64 {
    use std::time::SystemTime;
    SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .map(|d| d.subsec_nanos() as u64)
        .unwrap_or(0)
}

fn preview(value: &str, max_chars: usize) -> String {
    let mut chars = value.chars();
    let mut out: String = chars.by_ref().take(max_chars).collect();
    if chars.next().is_some() {
        out.push_str("...");
    }
    out
}

fn step_callback_name(step: &StepAction, index: usize) -> String {
    step.step_name
        .as_deref()
        .map(str::trim)
        .filter(|s| !s.is_empty())
        .map(ToOwned::to_owned)
        .unwrap_or_else(|| format!("第 {index} 步"))
}

fn step_max_retries(step: &StepAction) -> u64 {
    step.max_retries.unwrap_or(DEFAULT_STEP_MAX_RETRIES).max(1)
}

fn describe_step(
    step: &StepAction,
    index: usize,
    total: usize,
    ctx: &HashMap<String, String>,
) -> String {
    let action = step.action.as_str();
    let step_name = step_callback_name(step, index);
    let selector = render_opt(step.selector.as_deref(), ctx);
    let value = render_opt(step.value.as_deref(), ctx);
    let url = render_opt(step.url.as_deref(), ctx);
    let expected = render_opt(step.expected.as_deref(), ctx);
    let timeout = step.timeout.unwrap_or(15);

    let detail = match action {
        "navigate" => format!("打開網址 {url}"),
        "click" => format!("點擊元素 {selector}"),
        "input" => format!("填寫 {selector} = {}", preview(&value, 24)),
        "type" => format!("逐字輸入 {selector} = {}", preview(&value, 24)),
        "select" => format!("選擇 {selector} = {}", preview(&value, 24)),
        "wait" => {
            let seconds = step
                .seconds
                .or_else(|| step.ms.map(|ms| ms as f64 / 1000.0))
                .or_else(|| value.parse::<f64>().ok())
                .unwrap_or(1.0);
            format!("等待 {seconds}s")
        }
        "wait_text" => {
            if expected.is_empty() {
                format!("等待元素出現 {selector}，timeout={timeout}s")
            } else {
                format!("等待 {selector} 出現文字 {}", preview(&expected, 30))
            }
        }
        "wait_selector" => format!("等待元素 {selector}，timeout={timeout}s"),
        "wait_ga" => format!("等待並填入 GA/OTP 到 {selector}，timeout={timeout}s"),
        "captcha_image" | "request_captcha" | "captcha" => {
            format!("截取圖形驗證碼 {selector} 並等待用戶輸入，timeout={timeout}s")
        }
        "screenshot" => format!("保存截圖 {}", step.name.as_deref().unwrap_or("screenshot")),
        "js" => "執行自定義 JavaScript".to_string(),
        "scroll" => format!("滾動 {}px", step.amount.unwrap_or(500)),
        other => format!("執行未知動作 {other}"),
    };

    format!("步驟 {index}/{total}「{step_name}」: {detail}")
}

fn unresolved_single_placeholder(raw: Option<&str>, rendered: &str) -> Option<String> {
    let raw = raw?.trim();
    if raw != rendered.trim() {
        return None;
    }

    let inner = raw.strip_prefix("{{")?.strip_suffix("}}")?.trim();
    if inner.is_empty() || !inner.chars().all(|c| c.is_ascii_alphanumeric() || c == '_') {
        return None;
    }

    Some(inner.to_string())
}

fn browser_profile_dir(task: &TaskData) -> PathBuf {
    use std::time::{SystemTime, UNIX_EPOCH};

    let ts = SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|d| d.as_millis())
        .unwrap_or(0);
    let order_no = sanitize_profile_component(&task.order_no);

    std::env::temp_dir()
        .join("pcauto-chrome-profiles")
        .join(format!(
            "task-{}-{order_no}-{}-{ts}",
            task.task_id,
            std::process::id()
        ))
}

fn sanitize_profile_component(value: &str) -> String {
    let mut s: String = value
        .chars()
        .map(|c| {
            if c.is_ascii_alphanumeric() || matches!(c, '-' | '_') {
                c
            } else {
                '_'
            }
        })
        .take(80)
        .collect();

    if s.is_empty() {
        s.push_str("unknown");
    }

    s
}
