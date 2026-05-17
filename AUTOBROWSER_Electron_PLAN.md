# AUTOBROWSER Electron 遷移技術方案

> 從 Rust + chromiumoxide + egui 遷移至 Electron + React + TypeScript + Playwright
>
> 撰寫者:代理 A 撰寫時間:2026-05-16
> 對應 git branch:`Electron`(工作目錄:`autobrowser/`,新專案目錄:`autobrowser/autobrowser-next/`)
>
> **目標讀者**:代理 B(實作)、代理 C(驗收)

本文件為 1:1 行為遷移規格。所有 step action、API 端點、HMAC 簽名、回調流程、佔位符替換、重試策略**必須與既有 Rust 實作完全一致**,後端(`trader-system`)無須任何改動。

---

## 1. 技術棧選型

| 層級 | 選擇 | 理由 |
|---|---|---|
| 殼層 | **Electron 30+**(Chromium 124+) | 對標 egui 桌面 GUI,但內建 Chromium,可同時擔任 UI 與自動化執行宿主 |
| 視圖層 | **React 18 + TypeScript 5** | 既有後台 Vue/PHP 不衝突;React 生態最豐富,組件可重用 |
| UI 組件 | **Tailwind CSS 3 + shadcn/ui**(或 Mantine) | 對標 egui 的扁平卡片風格,快速產出 macOS 配色(`#F2F2F7` 背景、`#007AFF` 按鈕、`#FF3B30` 停止鍵) |
| 狀態管理 | **Zustand**(或 Jotai) | 比 Redux 輕,跟 egui 的 `Arc<Mutex<AppState>>` 思維對齊 |
| 瀏覽器自動化 | **Playwright 1.48+** + **playwright-extra** + **puppeteer-extra-plugin-stealth**(走 playwright-extra 相容層) | 取代 chromiumoxide,功能更全(自動下載瀏覽器、原生 stealth、locator 等待 API、screenshot/element handle 完整);stealth 取代既有的 `--disable-blink-features=AutomationControlled` + `navigator.webdriver` 注入 |
| 行程間通訊 | **Electron IPC**(`ipcMain` / `ipcRenderer`) + **`contextBridge`** | 主進程跑 Playwright + 掃單迴圈,渲染進程只負責 UI 與設定;走 `preload.ts` 暴露安全 API |
| HTTP client | **undici**(Node 18+ 內建 fetch) | 取代 `reqwest`,原生支援、無第三方依賴 |
| 簽名/加密 | **Node `crypto` (HMAC-SHA256)** | 取代 `hmac` + `sha2` crate |
| 並發控制 | **`p-limit`** | 取代 `tokio::spawn` + 並發上限手動檢查 |
| 模板替換 | 自寫 `{{var}}` regex(同 `template.rs`) | 不引入額外依賴,行為 1:1 |
| 打包 | **electron-builder**(NSIS + dmg + zip) | 主流選擇,簽名/自動更新生態完整 |
| Logger | **electron-log**(渲染端) + **pino**(主進程) | 取代 `tracing` |
| 測試 | **Vitest**(unit) + **Playwright Test**(端到端) | TS 生態標配 |
| 語言 | **TypeScript strict**;不接受 `any`,所有 step action / API payload 強型別 | 取代 Rust 的型別安全 |

**為什麼不用 puppeteer-core?** Playwright 對 `waitForSelector`、`locator.fill`、`elementHandle.screenshot`、cross-origin iframe、`page.evaluate` 的 API 更穩定,且官方支援 stealth(透過 playwright-extra)。chromiumoxide 在 Rust 端常遇到 CDP 事件流卡住的問題,Playwright 預設用 protocol multiplexer 規避。

**為什麼不用 chromium-bidi?** WebDriver BiDi 還不成熟,Vietnam 銀行頁面(`SEAB`、`ACB`、`OCB`)多為傳統表單,CDP/Playwright 足夠。

---

## 2. 目錄結構(`autobrowser/autobrowser-next/`)

```
autobrowser-next/
├─ package.json
├─ tsconfig.json
├─ tsconfig.main.json          # 主進程編譯設定(target ES2022, module CommonJS)
├─ tsconfig.renderer.json      # 渲染進程編譯設定(target ES2020, module ESNext)
├─ vite.config.ts              # 渲染進程開發伺服器
├─ electron-builder.yml        # 打包設定
├─ .eslintrc.cjs / .prettierrc
├─ playwright.config.ts        # 端到端測試用
│
├─ src/
│  ├─ main/                    # ★ 主進程(等價 main.rs + browser.rs + poller.rs + callback.rs)
│  │  ├─ index.ts              # Electron app 入口(對標 main.rs)
│  │  ├─ ipc.ts                # IPC handlers 註冊(start/stop poller、saveConfig、subscribeLogs)
│  │  ├─ poller.ts             # 掃單迴圈 + 並發控管(對標 poller.rs)
│  │  ├─ executor.ts           # 單筆訂單瀏覽器執行器(對標 browser.rs BrowserExecutor)
│  │  ├─ actions/              # ★ 每個 step action 一個檔案,易於 code review
│  │  │  ├─ index.ts           # action registry(name -> handler)
│  │  │  ├─ types.ts           # ActionContext / ActionResult 型別
│  │  │  ├─ navigate.ts
│  │  │  ├─ captchaPrefetch.ts
│  │  │  ├─ input.ts
│  │  │  ├─ type.ts
│  │  │  ├─ click.ts
│  │  │  ├─ select.ts
│  │  │  ├─ dropdown.ts
│  │  │  ├─ waitText.ts
│  │  │  ├─ waitSelector.ts
│  │  │  ├─ waitGa.ts
│  │  │  ├─ captchaImage.ts
│  │  │  ├─ wait.ts
│  │  │  ├─ screenshot.ts
│  │  │  ├─ js.ts
│  │  │  └─ scroll.ts
│  │  ├─ callback.ts           # 對標 callback.rs:HMAC + 8 個 API 封裝
│  │  ├─ config.ts             # 載入/保存 config.json(對標 config.rs)
│  │  ├─ template.ts           # {{var}} 替換(對標 template.rs)
│  │  ├─ chrome.ts             # 系統 Chrome 偵測 + Playwright launchPersistentContext 包裝
│  │  ├─ profileDir.ts         # 每筆訂單獨立 userDataDir(對標 browser_profile_dir)
│  │  ├─ logger.ts             # pino + IPC 廣播
│  │  └─ types.ts              # AppConfig / TaskData / StepAction / LogEntry / events
│  │
│  ├─ preload/
│  │  └─ index.ts              # contextBridge 暴露:bridge.startPoller / stopPoller / saveConfig / onLog
│  │
│  ├─ renderer/                # ★ 渲染進程(等價 ui/app.rs + ui/settings.rs)
│  │  ├─ main.tsx              # React 入口
│  │  ├─ App.tsx               # 主視窗(對標 ui/app.rs)
│  │  ├─ components/
│  │  │  ├─ StatusCard.tsx     # 狀態卡片(運行狀態 + 任務數 + 倒計時)
│  │  │  ├─ ControlBar.tsx     # 啟動/停止/設定 三按鈕
│  │  │  ├─ LogPanel.tsx       # 黑底彩色 log 串流(對標 egui ScrollArea stick_to_bottom)
│  │  │  └─ SettingsDialog.tsx # 設定對話框(對標 ui/settings.rs)
│  │  ├─ store/
│  │  │  └─ useAppStore.ts     # Zustand:logs / countdown / activeCount / isRunning
│  │  └─ styles/
│  │     └─ globals.css        # Tailwind + macOS 配色 token
│  │
│  └─ shared/                  # 主/渲染共享型別
│     └─ ipc-channels.ts       # IPC channel 名稱常數
│
├─ resources/
│  ├─ icon.icns                # mac
│  └─ icon.ico                 # win
│
└─ tests/
   ├─ unit/                    # vitest
   │  ├─ template.test.ts
   │  ├─ callback.test.ts      # HMAC 簽名比對 Rust 版
   │  └─ actions/*.test.ts
   └─ e2e/                     # playwright test
      └─ acb-prefetch.spec.ts  # Phase 0 PoC 用
```

