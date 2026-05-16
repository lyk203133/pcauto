// AppConfig is shared between main and renderer (renderer reads/writes via IPC).
// Field names mirror the Rust `AppConfig` struct (snake_case on disk).

export interface AppConfig {
  server_url: string;
  api_key: string;
  hmac_secret: string;
  poll_interval: number;
  max_concurrent_tasks: number;
  browser_type: string;
  show_browser: boolean;
  proxy: string | null;
}

export const DEFAULT_CONFIG: AppConfig = {
  server_url: 'http://localhost:8088',
  api_key: '',
  hmac_secret: '',
  poll_interval: 5,
  max_concurrent_tasks: 3,
  browser_type: 'chrome',
  show_browser: true,
  proxy: null,
};
