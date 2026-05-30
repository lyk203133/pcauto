# `branch` 條件分支節點 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在自動化引擎新增一個 `branch` 控制流步驟,以 race 偵測 `xx`/`yy` 誰先出現決定跳往哪一步,解決 ACB 通用模板 step 5「第一次出 OTP、第二次已登入直接跳 step9」的分岔。

**Architecture:** 純邏輯(`resolveGoto` / `pickBranchGoto` / 解析)放在零依賴、可單元測試的 `branch.ts`;`types.ts` 與 `executor.ts` 只做接線,以 `tsc` 編譯為驗證關卡。`branch` 在 executor 主迴圈特判(action handler 無法改 `idx`),沿用既有 `goto` 詞彙與 `MAX_GOTO_COUNT` 迴圈保護。後台 `form.php` 新增「條件分支」卡片。

**Tech Stack:** TypeScript (Node 22, `node --test --experimental-strip-types`, 零新依賴)、Playwright/Electron、PHP 模板。

設計來源:`auto-browser/docs/superpowers/specs/2026-05-30-branch-node-design.md`

---

## 檔案結構

| 檔案 | 責任 |
|------|------|
| `auto-browser/src/main/branch.ts`(新增)| 零依賴純邏輯:型別 `GotoTarget`/`BranchRule`/`GotoResolution`、`resolveGoto`、`pickBranchGoto`、`parseBranches`、`parseGotoTarget` |
| `auto-browser/src/main/branch.test.ts`(新增)| 上述純邏輯的 node:test 測試 |
| `auto-browser/src/main/types.ts`(改)| `StepAction` 新增 `branches`/`default_goto`;`parseStepAction` 呼叫 `parseBranches`/`parseGotoTarget` |
| `auto-browser/src/main/browser/executor.ts`(改)| 抽 `isSelectorPresent`;`checkOnError` 改用 `resolveGoto`;新增 `raceBranch`;主迴圈特判 `branch` |
| `auto-browser/src/main/actions/index.ts`(改)| 註冊 `branch` no-op,避免 `lookupAction` 警告 |
| `trader-system/resources/views/admin/automation_tasks/form.php`(改)| 「條件分支」卡片:規則清單 + default_goto + timeout;序列化 |
| `automation_tasks` id=1 資料(手動)| step 5 改為 branch 步驟 |

> 注意:`branch.ts` **不得** import `types.ts`(會引入無副檔名相對 import,使 `node --test` 解析失敗)。numeric 強制轉換在 `branch.ts` 內自帶 `toU64`。

---

## Task 1: 純邏輯 `resolveGoto` + `pickBranchGoto`

**Files:**
- Create: `auto-browser/src/main/branch.ts`
- Test: `auto-browser/src/main/branch.test.ts`

- [ ] **Step 1: 寫失敗測試**

`auto-browser/src/main/branch.test.ts`:
```ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveGoto, pickBranchGoto, type BranchRule } from './branch.ts';

test('resolveGoto: restart → 0', () => assert.equal(resolveGoto('restart', 5, 10), 0));
test('resolveGoto: undefined → 0 (預設 restart)', () => assert.equal(resolveGoto(undefined, 5, 10), 0));
test('resolveGoto: prev → idx-1', () => assert.equal(resolveGoto('prev', 5, 10), 4));
test('resolveGoto: prev 在第一步 → 0', () => assert.equal(resolveGoto('prev', 0, 10), 0));
test('resolveGoto: next → idx+1', () => assert.equal(resolveGoto('next', 4, 10), 5));
test('resolveGoto: requeue', () => assert.equal(resolveGoto('requeue', 1, 10), 'requeue'));
test('resolveGoto: fail', () => assert.equal(resolveGoto('fail', 1, 10), 'fail'));
test('resolveGoto: 數字 9 (1-based) → 8', () => assert.equal(resolveGoto(9, 0, 10), 8));
test('resolveGoto: 數字字串 "9" → 8', () => assert.equal(resolveGoto('9', 0, 10), 8));
test('resolveGoto: 未知字串 → 0', () => assert.equal(resolveGoto('???', 3, 10), 0));

const rules: BranchRule[] = [
  { selector: '#otp', goto: 'next' },
  { selector: '.s9', goto: 9 },
];
test('pickBranchGoto: 依序第一個命中者勝', () => {
  assert.equal(pickBranchGoto(rules, (s) => s === '#otp'), 'next');
});
test('pickBranchGoto: 只有第二個命中 → 其 goto', () => {
  assert.equal(pickBranchGoto(rules, (s) => s === '.s9'), 9);
});
test('pickBranchGoto: 兩個都在 → 順序優先第一個', () => {
  assert.equal(pickBranchGoto(rules, () => true), 'next');
});
test('pickBranchGoto: 都不在 → null', () => {
  assert.equal(pickBranchGoto(rules, () => false), null);
});
test('pickBranchGoto: 空 selector 規則跳過', () => {
  assert.equal(pickBranchGoto([{ selector: '', goto: 5 }, { selector: '.s9', goto: 9 }], (s) => s === '.s9'), 9);
});
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd auto-browser && node --test --experimental-strip-types src/main/branch.test.ts`
Expected: FAIL — `Cannot find module './branch.ts'`(檔案尚未建立)

