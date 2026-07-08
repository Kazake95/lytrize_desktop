<div align="center">

# Lytrize Desktop

**Local-first data analytics for Linux — no cloud, no account, no setup.**

Upload a CSV or Excel file and get interactive charts, dashboards, and insights in seconds. Everything stays on your device.

[![Platform](https://img.shields.io/badge/platform-Linux%20\(amd64\)-blue?style=flat-square)](https://github.com/Kazake95/lytrize_desktop)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square\&logo=python\&logoColor=white)](https://python.org)

</div>

<div align="center">

![Lytrize Logo](backend/assets/lytrize.png)

**[📥 Download Desktop App](https://github.com/Kazake95/lytrize_desktop/releases)**

</div>

### Highlights

- **Saved session backups** — create local backup files for your analyses and dashboards.
- **Restore from JSON backups** — import any compatible JSON backup file, including backups shared by other users.
- **Local-first workflow** — no cloud, no account, no data leaving your device.

---

## What is Lytrize?

Lytrize is a desktop analytics app that runs entirely on your computer. Drop in a spreadsheet and get charts, statistics, and a shareable dashboard — no internet connection required, no sign-up, no data ever leaving your machine.

Built for people who work with data regularly and want answers fast, without opening a browser tab, logging into a service, or waiting for a cloud query to finish.

---

## Current Features

|                            |                                                                                                                               |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **📂 CSV & Excel support** | Upload `.csv` or `.xlsx` files up to **400 MB**                                                                               |
| **📊 10 chart types**      | Bar, pie/donut, scatter, histogram, time series, correlation heatmap, matrix/pivot, geographic map, outlier, and data quality |
| **🔍 Auto insights**       | Automated plain-language observations generated for every chart                                                               |
| **🗂️ Dashboard builder**  | Arrange charts in a portrait or landscape grid, add KPI summary cards, set a title, and save                                  |
| **📤 Export**              | Download as a self-contained HTML file (no server dependency) — then use your browser's DevTools to save as PNG               |
| **🧹 Data tools**          | Column rename, type cast, outlier flagging, and missing-value handling before analysis                                        |
| **💾 Session backup & restore** | Save local session backups and restore any compatible JSON backup file, including backups shared by other users           |
| **💾 Session saving**      | Analyses and dashboards persist locally — pick up exactly where you left off after a restart                                  |
| **🔒 Fully offline**       | No telemetry, no analytics, no outbound network requests                                                                      |


## Upcoming Features

| Feature | Description |
|---------|-------------|
| **🖼️ Full-page PNG Export** | Dedicated Chrome extension for capturing the exported dashboard HTML as a full-page PNG image. |
| **☀️ Complete Light Mode** | A fully polished light theme with consistent styling across every page, component, chart, and dialog. |


---

## System requirements

* **OS:** Linux (Ubuntu 20.04 LTS or later; any modern Debian-based or RPM-based distro)
* **Architecture:** amd64 (64-bit)
* **Python:** 3.11 or later is required to build from source. Packaged installs use an isolated virtual environment and the system Python on the target Linux machine.
* **Browser:** Any installed browser — Chrome, Chromium, Firefox, Brave, or Edge — to view the app and export PNGs
* **Disk:** ~400 MB installed (includes a self-contained Python virtual environment)
* **RAM:** 2 GB minimum; 4 GB or more recommended for files over 100 MB

---

## Install

### Option 1 — Debian / Ubuntu (.deb) *(recommended)*

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

No manual Python setup, no `pip install`, no virtual environment to activate.

### Option 2 — Fedora / RHEL / openSUSE (.rpm)

```bash
sudo dnf install lytrize-1.0-1.x86_64.rpm
# or on older systems:
sudo rpm -i lytrize-1.0-1.x86_64.rpm
```

### Option 3 — Build from source

See [CONTRIBUTING.md](./CONTRIBUTING.md#quick-start-for-developers) for the full developer setup.

---

## How to use Lytrize

**1. Open the app**
Launch Lytrize from your application menu or run `lytrize` in a terminal. A launcher window appears while the Streamlit backend starts, then your browser opens automatically.

**2. Upload a file**
Click **Start New Analysis** on the home screen and choose a CSV or Excel file. Lytrize shows a data preview and lets you rename columns, fix data types, and flag outliers before proceeding.

**3. Run an analysis**
On the Analysis page, click any chart-type card — bar chart, time series, scatter plot, correlation heatmap, and so on — configure the columns and options, then click **Generate**. Charts appear immediately with auto-generated insights.

**4. Build a dashboard**
Generated charts collect in your session. Click **Proceed to Dashboard** to arrange them, add KPI summary cards, set a title, and choose a portrait (2-column) or landscape (3-column) layout.

**5. Save, back up, and export**
Your session saves automatically as you work. Use **Save Session** to lock in a named checkpoint visible on the home screen. Use **Restore Backup** to import any compatible JSON backup file from another user or from your own archive. Use **Download HTML** to download a standalone file you can open in any browser or share with a colleague. The downloaded HTML page can be saved as PNG using your browser's DevTools screenshot feature.

---

## Where is my data stored?

Everything lives on your machine:

| What                          | Where                                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Sessions, charts, KPIs        | `~/.local/share/lytrize/lytrize.db` (SQLite)                                                                  |
| Active DataFrame (in-session) | `$XDG_RUNTIME_DIR/lytrize/df_<id>.parquet` (RAM-backed tmpfs if available; falls back to `~/.cache/lytrize/`) |
| Launcher preferences          | `~/.local/share/lytrize/launcher_prefs.json`                                                                  |
| Backend log                   | Streamlit writes to stderr by default; check terminal output or redirect to a file                            |

The parquet snapshot is used to restore your loaded dataset after a browser tab refresh. It is not persisted across reboots if stored on tmpfs — if the app restarts after a reboot and your file is gone, you will be prompted to re-upload.

---

## Uninstall

```bash
sudo dpkg -r lytrize          # Debian / Ubuntu
sudo dnf remove lytrize       # Fedora / RHEL
```

User data at `~/.local/share/lytrize/` is not removed by the package uninstaller. Delete it manually if you want a complete clean:

```bash
rm -rf ~/.local/share/lytrize
```

---

## Troubleshooting

**The app does not start**
Run `lytrize` from a terminal to see live output. Check the terminal for Python tracebacks.

**Missing dependencies after install**
Run `sudo apt-get install -f` (Debian/Ubuntu) or `sudo dnf install -f` (Fedora/RHEL) then try again.

**Downloading as PNG / image**
The app exports a standalone HTML file. To save that page as a PNG, use your browser's built-in screenshot tools:

* **Chrome/Edge/Opera/Brave:** Open DevTools (`Ctrl+Shift+I`), then `Ctrl+Shift+P`, type "screenshot", choose **Capture full size screenshot**
* **Firefox/LibreWolf:** `Ctrl+Shift+S` (or right-click → *Take Screenshot*)

**The browser does not open automatically**
If no supported browser is detected, copy `http://127.0.0.1:8501` into any browser while the launcher window shows "Running".

**Something looks broken**
Check the terminal output for Python tracebacks. If the issue is reproducible, open an issue and attach the log.

---

## Contributing

Lytrize is open source. Bug reports, feature requests, and pull requests are welcome.

Before opening a PR, please read [CONTRIBUTING.md](./CONTRIBUTING.md) for the architecture, development setup, and contribution guidelines.