import { useAppStore } from '../store/useAppStore';

interface Props {
  onSettings: () => void;
}

export function ControlBar({ onSettings }: Props): JSX.Element {
  const running = useAppStore((s) => s.running);

  const handleStart = async (): Promise<void> => {
    await window.autobrowser.startPoller();
  };
  const handleStop = async (): Promise<void> => {
    await window.autobrowser.stopPoller();
  };

  return (
    <div className="card control-bar">
      <button className="btn-start" disabled={running} onClick={() => void handleStart()}>
        ▶ 啟動
      </button>
      <button className="btn-stop" disabled={!running} onClick={() => void handleStop()}>
        ⏹ 停止
      </button>
      <button className="btn-settings" onClick={onSettings}>
        ⚙ 設定
      </button>
    </div>
  );
}