- [ ] **Step 3: 寫最小實作**

`auto-browser/src/main/branch.ts`:
```ts
// 零依賴的分支控制流純邏輯。不得 import './types'（會引入無副檔名相對 import，
// 使 node --test 的 ESM 解析失敗）。numeric 強制轉換自帶 toU64。

export type GotoTarget = 'restart' | 'prev' | 'next' | 'requeue' | 'fail' | number;
export interface BranchRule { selector: string; goto: GotoTarget }
export type GotoResolution = number | 'requeue' | 'fail';

/** 解析為 0-based 步驟索引，或控制 sentinel。total 用於語意參考（next 不超過步數）。 */
export function resolveGoto(
  target: string | number | undefined | null,
  currentIdx: number,
  total: number,
): GotoResolution {
  if (target === undefined || target === null) return 0; // 預設 restart
  if (typeof target === 'number') {
    return Number.isFinite(target) && target >= 1 ? Math.trunc(target) - 1 : 0;
  }
  const t = target.trim().toLowerCase();
  if (t === 'restart') return 0;
  if (t === 'prev') return Math.max(0, currentIdx - 1);
  if (t === 'next') return Math.min(currentIdx + 1, total);
  if (t === 'requeue') return 'requeue';
  if (t === 'fail') return 'fail';
  if (/^\d+$/.test(t)) {
    const n = Number(t);
    return n >= 1 ? n - 1 : 0;
  }
  return 0;
}

/** 依陣列順序回傳第一條 selector 為 present 的規則 goto；皆不在回傳 null。 */
export function pickBranchGoto(
  branches: BranchRule[],
  isPresent: (selector: string) => boolean,
): GotoTarget | null {
  for (const rule of branches) {
    if (rule.selector && isPresent(rule.selector)) return rule.goto;
  }
  return null;
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd auto-browser && node --test --experimental-strip-types src/main/branch.test.ts`
Expected: PASS — `# pass 15 / # fail 0`

- [ ] **Step 5: Commit**

```bash
cd auto-browser
git add src/main/branch.ts src/main/branch.test.ts
git commit -m "feat(branch): resolveGoto + pickBranchGoto 純邏輯

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 2: 分支解析 `parseBranches` + `parseGotoTarget`

**Files:**
- Modify: `auto-browser/src/main/branch.ts`
- Test: `auto-browser/src/main/branch.test.ts`

- [ ] **Step 1: 追加失敗測試**(附到 `branch.test.ts` 末端)

```ts
import { parseBranches, parseGotoTarget } from './branch.ts';

