# Contributing to Lytrize

Thanks for your interest! This guide covers the repository layout, local development setup, architecture, and conventions used in Lytrize. It doubles as the **complete developer documentation** for the app and codebase.

---

## Table of Contents

1. [Project Overview](#project-overview)
2. [Repository Structure](#repository-structure)
3. [Architecture](#architecture)
4. [Data Flow](#data-flow)
5. [Development Setup](#development-setup)
6. [Module-by-Module Reference](#module-by-module-reference)
7. [Adding a New Chart Type](#adding-a-new-chart-type)
8. [Adding a New Page](#adding-a-new-page)
9. [Making UI Changes](#making-ui-changes)
10. [Database Schema](#database-schema)
11. [Session State Keys](#session-state-keys)
12. [Performance Considerations](#performance-considerations)
13. [Packaging & Building](#packaging--building)
14. [Testing Guidelines](#testing-guidelines)
15. [Debugging Guide](#debugging-guide)
16. [Code Style and Conventions](#code-style-and-conventions)
17. [Contributing Workflow](#contributing-workflow)
18. [Known Issues & Limitations](#known-issues--limitations)
19. [License](#license)

---

## Project Overview

Lytrize is a **local-first, offline desktop analytics application** for Linux. It lets users upload CSV or Excel files and generate interactive Plotly charts, dashboards, and plain-English insights — all without an internet connection, cloud account, or telemetry.

### Key Design Principles

| Principle | How it's implemented |
|---|---|
| **Local-first** | All data stays on the user's machine. SQLite database at `~/.local/share/lytrize/lytrize.db`. No server, no cloud. |
| **Offline** | No outbound network requests. Plotly.js is bundled inline in exports. Fonts are loaded via Google Fonts with a `noscript` fallback (or system fonts). |
| **No account required** | A permanent local guest user is created automatically on first launch. |
| **Crash recovery** | The desktop launcher detects Streamlit crashes and shows a recoverable error. Sessions auto-save to drafts on every chart mutation. |
| **Fast** | Chunked CSV reader, dtype optimization, smart sampling, and Streamlit fragment isolation for per-chart interactivity. |

### Technology Stack

| Layer | Technology |
|---|---|
| **Backend** | Python 3.11+, Streamlit, Pandas, Plotly, PyArrow, statsmodels, pycountry |
| **Desktop Launcher** | PySide6 (Qt 6) |
| **Database** | SQLite (WAL mode) |
| **Packaging** | `.deb` (dpkg-deb), `.rpm` (rpmbuild) |
| **Export** | Self-contained HTML with inline Plotly.js |

---

## Repository Structure

```text
lytrize_desktop/
├── backend/                    # Streamlit application and all data processing code
│   ├── app.py                  # Entry point: routing, session restore, CSS injection
│   ├── config.py               # Shared constants (APP_NAME, APP_VERSION, APP_HOST, APP_PORT)
│   ├── assets/                 # Icons, welcome banner, bundled fonts
│   │   ├── lytrize.png / .ico
│   │   ├── welcome-banner.png
│   │   └── fonts/              # 40+ bundled TTF fonts for offline use
│   └── modules/
│       ├── __init__.py
│       ├── charts.py           # Palettes, chart layout, insight engine, JSON serialization
│       ├── database.py         # SQLite schema, all DB I/O, backup/restore
│       ├── export.py           # HTML export engine, theme system
│       ├── analysis/           # Chart runners and configuration registry
│       │   ├── __init__.py     # ANALYSIS_OPTIONS, _RUNNERS, _WIDGET_SPEC, config panels
│       │   ├── apply_lytrize_standard.py  # Shared chart styling helpers
│       │   ├── descriptive.py
│       │   ├── statistical.py
│       │   ├── distribution.py
│       │   ├── correlation.py
│       │   ├── categorical.py
│       │   ├── pie_chart.py
│       │   ├── time_series.py
│       │   ├── scatter_plot.py
│       │   ├── matrix_table.py
│       │   ├── outlier.py
│       │   ├── map_plot.py
│       │   ├── data_quality.py
│       │   └── insights.py       # Auto-insight generation
│       ├── pages/              # Streamlit page implementations
│       │   ├── __init__.py
│       │   ├── home.py         # Home page + saved sessions browser
│       │   ├── upload.py       # File upload, column classification, data cleaning
│       │   ├── analysis.py     # Analysis selection and chart generation
│       │   ├── dashboard.py    # Dashboard builder, KPI cards, export
│       │   └── auth.py         # Guest profile, backup/restore
│       ├── ui/                 # UI components and styling
│       │   ├── __init__.py
│       │   ├── css.py          # Global CSS injection, theme tokens, fonts
│       │   ├── chart_card.py   # Per-chart card in isolated @st.fragment
│       │   ├── chart_settings.py  # Display options, typography, font stacks
│       │   ├── column_manager.py  # Column rename UI
│       │   ├── column_tools.py    # Column type classifier, dtype transformer
│       │   ├── data_cleaner.py    # Missing value and outlier handling
│       │   ├── excel_loader.py    # Multi-sheet Excel loader
│       │   ├── font_manager.py    # Font picker, preview CSS
│       │   └── theme_tokens.py    # Design token definitions
│       └── utils/
│           ├── __init__.py
│           ├── perf.py         # Fast readers, dtype optimization, sampling
│           └── session_cache.py  # Parquet snapshots, session_state memo decorator
├── desktop/                   # PySide6 desktop launcher
│   ├── gui.py                 # Main launcher window, browser selection, crash recovery
│   └── launcher.py            # CLI entry point (called by /usr/local/bin/lytrize)
├── packaging/                 # Package build definitions
│   ├── deb/                   # .deb package structure (DEBIAN/, usr/)
│   └── rpm/                   # .rpm spec file and structure
├── service/                   # systemd user service
│   └── lytrize.service
├── build.sh                   # .deb build script
├── build_rpm.sh               # .rpm build script
├── requirements.txt           # Python dependencies
├── .gitignore
├── LICENSE                    # MIT
├── README.md                  # User-facing documentation
└── CONTRIBUTING.md            # This file — developer documentation
```

---

## Architecture

Lytrize has a **two-layer architecture**: a PySide6 desktop launcher that manages a Streamlit backend subprocess.

```text
┌─────────────────────────────────────────────────────────────────────┐
│                    desktop/ (Launcher Layer)                        │
│  gui.py       — PySide6 window: browser selection, Streamlit         │
│                 subprocess management, system tray, crash recovery   │
│  launcher.py  — CLI entry point called by /usr/local/bin/lytrize    │
│                 (resolves the venv Python and launches gui.py)       │
└──────────────────────────┬──────────────────────────────────────────┘
                           │ subprocess (python -m streamlit run)
                           ▼
┌─────────────────────────────────────────────────────────────────────┐
│                   backend/ (Streamlit Application)                   │
│  app.py        — Entry point: routing, session restore, CSS inject  │
│  config.py     — APP_NAME, APP_VERSION, APP_HOST, APP_PORT          │
│                                                                     │
│  modules/                                                           │
│    charts.py     — Palettes, chart_layout(), insight engine,        │
│                    charts_to_json(), charts_json_cached()             │
│    database.py   — SQLite schema, init_db(), CRUD, backup/restore,  │
│                    session management                              │
│    export.py     — generate_html_report(), theme system,            │
│                    _merge_theme(), _apply_axes(), _apply_legend_names()│
│                                                                     │
│    analysis/      — Chart runners and configuration registry         │
│      __init__.py     — ANALYSIS_OPTIONS, _RUNNERS, _WIDGET_SPEC,    │
│                        render_config_panel(), _collect_kwargs(),      │
│                        _run(), generate_insights()                    │
│      descriptive.py, statistical.py, distribution.py,               │
│      correlation.py, categorical.py, pie_chart.py,                  │
│      time_series.py, scatter_plot.py, matrix_table.py,              │
│      outlier.py, map_plot.py, data_quality.py,                      │
│      insights.py, apply_lytrize_standard.py                          │
│                                                                     │
│    pages/         — Streamlit page implementations                    │
│      home.py         — Home page + saved sessions browser            │
│      upload.py       — File upload, column classification, cleaning  │
│      analysis.py     — Analysis selection and chart generation       │
│      dashboard.py    — Dashboard builder, KPI cards, export          │
│      auth.py         — Guest profile, backup/restore                 │
│                                                                     │
│    ui/            — UI components and styling                        │
│      css.py            — Global CSS, theme tokens, font injection   │
│      chart_card.py     — Per-chart card in isolated @st.fragment      │
│      chart_settings.py — Display options, typography, font stacks    │
│      column_manager.py — Column rename UI                            │
│      column_tools.py   — Column type classifier, dtype transformer  │
│      data_cleaner.py   — Missing value and outlier handling          │
│      excel_loader.py   — Multi-sheet Excel loader                    │
│      font_manager.py   — Font picker, preview CSS                    │
│      theme_tokens.py   — Design token definitions                    │
│                                                                     │
│    utils/         — Performance and caching utilities               │
│      perf.py          — Fast readers, dtype optimization, sampling  │
│      session_cache.py — Parquet snapshots, session_state memo        │
└─────────────────────────────────────────────────────────────────────┘
```

### Launcher Lifecycle

1. **Launch** — `lytrize` → `/usr/local/bin/lytrize` → `desktop/launcher.py` → `desktop/gui.py`
2. **Browser detection** — `_detect_browsers()` scans for Chrome, Chromium, Brave, Edge, Vivaldi, Opera, Firefox, Firefox ESR, Zen, LibreWolf. Deduplicates by resolved binary path.
3. **Streamlit start** — `Launcher._start()` spawns `python -m streamlit run backend/app.py` as a subprocess in a new process group (`start_new_session=True`).
4. **Wait** — `_WaitThread` polls TCP port 8501 until Streamlit accepts connections (30s timeout).
5. **Watch** — `_WatchThread` blocks on `proc.wait()` to detect unexpected exits. `cancel()` must be called before intentional termination to suppress false crash reports.
6. **Browser open** — On ready, the launcher opens the app URL in the selected browser:
   - **Chromium-based**: `--app=<url>` (strips browser chrome, isolated profile)
   - **Firefox/Gecko**: `--new-instance --profile <isolated> --kiosk`
   - **xdg-open** (fallback): delegates to system default
7. **System tray** — The launcher minimizes to the system tray with "Open App" and "Stop & Quit" actions.
8. **Crash recovery** — If Streamlit exits with a non-zero code (and not cancelled), the launcher shows "Crashed (exit N) — click Start to retry" and enables the Start button.

### Browser Isolation

- **Chromium-based browsers** launch with `--app=<url>` which opens the page in a standalone maximised window with no address bar, tabs, or toolbar. An isolated profile is stored at `~/.local/share/lytrize/browser-profiles/chromium/`.
- **Firefox / LibreWolf / Zen** launch with `--new-instance` + a dedicated isolated profile at `~/.local/share/lytrize/browser-profiles/firefox/`. A `user.js` file suppresses first-run dialogs, telemetry prompts, and crash reporters. A `userChrome.css` file hides the URL bar and tab strip.
- **xdg-open** (fallback) delegates to the system default handler with no isolation.

---

## Data Flow

1. **Launcher starts Streamlit** — `desktop/gui.py` spawns `python -m streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1`.
2. **App bootstrap** — `app.py:main()` calls `_init_db_once()` (creates SQLite tables), `inject_css()` (loads fonts + stylesheet), creates a guest user if needed, and restores any saved draft.
3. **Routing** — `app.py` reads `st.session_state.page` (or the `p` URL parameter) and dispatches to `page_home()`, `page_upload()`, `page_analysis()`, `page_dashboard()`, or `page_profile()`.
4. **Upload** — `page_upload()` uses `read_csv_fast()` or `read_excel_sheet()` from `perf.py` to load the file, runs `optimize_dtypes()`, and stores the DataFrame in `st.session_state.df`. The column classifier (`column_tools.py`) auto-detects numeric, categorical, and datetime columns.
5. **Analysis** — `page_analysis()` renders chart-type cards from `ANALYSIS_OPTIONS`. When the user clicks **Generate**, `_collect_kwargs()` reads widget values from `session_state`, `_run()` dispatches to the appropriate chart runner, and `generate_chart_insights()` produces plain-English observations.
6. **Chart display** — Each chart is rendered in an isolated `@st.fragment` (`chart_card.py`) so that adjusting one chart's settings only reruns that chart, not the entire page.
7. **Dashboard** — `page_dashboard()` arranges charts in a grid, calculates KPI cards, and renders the export button. `generate_html_report()` from `export.py` produces a self-contained HTML file with inline Plotly.js.
8. **Persistence** — Drafts auto-save on every chart mutation via `save_draft()`. Saved sessions are stored in the `sessions` table via `save_session_db()`. The DataFrame is snapshotted to parquet via `save_df_snapshot()` for tab-refresh recovery.

---

## Development Setup

### Prerequisites

- **OS:** Linux (Ubuntu 20.04 LTS or later recommended)
- **Python:** 3.11 or newer
- **Browser:** Chrome, Chromium, Firefox, Brave, or Edge (for testing)
- **Git**

### Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop

# 2. Create a virtual environment
python3 -m venv venv
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Run the app in development
streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1
```

Open `http://127.0.0.1:8501` in your browser.

> **Note:** The packaged launcher under `desktop/launcher.py` is for installed builds only. It expects the app at `/opt/lytrize`, so do not use it for a source checkout. For development, use `streamlit run backend/app.py` directly.

### Development Environment Variables

| Variable | Default | Purpose |
|---|---|---|
| `LYTRIZE_DB_PATH` | `~/.local/share/lytrize/lytrize.db` | Override the SQLite database path (useful for testing) |
| `XDG_RUNTIME_DIR` | (system default) | Controls where parquet snapshots are stored (tmpfs if available) |
| `XDG_CACHE_HOME` | `~/.cache` | Fallback cache directory for parquet snapshots |

Example for testing with a throwaway database:
```bash
LYTRIZE_DB_PATH=/tmp/lytrize_test.db streamlit run backend/app.py
```

### Running the Desktop Launcher from Source

To test the PySide6 launcher from a source checkout:

```bash
python desktop/gui.py
```

This will use the source tree's `backend/app.py` directly (no `/opt/lytrize` needed).

---

## Module-by-Module Reference

### `backend/app.py` — Entry Point

The main Streamlit application. Key responsibilities:

- **`main()`** — Orchestrates app startup: initializes the database, injects CSS, creates/restores the guest user, restores drafts, and dispatches to the active page.
- **`_init_db_once()`** — Cached function that calls `init_db()` exactly once per process.
- **`_restore_draft(user_id)`** — Reloads an in-progress analysis session from `draft_sessions` into `session_state`: charts (deserialized from Plotly JSON), KPIs, dashboard title, layout mode, column descriptions, and the DataFrame snapshot.
- **Routing** — Reads `st.session_state.page` (or the `p` URL parameter) and calls the corresponding page function. URL parameters `p` (page) and `sid` (session ID) are kept in sync.

### `backend/config.py` — Constants

Shared configuration constants:
- `APP_NAME = "Lytrize"`
- `APP_VERSION = "1.0"`
- `APP_HOST = "127.0.0.1"`
- `APP_PORT = 8501`

### `backend/modules/charts.py` — Chart Utilities & Insight Engine

- **`PALETTES`** — 15 named color palettes (Default Blue-Purple, Vibrant, Nature Green, Warm Sunset, etc.)
- **`chart_layout(height)`** — Returns a dict of Plotly layout kwargs used by every chart (transparent background, no gridlines, dark hover labels).
- **`generate_chart_insights(chart_type, title, fig, col_descriptions)`** — Produces plain-English observations from a Plotly figure. Handles distributions, correlations, outliers, time series, categorical/pie, scatter, statistical, data quality, and matrix charts.
- **`charts_to_json(charts)`** — Serializes the active chart list to JSON for database storage.
- **`charts_json_cached()`** — Memoized version that only re-serializes when the chart set or notes actually change (debounced autosave).
- **`clean_insights(insights)`** — Strips markdown bold markers and normalizes spacing from insight text.
- **Helper functions** — `_fmt_num()` (K/M/B formatting), `_fmt_pct()`, `_fmt_label()`, `_as_number_series()`, `_as_list()`, `_plural()`.

### `backend/modules/database.py` — Database Layer

All SQLite operations. Key functions:

- **`init_db()`** — Creates all tables (`users`, `sessions`, `user_activity`, `draft_sessions`). Safe to call every startup (`CREATE TABLE IF NOT EXISTS`). Includes migration logic via `ALTER TABLE ... ADD COLUMN` wrapped in `try/except`.
- **`_connect()`** — Returns a SQLite connection with WAL mode, NORMAL synchronous, 8MB cache, MEMORY temp store, and 128MB mmap.
- **`_db()`** — Context manager that commits on success and rolls back on error.
- **`get_or_create_guest_user()`** — Returns the permanent local guest user, creating it if needed.
- **`save_draft(...)`** / **`get_draft(user_id)`** / **`clear_draft(user_id)`** — Draft session management (auto-save during analysis).
- **`save_session_db(...)`** / **`update_session_db(...)`** / **`delete_session_db(...)`** — Saved session CRUD.
- **`get_user_sessions(user_id)`** — Returns the 20 most recent sessions (cached with `@st.cache_data`, 30s TTL).
- **`save_draft(...)`** / **`get_draft(user_id)`** / **`clear_draft(user_id)`** — Draft session management (auto-save during analysis).
- **`save_session_db(...)`** / **`update_session_db(...)`** / **`delete_session_db(...)`** — Saved session CRUD.
- **`get_user_sessions(user_id)`** — Returns the 20 most recent sessions (cached with `@st.cache_data`, 30s TTL).
- **`get_session_charts(session_id, user_id)`** — Loads and deserializes charts from a saved session (Plotly JSON → Figure objects).
- **`get_session_meta(session_id, user_id)`** — Fetches dashboard metadata (title, KPIs, layout, grid order, export settings).
- **`export_sessions_to_dict(...)`** / **`import_sessions_from_dict(...)`** — Backup/restore as JSON.
- **`merge_user_data(source_user_id, target_user_id)`** — Reassigns local data from a guest account to a newly signed-in account.
- **`log_activity(user_id, action_type, detail, session_id)`** — Appends to the audit log (never raises).

### `backend/modules/export.py` — HTML Export Engine

- **`generate_html_report(charts, session_name, orientation, kpis, dashboard_title, grid_cols_n, theme)`** — Generates a fully self-contained HTML dashboard file with inline Plotly.js, embedded fonts, KPI cards, insights, notes, and print-optimized CSS.
- **`DEFAULT_THEME`** — 25+ theme keys (background colors, card colors, typography, layout, etc.).
- **`_merge_theme(user_theme)`** — Merges user overrides over defaults.
- **`_apply_axes(fig, x_lbl, y_lbl, text_style)`** — Applies axis titles and tick fonts to a figure copy.
- **`_apply_legend_names(fig, legend_names, legend_title, text_style)`** — Renames traces and styles the legend.
- **`_h(text)`** — HTML-escapes a value (use for all user-controlled text in HTML strings).

### `backend/modules/analysis/__init__.py` — Analysis Registry

The central registry that connects chart types to their runners and configuration widgets.

- **`ANALYSIS_OPTIONS`** — List of 11 chart-type cards shown on the Analysis page. Each has `id`, `icon`, `name`, `desc`.
- **`_RUNNERS`** — Dict mapping `aid → runner_function`. Each runner returns a list of `(title, fig)` tuples.
- **`_WIDGET_SPEC`** — Dict mapping `aid → list of (key, kwarg, kind)` tuples defining the configuration widgets for each chart type. Kinds: `scalar`, `list`, `palette`, `scalar_map`, `number`, `bool`.
- **`render_config_panel(aid, df)`** — Renders the configuration widgets for a chart type (non-scoped, used on the main analysis page).
- **`render_config_panel_scoped(uid, aid, df)`** — Renders uid-scoped configuration widgets (used in the regenerate panel).
- **`_collect_kwargs(aid, df)`** / **`_collect_kwargs_scoped(uid, aid, df)`** — Reads widget values from `session_state` and returns a kwargs dict for the runner.
- **`_run(aid, df, **kwargs)`** — Dispatches to the correct runner and returns `(uid, title, fig)` tuples. Calls `generate_insights()` for each chart.

### `backend/modules/analysis/*.py` — Chart Runners

Each runner module implements a `run_<type>(df, **kwargs)` function that returns a list of `(title, fig)` tuples.

| Module | Runner | What it produces |
|---|---|---|
| `descriptive.py` | `run_descriptive(df)` | Summary statistics table (no kwargs) |
| `statistical.py` | `run_statistical(df, **kwargs)` | Bar charts of mean/median/min/max/std grouped by category |
| `distribution.py` | `run_distribution(df, **kwargs)` | Histograms and boxplots |
| `correlation.py` | `run_correlation(df, **kwargs)` | Correlation matrix heatmap |
| `categorical.py` | `run_categorical(df, **kwargs)` | Bar/column charts with aggregation, dual Y-axis |
| `pie_chart.py` | `run_pie_chart(df, **kwargs)` | Pie and donut charts with sorting and top-N |
| `time_series.py` | `run_time_series(df, **kwargs)` | Line charts with date grouping and aggregation |
| `scatter_plot.py` | `run_scatter_plot(df, **kwargs)` | Scatter plots with trendlines (OLS/LOWESS) |
| `matrix_table.py` | `run_matrix_table(df, **kwargs)` | Pivot table as a data table |
| `matrix_heatmap.py` | `run_matrix_heatmap(df, **kwargs)` | Pivot table as a heatmap |
| `outlier.py` | `run_outlier(df, **kwargs)` | IQR-based outlier detection charts |
| `outlier.py` | `run_outlier_upload(df)` | Outlier summary for the upload page |
| `map_plot.py` | `run_map_plot(df, **kwargs)` | Geographic scatter or choropleth maps |
| `data_quality.py` | `run_data_quality(df)` | Missing values, duplicates, column quality |
| `insights.py` | `generate_insights(aid, df, uid, **kwargs)` | Auto-insight generation for each chart |
| `apply_lytrize_standard.py` | (helpers) | Shared chart styling and figure normalization |

### `backend/modules/pages/` — Page Implementations

#### `home.py` — Home Page
- Renders a welcome banner with the OS username.
- Shows KPI summary cards (saved sessions, datasets analysed, available analyses).
- Lists the 20 most recent saved sessions with View, Edit, Rename, and Delete buttons.
- "Start New Analysis" button clears all session state and navigates to the upload page.

#### `upload.py` — Upload & Data Preparation
- File uploader for CSV and Excel (up to 300 MB).
- Data preview (top/bottom/random 10 rows).
- Column descriptions (optional, improves auto-insights).
- Data quality summary (missing values, duplicates).
- Outlier detection.
- Column Manager (rename columns).
- Data-type Transformer (change dtypes).
- Data Cleaner (handle missing values and outliers).
- CSV download (export cleaned data).
- Column Classifier (auto-detect numeric/categorical/datetime columns).
- Parquet snapshot saved immediately after upload for tab-refresh recovery.

#### `analysis.py` — Analysis & Chart Generation
- Renders chart-type cards from `ANALYSIS_OPTIONS` in a 5-column grid.
- When a chart type is selected, renders the configuration panel (`render_config_panel()`).
- "Generate Charts" button calls `_collect_kwargs()` + `_run()` + `_add_charts()`.
- Generated charts are rendered via `render_chart_card()` in isolated fragments.
- "Proceed to Dashboard" button saves and navigates to the dashboard.
- Supports edit mode (adding charts to an existing saved session) and regenerate mode (re-running a chart with new settings).

#### `dashboard.py` — Dashboard Builder
- KPI card management (13 KPI types: sum, mean, median, count, min, max, % of total, unique count, date range, top/bottom category, MoM/YoY % change).
- Dashboard title and session name input.
- Export layout selection (portrait 2-column or landscape 3-column).
- Save/Update buttons.
- Visual layout builder (drag-and-drop grid arrangement with full-width support).
- Chart rendering with per-chart settings (Chart Settings + Typography expanders).
- HTML export via `generate_html_report()`.

#### `auth.py` — Guest Profile & Backup
- Guest profile page with local data information.
- **Backup** — Exports all saved sessions as a portable JSON file (select which sessions to include).
- **Restore** — Imports sessions from a Lytrize backup JSON file.

### `backend/modules/ui/` — UI Components

#### `css.py` — Global CSS
- Hides all Streamlit chrome (toolbar, header, deploy button).
- Injects Google Fonts (Inter, Sora, JetBrains Mono) with `noscript` fallback.
- Defines CSS custom properties for dark and light themes.
- Styles all Streamlit components: buttons, inputs, selectboxes, multiselects, expanders, sliders, checkboxes, tabs, file uploader, tooltips, color picker, dataframe toolbar.
- `inject_css()` — Call once per page to load fonts + stylesheet.
- `inject_footer()` — Renders the footer with version info.
- `render_logo()` — Renders the Lytrize logo.
- `set_theme_mode(mode)` / `get_theme_mode()` — Theme switching (dark/light).

#### `chart_card.py` — Per-Chart Card (Isolated Fragment)
- **`render_chart_card(uid, title, fig, chart_type, meta, auto_insights, ...)`** — Renders a single chart inside an `@st.fragment` so that adjusting one chart's settings only reruns that chart.
- Two-column layout: settings (left) + chart (right).
- Settings include: Chart Settings expander (display options) and Typography expander (fonts, sizes, colors).
- Top bar: title/subtitle preview, Edit Chart button, Delete button.
- **`get_display_fig(uid, base_fig, meta, chart_type)`** — Memoized display-figure cache. Only rebuilds when meta or base figure changes.
- **`_fig_signature(fig)`** — Content-aware MD5 signature of a Plotly figure for cache invalidation.

#### `chart_settings.py` — Display Options & Typography
- **`CHART_TYPE_SETTINGS`** — Per-chart-type capabilities: which controls and typography options are available.
- **`apply_chart_display_options(fig, meta, chart_type)`** — Applies all display options from meta to a figure (value labels, bar gap, line width, histogram bins, pie settings, heatmap annotations, table styling, etc.).
- **`render_chart_settings_controls(uid, title, fig, chart_type, meta, ...)`** — Renders the Chart Settings expander UI.
- **`render_typography_controls(uid, fig, chart_type, meta, ...)`** — Renders the Typography expander UI.
- **`FONT_STACK_MAP`** — 40+ font families mapped to CSS font stacks with fallbacks.
- **`default_text_style()`** — Default typography settings (family, sizes, colors).
- **`merge_text_style(raw)`** — Merges stored text-style dict over defaults.
- **`compute_meta_hash(meta)`** — Hashes the full meta dict for cache invalidation.

#### `column_manager.py` — Column Rename
- `show_column_manager(df)` — UI for renaming columns with a table of old/new names.

#### `column_tools.py` — Column Classification & Type Transformation
- `show_column_classifier(df)` — Auto-detects numeric, categorical, and datetime columns. Sets `st.session_state.num_cols`, `cat_cols`, `dt_cols`.
- `show_dtype_transformer(df)` — UI for changing column data types (e.g., string → datetime, int → float).

#### `data_cleaner.py` — Missing Values & Outliers
- `show_data_cleaner(df)` — UI for handling missing values (drop, fill with mean/median/mode/constant) and outlier treatment.

#### `excel_loader.py` — Excel Loader
- `show_excel_loader(uploaded)` — UI for selecting sheets from multi-sheet Excel files.

#### `font_manager.py` — Font Picker
- `font_select(label, key, ...)` — Streamlit selectbox for font selection.
- `get_font_stack(font_name)` — Resolves a font name to a CSS font stack.
- `inject_font_preview_css()` — Injects CSS for font preview rendering.

#### `theme_tokens.py` — Design Tokens
- Defines design token constants used across the UI.

### `backend/modules/utils/` — Utilities

#### `perf.py` — Performance Utilities
- **`read_csv_fast(file, **kwargs)`** — Reads a CSV file and returns a dtype-optimised DataFrame. Uses chunked reading for files over 30 MB.
- **`read_csv_chunked(file, chunksize, max_rows)`** — Reads large CSVs in chunks and concatenates with dtype optimization.
- **`read_excel_sheet(file, sheet_name)`** — Reads a single Excel sheet with dtype optimization.
- **`get_sheet_names(file)`** — Returns sheet names without loading data.
- **`optimize_dtypes(df)`** — Shrinks DataFrame memory: downcasts integers/floats, converts low-cardinality object columns to category.
- **`sample_for_plot(df, n, random_state)`** — Returns a random sample of at most n rows for Plotly rendering.
- **`sample_for_histogram(df, n)`** — Sampling for histogram/distribution charts.
- **`enforce_render_limit(df, chart_type)`** — Samples df to the render budget for a given chart type.
- **`top_n_with_other(series, n)`** — Keeps top-n categories and replaces the rest with "Other".
- **`mem_mb(df)`** — Returns total DataFrame memory usage in MB.
- **`RENDER_LIMITS`** — Per-chart-type render budgets (scatter: 8K, histogram: 50K, map: 10K, line: 50K, bar: 5K, heatmap: 500).

#### `session_cache.py` — Session Cache
- **`set_df(df)`** — Replaces `st.session_state.df`, bumps the `_df_version` counter, and invalidates all derived caches.
- **`update_df(df)`** — Shallow-copies df then stores via `set_df()` (for in-place mutations).
- **`save_df_snapshot(user_id, df)`** — Persists a DataFrame to a parquet snapshot for tab-refresh recovery.
- **`load_df_snapshot(user_id)`** — Restores the DataFrame from parquet. Enforces a 512 MB limit.
- **`df_cache_path(user_id)`** — Returns the parquet snapshot path (`$XDG_RUNTIME_DIR/lytrize/df_<id>.parquet` or `~/.cache/lytrize/`).
- **`session_cached(fn)`** — Decorator that caches a function's return value in `session_state`, keyed by function name and arguments.
- **`make_json_safe(value)`** — Returns a JSON-serializable version of a value.

### `desktop/gui.py` — Desktop Launcher

The PySide6 launcher window. Key components:

- **`Launcher`** — Main window class. Manages the UI (header, status, browser picker, Start/Open/Stop buttons, system tray) and the Streamlit subprocess lifecycle.
- **`_WaitThread`** — QThread that polls TCP port 8501 until Streamlit is ready (30s timeout).
- **`_WatchThread`** — QThread that monitors the Streamlit subprocess for unexpected exits.
- **`_PulseDot`** — Animated status indicator (green pulse when running, grey when stopped).
- **`_ensure_firefox_profile(profile_dir)`** — Creates a minimal Firefox profile with `user.js` and `userChrome.css` to suppress first-run dialogs and hide browser chrome.
- **`_detect_browsers()`** — Scans for installed browsers and returns a deduplicated list.
- **`_find_icon()`** — Returns the first existing icon file from `backend/assets/`.
- **`_load_prefs()` / `_save_prefs()`** — Persists launcher preferences (browser choice) atomically.

### `desktop/launcher.py` — CLI Entry Point

Called by `/usr/local/bin/lytrize`. Resolves the venv Python (`/opt/lytrize/venv/bin/python` or system `python3`) and launches `desktop/gui.py`.

---

## Adding a New Chart Type

1. **Create the runner** — Create `backend/modules/analysis/<new_type>.py` with a `run_<new_type>(df, **kwargs)` function that returns a list of `(title, fig)` tuples. Use `chart_layout()` from `charts.py` for consistent styling and `apply_hover_format()` for hover templates.

2. **Register it** — In `backend/modules/analysis/__init__.py`:
   - Import the runner: `from modules.analysis.<new_type> import run_<new_type>`
   - Add to `ANALYSIS_OPTIONS`:
     ```python
     {"id": "<new_type>", "icon": "📈", "name": "New Type", "desc": "Brief description"},
     ```
   - Add to `_RUNNERS`:
     ```python
     "<new_type>": run_<new_type>,
     ```

3. **Add widget spec** (if your chart needs configuration controls) — Add to `_WIDGET_SPEC`:
   ```python
   "<new_type>": [
       ("x", "x_cols", "scalar"),
       ("y", "y_cols", "list"),
       ("palette", "palette", "palette"),
   ],
   ```
   Widget kinds: `scalar` (selectbox), `list` (multiselect), `palette` (palette selectbox), `scalar_map` (selectbox with custom options), `number` (number_input), `bool` (checkbox).

4. **Add config panel** — In `render_config_panel()` and `render_config_panel_scoped()`, add an `elif aid == "<new_type>":` branch that renders the appropriate Streamlit widgets using `st.columns()`, `st.selectbox()`, `st.multiselect()`, etc. Use `_sk(aid, key)` for non-scoped keys and `_sk_uid(uid, aid, key)` for scoped keys.

5. **Add kwargs collection** — In `_collect_kwargs()` and `_collect_kwargs_scoped()`, add an `elif aid == "<new_type>":` branch that reads widget values and builds the kwargs dict for the runner.

6. **Add auto-insights** (optional) — If your chart type should generate insights, add a branch in `generate_chart_insights()` in `charts.py`.

That's it — no other files need changes.

---

## Adding a New Page

1. **Create the page** — Create `backend/modules/pages/<new_page>.py` with a `page_<new_page>()` function. Call `render_logo()` at the top and `inject_footer()` at the bottom.

2. **Import it** — In `backend/app.py`:
   ```python
   from modules.pages.<new_page> import page_<new_page>
   ```

3. **Add routing** — In `main()`, add:
   ```python
   elif p == "<new_page>": page_<new_page>()
   ```

4. **Add navigation** — Add a button to switch to the new page:
   ```python
   if st.button("New Page"):
       st.session_state.page = "<new_page>"
       st.rerun()
   ```

---

## Making UI Changes

### CSS

- **App-wide styles** — Edit `modules/ui/css.py`. The `_build_css()` function generates the full stylesheet. Use `_theme_vars()` for dark/light theme variables.
- **Per-page styling** — Add inline `st.markdown()` with `unsafe_allow_html=True` in the page module.
- **Component styles** — Use CSS classes defined in `css.py` (`.kpi-card`, `.sess-card`, `.ag-card`, `.welcome-banner`, `.sec-label`, etc.).
- **Avoid external CSS frameworks** — All styling is done with custom CSS.

### Streamlit Widgets

- Use `st.columns()` for layout and `st.expander()` for grouped controls.
- Keep widget keys unique with per-page prefixes (e.g., `f"btn_{opt['id']}"`).
- Use `on_change` callbacks for immediate state updates.
- Use `@st.fragment` for per-chart interactivity (see `chart_card.py`).

### Typography System

- Font families are defined in `FONT_STACK_MAP` in `chart_settings.py` (40+ options with CSS fallbacks).
- Typography controls (family, size, color, style) are stored in `chart_meta_{uid}` under the `text_style` key.
- `apply_chart_display_options()` applies typography to Plotly figures.
- `apply_chart_display_options()` deep-copies the figure before mutating — never mutate a shared figure in-place.

### Chart Display Options

- Per-chart display options are stored in `chart_meta_{uid}` under the `display_options` key.
- `CHART_TYPE_SETTINGS` in `chart_settings.py` defines which controls are available per chart type.
- The display-figure cache (`get_display_fig()`) only rebuilds when `compute_meta_hash(meta)` or the figure signature changes.

---

## Database Schema

All tables are created in `init_db()` with `CREATE TABLE IF NOT EXISTS`. Migrations use `ALTER TABLE ... ADD COLUMN` wrapped in `try/except`.

### `users`
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `username` | TEXT UNIQUE | Username (3-40 chars, alphanumeric + `_.-`) |
| `email` | TEXT UNIQUE | Email address |
| `password_hash` | TEXT | Hashed placeholder password for the local guest user. |
| `created_at` | TIMESTAMP | Default `CURRENT_TIMESTAMP` |
| `is_guest` | INTEGER | 1 for guest users, 0 for registered |
| `uuid` | TEXT UNIQUE | Unique identifier for backup/restore |

### `sessions`
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `user_id` | INTEGER FK | References `users(id)` |
| `session_uuid` | TEXT UNIQUE | UUID for backup/restore |
| `session_name` | TEXT | User-friendly name |
| `file_name` | TEXT | Original uploaded file name |
| `rows_count` | INTEGER | Row count of the dataset |
| `cols_count` | INTEGER | Column count |
| `analysis_types` | TEXT | JSON list of analysis types used |
| `charts_json` | TEXT | JSON array of charts (fig_json, title, desc, insights, meta) |
| `dashboard_title` | TEXT | Dashboard title |
| `kpis_json` | TEXT | JSON array of KPI cards |
| `layout_mode` | TEXT | "portrait" or "landscape" |
| `grid_order_json` | TEXT | JSON array of chart UIDs in grid order |
| `grid_fullwidth_json` | TEXT | JSON object of chart UID → full_width bool |
| `export_text_json` | TEXT | JSON object of text export settings |
| `export_colours_json` | TEXT | JSON object of color export settings |
| `source` | TEXT | "local" or "restored" |
| `created_at` | TIMESTAMP | Default `CURRENT_TIMESTAMP` |
| `updated_at` | TIMESTAMP | Updated on each save |

### `draft_sessions`
| Column | Type | Description |
|---|---|---|
| `user_id` | INTEGER PK | References `users(id)` (one draft per user) |
| `page` | TEXT | Current page ("home", "upload", "analysis", "dashboard") |
| `charts_json` | TEXT | JSON array of in-progress charts |
| `file_name` | TEXT | Current file name |
| `editing_session_id` | INTEGER | Session being edited (if in edit mode) |
| `editing_session_name` | TEXT | Name of session being edited |
| `editing_file_name` | TEXT | File name of session being edited |
| `dashboard_title` | TEXT | In-progress dashboard title |
| `kpis_json` | TEXT | In-progress KPIs |
| `chart_meta_json` | TEXT | JSON object of chart metadata |
| `layout_mode` | TEXT | "portrait" or "landscape" |
| `col_descriptions_json` | TEXT | JSON object of column descriptions |
| `updated_at` | TIMESTAMP | Default `CURRENT_TIMESTAMP` |

### `user_activity`
| Column | Type | Description |
|---|---|---|
| `id` | INTEGER PK | Auto-increment primary key |
| `user_id` | INTEGER FK | References `users(id)` |
| `session_id` | INTEGER | References `sessions(id)` (nullable) |
| `action_type` | TEXT | e.g., "analysis_run", "dashboard_saved", "session_updated" |
| `action_detail` | TEXT | JSON or text detail |
| `ts` | TIMESTAMP | Default `CURRENT_TIMESTAMP` |

| Column | Type | Description |
|---|---|---|
| `token` | TEXT PK | UUID token string |
| `user_id` | INTEGER FK | References `users(id)` |
| `username` | TEXT | Username at token creation |
| `expires_at` | TIMESTAMP | 7 days from creation |

---

## Session State Keys

The application uses `st.session_state` extensively. Keys are prefixed to avoid collisions.

### Core State

| Key | Set when | Description |
|---|---|---|
| `user_id` | app bootstrap | Integer local identity ID |
| `username` | app bootstrap | Display name |
| `is_guest` | app bootstrap | Boolean guest flag |
| `page` | app routing | Current page: "home", "upload", "analysis", "dashboard", "profile" |
| `df` | upload page | Active DataFrame |
| `file_name` | upload page | Original file name |
| `file_signature` | upload page | Stable signature of the uploaded file |
| `col_descriptions` | upload page | `{col: desc}` from column classifier |
| `num_cols` | upload page | Confirmed numeric column names |
| `cat_cols` | upload page | Confirmed categorical column names |
| `dt_cols` | upload page | Confirmed datetime column names |
| `charts` | analysis page | `[(uid, title, fig), ...]` |
| `selected_analyses` | analysis page | List of analysis type IDs used |
| `dashboard_title` | dashboard page | Dashboard title |
| `kpis` | dashboard page | List of KPI card dicts |
| `layout_mode` | dashboard page | "portrait" or "landscape" |
| `grid_order` | dashboard page | List of chart UIDs in grid order |
| `grid_fullwidth` | dashboard page | Dict of chart UID → full_width bool |
| `grid_cols_n` | dashboard page | 2 or 3 (grid columns) |

### Session Restore / Edit Mode

| Key | Set when | Description |
|---|---|---|
| `editing_session_id` | home (edit) | Integer session being edited |
| `editing_session_name` | home (edit) | Name of session being edited |
| `editing_file_name` | home (edit) | File name of session being edited |
| `view_session_id` | home (view) | Integer session being viewed |
| `view_session_name` | home (view) | Name of session being viewed |
| `_view_charts` | dashboard (view) | Loaded charts from saved session |
| `_vsid` | dashboard (view) | View session ID (cache invalidation) |

### Chart Metadata

| Key | Description |
|---|---|
| `chart_type_{uid}` | Analysis type ID for the chart |
| `desc_{uid}` | User-written notes for the chart |
| `auto_insights_{uid}` | List of auto-generated insight strings |
| `chart_meta_{uid}` | Dict of display options, text style, custom title, subtitle, etc. |

### Internal / Cache Keys

| Key | Description |
|---|---|
| `_df_version` | Incremented on every `set_df()` call (cache invalidation) |
| `_df_snapshot_sig` | Signature of the last saved DataFrame snapshot |
| `_notes_shadow` | Dict of `{uid: note}` synced from `desc_{uid}` keys |
| `_active_analysis` | Currently selected analysis type on the analysis page |
| `_regen_uid` / `_regen_type` / `_regen_restore` | Regenerate mode state |
| `_display_fig_{uid}` / `_display_fig_hash_{uid}` | Display-figure cache |
| `_charts_json_cache_val` / `_charts_json_cache_sig` | Charts JSON cache |
| `_ul_preview_cache` / `_ul_preview_cache_key` | Upload page preview cache |
| `_dq_charts` / `_dq_sig` | Data quality chart cache |
| `_analysis_notes_loaded` | Flag: analysis notes restored |
| `_edit_notes_loaded` | Flag: edit-mode notes restored |
| `_analysis_page_ready` | Flag: analysis page initialized |

### Widget Keys

Configuration widgets use namespaced keys:
- `_cfg_{aid}_{key}` — Non-scoped widget keys (main analysis page)
- `_edit_{uid}_{aid}_{key}` — Scoped widget keys (regenerate panel)

---

## Performance Considerations

### Caching Strategy

| Cache | Mechanism | What it caches |
|---|---|---|
| Database init | `@st.cache_resource` | `init_db()` — runs once per process |
| User sessions | `@st.cache_data(ttl=30)` | `get_user_sessions()` — 30s TTL |
| Display figures | `session_state` dict | `get_display_fig()` — rebuilt only when meta or figure changes |
| Charts JSON | `session_state` dict | `charts_to_json()` — debounced, only re-serializes when charts or notes change |
| CSV reading | `@st.cache_resource(max_entries=1)` | `_read_csv_cached()` — cached by file signature |
| Pivot tables | `@st.cache_data(ttl=300)` | `_pivot_impl()` — 5-minute TTL |
| Session cache | Custom `session_cached` decorator | Any pure function, keyed by args |

### DataFrame Optimization

- **`optimize_dtypes(df)`** — Downcasts integers (int64 → int8/16/32), floats (float64 → float32), and converts low-cardinality object columns to `category` dtype. Can reduce memory by 50-70%.
- **Chunked reading** — CSVs over 30 MB are read in 200K-row chunks with dtype optimization applied per chunk.
- **Parquet snapshots** — The DataFrame is saved to parquet after upload for tab-refresh recovery. Stored on tmpfs (`$XDG_RUNTIME_DIR`) if available, falling back to `~/.cache/lytrize/`.

### Sampling

- **`sample_for_plot(df, n)`** — Random sample of at most n rows for Plotly rendering.
- **`sample_for_histogram(df, n)`** — Sampling for distribution charts (50K default).
- **`enforce_render_limit(df, chart_type)`** — Samples to per-chart-type render budgets:
  - scatter: 8,000 | histogram: 50,000 | map: 10,000 | line: 50,000 | bar: 5,000 | heatmap: 500

### Fragment Isolation

- Each chart card is rendered inside an `@st.fragment` (`chart_card.py`).
- Adjusting one chart's settings (typography, display options) only reruns that chart's fragment — the rest of the page (nav, preview, KPIs, other charts) stays inert.
- This is the single largest performance win for interactivity.

### Common Pitfalls

- **Streamlit reruns are expensive** — Avoid heavy computation at module top-level. Use `@st.cache_data` or `@st.cache_resource`.
- **Session state key collisions** — Always prefix keys (`_cfg_`, `auto_insights_`, `desc_`, `chart_meta_`).
- **Circular imports** — Keep chart runners in `modules/analysis/` and UI helpers in `modules/ui/`. Shared constants go in `charts.py` or `config.py`.
- **Plotly figure mutability** — Deep-copy figures before mutating them in export or display helpers. Plotly figures are mutable and shared across reruns.
- **Cache invalidation** — `compute_meta_hash()` hashes the full meta dict so any future key auto-invalidates the display cache.

---

## Packaging & Building

### .deb Package

```bash
bash build.sh
```

The build script (`build.sh`):
1. Cleans the build directory
2. Copies `backend/`, `desktop/`, and `service/` to the staging area
3. Creates an isolated Python virtual environment
4. Installs all dependencies (streamlit, pandas, plotly, openpyxl, statsmodels, pycountry, PySide6)
5. Patches venv shebangs for portability
6. Slims the venv (removes `__pycache__`, tests, docs, `.pyc` files)
7. Bakes icons at standard sizes (16-256px)
8. Sets permissions and builds the `.deb` with `dpkg-deb`

Output: `build/lytrize_1.0_amd64.deb`

### .rpm Package

```bash
bash build_rpm.sh
```

The build script (`build_rpm.sh`):
1. Cleans and stages files
2. Creates an isolated venv and installs dependencies
3. Patches venv shebangs
4. Slims the venv
5. Builds the RPM with `rpmbuild` using the spec file at `packaging/rpm/lytrize.spec`

Output: `build/lytrize-1.0-1.x86_64.rpm`

### What Gets Bundled

| Component | Location | Size |
|---|---|---|
| Backend code | `/opt/lytrize/backend/` | ~5 MB |
| Desktop launcher | `/opt/lytrize/desktop/` | ~1 MB |
| Isolated Python venv | `/opt/lytrize/venv/` | ~350 MB |
| Fonts | `/opt/lytrize/backend/assets/fonts/` | ~5 MB |
| Icons | `/usr/share/icons/hicolor/` | ~1 MB |
| Desktop entry | `/usr/share/applications/lytrize.desktop` | — |
| Launcher binary | `/usr/local/bin/lytrize` | — |

### Post-Install

- The `.deb` postinst and `.rpm` `%post` script:
  - Re-links venv Python symlinks to the system Python
  - Fixes permissions (world-readable so non-root users can run the app)
  - Creates the per-user data directory
  - Refreshes icon and desktop caches

### Uninstall

- The package uninstaller removes `/opt/lytrize/` and system files but **not** user data at `~/.local/share/lytrize/`.
- The `.rpm` `%preun` and `%postun` scripts also terminate running instances and stop systemd user services.

---

## Testing Guidelines

Currently, the project does not include an automated test suite. When adding new features, please:

1. **Run the app manually** — `streamlit run backend/app.py` and exercise the new code path.
2. **Verify edge cases**:
   - Empty DataFrames
   - Missing columns
   - Very large files (>100 MB)
   - Special characters in column names
   - Files with mixed data types
   - Excel files with multiple sheets
3. **Check auto-save** — Verify the draft is saved on every chart mutation and restored after a browser tab refresh.
4. **Check draft cleanup** — Verify drafts are cleared after a successful session save.
5. **Check the insight engine** — If you add a new chart runner, confirm that the insight engine produces at least one insight and does not crash on degenerate data.
6. **Check export** — Verify the HTML export is self-contained (no external CDN dependencies) and renders correctly in Chrome and Firefox.
7. **Check cross-platform** — If possible, test on both Ubuntu and Fedora.

---

## Debugging Guide

### Backend (Streamlit)

- Run with `streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1` to see live logs in the terminal.
- Use `st.write()` or `st.json()` to inspect `st.session_state` during development.
- The launcher writes backend logs to `~/.local/share/lytrize/streamlit.log` when launched from the desktop entry.
- Use `LYTRIZE_DB_PATH=/tmp/lytrize_test.db` to use a throwaway database for debugging.

### Desktop Launcher

- Launch from a terminal with `python desktop/gui.py` to see Qt debug output.
- Browser profiles are stored under `~/.local/share/lytrize/browser-profiles/`. Delete a profile to reset browser state.
- If the launcher hangs, check for a stale Streamlit process: `pkill -f streamlit` and restart.
- The launcher polls TCP port 8501 with a 30-second timeout. If Streamlit takes longer to start, increase `_POLL_MAX_TRIES` in `gui.py`.

### Database

- The SQLite database lives at `~/.local/share/lytrize/lytrize.db`. Inspect it with:
  ```bash
  sqlite3 ~/.local/share/lytrize/lytrize.db ".tables"
  sqlite3 ~/.local/share/lytrize/lytrize.db "SELECT * FROM sessions LIMIT 5;"
  ```
- Set `LYTRIZE_DB_PATH=/tmp/lytrize_test.db` to use a throwaway database.
- Drafts are stored in `draft_sessions`. If the app feels slow, verify that draft cleanup is happening after saves.
- The database uses WAL mode for concurrent read/write access.

### Common Pitfalls

- **Streamlit reruns are expensive** — Avoid heavy computation at module top-level; use `@st.cache_data` or `@st.cache_resource`.
- **Session state key collisions** — Always prefix keys (`_cfg_`, `auto_insights_`, `desc_`, `chart_meta_`).
- **Circular imports** — Keep chart runners in `modules/analysis/` and UI helpers in `modules/ui/`. Shared constants go in `charts.py` or `config.py`.
- **Plotly figure mutability** — Deep-copy figures before mutating them in export or display helpers.
- **Duplicate widget IDs** — When rendering the same widget in a loop, use unique keys derived from the loop variable.
- **Fragment scope** — `st.rerun()` inside an `@st.fragment` only reruns that fragment. Use `st.rerun(scope="app")` to rerun the entire app (e.g., when navigating pages from within a chart card).

---

## Code Style and Conventions

- **Python version:** 3.11+
- **Docstrings:** Use Google-style docstrings (`Args`, `Returns`, `Raises`).
- **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- **Streamlit session state keys:** Prefix keys to avoid collisions (`_cfg_{aid}_{key}`, `auto_insights_{uid}`, `desc_{uid}`, `chart_meta_{uid}`).
- **Error handling:** Catch and log errors; do not crash the UI. Use `try/except` around user-facing operations.
- **Performance:** Use `@st.cache_resource` for one-per-process assets and `@st.cache_data` for computed data. Avoid unnecessary disk I/O on reruns.
- **HTML escaping:** Use the `_h()` helper from `modules/export.py` when injecting user-controlled text into HTML strings.
- **Imports:** Use absolute imports (e.g., `from modules.database import init_db`). Local imports (inside functions) are acceptable for avoiding circular dependencies.
- **Line length:** 100 characters (soft limit).
- **Type hints:** Use type hints for function signatures. `Optional[T]`, `list[T]`, `dict[str, T]` are preferred over `Union` and `List`/`Dict`.

---

## Contributing Workflow

1. **Open an issue first** — Describe the bug or feature before opening a PR.
2. **Fork and clone** — Fork the repository and clone your fork.
3. **Create a branch** — `git checkout -b feature/my-feature`
4. **Make changes** — Follow the code style and conventions above.
5. **Update documentation** — If your change affects user-facing behavior, update `README.md`. If it affects the codebase architecture or development workflow, update `CONTRIBUTING.md`.
6. **Test manually** — Run the app and verify your changes work.
7. **Commit** — Write clear, descriptive commit messages. Reference the issue number (e.g., `Fix #123: ...`).
8. **Push and open a PR** — Push to your fork and open a pull request against `main`.
9. **PR description** — Include a summary of changes, testing steps, and any breaking changes.

### PR Guidelines

- Keep PRs focused — one change per PR.
- Update `README.md` and `CONTRIBUTING.md` if behavior changes.
- Ensure the app runs: `streamlit run backend/app.py`.
- Mention testing steps in the PR description.
- Code will be reviewed for correctness, performance, and style.

---

## Known Issues & Limitations

1. **No dedicated PNG download button** — Users must use browser DevTools to capture the exported HTML page as a PNG image. A Chrome extension is planned for this.
2. **Some CSS color values in the HTML export lack fallback values** when a theme key is missing. The `_merge_theme()` function provides defaults, but edge cases may still produce unstyled elements.
3. **Streamlit reruns trigger full-page refreshes**, which can be slow for larger datasets. Fragment isolation (`chart_card.py`) mitigates this for per-chart interactions, but page-level changes still trigger a full rerun.
4. **No automated test suite** — Testing is currently manual. Contributions adding tests are highly welcome.
5. **Excel files larger than 300 MB are not supported** — The Streamlit file uploader has a default size limit.
6. **Map plots require `pycountry`** — Geographic scatter and choropleth maps depend on the `pycountry` package for country/region name resolution.
7. **Light mode is partially implemented** — Dark mode is the primary theme. Light mode overrides exist in `css.py` but may have visual inconsistencies on some components.
8. **Session restore after reboot** — If the parquet snapshot is stored on tmpfs (`$XDG_RUNTIME_DIR`), it is lost across reboots. The user will be asked to re-upload the file.
9. **Firefox kiosk mode** — Firefox's `--kiosk` mode is the closest equivalent to Chromium's `--app=` mode, but it may still show a tab bar or address bar on some Firefox versions.

---

## License

MIT — see [LICENSE](./LICENSE) for the full text.