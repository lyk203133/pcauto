// Mirror of pcauto/src/config.rs
//
// Load order:
//   1. cwd/config.json (development)
//   2. dirname(process.execPath)/config.json (packaged)
//   3. app.getPath('userData')/config.json (Electron-preferred — created if needed)
//
// We follow the Rust behaviour of merging missing keys with defaults so older
// configs keep working when new fields are added.

import { existsSync, readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { dirname, join } from 'node:path';
import { app } from 'electron';
import type { AppConfig } from '../shared/config';
import { DEFAULT_CONFIG } from '../shared/config';

function candidatePaths(): string[] {
  const paths: string[] = [];
  paths.push(join(process.cwd(), 'config.json'));
  try {
    paths.push(join(dirname(process.execPath), 'config.json'));
  } catch {
    /* ignore */
  }
  try {
    paths.push(join(app.getPath('userData'), 'config.json'));
  } catch {
    /* Electron app not ready yet — skip */
  }
  return paths;
}

function configPathForWrite(): string {
  for (const p of candidatePaths()) {
    if (existsSync(p)) return p;
  }
  // First write: prefer userData; fall back to cwd.
  try {
    const dir = app.getPath('userData');
    mkdirSync(dir, { recursive: true });
    return join(dir, 'config.json');
  } catch {
    return join(process.cwd(), 'config.json');
  }
}

function mergeWithDefaults(value: unknown): AppConfig {
  const out: AppConfig = { ...DEFAULT_CONFIG };
  if (value && typeof value === 'object') {
    const v = value as Record<string, unknown>;
    if (typeof v['server_url'] === 'string') out.server_url = v['server_url'];
    if (typeof v['api_key'] === 'string') out.api_key = v['api_key'];
    if (typeof v['hmac_secret'] === 'string') out.hmac_secret = v['hmac_secret'];
    if (typeof v['poll_interval'] === 'number') out.poll_interval = v['poll_interval'];
    if (typeof v['max_concurrent_tasks'] === 'number') {
      out.max_concurrent_tasks = v['max_concurrent_tasks'];
    }
    if (typeof v['browser_type'] === 'string') out.browser_type = v['browser_type'];
    if (typeof v['show_browser'] === 'boolean') out.show_browser = v['show_browser'];
    if (typeof v['proxy'] === 'string') out.proxy = v['proxy'];
    else if (v['proxy'] === null) out.proxy = null;
  }
  return out;
}

export function loadConfig(): AppConfig {
  for (const p of candidatePaths()) {
    if (!existsSync(p)) continue;
    try {
      const text = readFileSync(p, 'utf8');
      const parsed = JSON.parse(text) as unknown;
      return mergeWithDefaults(parsed);
    } catch (err) {
      // Log to stderr and continue trying other paths.
      // eslint-disable-next-line no-console
      console.warn(`[config] failed to parse ${p}: ${(err as Error).message}`);
    }
  }
  return { ...DEFAULT_CONFIG };
}

export function saveConfig(cfg: AppConfig): void {
  const path = configPathForWrite();
  const dir = dirname(path);
  try {
    mkdirSync(dir, { recursive: true });
  } catch {
    /* ignore */
  }
  writeFileSync(path, JSON.stringify(cfg, null, 2), 'utf8');
}

export function configFilePath(): string {
  for (const p of candidatePaths()) {
    if (existsSync(p)) return p;
  }
  return configPathForWrite();
}
