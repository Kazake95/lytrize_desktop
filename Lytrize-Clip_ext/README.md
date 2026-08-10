# Lytrize-Clip

A Chromium extension that captures full-page screenshots of any webpage — including expanded dropdowns, modals, and lazy-loaded content — in a single native shot. No scrolling, no zooming, no viewport stitching.

## How it works

Uses Chrome DevTools Protocol (`Page.captureScreenshot` with `captureBeyondViewport`) to capture the entire rendered surface exactly as you see it, then downloads the PNG via the browser's native download manager.

## Install (Linux)

```bash
**Download - **https://github.com/Kazake95/lytrize######
cd Lytrize-Clip
chmod +x Lytrize-Clip_installer.sh
./Lytrize-Clip_installer.sh [browser-name]
```

`browser-name`: `chrome` | `chromium` | `edge` | `brave` | `opera` | `vivaldi` | `auto` (default)

**Restart your browser & pin it for quick access** after running the script.

> **Note:** The `Lytrize-Clip/` extension folder must sit in the same directory as the installer script.

## Manual install (any OS)

1. Open `chrome://extensions`
2. Enable **Developer mode**
3. Click **Load unpacked**
4. Select the `Lytrize-Clip` folder

## Permissions

- `debugger` — required to access Chrome DevTools Protocol for native full-page capture
- `activeTab` — captures the current tab only
- `downloads` — saves the PNG via the browser download manager

No data is collected, transmitted, or stored.

## License

MIT