test('parseBranches: 解析 selector + goto', () => {
  const r = parseBranches([{ selector: '#otp', goto: 'next' }, { selector: '.s9', goto: 9 }]);
  assert.deepEqual(r, [{ selector: '#otp', goto: 'next' }, { selector: '.s9', goto: 9 }]);
});
test('parseBranches: goto 數字字串轉數字', () => {
  assert.deepEqual(parseBranches([{ selector: '.s9', goto: '9' }]), [{ selector: '.s9', goto: 9 }]);
});
test('parseBranches: 缺 selector 的規則被丟棄', () => {
  assert.deepEqual(parseBranches([{ goto: 5 }, { selector: '.ok', goto: 'fail' }]), [{ selector: '.ok', goto: 'fail' }]);
});
test('parseBranches: 非陣列 → undefined', () => assert.equal(parseBranches('x'), undefined));
test('parseBranches: 空陣列 → undefined', () => assert.equal(parseBranches([]), undefined));
test('parseGotoTarget: 字串保留', () => assert.equal(parseGotoTarget('fail'), 'fail'));
test('parseGotoTarget: 數字字串轉數字', () => assert.equal(parseGotoTarget('9'), 9));
test('parseGotoTarget: 缺值 → undefined', () => assert.equal(parseGotoTarget(undefined), undefined));
```

- [ ] **Step 2: 跑測試確認失敗**

Run: `cd auto-browser && node --test --experimental-strip-types src/main/branch.test.ts`
Expected: FAIL — `parseBranches` / `parseGotoTarget` 不存在(export 未定義)

- [ ] **Step 3: 在 `branch.ts` 末端追加實作**

```ts
function toU64(v: unknown): number | undefined {
  if (typeof v === 'number') return Number.isFinite(v) && v >= 0 ? Math.trunc(v) : undefined;
  if (typeof v === 'string') {
    const s = v.trim();
    if (!/^\d+$/.test(s)) return undefined;
    return Number(s);
  }
  return undefined;
}

/** 把後端傳來的 goto 原值正規化為 GotoTarget（字串保留、純數字字串轉 number）。 */
export function parseGotoTarget(v: unknown): GotoTarget | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : undefined;
  if (typeof v === 'string') {
    const s = v.trim();
    if (s === '') return undefined;
    const n = toU64(s);
    return n !== undefined ? n : s;
  }
  return undefined;
}

/** 解析 branches 陣列；丟棄缺 selector 或 goto 無法解析的規則；無有效規則回傳 undefined。 */
export function parseBranches(v: unknown): BranchRule[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out: BranchRule[] = [];
  for (const item of v) {
    if (!item || typeof item !== 'object') continue;
    const o = item as Record<string, unknown>;
    const selector = typeof o['selector'] === 'string' ? (o['selector'] as string) : undefined;
    const goto = parseGotoTarget(o['goto']);
    if (selector && selector.length > 0 && goto !== undefined) out.push({ selector, goto });
  }
  return out.length > 0 ? out : undefined;
}
```

- [ ] **Step 4: 跑測試確認通過**

Run: `cd auto-browser && node --test --experimental-strip-types src/main/branch.test.ts`
Expected: PASS — `# pass 23 / # fail 0`

- [ ] **Step 5: Commit**

```bash
cd auto-browser
git add src/main/branch.ts src/main/branch.test.ts
git commit -m "feat(branch): parseBranches + parseGotoTarget 解析

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 3: `types.ts` 接線(schema + parseStepAction)

**Files:**
- Modify: `auto-browser/src/main/types.ts:12-34`(StepAction)、`:122-173`(parseStepAction)

- [ ] **Step 1: StepAction 新增欄位**

在 `types.ts` 開頭 import 區(`export { DEFAULT_CONFIG } ...` 之後)加入:
```ts
import type { BranchRule, GotoTarget } from './branch';
export type { BranchRule, GotoTarget } from './branch';
```
在 `StepAction` interface(`on_error_request?: string;` 那行之後、`}` 之前)加入:
```ts
  branches?: BranchRule[];        // action==='branch' 時的有序賽跑規則
  default_goto?: GotoTarget;      // branch 逾時皆未命中時的去向（預設 'fail'）
```

- [ ] **Step 2: parseStepAction 解析新欄位**

在 `types.ts` 檔案上方既有 import 區補：
```ts
import { parseBranches, parseGotoTarget } from './branch';
```
在 `parseStepAction` 的 return 物件中(`on_error_request: asString(r['on_error_request']),` 之後)加入:
```ts
    branches: parseBranches(r['branches']),
    default_goto: parseGotoTarget(r['default_goto']),
```

- [ ] **Step 3: 編譯驗證(型別關卡)**

Run: `cd auto-browser && npx tsc -p tsconfig.main.json --noEmit`
Expected: 無錯誤輸出(exit 0)

- [ ] **Step 4: Commit**

```bash
cd auto-browser
git add src/main/types.ts
git commit -m "feat(branch): StepAction 加 branches/default_goto 並解析

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 4: executor 重構 — 抽 `isSelectorPresent`、`checkOnError` 改用 `resolveGoto`

