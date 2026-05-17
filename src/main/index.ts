// Electron main process entry. Mirrors autobrowser/src/main.rs.

import { app, BrowserWindow, shell } from 'electron';
import { join } from 'node:path';
import { existsSync } from 'node:fs';
import { registerIpcHandlers } from './ipc';
import { poller } from './poller';
import { sweepOrphanProfiles } from './profileDir';

const isDev = !!process.env.AUTOBROWSER_DEV;
const VITE_DEV_SERVER = process.env.VITE_DEV_SERVER_URL ?? 'http://localhost:5173';

let mainWindow: BrowserWindow | undefined;

function createWindow(): void {
  const preloadPath = join(__dirname, '..', 'preload', 'index.js');
  mainWindow = new BrowserWindow({
    width: 380,
    height: 720,
    minWidth: 320,
    minHeight: 480,
    alwaysOnTop: true,
    title: 'AutoBrowser',
    titleBarStyle: process.platform === 'darwin' ? 'hiddenInset' : 'default',
    backgroundColor: '#F2F2F7',
    webPreferences: {
      preload: existsSync(preloadPath) ? preloadPath : undefined,
      contextIsolation: true,
      nodeIntegration: false,
      sandbox: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    void shell.openExternal(url);
    return { action: 'deny' };
  });

  if (isDev) {
    void mainWindow.loadURL(VITE_DEV_SERVER);
    mainWindow.webContents.openDevTools({ mode: 'detach' });
  } else {
    const indexHtml = join(__dirname, '..', 'renderer', 'index.html');
    void mainWindow.loadFile(indexHtml);
  }

  mainWindow.on('closed', () => {
    mainWindow = undefined;
  });
}

void app.whenReady().then(() => {
  sweepOrphanProfiles();
  registerIpcHandlers();
  createWindow();
  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) createWindow();
  });
});

app.on('window-all-closed', () => {
  void poller.stop().finally(() => {
    if (process.platform !== 'darwin') app.quit();
  });
});

app.on('before-quit', () => {
  void poller.stop();
});
