# Contributing to Lytrize

Thanks for your interest. This guide covers the repository layout, local development setup, and conventions used in Lytrize.

---

## Quick Start for Developers

### 1. Clone the repository

```bash
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop
```

### 2. Create a virtual environment

Use Python 3.11 or newer.

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app in development

```bash
streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1
```

The packaged launcher under `desktop/launcher.py` is for installed builds only. It expects the app at `/opt/lytrize`, so do not use it for a source checkout.

---

## Repository Overview

Lytrize has two main layers:

* `desktop/` — launcher layer (launcher window, browser selection, Streamlit process management).
* `backend/` — Streamlit application and all data processing code.

The backend runs locally and offline. It uses a local SQLite database for sessions, drafts, and user identity.

---

## Architecture

```text
┌─────────────────────────────────────────────────────────────┐
│                     desktop/ (launcher layer)               │
│  gui.py       — Main launcher window, browser selection,    │
│                 Streamlit subprocess management             │
│  launcher.py  — Entry point for installed builds           │
└──────────────────────┬──────────────────────────────────────┘
                       │ subprocess
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    backend/ (Streamlit app)                 │
│  app.py        — Entry point, routing, session restore,    │
│                   Plotly offline config, CSS injection      │
│  config.py     — Shared constants                           │
│                                                             │
│  modules/                                                   │
│    charts.py     — Palettes, chart layout, insight engine   │
│    database.py   — SQLite CRUD, local identity, sessions    │
│    export.py     — Self-contained HTML dashboard export     │
│                                                             │
│    analysis/      — Chart runners and chart standardizer    │
│      apply_lytrize_standard.py                              │
│      descriptive.py                                         │
│      statistical.py                                          │
│      distribution.py                                         │
│      correlation.py                                          │
│      categorical.py                                          │
│      pie_chart.py                                            │
│      time_series.py                                          │
│      scatter_plot.py                                         │
│      matrix_table.py                                         │
│      outlier.py                                              │
│      map_plot.py                                             │
│      insights.py                                             │
│                                                             │
│    pages/                                                   │
│      home.py         — Home and saved sessions              │
│      upload.py       — File upload and column classifier    │
│      analysis.py     — Chart card grid and generation       │
│      dashboard.py    — Dashboard builder                    │
│      auth.py         — Local profile and session controls   │
│                                                             │
│    ui/                                                      │
│      css.py           — Global CSS and footer/logo helpers  │
│      column_tools.py  — Column type classification UI      │
│      column_manager.py — Column name and type management    │
│      data_cleaner.py  — Missing value and outlier handling  │
│      chart_settings.py — Per-chart settings panel           │
│      font_manager.py  — Font family and style picker        │
│      theme_tokens.py  — Design tokens                       │
│                                                             │
│    utils/                                                   │
│      perf.py          — Dtype optimization, readers,        │
│                         sampling                             │
│      session_cache.py  — Parquet snapshots for tab refresh  │
└─────────────────────────────────────────────────────────────┘
```

### Data flow

1. The launcher starts Streamlit and opens the browser with the app URL.
2. `app.py` sets up SQLite, restores drafts, and routes to the active page.
3. The upload page loads a file, runs it through the fast reader, classifies columns, and stores the result in `session_state`.
4. The analysis page renders chart cards and dispatches each chart type to its runner.
5. Charts are stored as Plotly JSON in `st.session_state` and in the draft database.
6. The dashboard page arranges charts, adds KPIs, and optionally exports the result.

---

## Project structure

```text
lytrize_desktop/
├── backend/
│   ├── app.py
│   ├── config.py
│   ├── assets/
│   │   ├── lytrize.png / .ico
│   │   └── fonts/
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── charts.py
│   │   ├── database.py
│   │   ├── export.py
│   │   ├── analysis/
│   │   │   ├── apply_lytrize_standard.py
│   │   │   ├── descriptive.py
│   │   │   ├── statistical.py
│   │   │   ├── distribution.py
│   │   │   ├── correlation.py
│   │   │   ├── categorical.py
│   │   │   ├── pie_chart.py
│   │   │   ├── time_series.py
│   │   │   ├── scatter_plot.py
│   │   │   ├── matrix_table.py
│   │   │   ├── outlier.py
│   │   │   ├── map_plot.py
│   │   │   └── insights.py
│   │   ├── pages/
│   │   │   ├── home.py
│   │   │   ├── upload.py
│   │   │   ├── analysis.py
│   │   │   ├── dashboard.py
│   │   │   └── auth.py
│   │   ├── ui/
│   │   │   ├── css.py
│   │   │   ├── column_manager.py
│   │   │   ├── column_tools.py
│   │   │   ├── data_cleaner.py
│   │   │   ├── chart_settings.py
│   │   │   ├── excel_loader.py
│   │   │   ├── font_manager.py
│   │   │   └── theme_tokens.py
│   │   └── utils/
│   │       ├── perf.py
│   │       └── session_cache.py
├── desktop/
│   ├── gui.py
│   └── launcher.py
├── packaging/
│   ├── deb/
│   └── rpm/
├── service/
│   └── lytrize.service
├── assets/
├── requirements.txt
├── .gitignore
├── LICENSE
├── README.md
└── CONTRIBUTING.md
```

