// IPC handler registration. Renderer talks to main exclusively via these channels.

import { ipcMain } from 'electron';
import { Ch } from '../shared/ipc-channels';
import type { AppConfig } from '../shared/config';
import { loadConfig, saveConfig } from './config';
import { poller } from './poller';
import { log } from './logger';

export function registerIpcHandlers(): void {
  ipcMain.handle(Ch.StartPoller, () => {
    poller.start();
    return poller.isRunning();
  });

  ipcMain.handle(Ch.StopPoller, async () => {
    await poller.stop();
    return poller.isRunning();
  });

  ipcMain.handle(Ch.GetConfig, (): AppConfig => {
    return loadConfig();
  });

  ipcMain.handle(Ch.SaveConfig, (_event, cfg: AppConfig): boolean => {
    try {
      saveConfig(cfg);
      return true;
    } catch (e) {
      log(`❌ 保存配置失敗: ${(e as Error).message}`);
      return false;
    }
  });

  ipcMain.handle(Ch.GetIsRunning, (): boolean => {
    return poller.isRunning();
  });
}
