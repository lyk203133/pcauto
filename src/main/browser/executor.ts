// Mirror of autobrowser/src/browser.rs::BrowserExecutor
//
// Lifecycle:
//   1. Launch a Chromium browserContext with a per-task profile dir.
//   2. Iterate steps. Each step:
//      - render selector/value/url/expected via template ctx
//      - send step-callback("running")
//      - check_captcha → handle_captcha (block while one of the 9 selectors is visible)
//      - dispatch to the registered action handler
//      - on success: send step-callback("success") and a 500-1199ms random pause
//      - on failure: retry up to max_retries (5s pause between attempts);
//        if exhausted, capture a failure screenshot and return TaskFailure.
//
// stops are signalled by an AbortController; every long-running helper accepts a
// `shouldStop` closure so it can bail out promptly.

// CloakBrowser 是純 ESM 套件，在 CommonJS Electron 環境需用動態 import() 載入。
// tsc 會把動態 import() 轉成 require()，用 new Function 不變成 require 來繞過。
type CloakLaunchPersistentContext = typeof import('cloakbrowser')['launchPersistentContext'];
async function getCloakLaunch(): Promise<CloakLaunchPersistentContext> {
  // eslint-disable-next-line @typescript-eslint/no-implied-eval
  const dynamicImport = new Function('m', 'return import(m)') as (m: string) => Promise<typeof import('cloakbrowser')>;
  const mod = await dynamicImport('cloakbrowser');
  return mod.launchPersistentContext;
}
import type { Browser, BrowserContext, Page } from 'playwright';
import type { AppConfig, StepAction, TaskData, TaskFailure } from '../types';
import { buildTemplateContext } from '../types';
import { resolveGoto, pickBranchGoto, type GotoResolution } from '../branch';
import { renderOpt } from '../template';
import { lookupAction } from '../actions';
import type { ActionContext } from '../actions/types';
import { sendStepCallback, requestGa, setNeedsCredentials, requeueTask } from '../api/callback';
import { buildProfileDir, cleanupProfileDir } from '../profileDir';
import { log as broadcastLog } from '../logger';

const STEP_RETRY_DELAY_SECS = 5;
const DEFAULT_STEP_MAX_RETRIES = 3;

const CAPTCHA_SELECTORS: readonly string[] = [
  '.g-recaptcha',
  '[data-sitekey]',
  '.cf-turnstile',
  '#hcaptcha',
  '.h-captcha',
  '#captcha',
  '.captcha-container',
  "iframe[src*='captcha']",
  '.challenge-form',
];

interface ExecuteResult {
  /** true = success; false = stopped by user (no callback); throws TaskFailure on error */
  ok: boolean;
}

export interface RunInput {
  cfg: AppConfig;
  task: TaskData;
  shouldStop: () => boolean;
}

export interface RunOutput {
  status: 'success' | 'stopped' | 'failed';
  failure?: TaskFailure;
}

function stepCallbackName(step: StepAction, index: number): string {
  const t = step.step_name?.trim();
  if (t && t.length > 0) return t;
  return `第 ${index} 步`;
}

function stepMaxRetries(step: StepAction): number {
  return Math.max(step.max_retries ?? DEFAULT_STEP_MAX_RETRIES, 1);
}

function preview(value: string, max: number): string {
  if (value.length <= max) return value;
  return value.slice(0, max) + '...';
}

