// 零依賴的分支控制流純邏輯。不得 import './types'（會引入無副檔名相對 import，
// 使 node --test 的 ESM 解析失敗）。numeric 強制轉換自帶 toU64。

export type GotoTarget = 'restart' | 'prev' | 'next' | 'requeue' | 'fail' | number;
/** 一條分支規則：偵測到 selector 出現時，跳往 goto。 */
export interface BranchRule { selector: string; goto: GotoTarget }
export type GotoResolution = number | 'requeue' | 'fail';

/** 解析為 0-based 步驟索引，或控制 sentinel（'requeue' / 'fail'）。
 *  注意：'next' 在最後一步會回傳 total（== steps.length），即「越過結尾」的哨兵值，
 *  讓 executor 的 while (idx < steps.length) 自然結束 = 任務正常完成（不可改成 total-1，
 *  否則最後一步的 branch 會跳回自己造成迴圈）。 */
export function resolveGoto(
  target: string | number | undefined | null,
  currentIdx: number,
  total: number,
): GotoResolution {
  if (target === undefined || target === null) return 0; // 預設 restart
  if (typeof target === 'number') {
    // 1-based step number; 0 或負數非法 → 視為 restart(0)
    return Number.isFinite(target) && target >= 1 ? Math.trunc(target) - 1 : 0;
  }
  const t = target.trim().toLowerCase();
  if (t === 'restart') return 0;
  if (t === 'prev') return Math.max(0, currentIdx - 1);
  if (t === 'next') return Math.min(currentIdx + 1, total);
  if (t === 'requeue') return 'requeue';
  if (t === 'fail') return 'fail';
  if (/^\d+$/.test(t)) {
    const n = Number(t);
    return n >= 1 ? n - 1 : 0;
  }
  return 0;
}

/** 依陣列順序回傳第一條 selector 為 present 的規則 goto；皆不在回傳 null。 */
export function pickBranchGoto(
  branches: BranchRule[],
  isPresent: (selector: string) => boolean,
): GotoTarget | null {
  for (const rule of branches) {
    if (rule.selector && isPresent(rule.selector)) return rule.goto;
  }
  return null;
}

function toU64(v: unknown): number | undefined {
  if (typeof v === 'number') return Number.isFinite(v) && v >= 0 ? Math.trunc(v) : undefined;
  if (typeof v === 'string') {
    const s = v.trim();
    if (!/^\d+$/.test(s)) return undefined;
    return Number(s);
  }
  return undefined;
}

/** 把後端傳來的 goto 原值正規化為 GotoTarget：純數字字串轉 number、已知關鍵字字面量保留，
 *  其餘（含未知字串）回傳 undefined。 */
export function parseGotoTarget(v: unknown): GotoTarget | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'number') return Number.isFinite(v) ? Math.trunc(v) : undefined;
  if (typeof v === 'string') {
    const s = v.trim();
    if (s === '') return undefined;
    const n = toU64(s);
    if (n !== undefined) return n;
    if (s === 'restart' || s === 'prev' || s === 'next' || s === 'requeue' || s === 'fail') return s;
    return undefined;
  }
  return undefined;
}

/** 解析 branches 陣列；丟棄缺 selector 或 goto 無法解析的規則；無有效規則回傳 undefined。 */
export function parseBranches(v: unknown): BranchRule[] | undefined {
  if (!Array.isArray(v)) return undefined;
  const out: BranchRule[] = [];
  for (const item of v) {
    if (!item || typeof item !== 'object') continue;
    const o = item as Record<string, unknown>;
    const selector = typeof o['selector'] === 'string' ? (o['selector'] as string) : undefined;
    const goto = parseGotoTarget(o['goto']);
    if (selector && selector.length > 0 && goto !== undefined) out.push({ selector, goto });
  }
  return out.length > 0 ? out : undefined;
}
