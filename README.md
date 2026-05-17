# autobrowser-next

Electron + TypeScript + Playwright re-implementation of the Rust autobrowser.
Behaviour parity with the Rust version is the design goal — every step action,
HMAC signature, and API call must remain byte-identical so the existing
`trader-system` backend keeps working unchanged.

> Project rule: only files under `autobrowser/autobrowser-next/` belong to this
> migration. The Rust code in `autobrowser/src/` is retained for reference.

## Quick start

```sh
cd autobrowser/autobrowser-next
npm install
cp config.json.example config.json   # then fill in api_key / hmac_secret
npm run build
npm start                            # launches the Electron GUI
```

Development mode (Vite HMR for the renderer, tsc --watch for main):

```sh
npm run dev:renderer    # renderer dev server on :5173
npm run dev:main        # tsc --watch for main process
# in a third terminal:
AUTOBROWSER_DEV=1 npx electron .
```

## Configuration

`config.json` is read from (in order):

1. `process.cwd()/config.json` (development)
2. `<execPath>/../config.json` (packaged)
3. `app.getPath('userData')/config.json` (Electron preferred)

The example file uses placeholder secrets — fill in real values before running.

Fields (mirror of Rust `AppConfig`):

| field | meaning |
| --- | --- |
| `server_url` | Backend base URL, e.g. `https://api.example.com` |
| `api_key` | Sent as `X-AutoBrowser-Key` header |
| `hmac_secret` | Used to sign final callbacks (`HMAC-SHA256(order_no|status|timestamp)`) |
| `poll_interval` | Seconds between `/pending-tasks` calls |
| `max_concurrent_tasks` | p-limit slot count |
| `browser_type` | `chrome` (default). `cloakbrowser` reserved for Phase 2 |
| `show_browser` | `false` → headless |
| `proxy` | optional `http://host:port` |

## Project layout

```
autobrowser-next/
├── package.json
├── tsconfig*.json           # main / preload / renderer compile configs
├── vite.config.ts           # renderer only
├── electron-builder.yml
├── src/
│  ├── shared/               # ipc channels + AppConfig (main+renderer)
│  ├── main/
│  │  ├── index.ts           # Electron entry (= main.rs)
│  │  ├── ipc.ts             # IPC handler registration
│  │  ├── poller.ts          # scan loop + p-limit (= poller.rs)
│  │  ├── config.ts          # config.json load/save (= config.rs)
│  │  ├── template.ts        # {{var}} substitution + unresolvedSinglePlaceholder
│  │  ├── types.ts           # StepAction/TaskData parsing (= models.rs)
│  │  ├── logger.ts          # log classifier + broadcaster
│  │  ├── profileDir.ts      # per-task Chrome profile directories
│  │  ├── api/
│  │  │  ├── http.ts         # fetch wrapper with timeouts
│  │  │  └── callback.ts     # 9 endpoints + HMAC (= callback.rs)
│  │  ├── browser/
│  │  │  ├── chrome.ts       # find_system_chrome
│  │  │  └── executor.ts     # BrowserExecutor (step loop, captcha watchdog)
│  │  └── actions/
│  │     ├── index.ts        # action registry
│  │     ├── types.ts        # ActionContext + ActionHandler
│  │     ├── _helpers.ts     # fillWithVerify, waitForAnyVisible, etc.
│  │     ├── navigate.ts
│  │     ├── captchaPrefetch.ts
│  │     ├── input.ts
│  │     ├── type.ts
│  │     ├── click.ts
│  │     ├── select.ts
│  │     ├── dropdown.ts
│  │     ├── waitText.ts
│  │     ├── waitSelector.ts
│  │     ├── waitGa.ts
│  │     ├── captchaImage.ts
│  │     ├── wait.ts
│  │     ├── screenshot.ts
│  │     ├── js.ts
│  │     └── scroll.ts
│  ├── preload/index.ts       # contextBridge -> window.autobrowser
│  └── renderer/              # React UI (= ui/app.rs)
│     ├── index.html
│     ├── main.tsx
│     ├── App.tsx
│     ├── types.d.ts
│     ├── store/useAppStore.ts
│     ├── components/
│     │  ├── StatusCard.tsx
│     │  ├── ControlBar.tsx
│     │  ├── LogPanel.tsx
│     │  └── SettingsDialog.tsx
│     └── styles/globals.css
└── resources/                # app icons (placeholder)
```

## Step action coverage

15 actions, plus the 3 aliases `request_captcha` and `captcha` that map to
`captcha_image`. Behaviour parity rules to be aware of:

* `dropdown` default `option_selector` — the string in
  `src/main/actions/dropdown.ts::DEFAULT_OPTION_SELECTOR` must remain byte-for-byte
  identical with `browser.rs:710`.
* `input` action checks for an *unresolved single placeholder*
  (`{{name}}` only) before filling; on hit, it triggers `request_ga` +
  `poll_ga`. See `template.ts::unresolvedSinglePlaceholder`.
* `wait_ga` reuses cached `code` / `ga_code` from a prior
  `captcha_prefetch` so the GA countdown does not pop up twice.
* `captcha_prefetch` writes both `code` and `ga_code` keys after polling
  `/get-credentials`.

## Test plan (Phase 1 acceptance is owned by agent C)

* HMAC `({secret, order_no, status, ts}) -> hex` must match Rust output bit-for-bit.
* `dropdown` default `option_selector` string equality.
* `unresolvedSinglePlaceholder` fixture parity.
* Smoke test: SEAB / OCB / ACB at least 3 orders each.
