use serde::de::Error as DeError;
use serde::{Deserialize, Deserializer, Serialize};
use std::collections::HashMap;

/// 單個任務步驟
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct StepAction {
    pub action: String,
    pub step_name: Option<String>,
    pub selector: Option<String>,
    pub value: Option<String>,
    pub url: Option<String>,
    pub expected: Option<String>,
    #[serde(default, deserialize_with = "de_opt_f64")]
    pub seconds: Option<f64>,
    #[serde(default, deserialize_with = "de_opt_u64")]
    pub ms: Option<u64>,
    #[serde(default, deserialize_with = "de_opt_i32")]
    pub amount: Option<i32>,
    pub code: Option<String>,
    pub name: Option<String>,
    pub variable: Option<String>,
    pub captcha_type: Option<String>, // captcha_prefetch 用：image | ga
    #[serde(default, alias = "options_selector")]
    pub option_selector: Option<String>, // dropdown 用：選項元素 CSS
    pub match_type: Option<String>,      // dropdown 用：exact | contains（預設 contains）
    #[serde(default, deserialize_with = "de_opt_u64")]
    pub timeout: Option<u64>,
    #[serde(default, deserialize_with = "de_opt_u64")]
    pub max_retries: Option<u64>,
}

fn de_opt_u64<'de, D>(deserializer: D) -> Result<Option<u64>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Option::<serde_json::Value>::deserialize(deserializer)?;
    match value {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Number(n)) => n
            .as_u64()
            .map(Some)
            .ok_or_else(|| D::Error::custom("expected unsigned integer")),
        Some(serde_json::Value::String(s)) => {
            let s = s.trim();
            if s.is_empty() {
                Ok(None)
            } else {
                s.parse::<u64>()
                    .map(Some)
                    .map_err(|_| D::Error::custom("expected unsigned integer string"))
            }
        }
        _ => Err(D::Error::custom("expected unsigned integer or string")),
    }
}

fn de_opt_i32<'de, D>(deserializer: D) -> Result<Option<i32>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Option::<serde_json::Value>::deserialize(deserializer)?;
    match value {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Number(n)) => n
            .as_i64()
            .and_then(|v| i32::try_from(v).ok())
            .map(Some)
            .ok_or_else(|| D::Error::custom("expected 32-bit integer")),
        Some(serde_json::Value::String(s)) => {
            let s = s.trim();
            if s.is_empty() {
                Ok(None)
            } else {
                s.parse::<i32>()
                    .map(Some)
                    .map_err(|_| D::Error::custom("expected integer string"))
            }
        }
        _ => Err(D::Error::custom("expected integer or string")),
    }
}

fn de_opt_f64<'de, D>(deserializer: D) -> Result<Option<f64>, D::Error>
where
    D: Deserializer<'de>,
{
    let value = Option::<serde_json::Value>::deserialize(deserializer)?;
    match value {
        None | Some(serde_json::Value::Null) => Ok(None),
        Some(serde_json::Value::Number(n)) => n
            .as_f64()
            .map(Some)
            .ok_or_else(|| D::Error::custom("expected number")),
        Some(serde_json::Value::String(s)) => {
            let s = s.trim();
            if s.is_empty() {
                Ok(None)
            } else {
                s.parse::<f64>()
                    .map(Some)
                    .map_err(|_| D::Error::custom("expected number string"))
            }
        }
        _ => Err(D::Error::custom("expected number or string")),
    }
}

/// 從後端 API 返回的任務
#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct TaskData {
    pub task_id: u64,
    pub order_no: String,
    pub steps: Vec<StepAction>,
    /// 其他字段，用於模板上下文
    #[serde(flatten)]
    pub extra: HashMap<String, serde_json::Value>,
}

impl TaskData {
    /// 把 task_data 的所有字段轉換為模板上下文（String -> String）
    pub fn template_context(&self) -> HashMap<String, String> {
        let mut ctx = HashMap::new();
        ctx.insert("task_id".to_string(), self.task_id.to_string());
        ctx.insert("order_no".to_string(), self.order_no.clone());
        for (k, v) in &self.extra {
            let s = match v {
                serde_json::Value::String(s) => s.clone(),
                other => other.to_string(),
            };
            ctx.insert(k.clone(), s);
        }
        ctx
    }
}

/// GET /api/pcauto/pending-tasks 的響應
#[derive(Debug, Deserialize)]
pub struct PendingTasksResponse {
    pub tasks: Vec<TaskData>,
}

