# PCAUTO Electron 遷移進度

本檔案由三個子代理輪流寫入。請在自己的區塊下追加新條目(時間倒序),不要修改其他代理的條目。

---

## 代理 A — 技術方案(PCAUTO_Electron_PLAN.md)

| 時間 | 狀態 | 摘要 |
|---|---|---|
| 2026-05-16 | 進行中 | 完成 §1 技術棧選型(Electron + React + TS + Playwright + playwright-extra/stealth + electron-builder) |
| 2026-05-16 | 進行中 | 完成 §2 目錄結構(`pcauto-next/` 骨架,主進程 / 渲染 / preload / shared 分離,每個 action 獨立檔) |
| 2026-05-16 | 進行中 | 完成 §3 模組對應表(main.rs/poller.rs/browser.rs/callback.rs/models.rs/template.rs/config.rs/ui/ → TS 1:1 對映) |
| 2026-05-16 | 進行中 | 完成 §4 Step Action 完整移植清單(15 個 action:navigate/captcha_prefetch/input/type/click/select/dropdown/wait_text/wait_selector/wait_ga/captcha_image/wait/screenshot/js/scroll,每個含 Rust file:line 引用、Playwright API、簽名) |
| 2026-05-16 | 進行中 | 完成 §5 後端 API 介面(9 個端點 1:1 對拍 callback.rs,HMAC-SHA256 公式與 timeout 全部列表) |
| 2026-05-16 | 進行中 | 完成 §6 並發架構(選 Promise + p-limit,worker_threads 已排除並列出 3 條理由) |
| 2026-05-16 | 進行中 | 完成 §7 Chrome profile 隔離(buildProfileDir / cleanupProfileDir,Windows EBUSY retry 對策) |
| 2026-05-16 | 進行中 | 完成 §8 GUI 設計(主視窗 ASCII 草圖、macOS 配色 token、SettingsDialog 8 欄位、IPC channel 列表) |
| 2026-05-16 | 進行中 | 完成 §9 打包與分發(electron-builder.yml 範本、Playwright Chromium asarUnpack、mac/win 雙平台) |
| 2026-05-16 | 進行中 | 完成 §10 遷移路徑(Phase 0~3,Phase 0 PoC 鎖定 ACB:captcha_prefetch + wait_ga 鏈路最複雜) |
| 2026-05-16 | 進行中 | 完成 §11 風險與緩解(共列 7 個風險:stealth/銀行風控、Windows EBUSY、event loop 阻塞、佔位符判定、dropdown 預設字串、auto-launch、step-callback throttle) |
| 2026-05-16 | 完成 | PCAUTO_Electron_PLAN.md 全文交付,共 862 行 / 34242 字元 / 12 章 + 2 附錄 |

---

## 代理 B — UI 與 Rust 重構

| 時間 | 狀態 | 摘要 |
|---|---|---|
| 2026-05-16 | 進行中 | 建立 `pcauto-next/` 專案骨架(package.json + tsconfig*.json + vite.config + electron-builder.yml + .gitignore + config.json.example + README.md) |
| 2026-05-16 | 進行中 | 建立 shared 型別(ipc-channels.ts、config.ts),主進程 types.ts(對標 models.rs,含 coerceOptU64/I32/F64 與 parseStepAction/parseTaskData) |
| 2026-05-16 | 進行中 | 完成 template.ts(對標 template.rs)+ unresolvedSinglePlaceholder(對拍 browser.rs:1419-1431) |
| 2026-05-16 | 進行中 | 完成 config.ts(雙路徑載入)、logger.ts(classifyLevel 對拍 LogEntry::classify)、profileDir.ts(含 24h 孤兒掃除) |
| 2026-05-16 | 進行中 | 完成 api/http.ts + api/callback.ts(9 個端點,HMAC-SHA256 一致;timeout 4/5/10s 全對拍) |
| 2026-05-16 | 進行中 | 完成 15 個 step action 各一檔(actions/*.ts):navigate / captcha_prefetch / input / type / click / select / dropdown / wait_text / wait_selector / wait_ga / captcha_image / wait / screenshot / js / scroll,含 DEFAULT_OPTION_SELECTOR 字串對拍 |
| 2026-05-16 | 進行中 | 完成 browser/executor.ts(對標 BrowserExecutor;captcha 9 selector watchdog + step 重試 + 失敗截圖 + 隨機 500-1199ms 間隔) |
| 2026-05-16 | 進行中 | 完成 poller.ts(對標 poller.rs,p-limit 並發控管 + 最終 callback 3 次重試 + AbortController 停止訊號) |
| 2026-05-16 | 進行中 | 完成 IPC 層(main/ipc.ts + main/index.ts + preload/index.ts)與 React 渲染端(App / StatusCard / ControlBar / LogPanel / SettingsDialog + Zustand store + macOS 配色 globals.css) |
| 2026-05-16 | 目錄調整 | 依用戶指示移除 Rust 檔案、把 `pcauto-next/*` 上提至 `pcauto/` 根目錄；`rust` 分支保留原樣 |
| 2026-05-17 | 修復 | 修正 tsconfig.main.json / tsconfig.preload.json 的 outDir（從 `dist/main` 和 `dist/preload` 改為 `dist`，rootDir 保持 `src`），使 `dist/main/index.js` 和 `dist/preload/index.js` 路徑正確對應 `package.json` `main` 入口 |
| 2026-05-17 | 修復 | 降版 `p-limit` 至 v3（CJS 相容），修正 `LimitFunction` 型別 import 改用 `ReturnType<typeof pLimit>` |
| 2026-05-17 | 驗證 | `npm run build` 全通過（main + preload + renderer）；`electron .` 啟動無崩潰 |

---

## 代理 C — 測試驗收

| 時間 | 狀態 | 摘要 |
|---|---|---|

---

## 里程碑

- [ ] A 完成:`PCAUTO_Electron_PLAN.md` 通過
- [ ] B 完成:`pcauto/`(根目錄)可 build 並啟動
- [ ] B 完成:所有 step actions 移植到 Playwright
- [ ] C 完成:基本功能煙霧測試
- [ ] C 完成:ACB captcha_prefetch + GA 端到端測試
