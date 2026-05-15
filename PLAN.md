# PCauto Rust 重構開發計劃

## 項目概述

將現有的 Python PyQt5 桌面自動化工具（pcauto v2.0）完整重構為 Rust，功能對等、行為一致。

**原始功能：**
- 定時掃單：每隔 N 秒 GET `/api/pcauto/pending-tasks`，獲取待處理訂單
- 瀏覽器自動化：使用 Playwright/Chrome 執行步驟（click、fill、navigate 等）
- 模板變量替換：步驟中 `{{order_no}}` 等變量自動替換
- HMAC-SHA256 回調：任務完成後 POST `/api/pcauto/callback`，帶簽名
- 步驟進度回調：每步執行前後 POST `/api/pcauto/step-callback`
- GA/OTP 支援：遇到 `wait_ga` 步驟時通知後端，輪詢 GA 碼填入
- 驗證碼處理：自動檢測 reCAPTCHA/hCaptcha，暫停等用戶手動處理
- GUI 界面：右側窄條面板，顯示狀態、日誌、啟停按鈕、設定
- 配置管理：讀寫 `config.json`（server_url, api_key, hmac_secret, poll_interval, browser_type）

---

## 技術棧

| 組件 | Rust Crate | 說明 |
|------|-----------|------|
| GUI | `egui` + `eframe` | 即時模式 GUI，輕量跨平台 |
| HTTP | `reqwest` + `tokio` | 異步 HTTP 客戶端 |
| 瀏覽器自動化 | `chromiumoxide` | CDP-based，類似 Playwright |
| HMAC | `hmac` + `sha2` | 簽名算法 |
| 序列化 | `serde` + `serde_json` | JSON 配置與 API |
| 異步運行時 | `tokio` | 多線程異步 |
| 日誌 | `tracing` + `tracing-subscriber` | 結構化日誌 |
| 正則 | `regex` | `{{variable}}` 模板替換 |
| 時間 | `chrono` | 時間戳 |
| 跨平台路徑 | `dirs` | 應用數據目錄 |

---

## 目錄結構

```
src/
├── main.rs              # 入口，初始化 tokio + eframe
├── config.rs            # 配置管理（讀寫 config.json）
├── models.rs            # TaskData、StepAction 數據模型
├── poller.rs            # 定時掃單（tokio task）
├── browser.rs           # 瀏覽器自動化（chromiumoxide）
├── callback.rs          # HMAC 回調發送
├── template.rs          # {{variable}} 模板替換
└── ui/
    ├── mod.rs           # UI 模塊入口
    ├── app.rs           # eframe App 主體，持有狀態
    └── settings.rs      # 設定對話框
Cargo.toml
config.json.example
```

---

## 數據模型

### `TaskData`（從後端 API 返回）
```rust
struct TaskData {
    task_id: u64,
    order_no: String,
    steps: Vec<StepAction>,
    // 其他字段也放入模板上下文
}
```

### `StepAction`（steps 列表中每個步驟）
```rust
struct StepAction {
    action: String,        // navigate|click|input|type|select|wait|wait_text|wait_selector|wait_ga|screenshot|js|scroll
    selector: Option<String>,
    value: Option<String>,
    url: Option<String>,
    expected: Option<String>,
    seconds: Option<f64>,
    amount: Option<i32>,
    code: Option<String>,
    name: Option<String>,
    timeout: Option<u64>,
}
```

### `AppConfig`
```rust
struct AppConfig {
    server_url: String,
    api_key: String,
    hmac_secret: String,
    poll_interval: u64,   // 秒
    browser_type: String, // "chrome" | "cloakbrowser"
}
```

### `AppState`（UI 共享狀態）
```rust
struct AppState {
    is_running: bool,
    active_tasks: HashMap<String, JoinHandle<()>>,
    logs: VecDeque<LogEntry>,  // 最多 1000 條
    countdown: u64,
    status: String,
}
```

---

## 開發任務清單

### Phase 1：項目骨架
- [ ] 1.1 初始化 Cargo.toml，添加所有依賴
- [ ] 1.2 實現 `config.rs`：load/save config.json，DEFAULT_CONFIG
- [ ] 1.3 實現 `models.rs`：TaskData、StepAction、AppConfig、LogEntry
- [ ] 1.4 實現 `template.rs`：`render(value, ctx)` 替換 `{{key}}`