**Files:**
- Modify: `auto-browser/src/main/browser/executor.ts:30-34`(imports)、`:332-367`(checkOnError)、`:466`(呼叫端)

行為必須與現狀一致(僅重構),這步不改外部行為。

- [ ] **Step 1: import 純邏輯**

在 executor.ts import 區(`import { buildProfileDir, cleanupProfileDir } ...` 附近)加入:
```ts
import { resolveGoto, pickBranchGoto, type GotoResolution } from '../branch';
```

- [ ] **Step 2: 新增共用 `isSelectorPresent`**(放在 `checkOnError` 上方)

```ts
/** 與 checkOnError 共用的可見性判定：元素存在且（可見 或 有非空文字）。 */
async function isSelectorPresent(page: Page, selector: string): Promise<boolean> {
  const script = `(function() {
    var el = document.querySelector(${JSON.stringify(selector)});
    if (!el) return false;
    var visible = !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
    var hasText = (el.innerText || el.textContent || '').trim().length > 0;
    return visible || hasText;
  })()`;
  try {
    return (await page.evaluate(script)) as boolean;
  } catch {
    return false; // 頁面導航中 → 視為尚未出現
  }
}
```

- [ ] **Step 3: 改寫 `checkOnError` 使用共用函式 + `resolveGoto`**

把現有 `checkOnError`(types.ts 行 332-367 對應的整個函式)替換為:
```ts
/** 步驟成功後檢查 on_error_selector，輪詢至多 on_error_timeout 秒（預設 2）。
 *  回傳要跳轉的 0-based index / 'requeue' / 'fail'，或 null 表示無錯誤繼續。 */
async function checkOnError(
  page: Page,
  step: import('../types').StepAction,
  currentIdx: number,
  total: number,
): Promise<GotoResolution | null> {
  if (!step.on_error_selector) return null;
  const timeoutMs = (step.on_error_timeout ?? 2) * 1000;
  const deadline = Date.now() + timeoutMs;
  let detected = false;
  while (Date.now() < deadline) {
    if (await isSelectorPresent(page, step.on_error_selector)) { detected = true; break; }
    await new Promise<void>((r) => setTimeout(r, 200));
  }
  if (!detected) return null;
  return resolveGoto(step.on_error_goto, currentIdx, total);
}
```

- [ ] **Step 4: 更新呼叫端傳入 `total`**

`executor.ts` 內 `const gotoResult = await checkOnError(page, step, idx);` 改為:
```ts
        const gotoResult = await checkOnError(page, step, idx, total);
```
(`total` 已於 `executeSteps` 內定義為 `steps.length`。)

- [ ] **Step 5: 編譯驗證**

Run: `cd auto-browser && npx tsc -p tsconfig.main.json --noEmit`
Expected: 無錯誤輸出(exit 0)

- [ ] **Step 6: Commit**

```bash
cd auto-browser
git add src/main/browser/executor.ts
git commit -m "refactor(executor): 抽 isSelectorPresent、checkOnError 改用 resolveGoto

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 5: executor `branch` 執行 + 註冊 no-op

**Files:**
- Modify: `auto-browser/src/main/browser/executor.ts`(新增 `raceBranch`、主迴圈特判)
- Modify: `auto-browser/src/main/actions/index.ts`

- [ ] **Step 1: 新增 `raceBranch`**(放在 `checkOnError` 之後、`executeSteps` 之前)

```ts
/** branch 步驟的賽跑：每 200ms 依序測試 branches[].selector，第一個 present 勝。
 *  逾時前皆未命中 → 採 default_goto（預設 'fail'）。回傳已解析的去向。 */
