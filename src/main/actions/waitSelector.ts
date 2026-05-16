import type { ActionHandler } from './types';
import { StepError } from './types';
import { waitForSelector } from './_helpers';

export const waitSelector: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('wait_selector 缺少 selector,請在規則中配置');
  log(`  → wait_selector ${rendered.selector}`);
  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`wait_selector timeout: ${rendered.selector}`);
  }
};
