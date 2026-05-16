// Mirror of pcauto/src/poller.rs
//
// Topology (PLAN.md §6):
//   - setInterval-ish loop driven by `setTimeout` that calls /pending-tasks every
//     `cfg.poll_interval` seconds.
//   - For each new task, queue it onto `p-limit(cfg.max_concurrent_tasks)`.
//   - Stop = AbortController.signal.aborted; every long sleep / poll checks it.

import { BrowserWindow } from 'electron';
import pLimit from 'p-limit';
import { loadConfig } from './config';
import { sendCallback } from './api/callback';
import { httpRequest, safeJsonParse } from './api/http';
import { log } from './logger';
import { runTask } from './browser/executor';
import { parseTaskData, type PendingTasksResponse, type TaskData } from './types';
import { Ch } from '../shared/ipc-channels';

const CALLBACK_RETRY_DELAY_SECS = 10;
const CALLBACK_MAX_ATTEMPTS = 3;

function broadcastState<T>(channel: string, payload: T): void {
  for (const w of BrowserWindow.getAllWindows()) {
    if (!w.isDestroyed()) w.webContents.send(channel, payload);
  }
}

class Poller {
  private abort: AbortController | undefined;
  private loopPromise: Promise<void> | undefined;
  private activeOrders = new Set<string>();
  private limit: ReturnType<typeof pLimit> | undefined;

  isRunning(): boolean {
    return this.abort !== undefined;
  }

  start(): void {
    if (this.abort) return;
    this.abort = new AbortController();
    const cfg = loadConfig();
    if (!cfg.server_url || !cfg.api_key) {
      log('⚠️ 後端 URL 或 API Key 未設定,請先在設定中配置');
      this.abort = undefined;
      return;
    }
    this.limit = pLimit(Math.max(cfg.max_concurrent_tasks, 1));
    broadcastState(Ch.RunningState, { running: true });
    this.loopPromise = this.runLoop(this.abort.signal);
  }

  async stop(): Promise<void> {
    const ab = this.abort;
    if (!ab) return;
    ab.abort();
    this.abort = undefined;
    broadcastState(Ch.RunningState, { running: false });
    broadcastState(Ch.Countdown, { remaining: 0 });
    if (this.loopPromise) {
      try {
        await this.loopPromise;
      } catch {
        /* ignore */
      }
      this.loopPromise = undefined;
    }
  }

  private shouldStop(signal: AbortSignal): () => boolean {
    return () => signal.aborted;
  }

  private async runLoop(signal: AbortSignal): Promise<void> {
    log('🔄 掃單服務已啟動');
    try {
      while (!signal.aborted) {
        broadcastState(Ch.ActiveCount, { count: this.activeOrders.size });
        const cfg = loadConfig();
        await this.pollOnce(cfg, signal);
        const interval = Math.max(cfg.poll_interval, 1);
        for (let remaining = interval; remaining >= 1; remaining--) {
          if (signal.aborted) break;
          broadcastState(Ch.Countdown, { remaining });
          await new Promise<void>((r) => setTimeout(r, 1000));
        }
        if (!signal.aborted) broadcastState(Ch.Countdown, { remaining: 0 });
      }
    } finally {
      log('⏹ 掃單服務已停止');
    }
  }

  private async pollOnce(
    cfg: ReturnType<typeof loadConfig>,
    signal: AbortSignal,
  ): Promise<void> {
    const serverUrl = cfg.server_url.replace(/\/+$/, '');
    if (!serverUrl || !cfg.api_key) return;
    const pollUrl = `${serverUrl}/api/pcauto/pending-tasks`;
    log(`>> 掃單 ${pollUrl}`);
    const t0 = Date.now();
    try {
      const resp = await httpRequest(pollUrl, {
        method: 'GET',
        headers: { 'X-Pcauto-Key': cfg.api_key },
        timeoutMs: 10_000,
        signal,
      });
      const elapsed = ((Date.now() - t0) / 1000).toFixed(2);
      if (!resp.ok) {
        log(`⚠️ HTTP ${resp.status}(${elapsed}s) —— 請確認 API Key 和後端 URL`);
        return;
      }
      const data = safeJsonParse<PendingTasksResponse>(resp.text);
      if (!data) {
        log('❌ 解析響應失敗');
        return;
      }
      const rawTasks = Array.isArray(data.tasks) ? data.tasks : [];
      if (rawTasks.length === 0) {
        log(`🔍 無待處理任務(${elapsed}s)`);
      } else {
        log(`📋 發現 ${rawTasks.length} 個待處理任務(${elapsed}s)`);
      }
      for (const raw of rawTasks) {
        let task: TaskData;
        try {
          task = parseTaskData(raw);
        } catch (e) {
          log(`❌ 解析任務失敗: ${(e as Error).message}`);
          continue;
        }
        this.startTask(task, cfg.max_concurrent_tasks, signal);
      }
    } catch (e) {
      const elapsed = ((Date.now() - t0) / 1000).toFixed(2);
      log(`❌ 掃單失敗(${elapsed}s): ${(e as Error).message}`);
    }
  }

