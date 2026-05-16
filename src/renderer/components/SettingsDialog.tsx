import { useEffect, useState } from 'react';
import type { AppConfig } from '../../shared/config';
import { DEFAULT_CONFIG } from '../../shared/config';

interface Props {
  open: boolean;
  onClose: () => void;
}

export function SettingsDialog({ open, onClose }: Props): JSX.Element | null {
  const [cfg, setCfg] = useState<AppConfig>(DEFAULT_CONFIG);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (!open) return;
    setLoading(true);
    window.pcauto
      .getConfig()
      .then((value) => setCfg(value))
      .finally(() => setLoading(false));
  }, [open]);

  if (!open) return null;

  const update = <K extends keyof AppConfig>(key: K, value: AppConfig[K]): void => {
    setCfg((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = async (): Promise<void> => {
    const wasRunning = await window.pcauto.getIsRunning();
    const ok = await window.pcauto.saveConfig(cfg);
    if (!ok) return;
    if (wasRunning) {
      await window.pcauto.stopPoller();
      await window.pcauto.startPoller();
    }
    onClose();
  };

  return (
    <div className="modal-backdrop">
      <div className="modal">
        <h2>設定</h2>
        {loading ? (
          <div>載入中...</div>
        ) : (
          <>
            <div className="field">
              <label>後端 URL</label>
              <input
                type="text"
                value={cfg.server_url}
                onChange={(e) => update('server_url', e.target.value)}
              />
            </div>
            <div className="field">
              <label>API Key</label>
              <input
                type="password"
                value={cfg.api_key}
                onChange={(e) => update('api_key', e.target.value)}
              />
            </div>
            <div className="field">
              <label>HMAC Secret</label>
              <input
                type="password"
                value={cfg.hmac_secret}
                onChange={(e) => update('hmac_secret', e.target.value)}
              />
            </div>
            <div className="field">
              <label>輪詢間隔(秒)</label>
              <input
                type="number"
                min={1}
                value={cfg.poll_interval}
                onChange={(e) =>
                  update('poll_interval', Math.max(1, Number(e.target.value) || 1))
                }
              />
            </div>
            <div className="field">
              <label>最大並發任務</label>
              <input
                type="number"
                min={1}
                value={cfg.max_concurrent_tasks}
                onChange={(e) =>
                  update('max_concurrent_tasks', Math.max(1, Number(e.target.value) || 1))
                }
              />
            </div>
            <div className="field">
              <label>瀏覽器類型</label>
              <select
                value={cfg.browser_type}
                onChange={(e) => update('browser_type', e.target.value)}
              >
                <option value="chrome">chrome</option>
                <option value="cloakbrowser">cloakbrowser (預留)</option>
              </select>
            </div>
            <div className="field-checkbox">
              <input
                id="show_browser"
                type="checkbox"
                checked={cfg.show_browser}
                onChange={(e) => update('show_browser', e.target.checked)}
              />
              <label htmlFor="show_browser">打開瀏覽器(取消勾選 = headless)</label>
            </div>
            <div className="field">
              <label>代理(可選,e.g. http://host:port)</label>
              <input
                type="text"
                value={cfg.proxy ?? ''}
                onChange={(e) => update('proxy', e.target.value || null)}
              />
            </div>
          </>
        )}
        <div className="modal-actions">
          <button onClick={onClose}>取消</button>
          <button className="primary" onClick={() => void handleSave()}>
            保存
          </button>
        </div>
      </div>
    </div>
  );
}
