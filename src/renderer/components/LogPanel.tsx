import { useEffect, useRef } from 'react';
import { useAppStore } from '../store/useAppStore';

export function LogPanel(): JSX.Element {
  const logs = useAppStore((s) => s.logs);
  const clearLogs = useAppStore((s) => s.clearLogs);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [logs]);

  return (
    <>
      <div className="log-header">
        <span className="log-header-label">LOG</span>
        <button className="log-clear" onClick={clearLogs} aria-label="clear logs">
          ✖
        </button>
      </div>
      <div className="log-panel" ref={scrollRef}>
        {logs.map((entry, i) => (
          <div key={i} className={`log-line ${entry.level}`}>
            [{entry.timestamp}] {entry.message}
          </div>
        ))}
      </div>
    </>
  );
}
