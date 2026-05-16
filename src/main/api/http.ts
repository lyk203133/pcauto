// Thin wrapper around global fetch with a per-request timeout helper.
// Node 18+ ships fetch globally, so no external dependency is required.

export interface FetchOpts {
  method?: 'GET' | 'POST';
  headers?: Record<string, string>;
  body?: string;
  timeoutMs?: number;
  signal?: AbortSignal;
}

export interface FetchResult {
  ok: boolean;
  status: number;
  text: string;
}

export async function httpRequest(url: string, opts: FetchOpts = {}): Promise<FetchResult> {
  const controller = new AbortController();
  let timer: ReturnType<typeof setTimeout> | undefined;
  if (opts.timeoutMs && opts.timeoutMs > 0) {
    timer = setTimeout(() => controller.abort(new Error('timeout')), opts.timeoutMs);
  }
  let outerAbort: (() => void) | undefined;
  if (opts.signal) {
    if (opts.signal.aborted) controller.abort(opts.signal.reason);
    else {
      outerAbort = () => controller.abort(opts.signal!.reason);
      opts.signal.addEventListener('abort', outerAbort, { once: true });
    }
  }
  try {
    const resp = await fetch(url, {
      method: opts.method ?? 'GET',
      headers: opts.headers,
      body: opts.body,
      signal: controller.signal,
    });
    const text = await resp.text();
    return { ok: resp.ok, status: resp.status, text };
  } finally {
    if (timer) clearTimeout(timer);
    if (outerAbort && opts.signal) opts.signal.removeEventListener('abort', outerAbort);
  }
}

export function safeJsonParse<T = unknown>(text: string): T | undefined {
  try {
    return JSON.parse(text) as T;
  } catch {
    return undefined;
  }
}
