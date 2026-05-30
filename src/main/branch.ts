// 零依賴的分支控制流純邏輯。不得 import './types'（會引入無副檔名相對 import，
// 使 node --test 的 ESM 解析失敗）。numeric 強制轉換自帶 toU64。

export type GotoTarget = 'restart' | 'prev' | 'next' | 'requeue' | 'fail' | number;
export interface BranchRule { selector: string; goto: GotoTarget }
export type GotoResolution = number | 'requeue' | 'fail';

/** 解析為 0-based 步驟索引，或控制 sentinel。total 用於語意參考（next 不超過步數）。 */
export function resolveGoto(
  target: string | number | undefined | null,
  currentIdx: number,
  total: number,
): GotoResolution {
  if (target === undefined || target === null) return 0; // 預設 restart
  if (typeof target === 'number') {
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