async function raceBranch(
  page: Page,
  step: import('../types').StepAction,
  idx: number,
  total: number,
  shouldStop: () => boolean,
): Promise<{ resolved: GotoResolution; matched: boolean } | { stopped: true }> {
  const branches = step.branches ?? [];
  const timeoutMs = (step.timeout ?? 10) * 1000;
  const deadline = Date.now() + timeoutMs;

  while (Date.now() < deadline) {
    if (shouldStop()) return { stopped: true };
    const present = new Set<string>();
    for (const rule of branches) {
      if (!rule.selector) continue;
      if (await isSelectorPresent(page, rule.selector)) { present.add(rule.selector); break; }
    }
    const goto = pickBranchGoto(branches, (s) => present.has(s));
    if (goto !== null) return { resolved: resolveGoto(goto, idx, total), matched: true };
    await new Promise<void>((r) => setTimeout(r, 200));
  }
  return { resolved: resolveGoto(step.default_goto ?? 'fail', idx, total), matched: false };
}
```

- [ ] **Step 2: 主迴圈特判 `branch`**

在 `executeSteps` 的 `while (idx < steps.length) {` 內,計算出 `stepName` 與 `stepKey` 之後、`let attempt = 0;` 之前,插入:
```ts
      // ── branch：控制流節點，不派發 handler，不做 on_error 後置檢查 ──
      if (action === 'branch') {
        await sendStepCallback({
          cfg, taskId: task.task_id, orderNo: task.order_no, step: stepKey, stepName,
          action, attempt: 1, maxRetries: 1, status: 'running',
          message: `分支判斷中（最多 ${step.timeout ?? 10}s）`,
        });
        const r = await raceBranch(page, step, idx, total, shouldStop);
        if ('stopped' in r) { broadcastLog('⏹ 用戶已停止'); return { ok: false }; }
        const { resolved, matched } = r;

        if (resolved === 'requeue') {
          broadcastLog(`  ♻️ 分支步驟 ${idx + 1} → 重置任務並重新排隊`);
          await requeueTask(cfg, task.task_id, task.order_no);
          return { ok: false };
        }
        if (resolved === 'fail') {
          const reason = matched
            ? `步驟 ${idx + 1}「${stepName}」分支命中 fail 規則,中斷任務`
            : `步驟 ${idx + 1}「${stepName}」分支判斷逾時(${step.timeout ?? 10}s 內規則皆未命中),中斷任務`;
          broadcastLog(`  ❌ ${reason}`);
          await sendStepCallback({
            cfg, taskId: task.task_id, orderNo: task.order_no, step: stepKey, stepName,
            action, attempt: 1, maxRetries: 1, status: 'failed', message: reason, reason,
          });
          // eslint-disable-next-line @typescript-eslint/no-throw-literal
          throw { reason, failure_image_data: await captureFailureScreenshot(page, stepName) };
        }

        gotoCount += 1;
        if (gotoCount > MAX_GOTO_COUNT) {
          const reason = `分支跳轉超過 ${MAX_GOTO_COUNT} 次,中止任務`;
          broadcastLog(`  ❌ ${reason}`);
          // eslint-disable-next-line @typescript-eslint/no-throw-literal
          throw { reason, failure_image_data: await captureFailureScreenshot(page, stepName) };
        }
        broadcastLog(`  ↳ 分支${matched ? '命中' : '逾時預設'} → 跳至步驟 ${resolved + 1}`);
        await sendStepCallback({
          cfg, taskId: task.task_id, orderNo: task.order_no, step: stepKey, stepName,
          action, attempt: 1, maxRetries: 1, status: 'success',
          message: `分支${matched ? '命中' : '逾時預設'} → 步驟 ${resolved + 1}`,
        });
        idx = resolved;
        await new Promise<void>((r) => setTimeout(r, randMs()));
        continue;
      }
```

- [ ] **Step 3: 註冊 `branch` no-op**

`auto-browser/src/main/actions/index.ts` 的 `actionRegistry` 物件中加入一行(放在 `screenshot,` 之後):
```ts
  branch: async () => { /* 控制流由 executor 特判，handler 不執行頁面操作 */ },
```

- [ ] **Step 4: 編譯驗證**

Run: `cd auto-browser && npx tsc -p tsconfig.main.json --noEmit`
Expected: 無錯誤輸出(exit 0)

- [ ] **Step 5: 手動冒煙(無瀏覽器,驗證 race 邏輯接線)**

建立臨時驗證腳本 `auto-browser/src/main/_branch_smoke.test.ts`:
```ts
import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveGoto, pickBranchGoto } from './branch.ts';

