// Mirror of autobrowser/src/callback.rs
//
// All endpoints, headers, payload shapes and timeouts MUST match the Rust client
// 1:1 — the PHP backend (AutoBrowserController) is unchanged.

import { createHmac } from 'node:crypto';
import type { AppConfig, GetCredentialsResponse, GetGaResponse } from '../types';
import { httpRequest, safeJsonParse } from './http';
import { log } from '../logger';

/** HMAC-SHA256 over `${order_no}|${status}|${timestamp}`; hex-encoded. */
export function computeHmac(
  secret: string,
  orderNo: string,
  status: number,
  timestamp: number,
): string {
  const msg = `${orderNo}|${status}|${timestamp}`;
  return createHmac('sha256', secret).update(msg).digest('hex');
}

function nowEpochSeconds(): number {
  return Math.floor(Date.now() / 1000);
}

function trimTrailingSlash(s: string): string {
  let end = s.length;
  while (end > 0 && s.charCodeAt(end - 1) === 0x2f /* '/' */) end--;
  return s.slice(0, end);
}

function headers(cfg: AppConfig): Record<string, string> {
  return {
    'Content-Type': 'application/json',
    'X-AutoBrowser-Key': cfg.api_key,
  };
}

export interface SendCallbackArgs {
  cfg: AppConfig;
  taskId: number;
  orderNo: string;
  status: number; // 2=完成, 3=失敗
  reason: string;
  failureImageData?: string;
}

export async function sendCallback(args: SendCallbackArgs): Promise<boolean> {
  const { cfg, taskId, orderNo, status, reason } = args;
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) {
    log('⚠️ 回調 URL 或 API Key 未設定,跳過回調');
    return false;
  }

  const url = `${serverUrl}/api/autobrowser/callback`;
  const ts = nowEpochSeconds();
  const sign = computeHmac(cfg.hmac_secret, orderNo, status, ts);

  const payload: Record<string, unknown> = {
    task_id: taskId,
    order_no: orderNo,
    status,
    reason,
    error_msg: status === 3 ? reason : '',
    timestamp: ts,
    sign,
  };
  if (args.failureImageData && args.failureImageData.trim() !== '') {
    payload['failure_image_data'] = args.failureImageData;
  }

  try {
    const resp = await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify(payload),
      timeoutMs: 10_000,
    });
    if (!resp.ok) {
      log(`❌ 回調失敗 HTTP ${resp.status}: ${orderNo}`);
      return false;
    }
    const body = safeJsonParse<{ success?: boolean }>(resp.text) ?? {};
    if (body.success === true) {
      log(`回調成功: ${orderNo} status=${status}`);
      return true;
    }
    log(`❌ 回調失敗(業務錯誤): ${resp.text}`);
    return false;
  } catch (e) {
    log(`❌ 回調失敗: ${(e as Error).message}`);
    return false;
  }
}

export interface StepCallbackArgs {
  cfg: AppConfig;
  taskId: number;
  orderNo: string;
  step: string;
  stepName: string;
  action: string;
  attempt: number;
  maxRetries: number;
  status: 'running' | 'success' | 'failed';
  message: string;
  reason?: string;
}

export async function sendStepCallback(args: StepCallbackArgs): Promise<void> {
  const { cfg } = args;
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return;
  const url = `${serverUrl}/api/autobrowser/step-callback`;
  const payload = {
    task_id: args.taskId,
    order_no: args.orderNo,
    step: args.step,
    step_name: args.stepName,
    action: args.action,
    attempt: args.attempt,
    max_retries: args.maxRetries,
    status: args.status,
    message: args.message,
    reason: args.reason ?? '',
  };
  try {
    await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify(payload),
      timeoutMs: 4_000,
    });
  } catch (e) {
    // step callback errors are non-fatal — match Rust's tracing::debug behaviour.
    // eslint-disable-next-line no-console
    console.debug(`步驟回調失敗(非致命): ${(e as Error).message}`);
  }
}

export async function requestGa(
  cfg: AppConfig,
  taskId: number,
  orderNo: string,
  variable: string,
): Promise<void> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return;
  const url = `${serverUrl}/api/autobrowser/request-ga`;
  try {
    await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify({ task_id: taskId, order_no: orderNo, variable }),
      timeoutMs: 5_000,
    });
  } catch (e) {
    log(`⚠️ request-ga 失敗: ${(e as Error).message}`);
  }
}

