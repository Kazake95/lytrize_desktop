# Lytrize Desktop — Codebase Documentation

**Source reviewed:** `Archive(12).zip`  
**Scope:** static inspection of the repository structure and Python source files.  
**Note:** I did not execute the app. This document describes what is present in the archive.

---

## 1) What this project is

Lytrize Desktop is a **local-first Linux analytics application**. It uses:

- a **Streamlit backend** for the web UI and analytics workflow
- a **PySide6 desktop launcher** to start the backend and open the UI in an isolated browser window
- a **local SQLite database** for sessions, drafts, users, tokens, and backups
- **Plotly** for interactive charts
- **Pandas / OpenPyXL** for dataset loading and transformation

The app is intended to stay offline and keep data on the local machine.

---

## 2) Top-level repository layout

### Root files
- `README.md` — product overview, install/build instructions, chart types, storage locations, and troubleshooting.
- `requirements.txt` — Python dependencies for the backend and launcher.
- `build.sh` — Debian package builder.
- `build_rpm.sh` — RPM package builder.
- `LICENSE` — MIT license.
- `CONTRIBUTING.md` — development guidance.
- `service/lytrize.service` — systemd user service for running Streamlit.
- `packaging/` — Debian/RPM package metadata and launcher wrappers.

### Main runtime directories
- `backend/` — Streamlit app, analysis engine, UI components, database layer, assets.
- `desktop/` — native launcher entry point and Qt GUI.

---

## 3) Runtime architecture

### Startup flow
1. The packaged launcher runs `desktop/launcher.py`.
2. `desktop/launcher.py` resolves the bundled Python interpreter and starts `desktop/gui.py`.
3. `desktop/gui.py` starts the Streamlit backend from `backend/app.py`.
4. `backend/app.py` initializes the local database and Streamlit page routing.
5. The app resolves the user as a guest user if no authenticated user exists yet.
6. The frontend page flow is driven by `st.session_state.page` and query parameters.

### Core app pages
- `home` — landing page and session browser
- `upload` — file upload, preview, cleanup, and data quality entry point
- `analysis` — chart selection and chart generation
- `dashboard` — chart arrangement, KPI cards, editing, and export
- `profile/auth` — backup and restore experience

---

## 4) Important files and responsibilities

### `backend/app.py`
Main Streamlit entry point.

Responsibilities:
- sets the Streamlit page config
- initializes the SQLite database once per process
- injects the global CSS theme
- creates or restores the current user context
- restores any saved draft/session state into `st.session_state`
- routes between pages using the `page` session key and query parameters

Important helpers:
- `_init_db_once()`
- `_restore_draft(user_id)`
- `main()`

### `backend/modules/database.py`
All database operations live here.

Responsibilities:
- SQLite connection setup and pragmas
- auth / guest user handling
- token creation and validation
- session save/load/update/delete
- draft persistence
- backup import/export helpers
- activity logging
- simple login rate limiting

This is the most important file for issue reports involving:
- login/auth problems
- saved sessions not appearing
- restore/backup failures
- corrupt or missing database records
- token/session persistence issues

### `backend/modules/utils/session_cache.py`
Session-state and dataset snapshot helpers.

Responsibilities:
- `set_df()` and `update_df()` are the canonical way to replace the current DataFrame
- bumps `_df_version` so cached widgets refresh correctly
- clears stale preview / transform / quality cache keys
- saves and loads parquet snapshots for the active DataFrame
- lightweight memoization via `session_cached()`

This file is central when debugging:
- stale previews
- widgets not updating after edits
- reload/refresh recovery issues
- dataframe snapshot restoration problems

### `backend/modules/utils/perf.py`
Performance helpers for large datasets.

Responsibilities:
- DataFrame memory reporting
- dtype optimization
- CSV reading with chunked fallback for large files
- sampling helpers for charts
- Excel sheet helpers
- cached pivot utilities

This file matters for:
- large CSV performance
- memory usage regressions
- chart sampling issues
- Excel ingestion speed

### `backend/modules/charts.py`
Shared chart utilities and chart JSON helpers.

