// Mirror of browser.rs `wait_ga` arm (L888-966).
//
// IMPORTANT: the cached-value path is what prevents a SECOND GA countdown after
// captcha_prefetch already collected account+password+code together. We MUST
// reuse vars[variable] / vars.code / vars.ga_code (in that order) when present.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { renderOpt } from '../template';
import { pollGa, requestGa } from '../api/callback';
import { fillWithVerify } from './_helpers';

export const waitGa: ActionHandler = async (ctx) => {
  const { step, task, cfg, vars, rendered, log, shouldStop } = ctx;

  // Resolve `variable` — `step.variable` > `step.name` > "code".
  const rawVar = renderOpt(step.variable ?? step.name ?? 'code', vars);
  // Strip surrounding braces (allows users to type `{{code}}` in admin UI).
  const stripped = rawVar.replace(/^\{+/, '').replace(/\}+$/, '').trim();
  const variable = stripped === '' ? 'code' : stripped;

  // Cached value from earlier captcha_prefetch or wait_ga.
  const cached =
    (vars.get(variable) && vars.get(variable)!.length > 0 ? vars.get(variable) : undefined) ??
    (vars.get('code') && vars.get('code')!.length > 0 ? vars.get('code') : undefined) ??
    (vars.get('ga_code') && vars.get('ga_code')!.length > 0 ? vars.get('ga_code') : undefined);

  let gaCode: string;
  if (cached !== undefined) {
    log(`  ↳ wait_ga: 沿用先前已收集的 {{${variable}}}(跳過二次輸入)`);
    gaCode = cached;
  } else {
    await requestGa(cfg, task.task_id, task.order_no, variable);
    log('  🔐 已通知用戶輸入 GA 碼,等待中...');
    const baseTimeout = step.timeout ?? 120;
    const waitSec = Math.max(baseTimeout, 120);
    const code = await pollGa(cfg, task.task_id, waitSec, shouldStop);
    if (code === '') {
      log('  ❌ GA 等待超時');
      throw new StepError('GA 等待超時');
    }
    gaCode = code;
  }

  vars.set(variable, gaCode);
  vars.set('code', gaCode);
  vars.set('ga_code', gaCode);

  if (!rendered.selector) {
    log(`  ↳ wait_ga: 已保存 {{${variable}}},未配置 selector,交由後續步驟填入`);
    return;
  }
  log(`  → wait_ga: 填入 GA 碼至 ${rendered.selector}`);
  const ok = await fillWithVerify(ctx.page, rendered.selector, gaCode, 'GA 碼', 3, log);
  if (!ok) throw new StepError('GA 碼填入失敗');
};
