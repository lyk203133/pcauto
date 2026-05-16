// Mirror of browser.rs `js` arm (L1071-1077).

import type { ActionHandler } from './types';
import { StepError } from './types';
import { render } from '../template';

export const js: ActionHandler = async (ctx) => {
  const { page, step, vars, log } = ctx;
  const code = render(step.code ?? '', vars);
  log('  → js executed');
  try {
    await page.evaluate(code);
  } catch (e) {
    throw new StepError(`js evaluate: ${(e as Error).message}`);
  }
};
