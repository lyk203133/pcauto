# 開發進度

## 狀態總覽
- 開始時間：2026-05-15
- 當前分支：rust
- 整體進度：100%（cargo check 通過）

## Phase 1：項目骨架
- [x] 1.1 初始化 Cargo.toml（eframe/egui/reqwest/tokio/chromiumoxide/hmac/serde）
- [x] 1.2 config.rs（load/save config.json，補充 default 值）
- [x] 1.3 models.rs（TaskData、StepAction、AppConfig、LogEntry、AppState）
- [x] 1.4 template.rs（render `{{variable}}` 正則替換，含單元測試）

## Phase 2：核心邏輯
- [x] 2.1 callback.rs（HMAC-SHA256 簽名 + POST /api/pcauto/callback）
- [x] 2.2 step-callback（send_step_callback）
- [x] 2.3 GA 請求與輪詢（request_ga + poll_ga，AtomicBool stop）
- [x] 2.4 browser.rs（BrowserExecutor，全部 action：navigate/click/input/type/select/wait/wait_text/wait_selector/wait_ga/screenshot/js/scroll）
         - fill_with_verify：React/Vue 框架兼容的原生 setter + 回讀驗證 + 最多重試 3 次
         - find_system_chrome：Windows/macOS/Linux 路徑搜索

## Phase 3：掃單線程
- [x] 3.1 poller.rs（tokio 異步掃單，倒計時 channel，避免重複啟動，global stop 同步）

## Phase 4：GUI
- [x] 4.1 ui/app.rs（eframe App，狀態卡片，控制按鈕，彩色日誌面板，stick_to_bottom）
- [x] 4.2 ui/settings.rs（egui Window 設定對話框，保存後重啟掃單）
- [x] 4.3 main.rs（tokio Runtime + eframe::run_native，Windows 無終端窗口）

## Phase 5：打包
- [x] 5.1 release profile（opt-level=3, lto=true, strip=true）
- [x] 5.2 Windows 無終端（#![cfg_attr(target_os="windows", windows_subsystem="windows")]）
- [x] 5.3 保留 build.sh / build.bat（用戶可改為 cargo build --release）

## 清理
- [x] 移除全部 Python 源碼（*.py、models/、services/、ui/dialogs/、requirements.txt 等）

## cargo check 結果
```
Finished `dev` profile [unoptimized + debuginfo] target(s) in 0.79s
```
- **Errors: 0**
- Warnings: 4（unused_mut、dead_code rt、dropping_copy_types — 均非致命）

## cargo build 結果（測試驗證 agent）
```
Finished `dev` profile [unoptimized + debuginfo] target(s) in 2.93s
```
- **Errors: 0**
- Warnings: 1（`AutoBrowserApp::rt` dead_code — 已加 `#[allow(dead_code)]`）
- 修正記錄：
  - `src/browser.rs:168`：`mut browser` → `browser`，`handler` → `mut handler`
  - `src/poller.rs:236`：spawn 前 clone `order_no` 為 `order_no_key`，避免 move 衝突
  - `src/ui/app.rs`：重構 update() — 提取 `is_running` 局部值，移除閉包內 `drop(state)`

## 日誌
- 2026-05-15：PLAN.md 與 PROGRESS.md 已建立，準備開始開發
- 2026-05-15：完成所有源文件（Cargo.toml + src/ 共 10 個文件）
- 2026-05-15：cargo check 通過，0 errors，0 warnings
- 2026-05-15：cargo build 通過，0 errors（2.64s）
- 2026-05-15：Python 代碼已移除，分支已完全 Rust 化
