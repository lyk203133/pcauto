// Mirror of browser.rs `input` arm (L578-625).
// If the rendered `value` is an unresolved single placeholder (e.g. `{{code}}`),
// trigger request_ga + poll_ga and store the result into ctx.vars BEFORE filling.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { unresolvedSinglePlaceholder } from '../template';
import { pollGa, requestGa } from '../api/callback';
import { fillWithVerify, preview, waitForSelector } from './_helpers';

export const input: ActionHandler = async (ctx) => {
  const { page, step, task, cfg, vars, rendered, timeoutMs, timeoutSec, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('input 缺少 selector');

  let value = rendered.value;
  const placeholderVar = unresolvedSinglePlaceholder(step.value, rendered.value);
  if (placeholderVar !== undefined) {
    await requestGa(cfg, task.task_id, task.order_no, placeholderVar);
    log(`  🔐 等待用戶輸入 {{${placeholderVar}}}...`);

    const baseTimeout = step.timeout ?? 120;
    const waitSec = Math.max(baseTimeout, 120);
    const code = await pollGa(cfg, task.task_id, waitSec, shouldStop);
    if (code === '') {
      throw new StepError(`等待 {{${placeholderVar}}} 超時`);
    }
    vars.set(placeholderVar, code);
    if (placeholderVar === 'ga_code') {
      // Do nothing extra, just keep ga_code
    } else if (placeholderVar === 'code') {
      // Do nothing extra, just keep code
    }
    value = code;
  }

  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`input: 等待元素超時 ${rendered.selector}`);
  }
  log(`  → input ${rendered.selector} = ${preview(value, 20)}`);
  const ok = await fillWithVerify(page, rendered.selector, value, '輸入值', 3, log);
  if (!ok) throw new StepError('fill_with_verify 失敗');
  void timeoutSec; // reserved for future use; kept to mirror Rust signature
};
