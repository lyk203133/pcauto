// Mirror of autobrowser/src/template.rs
// Regex: `\{\{\s*(\w+)\s*\}\}` — \w in Rust regex == ASCII [A-Za-z0-9_].
// Note: the JS \w in default mode includes the same set when no Unicode flag is used.
// We deliberately do NOT pass /u to keep parity with Rust's default ASCII semantics.

const TEMPLATE_RE = /\{\{\s*(\w+)\s*\}\}/g;

export function render(value: string, ctx: Map<string, string>): string {
  return value.replace(TEMPLATE_RE, (match, key: string) => {
    const trimmed = key.trim();
    const v = ctx.get(trimmed);
    return v !== undefined ? v : match;
  });
}

export function renderOpt(value: string | undefined, ctx: Map<string, string>): string {
  if (value === undefined || value === null) return '';
  return render(value, ctx);
}

/**
 * Match Rust `unresolved_single_placeholder` (browser.rs:1419-1431).
 *
 * Returns the inner variable name iff:
 *
 *   1. `raw.trim() === rendered.trim()` — render() did NOT substitute anything
 *      (e.g. the ctx had no entry for the key so the brace literal survived).
 *   2. `raw.trim()` starts with `{{` and ends with `}}`.
 *   3. The inner content (between braces, trimmed) is non-empty and contains
 *      only ASCII alphanumerics and underscores.
 *
 * Examples (mirroring the Rust function precisely):
 *   `{{code}}`      -> "code"
 *   `{{ code }}`    -> "code"     (inner is trimmed)
 *   `pre{{code}}`   -> undefined  (doesn't start with `{{`)
 *   `{{co-de}}`     -> undefined  (hyphen isn't `[A-Za-z0-9_]`)
 *   `{{code}}{{x}}` -> undefined  (after strip prefix/suffix, inner contains `}}{{`)
 */
export function unresolvedSinglePlaceholder(
  raw: string | undefined,
  rendered: string,
): string | undefined {
  if (raw === undefined || raw === null) return undefined;
  const rawTrim = raw.trim();
  if (rawTrim !== rendered.trim()) return undefined;
  if (!rawTrim.startsWith('{{') || !rawTrim.endsWith('}}')) return undefined;
  const innerRaw = rawTrim.slice(2, rawTrim.length - 2).trim();
  if (innerRaw.length === 0) return undefined;
  for (let i = 0; i < innerRaw.length; i++) {
    const c = innerRaw.charCodeAt(i);
    const isAlpha = (c >= 0x30 && c <= 0x39) || (c >= 0x41 && c <= 0x5a) || (c >= 0x61 && c <= 0x7a);
    const isUnderscore = c === 0x5f;
    if (!isAlpha && !isUnderscore) return undefined;
  }
  return innerRaw;
}
