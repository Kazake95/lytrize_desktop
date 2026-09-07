# Contributors

Thanks to everyone who has contributed to Lytrize! This file acknowledges the people and contributions that have helped shape the project.

---

## Core Team

### Kazake95 — Creator & Lead Developer

- Designed and built the entire application architecture
- Streamlit backend with 11 chart types and dashboard builder
- PySide6 desktop launcher with browser isolation and crash recovery
- SQLite database layer with session management and auto-save
- Cross-platform packaging (.deb, .rpm, Windows .exe via Inno Setup 7)
- Offline font bundling and HTML export system
- Auto-update on re-upload with transform log preservation

---

## How to Contribute

Lytrize is open source and welcomes contributions from everyone. Here is how you can help:

### Reporting Bugs

1. Check if the issue already exists in the [issue tracker](https://github.com/Kazake95/lytrize_desktop/issues).
2. If not, open a new issue with:
   - A clear description of the problem
   - Steps to reproduce
   - Your operating system (Linux distribution or Windows version)
   - The Lytrize version (check `backend/config.py` or the About section in the app)
   - Relevant log output (backend log at `~/.local/share/lytrize/streamlit.log` on Linux, `%APPDATA%\Lytrize\streamlit.log` on Windows)

### Suggesting Features

1. Open an issue describing the feature you would like to see.
2. Explain the use case and why it would be valuable.
3. If you have ideas for implementation, include them in the description.

### Code Contributions

1. **Fork** the repository on GitHub.
2. **Clone** your fork locally:
   ```bash
   git clone https://github.com/YOUR_USERNAME/lytrize_desktop.git
   cd lytrize_desktop
   ```
3. **Set up your development environment** — see [CONTRIBUTOR.md](./CONTRIBUTOR.md#development-setup) for full instructions.
4. **Create a branch** for your changes:
   ```bash
   git checkout -b feature/my-feature
   ```
5. **Make your changes** following the code style and conventions in [CONTRIBUTOR.md](./CONTRIBUTOR.md#code-style).
6. **Test** your changes on your platform:
   ```bash
   streamlit run backend/app.py
   ```
7. **Commit** with a clear, descriptive message:
   ```bash
   git commit -m "Add feature: description of changes"
   ```
8. **Push** to your fork:
   ```bash
   git push origin feature/my-feature
   ```
9. **Open a Pull Request** against the `main` branch.

### Documentation

Improvements to documentation are always welcome:

- Fix typos or unclear instructions in README.md or CONTRIBUTOR.md
- Add examples or screenshots
- Translate documentation to other languages
- Improve code comments and docstrings

### Testing

- Test bug fixes and new features on your platform
- Report any regressions you find
- If possible, test on both Linux and Windows

---

## Contribution Guidelines

- Keep PRs focused — one change per PR
- Follow the existing code style and naming conventions
- Update documentation if your change affects user-facing behavior
- Ensure the app runs: `streamlit run backend/app.py`
- Mention testing steps in your PR description
- Be respectful and constructive in all interactions

---

## Development Platforms

Lytrize is developed and tested on:

- **Linux:** Ubuntu 20.04+, Fedora, Debian-based distributions
- **Windows:** Windows 10/11 (64-bit)

Contributions that improve compatibility with other platforms (e.g., macOS) are welcome, though the primary focus is Linux and Windows.

---

## Development Setup

### Prerequisites

- **Python 3.11+**
- **pip** (usually bundled with Python)
- **Git**
- **Inno Setup 7** (Windows builds only — download from https://jrsoftware.org/isdl.php)

### Running Locally

```bash
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop
python -m venv venv
source venv/bin/activate          # Linux/macOS
# or: venv\Scripts\activate       # Windows
pip install -r requirements.txt
streamlit run backend/app.py
```

### Shared Configuration

| Constant | Value |
|---|---|
| `APP_NAME` | `"Lytrize"` |
| `APP_VERSION` | `"1.2"` |
| `APP_HOST` | `"127.0.0.1"` |
| `APP_PORT` | `8501` |

## Codebase Manual

This section is the developer's map of the codebase — what lives where, how
data flows, and how the pieces fit together.

### Project Structure

```
lytrize_desktop/
├── backend/
│   ├── app.py                  # Streamlit entry point (page router)
│   ├── config.py               # APP_NAME / APP_VERSION / host & port constants
│   ├── assets/                 # Logo, screenshots, bundled fonts
│   ├── tests/                  # Pytest suite (run: pytest backend/tests)
│   └── modules/
│       ├── __init__.py         # Analysis registry (ANALYSIS_OPTIONS, _RUNNERS,
│       │                       #   _WIDGET_SPEC, config panel & kwargs collectors)
│       ├── charts.py           # Shared chart helpers: layout, palettes, hover
│       │                       #   formatting, column-type caches (num/cat/dt)
│       ├── database.py         # SQLite layer: sessions, drafts, backups
│       ├── export.py           # Standalone HTML report generation
│       ├── pages/              # One module per app page (Streamlit)
│       │   ├── home.py         #   Home: sessions, backup/restore
│       │   ├── upload.py       #   Upload: file ingest, dtype optimizer,
│       │   │                   #     column classifier, Geo Standardiser
│       │   ├── analysis.py     #   Analysis: chart cards, regenerate panel
│       │   ├── dashboard.py    #   Dashboard: grid layout, KPIs, HTML export
│       │   └── auth.py         #   Local session/auth handling
│       ├── analysis/           # One runner per chart type (pure logic)
│       │   ├── descriptive.py, statistical.py, distribution.py,
│       │   ├── correlation.py, categorical.py, pie_chart.py,
│       │   ├── time_series.py, scatter_plot.py, matrix_table.py,
│       │   ├── outlier.py, data_quality.py
│       │   └── map_plot.py     #   Scatter + choropleth maps, geo resolution
│       ├── ui/                 # Reusable Streamlit widgets/panels
│       │   ├── chart_card.py       # Chart container + display cache
│       │   ├── chart_settings.py   # Layout/Typography/Colorbar controls +
│       │   │                       #   display-option -> figure applier
│       │   ├── column_tools.py     # Data-type transformer + Geo Standardiser
│       │   ├── column_manager.py   # Add/rename/remove columns
│       │   ├── data_cleaner.py     # Missing values / outlier rows
│       │   └── excel_loader.py, css.py, font_manager.py
│       └── utils/
│           ├── session_cache.py    # Active DataFrame snapshot (parquet)
│           ├── perf.py             # Chunked CSV reader, dtype optimizer
│           ├── transform_log.py    # Replayable column transforms
│           └── regenerate.py       # Re-runs saved chart/KPI recipes
├── desktop/
│   ├── gui.py                  # PySide6 launcher GUI (tray, browser picker)
│   └── launcher.py             # Backend process management, browser isolation
├── packaging/
│   ├── deb/                    # Debian package skeleton + build script
│   ├── rpm/                    # RPM package skeleton + build script
│   └── windows/                # Inno Setup script (lytrize.iss)
├── service/lytrize.service     # systemd user service (optional)
├── build.sh / build_rpm.sh     # Linux package build entry points
└── build_windows.ps1           # Windows installer build entry point
```

### Architecture & Data Flow

```
Launcher (PySide6, desktop/)
  └─ spawns Streamlit backend (backend/app.py) on 127.0.0.1:8501
       └─ opens the user's browser in an isolated profile

Upload page ──file──► dtype optimizer + column classifier + Geo Standardiser
     │                     (utils/perf.py, ui/column_tools.py)
     ▼
Session state ──► parquet snapshot (utils/session_cache.py) + SQLite draft
     ▼
Analysis page ──► config panel (modules/analysis/__init__.py)
     │             _WIDGET_SPEC + _collect_kwargs → runner kwargs
     ▼
Chart runner (modules/analysis/<type>.py) ──► plotly Figure
     ▼
chart_card.py ──► apply_chart_display_options (ui/chart_settings.py)
     │             layout / typography / colorbar / colorscale per chart
     ▼
Dashboard page ──► KPIs + grid ──► export.py ──► standalone HTML
```

Key ideas:

- **Runners are pure functions.** Each chart runner in `modules/analysis/`
  takes a DataFrame plus scalar kwargs and returns `[(title, figure), ...]`.
  No `st.*` calls, no session access inside runners.
- **Generation kwargs are snapshotted.** Every chart stores its exact
  `_generation_kwargs` in `chart_meta_<uid>` so the Edit-chart panel and the
  auto-update regeneration (`utils/regenerate.py`) can re-run it against
  fresh data later.
- **Display options are a separate layer.** Colour, colorbar, typography and
  legend tweaks live in `meta["display_options"]` / `meta["text_style"]` and
  are applied by `apply_chart_display_options()` *after* generation — they
  never change the underlying data.

### Key Subsystems

| Subsystem | Where | What it does |
|---|---|---|
| Column classification | `ui/column_tools.py` (classifier) + `charts.py` (`num_cols`/`cat_cols`/`dt_cols`) | Users confirm numeric/categorical/datetime columns; dropdown lists across the app read these caches |
| Dtype optimizer | `utils/perf.py` (`optimize_dtypes`) | Downcasts numerics; converts low-cardinality text to `category`. **Any code filtering "text columns" must accept object, string AND category dtypes** |
| Session persistence | `utils/session_cache.py` | Saves the active DataFrame as a parquet snapshot so a browser refresh does not lose the upload |
| Transform log & auto-update | `utils/transform_log.py`, `utils/regenerate.py` | Column renames / calculated columns are recorded and replayed on re-upload; every saved chart recipe is re-run against the new data |
| Chart settings | `ui/chart_settings.py` | Declarative capability map (`CHART_TYPE_SETTINGS`, `_CONTROL_META`) drives which controls each chart type gets; `apply_chart_display_options()` applies them to figures |
| Geo name resolution | `analysis/map_plot.py` | `_build_country_map` (pycountry + aliases), `_build_us_state_map`, `_build_world_regions_map` (European/Indian/etc. states), `_CITY_COORDS`; `resolve_geo_names()` picks the best match, `detect_geo_column()` auto-selects the location column |
| Database | `modules/database.py` | SQLite: saved sessions, drafts, KPIs, chart metadata; user-scoped rows |

### Adding a New Chart Type

1. **Write the runner** — `backend/modules/analysis/<your_chart>.py`:
   `def run_<chart>(df, ..., **kwargs) -> list[tuple[str, Figure]]`.
   Pure logic only — no `st.*` calls, no session access. Tag the figure with
   `fig._lytrize_meta = {...}` (see `map_plot.py` for the fields).
2. **Register it** in `backend/modules/analysis/__init__.py`:
   - Add an entry to `ANALYSIS_OPTIONS` (id, icon, name, description).
   - Map the id to your runner in `_RUNNERS`.
   - Add its widget keys to `_WIDGET_SPEC[<id>]` (Edit-chart state capture).
   - Add a config branch in `_render_config_panel_body()` and kwargs in
     `_collect_kwargs()`. **Every dropdown key must appear in `_WIDGET_SPEC`**,
     otherwise its selection will not survive the Edit chart panel.
3. **Declare capabilities** in `CHART_TYPE_SETTINGS`
   (`backend/modules/ui/chart_settings.py`): `has_axes`, `has_legend`,
   `controls`, `typography` — this drives which chart-settings controls render.
4. **Persist compatibility** (optional) — add old→new key mappings to
   `_compat_map` in `_restore_regen_ws` (`modules/pages/analysis.py`) if charts
   saved by older versions must keep regenerating.
5. **Test** — add `backend/tests/test_<chart>.py`, run the suite, and make
   sure it passes before opening a PR.

### Testing

```bash
# from the repository root
pytest backend/tests -v
```

- The suite currently covers Map Plot encoding, value/size behaviour,
  choropleth chart settings and hover extras (50 tests).
- `backend/tests/conftest.py` puts `backend/` on `sys.path`, so tests import
  `modules.*` directly and can run from the repo root.
- Runners are tested as pure functions; Streamlit widgets are not executed in
  tests. When a test needs the tile basemap path it monkeypatches
  `map_plot._tiles_online` — keep network access out of tests.

## Building Packages

### .deb (Debian/Ubuntu)

```bash
bash packaging/deb/build_deb.sh
# Output: build/lytrize_1.2_amd64.deb
```

### .rpm (Fedora/RHEL/openSUSE)

```bash
bash packaging/rpm/build_rpm.sh
# Output: build/lytrize-1.2-1.x86_64.rpm
```

### Windows .exe Installer

```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
# Output: build\LytrizeSetup_1.2.exe
```

Requires Python 3.11+ and Inno Setup 7. The script stages the app, slims the venv, and compiles the installer via ISCC.

## Code Style

- **Python 3.11+**
- **Docstrings:** Google-style (`Args`, `Returns`, `Raises`)
- **Naming:** `snake_case` functions/variables, `PascalCase` classes, `UPPER_SNAKE` constants
- **Imports:** stdlib → third-party → local (each group alphabetized)
- **Line length:** ~100 chars max
- **Type hints:** preferred on public functions

## License

By contributing to Lytrize, you agree that your contributions will be licensed under the MIT License. See [LICENSE](./LICENSE) for the full text.
