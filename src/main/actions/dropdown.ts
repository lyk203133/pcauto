// Mirror of browser.rs `dropdown` arm (L694-809).
//
// ⚠ DEFAULT_OPTION_SELECTOR string must match Rust EXACTLY — the back-office
// templates rely on the default value when option_selector is unset. Do NOT
// reorder selectors or change whitespace.

import type { ActionHandler } from './types';
import { StepError } from './types';
import { render } from '../template';
import { preview, waitForSelector } from './_helpers';

export const DEFAULT_OPTION_SELECTOR =
  '[role="option"], [role="menuitem"], .dropdown-item, .ant-select-item, .el-select-dropdown__item, li';

export const dropdown: ActionHandler = async (ctx) => {
  const { page, step, vars, rendered, timeoutMs, timeoutSec, log, shouldStop } = ctx;
  if (!rendered.selector) throw new StepError('dropdown 缺少 selector(trigger 元素)');
  if (!rendered.value) throw new StepError('dropdown 缺少 value(要選的選項文字)');

  const rawOptionSel = step.option_selector?.trim();
  const optionSel =
    rawOptionSel && rawOptionSel.length > 0
      ? render(rawOptionSel, vars)
      : DEFAULT_OPTION_SELECTOR;

  const rawMatch = step.match_type?.trim();
  const matchType = rawMatch && rawMatch.length > 0 ? rawMatch : 'contains';
  const exact = matchType.toLowerCase() === 'exact';

  if (!(await waitForSelector(page, rendered.selector, timeoutMs, shouldStop))) {
    throw new StepError(`dropdown: 等待 trigger 超時 ${rendered.selector}`);
  }
  log(`  → dropdown 開啟 ${rendered.selector}`);
  try {
    await page.locator(rendered.selector).first().click({ timeout: timeoutMs });
  } catch (e) {
    throw new StepError(`dropdown click trigger: ${(e as Error).message}`);
  }

  log(`  → dropdown 選項 ${optionSel} = "${rendered.value}"`);
  // 1:1 port of the Rust pick_js: same norm/isVisible/exact-or-contains logic,
  // returns { ok, text } on success or { ok: false, sample } on timeout.
  const pickScript = `new Promise((resolve) => {
    var deadline = Date.now() + ${timeoutSec * 1000};
    var optSel = ${JSON.stringify(optionSel)};
    var target = ${JSON.stringify(rendered.value)};
    var exact = ${exact ? 'true' : 'false'};
    function norm(s) { return (s || '').replace(/\\s+/g, ' ').trim(); }
    function isVisible(el) {
      if (!el) return false;
      var r = el.getBoundingClientRect();
      if (!(r.width > 0 || r.height > 0)) return false;
      var cs = getComputedStyle(el);
      return cs.visibility !== 'hidden' && cs.display !== 'none' && cs.opacity !== '0';
    }
    function tryPick() {
      var nodes = document.querySelectorAll(optSel);
      var t = norm(target).toLowerCase();
      for (var i = 0; i < nodes.length; i++) {
        var el = nodes[i];
        if (!isVisible(el)) continue;
        var txt = norm(el.innerText || el.textContent || '').toLowerCase();
        var ok = exact ? (txt === t) : (txt.indexOf(t) !== -1);
        if (ok) {
          el.scrollIntoView({ block: 'nearest' });
          el.click();
          resolve({ ok: true, text: el.innerText || el.textContent || '' });
          return;
        }
      }
      if (Date.now() > deadline) {
        var sample = [];
        document.querySelectorAll(optSel).forEach(function (el) {
          if (sample.length < 8 && isVisible(el)) {
            sample.push(norm(el.innerText || el.textContent || ''));
          }
        });
        resolve({ ok: false, sample: sample });
        return;
      }
      setTimeout(tryPick, 150);
    }
    tryPick();
  })`;
  let res: { ok?: boolean; text?: string; sample?: string[] };
  try {
    res = (await page.evaluate(pickScript)) as typeof res;
  } catch (e) {
    throw new StepError(`dropdown evaluate: ${(e as Error).message}`);
  }
  if (!res?.ok) {
    const sample = (res?.sample ?? []).join(' | ');
    throw new StepError(
      `dropdown 找不到選項「${rendered.value}」(${matchType});可見選項: [${sample}]`,
    );
  }
  log(`  ✓ dropdown 選中: ${preview(res.text ?? '', 30)}`);
};