function describeStep(
  step: StepAction,
  index: number,
  total: number,
  ctx: Map<string, string>,
): string {
  const action = step.action;
  const stepName = stepCallbackName(step, index);
  const selector = renderOpt(step.selector, ctx);
  const value = renderOpt(step.value, ctx);
  const url = renderOpt(step.url, ctx);
  const expected = renderOpt(step.expected, ctx);
  const timeout = step.timeout ?? 15;

  let detail: string;
  switch (action) {
    case 'navigate':
      detail = `打開網址 ${url}`;
      break;
    case 'click':
      detail = `點擊元素 ${selector}`;
      break;
    case 'input':
      detail = `填寫 ${selector} = ${preview(value, 24)}`;
      break;
    case 'type':
      detail = `逐字輸入 ${selector} = ${preview(value, 24)}`;
      break;
    case 'select':
      detail = `選擇 ${selector} = ${preview(value, 24)}`;
      break;
    case 'dropdown':
      detail = `下拉 ${selector} → 選「${preview(value, 24)}」`;
      break;
    case 'wait': {
      const seconds =
        step.seconds ??
        (step.ms !== undefined ? step.ms / 1000 : undefined) ??
        Number.parseFloat(value);
      const sec = Number.isFinite(seconds) ? seconds : 1.0;
      detail = `等待 ${sec}s`;
      break;
    }
    case 'wait_text':
      detail =
        expected === ''
          ? `等待元素出現 ${selector},timeout=${timeout}s`
          : `等待 ${selector} 出現文字 ${preview(expected, 30)}`;
      break;
    case 'wait_selector':
      detail = `等待元素 ${selector},timeout=${timeout}s`;
      break;
    case 'wait_ga':
      detail = `等待並填入 GA/OTP 到 ${selector},timeout=${timeout}s`;
      break;
    case 'captcha_image':
    case 'request_captcha':
    case 'captcha':
      detail = `截取圖形驗證碼 ${selector} 並等待用戶輸入,timeout=${timeout}s`;
      break;
    case 'screenshot':
      detail = `保存截圖 ${step.name ?? 'screenshot'}`;
      break;
    case 'js':
      detail = '執行自定義 JavaScript';
      break;
    case 'scroll':
      detail = `滾動 ${step.amount ?? 500}px`;
      break;
    default:
      detail = `執行未知動作 ${action}`;
      break;
  }
  return `步驟 ${index}/${total}「${stepName}」: ${detail}`;
}

async function checkCaptcha(page: Page): Promise<boolean> {
  for (const sel of CAPTCHA_SELECTORS) {
    try {
      const script = `(function() {
        var el = document.querySelector(${JSON.stringify(sel)});
        return el ? (el.offsetWidth > 0 && el.offsetHeight > 0) : false;
      })()`;
      const v = (await page.evaluate(script)) as boolean;
      if (v) return true;
    } catch {
      /* ignore */
    }
  }
  return false;
}

async function handleCaptcha(page: Page, shouldStop: () => boolean): Promise<void> {
  broadcastLog('⚠️ 檢測到驗證碼,等待人工處理...');
  while (true) {
    if (shouldStop()) return;
    await new Promise<void>((r) => setTimeout(r, 1000));
    if (!(await checkCaptcha(page))) break;
  }
  broadcastLog('✅ 驗證碼已解決');
}

async function captureFailureScreenshot(
  page: Page,
  stepName: string,
): Promise<string | undefined> {
  try {
    const buf = await Promise.race([
      page.screenshot({ type: 'png' }),
      new Promise<Buffer>((_resolve, reject) =>
        setTimeout(() => reject(new Error('timeout')), 5000),
      ),
    ]);
    broadcastLog(`  📷 已截取失敗畫面:${stepName}`);
    return `data:image/png;base64,${buf.toString('base64')}`;
  } catch (e) {
    broadcastLog(`  ⚠️ 失敗畫面截圖失敗:${(e as Error).message}`);
    return undefined;
  }
}

async function launchContextAndPage(
  cfg: AppConfig,
  profileDir: string,
  log: (msg: string) => void,
): Promise<{ context: BrowserContext | Browser; page: Page }> {
  // CloakBrowser 使用 source-level C++ patches，不需手動修改 flags 或注入 JS。
  // --disable-blink-features=AutomationControlled、navigator.webdriver、CDP 自動化信號
  // 均在 binary 層已處理，無需額外設定。
  const args: string[] = [
    '--no-sandbox',
    '--no-first-run',
    '--no-default-browser-check',
    '--start-maximized',
  ];
  if (cfg.proxy && cfg.proxy.length > 0) {
    args.push(`--proxy-server=${cfg.proxy}`);
  }

  if (cfg.show_browser) log('🪟 瀏覽器顯示模式');
  else log('🕶 無頭瀏覽器模式');
  log('🛡 使用 CloakBrowser 隱身引擎 (source-level stealth)');

  const launchPersistentContext = await getCloakLaunch();
  const ctx = await launchPersistentContext({
    userDataDir: profileDir,
    headless: !cfg.show_browser,
    args,
    viewport: { width: 1366, height: 900 },
    humanize: true,
  });

  let page: Page;
  const pages = ctx.pages();
  if (pages.length > 0) {
    page = pages[0]!;
  } else {
    page = await ctx.newPage();
  }
  log('✅ CloakBrowser 啟動成功');
  return { context: ctx, page };
}

