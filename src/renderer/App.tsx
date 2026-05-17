import { useEffect, useState } from 'react';
import { StatusCard } from './components/StatusCard';
import { ControlBar } from './components/ControlBar';
import { LogPanel } from './components/LogPanel';
import { SettingsDialog } from './components/SettingsDialog';
import { useAppStore } from './store/useAppStore';

export function App(): JSX.Element {
  const appendLog = useAppStore((s) => s.appendLog);
  const setRunning = useAppStore((s) => s.setRunning);
  const setCountdown = useAppStore((s) => s.setCountdown);
  const setActiveCount = useAppStore((s) => s.setActiveCount);
  const [settingsOpen, setSettingsOpen] = useState(false);

  useEffect(() => {
    const unsubLog = window.autobrowser.onLog((e) => appendLog(e));
    const unsubRunning = window.autobrowser.onRunningState((e) => setRunning(e.running));
    const unsubCountdown = window.autobrowser.onCountdown((e) => setCountdown(e.remaining));
    const unsubActive = window.autobrowser.onActiveCount((e) => setActiveCount(e.count));

    void window.autobrowser.getIsRunning().then((r) => setRunning(r));

    return () => {
      unsubLog();
      unsubRunning();
      unsubCountdown();
      unsubActive();
    };
  }, [appendLog, setRunning, setCountdown, setActiveCount]);

  return (
    <div className="app">
      <div className="app-title">AutoBrowser</div>
      <StatusCard />
      <ControlBar onSettings={() => setSettingsOpen(true)} />
      <LogPanel />
      <SettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} />
    </div>
  );
}
