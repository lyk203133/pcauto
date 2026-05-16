// Native <select> handler — mirror of browser.rs select arm (L672-692).

import type { ActionHandler } from './types';
import { StepError } from './types';
import { waitForSelector } from './_helpers';

export const select: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('select 缺少 selector');
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`select: 等待元素超時 ${rendered.selector}`);
  }
  log(`  → select ${rendered.selector} = ${rendered.value}`);
  const script = `(function() {
    var el = document.querySelector(${JSON.stringify(rendered.selector)});
    if (!el) return false;
    el.value = ${JSON.stringify(rendered.value)};
    el.dispatchEvent(new Event('change', { bubbles: true }));
    return true;
  })()`;
  try {
    await page.evaluate(script);
  } catch (e) {
    throw new StepError(`select evaluate: ${(e as Error).message}`);
  }
};
