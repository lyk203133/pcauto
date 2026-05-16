// Mirror of browser.rs `scroll` arm (L1079-1086).

import type { ActionHandler } from './types';
import { StepError } from './types';

export const scroll: ActionHandler = async (ctx) => {
  const { page, step, log } = ctx;
  const amount = step.amount ?? 500;
  log(`  → scroll ${amount}px`);
  try {
    await page.evaluate((px: number) => window.scrollBy(0, px), amount);
  } catch (e) {
    throw new StepError(`scroll: ${(e as Error).message}`);
  }
};
