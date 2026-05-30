import test from 'node:test';
import assert from 'node:assert/strict';
import { resolveGoto, pickBranchGoto, type BranchRule } from './branch.ts';

test('resolveGoto: restart → 0', () => assert.equal(resolveGoto('restart', 5, 10), 0));
test('resolveGoto: undefined → 0 (預設 restart)', () => assert.equal(resolveGoto(undefined, 5, 10), 0));
test('resolveGoto: prev → idx-1', () => assert.equal(resolveGoto('prev', 5, 10), 4));
test('resolveGoto: prev 在第一步 → 0', () => assert.equal(resolveGoto('prev', 0, 10), 0));
test('resolveGoto: next → idx+1', () => assert.equal(resolveGoto('next', 4, 10), 5));
test('resolveGoto: requeue', () => assert.equal(resolveGoto('requeue', 1, 10), 'requeue'));
test('resolveGoto: fail', () => assert.equal(resolveGoto('fail', 1, 10), 'fail'));
test('resolveGoto: 數字 9 (1-based) → 8', () => assert.equal(resolveGoto(9, 0, 10), 8));
test('resolveGoto: 數字字串 "9" → 8', () => assert.equal(resolveGoto('9', 0, 10), 8));
test('resolveGoto: 未知字串 → 0', () => assert.equal(resolveGoto('???', 3, 10), 0));

const rules: BranchRule[] = [
  { selector: '#otp', goto: 'next' },
  { selector: '.s9', goto: 9 },
];
test('pickBranchGoto: 依序第一個命中者勝', () => {
  assert.equal(pickBranchGoto(rules, (s) => s === '#otp'), 'next');
});
test('pickBranchGoto: 只有第二個命中 → 其 goto', () => {
  assert.equal(pickBranchGoto(rules, (s) => s === '.s9'), 9);
});
test('pickBranchGoto: 兩個都在 → 順序優先第一個', () => {
  assert.equal(pickBranchGoto(rules, () => true), 'next');
});
test('pickBranchGoto: 都不在 → null', () => {
  assert.equal(pickBranchGoto(rules, () => false), null);
});
test('pickBranchGoto: 空 selector 規則跳過', () => {
  assert.equal(pickBranchGoto([{ selector: '', goto: 5 }, { selector: '.s9', goto: 9 }], (s) => s === '.s9'), 9);
});
