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

### Screenshots

![Upload page](https://via.placeholder.com/800x450/1e293b/a78bfa?text=Upload+Page)
![Analysis page](https://via.placeholder.com/800x450/1e293b/a78bfa?text=Analysis+Page)
![Dashboard](https://via.placeholder.com/800x450/1e293b/a78bfa?text=Dashboard)
![Dashboard](https://via.placeholder.com/800x450/1e293b/a78bfa?text=Chart+Settings)

*Replace these placeholder images with your own screenshots.*

---

### Highlights

- **Saved session backups** — make local backup files of your analyses and dashboards.
- **Restore from JSON backups** — import any backup file, even ones shared by other users.
- **Local-first** — no cloud, no account, your data never leaves your device.

---

## What is Lytrize?

Lytrize is a desktop analytics app that runs entirely on your computer. Drop in a spreadsheet and get charts, statistics, and a shareable dashboard. No internet connection needed, no sign-up, no data ever leaving your machine.

Built for people who work with data often and want answers fast — without opening a browser tab, logging into a service, or waiting for a cloud query to finish.

---

## Features

|                            |                                                                                                                               |
| -------------------------- | ----------------------------------------------------------------------------------------------------------------------------- |
| **📂 CSV & Excel support** | Upload `.csv` or `.xlsx` files up to **400 MB**                                                                               |
| **📊 10 chart types**      | Bar, pie/donut, scatter, histogram, time series, correlation heatmap, matrix/pivot, geographic map, outlier, and data quality |
| **🔍 Auto insights**       | Plain-English observations generated for every chart automatically                                                            |
| **🗂️ Dashboard builder**  | Arrange charts in a portrait or landscape grid, add KPI summary cards, set a title, and save                                  |
| **📤 Export**              | Download as a self-contained HTML file — then use your browser's DevTools to save as PNG                                      |
| **🧹 Data tools**          | Rename columns, change data types, flag outliers, and handle missing values before analysis                                   |
| **💾 Session backup & restore** | Save local session backups and restore any compatible JSON backup, including ones shared by other users                   |
| **💾 Session saving**      | Analyses and dashboards save automatically — pick up where you left off after a restart                                       |
| **🔒 Fully offline**       | No telemetry, no analytics, no outbound network requests                                                                      |


## Upcoming Features

| Feature | Description |
|---------|-------------|
| **🖼️ Full-page PNG Export** | Dedicated Chrome extension for capturing the exported dashboard HTML as a full-page PNG image. |
| **☀️ Complete Light Mode** | A fully polished light theme with consistent styling across every page, component, chart, and dialog. |


---

## System Requirements

* **OS:** Linux (Ubuntu 20.04 LTS or later; any modern Debian-based or RPM-based distro)
* **Architecture:** amd64 (64-bit)
* **Python:** 3.11 or later required to build from source. Packaged installs use an isolated virtual environment with the system Python.
* **Browser:** Any installed browser — Chrome, Chromium, Firefox, Brave, or Edge
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

## How to Use Lytrize

**1. Open the app**
Launch Lytrize from your application menu or run `lytrize` in a terminal. A launcher window appears while the Streamlit backend starts, then your browser opens automatically.

**2. Upload a file**
Click **Start New Analysis** on the home screen and choose a CSV or Excel file. Lytrize shows a preview and lets you rename columns, fix data types, and flag outliers before proceeding.

**3. Run an analysis**
On the Analysis page, click any chart-type card — bar chart, time series, scatter plot, correlation heatmap, and so on. Choose your columns and options, then click **Generate**. Charts appear right away with auto-generated insights.

**4. Build a dashboard**
Charts you generate collect in your session. Click **Proceed to Dashboard** to arrange them, add KPI summary cards, set a title, and pick a portrait (2-column) or landscape (3-column) layout.

**5. Save, back up, and export**
Your session saves automatically as you work. Use **Save Session** to make a named checkpoint you can see on the home screen. Use **Restore Backup** to import any compatible JSON backup from another user or from your own archive. Use **Download HTML** to get a standalone file you can open in any browser or share with someone else. Save the HTML page as PNG using your browser's DevTools screenshot tool.

---

## Where is My Data Stored?

Everything lives on your machine:

| What                          | Where                                                                                                         |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------- |
| Sessions, charts, KPIs        | `~/.local/share/lytrize/lytrize.db` (SQLite)                                                                  |
| Active DataFrame (in-session) | `$XDG_RUNTIME_DIR/lytrize/df_<id>.parquet` (RAM-backed tmpfs if available; falls back to `~/.cache/lytrize/`) |
| Launcher preferences          | `~/.local/share/lytrize/launcher_prefs.json`                                                                  |
| Backend log                   | Streamlit writes to stderr by default; check terminal output or redirect to a file                            |

The parquet snapshot is used to restore your loaded dataset after a browser tab refresh. It is not kept across reboots if stored on tmpfs — if the app restarts after a reboot and your file is gone, you will be asked to re-upload.

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
Check the terminal output for Python tracebacks. If the issue happens again, open an issue and attach the log.

---

## Contributing

Lytrize is open source. Bug reports, feature requests, and pull requests are welcome.

Before opening a PR, please read [CONTRIBUTING.md](./CONTRIBUTING.md) for the development setup and guidelines.

---

## License

MIT — see [LICENSE](./LICENSE) for the full text.