// 模擬 raceBranch 的純決策部分：xx 先出現走 next；只有 yy 走 step9；都沒 → default fail
test('smoke: xx 出現 → next(idx+1)', () => {
  const branches = [{ selector: '#otp', goto: 'next' as const }, { selector: '.s9', goto: 9 }];
  const g = pickBranchGoto(branches, (s) => s === '#otp');
  assert.equal(resolveGoto(g, 4, 12), 5);
});
test('smoke: 只有 yy → step9(0-based 8)', () => {
  const branches = [{ selector: '#otp', goto: 'next' as const }, { selector: '.s9', goto: 9 }];
  const g = pickBranchGoto(branches, (s) => s === '.s9');
  assert.equal(resolveGoto(g, 4, 12), 8);
});
test('smoke: 都沒 → default fail', () => {
  assert.equal(resolveGoto('fail', 4, 12), 'fail');
});
```
Run: `cd auto-browser && node --test --experimental-strip-types src/main/_branch_smoke.test.ts`
Expected: PASS — `# pass 3`
然後刪除臨時檔:`rm auto-browser/src/main/_branch_smoke.test.ts`

- [ ] **Step 6: Commit**

```bash
cd auto-browser
git add src/main/browser/executor.ts src/main/actions/index.ts
git commit -m "feat(branch): executor raceBranch 執行 + 註冊 branch no-op

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 6: 後台表單「條件分支」卡片

**Files:**
- Modify: `trader-system/resources/views/admin/automation_tasks/form.php`

此 repo 無前端測試;驗證為「載入編輯頁、操作、看 JSON 預覽」。

- [ ] **Step 1: ACTION_DEFS 加入 branch**

在 `form.php` `ACTION_DEFS` 物件(`check_error:` 條目之後、結尾 `};` 之前)加入:
```js
  branch: { label: '條件分支', color: '#6610f2', custom: true, fields: [] },
```

- [ ] **Step 2: renderStepCard 對 branch 改用自訂卡片內容並隱藏錯誤分支**

在 `renderStepCard`,把:
```js
  // ── 錯誤分支（所有 action 均可設定）─────────────────────────────
  const errorBranchHtml = renderErrorBranch(step, i);
```
改為:
```js
  // branch 用自訂內容；其餘 action 顯示錯誤分支
  const isBranch = uiAction === 'branch';
  const errorBranchHtml = isBranch ? '' : renderErrorBranch(step, i);
```
並把 card 結尾的:
```js
      ${def.fields.length || uiAction === 'navigate' ? `<div class="step-fields"><div class="form-row">${fieldsHtml}${navigateExtra}</div></div>` : ''}
      ${errorBranchHtml}
```
改為:
```js
      ${isBranch ? renderBranchBody(step, i) : (def.fields.length || uiAction === 'navigate' ? `<div class="step-fields"><div class="form-row">${fieldsHtml}${navigateExtra}</div></div>` : '')}
      ${errorBranchHtml}
```

- [ ] **Step 3: 新增 branch 卡片渲染與 goto 選項產生器**

在 `renderErrorBranch` 函式定義之前(或之後)加入:
```js
// ── 條件分支：goto 下拉選項（next/fail/restart/prev/requeue/各步驟）──
function branchGotoOptions(selVal, selfIdx) {
  const v = String(selVal ?? '');
  const opt = (val, label) => `<option value="${val}" ${v === val ? 'selected' : ''}>${label}</option>`;
  return [
    opt('next', '➡ 下一步（繼續）'),
    opt('fail', '❌ 失敗中斷'),
    opt('restart', '🔄 第1步'),
    opt('prev', '⬅ 上一步'),
    opt('requeue', '♻️ 重置並重排'),
    ...steps.map((s, j) => {
      if (j === selfIdx) return ''; // 不能跳自己
      return `<option value="${j + 1}" ${v === String(j + 1) ? 'selected' : ''}>第 ${j + 1} 步 — ${esc(s.step_name || s.action)}</option>`;
    }),
  ].join('');
}