export async function notifyCaptchaResult(
  cfg: AppConfig,
  taskId: number,
  orderNo: string,
  success: boolean,
  reason: string,
): Promise<void> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return;
  const url = `${serverUrl}/api/autobrowser/captcha-result`;
  try {
    await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify({ task_id: taskId, order_no: orderNo, success, reason }),
      timeoutMs: 5_000,
    });
  } catch {
    /* non-fatal */
  }
}

export async function requestCaptcha(
  cfg: AppConfig,
  taskId: number,
  orderNo: string,
  imageData: string,
  variable: string,
): Promise<boolean> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return false;
  const url = `${serverUrl}/api/autobrowser/request-captcha`;
  try {
    const resp = await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify({
        task_id: taskId,
        order_no: orderNo,
        image_data: imageData,
        variable,
      }),
      timeoutMs: 10_000,
    });
    return resp.ok;
  } catch (e) {
    log(`⚠️ request-captcha 失敗: ${(e as Error).message}`);
    return false;
  }
}

export async function setNeedsCredentials(
  cfg: AppConfig,
  taskId: number,
  orderNo: string,
  captchaType: string,
  clearCaptcha = false,
): Promise<void> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return;
  const url = `${serverUrl}/api/autobrowser/set-needs-credentials`;
  try {
    await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify({
        task_id: taskId,
        order_no: orderNo,
        captcha_type: captchaType,
        clear_captcha: clearCaptcha,
      }),
      timeoutMs: 5_000,
    });
  } catch {
    /* non-fatal */
  }
}

/** Poll `/get-ga` once a second until ready, timeout or abort. Returns '' on timeout. */
export async function pollGa(
  cfg: AppConfig,
  taskId: number,
  timeoutSec: number,
  shouldStop: () => boolean,
): Promise<string> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return '';
  const url = `${serverUrl}/api/autobrowser/get-ga?task_id=${encodeURIComponent(String(taskId))}`;
  const deadline = Date.now() + timeoutSec * 1000;
  while (Date.now() < deadline) {
    if (shouldStop()) return '';
    try {
      const resp = await httpRequest(url, {
        method: 'GET',
        headers: { 'X-AutoBrowser-Key': cfg.api_key },
        timeoutMs: 5_000,
      });
      if (resp.ok) {
        const data = safeJsonParse<GetGaResponse>(resp.text);
        if (data && data.ready) {
          const code = data.ga_code ?? data.code ?? '';
          if (code.length > 0) return code;
        }
      }
    } catch {
      /* ignore network errors and keep polling */
    }
    await sleep(1000, shouldStop);
  }
  return '';
}

export async function pollCredentials(
  cfg: AppConfig,
  taskId: number,
  timeoutSec: number,
  shouldStop: () => boolean,
): Promise<{ account: string; password: string; code: string } | undefined> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return undefined;
  const url = `${serverUrl}/api/autobrowser/get-credentials?task_id=${encodeURIComponent(String(taskId))}`;
  const deadline = Date.now() + timeoutSec * 1000;
  while (Date.now() < deadline) {
    if (shouldStop()) return undefined;
    try {
      const resp = await httpRequest(url, {
        method: 'GET',
        headers: { 'X-AutoBrowser-Key': cfg.api_key },
        timeoutMs: 5_000,
      });
      if (resp.ok) {
        const data = safeJsonParse<GetCredentialsResponse>(resp.text);
        if (data && data.ready) {
          const account = data.account ?? '';
          const password = data.password ?? '';
          const code = data.code ?? '';
          if (account && password && code) return { account, password, code };
        }
      }
    } catch {
      /* ignore */
    }
    await sleep(1000, shouldStop);
  }
  return undefined;
}

export async function requeueTask(
  cfg: AppConfig,
  taskId: number,
  orderNo: string,
): Promise<void> {
  const serverUrl = trimTrailingSlash(cfg.server_url);
  if (!serverUrl || !cfg.api_key) return;
  const url = `${serverUrl}/api/autobrowser/requeue-task`;
  try {
    await httpRequest(url, {
      method: 'POST',
      headers: headers(cfg),
      body: JSON.stringify({ task_id: taskId, order_no: orderNo }),
      timeoutMs: 5_000,
    });
  } catch {
    /* non-fatal */
  }
}

async function sleep(ms: number, shouldStop: () => boolean): Promise<void> {
  const start = Date.now();
  while (Date.now() - start < ms) {
    if (shouldStop()) return;
    const remaining = ms - (Date.now() - start);
    await new Promise<void>((r) => setTimeout(r, Math.min(100, remaining)));
  }
}