**重點**:
- **主進程**獨佔 Playwright 與所有網路 I/O,渲染進程只看 IPC 事件。理由:Playwright 在 Node 環境跑,效能與 stability 都比 renderer 內好;主進程崩潰時 Electron 會自動退出,符合 fail-fast。
- **每個 action 一個檔案**:Rust 版 1500+ 行的 `browser.rs` 太大,TS 版拆細以利測試。
- **`shared/`** 放純型別,雙端 import,避免重複定義。

---

## 3. 模組對應表

| Rust 檔案 | TS 對應 | 備註 |
|---|---|---|
| `src/main.rs` | `src/main/index.ts` | Electron `app.whenReady()` 取代 `eframe::run_native` |
| `src/poller.rs` | `src/main/poller.ts` | `tokio::spawn(poll_loop)` → `setInterval` + `AbortController`;`PollEvent` enum → IPC event payload |
| `src/browser.rs::BrowserExecutor` | `src/main/executor.ts` + `src/main/actions/*` | `match step.action` 拆成 action registry(`Record<string, ActionHandler>`) |
| `src/browser.rs::find_system_chrome` | `src/main/chrome.ts::findSystemChrome` | 沿用同樣的候選路徑表 |
| `src/browser.rs::browser_profile_dir` | `src/main/profileDir.ts::buildProfileDir` | `os.tmpdir()` + `task-{id}-{order}-{pid}-{ts}` |
| `src/browser.rs::wait_for_any_selector` | `src/main/executor.ts::waitForAnyVisible` | Playwright `page.waitForFunction` |
| `src/browser.rs::fill_with_verify` | `src/main/actions/_helpers.ts::fillWithVerify` | locator.fill + 回讀 |
| `src/browser.rs::check_captcha / handle_captcha` | `src/main/executor.ts::captchaWatchdog` | 同樣 9 個 CSS selector 列表 |
| `src/callback.rs` | `src/main/callback.ts` | 8 個函式 1:1 對映,所有 URL/payload/header 一致 |
| `src/callback.rs::compute_hmac` | `src/main/callback.ts::computeHmac` | `crypto.createHmac('sha256', secret).update(\`${order_no}|${status}|${ts}\`).digest('hex')` |
| `src/config.rs` | `src/main/config.ts` | `app.getPath('userData')/config.json` 為主路徑,落 cwd/exe 旁為相容路徑(同 Rust 邏輯) |
| `src/models.rs` | `src/main/types.ts` + `src/shared/*` | `StepAction` / `TaskData` / `AppConfig` / `LogEntry` |
| `src/models.rs::de_opt_u64/i32/f64`(寬鬆解析) | `src/main/types.ts::coerce*`(zod transform) | 後端會傳 `"15"` 字串型別,要容錯 |
| `src/template.rs` | `src/main/template.ts` | regex `/\{\{\s*(\w+)\s*\}\}/g` |
| `src/ui/app.rs` | `src/renderer/App.tsx` + `components/*` | 三大區塊:狀態卡 / 按鈕列 / log 面板 |
| `src/ui/settings.rs` | `src/renderer/components/SettingsDialog.tsx` | 同 8 個欄位 |
| `src/ui/mod.rs` | (無對應,React 直接 import) | — |

---

## 4. Step Action 完整移植清單

> 來源:`autobrowser/src/browser.rs` L435 開始的 `match action`(總共 14 個分支 + `unknown`)。
>
> 共識:每個 action 收到一個 `ActionContext`,回傳 `Promise<void>`(失敗 throw Error)。Selector / value / url / expected 等欄位在進 handler 前已透過 `renderOpt(ctx)` 完成 `{{var}}` 替換。

### 共用型別

```ts
// src/main/actions/types.ts
import { Page } from 'playwright';
import { AppConfig, StepAction, TaskData } from '../types';

export interface ActionContext {
  page: Page;
  step: StepAction;
  task: TaskData;
  cfg: AppConfig;
  vars: Map<string, string>;          // 對應 Rust 的 ctx_lock,可寫入(captcha_prefetch/wait_ga 會寫 account/password/code/ga_code)
  attempt: number;
  shouldStop: () => boolean;          // 對應 Arc<AtomicBool>
  log: (msg: string) => void;         // 直送 IPC
  http: HttpClient;                   // 對應 reqwest::Client
  rendered: {                         // 預先渲染好的字串
    selector: string;
    value: string;
    url: string;
    expected: string;
  };
  timeoutMs: number;                  // step.timeout * 1000(預設 15000)
}

export type ActionHandler = (ctx: ActionContext) => Promise<void>;
```

