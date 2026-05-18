// Reusable helpers for action handlers.

import type { Page } from 'playwright';

/** Truncate to N characters, append '...' if there was more. */
export function preview(value: string, max: number): string {
  if (value.length <= max) return value;
  return value.slice(0, max) + '...';
}

/** Sleep, checking shouldStop every 100ms; returns true if completed without stop. */
export async function cancellableSleep(
  ms: number,
  shouldStop: () => boolean,
): Promise<boolean> {
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (shouldStop()) return false;
    const remaining = ms - (Date.now() - start);
    await new Promise<void>((r) => setTimeout(r, Math.min(100, remaining)));
  }
  return !shouldStop();
}

/**
 * Wait until any of the given selectors resolves to a visible element, or the
 * timeout expires. Polls every 200ms. Mirrors browser.rs::wait_for_any_selector.
 *
 * Returns the matching selector, or undefined on timeout / stop.
 */
export async function waitForAnyVisible(
  page: Page,
  selectors: string[],
  timeoutMs: number,
  shouldStop: () => boolean,
): Promise<string | undefined> {
  const deadline = Date.now() + timeoutMs;
  const selectorsJson = JSON.stringify(selectors);
  // eslint-disable-next-line @typescript-eslint/no-implied-eval
  const script = `(function() {
    var selectors = ${selectorsJson};
    function isVisible(el) {
      return !!(el && (el.offsetWidth || el.offsetHeight || el.getClientRects().length));
    }
    for (var i = 0; i < selectors.length; i++) {
      try {
        var el = document.querySelector(selectors[i]);
        if (isVisible(el)) { return selectors[i]; }
      } catch (e) {}
    }
    return null;
  })()`;
  while (true) {
    if (shouldStop()) return undefined;
    try {
      const r = (await page.evaluate(script)) as string | null;
      if (r) return r;
    } catch {
      /* retry */
    }
    if (Date.now() >= deadline) return undefined;
    await new Promise<void>((r) => setTimeout(r, 200));
  }
}

export async function waitForSelector(
  page: Page,
  selector: string,
  timeoutMs: number,
  shouldStop: () => boolean,
): Promise<boolean> {
  return (await waitForAnyVisible(page, [selector], timeoutMs, shouldStop)) !== undefined;
}

/** Read `el.value` of the first matching element. Returns undefined when missing. */
export async function readInputValue(
  page: Page,
  selector: string,
): Promise<string | undefined> {
  try {
    const script = `(function() {
      var el = document.querySelector(${JSON.stringify(selector)});
      return el ? el.value : null;
    })()`;
    const r = (await page.evaluate(script)) as string | null;
    if (r === null) return undefined;
    return r;
  } catch {
    return undefined;
  }
}

/**
 * Fill a form input using the native value setter (compatible with React/Vue
 * controlled components) and verify by reading back. Retries up to maxRetries.
 *
 * Mirrors browser.rs::fill_with_verify.
 */
export async function fillWithVerify(
  page: Page,
  selector: string,
  value: string,
  label: string,
  maxRetries: number,
  log: (msg: string) => void,
): Promise<boolean> {
  for (let attempt = 1; attempt <= maxRetries; attempt++) {
    const fillScript = `(function() {
      var el = document.querySelector(${JSON.stringify(selector)});
      if (!el) return false;
      var proto = el instanceof HTMLTextAreaElement
        ? window.HTMLTextAreaElement.prototype
        : (el instanceof HTMLSelectElement ? window.HTMLSelectElement.prototype : window.HTMLInputElement.prototype);
      var nativeSetter = Object.getOwnPropertyDescriptor(proto, 'value');
      if (nativeSetter && nativeSetter.set) {
        nativeSetter.set.call(el, ${JSON.stringify(value)});
      } else {
        el.value = ${JSON.stringify(value)};
      }
      el.dispatchEvent(new Event('input', { bubbles: true }));
      el.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    })()`;
    let ok = true;
    try {
      const r = (await page.evaluate(fillScript)) as boolean;
      if (r === false) {
        log(`  ❌ ${label}:元素未找到 ${selector}(第${attempt}次)`);
        ok = false;
      }
    } catch (e) {
      log(`  ❌ ${label}填入失敗(第${attempt}次): ${(e as Error).message}`);
      ok = false;
    }
    if (!ok) {
      if (attempt < maxRetries) await new Promise<void>((r) => setTimeout(r, 500));
      continue;
    }

    const actual = await readInputValue(page, selector);
    if (actual === undefined) {
      log(`  ✔ ${label}(無法回讀,視為通過)`);
      return true;
    }
    const toNum = (s: string) => parseFloat(s.replace(/[,\s]/g, ''));
    const aNum = toNum(actual);
    const vNum = toNum(value);
    const numericMatch = !isNaN(aNum) && !isNaN(vNum) && aNum === vNum;
    if (actual === value || numericMatch) {
      log(`  ✔ ${label}驗證通過(第${attempt}次)`);
      return true;
    }
    log(
      `  ⚠️ ${label}不一致(第${attempt}次)  期望="${preview(value, 20)}"  實際="${preview(actual, 20)}"`,
    );
    if (attempt < maxRetries) {
      log('  🔄 清空後重新填入...');
      try {
        const clearScript = `(function() {
          var el = document.querySelector(${JSON.stringify(selector)});
          if (el) { el.value = ''; el.dispatchEvent(new Event('input', { bubbles: true })); }
        })()`;
        await page.evaluate(clearScript);
      } catch {
        /* ignore */
      }
      await new Promise<void>((r) => setTimeout(r, 500));
    }
  }
  log(`  ❌ ${label}重試 ${maxRetries} 次仍不一致,步驟失敗`);
  return false;
}

/**
 * Wait for the document to reach readyState === 'complete', polling every 100ms.
 * Falls back silently after the deadline (matches Rust behaviour).
 */
export async function waitDocumentComplete(
  page: Page,
  timeoutMs: number,
  shouldStop: () => boolean,
): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    if (shouldStop()) return;
    try {
      const ready = (await page.evaluate('document.readyState')) as string;
      if (ready === 'complete') return;
    } catch {
      /* ignore */
    }
    await new Promise<void>((r) => setTimeout(r, 100));
  }
}
