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
/usr/local/bin/lytrize  (shell stub)
        │
        ▼
desktop/launcher.py     (resolves venv Python, execs gui.py)
        │
        ▼
desktop/gui.py          (PySide6 window + system tray)
        │   spawns subprocess
        ▼
streamlit run backend/app.py
        │   serves on 127.0.0.1:8501 (loopback only)
        ▼
User's browser          (opened automatically by gui.py in app mode)
```

The PySide6 window is a thin launcher. It starts Streamlit as a child process, polls the port until Streamlit is ready, then opens the browser. All application logic lives in the Streamlit backend.

Session state is split across two layers:
- **`st.session_state`** — in-memory, per-WebSocket-session. Cleared on browser refresh.
- **SQLite (`~/.local/share/lytrize/lytrize.db`)** — persistent across restarts. Charts, dashboards, KPIs, and draft sessions are saved here on every autosave.
- **Parquet snapshot (`$XDG_RUNTIME_DIR/lytrize/df_<user_id>.parquet`)** — the loaded DataFrame is too large for SQLite; it lives in a tmpfs file that is restored on reconnect and cleared on reboot.

---

## Repository layout

```
lytrize_desktop/
├── backend/
│   ├── app.py                   Entry point — page routing and session bootstrap
│   ├── config.py                Shared runtime constants (APP_HOST, APP_PORT, …)
│   ├── .streamlit/
│   │   └── config.toml          Server config (port, theme, no usage stats)
│   ├── assets/                  App icon and welcome banner
│   └── modules/
│       ├── analysis/
│       │   ├── __init__.py      Analysis registry (ANALYSIS_OPTIONS, _RUNNERS,
│       │   │                    render_config_panel, _collect_kwargs)
│       │   ├── apply_lytrize_standard.py  Universal chart post-processor
│       │   ├── categorical.py
│       │   ├── correlation.py
│       │   ├── data_quality.py
│       │   ├── descriptive.py
│       │   ├── distribution.py
│       │   ├── insights.py      Auto-insight engine for all chart types
│       │   ├── map_plot.py
│       │   ├── matrix_table.py
│       │   ├── outlier.py
│       │   ├── pie_chart.py
│       │   ├── scatter_plot.py
│       │   ├── statistical.py
│       │   └── time_series.py
│       ├── charts.py            Palettes, chart_layout(), charts_to_json()
│       ├── database.py          All SQLite I/O — schema, CRUD, backup/restore
│       ├── export.py            HTML report generation
│       ├── pages/
│       │   ├── analysis.py      Chart generation UI and config panels
│       │   ├── auth.py          Profile / account page
│       │   ├── dashboard.py     Dashboard view/edit, KPI engine, export
│       │   ├── home.py          Home page — session list, recent activity
│       │   └── upload.py        File upload, preview, cleaning pipeline
│       ├── playwright_renderer.py  HTML → PNG via system browser (headless)
│       └── ui/
│           ├── chart_settings.py   Per-chart settings panel and typography
│           ├── column_manager.py   Column rename / reorder UI
│           ├── column_tools.py     Type casting and column derivation
│           ├── css.py              Global CSS injection and logo helpers
│           ├── data_cleaner.py     Missing-value and outlier cleaning UI
│           ├── excel_loader.py     Sheet selector and Excel-specific loading
│           └── theme_tokens.py     Design tokens (colours, spacing)
│       └── utils/
│           ├── perf.py             Pure-data performance helpers (no Streamlit)
│           └── session_cache.py    Parquet df snapshot for cross-tab persistence
├── desktop/
│   ├── gui.py                   PySide6 launcher window, browser detection, tray
│   └── launcher.py              CLI entry point called by /usr/local/bin/lytrize
├── packaging/
│   ├── DEBIAN/
│   │   ├── control              Package metadata and dependencies
│   │   ├── postinst             Post-install hook (Python re-link, icon cache, permissions)
│   │   └── postrm               Post-removal cleanup
│   └── usr/
│       ├── local/bin/lytrize    Shell stub
│       └── share/applications/lytrize.desktop  Desktop entry
├── service/
│   └── lytrize.service          Optional systemd user service
├── requirements.txt             Python runtime dependencies
└── build.sh                     Debian package build script
```

---

## Quick start for developers

```bash
# 1. Clone the repo
git clone <repo-url>
cd lytrize_desktop

# 2. Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# 3. Install Python dependencies
pip install -r requirements.txt
pip install PySide6

