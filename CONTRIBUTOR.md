# Lytrize Desktop — Developer Manual & Encyclopedia

> **A complete reference for understanding, modifying, and extending the Lytrize Desktop application.**

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Technology Stack](#2-technology-stack)
3. [Architecture Overview](#3-architecture-overview)
4. [Directory Structure](#4-directory-structure)
5. [Module Encyclopedia](#5-module-encyclopedia)
6. [Session State Reference](#6-session-state-reference)
7. [Chart System Architecture](#7-chart-system-architecture)
8. [Desktop Launcher Architecture](#8-desktop-launcher-architecture)
9. [Database Layer](#9-database-layer)
10. [Fragment Isolation Pattern](#10-fragment-isolation-pattern)
11. [Data Flow Lifecycle](#11-data-flow-lifecycle)
12. [Typography & Theming System](#12-typography--theming-system)
13. [Performance Optimization](#13-performance-optimization)
14. [Build & Packaging](#14-build--packaging)
15. [Development Setup](#15-development-setup)
16. [How-To Guides](#16-how-to-guides)
17. [Code Style & Conventions](#17-code-style--conventions)
18. [Testing](#18-testing)
19. [Git Workflow & PR Guidelines](#19-git-workflow--pr-guidelines)
20. [Troubleshooting](#20-troubleshooting)
21. [FAQ](#21-faq)

---

## 1. Project Overview

**Lytrize Desktop** is a local-first, offline data analytics application for Linux and Windows. It lets users upload CSV or Excel files and instantly generate interactive charts and dashboards — everything stays on the device.

### Design Philosophy

- **No cloud, no account, no telemetry** — the app makes zero network requests
- **Single local user** — identified by OS username (`getpass.getuser()`)
- **Two-process architecture** — a PySide6 launcher window manages the Streamlit backend subprocess
- **Browser-isolated UI** — the Streamlit web app opens in a dedicated browser window (Chromium `--app=` mode or Firefox `--kiosk`)
- **Power BI-class responsiveness** — `@st.fragment` isolation means adjusting one chart doesn't rerun the entire page

### Key Capabilities

| Feature | Description |
|---|---|
| 11 chart types | Bar, pie/donut, scatter, histogram, time series, correlation, pivot table, matrix heatmap, geographic map, outlier, data quality |
| Dashboard builder | Portrait (2-col) or landscape (3-col) grid with KPI cards |
| HTML export | Self-contained file with inline Plotly.js |
| Auto-update on re-upload | Re-upload a dataset → all charts & KPIs regenerate automatically |
| Session backup/restore | JSON backup files, shareable across machines |
| Data tools | Rename, dtype convert, calculated columns, outlier detection, missing value handling |
| Large file support | Up to 400 MB via chunked CSV reading, dtype optimization, and smart sampling |

---

## 2. Technology Stack

### Core Dependencies (from `requirements.txt`)

| Package | Version | Purpose |
|---|---|---|
| `streamlit` | >=1.47.0, <2.0.0 | Web UI framework (bundles Plotly.js 2.35.0 for map/scattermap support) |
| `plotly` | >=5.24.1, <6.0.0 | Interactive charting library |
| `pandas` | >=2.2.0, <3.0.0 | Data manipulation |
| `pyarrow` | >=18.0.0 | Parquet read/write for DataFrame snapshots |
| `openpyxl` | >=3.1.0, <4.0.0 | Excel file reading |
| `scipy` | >=1.12.0, <2.0.0 | Statistical functions |
| `statsmodels` | >=0.14.0, <0.15.0 | Statistical models |
| `pycountry` | >=23.12.11, <25.0.0 | Country name resolution for maps |
| `PySide6` | >=6.11.0, <7.0.0 | Qt for Python — desktop launcher GUI |


---

## 3. Architecture Overview

```
+-----------------------------------------------------------------+
|                        Lytrize Desktop                          |
|                                                                 |
|  +----------------------+       +----------------------------+  |
|  |   desktop/gui.py     |       |     backend/app.py         |  |
|  |   (PySide6 Launcher) |       |     (Streamlit Backend)    |  |
|  |                      |       |                            |  |
|  |  - Browser detection | spawn |  - Page routing            |  |
|  |  - Subprocess mgmt   |------>|  - Session management      |  |
|  |  - Crash recovery    |       |  - Chart generation        |  |
|  |  - System tray       |       |  - Database operations     |  |
|  |  - QThread workers   |       |  - Export engine           |  |
|  +----------------------+       +----------------------------+  |
|           |                                  |                   |
|           | browser                          | SQLite            |
|           v                                  v                   |
|  +----------------------+       +----------------------------+  |
|  |  Isolated Browser    |       |    lytrize.db (SQLite)     |  |
|  |  Window              |       |    + parquet snapshots     |  |
|  +----------------------+       +----------------------------+  |
+-----------------------------------------------------------------+
```

### Process Lifecycle

1. User launches `desktop/gui.py` (or `desktop/launcher.py` on Linux)
2. Launcher detects installed browsers and shows the launcher window
3. On "Start", launcher spawns `streamlit run backend/app.py` as a subprocess
4. `_WaitThread` polls `127.0.0.1:8501` until Streamlit accepts connections
5. Launcher opens the selected browser in isolated mode pointing to the URL
6. `_WatchThread` monitors the subprocess for unexpected exits (crash recovery)


---

## 4. Directory Structure

```
lytrize_desktop/
|-- backend/                        # Streamlit application (the "backend")
|   |-- app.py                      # Entry point: page routing, session init, draft restore
|   |-- config.py                   # APP_NAME, APP_VERSION, APP_HOST, APP_PORT
|   |-- assets/                     # Static assets
|   |   |-- fonts/                  # Bundled TTF fonts (base64-embedded in HTML export)
|   |   |-- lytrize.ico             # App icon (Windows)
|   |   |-- lytrize.png             # App icon (Linux)
|   |   |-- screenshots/            # README screenshots
|   |   |-- styles.css              # Main stylesheet (with %%VARS_CSS%% and %%EXTRA%% placeholders)
|   |   +-- welcome-banner.png      # Home page banner image
|   |-- modules/                    # Core logic
|   |   |-- __init__.py             # Package marker
|   |   |-- analysis/               # Chart runners & config layer
|   |   |   |-- __init__.py         # ANALYSIS_OPTIONS, _RUNNERS, _WIDGET_SPEC, _collect_kwargs, _run
|   |   |   |-- apply_lytrize_standard.py  # Standard layout/color application
|   |   |   |-- categorical.py      # Bar charts (run_categorical)
|   |   |   |-- correlation.py      # Correlation heatmap (run_correlation)
|   |   |   |-- data_quality.py     # Missing values, duplicates (run_data_quality)
|   |   |   |-- descriptive.py      # Summary statistics table (run_descriptive)
|   |   |   |-- distribution.py     # Histograms & boxplots (run_distribution)
|   |   |   |-- map_plot.py         # Geographic scatter & choropleth (run_map_plot)
|   |   |   |-- matrix_table.py     # Heatmap & pivot table (run_matrix_heatmap, run_matrix_table)
|   |   |   |-- outlier.py          # IQR outlier detection (run_outlier)
|   |   |   |-- pie_chart.py        # Pie & donut charts (run_pie_chart)
|   |   |   |-- scatter_plot.py     # Scatter with trendlines (run_scatter_plot)
|   |   |   |-- statistical.py      # Mean/min/max/std bars (run_statistical)
|   |   |   +-- time_series.py      # Time series line charts (run_time_series)
|   |   |-- charts.py               # Shared chart utilities, palettes, hover formatting
|   |   |-- database.py             # All SQLite operations
|   |   |-- export.py               # HTML report generation engine
|   |   |-- pages/                  # Streamlit page renderers
|   |   |   |-- __init__.py
|   |   |   |-- analysis.py         # Analysis selection & chart generation page
|   |   |   |-- auth.py             # Backup & restore page (no real auth)
|   |   |   |-- dashboard.py        # Dashboard builder, KPI, save/export page
|   |   |   |-- home.py             # Home page with saved sessions list
|   |   |   +-- upload.py           # File upload & column classification page
|   |   |-- ui/                     # Reusable UI components
|   |   |   |-- __init__.py
|   |   |   |-- chart_card.py       # Per-chart card rendered in @st.fragment
|   |   |   |-- chart_settings.py   # Chart type capability map & display option adapters
|   |   |   |-- column_manager.py   # Add/remove/rename columns, calculated columns
|   |   |   |-- column_tools.py     # Dtype conversion & column classification
|   |   |   |-- css.py              # Global CSS injection, theme, logo, footer
|   |   |   |-- data_cleaner.py     # Text/numeric cleaning tools
|   |   |   |-- excel_loader.py     # Multi-sheet Excel browser & table joiner
|   |   |   +-- font_manager.py     # Font registry, @font-face injection, font selector
|   |   +-- utils/                  # Utility modules
|   |       |-- __init__.py


---

## 5. Module Encyclopedia

### 5.1 `backend/app.py` - Application Entry Point

**Purpose**: Streamlit entry point. Handles page routing, session initialization, and draft restoration.

| Function | Signature | Description |
|---|---|---|
| `_init_db_once()` | `-> None` | `@st.cache_resource` - calls `init_db()` exactly once per process |
| `_restore_draft(user_id)` | `(int) -> None` | Reloads an in-progress analysis from SQLite into `session_state` |
| `main()` | `-> None` | Sets page config, initializes DB, routes to the correct page function |

**Page routing logic** (in `main()`):
```python
if   p == "home":      page_home()
elif p == "upload":    page_upload()
elif p == "analysis":  page_analysis()
elif p == "dashboard": page_dashboard()
elif p == "profile":   page_profile()
```

**URL query params**:
- `?p=<page>` - current page (set on every render)
- `?sid=<session_id>` - when viewing a saved session
- `?nav=home` - forces navigation to home (clears view state)

---

### 5.2 `backend/config.py` - Application Constants

```python
APP_NAME    = "Lytrize"
APP_VERSION = "1.2"
APP_HOST    = "127.0.0.1"
APP_PORT    = 8501
```



---

### 5.4 `backend/modules/charts.py` - Shared Chart Utilities

**Purpose**: Common chart layout, palettes, hover formatting, and column type accessors.

| Function | Signature | Description |
|---|---|---|
| `chart_layout(height)` | `(int \| None) -> dict` | Returns Plotly layout kwargs used by every chart |
| `apply_hover_format(fig)` | `(Figure) -> None` | Applies K/M/B-formatted hover templates to all traces |
| `charts_to_json(charts)` | `(list) -> str` | Serializes chart list to JSON for DB storage |
| `num_cols()` | `-> list` | Returns confirmed numeric columns (cached by `_df_version`) |
| `cat_cols()` | `-> list` | Returns confirmed categorical columns |
| `dt_cols()` | `-> list` | Returns confirmed datetime columns |

**Color Palettes** (`PALETTES`):
- Default, Pastel, Warm, Cool, Monochrome (10 colors each)

---

### 5.5 `backend/modules/database.py` - SQLite Database Layer

**Purpose**: All database operations. Uses a context manager pattern with WAL mode.

**Connection Settings**:
- `PRAGMA journal_mode=WAL` - write-ahead logging for concurrent reads
- `PRAGMA synchronous=NORMAL` - balanced durability/performance
- `PRAGMA cache_size=-8000` - 8 MB cache
- `PRAGMA temp_store=MEMORY` - temp tables in memory
- `PRAGMA mmap_size=134217728` - 128 MB memory-mapped I/O

**Key Functions**: `init_db()`, `get_or_create_local_user()`, `save_session_db()`, `update_session_db()`, `get_user_sessions()`, `delete_session_db()`, `save_draft()`, `get_draft()`, `clear_draft()`, `export_sessions_to_dict()`, `import_sessions_from_dict()`, `log_activity()`

**Database Tables**: `users`, `sessions`, `drafts`, `activity_log`, `datasets`

---

### 5.6 `backend/modules/export.py` - HTML Export Engine

**Purpose**: Generates self-contained HTML files from dashboards.

| Function | Signature | Description |
|---|---|---|
| `generate_html_report(charts, kpis, title, theme, ...)` | `-> str` | Main export function - returns complete HTML string |
| `_apply_axes(fig, x_lbl, y_lbl, text_style)` | `-> Figure` | Applies axis labels and tick fonts |
| `_merge_theme(user_theme)` | `-> dict` | Merges user overrides into `DEFAULT_THEME` |

---

### 5.7 `backend/modules/pages/` - Page Renderers

| File | Purpose | Key Functions |
|---|---|---|
| `analysis.py` | Chart-type selection, config, generation | `page_analysis()`, `_render_config_and_actions()`, `_run()` |
| `upload.py` | File upload, column classification | `page_upload()`, `_render_column_manager()`, `_render_data_cleaner()` |
| `dashboard.py` | Grid layout, KPI, save/export | `page_dashboard()`, `_persist()`, `_calc_kpi()` |
| `home.py` | Welcome screen, session list | `page_home()` |
| `auth.py` | Backup/restore | `page_profile()` |

---

### 5.8 `backend/modules/ui/` - UI Components



---

## 6. Session State Reference

`st.session_state` is the global state dictionary. Here is a comprehensive catalog:

### User & Session Keys

| Key | Type | Description |
|---|---|---|
| `user_id` | `int` | Local user ID |
| `username` | `str` | OS username |
| `page` | `str` | Current page: home, upload, analysis, dashboard, profile |
| `theme` | `str` | dark or light |

### DataFrame Keys

| Key | Type | Description |
|---|---|---|
| `df` | `DataFrame` | The active dataset |
| `_df_version` | `int` | Incremented on every DataFrame change (cache invalidation) |
| `num_cols` | `list` | Confirmed numeric column names |
| `cat_cols` | `list` | Confirmed categorical column names |
| `dt_cols` | `list` | Confirmed datetime column names |
| `file_name` | `str` | Name of the uploaded file |

### Chart Keys

| Key | Type | Description |
|---|---|---|
| `charts` | `list[tuple]` | `[(uid, title, fig), ...]` - active chart list |
| `selected_analyses` | `list[str]` | Chart type ids selected for generation |
| `chart_type_{uid}` | `str` | Chart type for a specific chart |
| `chart_meta_{uid}` | `dict` | Metadata for a chart (includes `_generation_kwargs`) |
| `desc_{uid}` | `str` | Notes text for a specific chart |
| `_notes_shadow` | `dict` | `{uid: note_text}` - shadow copy for persistence |
| `_regen_uid` | `str` | UID of chart being edited |

### Dashboard Keys

| Key | Type | Description |
|---|---|---|
| `dashboard_title` | `str` | User-set title |
| `layout_mode` | `str` | portrait or landscape |
| `kpis` | `list[dict]` | KPI cards (each has `_recipe`) |
| `grid_order` | `list` | Chart UIDs in display order |
| `grid_fullwidth` | `dict` | `{uid: bool}` - full-width charts |
| `ex_{key}` | various | Export theme overrides |

---

## 7. Chart System Architecture

### How a Chart is Generated

1. User clicks chart-type card
2. `_render_config_and_actions()` renders config panel in fragment
3. User configures widgets (columns, palette, etc.)
4. User clicks "Generate"
5. `_collect_kwargs(aid, df, uid)` reads widget values from session_state
6. `_run(aid, df, **kwargs)` dispatches to `_RUNNERS[aid](df, **kwargs)`
7. Runner returns `[(title, fig), ...]`
8. `_run()` assigns UIDs, returns `[(uid, title, fig), ...]`
9. Charts appended to `session_state.charts`
10. `chart_meta_{uid}["_generation_kwargs"] = kwargs` (for regeneration)

### Chart Runner Contract



---

## 11. Data Flow Lifecycle

### Upload -> Analysis -> Dashboard -> Export

1. **Upload**: File is read, columns classified, DataFrame stored in `session_state.df`
2. **Analysis**: User selects chart type, configures widgets, clicks Generate -> `_run()` dispatches to runner
3. **Dashboard**: Charts arranged in grid, KPIs calculated, notes added
4. **Export**: `generate_html_report()` produces self-contained HTML with inline Plotly.js

### Re-upload & Auto-Update Flow

1. User re-uploads same dataset (with updates)
2. `replay_transform_log()` replays structural transforms
3. `validate_columns()` checks if referenced columns exist
4. `regenerate_charts()` re-runs each chart's `_generation_kwargs`
5. `regenerate_kpis()` recomputes each KPI's `_recipe`

---

## 12. Typography & Theming System

### Default Typography Settings

```python
default_text_style() = {
    "family": "Inter, system-ui, sans-serif",
    "header_size": 28,
    "header_color": "#6163df",
    "legend_title_size": 12,
    "legend_title_color": "#cbd5e1",
    "legend_item_size": 11,
    "legend_item_color": "#e2e8f0",
    "axis_title_size": 12,
    "axis_title_color": "#cbd5e1",
    "axis_tick_size": 10,
    "axis_tick_color": "#94a3b8",
}
```

---

## 13. Performance Optimization

### Render Limits

| Chart Type | Max Points |
|---|---|
| scatter | 8,000 |
| histogram | 50,000 |
| map | 10,000 |
| line | 50,000 |
| bar | 5,000 |
| heatmap | 500 |

### Caching Strategy

| Cache | Key | Invalidation |
|---|---|---|
| Column types | `_df_version` | DataFrame change |
| Describe stats | `(_df_version, tuple(cols))` | DataFrame/column change |
| Charts JSON | `compute_meta_hash(meta)` | Any meta key change |


---

## 16. How-To Guides

### How to Add a New Chart Type

1. **Create the runner file** - `backend/modules/analysis/my_chart.py`:
   ```python
   def run_my_chart(df, x_cols=None, y_cols=None, palette=None, **kwargs):
       charts = []
       # ... build figures ...
       charts.append(("My Chart", fig))
       return charts
   ```

2. **Register in `backend/modules/analysis/__init__.py`**:
   - Add to `ANALYSIS_OPTIONS` (id, icon, name, desc)
   - Add to `_RUNNERS` dict
   - Add widget keys to `_WIDGET_SPEC[<id>]`
   - Add config branch in `_render_config_panel_body()`
   - Add kwargs collection in `_collect_kwargs()`

3. **Declare capabilities** in `CHART_TYPE_SETTINGS` (`chart_settings.py`)

4. **Test** - create `backend/tests/test_my_chart.py`

### How to Add a New Page

1. Create `backend/modules/pages/my_page.py` with `page_my_page()` function
2. Import and register in `backend/app.py`
3. Add navigation button in `css.py:render_logo()` or home page

### How to Add a New Font

1. Add TTF file to `backend/assets/fonts/`
2. Register in `font_manager.py` `FONT_ENTRIES` list
3. Font will be automatically embedded via `inject_bundled_font_css()`

---

## 17. Code Style & Conventions

### Naming Conventions

| Element | Convention | Example |
|---|---|---|
| Functions | `snake_case` | `run_categorical`, `page_home` |
| Variables | `snake_case` | `user_id`, `chart_type` |
| Classes | `PascalCase` | `Launcher`, `_WaitThread` |
| Constants | `UPPER_SNAKE` | `APP_NAME`, `PALETTES` |
| Private functions | `_leading_underscore` | `_restore_draft`, `_connect` |

### Import Ordering


---

## 18. Testing

### Running Tests

```bash
pytest backend/tests -v
```

### Test Patterns

- **Runners are tested as pure functions** - Streamlit widgets are not executed
- **Network access is monkeypatched out** - `map_plot._tiles_online` is patched for tile tests
- **Test data is created inline** - small DataFrames constructed in each test

---

## 19. Git Workflow & PR Guidelines

### Branch Naming

| Prefix | Use Case |
|---|---|
| `feature/` | New features |
| `bugfix/` | Bug fixes |
| `refactor/` | Code refactoring |
| `docs/` | Documentation updates |

### PR Guidelines

1. **One change per PR** - keep PRs focused
2. **Follow code style** - naming, imports, docstrings
3. **Test your changes** - run `pytest backend/tests -v`
4. **Ensure the app runs** - `streamlit run backend/app.py`

---

## 20. Troubleshooting

### App Won't Start
- Run from terminal to see errors
- Check the log: `~/.local/share/lytrize/streamlit.log` (Linux) or `%APPDATA%\Lytrize\streamlit.log` (Windows)

### Port Already in Use
```bash
# Linux
lsof -i :8501
kill <PID>

# Windows
netstat -ano | findstr :8501
taskkill /PID <PID> /F
```

### Database Corruption
```bash
# Linux


---

## Appendix A: Key Session State Keys Quick Reference

```
user_id              -> int
username             -> str
page                 -> str
df                   -> DataFrame
_df_version          -> int
num_cols             -> list
cat_cols             -> list
dt_cols              -> list
file_name            -> str
charts               -> list[tuple]
selected_analyses    -> list[str]
chart_type_{uid}     -> str
chart_meta_{uid}     -> dict
desc_{uid}           -> str
_notes_shadow        -> dict
dashboard_title      -> str
layout_mode          -> str
kpis                 -> list[dict]
grid_order           -> list
grid_fullwidth       -> dict
transform_log        -> list[dict]
editing_session_id   -> int
view_session_id      -> int
theme                -> str
```

## Appendix B: Chart Type IDs

| ID | Name |
|---|---|
| `descriptive` | Descriptive |
| `statistical` | Statistical |
| `distribution` | Distribution |
| `correlation` | Correlation |
| `categorical` | Categorical Bar |
| `pie_chart` | Pie & Donut |
| `time_series` | Time Series |
| `scatter_plot` | Scatter Plot |
| `matrix_heatmap` | Matrix Heatmap |
| `matrix_table` | Pivot Table |
| `map_plot` | Map Plot |
| `data_quality` | Data Quality (upload page) |
| `outlier` | Outlier Detection (upload page) |

## Appendix C: File Modification Impact Matrix

| File | Modifying Affects |
|---|---|
| `backend/config.py` | Host/port for both backend and launcher |
| `backend/app.py` | Page routing, session init, draft restore |
| `backend/modules/analysis/__init__.py` | Chart registry, config panel, kwargs collection |
| `backend/modules/charts.py` | All chart layouts, hover formats, column type access |
| `backend/modules/database.py` | All persistence operations |
| `backend/modules/export.py` | HTML export output |
| `backend/modules/pages/analysis.py` | Analysis page behavior, chart generation flow |
| `backend/modules/pages/dashboard.py` | Dashboard layout, KPI calculation, save/export |
| `backend/modules/ui/chart_card.py` | Per-chart settings UI |
| `backend/modules/ui/chart_settings.py` | Which settings each chart type gets |
| `backend/modules/ui/css.py` | Global styling, theme, layout |
| `desktop/gui.py` | Launcher behavior, browser detection, crash recovery |
| `requirements.txt` | All dependency versions |

---

*This document is the definitive developer reference for the Lytrize Desktop codebase. For user-facing documentation, see [README.md](./README.md).*

*Last updated: 2026-09-07 for Lytrize v1.2*
rm ~/.local/share/lytrize/lytrize.db

# Windows
Remove-Item "$env:APPDATA\Lytrize\lytrize.db"
```

### Charts Not Rendering
- Check browser console for JavaScript errors
- Verify Plotly.js version compatibility (streamlit >=1.47 bundles 2.35.0)
- Check that the DataFrame has the expected columns

---

## 21. FAQ

### Q: Why two processes (launcher + backend)?
**A**: The launcher provides a native desktop experience (system tray, browser isolation, crash recovery) while the backend leverages Streamlit's rapid web UI development.

### Q: Why `@st.fragment` everywhere?
**A**: Without fragments, any widget interaction reruns the entire page. With 10+ charts, this becomes unusable. Fragments isolate each chart.

### Q: How does auto-update on re-upload work?
**A**: When a chart is generated, its `_generation_kwargs` are stored. On re-upload, `regenerate_charts()` re-runs each chart's runner with the stored kwargs against the new DataFrame.

### Q: How are large files handled?
**A**: Three strategies: chunked reading (CSVs > 30 MB), dtype optimization (downcast ints/floats, categorize strings), and smart sampling (charts sample to render limits).

### Q: Why are fonts bundled locally?
**A**: To ensure consistent rendering across all systems regardless of installed fonts. All TTF files are base64-embedded via `@font-face` rules.

### Q: Why WAL mode for SQLite?
**A**: Write-Ahead Logging allows concurrent reads while writing, important because the main thread reads/writes session state while background threads write parquet snapshots.

1. Standard library
2. Third-party
3. Local modules

### Docstrings

Google-style with `Args`, `Returns`, `Raises`.

### Error Handling

- Use `logging.getLogger(__name__)` for all logging
- Suppress expected errors with `exc_info=True`
- User-facing errors use `st.error()` / `st.warning()`
- Never crash the app - catch exceptions at runner boundaries
| CSV export | `(fname, index_choice, _df_version)` | File or index change |

---

## 14. Build & Packaging

### .deb (Debian/Ubuntu)
```bash
bash build.sh
# Output: build/lytrize_1.2_amd64.deb
```

### .rpm (Fedora/RHEL/openSUSE)
```bash
bash build_rpm.sh
# Output: build/lytrize-1.2-1.x86_64.rpm
```

### Windows .exe Installer
```powershell
powershell -ExecutionPolicy Bypass -File build_windows.ps1
# Output: build\LytrizeSetup_1.2.exe
```
**Requirements**: Python 3.11+, Inno Setup 7

---

## 15. Development Setup

### Linux
```bash
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run backend/app.py
```

### Windows
```powershell
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop
python -m venv venv
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
streamlit run backend/app.py
```

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `LYTRIZE_DB_PATH` | Override SQLite database path | Platform-specific |
| `LYTRIZE_CACHE_DIR` | Override cache directory | Platform-specific |
Every runner follows this pattern:

```python
def run_<chart_type>(df, <specific_cols>=None, palette=None, **kwargs) -> list[tuple[str, Figure]]:
    charts = []
    # ... build figures with plotly ...
    charts.append(("Chart Title", fig))
    return charts
```

**Rules for runners**:
1. **Pure logic only** - no `st.*` calls (except `st.warning` for edge cases)
2. **Return `list[tuple[str, Figure]]`** - each tuple is `(title, plotly_figure)`
3. **Tag figures** with `fig._lytrize_meta = {...}` for map_plot.py-style metadata
4. **Use `chart_layout()`** from `charts.py` for consistent layout
5. **Use `sample_for_plot()`** from `perf.py` for large datasets

---

## 8. Desktop Launcher Architecture

### Browser Detection

| Browser | Chromium Mode | Firefox Mode |
|---|---|---|
| Chrome, Brave, Edge, Vivaldi, Opera | `--app=<url>` | -- |
| Firefox, LibreWolf, Zen | -- | `--new-instance -profile <isolated> --kiosk` |

### Crash Recovery

If the Streamlit subprocess exits unexpectedly:
1. `_WatchThread` emits `crashed` signal
2. Launcher shows error state with "Restart" button
3. `_crash_count` tracks consecutive crashes
4. After 3 crashes, shows "Multiple crashes detected" warning

---

## 9. Database Layer

### Schema (Key Tables)

**users**: id, username, created_at

**sessions**: id, user_id, session_name, file_name, charts_json, kpis_json, layout_mode, grid_order_json, transform_log_json, created_at, updated_at

**drafts**: user_id, charts_json, kpis_json, updated_at

**activity_log**: id, user_id, action, detail, created_at

**datasets**: id, user_id, file_name, rows_count, cols_count

---

## 10. Fragment Isolation Pattern

### Where Fragments Are Used

| Location | Fragment Function | What It Isolates |
|---|---|---|
| `analysis.py` | `_render_config_and_actions()` | Config panel + Generate button |
| `upload.py` | `_render_upload_preview()` | Upload preview |
| `upload.py` | `_render_data_quality()` | Data quality section |
| `upload.py` | `_render_column_manager()` | Column manager |
| `upload.py` | `_render_data_cleaner()` | Data cleaner |
| `chart_card.py` | `render_chart_card()` | Each individual chart |
| `data_quality.py` | `_missing_controls()` | Missing value controls |

### Fragment Scope Rules

| Behavior | Inside Fragment | Outside Fragment |
|---|---|---|
| `st.rerun()` | Reruns only the fragment | Reruns entire app |
| `st.rerun(scope="app")` | Reruns entire app | Reruns entire app |
| Widget key scope | Local to fragment | Global |
| File | Purpose | Key Functions |
|---|---|---|
| `chart_card.py` | Per-chart card in @st.fragment | `render_chart_card()` |
| `chart_settings.py` | Chart type capability map | `apply_chart_display_options()`, `default_text_style()` |
| `column_manager.py` | Add/remove/rename columns | `show_column_manager()`, `_safe_formula_eval()` |
| `column_tools.py` | Dtype conversion & classification | `show_dtype_transformer()`, `convert_series_dtype()` |
| `css.py` | Global CSS, theme, logo | `inject_css()`, `render_logo()`, `set_theme_mode()` |
| `data_cleaner.py` | Text/numeric cleaning | `show_data_cleaner()` |
| `excel_loader.py` | Multi-sheet Excel handler | `show_excel_loader()` |
| `font_manager.py` | Font registry | `inject_bundled_font_css()`, `font_select()` |

---

### 5.9 `backend/modules/utils/` - Utility Modules

| File | Purpose | Key Functions |
|---|---|---|
| `paths.py` | Cross-platform path resolution | `data_dir()`, `cache_dir()`, `snapshot_dir()` |
| `session_cache.py` | DataFrame snapshots + memo | `set_df()`, `update_df()`, `save_df_snapshot()`, `load_df_snapshot()` |
| `transform_log.py` | Structural transform recording | `log_transform()`, `replay_transform_log()` |
| `regenerate.py` | Chart & KPI regeneration | `regenerate_charts()`, `regenerate_kpis()` |
| `perf.py` | Performance optimization | `optimize_dtypes()`, `read_csv_fast()`, `sample_for_plot()` |

---

### 5.10 `desktop/gui.py` - PySide6 Launcher

**Purpose**: Desktop launcher window that manages the Streamlit backend subprocess.

| Class | Base | Description |
|---|---|---|
| `_WaitThread` | `QThread` | Polls TCP until Streamlit is ready |
| `_WatchThread` | `QThread` | Monitors subprocess for crashes |
| `_PulseDot` | `QWidget` | Animated pulse indicator |
| `Launcher` | `QWidget` | Main launcher window |
> **Rule**: `gui.py` imports these values rather than hardcoding them.

---

### 5.3 `backend/modules/analysis/__init__.py` - Chart Registry & Config Layer

**Purpose**: Central registry for all chart types. This is the most critical module for understanding the chart system.

**Key Data Structures**:

| Name | Type | Description |
|---|---|---|
| `ANALYSIS_OPTIONS` | `list[dict]` | UI metadata for each chart type: `id`, `icon`, `name`, `desc` |
| `_RUNNERS` | `dict[str, callable]` | Maps chart type id to runner function |
| `_WIDGET_SPEC` | `dict[str, list[tuple]]` | Maps chart type id to widget spec for Edit-chart state capture |
| `_NEEDS_AXES` | `set[str]` | Chart types that support axis configuration |

**Key Functions**:

| Function | Signature | Description |
|---|---|---|
| `render_config_panel(active, df, analysis_name)` | `(str, DataFrame, str) -> None` | Renders the configuration UI for the active chart type |
| `_collect_kwargs(aid, df, uid)` | `(str, DataFrame, int) -> dict` | Reads widget values from `session_state` and builds kwargs for the runner |
| `_run(aid, df, **kwargs)` | `(str, DataFrame, **kwargs) -> list[tuple]` | Dispatches to the correct runner, returns `[(uid, title, fig), ...]` |
| `_collect_widget_state(aid)` | `(str) -> dict` | Captures current widget values for later restoration |
|   |       |-- paths.py            # Cross-platform data/cache dir resolution
|   |       |-- perf.py             # Performance: dtype optimization, sampling, chunked CSV
|   |       |-- regenerate.py       # Chart & KPI regeneration on re-upload
|   |       |-- session_cache.py    # DataFrame snapshot helpers, session_cached decorator
|   |       +-- transform_log.py    # Structural transform recording & replay
|   +-- tests/                      # pytest test suite
|       |-- conftest.py             # Test fixtures (adds backend/ to sys.path)
|       |-- test_choropleth_settings.py
|       |-- test_map_plot_encoding.py
|       |-- test_map_plot_hover_extras.py
|       +-- test_map_plot_value_size.py
|-- desktop/                        # PySide6 launcher
|   |-- gui.py                      # Main launcher window (QWidget, QThread workers)
|   +-- launcher.py                 # CLI entry point for installed builds
|-- packaging/                      # Distribution packaging
|   |-- deb/                        # Debian/Ubuntu packaging
|   |   |-- DEBIAN/                 # control, postinst, postrm
|   |   +-- usr/                    # .desktop file, bin launcher stub
|   +-- rpm/                        # Fedora/RHEL/openSUSE packaging
|       |-- lytrize.spec            # RPM spec file
|       +-- usr/                    # .desktop file, bin launcher stub
|-- service/
|   +-- lytrize.service             # systemd user service unit (Linux)
|-- build.sh                        # .deb builder script
|-- build_rpm.sh                    # .rpm builder script
|-- build_windows.ps1               # Windows .exe installer builder (Inno Setup 7)
|-- requirements.txt                # Python dependencies
|-- LICENSE                         # MIT License
|-- README.md                       # User-facing documentation
+-- CONTRIBUTOR.md                  # This file - developer manual
```
7. On "Stop & Quit", launcher terminates the subprocess and all browser windows

### Threading Model (Launcher)

| Thread | Class | Purpose |
|---|---|---|
| Main thread | -- | Qt event loop, widget interactions |
| Wait thread | `_WaitThread(QThread)` | Polls TCP port until backend is ready |
| Watch thread | `_WatchThread(QThread)` | Blocks on `proc.wait()` to detect crashes |

> **Rule**: All subprocess I/O happens in QThread subclasses. Results communicate back to the main thread exclusively via Qt signals. Never call Qt widget methods from a non-main thread.

### Python Version

- **3.11+** required (uses `match`/`case`, `tomlib`, `ExceptionGroup`, etc.)

### Platforms

| Platform | Data Directory | Cache Directory |
|---|---|---|
| Linux | `~/.local/share/lytrize` | `$XDG_CACHE_HOME/lytrize` or `~/.cache/lytrize` |
| Windows | `%APPDATA%\Lytrize` | `%LOCALAPPDATA%\Lytrize` |