// Mirror of browser.rs `captcha_prefetch` arm (L461-561).
//
// Flow:
//   1. Navigate to (rendered.url || vars.site_url).
//   2. Branch on captcha_type:
//      - "ga"/"totp": notify request_ga(code).
//      - "none"/"credentials": request only account/password after page load.
//      - default ("image"): wait up to `ms` for the captcha element, screenshot
//        it, base64-encode, and call request_captcha. If the element never
//        appears, log a skip message.
//   3. POST /set-needs-credentials so the backend prompts the user.
//   4. Poll /get-credentials until account/password are ready; code is optional
//      for captcha_type "none"/"credentials".
//      (timeout >= 120s).
//   5. Write account/password/code/ga_code into vars.

import type { ActionHandler } from './types';
import { StepError } from './types';
import {
  pollCredentials,
  requestCaptcha,
  requestGa,
  setNeedsCredentials,
} from '../api/callback';
import { waitDocumentComplete, waitForSelector } from './_helpers';

export const captchaPrefetch: ActionHandler = async (ctx) => {
  const { page, step, task, cfg, vars, rendered, timeoutMs, log, shouldStop } = ctx;

  let url = rendered.url;
  if (!url) {
    url = vars.get('site_url') ?? '';
  }
  if (!url) {
    throw new StepError('captcha_prefetch 缺少 url(步驟未填且 site_url 為空)');
  }
  log(`  → captcha_prefetch: 導航至 ${url}`);
  try {
    await page.goto(url, { waitUntil: 'load', timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`captcha_prefetch goto: ${(e as Error).message}`);
  }
  try {
    await page.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
  } catch {
    /* fall through to readyState polling */
  }
  await waitDocumentComplete(page, timeoutMs, shouldStop);

  const captchaType = step.captcha_type ?? 'image';

  if (captchaType === 'ga' || captchaType === 'totp') {
    log('  → captcha_prefetch(ga): 首屏需要 Google 驗證碼');
    await requestGa(cfg, task.task_id, task.order_no, 'code');
  } else if (captchaType === 'none' || captchaType === 'credentials') {
    log('  → captcha_prefetch(credentials): 頁面已載入,直接要求會員輸入帳密');
  } else {
    if (!rendered.selector) {
      throw new StepError('captcha_prefetch 缺少 selector(驗證碼圖片元素)');
    }
    const msField = step.ms;
    const captchaTimeoutSec = msField !== undefined ? Math.floor(msField / 1000) : 5;
    const hasCaptcha = await waitForSelector(
      page,
      rendered.selector,
      captchaTimeoutSec * 1000,
      shouldStop,
    );
    if (hasCaptcha) {
      log(`  → captcha_prefetch(image): 截圖 ${rendered.selector}`);
      let buf: Buffer;
      try {
        buf = await page.locator(rendered.selector).first().screenshot({ type: 'png' });
      } catch (e) {
        throw new StepError(`captcha_prefetch screenshot: ${(e as Error).message}`);
      }
      const imageData = `data:image/png;base64,${buf.toString('base64')}`;
      const ok = await requestCaptcha(
        cfg,
        task.task_id,
        task.order_no,
        imageData,
        'code',
      );
      if (!ok) throw new StepError('captcha_prefetch 回傳後端失敗');
    } else {
      log('  → captcha_prefetch(image): 未找到驗證碼元素,直接要求帳密');
    }
  }

  await setNeedsCredentials(cfg, task.task_id, task.order_no, captchaType);

  const needsCode = captchaType !== 'none' && captchaType !== 'credentials';
  const waitLabel = captchaType === 'ga' || captchaType === 'totp'
    ? '帳密+GA碼'
    : (needsCode ? '帳密+驗證碼' : '帳密');
  log(`  🔐 等待會員輸入 ${waitLabel}...`);
  const baseTimeout = step.timeout ?? 180;
  const waitSec = Math.max(baseTimeout, 120);
  const credentials = await pollCredentials(cfg, task.task_id, waitSec, shouldStop);
  if (!credentials) throw new StepError('captcha_prefetch: 等待帳密+驗證碼超時');

  log(`  ✅ 收到${needsCode ? '帳密+驗證碼' : '帳密'}`);
  vars.set('account', credentials.account);
  vars.set('password', credentials.password);
  if (credentials.code) {
    vars.set('code', credentials.code);
    vars.set('ga_code', credentials.code);
  }
};