### 4.1 `navigate`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:436-459`:`page.goto(url)` → `wait_for_navigation` → 輪詢 `document.readyState === 'complete'`,deadline = timeout 秒 |
| Playwright 對應 | `await page.goto(url, { waitUntil: 'load', timeout: timeoutMs })` → `await page.waitForLoadState('domcontentloaded')`;若還不足,加 `await page.waitForFunction(() => document.readyState === 'complete', null, { timeout: timeoutMs })` |
| 必填 | `url`(可含 `{{site_url}}`) |
| Log | `→ navigate {url}` / `✓ 頁面載入完成` |

### 4.2 `captcha_prefetch`(★ 最複雜)

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:461-561`:`url` 為空時 fallback `{{site_url}}`;`captcha_type` ∈ `image`(預設) / `ga` / `totp`。<br>**image 分支**:`waitForSelector(captchaSelector, ms ?? 5000)` → 若找到就 `elementHandle.screenshot('png')` → base64 → `request_captcha(image_data, "code")`;沒找到就跳過。<br>**ga / totp 分支**:`request_ga("code")`。<br>無論哪個分支:呼叫 `POST /api/autobrowser/set-needs-credentials` 通知後端需要帳密,然後 `poll_credentials(timeout >= 120s)` 取得 `(account, password, code)` 寫入 `vars`(同時寫 `code` 和 `ga_code` 兩個 key) |
| Playwright 對應 | `await page.goto(url)` → `waitForLoadState('domcontentloaded')` → 如果 `captcha_type === 'image'` 用 `page.locator(selector).first().screenshot({ type: 'png' })` |
| 必填 | `selector`(驗證碼圖片元素)、url 或 `{{site_url}}` |
| 選填 | `captcha_type`(預設 `image`)、`ms`(image 等待 captcha 元素秒數,預設 5)、`timeout`(等待會員輸入,最低 120s) |
| 副作用 | 寫入 `vars.account`、`vars.password`、`vars.code`、`vars.ga_code` |
| Log | `→ captcha_prefetch: 導航至 {url}` / `→ captcha_prefetch(image): 截圖 {selector}` / `🔐 等待會員輸入 帳密+驗證碼...` / `✅ 收到帳密+驗證碼` |

### 4.3 `input`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:578-625`:若 `value` 是「未解析的單一佔位符」(如 `{{code}}` 原樣保留),先 `request_ga(variable)` + `poll_ga(timeout >= 120s)` 拿到後寫入 vars 與 `value`;接著 `wait_for_selector` → `fillWithVerify` |
| Playwright 對應 | `locator.waitFor({ state: 'visible' })` → `locator.fill(value)` → 回讀 `locator.inputValue()` 驗證一致,不一致最多 3 次 |
| 必填 | `selector` |
| 選填 | `value`(可含佔位符)、`timeout` |
| Log | `→ input {selector} = {preview 20}` / `✔ 輸入值驗證通過(第 N 次)` |
| 注意 | **未解析佔位符偵測** 必須跟 Rust 完全一致:整個 trim 後 raw 與 rendered 相等,且 raw 形如 `{{name}}` 且 name 只含 `[A-Za-z0-9_]`。見 `browser.rs:1419-1431`。 |

### 4.4 `type`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:627-670`:`elem.click()` → JS 逐字 push value 並派發 `input`/`change` event;回讀不一致時 fallback 走 `fillWithVerify` |
| Playwright 對應 | `await locator.click()` → `await locator.pressSequentially(value, { delay: 30 })`(內建逐字打字)。回讀不一致則 fallback `locator.fill` + 驗證 |
| 必填 | `selector`、`value` |
| 選填 | `timeout` |
| 注意 | Playwright 的 `pressSequentially` 已派發 keydown/keypress/keyup + input event,行為比 Rust 自寫 JS 更可靠。 |

### 4.5 `click`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:563-576`:`wait_for_selector` → `find_element` → `elem.click()` |
| Playwright 對應 | `await page.locator(selector).first().click({ timeout: timeoutMs })` |
| 必填 | `selector` |

### 4.6 `select`(原生 `<select>`)

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:672-692`:JS 設 `el.value = "..."` + 派發 `change` |
| Playwright 對應 | `await page.locator(selector).selectOption(value)`(Playwright 內建會派發 change) |
| 必填 | `selector`、`value` |

### 4.7 `dropdown`(自訂下拉,非 `<select>`)

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:694-809`:點 trigger → 在 `option_selector`(預設 `[role="option"], [role="menuitem"], .dropdown-item, .ant-select-item, .el-select-dropdown__item, li`)輪詢 deadline,找文字 `contains` 或 `exact` 比對成功的「可見」項目,scrollIntoView + click;失敗時收集前 8 個可見選項作為 sample 寫入錯誤訊息 |
| Playwright 對應 | `await page.locator(triggerSelector).click()` → `await page.waitForFunction((args) => { /* 一樣的 isVisible + 匹配邏輯 */ }, { optionSelector, value, exact }, { timeout: timeoutMs, polling: 150 })`;失敗時自行 `page.evaluate` 收集 sample 文字 |
| 必填 | `selector`(trigger)、`value`(選項文字) |
| 選填 | `option_selector`(別名 `options_selector`)、`match_type`(`contains` / `exact`,預設 `contains`)、`timeout` |
| 注意 | **預設 option_selector 字串、isVisible 判斷規則、norm 函式邏輯,必須與 Rust JS 完全一致**(會直接影響後台模板已配置好的選擇器)。 |

### 4.8 `wait_text`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:831-876`:`expected` 為空 → 退化成 `wait_for_selector`;非空 → 輪詢檢查 `el` 可見 且 `innerText.indexOf(expected) !== -1` |
| Playwright 對應 | 若 `expected` 為空:`await page.locator(selector).first().waitFor({ state: 'visible', timeout: timeoutMs })`;否則 `await expect(page.locator(selector).first()).toContainText(expected, { timeout: timeoutMs })`(用 `@playwright/test` 的 expect)或自行 `waitForFunction` |
| 必填 | `selector` |
| 選填 | `expected`、`timeout` |

### 4.9 `wait_selector`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:878-886`:純粹 `wait_for_selector(selector, timeout)` |
| Playwright 對應 | `await page.locator(selector).first().waitFor({ state: 'visible', timeout: timeoutMs })` |
| 必填 | `selector` |

