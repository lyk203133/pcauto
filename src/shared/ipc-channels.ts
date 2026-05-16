// IPC channel name constants shared between main and renderer.
// Keep in sync with src/main/ipc.ts and src/preload/index.ts.

export const Ch = {
  // main -> renderer (broadcast)
  LogAppend: 'log/append',
  Countdown: 'state/countdown',
  ActiveCount: 'state/active-count',
  TaskStarted: 'task/started',
  TaskDone: 'task/done',
  RunningState: 'state/running',

  // renderer -> main (invoke)
  StartPoller: 'poller/start',
  StopPoller: 'poller/stop',
  GetConfig: 'config/get',
  SaveConfig: 'config/save',
  GetIsRunning: 'state/is-running',
} as const;

export type LogLevel = 'error' | 'warning' | 'success' | 'step' | 'normal';

export interface LogEntry {
  timestamp: string;
  message: string;
  level: LogLevel;
}

export interface TaskStartedEvent {
  order_no: string;
}

export interface TaskDoneEvent {
  order_no: string;
  success: boolean;
}

export interface CountdownEvent {
  remaining: number;
}

export interface ActiveCountEvent {
  count: number;
}

export interface RunningStateEvent {
  running: boolean;
}