function randMs(): number {
  // 500..1199ms (matches Rust `500 + (rand_ms() % 700)`).
  return 500 + Math.floor(Math.random() * 700);
}

export async function runTask(input: RunInput): Promise<RunOutput> {
  const { cfg, task, shouldStop } = input;
  const orderNo = task.order_no;
  broadcastLog(`▶ 開始執行任務 ${orderNo}`);
  broadcastLog('🌐 正在啟動瀏覽器...');

  const profileDir = buildProfileDir(task.task_id, task.order_no);
  let context: BrowserContext | undefined;
  try {
    const launched = await launchContextAndPage(cfg, profileDir, broadcastLog);
    context = launched.context as BrowserContext;
    const page = launched.page;
    try {
      const out = await executeSteps({ cfg, task, page, shouldStop });
      if (out.ok) {
        broadcastLog(`✅ 任務完成: ${orderNo}`);
        return { status: 'success' };
      }
      broadcastLog(`⏹ 任務已停止: ${orderNo}`);
      return { status: 'stopped' };
    } catch (e) {
      const failure = e as TaskFailure;
      broadcastLog(`❌ 任務失敗: ${orderNo} — ${failure.reason}`);
      return { status: 'failed', failure };
    }
  } catch (e) {
    const reason = (e as Error).message;
    broadcastLog(`❌ 任務啟動失敗: ${orderNo} — ${reason}`);
    return { status: 'failed', failure: { reason } };
  } finally {
    if (context) {
      try {
        await Promise.race([
          context.close(),
          new Promise<void>((_, reject) =>
            setTimeout(() => reject(new Error('close timeout')), 5000),
          ),
        ]);
      } catch {
        broadcastLog('⚠️ Chrome 關閉超時');
      }
    }
    await cleanupProfileDir(profileDir);
  }
}

/** 跳轉時清掉 vars 中的過期值，並通知會員端重填 */
async function handleOnErrorRequest(
  request: string | undefined,
  cfg: import('../types').AppConfig,
  task: import('../types').TaskData,
  vars: Map<string, string>,
): Promise<void> {
  if (!request) return;
  const req = request.trim().toLowerCase();

  // 清 code 相關 vars（OTP / GA）
  const clearCode = () => {
    vars.delete('code');
    vars.delete('ga_code');
    vars.delete('otp_code');
    for (let i = 1; i <= 20; i++) {
      vars.delete(`code${i}`);
      vars.delete(`split_code_${i}`);
    }
  };

  if (req === 'code') {
    clearCode();
    broadcastLog('  🔄 on_error_request=code：清除 code 並通知會員重填 OTP');
    await requestGa(cfg, task.task_id, task.order_no, 'code');
  } else if (req === 'credentials') {
    clearCode();
    vars.delete('account');
    vars.delete('password');
    broadcastLog('  🔄 on_error_request=credentials：清除帳密並通知會員重填');
    const captchaType = task.steps.find((s) => s.action === 'captcha_prefetch')?.captcha_type ?? 'none';
    // clearCaptcha=true：清除舊驗證碼圖；無圖驗證碼流程則只要求會員重填帳密。
    await setNeedsCredentials(cfg, task.task_id, task.order_no, captchaType, true);
  }
}

/** 與 checkOnError / branch 共用的可見性判定：元素存在且（可見 或 有非空文字）。 */
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

/** 步驟成功後檢查 on_error_selector，輪詢至多 on_error_timeout 秒（預設 2）。
 *  回傳要跳轉的 0-based index、'requeue'，或 null（無錯誤繼續）。on_error_goto 不會產生 'fail'，
 *  但型別上仍可能回傳 'fail'，呼叫端會明確中止。 */
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