### 4.10 `wait_ga`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:888-966`:解析 `variable`(`step.variable` → `step.name` → `"code"`,並去掉外層 `{{}}`);若 `vars` 已有(來自先前 `captcha_prefetch`)直接沿用,否則 `request_ga(variable)` + `poll_ga(timeout >= 120s)`;拿到後寫入 vars 的 `{variable}` / `code` / `ga_code`,然後 `fillWithVerify(selector, code)` |
| Playwright 對應 | 同 Rust 流程;填入用 `locator.fill` + 回讀 |
| 必填 | `selector` |
| 選填 | `variable`(預設 `code`)、`timeout`(預設 120,最低 120) |

### 4.11 `captcha_image`(別名 `request_captcha`、`captcha`)

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:968-1051`:`attempt > 1` 時先 `notify_captcha_result(success=false)`;`wait_for_selector` → `elementHandle.screenshot('png')` → base64 → `request_captcha(image_data, variable)` → `poll_ga(timeout >= 120s)` → 寫入 vars。**不**自動填入 input(由後續 `input` 步驟透過 `{{code}}` 取出) |
| Playwright 對應 | `page.locator(selector).first().screenshot({ type: 'png' })` → `Buffer.toString('base64')` |
| 必填 | `selector` |
| 選填 | `variable`(預設 `code`)、`timeout`(預設 120,最低 120) |

### 4.12 `wait`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:811-829`:`seconds` 優先,其次 `ms / 1000`,再 fallback `value.parse::<f64>`,最後 1.0;以 100ms 為粒度檢查 `shouldStop` |
| Playwright 對應 | 自寫 `for (let elapsed = 0; elapsed < totalMs; elapsed += 100) { if (shouldStop()) throw; await sleep(min(100, totalMs - elapsed)); }`;**不**用 `page.waitForTimeout`(無法中途取消) |
| 必填 | (擇一)`seconds` / `ms` / `value` |

### 4.13 `screenshot`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:1053-1069`:`{name}_{HHmmss}.png` 存到 cwd |
| Playwright 對應 | `await page.screenshot({ path: \`${name}_${ts}.png\`, type: 'png' })` |
| 選填 | `name`(預設 `screenshot`) |

### 4.14 `js`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:1071-1077`:`page.evaluate(code)`,code 先過 template 替換 |
| Playwright 對應 | `await page.evaluate(code)`,**不**用 `new Function`(會被 Chromium block) |
| 必填 | `code` |

### 4.15 `scroll`

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:1079-1086`:`window.scrollBy(0, amount)`,預設 500 |
| Playwright 對應 | `await page.evaluate((amount) => window.scrollBy(0, amount), step.amount ?? 500)` |
| 選填 | `amount`(預設 500) |

### 4.16 未知 action

| 項目 | 內容 |
|---|---|
| Rust 行為 | `browser.rs:1088-1090`:log warn 並跳過(不算失敗) |
| TS 行為 | 一致 |

### 4.17 `check_error`(備案,目前 Rust 未實作但 form.php 有定義)

`form.php:238-242` 的 `ACTION_DEFS` 列了 `check_error`(錯誤偵測 + 回退步數),但 `browser.rs` 沒實作。**TS 版同樣不需實作**,維持 Rust 原有覆蓋面;若代理 B 要實作請另開 PR。

### 共用機制(每個步驟外層)

| 機制 | Rust | TS |
|---|---|---|
| 步驟重試 | `executor::execute_steps`:`max_retries`(預設 3),失敗間隔 5s | 同;讀 `step.max_retries ?? 3`,最少 1 |
| `should_stop` 檢查 | 每個 sleep 都檢查 | 用 `AbortController` + `signal.aborted` |
| 隨機間隔 | `rand_ms() % 700 + 500`,即 500~1199ms | 一樣的範圍,可用 `crypto.randomInt(500, 1200)` |
| 步驟前回調 | `send_step_callback(..., "running")` | 同 |
| 步驟成功回調 | `send_step_callback(..., "success")` | 同 |
| 步驟失敗回調 | `send_step_callback(..., "failed")` + 達到 max 時帶 reason | 同 |
| 達到 max 後 | `capture_failure_screenshot(page)` → `TaskFailure { reason, failure_image_data }` → 最終 `send_callback(status=3)` | 同 |
| 步驟前驗證碼檢查 | `check_captcha` 掃 9 個 selector,有則 `handle_captcha` 等待人工 | 同(主要防護銀行頁面跳出 cloudflare 等) |

---

## 5. 後端 API 介面(零改動)

**所有端點、HTTP method、header、payload、回應格式必須與 Rust 版完全一致**。基底路徑:`{server_url}/api/autobrowser/...`,所有請求帶 header `X-AutoBrowser-Key: {api_key}`(除 `login` 外)。

| # | 端點 | Method | Body / Query | 回應重點 | Rust 來源 |
|---|---|---|---|---|---|
| 1 | `/api/autobrowser/pending-tasks` | GET | — | `{ tasks: TaskData[] }` | `poller.rs:140-199` |
| 2 | `/api/autobrowser/step-callback` | POST | `{ task_id, order_no, step, step_name, action, attempt, max_retries, status: "running"\|"success"\|"failed", message, reason }` | 任意(失敗不致命) | `callback.rs:86-127` |
| 3 | `/api/autobrowser/request-ga` | POST | `{ task_id, order_no, variable }` | 任意 | `callback.rs:130-157` |
| 4 | `/api/autobrowser/request-captcha` | POST | `{ task_id, order_no, image_data, variable }` `image_data` 為 `data:image/png;base64,...` | `2xx` 視為成功 | `callback.rs:192-226` |
| 5 | `/api/autobrowser/set-needs-credentials` | POST | `{ task_id, order_no, captcha_type }` | 任意 | `browser.rs:530-539`(inline) |
| 6 | `/api/autobrowser/get-ga` | GET | query `task_id` | `{ ready: bool, ga_code?: string, code?: string }`;`ready=true` 且 `ga_code` 或 `code` 非空時回傳 | `callback.rs:230-273` |
| 7 | `/api/autobrowser/get-credentials` | GET | query `task_id` | `{ ready: bool, account?, password?, code? }`,三者皆非空才回傳 | `callback.rs:276-319` |
| 8 | `/api/autobrowser/captcha-result` | POST | `{ task_id, order_no, success: bool, reason }` | 任意 | `callback.rs:160-189` |
| 9 | `/api/autobrowser/callback` | POST | `{ task_id, order_no, status: 2\|3, reason, error_msg, timestamp, sign, failure_image_data? }` | `{ success: bool }` | `callback.rs:23-83` |

### HMAC 簽名(必須位元一致)

```
message = `${order_no}|${status}|${timestamp}`     // | 是 ASCII 0x7C
sign    = hex(HMAC_SHA256(secret = hmac_secret, message))
```

TS 實作:

```ts
import { createHmac } from 'node:crypto';
export function computeHmac(secret: string, orderNo: string, status: number, ts: number): string {
  return createHmac('sha256', secret)
    .update(`${orderNo}|${status}|${ts}`)
    .digest('hex');
}
```

**驗收測試**:代理 C 必須對同一組 `(secret, order_no, status, ts)` 比對 Rust 與 TS 輸出的 hex 字串,**完全相同才算過**。

### 輪詢/超時策略(原樣搬)

| 場景 | Rust 邏輯 | TS 實作 |
|---|---|---|
| `poll_ga` | 每 1s GET 一次,直到 `ready=true` 或 timeout 或 stop | 一致 |
| `poll_credentials` | 同上,但要 `account/password/code` 三者非空 | 一致 |
| 最終 callback 重試 | 3 次,間隔 10s | 一致 |
| `step-callback` timeout | 4s | 一致 |
| `request-ga` timeout | 5s | 一致 |
| `request-captcha` timeout | 10s | 一致 |
| `pending-tasks` timeout | 10s | 一致 |
| `callback` timeout | 10s | 一致 |
| `get-ga` / `get-credentials` 單次 timeout | 5s | 一致 |

---

## 6. 並發架構

### 結論:**Promise + `p-limit`**,**不**用 worker_threads

### 理由

1. **Playwright 是異步 I/O bound**:CDP 訊息走 WebSocket,沒有 CPU 熱點,event loop 足以撐 5~10 個並發瀏覽器(對標 Rust 的 `tokio::spawn`)。
2. **worker_threads 跟 Playwright 衝突**:Playwright 主要 API 是 process-wide singleton 風格,在 worker 裡再起 `chromium.launch` 會踩到 IPC / pipe handle 重複 listen。社群多次討論結論一致:**單一 Node process + 多個 browserContext** 是最穩健的拓樸。
3. **降低除錯難度**:全部跑在主進程,Electron 內 `process._debugProcess` 一鍵接 chrome devtools,棧追蹤完整。

### 拓樸

```
main process (Electron)
├─ Poller (setInterval ${cfg.poll_interval}s)
│   └─ 每輪呼叫 GET /api/autobrowser/pending-tasks
│       └─ 對每筆新 task,送進 p-limit 佇列
│
├─ p-limit(maxConcurrentTasks)
│   ├─ slot 1 → BrowserExecutor(task A) → chromium.launchPersistentContext(profile A)
│   ├─ slot 2 → BrowserExecutor(task B) → chromium.launchPersistentContext(profile B)
│   └─ slot 3 → BrowserExecutor(task C) → chromium.launchPersistentContext(profile C)
│
└─ 每個 Executor 結束:close context → rmSync(profileDir) → 釋放 slot
```

```ts
// src/main/poller.ts(節錄)
import pLimit from 'p-limit';

