## Lytrize-Clip Chromium Extension

**[📥 Click to Download Lytrize-Clip ](https://github.com/Kazake95/lytrize_desktop/releases/tag/Lytrize_Clip_Chromium_Extension)**

**Lytrize-Clip** is the companion Chromium extension for taking full-page screenshots of rendered webpages. It captures the entire rendered surface in one native screenshot — without scrolling, zooming, or viewport stitching — and downloads the result as a PNG.

It is especially useful for capturing Lytrize dashboards and other long pages that contain expanded dropdowns, modals, or lazy-loaded content.

### How it works

Lytrize-Clip uses the Chrome DevTools Protocol (`Page.captureScreenshot` with `captureBeyondViewport`) to capture the full rendered page as one image. The PNG is then saved through the browser's native download manager.

### Install on Linux

The extension package includes `Lytrize-Clip_installler.sh` and the unpacked `Lytrize-Clip/` extension directory.

> **Important:** Close your Chromium-based browser before running the installer. The `Lytrize-Clip/` folder must remain in the same directory as the installer script.

**First download the zip from above link**

**Then close your browser before installation**

```bash

cd Lytrize-Clip
chmod +x Lytrize-Clip_installler.sh
./Lytrize-Clip_installler.sh [browser-name]

```

Supported browser names:

- `chrome`
- `chromium`
- `edge`
- `brave`
- `opera`
- `vivaldi`
- `auto` (default)

For example :

```bash
./Lytrize-Clip_installler.sh chrome
```

The installer detects the browser profile, creates or reuses a persistent extension key, updates the browser preferences, and creates a backup of the preferences file. Modern Chromium browsers still require the extension to be loaded through **Developer mode**.

After the installer finishes:

**Restart your browser & pin it for quick access** after running the script.

> **Note:** The `Lytrize-Clip/` extension folder must sit in the same directory as the installer script.

### Manual installation (any OS)

1. Open `chrome://extensions/` (or the equivalent extensions page in your Chromium browser).
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `Lytrize-Clip/` folder from the extension package.

### Permissions

- `debugger` — required to access Chrome DevTools Protocol for native full-page capture
- `activeTab` — limits capture access to the current active tab
- `downloads` — saves the PNG through the browser download manager

Lytrize-Clip does not collect, transmit, or store captured page data.
