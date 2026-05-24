<div align="center">

# Lytrize Desktop

**Local-first data analytics for Linux — no cloud, no account, no setup.**

Upload a CSV or Excel file and get interactive charts, dashboards, and insights in seconds. Everything stays on your device.

[![Platform](https://img.shields.io/badge/platform-Linux%20(amd64)-blue?style=flat-square)](https://github.com)
[![Python](https://img.shields.io/badge/python-3.11%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://python.org)
[![License](https://img.shields.io/badge/license-see%20LICENSE-lightgrey?style=flat-square)](./LICENSE)

</div>

---

## What is Lytrize?

Lytrize is a desktop analytics app that runs entirely on your computer. You drag in a spreadsheet, and it gives you charts, statistics, and a shareable dashboard — no internet connection required, no sign-up, no data ever leaving your machine.

It is built for people who work with data regularly and want answers fast, without opening a browser, logging into a service, or waiting for a cloud query to run.

---

## Features

| | |
|---|---|
| **📂 CSV & Excel support** | Upload `.csv`, `.xlsx`, or `.xls` files up to 500 MB |
| **📊 10+ chart types** | Bar, pie/donut, scatter, histogram, box plot, time series, correlation matrix, heatmap, and geographic map |
| **🔍 Auto insights** | Automated plain-language observations generated for each chart |
| **🗂️ Dashboard builder** | Arrange charts into a dashboard, add KPI cards, pick a layout, and save it |
| **📤 Export** | Download your dashboard as a self-contained HTML file or render it to PNG using your installed browser |
| **🧹 Data tools** | Column renaming, type casting, outlier flagging, and missing-value handling before analysis |
| **💾 Session saving** | Analyses and dashboards are saved locally so you can pick up exactly where you left off |
| **🔒 Fully offline** | No telemetry, no analytics, no network requests — confirmed by Streamlit's `gatherUsageStats = false` |

---

## System requirements

- **OS:** Any modern Debian/Fedora based distro
- **Architecture:** amd64 (64-bit) only
- **Python:** 3.11 or later (checked at install time)
- **Browser:** Any installed browser — Chrome, Chromium, Firefox, Brave, or Edge — to view the app and export PNGs
- **Disk:** ~400 MB for the installed package (includes a self-contained Python environment)
- **RAM:** 2 GB minimum; 4 GB or more recommended for large files

 - **Python packages:** See `requirements.txt` for the exact Python runtime dependencies. `PySide6` is required for the desktop launcher/GUI, and `pycountry` is an optional dependency used for geographic name matching in map visualisations.

---

## Install

### Option 1 — Download a prebuilt package (recommended)

Prebuilt packages for Debian (`.deb`) and RPM-based distros (`.rpm`) are provided on the [Releases page](https://github.com/lytrize/lytrize-desktop/releases). Download the package that matches your distribution.

- Install a Debian package:

```bash
sudo dpkg -i lytrize.deb
sudo apt -f install   # fix missing dependencies if prompted
```

- Install an RPM package (Fedora / RHEL / CentOS):

```bash
sudo rpm -Uvh lytrize.rpm
sudo dnf install ./lytrize.rpm
```

After installation launch from your application menu or run:

```bash
lytrize
```

Both package formats are built by the repository and may be uploaded as release assets. If you plan to distribute both formats, upload them to a single GitHub Release so users on either family of distributions can download the right artifact.

### Option 2 — Build from source

See [CONTRIBUTING.md](./CONTRIBUTING.md#quick-start-for-developers) for the full developer setup.

---

## How to use Lytrize

**1. Open the app**
Launch Lytrize from your application menu or by running `lytrize` in a terminal. A launcher window appears while the app starts, then your browser opens automatically.

**2. Upload a file**
Click **Upload** on the home screen and choose a CSV or Excel file. Lytrize shows a preview and lets you rename columns, fix data types, and flag outliers before proceeding.

**3. Run an analysis**
Go to the **Analysis** page. Click any chart type card — bar chart, time series, scatter plot, and so on — configure the columns, and click **Generate**. The chart appears instantly with auto-generated insights below it.

**4. Build a dashboard**
Charts you generate are added to your session. Switch to the **Dashboard** page to arrange them, add KPI summary cards, set a title, and choose a layout.

**5. Save and export**
Your session saves automatically. Use **Export HTML** to download a standalone file you can open in any browser or share with a colleague. Use **Render PNG** (upload the HTML back) to get a flat image.

---

## Uninstall

```bash
# For debian
sudo apt purge lytrize 
# For fedora
sudo dnf remove lytrize

```

Your saved sessions and preferences are kept at `~/.local/share/lytrize/` by default. The uninstaller will ask if you want to remove them.

---

## Frequently asked questions

**Does Lytrize need an internet connection?**
No. After installation everything runs locally. The only time a network is used is if you install from the internet — the app itself makes no outbound connections.

**What file formats are supported?**
`.csv`, `.xlsx`, and `.xls`. Column types are detected automatically. You can correct any misdetections on the upload screen before analysing.

**Where is my data stored?**
All data, saved sessions, and dashboards are stored in `~/.local/share/lytrize/lytrize.db` — a standard SQLite database file on your own machine.

**Can I run Lytrize without a desktop environment?**
The launcher window requires a display. If you only want the Streamlit backend (no GUI), see the [developer docs](./CONTRIBUTING.md#running-without-the-desktop-launcher).

**Something looks broken. What do I do?**
Run `lytrize` from a terminal to see log output. If the issue is reproducible, please [open an issue](https://github.com/lytrize/lytrize-desktop/issues) and include the terminal output.

---

## Contributing

Lytrize is open source. Bug reports, feature requests, and pull requests are welcome.

Before opening a PR, please read [CONTRIBUTING.md](./CONTRIBUTING.md) for the project architecture, development setup, and contribution guidelines.

---

## License

See [LICENSE](./LICENSE).