/// GET /api/pcauto/get-ga 的響應
#[derive(Debug, Deserialize)]
pub struct GetGaResponse {
    pub ready: bool,
    pub ga_code: Option<String>,
    pub code: Option<String>,
}

/// GET /api/pcauto/get-credentials 的響應（captcha_prefetch 用）
#[derive(Debug, Deserialize)]
pub struct GetCredentialsResponse {
    pub ready: bool,
    pub account: Option<String>,
    pub password: Option<String>,
    pub code: Option<String>,
}

/// 應用配置
#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct AppConfig {
    pub server_url: String,
    pub api_key: String,
    pub hmac_secret: String,
    pub poll_interval: u64,
    pub max_concurrent_tasks: usize,
    pub browser_type: String,
    pub show_browser: bool,
    pub proxy: Option<String>,
}

impl Default for AppConfig {
    fn default() -> Self {
        AppConfig {
            server_url: "http://localhost:8088".to_string(),
            api_key: "b3e377b9cff032a348861bf7b3e57fdddddad1d65a20771ca3d0d99127a56c59".to_string(),
            hmac_secret: "b3e377b9cff032a348861bf7b3e57fdddddad1d65a20771ca3d0d99127a56c59"
                .to_string(),
            poll_interval: 5,
            max_concurrent_tasks: 3,
            browser_type: "chrome".to_string(),
            show_browser: true,
            proxy: None,
        }
    }
}

/// 日誌條目
#[derive(Debug, Clone)]
pub struct LogEntry {
    pub timestamp: String,
    pub message: String,
    pub level: LogLevel,
}

#[derive(Debug, Clone, PartialEq)]
pub enum LogLevel {
    Error,
    Warning,
    Success,
    Step,
    Normal,
}

impl LogEntry {
    pub fn new(message: impl Into<String>) -> Self {
        let msg = message.into();
        let level = Self::classify(&msg);
        LogEntry {
            timestamp: chrono::Local::now().format("%H:%M:%S").to_string(),
            message: msg,
            level,
        }
    }

    fn classify(msg: &str) -> LogLevel {
        if msg.contains("❌")
            || msg.contains("error")
            || msg.contains("錯誤")
            || msg.contains("失敗")
            || msg.contains("failed")
        {
            LogLevel::Error
        } else if msg.contains("⚠")
            || msg.contains("warning")
            || msg.contains("警告")
            || msg.contains("驗證碼")
        {
            LogLevel::Warning
        } else if msg.contains("✅")
            || msg.contains("complete")
            || msg.contains("完成")
            || msg.contains("success")
            || msg.contains("成功")
            || msg.contains("✔")
        {
            LogLevel::Success
        } else if msg.contains("▶")
            || msg.contains("步驟")
            || msg.contains("Step")
            || msg.contains("🚀")
            || msg.contains("🔄")
        {
            LogLevel::Step
        } else {
            LogLevel::Normal
        }
    }

    pub fn egui_color(&self) -> egui::Color32 {
        match self.level {
            LogLevel::Error => egui::Color32::from_rgb(0xFF, 0x45, 0x3A),
            LogLevel::Warning => egui::Color32::from_rgb(0xFF, 0xD6, 0x0A),
            LogLevel::Success => egui::Color32::from_rgb(0x30, 0xD1, 0x58),
            LogLevel::Step => egui::Color32::from_rgb(0x64, 0xD2, 0xFF),
            LogLevel::Normal => egui::Color32::from_rgb(0x98, 0x98, 0x9D),
        }
    }
}

/// UI 和後台共享的應用狀態
#[derive(Debug)]
pub struct AppState {
    pub is_running: bool,
    pub active_task_count: usize,
    pub active_order_nos: std::collections::HashSet<String>,
    pub logs: std::collections::VecDeque<LogEntry>,
    pub countdown: u64,
    pub status: String,
}

impl Default for AppState {
    fn default() -> Self {
        AppState {
            is_running: false,
            active_task_count: 0,
            active_order_nos: std::collections::HashSet::new(),
            logs: std::collections::VecDeque::new(),
            countdown: 0,
            status: "已停止".to_string(),
        }
    }
}

impl AppState {
    pub const MAX_LOGS: usize = 1000;

    pub fn push_log(&mut self, msg: impl Into<String>) {
        let entry = LogEntry::new(msg);
        self.logs.push_back(entry);
        if self.logs.len() > Self::MAX_LOGS {
            self.logs.pop_front();
        }
    }
}
