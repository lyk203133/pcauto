// Lightweight log classifier + broadcaster.
// `classifyLevel` mirrors Rust `LogEntry::classify` (models.rs:217-249).

import { BrowserWindow } from 'electron';
import type { LogEntry, LogLevel } from '../shared/ipc-channels';
import { Ch } from '../shared/ipc-channels';

const MAX_LOGS = 1000;
const ring: LogEntry[] = [];

export function classifyLevel(msg: string): LogLevel {
  if (
    msg.includes('❌') ||
    msg.includes('error') ||
    msg.includes('錯誤') ||
    msg.includes('失敗') ||
    msg.includes('failed')
  ) {
    return 'error';
  }
  if (
    msg.includes('⚠') ||
    msg.includes('warning') ||
    msg.includes('警告') ||
    msg.includes('驗證碼')
  ) {
    return 'warning';
  }
  if (
    msg.includes('✅') ||
    msg.includes('complete') ||
    msg.includes('完成') ||
    msg.includes('success') ||
    msg.includes('成功') ||
    msg.includes('✔')
  ) {
    return 'success';
  }
  if (
    msg.includes('▶') ||
    msg.includes('步驟') ||
    msg.includes('Step') ||
    msg.includes('🚀') ||
    msg.includes('🔄')
  ) {
    return 'step';
  }
  return 'normal';
}

function nowHHMMSS(): string {
  const d = new Date();
  const pad = (n: number) => (n < 10 ? `0${n}` : String(n));
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`;
}

export function log(message: string): void {
  const entry: LogEntry = {
    timestamp: nowHHMMSS(),
    message,
    level: classifyLevel(message),
  };
  ring.push(entry);
  if (ring.length > MAX_LOGS) ring.shift();
  // mirror to stdout (helps when running without UI)
  // eslint-disable-next-line no-console
  console.log(`[${entry.timestamp}] ${message}`);
  for (const w of BrowserWindow.getAllWindows()) {
    if (!w.isDestroyed()) {
      w.webContents.send(Ch.LogAppend, entry);
    }
  }
}

export function recentLogs(): readonly LogEntry[] {
  return ring;
}

export function clearLogs(): void {
  ring.length = 0;
}