---

## Backend Modules

| Module                               | Purpose                                                  | Key exports                                                                        |
| ------------------------------------ | -------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `charts.py`                          | Palettes, default layouts, insight engine                | `PALETTES`, `chart_layout()`, `generate_chart_insights()`, `charts_to_json()`      |
| `database.py`                        | SQLite schema and all DB I/O, local identity, sessions   | `init_db()`, `save_session_db()`, `get_draft()`, `login_user()`, `register_user()` |
| `export.py`                          | Render charts to self-contained HTML                     | `generate_html_report()`                                                           |
| `analysis/__init__.py`               | Registry mapping `aid → runner`, config widget rendering | `ANALYSIS_OPTIONS`, `_RUNNERS`, `render_config_panel()`, `_run()`                  |
| `analysis/apply_lytrize_standard.py` | Shared chart styling helpers                             | Lytrize styling and figure normalization utilities                                 |
| `ui/css.py`                          | Global CSS injection, footer/logo helpers                | `inject_css()`, `inject_footer()`, `render_logo()`                                 |
| `utils/perf.py`                      | Fast readers, dtype optimization, sampling               | `read_csv_fast()`, `optimize_dtypes()`, `sample_for_plot()`                        |

---

## Adding a new chart type

1. Create `backend/modules/analysis/<new_type>.py` with a `run_<new_type>(df, **kwargs)` function that returns a list of `(title, fig)` tuples.
2. Import it in `backend/modules/analysis/__init__.py` and add one entry to:
   - `ANALYSIS_OPTIONS` (for the UI card)
   - `_RUNNERS` (to dispatch to your function)
3. If your chart needs config controls (column pickers, palettes, etc.), add entries to `_WIDGET_SPEC` in the same file.

That's it — no other files need changes.

---

## Making UI changes

* **CSS:** Edit `modules/ui/css.py` for app-wide styles. Per-page styling lives inline in `modules/pages/*.py`. Avoid external CSS frameworks.
* **Streamlit widgets:** Use `st.columns()` for layout and `st.expander()` for grouped controls. Keep widget keys unique with per-page prefixes.
* **New page:** Create a file in `modules/pages/`, add a route in `app.py`, import the page function, and set `st.session_state.page` to switch to it.

---

## Code Style and Conventions

* **Python version:** 3.11+.
* **Docstrings:** Use Google-style docstrings (`Args`, `Returns`, `Raises`).
* **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
* **Streamlit session state keys:** Prefix keys to avoid collisions, for example `_cfg_{aid}_{key}` or `auto_insights_{uid}`.
* **Error handling:** Catch and log errors; do not crash the UI.
* **Performance:** Use `@st.cache_resource` for one-per-process assets and `@st.cache_data` for computed data. Avoid unnecessary disk I/O on reruns.
* **HTML escaping:** Use the `_h()` helper from `modules/export.py` when injecting user-controlled text into HTML strings.

---

## Testing

Currently the project does not include a automated test suite. When adding new features, please:

1. Run the app manually (`streamlit run backend/app.py`) and exercise the new code path.
2. Verify common edge cases: empty DataFrames, missing columns, very large files, and special characters in column names.
3. Check that the auto-save draft does not grow unbounded; verify draft cleanup after save/update.
4. If you add a new chart runner, confirm that the insight engine produces at least one insight and does not crash on degenerate data.

---

## Debugging

### Backend (Streamlit)

- Run with `streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1` to see live logs in the terminal.
- Use `st.write()` or `st.json()` to inspect `st.session_state` during development.
- The launcher writes backend logs to `~/.local/share/lytrize/streamlit.log` when launched from the desktop entry.

### Desktop Launcher