const limit = pLimit(cfg.maxConcurrentTasks);
const activeOrders = new Set<string>();

async function onPollTick() {
  const tasks = await fetchPendingTasks();
  for (const task of tasks) {
    if (activeOrders.has(task.order_no)) continue;
    if (activeOrders.size >= cfg.maxConcurrentTasks) {
      log(`⏸ 已達並發上限 ${cfg.maxConcurrentTasks},暫不啟動: ${task.order_no}`);
      continue;
    }
    activeOrders.add(task.order_no);
    log(`🚀 已啟動任務: ${task.order_no}`);
    void limit(() => runTask(task).finally(() => activeOrders.delete(task.order_no)));
  }
}
```

### 「停止」訊號傳遞

- 全域 `AbortController abortAll`;`stopPoller()` 呼叫 `abortAll.abort()`。
- 每個 Executor 內所有 `await` 點都檢查 `signal.aborted`(沿用 Rust 的 `should_stop.load(Ordering::Relaxed)` 散布在 sleep / poll 迴圈的模式)。
- Playwright 的 `locator.waitFor` 走 `timeout` 而非 abort signal,所以要在迴圈外圍 `Promise.race([action, abortPromise(signal)])`。

---

## 7. Chrome Profile 隔離

### 目標(對標 `browser_profile_dir`,`browser.rs:1433-1449`)

每筆訂單拿一個獨立 `userDataDir`,任務結束(成功或失敗)後**刪除整個資料夾**,確保:
- 不同訂單 cookie / localStorage / IndexedDB 不互相污染。
- 銀行的「記住裝置」cookie 不會在第二單沿用導致被風控。
- 任務內 captcha 等 session 資料天然乾淨。

### TS 實作

```ts
// src/main/profileDir.ts
import { tmpdir } from 'node:os';
import { mkdirSync, rmSync } from 'node:fs';
import { join } from 'node:path';

export function buildProfileDir(taskId: number, orderNo: string): string {
  const safeOrder = orderNo.replace(/[^A-Za-z0-9_-]/g, '_').slice(0, 80) || 'unknown';
  const dir = join(
    tmpdir(),
    'autobrowser-chrome-profiles',
    `task-${taskId}-${safeOrder}-${process.pid}-${Date.now()}`,
  );
  mkdirSync(dir, { recursive: true });
  return dir;
}

export function cleanupProfileDir(dir: string) {
  try { rmSync(dir, { recursive: true, force: true }); } catch { /* ignore */ }
}
```

### Playwright launch

```ts
import { chromium } from 'playwright-extra';
import stealth from 'puppeteer-extra-plugin-stealth';
chromium.use(stealth());