# 4. Launch the full desktop app (PySide6 window + Streamlit backend)
python desktop/gui.py
```

The first launch creates `~/.local/share/lytrize/lytrize.db` automatically.

> **Do not** hard-code the repo path anywhere. Use `Path(__file__).resolve().parent` — the pattern used throughout the codebase — so paths remain correct regardless of where the repo is cloned.

---

## Running without the desktop launcher

If you are working on backend logic and want fast reload without the PySide6 window:

```bash
cd backend
streamlit run app.py --server.port 8501
```

Open `http://localhost:8501` in your browser. Hot-reloading works normally. The desktop launcher is not required for backend development.

---

## Important files at a glance

| File | What it owns |
|------|--------------|
| `backend/app.py` | Streamlit router, guest bootstrap, draft restore on startup |
| `backend/modules/database.py` | Every SQLite read and write — schema, migrations, CRUD, backup/restore |
| `backend/modules/charts.py` | `PALETTES`, `chart_layout()`, `charts_to_json()`, `generate_chart_insights()` |
| `backend/modules/analysis/__init__.py` | `ANALYSIS_OPTIONS` card registry, `_RUNNERS` dispatch table, config panel rendering |
| `backend/modules/analysis/apply_lytrize_standard.py` | Post-processing applied to every chart figure after the runner builds it |
| `backend/modules/analysis/insights.py` | Auto-insight generation for all chart types |
| `backend/modules/pages/upload.py` | File ingestion, type detection, column cleaning |
| `backend/modules/pages/analysis.py` | Chart generation loop, config panels, chart list management |
| `backend/modules/pages/dashboard.py` | Dashboard renderer, KPI cards, grid editor, HTML/PNG export |
| `backend/modules/playwright_renderer.py` | HTML → PNG using the system's installed browser (headless mode) |
| `backend/modules/ui/css.py` | All CSS injected into the Streamlit app |
| `backend/modules/utils/perf.py` | Pure-data helpers: `optimize_dtypes`, `sample_for_plot`, chunked CSV reader |
| `backend/modules/utils/session_cache.py` | `save_df_snapshot` / `load_df_snapshot` — parquet persistence for the loaded DataFrame |
| `desktop/gui.py` | PySide6 launcher, all browser detection and launch logic, system tray |

---

## Contribution rules

**Scope**
Keep pull requests small and focused. One feature or fix per PR. Reviewers should be able to understand the full change without context-switching.

**Code style**
- Format all Python with **Black** at default line length (88 characters).
- Use type hints on all new function signatures.
- Docstrings must be the **first statement** in a module, class, or function body — Python only recognises a string literal as `__doc__` when it appears before any import or assignment.
- Keep imports ordered: standard library → third-party → local.

**No network calls in app code**
Lytrize is offline-first. Do not add any `requests`, `httpx`, `urllib`, or other outbound calls to backend code. The only permitted network activity is the Streamlit WebSocket connection on loopback (`127.0.0.1`).

**SQLite boundary**
Do not open raw SQLite connections outside `database.py`. All schema and CRUD logic belongs there. Other modules call the functions it exports.

**Streamlit boundary in utils**
`modules/utils/perf.py` is a pure-data module. Do not add `import streamlit` at module level — it makes the module unimportable in scripts and tests that run without a Streamlit server. If a specific function in that file needs `@st.cache_data`, import `streamlit` locally inside the function body (see the existing `cached_pivot()` for the pattern).

**Verify imports before pushing**
```bash
python -c "import sys; sys.path.insert(0, 'backend'); import app"
```
This catches circular imports and missing dependencies without needing a running server.

---

## Performance guidelines

Streamlit reruns the entire script on every user interaction. The rules below prevent that from causing visible lag.

**Sample before plotting, not after**
The helpers `sample_for_plot()`, `enforce_render_limit()`, and `sample_for_histogram()` in `perf.py` must be called *before* building Plotly figures. A figure built from five million rows already has a large JSON payload — sampling the figure object has no effect on serialisation cost.

**Cache pure transforms with `@st.cache_data`**
Add `@st.cache_data` to any function that takes a DataFrame and returns a new one, with a reasonable `ttl`. Call `.clear()` on the cached function after any write that would invalidate the cached result.

**Cache one-time binary loads with `@st.cache_resource`**
Images, fonts, and icons read from disk and base64-encoded should use `@st.cache_resource` so the encoding runs once per process, not once per Streamlit rerun. See `_banner_data_uri()` in `pages/home.py` for the canonical example.

