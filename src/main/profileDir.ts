// Mirror of pcauto/src/browser.rs::browser_profile_dir / sanitize_profile_component
// Plus a startup sweeper for orphan profiles older than 24h (TS-only addition,
// see PLAN.md §7 "Cleanup timing").

import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { mkdirSync, readdirSync, rmSync, statSync } from 'node:fs';

const ROOT_NAME = 'pcauto-chrome-profiles';
const ORPHAN_AGE_MS = 24 * 60 * 60 * 1000;

function sanitize(value: string): string {
  let s = '';
  for (const ch of value) {
    if (s.length >= 80) break;
    const c = ch.charCodeAt(0);
    const isAlpha = (c >= 0x30 && c <= 0x39) || (c >= 0x41 && c <= 0x5a) || (c >= 0x61 && c <= 0x7a);
    if (isAlpha || ch === '-' || ch === '_') s += ch;
    else s += '_';
  }
  if (s.length === 0) s = 'unknown';
  return s;
}

export function buildProfileDir(taskId: number, orderNo: string): string {
  const dir = join(
    tmpdir(),
    ROOT_NAME,
    `task-${taskId}-${sanitize(orderNo)}-${process.pid}-${Date.now()}`,
  );
  mkdirSync(dir, { recursive: true });
  return dir;
}

/** Best-effort recursive removal with up to 3 retries (Windows EBUSY mitigation). */
export async function cleanupProfileDir(dir: string): Promise<void> {
  for (let attempt = 0; attempt < 3; attempt++) {
    try {
      rmSync(dir, { recursive: true, force: true });
      return;
    } catch {
      await new Promise<void>((r) => setTimeout(r, 500));
    }
  }
}

/** Remove orphan profiles older than 24h on startup. */
export function sweepOrphanProfiles(): void {
  const root = join(tmpdir(), ROOT_NAME);
  let entries: string[];
  try {
    entries = readdirSync(root);
  } catch {
    return;
  }
  const now = Date.now();
  for (const name of entries) {
    const full = join(root, name);
    try {
      const st = statSync(full);
      if (now - st.mtimeMs > ORPHAN_AGE_MS) {
        rmSync(full, { recursive: true, force: true });
      }
    } catch {
      /* ignore */
    }
  }
}