### Phase 2：核心邏輯
- [ ] 2.1 實現 `callback.rs`：HMAC-SHA256 簽名 + POST `/api/pcauto/callback`
- [ ] 2.2 實現步驟回調 `send_step_callback()`：POST `/api/pcauto/step-callback`
- [ ] 2.3 實現 GA 請求 `request_ga()` + 輪詢 `poll_ga()`
- [ ] 2.4 實現 `browser.rs`：
  - Chrome 路徑搜索（Windows/macOS/Linux）
  - chromiumoxide 初始化（headless=false、禁用 webdriver 特徵）
  - 代理支援
  - 驗證碼檢測（_check_captcha）
  - 所有 action 執行：navigate/click/input/type/select/wait/wait_text/wait_selector/wait_ga/screenshot/js/scroll
  - `_fill_with_verify`：填入後回讀驗證，最多重試 3 次
  - stop() 方法

### Phase 3：掃單線程
- [ ] 3.1 實現 `poller.rs`：
  - tokio task，每隔 poll_interval 秒執行 `poll_once()`
  - GET `/api/pcauto/pending-tasks`，帶 `X-Pcauto-Key` header
  - 避免重複啟動同一 order_no
  - 倒計時 channel 發送剩餘秒數
  - `stop()` 取消 task

### Phase 4：GUI
- [ ] 4.1 實現 `ui/app.rs`：eframe App，持有 Arc<Mutex<AppState>>
  - 定位右側 20% 屏幕寬，置頂
  - 狀態卡片：運行中/已停止，活躍任務數，倒計時
  - 控制按鈕：啟動/停止/設定
  - 日誌面板：彩色日誌（錯誤紅、警告黃、成功綠、步驟藍、普通灰）
  - 自動滾動到最新日誌
- [ ] 4.2 實現 `ui/settings.rs`：設定對話框
  - 後端 URL、API Key、HMAC Secret、輪詢間隔
  - 保存後如果正在運行則重啟掃單
- [ ] 4.3 實現 `main.rs`：tokio + eframe 整合，啟動 GUI

### Phase 5：打包
- [ ] 5.1 更新 `Cargo.toml`：release profile（opt-level=3, strip, lto）
- [ ] 5.2 Windows 無終端窗口（`#![windows_subsystem = "windows"]`）
- [ ] 5.3 更新 `build.sh` / `build.bat` 使用 `cargo build --release`

---

## API 接口規格

### GET `/api/pcauto/pending-tasks`
- Header: `X-Pcauto-Key: <api_key>`
- Response: `{"tasks": [{"task_id": 1, "order_no": "ORD001", "steps": [...]}]}`

### POST `/api/pcauto/callback`
- Header: `X-Pcauto-Key: <api_key>`
- Body: `{"task_id": 1, "order_no": "ORD001", "status": 2, "timestamp": 1234567890, "sign": "<hmac>"}`
- sign = HMAC-SHA256(hmac_secret, `{order_no}|{status}|{timestamp}`)
- status: 2=完成, 3=失敗

### POST `/api/pcauto/step-callback`
- Header: `X-Pcauto-Key: <api_key>`
- Body: `{"task_id": 1, "order_no": "ORD001", "step": "step_1_navigate", "status": "success", "message": "..."}`

### POST `/api/pcauto/request-ga`
- Header: `X-Pcauto-Key: <api_key>`
- Body: `{"task_id": 1, "order_no": "ORD001"}`

### GET `/api/pcauto/get-ga`
- Header: `X-Pcauto-Key: <api_key>`
- Params: `task_id=1`
- Response: `{"ready": true, "ga_code": "123456"}`

---

## 注意事項

1. `chromiumoxide` 需要 Chrome/Chromium 已安裝，搜索邏輯同 Python 版
2. `egui` 是即時模式 GUI，每幀重繪，日誌用 `VecDeque` 限制條數避免內存增長
3. tokio + eframe 整合：poller 在 `tokio::spawn`，UI 在主線程，通過 `Arc<Mutex<AppState>>` 或 channel 通信
4. Windows 打包需要 `embed-resource` 嵌入圖標（可選）
5. 步驟中的 `fill_with_verify` 在 chromiumoxide 中用 `element.evaluate()` 讀取 `input.value`
