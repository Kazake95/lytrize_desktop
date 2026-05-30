# Contributing to Lytrize

Lytrize is a local-first Linux desktop analytics app built with Streamlit and PySide6. All user data stays on-device in a local SQLite database. There is no cloud backend, no remote API, and no telemetry.

This document covers the project architecture, development environment, contribution rules, and step-by-step guides for the most common extension tasks.

---

## Table of contents

1. [Architecture overview](#architecture-overview)
2. [Repository layout](#repository-layout)
3. [Quick start for developers](#quick-start-for-developers)
4. [Running without the desktop launcher](#running-without-the-desktop-launcher)
5. [Important files at a glance](#important-files-at-a-glance)
6. [Contribution rules](#contribution-rules)
7. [Performance guidelines](#performance-guidelines)
8. [How to add a page](#how-to-add-a-page)
9. [How to add an analysis type](#how-to-add-an-analysis-type)
10. [Database guidelines](#database-guidelines)
11. [HTML → PNG export](#html--png-export)
12. [Backup and restore](#backup-and-restore)
13. [Packaging](#packaging)
14. [Pull request checklist](#pull-request-checklist)

---

## Architecture overview

```
User clicks "lytrize"
        │
        ▼
/usr/local/bin/lytrize  (shell stub — exports Qt env vars, writes launch log)
        │
        ▼
desktop/launcher.py     (resolves venv Python, execs gui.py)
        │
        ▼
desktop/gui.py          (PySide6 window + system tray)
        │   spawns subprocess
        │   stdout/stderr → ~/.local/share/lytrize/streamlit.log
        ▼
streamlit run backend/app.py
        │   serves on 127.0.0.1:8501 (loopback only — never exposed externally)
        ▼
User's browser          (opened by gui.py in isolated app-mode window)
```

The PySide6 window is a thin launcher. It starts Streamlit as a child process, polls TCP port 8501 until Streamlit accepts connections, then opens the browser. All application logic lives in the Streamlit backend.

The Streamlit backend subprocess stdout and stderr are redirected to `~/.local/share/lytrize/streamlit.log` — they are never inherited by the terminal or left as a raw inherited pipe. This prevents OS pipe buffer stalls on high log volume and keeps the terminal clean.

Browser subprocesses launched by `_open_app()` redirect to `/dev/null` for the same reason.

### State layers

Session state is split across three layers:

| Layer | Lifetime | Contents |
|-------|----------|----------|
| `st.session_state` | Per WebSocket session (cleared on browser refresh) | Active DataFrame, current charts, UI widget values |
| SQLite (`~/.local/share/lytrize/lytrize.db`) | Persistent across restarts | Saved sessions, chart JSON, KPIs, dashboard metadata, draft auto-saves |
| Parquet snapshot (`$XDG_RUNTIME_DIR/lytrize/df_<user_id>.parquet`) | Until reboot (RAM-backed tmpfs) | The loaded DataFrame, restored on reconnect, gone after reboot |

The parquet snapshot is written by `save_df_snapshot()` on every autosave and read back by `load_df_snapshot()` at session restore time. Files larger than 512 MB are skipped on load to prevent OOM; the user is prompted to re-upload instead.

---

## Repository layout

```
lytrize_desktop/
├── backend/
│   ├── app.py                   Entry point — page routing and session bootstrap
│   ├── config.py                Shared runtime constants (APP_HOST, APP_PORT, …)
│   ├── .streamlit/
│   │   └── config.toml          Server config (port, theme, gatherUsageStats=false)
│   ├── assets/                  App icon (lytrize.ico/png) and welcome banner
│   └── modules/
│       ├── analysis/
│       │   ├── __init__.py      Analysis registry: ANALYSIS_OPTIONS card list,
│       │   │                    _RUNNERS dispatch table, render_config_panel(),
│       │   │                    render_config_panel_scoped(), _collect_kwargs(),
│       │   │                    _collect_kwargs_scoped(), _run()
│       │   ├── apply_lytrize_standard.py  Universal chart post-processor
│       │   ├── categorical.py
│       │   ├── correlation.py
│       │   ├── data_quality.py
│       │   ├── descriptive.py
│       │   ├── distribution.py
│       │   ├── insights.py      Auto-insight engine (all chart types)
│       │   ├── map_plot.py
│       │   ├── matrix_table.py
│       │   ├── outlier.py
│       │   ├── pie_chart.py
│       │   ├── scatter_plot.py
│       │   ├── statistical.py
│       │   └── time_series.py
│       ├── charts.py            PALETTES, chart_layout(), charts_to_json(),
│       │                        generate_chart_insights(), apply_hover_format()
│       ├── database.py          All SQLite I/O — schema, migrations, CRUD,
│       │                        auth, tokens, backup/restore
│       ├── export.py            HTML report generation (self-contained, offline)
│       ├── pages/
│       │   ├── analysis.py      Chart generation UI, config panels, chart list
│       │   ├── auth.py          Profile / backup-restore page
│       │   ├── dashboard.py     Dashboard view/edit, KPI engine, save, export
│       │   ├── home.py          Home page — session list, KPI overview, new analysis
│       │   └── upload.py        File upload, preview, column cleaning pipeline
│       ├── playwright_renderer.py  HTML → PNG via system browser (headless)
│       └── ui/
│           ├── chart_settings.py   Per-chart settings panel, typography controls,
│           │                       apply_chart_display_options()
│           ├── column_manager.py   Column rename / reorder UI
│           ├── column_tools.py     Type casting and column derivation
│           ├── css.py              Global CSS injection and logo helpers
│           ├── data_cleaner.py     Missing-value and outlier cleaning UI
│           ├── excel_loader.py     Sheet selector and Excel-specific loading
│           └── theme_tokens.py     Design tokens (colours, spacing)
│       └── utils/
│           ├── perf.py             Pure-data performance helpers — optimize_dtypes(),
│           │                       sample_for_plot(), enforce_render_limit(),
│           │                       cached_pivot(), read_csv_fast/chunked(),
│           │                       read_excel_sheet(), get_sheet_names()
│           └── session_cache.py    Parquet df snapshot: save_df_snapshot(),
│                                   load_df_snapshot(), df_cache_path()
├── desktop/
│   ├── gui.py                   PySide6 launcher window, browser detection,
│   │                            subprocess management, system tray
│   └── launcher.py              CLI entry point called by /usr/local/bin/lytrize
├── packaging/
│   ├── DEBIAN/
│   │   ├── control              Package metadata and runtime dependencies
│   │   ├── postinst             Post-install hook (venv re-link, icon cache)
│   │   └── postrm               Post-removal cleanup
│   ├── rpm/
│   │   └── lytrize.spec         RPM spec (mirrors DEBIAN/control + postinst/postrm)
│   └── usr/
│       ├── local/bin/lytrize    Shell stub (sets Qt env vars, writes launch log)
│       └── share/applications/lytrize.desktop  Desktop entry file
├── service/
│   └── lytrize.service          Optional systemd user service
├── requirements.txt             Python runtime dependencies
├── build.sh                     Debian package build script
└── build_rpm.sh                 RPM package build script
```

---

## Quick start for developers

```bash
# 1. Clone the repo
git clone <repo-url>
cd lytrize_desktop

# 2. Create and activate a virtual environment
python3.11 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
pip install PySide6

# 4. Launch the full desktop app (PySide6 window + Streamlit backend)
python desktop/gui.py
```

The first launch creates `~/.local/share/lytrize/lytrize.db` automatically. Backend logs go to `~/.local/share/lytrize/streamlit.log`.

> **Path discipline:** Never hard-code repo paths. Use `Path(__file__).resolve().parent` — the pattern used throughout the codebase — so paths stay correct regardless of where the repo is cloned or what prefix the package is installed to.

---

## Running without the desktop launcher

For working on backend logic with fast hot-reload and no PySide6 window:

```bash
cd backend
streamlit run app.py --server.port 8501
```

Open `http://localhost:8501` in your browser. The desktop launcher is not required for backend development.

---

## Important files at a glance

| File | What it owns |
|------|--------------|
| `backend/app.py` | Streamlit router, guest bootstrap, draft restore on startup |
| `backend/modules/database.py` | Every SQLite read and write — schema, migrations, CRUD, backup/restore, auth |
| `backend/modules/charts.py` | `PALETTES`, `chart_layout()`, `charts_to_json()`, `generate_chart_insights()`, `apply_hover_format()` |
| `backend/modules/analysis/__init__.py` | `ANALYSIS_OPTIONS` card registry, `_RUNNERS` dispatch table, config panel rendering and kwargs collection |
| `backend/modules/analysis/apply_lytrize_standard.py` | Post-processing applied to every Plotly figure after its runner builds it |
| `backend/modules/analysis/insights.py` | Auto-insight generation for all chart types |
| `backend/modules/pages/upload.py` | File ingestion (CSV + Excel), dtype detection, column cleaning pipeline |
| `backend/modules/pages/analysis.py` | Chart generation loop, config panels, chart list rendering, autosave |
| `backend/modules/pages/dashboard.py` | Dashboard renderer, KPI card engine, grid editor, save, HTML/PNG export |
| `backend/modules/playwright_renderer.py` | HTML → PNG via the system's installed browser (no Playwright dependency) |
| `backend/modules/ui/css.py` | All CSS injected into the Streamlit app |
| `backend/modules/utils/perf.py` | Pure-data helpers: dtype optimisation, plot sampling, chunked CSV reader, cached pivot |
| `backend/modules/utils/session_cache.py` | `save_df_snapshot()` / `load_df_snapshot()` — parquet persistence for the active DataFrame |
| `desktop/gui.py` | PySide6 launcher, browser detection and launch, subprocess lifecycle, system tray |

---

## Contribution rules

**Scope**
Keep pull requests small and focused. One feature or fix per PR. Reviewers should be able to understand the full change without context-switching.

**Code style**
- Format all Python with **Black** at default line length (88 characters).
- Use type hints on all new function signatures. The codebase requires Python 3.11+, so `X | None`, `list[str]`, and `tuple[str, bool]` syntax is fine.
- Docstrings must be the **first statement** in a module, class, or function body — Python only recognises a string literal as `__doc__` when it appears before any import or assignment.
- Keep imports ordered: standard library → third-party → local.

**No network calls in app code**
Lytrize is offline-first. Do not add any `requests`, `httpx`, `urllib`, or other outbound calls to backend code. The only permitted network activity is the Streamlit WebSocket on loopback (`127.0.0.1:8501`).

**SQLite boundary**
Do not open raw `sqlite3.connect()` calls outside `database.py`. All schema and CRUD logic belongs there. Other modules call the functions it exports. Connection management uses the `_db()` context manager, which commits on success and rolls back on any exception — do not open raw connections that bypass it.

**Subprocess output**
All `subprocess.Popen()` calls must redirect `stdout` and `stderr`. Use a log file for the Streamlit backend process, and `/dev/null` (or `subprocess.DEVNULL`) for browser child processes. Never leave inherited pipe handles — they flood the terminal and can stall the subprocess when the OS pipe buffer fills.

**Streamlit boundary in utils**
`modules/utils/perf.py` is a pure-data module. Do not add `import streamlit` at module level — it makes the module unimportable in scripts and tests that run without a Streamlit server. The `cached_pivot()` function handles this by decorating a module-level function at import time with a guarded try/except, keeping the decorator application outside any per-call code path.

**Verify imports before pushing**
```bash
python -c "import sys; sys.path.insert(0, 'backend'); import app"
```
This catches circular imports and missing dependencies without needing a running server.

---

## Performance guidelines

Streamlit reruns the entire script on every user interaction. The rules below prevent that from causing visible lag.

**Sample before plotting, not after**
`sample_for_plot()`, `enforce_render_limit()`, and `sample_for_histogram()` in `perf.py` must be called *before* building Plotly figures. A figure built from five million rows already has a large JSON payload — sampling the figure object afterwards has no effect on serialisation cost.

**`cached_pivot()` is a module-level cached function — do not redefine its inner function per call**
`_pivot_impl` is decorated once at import time. Wrapping `@st.cache_data` inside a function body would create a new cache bucket on every call, making the cache completely non-functional. The pattern in `perf.py` — hoist the implementation to module scope, decorate once, wrap in a named public function — is the correct approach for any similar cached helper.

**Cache pure transforms with `@st.cache_data`**
Add `@st.cache_data` to any function that takes a DataFrame and returns a new one, with a reasonable `ttl`. Call `.clear()` on the cached function after any write that would invalidate the cached result.

**Cache one-time binary loads with `@st.cache_resource`**
Images, fonts, and icons read from disk and base64-encoded should use `@st.cache_resource` so the encoding runs once per process, not once per Streamlit rerun. See `_banner_data_uri()` in `pages/home.py` for the canonical example.

**Chunked CSV reader for large files**
`read_csv_chunked()` in `perf.py` caps peak RAM to `chunksize × row_size` instead of `total_rows × row_size`. Use it when `mem_mb(df) > available_ram / 2`.

**`optimize_dtypes()` on every loaded DataFrame**
Downcasting integers and converting low-cardinality strings to `pd.Categorical` reduces memory 25–60% on typical files. Always run it immediately after loading, before storing the DataFrame in `session_state`. `read_csv_fast()` and `read_excel_sheet()` call it automatically.

**Chart figure caching in the analysis page**
Each chart card in `pages/analysis.py` computes a `_post_hash` from `compute_meta_hash(meta)` after the settings panel runs. It stores the rendered figure in `st.session_state[_cache_key]` and the hash in `st.session_state[_cache_meta_key]`. On the next rerun, if the hash matches the stored hash, the cached figure is reused — no Plotly rebuild. Always use `_post_hash` (not any other variable name) when writing to `_cache_meta_key`.

---

## How to add a page

1. Create `backend/modules/pages/<name>.py`.
2. Implement a top-level handler function:
   ```python
   def page_<name>() -> None:
       ...
   ```
   Follow the structure in `pages/home.py`. Use `st.session_state` for cross-page state; document every new key in a comment where it is first written.

3. Import and register the handler in `backend/app.py`:
   ```python
   from modules.pages.<name> import page_<name>

   # In main(), in the routing block:
   elif p == "<name>": page_<name>()
   ```

4. Navigate to the page from another page:
   ```python
   st.session_state.page = "<name>"
   st.rerun()
   ```

---

## How to add an analysis type

1. Create `backend/modules/analysis/<type>.py`. Implement a runner with this signature:
   ```python
   def run_<type>(df: pd.DataFrame, **kwargs) -> list[tuple[str, go.Figure]]:
       """Return a list of (title, fig) tuples."""
       ...
   ```

2. Call `apply_lytrize_standard(fig, ...)` on every figure before returning it. This applies the standard Lytrize theme, sets `fig._lytrize_meta`, and strips noisy hover extras. See `apply_lytrize_standard.py` for full parameter docs.

3. Register the card and runner in `modules/analysis/__init__.py`:
   ```python
   # ANALYSIS_OPTIONS — drives the card grid on the analysis page
   {"id": "<type>", "icon": "🔣", "name": "Display Name", "desc": "One-line description"},

   # _RUNNERS — dispatch table
   "<type>": run_<type>,
   ```

4. If the analysis needs column-selector widgets, add a branch for `aid == "<type>"` in both `render_config_panel()` and `render_config_panel_scoped()`. Add a corresponding branch in `_collect_kwargs()` and `_collect_kwargs_scoped()` to translate widget values into runner kwargs.

5. Optionally add auto-insights: implement `_insights_<type>(fig) -> list[str]` in `modules/analysis/insights.py` and register it in `_FN_MAP` at the bottom of that file.

No changes to `pages/analysis.py` are needed — it reads `ANALYSIS_OPTIONS` and `_RUNNERS` automatically.

---

## Database guidelines

All schema logic lives in `backend/modules/database.py`.

**Always use the `_db()` context manager for writes**
```python
with _db() as conn:
    _execute(conn, "INSERT INTO ...", params)
# commits on clean exit, rolls back on any exception, always closes the connection
```

For read-only queries that don't need a transaction, open a raw connection and wrap it in `try/finally`:
```python
conn = _connect()
try:
    result = _execute_fetchone(conn, "SELECT ...", params)
finally:
    conn.close()
```

Never open a raw connection without a `try/finally`. A connection that leaks on exception holds a file lock and can block subsequent writes.

**Migrations must be safe for existing installs**
Add new columns with `ALTER TABLE … ADD COLUMN …` in a `try/except`, so users with existing databases get a silent no-op rather than a crash:
```python
try:
    c.execute("ALTER TABLE sessions ADD COLUMN my_col TEXT DEFAULT ''")
except Exception:
    pass  # column already exists
```

Use `_column_exists(conn, table, column)` before any `ALTER TABLE` to make migrations idempotent.

**Never rename or drop columns**
Old installed versions may still reference removed columns. Add new columns; deprecate old ones silently.

**Index columns used in WHERE or ORDER BY**
Use `_ensure_index()` for any column queried on startup. Missing indices on a large sessions table cause noticeable home-page load times.

**No raw connections outside this file**
Other modules must call exported functions, never open their own `sqlite3.connect()` calls.

---

## HTML → PNG export

The export flow in `pages/dashboard.py`:

1. `generate_html_report()` from `modules/export.py` produces a self-contained HTML file — all Plotly JS inlined, no external resources, opens in any browser offline.
2. The user downloads the HTML with the **Export HTML** button.
3. Optionally, they re-upload it to the **Render PNG** form, which calls `render_html_to_png()` from `modules/playwright_renderer.py`.

`playwright_renderer.py` does **not** use Playwright or any downloaded browser binary. It finds the user's installed browser with `shutil.which()` and calls it via `subprocess.run()` in headless mode:

- **Chromium-based** (Chrome, Chromium, Brave, Edge): `--headless=new --screenshot=<file> <url>`
- **Firefox / Firefox ESR**: `--headless --screenshot <file> <url>`

The function raises a `RuntimeError` with a clear message and the `apt install` command if no supported browser is found. Nothing to install for this feature beyond a browser.

When working on the export flow, test with both a Chromium-based browser and Firefox to verify output is correct for each rendering path.

---

## Backup and restore

**Export** (`export_sessions_to_dict()`) produces a JSON payload per session containing:
- Chart Plotly figure JSON, uid, type, title, notes, and metadata
- Dashboard title, KPIs, and layout mode
- Grid order and full-width state per chart
- Session UUID and timestamps

**Import** (`import_sessions_from_dict()`) uses last-write-wins: if an imported session's `updated_at` is newer than the local copy, the local row is overwritten. If the local copy is newer, the import is skipped and the session is added to the `skipped` list returned to the caller.

**`sanitize_restored_session()`** normalises every imported row before it is written:
- Rebinds the row to the current local `user_id`
- Strips cloud-only transport fields (`device_id`, `remote_uuid`, `deleted_at`, etc.)
- Preserves `session_uuid` for deduplication; generates a new one if absent

If you add new fields to sessions or charts, include them in the `export_sessions_to_dict()` query and in the `_insert_row()` INSERT inside `import_sessions_from_dict()`, and pass them through `sanitize_restored_session()`.

---

## Packaging

### Debian / Ubuntu

```bash
bash build.sh
sudo dpkg -i build/lytrize_1.2_amd64.deb
# If deps missing:
sudo apt-get install -f
lytrize
```

`build.sh` runs 7 steps:
1. Clean the previous build directory
2. Copy backend and desktop source files (strips `__pycache__` and editor temp files)
3. Create a Python venv at `build/lytrize_<version>_amd64/opt/lytrize/venv`
4. Install all Python dependencies into the venv
5. Patch venv shebangs for portability (`/opt/lytrize/venv/bin/python3`)
6. Slim the venv (removes `__pycache__`, test dirs, `.pyc` files)
7. Bake icon files at all standard sizes, then call `dpkg-deb`

**Packaging rules:**
- The installed venv lives at `/opt/lytrize/venv`. Never reference `.venv` or any other path in packaging code.
- `desktop/gui.py` checks `BASE / "venv" / "bin" / "python"` at runtime as the primary interpreter.
- `postinst` re-links the bundled venv by updating symlinks and `pyvenv.cfg` — no `ensurepip`, no network access required at install time. It handles Python minor-version mismatches by symlinking `lib/python<target>` → `lib/python<build>`.
- `postinst` does **not** use `set -e`. Each optional step (icon cache, symlinks) fails gracefully so one broken step cannot abort the entire install.
- The shell stub exports `QT_PLUGIN_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH`, and `LD_LIBRARY_PATH` so PySide6 finds its bundled Qt platform plugins without requiring system Qt packages. It writes launch errors to `/tmp/lytrize-launch.log`.
- Runtime system dependencies: `python3 (>= 3.11)`, `libgl1`, `libegl1`, `libglib2.0-0`, `libxcb-cursor0`, `libdbus-1-3`. If you add PySide6 features requiring additional Qt modules, add the corresponding system library to `Depends` in `packaging/DEBIAN/control`.

### RPM (Fedora / RHEL / openSUSE)

```bash
# Requires: sudo dnf install rpm-build
bash build_rpm.sh
sudo dnf install build/lytrize-1.2-1.x86_64.rpm
```

The spec file is at `packaging/rpm/lytrize.spec`. It mirrors `DEBIAN/control` for metadata, `postinst` for `%post`, and `postrm` for `%postun`. When changing either Debian or RPM packaging files, update both.

---

## Pull request checklist

- [ ] PR scope is one feature or one fix
- [ ] New functions have type hints and a docstring as the **first** statement in the body
- [ ] No `import streamlit` at module level in `modules/utils/perf.py`
- [ ] `@st.cache_resource` used for any new image or binary asset encoding
- [ ] `@st.cache_data` inner function defined at **module level**, not inside a calling function
- [ ] Plotly figures sample data **before** building the figure, not after
- [ ] All `subprocess.Popen()` calls redirect `stdout` and `stderr` (log file or `/dev/null`)
- [ ] Any new SQLite column added with `ALTER TABLE … ADD COLUMN …` in a `try/except`
- [ ] All DB writes go through `_db()` context manager; read-only connections use `try/finally`
- [ ] New session or chart fields included in `export_sessions_to_dict()`, `_insert_row()`, and `sanitize_restored_session()`
- [ ] No outbound network calls added to backend code
- [ ] `python -c "import sys; sys.path.insert(0, 'backend'); import app"` exits cleanly
- [ ] `bash build.sh` completes without errors
- [ ] If new PySide6/Qt features added, required system library added to `Depends` in `DEBIAN/control` **and** `Requires` in `packaging/rpm/lytrize.spec`
- [ ] This document updated if the workflow, architecture, or file layout changed