  private startTask(task: TaskData, maxConcurrent: number, signal: AbortSignal): void {
    const orderNo = task.order_no;
    if (this.activeOrders.has(orderNo)) return;
    const cap = Math.max(maxConcurrent, 1);
    if (this.activeOrders.size >= cap) {
      log(`⏸ 已達並發上限 ${cap},暫不啟動任務: ${orderNo}`);
      return;
    }
    this.activeOrders.add(orderNo);
    log(`🚀 已啟動任務: ${orderNo}`);
    broadcastState(Ch.TaskStarted, { order_no: orderNo });
    broadcastState(Ch.ActiveCount, { count: this.activeOrders.size });

    const limit = this.limit;
    if (!limit) {
      // shouldn't happen, but fall back to inline execution
      void this.runTaskWithCallback(task, signal).finally(() => {
        this.activeOrders.delete(orderNo);
        broadcastState(Ch.ActiveCount, { count: this.activeOrders.size });
      });
      return;
    }

    void limit(() => this.runTaskWithCallback(task, signal))
      .catch(() => {
        /* swallow — runTaskWithCallback already logs */
      })
      .finally(() => {
        this.activeOrders.delete(orderNo);
        broadcastState(Ch.ActiveCount, { count: this.activeOrders.size });
      });
  }

  private async runTaskWithCallback(task: TaskData, signal: AbortSignal): Promise<void> {
    const cfg = loadConfig();
    const shouldStop = this.shouldStop(signal);
    let success = false;
    try {
      const out = await runTask({ cfg, task, shouldStop });
      if (out.status === 'stopped') {
        broadcastState(Ch.TaskDone, { order_no: task.order_no, success: false });
        return;
      }
      const isSuccess = out.status === 'success';
      const callback = isSuccess
        ? {
            status: 2,
            reason: 'pcauto 自動化全部步驟已完成,準備完成訂單',
            label: '完成',
            failure_image_data: undefined as string | undefined,
          }
        : {
            status: 3,
            reason: out.failure?.reason ?? '未知失敗',
            label: '失敗',
            failure_image_data: out.failure?.failure_image_data,
          };
      success = await this.sendFinalCallback(task, callback, shouldStop);
      if (isSuccess && !success) {
        // backend rejected the success callback after all retries
      }
    } catch (e) {
      log(`❌ 任務內部錯誤: ${(e as Error).message}`);
    } finally {
      broadcastState(Ch.TaskDone, { order_no: task.order_no, success });
    }
  }

  private async sendFinalCallback(
    task: TaskData,
    cb: {
      status: number;
      reason: string;
      label: string;
      failure_image_data: string | undefined;
    },
    shouldStop: () => boolean,
  ): Promise<boolean> {
    const cfg = loadConfig();
    let attempt = 0;
    while (!shouldStop()) {
      attempt += 1;
      try {
        const ok = await sendCallback({
          cfg,
          taskId: task.task_id,
          orderNo: task.order_no,
          status: cb.status,
          reason: cb.reason,
          failureImageData: cb.failure_image_data,
        });
        if (ok) return cb.status === 2;
        if (attempt >= CALLBACK_MAX_ATTEMPTS) {
          log(
            `❌ ${cb.label}回調被後端拒絕;已失敗 ${attempt}/${CALLBACK_MAX_ATTEMPTS} 次,釋放任務`,
          );
          return false;
        }
        log(
          `❌ ${cb.label}回調被後端拒絕;第 ${attempt}/${CALLBACK_MAX_ATTEMPTS} 次失敗,${CALLBACK_RETRY_DELAY_SECS}s 後重試,暫不釋放任務`,
        );
      } catch (e) {
        if (attempt >= CALLBACK_MAX_ATTEMPTS) {
          log(
            `❌ ${cb.label}回調失敗: ${(e as Error).message};已失敗 ${attempt}/${CALLBACK_MAX_ATTEMPTS} 次,釋放任務`,
          );
          return false;
        }
        log(
          `❌ ${cb.label}回調失敗: ${(e as Error).message};第 ${attempt}/${CALLBACK_MAX_ATTEMPTS} 次失敗,${CALLBACK_RETRY_DELAY_SECS}s 後重試`,
        );
      }
      for (let i = 0; i < CALLBACK_RETRY_DELAY_SECS; i++) {
        if (shouldStop()) return false;
        await new Promise<void>((r) => setTimeout(r, 1000));
      }
    }
    return false;
  }
}

export const poller = new Poller();
