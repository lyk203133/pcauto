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
import { renderOpt } from '../template';
import { lookupAction } from '../actions';
import type { ActionContext } from '../actions/types';
import { sendStepCallback } from '../api/callback';
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

  for (let idx = 0; idx < steps.length; idx++) {
    const step = steps[idx]!;
    const action = step.action;
    const maxRetries = stepMaxRetries(step);
    const stepName = stepCallbackName(step, idx + 1);
    const stepKey = `step_${idx + 1}_${action}`;

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