**Chunked CSV reader for large files**
`read_csv_chunked()` in `perf.py` caps peak RAM to `chunksize × row_size` instead of `total_rows × row_size`. Use it when `mem_mb(df) > available_ram / 2`.

**`optimize_dtypes()` on every loaded DataFrame**
Downcasting integers and converting low-cardinality strings to `pd.Categorical` reduces memory 25–60 % on typical files. Always run it immediately after loading, before storing the DataFrame in `session_state`.

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

4. Navigate to the page from another page by setting:
   ```python
   st.session_state.page = "<name>"
   st.rerun()
   ```

---

## How to add an analysis type

1. Create `backend/modules/analysis/<type>.py`.
   Implement a runner with this signature:
   ```python
   def run_<type>(df: pd.DataFrame, **kwargs) -> list[tuple[str, go.Figure]]:
       """Return a list of (title, fig) tuples."""
       ...
   ```

2. Call `apply_lytrize_standard(fig, ...)` on every figure before returning it. This applies the standard Lytrize theme, sets `fig._lytrize_meta`, and strips noisy hover extras. See `apply_lytrize_standard.py` for full parameter docs.

3. Register the card in `modules/analysis/__init__.py`:
   ```python
   # ANALYSIS_OPTIONS — drives the card grid
   {"id": "<type>", "icon": "🔣", "name": "Display Name", "desc": "One-line description"},
   
   # _RUNNERS — dispatch table
   "<type>": run_<type>,
   ```

4. If the analysis needs column-selector widgets, add a branch in `render_config_panel()` and `render_config_panel_scoped()` in the same file.

5. Optionally add auto-insights: implement `_insights_<type>(fig) -> list[str]` in `modules/analysis/insights.py` and register it in `_FN_MAP` at the bottom of that file.

No changes to `pages/analysis.py` are needed. It reads `ANALYSIS_OPTIONS` and `_RUNNERS` automatically.

---

## Database guidelines

All schema logic lives in `backend/modules/database.py`.

**Migrations must be safe for existing installs**
Add new columns with `ALTER TABLE … ADD COLUMN …` wrapped in `try/except`, so users who already have the database do not get an error on upgrade:
```python
try:
    conn.execute("ALTER TABLE sessions ADD COLUMN my_col TEXT DEFAULT ''")
except Exception:
    pass  # Column already exists — no-op
```

Use `_column_exists(conn, table, column)` before any `ALTER TABLE` to make migrations idempotent.

**Never rename or drop columns**
Old installed versions may still reference removed columns. Add new columns; deprecate old ones silently.

**Index columns used in WHERE or ORDER BY on every page load**
Use `_ensure_index()` for any column queried on startup. Missing indices on a large sessions table cause noticeable load times.

**No raw connections outside this file**
Other modules must call exported functions, not open their own `sqlite3.connect(...)` calls.

---

## HTML → PNG export

The export flow in `pages/dashboard.py`:

1. `generate_html_report()` from `modules/export.py` produces a self-contained HTML file (all Plotly JS inlined, no external resources).
2. The user downloads the HTML with the **Export HTML** button.
3. Optionally, they re-upload it to the **Render PNG** form, which calls `render_html_to_png()` from `modules/playwright_renderer.py`.

`playwright_renderer.py` does **not** use Playwright or any downloaded browser binary. It detects the user's installed browser with `shutil.which()` and calls it via `subprocess` in headless mode:

- **Chromium-based** (Chrome, Chromium, Brave, Edge): `--headless=new --screenshot=<file> <url>`
- **Firefox / Firefox ESR**: `--headless --screenshot <file> <url>`

There is nothing to install for this feature. It works with any browser the user already has. If no supported browser is found, a clear error message is shown with the `apt install` command to fix it.

When working on the export flow, test with both a Chromium-based browser and Firefox to verify the output is correct for each rendering path.

---

## Backup and restore

Backup produces a JSON payload containing:
- Chart Plotly figure JSON, uid, type, title, notes, and metadata
- Dashboard title, KPIs, and layout mode
- Grid order and full-width state per chart
- Session UUIDs and timestamps

**`sanitize_restored_session()` in `database.py`** normalises every imported row before it is written:
- Rebinds the row to the current local `user_id`
- Strips any cloud-only transport fields (`device_id`, `remote_uuid`, etc.)
- Preserves `session_uuid` so `import_sessions_from_dict()` can deduplicate

