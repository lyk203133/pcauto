// Mirror of browser.rs `wait` arm (L811-829).
// seconds > ms/1000 > value.parseFloat > 1.0. Polls shouldStop every 100ms.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { cancellableSleep } from './_helpers';

export const wait: ActionHandler = async (ctx) => {
  const { step, rendered, log, shouldStop } = ctx;
  let seconds: number | undefined;
  if (step.seconds !== undefined && Number.isFinite(step.seconds)) {
    seconds = step.seconds;
  } else if (step.ms !== undefined && Number.isFinite(step.ms)) {
    seconds = step.ms / 1000;
  } else if (rendered.value) {
    const parsed = Number(rendered.value);
    if (Number.isFinite(parsed)) seconds = parsed;
  }
  if (seconds === undefined || !Number.isFinite(seconds)) seconds = 1.0;
  log(`  → wait ${seconds}s`);
  const ok = await cancellableSleep(Math.max(0, Math.floor(seconds * 1000)), shouldStop);
  if (!ok) throw new StepError('stopped');
};