- Launch from a terminal with `python desktop/launcher.py` or `python desktop/gui.py` to see Qt debug output.
- Browser profiles are stored under `~/.local/share/lytrize/browser-profiles/`. Delete a profile to reset browser state.
- If the launcher hangs, check for a stale Streamlit process: `pkill -f streamlit` and restart.

### Database

- The SQLite database lives at `~/.local/share/lytrize/lytrize.db`. You can inspect it with `sqlite3 ~/.local/share/lytrize/lytrize.db`.
- Set `LYTRIZE_DB_PATH=/tmp/lytrize_test.db` to use a throwaway database for debugging.
- Drafts are stored in `draft_sessions`. If the app feels slow, verify that draft cleanup is happening after saves.

### Common Pitfalls

- **Streamlit reruns are expensive.** Avoid heavy computation at module top-level; use `@st.cache_data` or `@st.cache_resource`.
- **Session state key collisions.** Always prefix keys (`_cfg_`, `auto_insights_`, `desc_`, etc.) to avoid clobbering built-in Streamlit keys.
- **Circular imports.** Keep chart runners in `modules/analysis/` and UI helpers in `modules/ui/`. If you need a shared constant, put it in `charts.py` or `config.py`, not in a page module.
- **Plotly figure mutability.** Deep-copy figures before mutating them in export or display helpers; Plotly figures are mutable and shared across reruns.

---

## Session State Keys

| Key                               | Set when      | Description                                                       |
| --------------------------------- | ------------- | ----------------------------------------------------------------- |
| `user_id`                         | app bootstrap | Integer local identity ID                                         |
| `username`                        | app bootstrap | Display name                                                      |
| `is_guest`                        | app bootstrap | Boolean guest flag                                                |
| `df`                              | upload page   | Active DataFrame                                                  |
| `col_descriptions`                | upload page   | `{col: desc}` from column classifier                              |
| `num_cols`, `cat_cols`, `dt_cols` | upload page   | Confirmed column types                                            |
| `charts`                          | analysis page | `[(uid, title, fig), ...]`                                        |
| `page`                            | app routing   | `"home"`, `"upload"`, `"analysis"`, `"dashboard"`, or `"profile"` |
| `editing_session_id`              | home edit     | Integer session being edited                                      |
| `view_session_id`                 | home view     | Integer session being viewed                                      |
| `_restore_to_page`                | app           | Internal: resume page after draft restore                         |

---

## Database Schema

* `users` — local identities.
* `sessions` — saved dashboards (charts as JSON, KPIs, grid layout).
* `draft_sessions` — auto-save per user (`user_id` as primary key).
* `user_activity` — append-only audit log.
* `login_tokens` — local persistent tokens for session restore.

Migrations are handled with `ALTER TABLE ... ADD COLUMN` wrapped in `try/except` inside `init_db()`.

---

## Building Packages

### .deb

```bash
cd packaging/deb
dpkg-deb --build .
# outputs lytrize_1.0_amd64.deb
```

### .rpm

Build using the spec file at `packaging/rpm/lytrize.spec`:

```bash
rpmbuild -ba packaging/rpm/lytrize.spec
```

The build creates an isolated virtual environment inside the package, bundles assets and fonts, and installs the desktop entry and launcher.

---

## Pull Request Process

1. Open an issue first describing the bug or feature.
2. Keep PRs focused — one change per PR.
3. Update `README.md` and `CONTRIBUTING.md` if behavior changes.
4. Ensure the app runs: `streamlit run backend/app.py`.
5. Mention testing steps in the PR description.

---

## Known Issues

1. No dedicated PNG download button — users must use browser DevTools to capture the exported HTML page as an image.
2. Some CSS color values in the generated HTML export lack fallback values when a theme key is missing.
3. Streamlit reruns trigger full-page refreshes, which can be slow for larger datasets.

---

## Performance Tips

- **DataFrame memory:** Use `modules/utils/perf.py::optimize_dtypes()` after loading large files to reduce memory usage by 50–70%.
- **Sampling:** For scatter plots and maps with >100k rows, `sample_for_plot()` is used automatically. The threshold is configurable in `perf.py`.
- **Caching:** Expensive computations (e.g., reading Excel sheets, parsing dates) are cached with `@st.cache_data`. Keep cache keys stable — don't include mutable objects like DataFrames in cache keys.
- **Draft autosave:** The draft is written on every chart card mutation. The `charts_json_cached()` helper in `charts.py` debounces serialisation so the draft only hits the DB when the chart set or notes actually change.

---

## License

MIT — see [LICENSE](./LICENSE).