// ── 條件分支卡片內容 ───────────────────────────────────────────────
function renderBranchBody(step, i) {
  const rules = Array.isArray(step.branches) ? step.branches : [];
  const timeoutVal = step.timeout !== undefined ? String(step.timeout) : '';
  const defaultVal = step.default_goto !== undefined ? String(step.default_goto) : 'fail';

  const ruleRows = rules.map((rule, k) => `
    <div class="form-row align-items-end mb-1">
      <div class="form-group col-12 col-md-6 mb-1">
        <label style="font-size:12px;">規則 ${k + 1}:偵測元素 Selector</label>
        <input type="text" class="form-control form-control-sm"
          value="${esc(rule.selector || '')}" placeholder="#otp-btn 或 .step9-marker"
          oninput="onBranchRuleField(${i},${k},'selector',this.value)">
      </div>
      <div class="form-group col-9 col-md-4 mb-1">
        <label style="font-size:12px;">出現時跳至</label>
        <select class="form-control form-control-sm"
          onchange="onBranchRuleField(${i},${k},'goto',this.value)">
          ${branchGotoOptions(rule.goto, i)}
        </select>
      </div>
      <div class="form-group col-3 col-md-2 mb-1">
        <button class="btn btn-sm btn-outline-danger btn-block" onclick="removeBranchRule(${i},${k})" title="刪除規則">
          <i class="fas fa-trash"></i>
        </button>
      </div>
    </div>`).join('');

  return `
    <div class="branch-body mt-2 pt-2" style="border-top:1px dashed #c5b3f0;">
      <div class="text-primary mb-1" style="font-size:12px;font-weight:600;">
        🔀 條件分支(由上而下賽跑，第一個出現的元素決定跳轉)
      </div>
      ${ruleRows || '<div class="text-muted small mb-1">尚無規則，點下方新增</div>'}
      <button class="btn btn-xs btn-outline-primary mb-2" onclick="addBranchRule(${i})">
        <i class="fas fa-plus"></i> 新增分支規則
      </button>
      <div class="form-row">
        <div class="form-group col-12 col-md-6 mb-1">
          <label style="font-size:12px;">皆未出現(逾時)時</label>
          <select class="form-control form-control-sm" onchange="onBranchDefault(${i},this.value)">
            ${branchGotoOptions(defaultVal, i)}
          </select>
        </div>
        <div class="form-group col-12 col-md-3 mb-1">
          <label style="font-size:12px;">賽跑逾時秒數</label>
          <input type="number" min="1" step="1" class="form-control form-control-sm"
            value="${esc(timeoutVal)}" placeholder="10"
            oninput="onFieldInput(${i},'timeout',this.value)">
        </div>
      </div>
    </div>`;
}

function onBranchRuleField(i, k, key, val) {
  if (!Array.isArray(steps[i].branches)) steps[i].branches = [];
  if (!steps[i].branches[k]) steps[i].branches[k] = { selector: '', goto: 'next' };
  if (key === 'goto' && /^\d+$/.test(val)) steps[i].branches[k][key] = parseInt(val, 10);
  else steps[i].branches[k][key] = val;
  updateJsonPreview();
}
function addBranchRule(i) {
  if (!Array.isArray(steps[i].branches)) steps[i].branches = [];
  steps[i].branches.push({ selector: '', goto: 'next' });
  renderAll();
}
function removeBranchRule(i, k) {
  if (Array.isArray(steps[i].branches)) steps[i].branches.splice(k, 1);
  renderAll();
}
function onBranchDefault(i, val) {
  steps[i].default_goto = /^\d+$/.test(val) ? parseInt(val, 10) : val;
  updateJsonPreview();
}
```

- [ ] **Step 4: onActionChange 切到 branch 時初始化**

在 `onActionChange` 內,`steps[i] = newStep;` 之前加入:
```js
  if (action === 'branch') {
    newStep.branches = Array.isArray(steps[i].branches) ? steps[i].branches : [];
    newStep.default_goto = steps[i].default_goto ?? 'fail';
    newStep.timeout = steps[i].timeout ?? 10;
  }