Restore uses last-write-wins: if an imported session's `updated_at` is newer than the local copy, the local row is overwritten. If the local copy is newer, the import is skipped.

If you add new fields to sessions or charts, add them to `sanitize_restored_session()` and ensure they are included in the backup payload.

---

## Packaging

Build the Debian package:

```bash
bash build.sh
```

This runs 7 steps:
1. Clean the previous build directory
2. Copy backend and desktop source files (strips `__pycache__` and editor copy files)
3. Create a Python virtual environment at `build/lytrize_<version>_amd64/opt/lytrize/venv`
4. Install all Python dependencies into the venv
5. Patch venv shebangs for portability (absolute paths → `/opt/lytrize/venv/bin/python3`)
6. Slim the venv (remove `__pycache__`, test directories, `.pyc` files)
7. Bake icon files into `usr/share/pixmaps/` and `usr/share/icons/hicolor/` at all standard sizes, then call `dpkg-deb` to produce `build/lytrize_<version>_amd64.deb`

Install and test the built package:

```bash
sudo dpkg -i build/lytrize_1.2_amd64.deb
# If dpkg reports missing deps:
sudo apt-get install -f
lytrize
```

**Packaging rules:**
- The installed venv lives at `/opt/lytrize/venv`. Do not reference `my_venv` or `.venv` in packaging code.
- `desktop/gui.py` checks `BASE / "venv" / "bin" / "python"` at runtime as the primary interpreter path.
- `postinst` re-links the bundled venv by updating Python symlinks and `pyvenv.cfg` directly — no `ensurepip`, no network access, no `python3-venv` invocation required at runtime. It also handles Python minor-version mismatches by symlinking `lib/python<target>` → `lib/python<build>`.
- Icons are baked into the `.deb` by `build.sh` at build time (not solely by `postinst`), so the app icon is always present even if postinst cache commands fail.
- `postinst` does **not** use `set -e`. Each step fails gracefully so one broken optional step (e.g. icon cache) cannot abort the entire install.
- The shell stub (`/usr/local/bin/lytrize`) exports `QT_PLUGIN_PATH`, `QT_QPA_PLATFORM_PLUGIN_PATH`, and `LD_LIBRARY_PATH` so PySide6 finds its bundled Qt platform plugins without requiring system Qt packages. It also writes launch errors to `/tmp/lytrize-launch.log`.
- If `build.sh` succeeds but `dpkg -i` fails with dependency errors, run `sudo apt-get install -f` to resolve them, then re-install.
- Runtime system dependencies are: `python3 (>= 3.11)`, `libgl1`, `libegl1`, `libglib2.0-0`, `libxcb-cursor0`, `libdbus-1-3`. If you add PySide6 features that require additional Qt modules, add the corresponding system library to `Depends` in `packaging/DEBIAN/control`.

### RPM package

An equivalent RPM build is available for Fedora / RHEL / openSUSE:

```bash
# Requires: sudo dnf install rpm-build
bash build_rpm.sh
sudo dnf install build/lytrize-1.2-1.x86_64.rpm
```

The spec file lives at `packaging/rpm/lytrize.spec`. It mirrors `DEBIAN/control` for metadata, `postinst` for `%post`, and `postrm` for `%postun`. When changing either Debian or RPM packaging files, update the counterpart too.

---

## Pull request checklist

- [ ] PR scope is limited to one feature or fix
- [ ] New functions have type hints and a docstring as the **first** statement in the body
- [ ] `import streamlit` not added at module level in `modules/utils/perf.py`
- [ ] `@st.cache_resource` used for any new image or binary asset encoding
- [ ] Plotly figures sample data **before** building the figure, not after
- [ ] Any new SQLite column added with `ALTER TABLE … ADD COLUMN …` in a `try/except`, using `_column_exists()` for idempotency
- [ ] New session or chart fields added to `sanitize_restored_session()` and the backup payload
- [ ] No outbound network calls added to backend code
- [ ] `python -c "import sys; sys.path.insert(0, 'backend'); import app"` exits cleanly
- [ ] `bash build.sh` completes without errors
- [ ] If new PySide6/Qt features added, required system library added to `Depends` in `DEBIAN/control` and `Requires` in `packaging/rpm/lytrize.spec`
- [ ] Docs updated if the workflow, architecture, or file structure changed
