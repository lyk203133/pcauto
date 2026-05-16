// Mirror of browser.rs `type` arm (L627-670).
// Click the element, then dispatch a character-by-character input. Fallback to
// fillWithVerify when the read-back disagrees with the intended value.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { fillWithVerify, readInputValue, waitForSelector } from './_helpers';

export const typeAction: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('type 缺少 selector');
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`type: 等待元素超時 ${rendered.selector}`);
  }
  log(`  → type ${rendered.selector}`);
  try {
    await page.locator(rendered.selector).first().click({ timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`type click: ${(e as Error).message}`);
  }
  const script = `(function() {
    var el = document.querySelector(${JSON.stringify(rendered.selector)});
    if (!el) return false;
    el.focus();
    el.value = '';
    var val = ${JSON.stringify(rendered.value)};
    for (var i = 0; i < val.length; i++) {
      el.value += val[i];
      el.dispatchEvent(new Event('input', { bubbles: true }));
    }
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`;
  try {
    await page.evaluate(script);
  } catch (e) {
    throw new StepError(`type evaluate: ${(e as Error).message}`);
  }
  const actual = await readInputValue(page, rendered.selector);
  if (actual !== rendered.value) {
    log('  ⚠️ type 後值不一致,改用 fill 重試');
    const ok = await fillWithVerify(page, rendered.selector, rendered.value, '輸入值', 3, log);
    if (!ok) throw new StepError('type fallback fill_with_verify 失敗');
  }
};