const MAX_GOTO_COUNT = 20; // 防無限循環

async function executeSteps(args: {
  cfg: AppConfig;
  task: TaskData;
  page: Page;
  shouldStop: () => boolean;
}): Promise<ExecuteResult> {
  const { cfg, task, page, shouldStop } = args;
  const steps = task.steps;
  const total = steps.length;
  const vars = buildTemplateContext(task);

  broadcastLog(`▶ 開始執行任務 ${task.order_no},共 ${total} 步`);
  broadcastLog('-'.repeat(40));

  let idx = 0;
  let gotoCount = 0;

  while (idx < steps.length) {
    const step = steps[idx]!;
    const action = step.action;
    const maxRetries = stepMaxRetries(step);
    const stepName = stepCallbackName(step, idx + 1);
    const stepKey = `step_${idx + 1}_${action}`;

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

    let attempt = 0;
    // eslint-disable-next-line no-constant-condition
    while (true) {
      if (shouldStop()) {
        broadcastLog('⏹ 用戶已停止');
        return { ok: false };
      }
      attempt += 1;

      const ctxSnapshot = new Map(vars);
      const description = describeStep(step, idx + 1, total, ctxSnapshot);
      broadcastLog(
        `步驟 ${idx + 1}/${total}: ${action}(第 ${attempt}/${maxRetries} 次)`,
      );

      await sendStepCallback({
        cfg,
        taskId: task.task_id,
        orderNo: task.order_no,
        step: stepKey,
        stepName,
        action,
        attempt,
        maxRetries,
        status: 'running',
        message: `${description};第 ${attempt}/${maxRetries} 次執行`,
      });

      // Captcha watchdog (same 9 selectors as Rust).
      if (await checkCaptcha(page)) {
        await handleCaptcha(page, shouldStop);
      }

      const handler = lookupAction(action);
      let stepError: string | undefined;

      if (handler === undefined) {
        broadcastLog(`  ⚠️ 未知 action: ${action},跳過`);
      } else {
        const renderedSelector = renderOpt(step.selector, vars);
        const renderedValue = renderOpt(step.value, vars);
        const renderedUrl = renderOpt(step.url, vars);
        const renderedExpected = renderOpt(step.expected, vars);
        const timeoutSec = step.timeout ?? 15;
        const actionCtx: ActionContext = {
          page,
          step,
          task,
          cfg,
          vars,
          attempt,
          shouldStop,
          log: broadcastLog,
          rendered: {
            selector: renderedSelector,
            value: renderedValue,
            url: renderedUrl,
            expected: renderedExpected,
          },
          timeoutMs: timeoutSec * 1000,
          timeoutSec,
        };
        try {
          await handler(actionCtx);
        } catch (e) {
          stepError = (e as Error).message ?? String(e);
        }
      }

      if (stepError === undefined) {
        // 步驟本身成功，檢查 on_error_selector 分支
        const gotoResult = await checkOnError(page, step, idx, total);
        if (gotoResult !== null) {
          if (gotoResult === 'requeue') {
            // requeue：直接重置，不通知 member（新任務的 captcha_prefetch 會重新推 member 端 UI）
            // 不送 sendStepCallback(failed)，避免後端 stepCallback 把 status 覆蓋回 3
            broadcastLog(`  ♻️ 步驟 ${idx + 1} 偵測到錯誤條件，重置任務並重新排隊`);
            await requeueTask(cfg, task.task_id, task.order_no);
            return { ok: false }; // 結束本次執行，poller 會重新撿起
          }

          await handleOnErrorRequest(step.on_error_request, cfg, task, vars);

          if (gotoResult === 'fail') {
            const reason = `步驟 ${idx + 1}「${stepName}」on_error_goto=fail，中止任務`;
            broadcastLog(`  ❌ ${reason}`);
            await sendStepCallback({
              cfg, taskId: task.task_id, orderNo: task.order_no,
              step: stepKey, stepName, action, attempt, maxRetries,
              status: 'failed', message: reason, reason,
            });
            // eslint-disable-next-line @typescript-eslint/no-throw-literal
            throw { reason, failure_image_data: await captureFailureScreenshot(page, stepName) };
          }

          const gotoIdx = gotoResult;
          gotoCount += 1;
          if (gotoCount > MAX_GOTO_COUNT) {
            const reason = `步驟 ${idx + 1}「${stepName}」on_error_goto 跳轉超過 ${MAX_GOTO_COUNT} 次，中止任務`;
            broadcastLog(`  ❌ ${reason}`);
            // eslint-disable-next-line @typescript-eslint/no-throw-literal
            throw { reason, failure_image_data: await captureFailureScreenshot(page, stepName) };
          }
          broadcastLog(
            `  ⚠️ 步驟 ${idx + 1} 偵測到錯誤條件（${step.on_error_selector}），跳轉至步驟 ${gotoIdx + 1}`,
          );
          await sendStepCallback({
            cfg, taskId: task.task_id, orderNo: task.order_no,
            step: stepKey, stepName, action, attempt, maxRetries,
            status: 'failed',
            message: `${description};偵測到錯誤條件，跳轉至步驟 ${gotoIdx + 1}`,
            reason: `on_error_goto → 步驟 ${gotoIdx + 1}`,
          });
          idx = gotoIdx;
          break; // 跳出 retry while，外層 while 會用新 idx
        }

        broadcastLog(`  ✅ 步驟 ${idx + 1} 完成`);
        await sendStepCallback({
          cfg,
          taskId: task.task_id,
          orderNo: task.order_no,
          step: stepKey,
          stepName,
          action,
          attempt,
          maxRetries,
          status: 'success',
          message: `${description};第 ${attempt}/${maxRetries} 次;結果:完成`,
        });
        idx += 1; // 正常前進
        break;
      }

      if (shouldStop()) {
        broadcastLog('⏹ 用戶已停止');
        return { ok: false };
      }
      broadcastLog(`  ❌ 步驟執行失敗: ${stepError}`);

      if (attempt >= maxRetries) {
        const finalReason = `步驟 ${idx + 1}/${total}「${stepName}」連續失敗 ${attempt}/${maxRetries} 次,最後原因:${stepError}`;
        broadcastLog(`  ❌ ${finalReason};中斷任務並回報失敗`);
        await sendStepCallback({
          cfg,
          taskId: task.task_id,
          orderNo: task.order_no,
          step: stepKey,
          stepName,
          action,
          attempt,
          maxRetries,
          status: 'failed',
          message: `${description};第 ${attempt}/${maxRetries} 次;結果:已達最大重試次數,中斷任務`,
          reason: finalReason,
        });
        const failureImage = await captureFailureScreenshot(page, stepName);
        // throw TaskFailure to caller
        const fail = {
          reason: finalReason,
          failure_image_data: failureImage,
        };
        // eslint-disable-next-line @typescript-eslint/no-throw-literal
        throw fail;
      }

      broadcastLog(
        `  ⏸ 步驟 ${idx + 1} 第 ${attempt}/${maxRetries} 次異常,原因:${stepError};${STEP_RETRY_DELAY_SECS}s 後重試`,
      );
      await sendStepCallback({
        cfg,
        taskId: task.task_id,
        orderNo: task.order_no,
        step: stepKey,
        stepName,
        action,
        attempt,
        maxRetries,
        status: 'failed',
        message: `${description};第 ${attempt}/${maxRetries} 次;結果:異常,等待 ${STEP_RETRY_DELAY_SECS}s 後重試`,
        reason: stepError,
      });

      for (let i = 0; i < STEP_RETRY_DELAY_SECS; i++) {
        if (shouldStop()) {
          broadcastLog('⏹ 用戶已停止');
          return { ok: false };
        }
        await new Promise<void>((r) => setTimeout(r, 1000));
      }
    }

    await new Promise<void>((r) => setTimeout(r, randMs()));
  }

  broadcastLog('-'.repeat(40));
  broadcastLog('✅ 任務完成');
  return { ok: true };
}
