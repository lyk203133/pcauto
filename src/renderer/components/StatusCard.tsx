import { useAppStore } from '../store/useAppStore';

export function StatusCard(): JSX.Element {
  const running = useAppStore((s) => s.running);
  const countdown = useAppStore((s) => s.countdown);
  const activeCount = useAppStore((s) => s.activeCount);

  const cdText = !running ? '' : countdown === 0 ? '⟳ 掃單中...' : `${countdown}s`;

  return (
    <div className="card status-card">
      <span className={`indicator ${running ? 'running' : 'stopped'}`}>
        {running ? '🔄 掃單運行中' : '⏸ 已停止'}
      </span>
      <span className="sep">|</span>
      <span className="meta">任務: {activeCount}</span>
      {cdText && (
        <>
          <span className="sep">|</span>
          <span className="meta">{cdText}</span>
        </>
      )}
    </div>
  );
}