```

- [ ] **Step 5: buildStepsJson 序列化 branch**

在 `buildStepsJson` 的 `.map((s, i) => {` 內,建立 `obj` 之後(`if (s.action === 'captcha_prefetch') {` 之前)加入:
```js
    if (s.action === 'branch') {
      const branches = (Array.isArray(s.branches) ? s.branches : [])
        .filter(r => r && String(r.selector || '').trim())
        .map(r => ({
          selector: String(r.selector).trim(),
          goto: /^\d+$/.test(String(r.goto)) ? parseInt(r.goto, 10) : r.goto,
        }));
      obj.branches = branches;
      const dg = s.default_goto ?? 'fail';
      obj.default_goto = /^\d+$/.test(String(dg)) ? parseInt(dg, 10) : dg;
      if (s.timeout !== undefined && String(s.timeout) !== '') {
        obj.timeout = /^\d+$/.test(String(s.timeout)) ? parseInt(s.timeout, 10) : s.timeout;
      }
      return obj;
    }
```

- [ ] **Step 6: 手動驗證**

1. 啟動站台(依 `trader-system/CLAUDE.md`:nginx:8088 + php-fpm:9074)。
2. 開 `/admin/automation-tasks/create`(或 edit)。
3. 新增一步,action 下拉選「條件分支」。
4. 點「新增分支規則」兩次,填 `#otp-btn → 下一步`、`.step9-marker → 第 9 步`,default 設「失敗中斷」,逾時填 12。
5. 看頁面下方 JSON 預覽應出現:
```json
{
  "step_name": "...",
  "max_retries": 3,
  "action": "branch",
  "branches": [
    { "selector": "#otp-btn", "goto": "next" },
    { "selector": ".step9-marker", "goto": 9 }
  ],
  "default_goto": "fail",
  "timeout": 12
}
```
Expected: JSON 與上方一致;切走再切回 branch 規則不遺失。

- [ ] **Step 7: Commit**

```bash
cd trader-system
git add resources/views/admin/automation_tasks/form.php
git commit -m "feat(automation): 後台新增條件分支(branch)步驟卡片

Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>"
```

---

## Task 7: ACB id=1 改寫 step 5(資料,手動)

**Files:**
- 資料變更(經後台 UI,非程式碼):`automation_tasks` id=1 的 `steps`

需要先拿到實際 selector:`xx`=OTP 按鈕、`yy`=step9 標誌元素。未知前用 placeholder,先不啟用此分支於正式環境。

- [ ] **Step 1: 備份現有 steps**

開 `/admin/automation-tasks/edit?id=1`,複製目前 JSON 預覽全文,貼到本機檔 `auto-browser/docs/superpowers/acb-id1-steps.backup.json` 留存。

- [ ] **Step 2: 在原 step 5 上方插入 branch 步驟**

用卡片「↑ 插入」在 step 5 位置加一個「條件分支」步驟,設定:
- 規則1:`<xx: OTP 按鈕 selector>` → `下一步`
- 規則2:`<yy: step9 標誌 selector>` → 第 N 步(N = 原 step9 在新清單中的位置)
- 皆未出現:`失敗中斷`
- 逾時:`12`

> 注意:插入新步驟後,後面所有步驟序號 +1。設定規則2 的目標步驟時,務必用「插入後」的新序號(下拉選單已即時反映)。

- [ ] **Step 3: 儲存並驗證 JSON**

儲存後重新進編輯頁,確認 branch 步驟的 `branches[1].goto` 指向正確的 step9 新序號。

- [ ] **Step 4: 端到端驗證(需真實 ACB 環境)**

1. 用一個全新 profile 跑一筆訂單 → 應命中規則1(OTP 按鈕出現)→ 走 OTP 流程。
2. 同一 profile 再跑一筆(已登入)→ 應命中規則2 → 直接跳 step9,略過 OTP。
3. `timeout=12` 是否足夠登入後頁面穩定;不足則調大。
4. 在 `auto-browser` 視窗 log 觀察 `↳ 分支命中 → 跳至步驟 N`。

> 此步依賴真實站台與 selector,無法在本機自動化;由你實機確認後再調 `timeout` 與 `default_goto`。

---

## Self-Review 結果

- **Spec coverage:** §3 schema → Task 3;§4 race → Task 1+5;§5 executor(resolveGoto/runBranch/no-op/MAX_GOTO_COUNT)→ Task 4+5;§6 form UI → Task 6;§7 ACB 改寫 → Task 7;§8 邊界(MAX_GOTO_COUNT、default fail、唯一 TS runtime)已落在 Task 5/7。✓
- **Placeholder scan:** 僅 Task 7 的 `<xx>`/`<yy>`/`第 N 步` 為「待你提供的真實 selector/序號」,屬資料而非程式碼缺漏,已於 spec §9 與本任務標明。其餘步驟皆含完整程式碼與指令。
- **Type consistency:** `resolveGoto(target, currentIdx, total)`、`pickBranchGoto(branches, isPresent)`、`GotoResolution = number|'requeue'|'fail'`、`BranchRule{selector,goto}`、`parseBranches`/`parseGotoTarget` 命名於 Task 1–6 全程一致。`isSelectorPresent`/`raceBranch`/`checkOnError(…, total)` 簽名一致。
