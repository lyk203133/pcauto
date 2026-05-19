// Mirror of browser.rs `wait_ga` arm (L888-966).
//
// IMPORTANT: only reuse an explicitly requested variable. Falling back to
// vars.code can accidentally reuse a login image captcha as a later OTP.

import type { Page } from 'playwright';
import type { ActionHandler } from './types';
import { StepError } from './types';
import { renderOpt } from '../template';
import { pollGa, requestGa } from '../api/callback';
import { fillWithVerify } from './_helpers';

// Parse "split_code_N" → N (1-20). Returns null for any other variable name.
function parseSplitN(variable: string): number | null {
  const m = variable.match(/^split_code_(\d+)$/);
  if (!m) return null;
  const n = parseInt(m[1]!, 10);
  return n >= 1 && n <= 20 ? n : null;
}

// Fill N separate input elements (querySelectorAll) each with one character.
async function fillSplitInputs(
  page: Page,
  selector: string,
  code: string,
  n: number,
  log: (msg: string) => void,
): Promise<boolean> {
  const chars = Array.from(code.slice(0, n).padEnd(n, '0'));
  const script = `(function() {
    var els = Array.from(document.querySelectorAll(${JSON.stringify(selector)}));
    if (els.length < ${n}) return els.length;
    var chars = ${JSON.stringify(chars)};
    var proto = window.HTMLInputElement.prototype;
    var setter = Object.getOwnPropertyDescriptor(proto, 'value');
    for (var i = 0; i < ${n}; i++) {
      var el = els[i];
      if (!el) continue;
      if (setter && setter.set) { setter.set.call(el, chars[i]); }
      else { el.value = chars[i]; }
      el.dispatchEvent(new Event('input',  { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
    }
    return ${n};
  })()`;

  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      const found = (await page.evaluate(script)) as number;
      if (found === n) {
        log(`  ✔ split_code_${n}: 已逐格填入 ${n} 位至 ${selector}`);
        return true;
      }
      log(`  ⚠️ split_code_${n}: 找到 ${found} 個元素，需要 ${n} 個（第 ${attempt} 次）`);
    } catch (e) {
      log(`  ❌ split_code_${n} 填入失敗（第 ${attempt} 次）: ${(e as Error).message}`);
    }
    if (attempt < 3) await new Promise<void>((r) => setTimeout(r, 500));
  }
  return false;
}

export const waitGa: ActionHandler = async (ctx) => {
  const { step, task, cfg, vars, rendered, log, shouldStop } = ctx;

  // Extract variable name — strip {{}} braces if admin typed them, but do NOT
  // run renderOpt here: the variable is what we're collecting, so on a retry it
  // would already be in vars and renderOpt would replace {{split_code_6}} with
  // the actual code value, breaking parseSplitN and the cache check.
  const rawVar = (step.variable ?? step.name ?? 'code').trim();
  const stripped = rawVar.replace(/^\{\{\s*/, '').replace(/\s*\}\}$/, '').trim();
  const variable = stripped === '' ? 'code' : stripped;

  // Cached value from an earlier wait_ga of the same variable.
  const cached = vars.get(variable) && vars.get(variable)!.length > 0 ? vars.get(variable) : undefined;

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
  vars.set('ga_code', gaCode);
  if (variable !== 'ga_code') {
     vars.set(variable, gaCode);
  }

  if (!rendered.selector) {
    log(`  ↳ wait_ga: 已保存 {{${variable}}},未配置 selector,交由後續步驟填入`);
    return;
  }

  // split_code_N: fill each character into a separate input element.
  const splitN = parseSplitN(variable);
  if (splitN !== null) {
    log(`  → wait_ga: split_code_${splitN} 逐格填入至 ${rendered.selector}`);
    const ok = await fillSplitInputs(ctx.page, rendered.selector, gaCode, splitN, log);
    if (!ok) throw new StepError(`split_code_${splitN} 逐格填入失敗`);
    return;
  }

  log(`  → wait_ga: 填入 GA 碼至 ${rendered.selector}`);
  const ok = await fillWithVerify(ctx.page, rendered.selector, gaCode, 'GA 碼', 3, log);
  if (!ok) throw new StepError('GA 碼填入失敗');
};
