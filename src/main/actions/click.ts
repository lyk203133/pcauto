import type { ActionHandler } from './types';
import { StepError } from './types';
import { waitForSelector } from './_helpers';

export const click: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('click 缺少 selector');
  log(`  → click ${rendered.selector}`);
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`click: 等待元素超時 ${rendered.selector}`);
  }
  try {
    await page.locator(rendered.selector).first().click({ timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`click: ${(e as Error).message}`);
  }
};