Responsibilities:
- chart serialization
- figure layout helpers
- hover formatting
- column-type helpers
- auto-insight text cleaning
- shared Plotly utilities used across analysis and dashboard views

### `backend/modules/analysis/__init__.py`
Analysis registry and configuration layer.

Responsibilities:
- defines `ANALYSIS_OPTIONS`
- defines chart capability metadata
- handles widget state collection
- handles scoped analysis configuration
- connects chart-type UI with the underlying runner functions

This is the dispatch layer for chart generation.

### `backend/modules/analysis/*.py`
Each file contains the renderer for one analysis type:

- `descriptive.py` — summary statistics table
- `statistical.py` — grouped numeric aggregates
- `distribution.py` — histograms and boxplots
- `correlation.py` — Pearson correlation heatmap
- `categorical.py` — categorical bar charts
- `pie_chart.py` — pie / donut charts
- `time_series.py` — time-based trend charts
- `scatter_plot.py` — scatter plots and trendlines
- `matrix_table.py` — pivot heatmap and pivot table
- `map_plot.py` — geographic charts
- `outlier.py` — IQR-based outlier detection
- `data_quality.py` — missing values, duplicates, and quality diagnostics
- `insights.py` — auto-insight text generation
- `apply_lytrize_standard.py` — common standardization pass for chart styling

### `backend/modules/ui/*.py`
Reusable Streamlit UI components.

Key responsibilities:
- `css.py` — global CSS, theme variables, footer, logo rendering, logout handling
- `chart_card.py` — isolated per-chart fragment rendering and display-figure caching
- `chart_settings.py` — chart controls, typography controls, display meta handling, font stack resolution
- `font_manager.py` — bundled font registry and preview helpers
- `data_cleaner.py` — text cleanup, find/replace, validation, string/numeric ops
- `column_manager.py` — add/remove/rename columns and safe derived-column formulas
- `column_tools.py` — dtype transformation and column classification
- `excel_loader.py` — multi-sheet Excel browser and workbook merge/join workflow

### `backend/modules/pages/*.py`
Page-level Streamlit screens.

- `home.py` — landing page, KPI summary, previous sessions list, new analysis entry point
- `upload.py` — file uploader, preview, Excel sheet selection, data quality entry point
- `analysis.py` — analysis selection, chart generation, autosave, regeneration, notes sync
- `dashboard.py` — dashboard editing, layout management, KPI builder, export
- `auth.py` — backup and restore page

### `desktop/gui.py`
PySide6 launcher window.

Responsibilities:
- finds installed browsers
- launches Streamlit in the bundled environment
- opens the app in Chromium app mode or Firefox kiosk-like mode
- stores launcher preferences
- provides tray integration and crash recovery

This file is the main place to inspect for:
- browser-launch problems
- app failing to open after backend startup
- launcher preference persistence issues
- desktop packaging problems

### `desktop/launcher.py`
Small CLI shim used by the installed `lytrize` command.

Responsibilities:
- resolves the installed Python runtime
- runs `desktop/gui.py`
- forwards CLI arguments

### Packaging / deployment
- `packaging/deb/DEBIAN/control` defines Debian package metadata and dependencies.
- `packaging/rpm/lytrize.spec` defines the RPM spec.
- `service/lytrize.service` runs Streamlit as a systemd user service.
- `build.sh` and `build_rpm.sh` assemble the packages and vendor a virtual environment into `/opt/lytrize/venv/`.

---

## 5) Data model and storage

### Local storage locations
From the code and README, the app uses:

- `~/.local/share/lytrize/lytrize.db` — main SQLite database
- `~/.local/share/lytrize/launcher_prefs.json` — launcher preferences
- `~/.local/share/lytrize/browser-profiles/` — isolated browser profiles
- session parquet snapshots in the user runtime/cache area via `session_cache.py`

### What is persisted
- users and guest identity
- tokens
- saved sessions
- dashboard charts and chart metadata
- drafts
- column descriptions
- layout mode and KPI settings
- backup/restore payloads

