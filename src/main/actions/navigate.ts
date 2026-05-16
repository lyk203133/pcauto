import type { ActionHandler } from './types';
import { StepError } from './types';
import { waitDocumentComplete } from './_helpers';

export const navigate: ActionHandler = async (ctx) => {
  const { page, rendered, timeoutMs, log, shouldStop } = ctx;
  if (!rendered.url) throw new StepError('navigate 缺少 url');
  log(`  → navigate ${rendered.url}`);
  try {
    await page.goto(rendered.url, { waitUntil: 'load', timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`navigate goto: ${(e as Error).message}`);
  }
  try {
    await page.waitForLoadState('domcontentloaded', { timeout: timeoutMs });
  } catch {
    /* don't fail on DCL — Rust just polls readyState */
  }
  await waitDocumentComplete(page, timeoutMs, shouldStop);
  log('  ✓ 頁面載入完成');
};
