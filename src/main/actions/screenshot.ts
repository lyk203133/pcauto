// Mirror of browser.rs `screenshot` arm (L1053-1069).

import { join } from 'node:path';
import type { ActionHandler } from './types';
import { StepError } from './types';

function hhmmss(): string {
  const d = new Date();
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${pad(d.getHours())}${pad(d.getMinutes())}${pad(d.getSeconds())}`;
}

export const screenshot: ActionHandler = async (ctx) => {
  const { page, step, log } = ctx;
  const name = step.name && step.name.trim().length > 0 ? step.name : 'screenshot';
  const file = `${name}_${hhmmss()}.png`;
  const path = join(process.cwd(), file);
  log(`  → screenshot → ${file}`);
  try {
    await page.screenshot({ path, type: 'png' });
  } catch (e) {
    throw new StepError(`screenshot: ${(e as Error).message}`);
  }
};