const ctx = await chromium.launchPersistentContext(profileDir, {
  executablePath: findSystemChrome() ?? undefined,   // 找不到時 Playwright 用自帶 Chromium
  headless: !cfg.show_browser,
  args: [
    '--no-sandbox',
    '--no-first-run',
    '--no-default-browser-check',
    '--start-maximized',
    '--disable-blink-features=AutomationControlled',
    ...(cfg.proxy ? [`--proxy-server=${cfg.proxy}`] : []),
  ],
  viewport: { width: 1366, height: 900 },
  ignoreDefaultArgs: ['--enable-automation'],         // stealth 額外保險
});
const page = await ctx.newPage();
```

### 清理時機

| 時機 | 動作 |
|---|---|
| 步驟全部成功 | `await ctx.close()` → `cleanupProfileDir(dir)` |
| 步驟失敗(reach max retries) | 同上,在 callback `status=3` 發送**之後**才刪(失敗截圖已收完) |
| 使用者按停止 | 同上 |
| Electron app 退出 | 啟動時掃 `os.tmpdir()/autobrowser-chrome-profiles/`,把超過 24h 的孤兒目錄一併清掉(Rust 版沒做,TS 順手做掉) |

### Windows 平台陷阱

Chrome 在 Windows 上關閉時偶爾還持有 `userDataDir` 內 lock file,`rmSync` 會丟 `EBUSY`。對策:`rmSync` 包 retry 3 次,每次間隔 500ms;最終失敗只 log 不 throw。

---

## 8. GUI 設計(對標 `ui/app.rs` egui 視窗)

### 主視窗尺寸

- 預設 `300 × 600`,可調整。
- `alwaysOnTop: true`(對標 `with_always_on_top()`)。
- Mac:`titleBarStyle: 'hiddenInset'` 取得原生半透明窄條;Windows:用 `frame: false` + 自繪 traffic light(可選,Phase 1 後)。

### 視覺風格(macOS Light)

| 區塊 | 顏色 | 字級 |
|---|---|---|
| 視窗背景 | `#F2F2F7` | — |
| 卡片背景 | `#FFFFFF` + 圓角 12 | — |
| 標題「AutoBrowser」 | `#1C1C1E` 16px bold | — |
| 灰色輔助文字 | `#8E8E93` | — |
| 啟動按鈕 | `#007AFF`(藍) | 14px white |
| 停止按鈕 | `#FF3B30`(紅) | 14px white |
| 設定按鈕 | 默認灰白底 | 14px |
| 運行中狀態指示 | `#30D158`(綠) + `🔄 掃單運行中` | 13px |
| 暫停狀態指示 | `#8E8E93` + `⏸ 已停止` | 13px |
| Log 面板背景 | `#1C1C1E` | — |
| Log 文字(分等級配色) | 同 Rust `LogEntry::egui_color`:錯誤 `#FF453A`、警告 `#FFD60A`、成功 `#30D158`、步驟 `#64D2FF`、一般 `#98989D` | 11px monospace |

### 主視窗版面(由上而下)

```
┌──────────────────────────────┐
│  AutoBrowser                 │  ← 標題列(自繪)
├──────────────────────────────┤
│ ┌──────────────────────────┐ │  ← 狀態卡(白底圓角)
│ │ 🔄 掃單運行中 │ 任務:2 │ 4s │ │
│ └──────────────────────────┘ │
│                              │
│ ┌──────────────────────────┐ │  ← 控制列(白底圓角)
│ │ [▶ 啟動]  [⏹ 停止]  [⚙ 設定] │
│ └──────────────────────────┘ │
│                              │
│  LOG                    [✖]  │  ← 日誌標題 + 清空鍵
│ ┌──────────────────────────┐ │
│ │ [21:38:01] 🔄 掃單服務..  │ │
│ │ [21:38:06] 📋 發現 1 個.. │ │
│ │ [21:38:06] 🚀 已啟動任務.. │ │
│ │ [21:38:08] ▶ 開始執行..   │ │  ← 黑底彩色 monospace
│ │ ...                       │ │
│ └──────────────────────────┘ │
└──────────────────────────────┘
```

### 設定對話框(獨立 BrowserWindow,modal)

| 欄位 | 型別 | Rust 來源 |
|---|---|---|
| 後端 URL | text | `server_url` |
| API Key | password | `api_key` |
| HMAC Secret | password | `hmac_secret` |
| 輪詢間隔(秒) | number,min 1 | `poll_interval` |
| 最大並發任務 | number,min 1 | `max_concurrent_tasks` |
| 瀏覽器類型 | dropdown:`chrome` / `cloakbrowser` | `browser_type`(`cloakbrowser` 暫保留,Phase 0 不實作) |
| 打開瀏覽器 | checkbox | `show_browser`(false 即 headless) |
| 代理(可選) | text | `proxy` |

按鈕:保存 / 取消;保存後若 poller 正在跑就 restart。

### IPC 事件(主→渲染)

```ts
// src/shared/ipc-channels.ts
export const Ch = {
  LogAppend:    'log/append',         // { ts, message, level }
  Countdown:    'state/countdown',    // { remaining: number }
  ActiveCount:  'state/active-count', // { count: number }
  TaskStarted:  'task/started',       // { order_no }
  TaskDone:     'task/done',          // { order_no, success }
  RunningState: 'state/running',      // { running: boolean }
} as const;
```

### 渲染→主(雙向 invoke)

```ts
window.autobrowser.startPoller();          // → main.poller.start()
window.autobrowser.stopPoller();           // → main.poller.stop()
window.autobrowser.getConfig();            // → AppConfig
window.autobrowser.saveConfig(cfg);        // → boolean
window.autobrowser.clearLogs();            // 純 renderer 端,無 IPC
```

---

## 9. 打包與分發(electron-builder)

### `package.json` 重點

```json
{
  "name": "autobrowser",
  "productName": "PCauto",
  "version": "2.0.0",
  "main": "dist/main/index.js",
  "scripts": {
    "dev": "concurrently \"vite\" \"tsc -p tsconfig.main.json -w\" \"electron .\"",
    "build": "vite build && tsc -p tsconfig.main.json",
    "dist:mac": "npm run build && electron-builder --mac",
    "dist:win": "npm run build && electron-builder --win",
    "dist:all": "npm run build && electron-builder -mw"
  }
}
```

### `electron-builder.yml`

```yaml
appId: com.autobrowser.app
productName: PCauto
asar: true
asarUnpack:
  - "node_modules/playwright-core/.local-browsers/**"   # Playwright 自帶 Chromium 不能進 asar
files:
  - "dist/**"
  - "package.json"
  - "!**/*.map"
extraResources:
  - { from: "resources", to: "." }
directories:
  output: release
mac:
  category: public.app-category.developer-tools
  target:
    - { target: dmg,  arch: [x64, arm64] }
    - { target: zip,  arch: [x64, arm64] }
  icon: resources/icon.icns
  hardenedRuntime: true
  gatekeeperAssess: false
  entitlements: build/entitlements.mac.plist
  entitlementsInherit: build/entitlements.mac.plist
win:
  target:
    - { target: nsis, arch: [x64] }
  icon: resources/icon.ico
nsis:
  oneClick: false
  perMachine: false
  allowToChangeInstallationDirectory: true
  shortcutName: PCauto
publish: null   # 暫不啟用自動更新,Phase 2 再說
```

