// keyboard_type: click to focus, then type character-by-character via Playwright's
// keyboard API. Each keystroke fires real browser key events, so sites that use
// data-next / auto-advance OTP inputs (e.g. ACB) receive proper input and focus
// naturally without needing per-digit selectors.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { waitForSelector } from './_helpers';

export const keyboardType: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('keyboard_type 缺少 selector');
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`keyboard_type: 等待元素超時 ${rendered.selector}`);
  }
  log(`  → keyboard_type ${rendered.selector} (${rendered.value.length} chars)`);
  try {
    await page.locator(rendered.selector).first().click({ timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`keyboard_type click: ${(e as Error).message}`);
  }
  if (shouldStop()) throw new StepError('stopped');
  try {
    await page.keyboard.type(rendered.value, { delay: 80 });
  } catch (e) {
    throw new StepError(`keyboard_type: ${(e as Error).message}`);
  }
};