### Backup behavior
The profile page exports/imports a JSON backup containing selected sessions and metadata. It does **not** include the original CSV/Excel source files.

---

## 6) Chart types exposed by the app

The registry in `backend/modules/analysis/__init__.py` exposes these analysis types:

- Descriptive
- Statistical
- Distribution
- Correlation
- Categorical Bar
- Pie & Donut
- Time Series
- Scatter Plot
- Matrix Heatmap
- Pivot Table
- Map Plot

The README also describes:
- outlier detection
- data quality diagnostics

---

## 7) How the workflow is structured

### Upload
`page_upload()` handles:
- CSV or Excel upload
- Excel sheet selection / joining
- preview table
- optional column descriptions
- data quality checks
- outlier run entry point
- session snapshot save

### Analysis
`page_analysis()` handles:
- choosing an analysis type
- building chart parameters
- generating the chart
- storing chart metadata
- syncing notes and autosaving draft/session state
- regenerating charts with preserved settings

### Dashboard
`page_dashboard()` handles:
- arranging generated charts
- editing titles, layout, and typography
- KPI cards
- persistent dashboard state
- HTML export generation

### Home
`page_home()` handles:
- new analysis start
- session browsing
- view/edit actions for past sessions

### Profile
`page_profile()` handles:
- exporting local session backups
- importing backup JSON files
- returning to home

---

## 8) Notable implementation patterns

### State management
The app relies heavily on `st.session_state` to keep:
- user identity
- loaded DataFrame
- current page
- chart list
- chart metadata
- edit mode state
- notes and KPI state

### Cache invalidation
The code uses explicit versioning and cache keys:
- `_df_version`
- preview cache keys
- chart display figure hashes
- meta hashes

This is important because stale Streamlit state is a likely source of bugs.

### Security / validation patterns
There are several defensive measures:
- safe formula evaluation for derived columns
- login rate limiting
- token validation
- JSON-safe serialization helpers
- local-only database path handling

---

## 9) Build and packaging notes

### Debian
- Build script: `build.sh`
- Package metadata: `packaging/deb/DEBIAN/control`
- Installs to `/opt/lytrize`
- Bundles a venv
- Installs a desktop launcher entry and icon assets

### RPM
- Build script: `build_rpm.sh`
- Spec file: `packaging/rpm/lytrize.spec`
- Uses a staging directory and rpmbuild

### Service
`service/lytrize.service` runs:
- `streamlit run /opt/lytrize/backend/app.py`
- bound to `127.0.0.1:8501`
- with the database path pointed to the user’s home directory

---

## 10) What to mention when reporting issues

Use this exact structure for future bug reports:

1. **Page** — home / upload / analysis / dashboard / profile
2. **Dataset type** — CSV or Excel, row count, column count, approximate size
3. **What changed last** — upload, dtype conversion, chart generation, edit chart, save session, restore backup, export HTML
4. **Expected result**
5. **Actual result**
6. **Relevant file or module** — for example:
   - upload problems → `backend/modules/pages/upload.py`
   - chart generation → `backend/modules/pages/analysis.py` and `backend/modules/analysis/*`
   - dashboard / export → `backend/modules/pages/dashboard.py` and `backend/modules/export.py`
   - persistence / auth → `backend/modules/database.py`
   - stale UI / refresh issues → `backend/modules/utils/session_cache.py`
   - launcher issues → `desktop/gui.py`
7. **Any error text / traceback**
8. **Whether the issue survives restart**

---

## 11) Gaps in the archive

I did **not** find a `tests/` directory in the archive, so there is no visible automated test suite in this snapshot.

---

## 12) Compact mental model

If you need the shortest possible view of the codebase:

- `desktop/` starts the app
- `backend/app.py` routes the Streamlit pages
- `backend/modules/database.py` persists everything
- `backend/modules/pages/*` implement user workflows
- `backend/modules/analysis/*` generate charts and insights
- `backend/modules/ui/*` controls the widgets and styling
- `backend/modules/export.py` turns dashboards into standalone HTML
- `backend/modules/utils/*` handles performance and cached session state