### Playwright Chromium 處理

- 開發階段:`postinstall` 跑 `playwright install chromium`,把 Chromium 下載到 `~/Library/Caches/ms-playwright`(mac)或 `%USERPROFILE%\AppData\Local\ms-playwright`(win)。
- 打包階段:把 `node_modules/playwright-core/.local-browsers/chromium-XXXX/` 整個塞進 `extraResources`,並設 `PLAYWRIGHT_BROWSERS_PATH=0`(Playwright 會優先用 `node_modules/.local-browsers` 旁的同層目錄)。
- 同時保留 `findSystemChrome()` 邏輯:如果使用者本機已裝 Chrome,優先用系統的(體積較小、更新較快)。

### macOS 簽名(Phase 2 才需要)

- `electron-builder` 走 `CSC_LINK` + `CSC_KEY_PASSWORD` 環境變數。
- Notarization 用 `notarize-cli` 或 builder 內建 `notarize` 設定。
- Phase 0 / 1 階段可先用 ad-hoc signing(`codesign --sign -`),只在內部測試機跑。

### Windows 簽名(Phase 2 才需要)

- 同 `CSC_LINK` 機制,需有 OV/EV code signing 證書。
- 沒有證書時用 NSIS 預設(會跳 SmartScreen 警告,內部用無妨)。

### 安裝包大小預估

| 資源 | 大小 |
|---|---|
| Electron(壓縮) | ~60 MB |
| Chromium(壓縮) | ~120 MB |
| 我們的 JS + node_modules | ~10 MB |
| **合計 dmg / nsis** | **~180~200 MB** |

對比 Rust 版的 ~15 MB,代價是 +185MB,但換來開發迭代速度與 Playwright 生態。

---

## 10. 遷移路徑(分階段)

### Phase 0 — PoC:ACB captcha_prefetch + GA(預計 2~3 天)

**為什麼選 ACB?**
- `captcha_prefetch` 是最複雜的 action(整合導航 + 截圖 + 後端帳密輪詢 + 多分支 captcha_type)。
- ACB 後續還會走 `wait_ga`(TOTP),又驗證了 `request-ga` / `poll-ga` 鏈路。
- 一旦 ACB 跑通,其他普通銀行(SEAB / OCB)只是 navigate + input + click 的子集。
- 若 ACB 跑不通,代表整體架構有問題,要趁早重新評估。

**Phase 0 交付物**:
1. `autobrowser-next/` 專案骨架(目錄、tsconfig、vite、electron-builder.yml)。
2. Electron 啟動,主視窗顯示 AutoBrowser 標題與三按鈕(StatusCard / ControlBar / LogPanel 可以是靜態)。
3. `main/poller.ts` 跑通 `GET /api/autobrowser/pending-tasks`,log 在主視窗刷新。
4. **以下 7 個 action 完整實作並通過單元測試**:`navigate` / `captcha_prefetch` / `input` / `click` / `wait_ga` / `wait_selector` / `wait`。
5. 端到端跑通 ACB 一筆完整訂單(從 pending-tasks → 截圖驗證碼 → 等帳密 → 登入 → wait_ga → 填入金額 → 提交 → callback)。
6. `callback.ts` 全部 8 個函式 + HMAC 寫好;單元測試對照 Rust 輸出。

### Phase 1 — 補齊所有 action 與 GUI(預計 3~5 天)

1. 補齊剩餘 7 個 action:`type` / `select` / `dropdown` / `wait_text` / `captcha_image` / `screenshot` / `js` / `scroll`。
2. GUI 接 IPC,實況顯示倒計時 / 活躍任務數 / log 串流。
3. 設定對話框完成,可保存/讀取 `config.json`。
4. 跑通 SEAB / OCB 各一筆訂單(普通流程)。
5. macOS 與 Windows 都能 `npm run dist` 出包並開啟。
6. 把 Rust 版的 `automation.log` 比對欄位(timestamp、message)在 TS log 也保留。

### Phase 2 — 穩定性 + 簽名 + 灰度(預計 3~5 天)

1. macOS Notarization、Windows code sign。
2. 壓力測試:同時 3 筆任務跑 1 小時,觀察記憶體 / handle leak。
3. Crash reporter(Sentry 或 electron 內建 crashReporter)接入。
4. 跟 Rust 版灰度共存:同一台機器交替跑,確認 callback、step-callback、HMAC 等對後端而言完全等價。
5. 移除 Rust 版前先讓代理 C 跑完整回歸測試(SEAB / OCB / ACB 各 ≥ 3 筆)。

### Phase 3 — 切換 + 棄用 Rust(預計 1~2 天)

1. 正式發版,內部所有 runner 換成 Electron 版。
2. 保留 Rust 版 1 個 release 週期做 rollback 備援。
3. 觀察 1 週後 archive Rust 版,只保留 source。

---

## 11. 風險與緩解

### Risk 1 — Playwright 跟 stealth 對銀行風控的隱蔽性

**風險**:Rust + chromiumoxide 使用的是「真實系統 Chrome + `--disable-blink-features=AutomationControlled`」,Vietnam 銀行(尤其 ACB)對 `navigator.webdriver`、`window.chrome.runtime` 偵測較敏感。Playwright 預設啟動參數帶 `--enable-automation`,風控標記比 chromiumoxide 明顯。

**緩解**:
- 啟動時 `ignoreDefaultArgs: ['--enable-automation']` + `puppeteer-extra-plugin-stealth`(透過 playwright-extra)。
- 保留 Rust 版的 `navigator.webdriver` override 注入(`page.addInitScript`)。
- Phase 0 直接拿 ACB 測,如果觸發風控,改 fork stealth plugin 補強。
- 終極方案:走 CDP 連接系統已啟動的 Chrome(`launch({ channel: 'chrome' })` 或 `connectOverCDP`),完全沿用使用者的 Chrome,僅在新分頁執行。

### Risk 2 — Chrome `userDataDir` 在 Windows 釋放慢導致 `EBUSY`

**風險**:Rust 版只清一次 + ignore error,Electron 版若每次 `rmSync` 失敗會造成 `os.tmpdir()` 累積堆滿。

