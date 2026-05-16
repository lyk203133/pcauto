// Mirror of pcauto/src/models.rs
// Lenient parsing helpers (coerceOptU64/I32/F64) reproduce serde's de_opt_* tolerance.

import type { AppConfig } from '../shared/config';
export type { AppConfig } from '../shared/config';
export { DEFAULT_CONFIG } from '../shared/config';

/**
 * StepAction mirrors Rust's `StepAction` struct.
 * All numeric fields tolerate string input (the backend sometimes sends "15" instead of 15).
 */
export interface StepAction {
  action: string;
  step_name?: string;
  selector?: string;
  value?: string;
  url?: string;
  expected?: string;
  seconds?: number;
  ms?: number;
  amount?: number;
  code?: string;
  name?: string;
  variable?: string;
  captcha_type?: string;
  option_selector?: string;
  match_type?: string;
  timeout?: number;
  max_retries?: number;
}

export interface TaskDataRaw {
  task_id: number;
  order_no: string;
  steps: unknown[];
  [extra: string]: unknown;
}

export interface TaskData {
  task_id: number;
  order_no: string;
  steps: StepAction[];
  extra: Record<string, unknown>;
}

export interface PendingTasksResponse {
  tasks: TaskDataRaw[];
}

export interface GetGaResponse {
  ready: boolean;
  ga_code?: string;
  code?: string;
}

export interface GetCredentialsResponse {
  ready: boolean;
  account?: string;
  password?: string;
  code?: string;
}

export interface TaskFailure {
  reason: string;
  failure_image_data?: string;
}

// ---------- lenient coercion (matches Rust de_opt_*) ----------

export function coerceOptU64(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'number') {
    if (!Number.isFinite(v) || v < 0) return undefined;
    return Math.trunc(v);
  }
  if (typeof v === 'string') {
    const s = v.trim();
    if (s === '') return undefined;
    const n = Number(s);
    if (!Number.isFinite(n) || n < 0) return undefined;
    return Math.trunc(n);
  }
  return undefined;
}

export function coerceOptI32(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'number') {
    if (!Number.isFinite(v)) return undefined;
    const t = Math.trunc(v);
    if (t < -2147483648 || t > 2147483647) return undefined;
    return t;
  }
  if (typeof v === 'string') {
    const s = v.trim();
    if (s === '') return undefined;
    const n = Number(s);
    if (!Number.isFinite(n)) return undefined;
    const t = Math.trunc(n);
    if (t < -2147483648 || t > 2147483647) return undefined;
    return t;
  }
  return undefined;
}

export function coerceOptF64(v: unknown): number | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'number') return Number.isFinite(v) ? v : undefined;
  if (typeof v === 'string') {
    const s = v.trim();
    if (s === '') return undefined;
    const n = Number(s);
    return Number.isFinite(n) ? n : undefined;
  }
  return undefined;
}

function asString(v: unknown): string | undefined {
  if (v === undefined || v === null) return undefined;
  if (typeof v === 'string') return v;
  return undefined;
}

/**
 * Parse a single step from the JSON received from the backend.
 * Throws if `action` is missing or not a string.
 */
export function parseStepAction(raw: unknown): StepAction {
  if (!raw || typeof raw !== 'object') {
    throw new Error('step is not an object');
  }
  const r = raw as Record<string, unknown>;
  const action = r['action'];
  if (typeof action !== 'string' || action.length === 0) {
    throw new Error('step.action missing or not a string');
  }
  // Support `options_selector` alias from Rust models.
  const optionSelector =
    asString(r['option_selector']) ?? asString(r['options_selector']);
  return {
    action,
    step_name: asString(r['step_name']),
    selector: asString(r['selector']),
    value: asString(r['value']),
    url: asString(r['url']),
    expected: asString(r['expected']),
    seconds: coerceOptF64(r['seconds']),
    ms: coerceOptU64(r['ms']),
    amount: coerceOptI32(r['amount']),
    code: asString(r['code']),
    name: asString(r['name']),
    variable: asString(r['variable']),
    captcha_type: asString(r['captcha_type']),
    option_selector: optionSelector,
    match_type: asString(r['match_type']),
    timeout: coerceOptU64(r['timeout']),
    max_retries: coerceOptU64(r['max_retries']),
  };
}

export function parseTaskData(raw: unknown): TaskData {
  if (!raw || typeof raw !== 'object') {
    throw new Error('task is not an object');
  }
  const r = raw as Record<string, unknown>;
  const taskId = coerceOptU64(r['task_id']);
  const orderNo = asString(r['order_no']);
  if (taskId === undefined) throw new Error('task.task_id missing');
  if (!orderNo) throw new Error('task.order_no missing');

  const rawSteps = r['steps'];
  if (!Array.isArray(rawSteps)) throw new Error('task.steps missing or not array');
  const steps = rawSteps.map(parseStepAction);

  const extra: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(r)) {
    if (k === 'task_id' || k === 'order_no' || k === 'steps') continue;
    extra[k] = v;
  }

  return { task_id: taskId, order_no: orderNo, steps, extra };
}

/**
 * Build the template context (variable -> string) used by `{{var}}` substitution.
 * Matches Rust `TaskData::template_context`.
 */
export function buildTemplateContext(task: TaskData): Map<string, string> {
  const ctx = new Map<string, string>();
  ctx.set('task_id', String(task.task_id));
  ctx.set('order_no', task.order_no);
  for (const [k, v] of Object.entries(task.extra)) {
    if (typeof v === 'string') {
      ctx.set(k, v);
    } else if (v === null || v === undefined) {
      ctx.set(k, '');
    } else {
      ctx.set(k, JSON.stringify(v));
    }
  }
  return ctx;
}

/** Helper: re-export AppConfig from shared so main can import everything from types.ts */
export type _ReexportConfig = AppConfig;
