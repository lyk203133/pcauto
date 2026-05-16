// Mirror of browser.rs `wait_text` arm (L831-876).

import type { ActionHandler } from './types';
import { StepError } from './types';
import { preview, waitForSelector } from './_helpers';

export const waitText: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, timeoutSec, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('wait_text 缺少 selector');
  if (!rendered.expected) {
    log(`  → wait_text ${rendered.selector}: 等待元素出現`);
    if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
      throw new StepError(`wait_text timeout: ${rendered.selector}`);
    }
    return;
  }
  log(`  → wait_text ${rendered.selector} = "${rendered.expected}"`);
  const script = `new Promise((resolve) => {
    var deadline = Date.now() + ${timeoutSec * 1000};
    function isVisible(el) {
      return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }
    function check() {
      var el = document.querySelector(${JSON.stringify(rendered.selector)});
      var text = isVisible(el) ? (el.innerText || el.textContent || '') : '';
      if (text.indexOf(${JSON.stringify(rendered.expected)}) !== -1) {
        resolve({ found: true, text: text });
        return;
      }
      if (Date.now() > deadline) { resolve({ found: false, text: text }); return; }
      setTimeout(check, 200);
    }
    check();
  })`;
  let res: { found?: boolean; text?: string };
  try {
    res = (await page.evaluate(script)) as typeof res;
  } catch (e) {
    throw new StepError(`wait_text: ${(e as Error).message}`);
  }
  if (!res?.found) {
    log(
      `  ⚠️ 期望文字 "${rendered.expected}" 未找到,實際: "${preview(res?.text ?? '', 50)}"`,
    );
    throw new StepError('wait_text 未找到期望文字');
  }
};
