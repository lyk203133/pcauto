# 設計:`branch` 分支判斷節點

日期:2026-05-30
範圍:`auto-browser`(執行引擎)+ `trader-system`(後台表單)
狀態:已通過 brainstorming,待實作

## 1. 問題

ACB 通用模板(`automation_tasks` id=1)的 step 5 會分岔:

- **第一次登入** → 頁面出現 OTP 按鈕(`xx`)→ 必須走 OTP 流程。
- **第二次(同一 profile 已登入過)** → `xx` 不存在,網站直接落到 step 9 對應的畫面。

目前模板只能寫死一條路。當 `xx` 不存在時,step 5 會一直重試 `xx`,直到 `max_retries` 用盡 → 整個任務失敗。

現有的唯一分支機制是 `on_error_selector` + `on_error_goto`,但它是「步驟**成功之後**才偵測錯誤元素」的**負向後置條件**,無法表達「步驟**執行前**先判斷頁面落在哪個狀態再決定走向」,也無法可靠區分「元素還沒 render」與「元素真的不存在」。

需要的是一個**前置的正向分支**:偵測頁面當前狀態,據此路由。

## 2. 方案決策

評估三種做法:

- **A. 獨立 `branch` 節點(採用)** — 新增一個不操作頁面、只做路由的控制流步驟。
- B. 在既有步驟上掛 `on_missing_selector` / `on_missing_goto` 守衛 — 新增面最小,但只能二元判斷(有/無),兩個元素賽跑不自然,且分支被綁死在某個動作步驟上。
- C. 把 `wait_selector` 擴成 `wait_any` — 重用既有動作,但讓「等待」語意混入控制流,命名混淆。

選 **A**:唯一能把「賽跑」當作一等公民、可重用、在步驟清單裡清楚可讀、且未來其他銀行遇到同樣「已登入就跳關」可直接套用的方案。它沿用既有的 `goto` 詞彙與 `MAX_GOTO_COUNT` 迴圈保護。

判斷訊號採 **race(賽跑)**:登入後等最多 T 秒,`xx`(OTP 按鈕)與 `yy`(step 9 標誌元素)誰先出現就走哪條,避免 `xx` render 太慢被誤判成「已登入」。

## 3. Schema(`auto-browser/src/main/types.ts`)

`StepAction` 新增選用欄位,並新增規則型別:

```ts
type GotoTarget = 'restart' | 'prev' | 'next' | 'requeue' | 'fail' | number; // number = 1-based 步驟
interface BranchRule { selector: string; goto: GotoTarget; }

// StepAction 新增:
branches?: BranchRule[];     // 有序;彼此賽跑
default_goto?: GotoTarget;   // 逾時前都沒命中時的去向(預設 'fail')
// 重用既有 `timeout` 作為賽跑視窗(預設 10s)與 `step_name`
```

`parseStepAction` 採白名單逐欄建構物件,因此必須**明確新增** `branches`(陣列,每筆 `{selector, goto}`)與 `default_goto` 的解析,`goto` 容忍字串/數字,與 `on_error_goto` 一致。

## 4. 賽跑語意(核心)

`branch` 步驟不操作頁面。每 ~200ms 輪詢一次,最多 `timeout` 秒。每一輪**依陣列順序**測試每條規則的 `selector`,第一個「可見或有非空文字」(重用 `checkOnError` 的可見性判定)的規則勝出 → 跳到其 `goto`。視窗結束都沒命中 → 走 `default_goto`。

## 5. 執行引擎整合(`auto-browser/src/main/browser/executor.ts`)

- 把 `checkOnError` 內部的 goto 解析抽成共用 `resolveGoto(target, idx, total)` → 回傳 `0-based idx | 'requeue' | 'fail'`,並擴充 `'next'`(idx+1)與 `'fail'`(丟 `TaskFailure`)。
- 主 `while` 迴圈在進入一般 handler/retry 區塊**之前**特判 `action === 'branch'`:
  1. 送 `running` callback。
  2. 跑賽跑邏輯。
  3. 命中 → 送 `success` callback、`gotoCount++`(重用既有 `MAX_GOTO_COUNT` 迴圈保護)、設定 `idx`、`continue`。
  4. 走到 `fail` → 送 `failed` callback + 失敗截圖,丟 `TaskFailure`。
  - `branch` 步驟不派發給動作 handler,也跳過 `on_error` 後置檢查。
- 在 action registry 註冊 `branch` 為 no-op,使 `lookupAction` 不會印警告。

## 6. 後台表單(`trader-system/resources/views/admin/automation_tasks/form.php`)

- 在 `ACTION_DEFS` 新增 `branch`,標記為自訂卡片渲染。
- 卡片內容:可重複的規則列清單,每列 = `selector` 輸入框 + `goto` `<select>`(重用既有 `gotoOptions` 產生器:restart / prev / 第 N 步,擴充 **next** 與 **fail**),搭配新增/刪除列按鈕、`default_goto` select、`timeout` 輸入框。

## 7. ACB id=1 改寫(step 5)

把寫死的 step 5 換成 `branch`:

```jsonc
{ "action": "branch", "step_name": "OTP/已登入 分支", "timeout": 12,
  "branches": [
    { "selector": "<xx: OTP 按鈕>",  "goto": "next" },  // 出現 → 進 OTP 步驟(6→8)
    { "selector": "<yy: step9 標誌>", "goto": 9 }        // 出現 → 跳過 OTP 直接到 step9
  ],
  "default_goto": "fail" }
```

OTP 處理步驟(6–8)維持原位;跳到 9 會乾淨地略過它們。實際 `xx`/`yy` selector 待提供前以 placeholder 佔位。

## 8. 假設與邊界

- 步驟 1–4(navigate / 填帳密 / 登入)維持現狀,分岔僅限 step 5。
- `MAX_GOTO_COUNT`(20)已可防止 branch→branch 無限迴圈。
- `default_goto: 'fail'` 為安全預設;若希望兩個標誌都沒出現時改為落入 OTP 流程,改成 `'next'`。
- 僅 TS `auto-browser`(package `autobrowser`)為實際執行端;原始碼中「Mirror of Rust」僅為歷史註解,無同步 Rust 程式需改。

## 9. 待補

- ACB id=1 的實際 `xx`(OTP 按鈕 selector)與 `yy`(step 9 標誌元素 selector)。
