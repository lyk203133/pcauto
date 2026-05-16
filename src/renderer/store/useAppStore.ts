import { create } from 'zustand';
import type { LogEntry } from '../../shared/ipc-channels';

interface AppState {
  logs: LogEntry[];
  running: boolean;
  countdown: number;
  activeCount: number;
  appendLog: (entry: LogEntry) => void;
  clearLogs: () => void;
  setRunning: (running: boolean) => void;
  setCountdown: (n: number) => void;
  setActiveCount: (n: number) => void;
}

const MAX_LOGS = 1000;

export const useAppStore = create<AppState>((set) => ({
  logs: [],
  running: false,
  countdown: 0,
  activeCount: 0,
  appendLog: (entry) =>
    set((s) => {
      const next = s.logs.length >= MAX_LOGS ? s.logs.slice(-MAX_LOGS + 1) : s.logs.slice();
      next.push(entry);
      return { logs: next };
    }),
  clearLogs: () => set({ logs: [] }),
  setRunning: (running) => set({ running }),
  setCountdown: (countdown) => set({ countdown }),
  setActiveCount: (activeCount) => set({ activeCount }),
}));
