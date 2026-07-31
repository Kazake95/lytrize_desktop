<div align="center">

# Lytrize Desktop

**Local-first data analytics for Linux — no cloud, no account, no setup.**

Upload a CSV or Excel file and get interactive charts, dashboards, and insights in seconds. Everything stays on your device.

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
3. **Upload** — click **Start New Analysis** on the home screen and choose a CSV or Excel file (up to 300 MB).
4. **Analyze** — on the Analysis page, click any chart-type card (bar, time series, scatter, correlation, etc.), choose your columns, and click **Generate**. Charts appear instantly with auto-generated insights.
5. **Build & Export** — click **Proceed to Dashboard**, arrange your charts in a grid, add KPI cards, then **Download HTML** to get a standalone file you can open in any browser or save as PNG via DevTools.

---

## Highlights

| | |
|---|---|
| **📊 11 chart types** | Bar, pie/donut, scatter, histogram, time series, correlation, pivot table, matrix heatmap, geographic map, outlier, and data quality |
| **🔍 Auto insights** | Plain-English observations generated for every chart automatically |
| **🗂️ Dashboard builder** | Arrange charts in a portrait (2-column) or landscape (3-column) grid, add KPI summary cards, set a title |
| **📤 Export** | Download as a self-contained HTML file — then use your browser's DevTools to save as PNG |
| **🧹 Data tools** | Rename columns, change data types, flag outliers, and handle missing values before analysis |
| **💾 Session backup & restore** | Save local session backups and restore any compatible JSON backup, including ones shared by other users |
| **🔒 Fully offline** | No telemetry, no analytics, no outbound network requests |
| **🚀 Fast** | Chunked CSV reader, dtype optimization, and smart sampling handle files up to 300 MB |

---

## What is Lytrize?

Lytrize is a desktop analytics app that runs entirely on your computer. Drop in a spreadsheet and get charts, statistics, and a shareable dashboard. No internet connection needed, no sign-up, no data ever leaving your machine.

Built for people who work with data often and want answers fast — without opening a browser tab, logging into a service, or waiting for a cloud query to finish.

### Desktop Launcher

Lytrize includes a native desktop launcher (PySide6) that manages the backend and opens the app in an isolated browser window. The launcher provides:

- **Browser selection** — choose Chrome, Chromium, Firefox, Brave, Edge, or your default browser
- **Isolated profiles** — Chromium-based browsers launch in app mode (`--app=`) with a separate profile; Firefox gets a clean isolated profile with `--kiosk`
- **System tray integration** — the app lives in the tray while running
- **Crash recovery** — if the backend crashes, the launcher shows a recoverable error instead of going blank

---

## System Requirements

| Requirement | Minimum | Recommended |
|---|---|---|
| **OS** | Linux (Ubuntu 20.04 LTS or later; Debian-based or RPM-based) | Ubuntu 22.04 LTS or later |
| **Architecture** | amd64 (64-bit) | amd64 (64-bit) |
| **Python** | 3.11+ (only for building from source) | 3.11+ |
| **Browser** | Any installed browser — Chrome, Chromium, Firefox, Brave, or Edge | Chromium-based (best experience) |
| **Disk** | ~400 MB installed (includes isolated Python venv) | ~400 MB |
| **RAM** | 2 GB minimum | 4 GB+ for files over 100 MB |

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
Click **Start New Analysis** on the home screen and choose a CSV or Excel file. Lytrize shows a preview and lets you rename columns, fix data types, and flag outliers before proceeding.

### 3. Run an analysis
On the Analysis page, click any chart-type card — bar chart, time series, scatter plot, correlation heatmap, and so on. Choose your columns and options, then click **Generate**. Charts appear right away with auto-generated insights.

### 4. Build a dashboard
Charts you generate collect in your session. Click **Proceed to Dashboard** to arrange them, add KPI summary cards, set a title, and pick a portrait (2-column) or landscape (3-column) layout.

### 5. Save, back up, and export
Your session saves automatically as you work. Use **Save Session** to make a named checkpoint you can see on the home screen. Use **Restore Backup** to import any compatible JSON backup from another user or from your own archive. Use **Download HTML** to get a standalone file you can open in any browser or share with someone else. Save the HTML page as PNG using your browser's DevTools screenshot tool.

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

User data at `~/.local/share/lytrize/` is **not** removed by the package uninstaller. Delete it manually if you want a complete clean:

```bash
rm -rf ~/.local/share/lytrize
```

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
Lytrize uses smart sampling for scatter plots and maps (default 8,000 points) and chunked reading for CSVs over 30 MB. For best performance with files over 100 MB, use 4 GB+ RAM.

**Something looks broken**
Check the terminal output for Python tracebacks. If the issue happens again, open an issue and attach the log.

**Database corruption**
If the app fails to start with a SQLite error, your database may be corrupt. Close the app completely, then:
```bash
rm ~/.local/share/lytrize/lytrize.db
```
Restart the app — a fresh database will be created automatically. Your saved sessions will be lost (use **Restore Backup** to recover from a JSON backup if you have one).

---
## Upcoming updates

**Official chromium extension for one click full page screenshot**

**Light mode theme**

**UI improvements & minor bug fixes**

---

## Contributing

Lytrize is open source. Bug reports, feature requests, and pull requests are welcome.

Before opening a PR, please read [CONTRIBUTING.md](./CONTRIBUTING.md) for the full development setup, architecture overview, and contribution guidelines.

---

## License

MIT — see [LICENSE](./LICENSE) for the full text.
