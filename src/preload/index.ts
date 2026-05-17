// Preload script — exposes a typed bridge on `window.autobrowser`.
// The renderer never imports node APIs directly.

import { contextBridge, ipcRenderer } from 'electron';
import { Ch } from '../shared/ipc-channels';
import type { AppConfig } from '../shared/config';
import type {
  ActiveCountEvent,
  CountdownEvent,
  LogEntry,
  RunningStateEvent,
  TaskDoneEvent,
  TaskStartedEvent,
} from '../shared/ipc-channels';

type Unsub = () => void;

const api = {
  startPoller: (): Promise<boolean> => ipcRenderer.invoke(Ch.StartPoller),
  stopPoller: (): Promise<boolean> => ipcRenderer.invoke(Ch.StopPoller),
  getConfig: (): Promise<AppConfig> => ipcRenderer.invoke(Ch.GetConfig),
  saveConfig: (cfg: AppConfig): Promise<boolean> =>
    ipcRenderer.invoke(Ch.SaveConfig, cfg),
  getIsRunning: (): Promise<boolean> => ipcRenderer.invoke(Ch.GetIsRunning),

  onLog: (cb: (entry: LogEntry) => void): Unsub =>
    subscribe(Ch.LogAppend, cb),
  onCountdown: (cb: (e: CountdownEvent) => void): Unsub =>
    subscribe(Ch.Countdown, cb),
  onActiveCount: (cb: (e: ActiveCountEvent) => void): Unsub =>
    subscribe(Ch.ActiveCount, cb),
  onTaskStarted: (cb: (e: TaskStartedEvent) => void): Unsub =>
    subscribe(Ch.TaskStarted, cb),
  onTaskDone: (cb: (e: TaskDoneEvent) => void): Unsub =>
    subscribe(Ch.TaskDone, cb),
  onRunningState: (cb: (e: RunningStateEvent) => void): Unsub =>
    subscribe(Ch.RunningState, cb),
};

function subscribe<T>(channel: string, cb: (payload: T) => void): Unsub {
  const handler = (_event: unknown, payload: T): void => cb(payload);
  ipcRenderer.on(channel, handler);
  return () => ipcRenderer.removeListener(channel, handler);
}

contextBridge.exposeInMainWorld('autobrowser', api);

export type AutoBrowserBridge = typeof api;
