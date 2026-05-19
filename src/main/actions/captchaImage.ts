// Mirror of browser.rs `captcha_image` / aliases (L968-1051).
// Does NOT auto-fill the input — the user's pipeline uses a subsequent `input`
// step with `{{code}}` to fill the value.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { renderOpt } from '../template';
import { notifyCaptchaResult, pollGa, requestCaptcha } from '../api/callback';
import { waitForSelector } from './_helpers';

export const captchaImage: ActionHandler = async (ctx) => {
  const { page, step, task, cfg, vars, attempt, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('captcha_image 缺少 selector');

  if (attempt > 1) {
    await notifyCaptchaResult(cfg, task.task_id, task.order_no, false, '驗證碼錯誤,請重新輸入');
  }

  const rawVar = renderOpt(step.variable ?? step.name ?? 'code', vars);
  const stripped = rawVar.replace(/^\{+/, '').replace(/\}+$/, '').trim();
  const variable = stripped === '' ? 'code' : stripped;

  log(`  → captcha_image: 截圖 ${rendered.selector},等待 {{${variable}}}`);
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`captcha_image timeout: ${rendered.selector}`);
  }

  let buf: Buffer;
  try {
    buf = await page.locator(rendered.selector).first().screenshot({ type: 'png' });
  } catch (e) {
    throw new StepError(`captcha_image screenshot: ${(e as Error).message}`);
  }
  const imageData = `data:image/png;base64,${buf.toString('base64')}`;

  const ok = await requestCaptcha(cfg, task.task_id, task.order_no, imageData, variable);
  if (!ok) throw new StepError('captcha_image 回傳後端失敗');

  log('  🔐 已回傳圖形驗證碼,等待用戶輸入...');
  const baseTimeout = step.timeout ?? 120;
  const waitSec = Math.max(baseTimeout, 120);
  const code = await pollGa(cfg, task.task_id, waitSec, shouldStop);
  if (code === '') throw new StepError('圖形驗證碼等待超時');

  vars.set(variable, code);
  if (variable === 'ga_code') {
     // do nothing
  } else if (variable === 'code') {
     // do nothing
  }
};
