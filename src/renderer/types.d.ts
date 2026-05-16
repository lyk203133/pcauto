// Ambient declaration for the contextBridge API.

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

interface PcautoBridge {
  startPoller(): Promise<boolean>;
  stopPoller(): Promise<boolean>;
  getConfig(): Promise<AppConfig>;
  saveConfig(cfg: AppConfig): Promise<boolean>;
  getIsRunning(): Promise<boolean>;
  onLog(cb: (entry: LogEntry) => void): Unsub;
  onCountdown(cb: (e: CountdownEvent) => void): Unsub;
  onActiveCount(cb: (e: ActiveCountEvent) => void): Unsub;
  onTaskStarted(cb: (e: TaskStartedEvent) => void): Unsub;
  onTaskDone(cb: (e: TaskDoneEvent) => void): Unsub;
  onRunningState(cb: (e: RunningStateEvent) => void): Unsub;
}

declare global {
  interface Window {
    pcauto: PcautoBridge;
  }
}

export {};
