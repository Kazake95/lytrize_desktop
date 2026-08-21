<div align="center">

# Lytrize Desktop

**Local-first data analytics for Linux — no cloud, no account, no setup.**

Upload a CSV or Excel file and get interactive charts and dashboards in seconds. Everything stays on your device.

[![Platform](https://img.shields.io/badge/platform-Linux%20(amd64)-blue?style=flat-square)](https://github.com/Kazake95/lytrize_desktop)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-831729?style=flat-square)](./LICENSE)

</div>

<div align="center">

![Lytrize Logo](backend/assets/lytrize.png)

**[📥 Download Desktop App](https://github.com/Kazake95/lytrize_desktop/releases)**

</div>

---

## Screenshots

| Start Up | Home Screen | Backup/Restore |
|---|---|---|
| ![Start Up](backend/assets/screenshots/3.png) | ![Home Screen](backend/assets/screenshots/4.png) | ![Backup/Restore](backend/assets/screenshots/5.png) |

| Upload | Analysis | Dashboard building |
|---|---|---|
| ![Upload](backend/assets/screenshots/6.png) | ![Analysis page](backend/assets/screenshots/7.png) | ![Dashboard](backend/assets/screenshots/10.png)

---

## Quick Start

1. **Install** — grab the `.deb` or `.rpm` from the [releases page](https://github.com/Kazake95/lytrize_desktop/releases) and install with `dpkg -i` or `dnf install`.
2. **Open** — launch `lytrize` from your application menu or terminal. The launcher window appears while the backend starts, then your browser opens automatically.
3. **Upload** — click **Start New Analysis** on the home screen and choose a CSV or Excel file (up to 400 MB).
4. **Analyze** — on the Analysis page, click any chart-type card (bar, time series, scatter, correlation, etc.), choose your columns, and click **Generate**. Charts appear instantly.
5. **Build & Export** — click **Proceed to Dashboard**, arrange your charts in a grid, add KPI cards, then **Download HTML** to get a standalone file you can open in any browser or save as PNG via DevTools.

---

## Highlights

| | |
|---|---|
| **📊 11 chart types** | Bar, pie/donut, scatter, histogram, time series, correlation, pivot table, matrix heatmap, geographic map, outlier, and data quality |
| **🗂️ Dashboard builder** | Arrange charts in a portrait (2-column) or landscape (3-column) grid, add KPI summary cards, set a title |
| **📤 Export** | Download as a self-contained HTML file — then use your browser's DevTools to save as PNG |
| **🧹 Data tools** | Rename columns, add calculated columns, change data types, flag outliers, and handle missing values before analysis |
| **🔄 Auto-update** | Re-upload updated datasets and automatically regenerate all charts and KPIs — column renames and calculated columns are preserved |
| **💾 Session backup & restore** | Save local session backups and restore any compatible JSON backup, including ones shared by other users |
| **🔒 Fully offline** | No telemetry, no analytics, no outbound network requests |
| **🚀 Fast** | Chunked CSV reader, dtype optimization, and smart sampling handle files up to 400 MB |

---

## What is Lytrize?

Lytrize is a desktop analytics app that runs entirely on your computer. Drop in a spreadsheet and get charts, statistics, and a shareable dashboard. No internet connection needed, no sign-up, no data ever leaving your machine.

Built for people who work with data often and want answers fast — without opening a browser tab, logging into a service, or waiting for a cloud query to finish.

### Desktop Launcher

Lytrize includes a native desktop launcher (PySide6) that manages the backend and opens the app in an isolated browser window. The launcher provides:

- **Browser selection** — choose Chrome, Chromium, Firefox, Brave, Edge, Vivaldi, Opera, or your default browser
- **Isolated profiles** — Chromium-based browsers launch in app mode (`--app=`) with a separate profile; Firefox gets a clean isolated profile with `--kiosk`
- **System tray integration** — the app lives in the tray while running
- **Crash recovery** — if the backend crashes, the launcher shows a recoverable error instead of going blank
- **Progress indicator** — animated status dot and progress bar during startup

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **OS** | Linux (Ubuntu 20.04 LTS or later; Debian-based or RPM-based) | Ubuntu 22.04 LTS or later |
| **Architecture** | amd64 (64-bit) | amd64 (64-bit) |
| **Python** | 3.11+ (only for building from source) | 3.11+ |
| **Browser** | Any installed browser — Chrome, Chromium, Firefox, Brave, or Edge | Chromium-based (best experience) |
| **Disk** | ~1.3 GB installed (1.1 GB app + 147 MB user data) | ~1.3 GB |
| **RAM** | 6 GB minimum | 8 GB+ for files over 100 MB |

---

## Install

### Option 1 — Debian / Ubuntu (.deb) 

```bash
sudo dpkg -i lytrize_1.0_amd64.deb
```

If `dpkg` reports missing dependencies:

```bash
sudo apt-get install -f
```

Launch from your application menu, or run:

```bash
lytrize
```

No manual Python setup, no `pip install`, no virtual environment to activate. The package bundles its own isolated Python virtual environment at `/opt/lytrize/venv/`.

### Option 2 — Fedora / RHEL / openSUSE (.rpm)

```bash
sudo dnf install lytrize-1.0-1.x86_64.rpm
# or on older systems:
sudo rpm -i lytrize-1.0-1.x86_64.rpm
```

### Option 3 — Build from source

See [CONTRIBUTING.md](./CONTRIBUTING.md#development-setup) for the full developer setup.

---

## How to Use Lytrize

### 1. Open the app
Launch Lytrize from your application menu or run `lytrize` in a terminal. A launcher window appears while the Streamlit backend starts, then your browser opens automatically.

### 2. Upload a file
Click **Start New Analysis** on the home screen and choose a CSV or Excel file. Lytrize shows a preview and lets you rename columns, add calculated columns, fix data types, and flag outliers before proceeding.

### 3. Run an analysis
On the Analysis page, click any chart-type card — bar chart, time series, scatter plot, correlation heatmap, and so on. Choose your columns and options, then click **Generate**. Charts appear right away.

### 4. Build a dashboard
Charts you generate collect in your session. Click **Proceed to Dashboard** to arrange them, add KPI summary cards, set a title, and pick a portrait (2-column) or landscape (3-column) layout.

### 5. Save, back up, and export
Your session saves automatically as you work. Use **Save Session** to make a named checkpoint you can see on the home screen. Use **Restore Backup** to import any compatible JSON backup from another user or from your own archive. Use **Download HTML** to get a standalone file you can open in any browser or share with someone else. Save the HTML page as PNG using your browser's DevTools screenshot tool.

### 6. Update your data
If you need to update your dataset, go to the Home page, click **Edit** on a saved session, and re-upload the modified file. Lytrize automatically reapplies your column renames and calculated columns, then regenerates all charts and KPIs with the new data.

---
## Lytrize-Clip Chromium Extension

**[📥 Download Lytrize-Clip Releases](https://github.com/Kazake95/lytrize_desktop/releases/tag/Lytrize_Clip_Chromium_Extension)**

**Lytrize-Clip** is the companion Manifest V3 Chromium extension for taking full-page screenshots of rendered webpages.

It captures the entire rendered document as **one native DevTools Protocol screenshot** — without scrolling, zooming, viewport stitching, or combining multiple screenshots.

It is especially useful for long dashboards and pages containing expanded dropdowns, modals, fixed-position UI, or dynamically rendered content.

### How it works

Lytrize-Clip uses `chrome.debugger` and the Chrome DevTools Protocol:

1. `Page.getLayoutMetrics` determines the page's intrinsic layout/content size.
2. `Page.captureScreenshot` captures the rendered page.
3. `captureBeyondViewport: true` captures content outside the visible viewport.
4. The resulting PNG is saved through the browser's native download manager.

The extension does **not** resize the viewport, scroll the page, or stitch multiple images together. This avoids changing responsive layout conditions during capture.

### Important: local `file://` pages

Chromium requires a user-controlled permission for extensions that access local files.

For a page such as:

```text
file:///home/user/Downloads/Saved_Session.html
```

open the browser's extension details page and enable:

**Allow access to file URLs**

For Chrome/Chromium:

```text
chrome://extensions/
```

Then open **Lytrize-Clip → Details → Allow access to file URLs**.

Without this setting, Chromium can reject the debugger attachment with:

> Cannot attach to this target.

Lytrize-Clip checks this condition before attaching and directs the user to the extension settings.

> **Important:** This setting is controlled by Chromium and cannot be enabled automatically by an extension.

### Install on Linux

The release package contains the installer script and the unpacked extension directory:

```text
Lytrize-Clip_ext/
├── Lytrize-Clip_installler.sh
└── Lytrize-Clip/
```

> The installer filename currently uses `installler` (three `l`s).

**First download the ZIP from the GitHub release link above.**

**Close all Chromium-based browsers before running the installer.**

```bash
cd Lytrize-Clip_ext
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

Example:

```bash
./Lytrize-Clip_installler.sh chrome
```

The installer detects the browser profile, creates or reuses a persistent extension key, updates browser extension preferences, enables Developer Mode, and creates a backup of the Preferences file.

After installation:

**Restart your browser and pin Lytrize-Clip for quick access.**

### Manual installation (any OS)

1. Open the browser's extensions page.
   - Chrome/Chromium: `chrome://extensions/`
   - Edge: `edge://extensions/`
   - Brave: `brave://extensions/`
   - Opera: `opera://extensions/`
   - Vivaldi: `vivaldi://extensions/`
2. Enable **Developer mode**.
3. Click **Load unpacked**.
4. Select the `Lytrize-Clip/` folder from the release package.

For local `file://` pages, also enable **Allow access to file URLs** in the extension's details page.

### Permissions

- `debugger` — required to access Chrome DevTools Protocol for native full-page capture
- `activeTab` — targets the current active tab
- `downloads` — saves the PNG through the browser download manager

There is no `host_permissions` entry in the current manifest. Local `file://` access remains controlled separately by Chromium's **Allow access to file URLs** setting.

### Compatibility

Lytrize-Clip targets current Manifest V3 Chromium-based browsers and is intended for:

- Google Chrome
- Chromium
- Microsoft Edge
- Brave
- Opera
- Vivaldi

Browser-specific behavior may vary with Chromium updates.

### Known limitation

A single native Chromium screenshot has practical bitmap and dimension limits. Extremely large documents can exceed those limits. Lytrize-Clip reports such failures rather than silently truncating the capture.

### Privacy

Lytrize-Clip does not collect, upload, transmit, or externally store captured page content or screenshots.

---
## Chart Types

| Chart | What it does |
|---|---|
| **Descriptive** | Full summary statistics table (count, mean, std, min, max, quartiles) |
| **Statistical** | Mean, median, min, max, std for numeric columns grouped by a category |
| **Distribution** | Histograms and boxplots for numeric columns |
| **Correlation** | Correlation matrix heatmap across numeric columns |
| **Categorical Bar** | Bar/column charts from categorical dimensions and numeric metrics |
| **Pie & Donut** | Share-of-total charts with sorting and top-N filtering |
| **Time Series** | Trends over time with date grouping (year, month, day, hour) and aggregation |
| **Scatter Plot** | Variable relationships with optional trendlines (OLS or LOWESS) |
| **Matrix Heatmap** | Cross-tabulation heatmap (pivot table as a heatmap) |
| **Pivot Table** | Cross-tabulation table (pivot table as a data table) |
| **Map Plot** | Geographic scatter (lat/lon) or choropleth (country/region names) |
| **Outlier** | IQR-based outlier detection across numeric columns |
| **Data Quality** | Missing values, duplicate rows, and column quality summary |

---

## Where is My Data Stored?

Everything lives on your machine:

| What | Where |
|---|---|
| Sessions, charts, KPIs, dashboard layouts | `~/.local/share/lytrize/lytrize.db` (SQLite) |
| Active DataFrame (in-session) | `$XDG_RUNTIME_DIR/lytrize/df_<id>.parquet` (RAM-backed tmpfs if available; falls back to `~/.cache/lytrize/`) |
| Launcher preferences (browser choice) | `~/.local/share/lytrize/launcher_prefs.json` |
| Browser profiles (isolated) | `~/.local/share/lytrize/browser-profiles/` |
| Backend log | Streamlit writes to stderr by default; check terminal output or redirect to a file |

The parquet snapshot is used to restore your loaded dataset after a browser tab refresh. It is not kept across reboots if stored on tmpfs — if the app restarts after a reboot and your file is gone, you will be asked to re-upload.

---

## Uninstall

```bash
sudo dpkg -r lytrize          # Debian / Ubuntu
sudo dnf remove lytrize       # Fedora / RHEL
```

> **⚠️ Warning:** The package uninstaller **removes all user data** — including saved sessions, dashboards, and the local database at `~/.local/share/lytrize/`. Back up your sessions first (Home → **Restore Backup** → **Backup**) if you want to keep them.

---

## Troubleshooting

**The app does not start**
Run `lytrize` from a terminal to see live output. Check the terminal for Python tracebacks. The backend log is also written to `~/.local/share/lytrize/streamlit.log`.

**Missing dependencies after install**
Run `sudo apt-get install -f` (Debian/Ubuntu) or `sudo dnf install -f` (Fedora/RHEL) then try again.

**Downloading as PNG / image**
The app exports a standalone HTML file. To save that page as a PNG, use your browser's built-in screenshot tools:

- **Chrome/Edge/Opera/Brave:** Open DevTools (`Ctrl+Shift+I`), then `Ctrl+Shift+P`, type "screenshot", choose **Capture full size screenshot**
- **Firefox/LibreWolf:** `Ctrl+Shift+S` (or right-click → *Take Screenshot*)

**The browser does not open automatically**
If no supported browser is detected, copy `http://127.0.0.1:8501` into any browser while the launcher window shows "Running".

**Large files are slow**
Lytrize uses smart sampling for scatter plots (8,000 points) and maps (5,000 points), plus chunked reading for CSVs over 30 MB. For best performance with files over 100 MB, use 8 GB+ RAM.

**Something looks broken**
Check the terminal output for Python tracebacks. If the issue happens again, open an issue and attach the log.

**Database corruption**
If the app fails to start with a SQLite error, your database may be corrupt. Close the app completely, then:
```bash
rm ~/.local/share/lytrize/lytrize.db
```
Restart the app — a fresh database will be created automatically. Your saved sessions will be lost (use **Restore Backup** to recover from a JSON backup if you have one).

---
## Upcoming development plan

**1. Light mode theme**

**2. Dynamic filter/slicer per chart**

**3. UI improvements & minor bug fixes**

---

## Contributing

Lytrize is open source. Bug reports, feature requests, and pull requests are welcome.

Before opening a PR, please read [CONTRIBUTING.md](./CONTRIBUTING.md) for the full development setup, architecture overview, and contribution guidelines.

---

## License

MIT — see [LICENSE](./LICENSE) for the full text.