**緩解**:
- `rmSync` 包 3 次 retry + 500ms 間隔。
- 啟動時掃 `tmpdir/autobrowser-chrome-profiles/` 把 24h 以上的孤兒目錄一併清掉。
- 在 SettingsDialog 加個「清除所有暫存 profile」按鈕(Phase 1.5 可選)。

### Risk 3 — Electron 主進程與 Playwright 共用 event loop 可能阻塞 GUI

**風險**:雖然 Playwright 是 async,但 `page.evaluate(largeScript)` 或大圖 base64 編碼會吃 CPU,阻塞 IPC 響應,GUI 卡頓。

**緩解**:
- 大檔案 base64 編碼用 `Buffer.toString('base64')`(C++ 內建,不會 block)。
- 真有 CPU bound 操作放 `worker_threads`(僅這種純運算 worker,不放 Playwright)。
- `BrowserWindow` 視窗渲染用獨立進程,主進程慢只會延遲 IPC,不會凍住視窗。

### Risk 4 — TS 與 Rust 對「未解析佔位符」判定不一致 → `input` 不會觸發 `wait_ga`

**風險**:Rust 在 `input` action 中偵測「value 在 render 後跟 raw 完全相同 且 形如 `{{name}}`」就改去 `request_ga` + `poll_ga`(`browser.rs:583-615`)。如果 TS 端 trim / regex 差一個字元,流程會直接填 `{{code}}` 字串到表單,銀行頁噴 invalid code。

**緩解**:
- `unresolvedSinglePlaceholder` 函式寫單元測試覆蓋:`{{code}}` ✓、`{{ code }}` ✗(Rust 也不接受)、`pre{{code}}` ✗、`{{co-de}}` ✗、`{{code}}{{x}}` ✗。
- 跟 Rust `unresolved_single_placeholder`(`browser.rs:1419-1431`)做 fixture 對拍。

### Risk 5 — `dropdown` action 預設 option_selector 字串差一字 → 後台模板全壞

**風險**:Rust 預設值是 `[role="option"], [role="menuitem"], .dropdown-item, .ant-select-item, .el-select-dropdown__item, li`(`browser.rs:710`)。如果代理 B 拼錯一個 selector 或漏一個逗號,所有用預設值的後台模板會選不到項目。

**緩解**:
- 在 `src/main/actions/dropdown.ts` 用 **唯讀 const** 抽出:`export const DEFAULT_OPTION_SELECTOR = '[role="option"], [role="menuitem"], .dropdown-item, .ant-select-item, .el-select-dropdown__item, li';`
- 單元測試對拍 Rust 字串(用 fixture)。
- 同樣 isVisible 判斷規則的 JS 文字也建議用 `String.raw` 內嵌,並對拍。

### Risk 6 — Electron auto-launch / 開機自啟在 macOS 與 Rust 版行為不一致

**風險**:Rust 版沒做開機自啟,Electron 預設也沒;若後續被要求加,Mac 走 LaunchAgent、Win 走 registry,跨平台差異大。**Phase 0~2 暫不實作**,但要在 SettingsDialog 預留欄位佔位避免未來改動波及。

**緩解**:列為 Phase 3+ 待辦,不阻塞 PoC。

### Risk 7 — `step-callback` 在高頻調用下被後端 throttle / DB 寫爆

**風險**:每步 3 次 callback(running / success / failed),3 筆並發 × 10 步 = 90 次/任務,還有 4s timeout 可能堆積。

**緩解**:沿用 Rust 的「失敗只 log 不致命」策略;後端在 AutoBrowserController 已有 batch write,實測在 Rust 下穩定。TS 版不改設計,只確保 timeout 4s 與 Rust 一致。

---

## 12. 進度檢核點(給代理 B / C)

代理 B 在實作時,每完成下列任一里程碑請在 `AUTOBROWSER_Electron_PROGRESS.md` 的「代理 B」表格追加一行:

- [ ] `autobrowser-next/` 骨架可啟動(空主視窗 + Hello)
- [ ] `callback.ts` 8 個函式 + HMAC 單測通過
- [ ] `template.ts` 與 `unresolvedSinglePlaceholder` 單測通過
- [ ] `navigate` / `click` / `input` / `wait_selector` / `wait` 五個基本 action 通過
- [ ] `captcha_prefetch` + ACB 端到端跑通(Phase 0 完成)
- [ ] 剩餘 9 個 action 全部通過(Phase 1 完成)
- [ ] GUI 三大區塊(狀態 / 控制 / log)完整,設定對話框可保存
- [ ] mac dmg + win nsis 出包成功

代理 C 驗收時對下列項目逐項打勾:

- [ ] HMAC 對拍 Rust 完全相同
- [ ] `dropdown` 預設 option_selector 字串對拍
- [ ] `unresolvedSinglePlaceholder` fixture 對拍
- [ ] SEAB / OCB / ACB 各跑 ≥ 3 筆,全部 status=2 成功 callback
- [ ] 停止鍵在任意 action 中按下,task 正確 abort
- [ ] 設定變更後 poller restart,新 config 立即生效
- [ ] 並發上限 3 時,第 4 筆 task 不會被啟動,log 出現「已達並發上限」

---

## 附錄 A:Rust → TS 型別對照

| Rust | TS |
|---|---|
| `Option<String>` | `string \| undefined` |
| `Arc<Mutex<HashMap<String, String>>>` | `Map<string, string>`(主進程單線程,無需鎖) |
| `Arc<AtomicBool>` | `AbortController` |
| `mpsc::UnboundedSender<String>` | `(msg: string) => void`(IPC `webContents.send`) |
| `tokio::spawn` | `void asyncFn()` 或 `p-limit(...)` |
| `tokio::time::sleep(Duration::from_millis(n))` | `new Promise(r => setTimeout(r, n))` |
| `serde_json::Value` | `unknown` + zod schema |
| `anyhow::Result<T>` | `Promise<T>`(throw Error 即失敗) |
| `chrono::Local::now().format("%H:%M:%S")` | `new Date().toLocaleTimeString('zh-TW', { hour12: false })` |

## 附錄 B:`config.json` 範例(雙端共用)

```json
{
  "server_url": "http://localhost:8088",
  "api_key": "b3e377b9...c59",
  "hmac_secret": "b3e377b9...c59",
  "poll_interval": 5,
  "max_concurrent_tasks": 3,
  "browser_type": "chrome",
  "show_browser": true,
  "proxy": null
}
```

TS 端可額外接受 camelCase(`serverUrl` 等),但讀檔時優先 snake_case 以相容 Rust 版舊配置。

---

**END**
