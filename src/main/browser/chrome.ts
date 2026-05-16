// Mirror of pcauto/src/browser.rs::find_system_chrome

import { existsSync } from 'node:fs';
import { join } from 'node:path';

export function findSystemChrome(): string | undefined {
  const candidates: string[] = [];
  const platform = process.platform;
  if (platform === 'win32') {
    const pf = process.env['ProgramFiles'] ?? 'C:\\Program Files';
    const pf86 = process.env['ProgramFiles(x86)'] ?? 'C:\\Program Files (x86)';
    const local = process.env['LOCALAPPDATA'] ?? '';
    candidates.push(
      join(pf, 'Google\\Chrome\\Application\\chrome.exe'),
      join(pf, 'Chromium\\Application\\chrome.exe'),
      join(pf86, 'Google\\Chrome\\Application\\chrome.exe'),
      join(pf86, 'Chromium\\Application\\chrome.exe'),
    );
    if (local) {
      candidates.push(join(local, 'Google\\Chrome\\Application\\chrome.exe'));
    }
  } else if (platform === 'darwin') {
    const home = process.env['HOME'] ?? '';
    candidates.push(
      '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
      '/Applications/Chromium.app/Contents/MacOS/Chromium',
    );
    if (home) {
      candidates.push(
        join(home, 'Applications/Google Chrome.app/Contents/MacOS/Google Chrome'),
      );
    }
  } else if (platform === 'linux') {
    candidates.push(
      '/usr/bin/google-chrome',
      '/usr/bin/google-chrome-stable',
      '/usr/bin/chromium-browser',
      '/usr/bin/chromium',
      '/snap/bin/chromium',
    );
  }
  return candidates.find((p) => {
    try {
      return existsSync(p);
    } catch {
      return false;
    }
  });
}
