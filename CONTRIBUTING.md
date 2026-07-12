# Contributing to Lytrize

Thank you for your interest in contributing. This guide covers the repository layout, local development setup, and the conventions used in Lytrize.

---

## Quick start for developers

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

For local development, run the Streamlit backend directly:

```bash
streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1
```

The packaged launcher under `desktop/launcher.py` is for installed builds only. It expects the application to live under `/opt/lytrize`, so do not use it for a source checkout.


If no automated tests are present yet, use the manual smoke-test steps in this file and in `extra/test_commands.txt`.

---

## Repository overview

Lytrize is split into two main layers:

* `desktop/` contains the launcher layer.
* `backend/` contains the Streamlit application and all data-processing code.

The backend is designed to run locally and offline. It uses a local SQLite database for sessions, drafts, and identity persistence.

---

## Architecture overview

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
│    analysis/        — Chart runners and chart standardizer  │
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
│    ui/                                                       │
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
2. `app.py` bootstraps SQLite, restores drafts, and routes to the active page.
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
│   │   ├── DEBIAN/control
│   │   ├── usr/local/bin/lytrize
│   │   └── usr/share/applications/lytrize.desktop
│   └── rpm/
│       ├── lytrize.spec
│       ├── usr/local/bin/lytrize
│       └── usr/share/applications/lytrize.desktop
├── service/
│   └── lytrize.service
├── requirements.txt
├── build.sh
├── build_rpm.sh
├── .gitignore
├── README.md
└── CONTRIBUTING.md
```

---

## Backend modules in detail

| Module                               | Purpose                                                  | Key exports                                                                        |
| ------------------------------------ | -------------------------------------------------------- | ---------------------------------------------------------------------------------- |
| `charts.py`                          | Palettes, default layouts, insight engine                | `PALETTES`, `chart_layout()`, `generate_chart_insights()`, `charts_to_json()`      |
| `database.py`                        | SQLite schema and all DB I/O, local identity, sessions   | `init_db()`, `save_session_db()`, `get_draft()`, `login_user()`, `register_user()` |
| `export.py`                          | Render charts to self-contained HTML                     | `generate_html_report()`                                                           |
| `analysis/__init__.py`               | Registry mapping `aid → runner`, config widget rendering | `ANALYSIS_OPTIONS`, `_RUNNERS`, `render_config_panel()`, `_run()`                  |
| `analysis/apply_lytrize_standard.py` | Shared chart standardization helpers                     | Lytrize styling and figure normalization utilities                                 |
| `ui/css.py`                          | Global CSS injection, footer/logo helpers                | `inject_css()`, `inject_footer()`, `render_logo()`                                 |
| `utils/perf.py`                      | Fast readers, dtype optimization, sampling               | `read_csv_fast()`, `optimize_dtypes()`, `sample_for_plot()`                        |

---

## Adding a new analysis type

1. Create `backend/modules/analysis/<new_type>.py` with a `run_<new_type>(df, **kwargs)` function that returns a list of `(title, fig)` tuples.
2. Import the runner in `backend/modules/analysis/__init__.py` and add it to `_RUNNERS` and `ANALYSIS_OPTIONS`.
3. Add a widget config branch in `render_config_panel()` and a collector branch in `_collect_kwargs()`.
4. Add insight logic in `generate_chart_insights()` in `modules/charts.py` if the chart type needs custom insight generation.

---

## Making UI changes

* **CSS:** Edit `modules/ui/css.py` for app-wide styles. Per-page styling lives inline in `modules/pages/*.py`. Avoid external CSS frameworks.
* **Streamlit widgets:** Use `st.columns()` for layout and `st.expander()` for grouped controls. Keep widget keys unique with per-page prefixes.
* **New page:** Create a file in `modules/pages/`, add a route in `app.py`, import the page function, and set `st.session_state.page` to switch to it.

---

## Code style and conventions

* **Python version:** 3.11+.
* **Docstrings:** Use Google-style docstrings (`Args`, `Returns`, `Raises`).
* **Naming:** `snake_case` for functions and variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
* **Streamlit session state keys:** Prefix keys to avoid collisions, for example `_cfg_{aid}_{key}` or `auto_insights_{uid}`.
* **Error handling:** Catch and log errors; do not crash the UI.
* **Performance:** Use `@st.cache_resource` for one-per-process assets and `@st.cache_data` for computed data. Avoid unnecessary disk I/O on reruns.
* **HTML escaping:** Use the `_h()` helper from `modules/export.py` when injecting user-controlled text into HTML strings.

---

## Session state keys

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

## Database schema

* `users` — local identities.
* `sessions` — saved dashboards (charts as JSON, KPIs, grid layout).
* `draft_sessions` — auto-save per user (`user_id` as primary key).
* `user_activity` — append-only audit log.
* `login_tokens` — local persistent tokens for session restore.

Migrations are handled with `ALTER TABLE ... ADD COLUMN` wrapped in `try/except` inside `init_db()`.

---

## Building packages

### .deb

```bash
./build.sh
# outputs lytrize_1.0_amd64.deb
```

### .rpm

```bash
./build_rpm.sh
# outputs lytrize-1.0-1.x86_64.rpm
```

The build scripts create an isolated virtual environment inside the package, bundle assets and fonts, and install the desktop entry and launcher under `/usr/local/bin/` and `/usr/share/applications/`.

---

## Testing

Run the backend in isolation with a dummy file:

```bash
streamlit run backend/app.py
```

Use `extra/test_commands.txt` for manual smoke-test commands.

---

## Pull request process

1. Open an issue first describing the bug or feature.
2. Keep PRs focused — one change per PR.
3. Update `README.md` and `CONTRIBUTING.md` if behavior changes.
4. Ensure the app runs: `streamlit run backend/app.py`.
5. Mention testing steps in the PR description.

---

## Known issues

1. No dedicated PNG download button — users must use browser DevTools to capture the exported HTML page as an image.
2. Some CSS color values in the generated HTML export lack fallback values when a theme key is missing.
3. Streamlit reruns trigger full-page refreshes, which can be slow for larger datasets.

---

## License

See [LICENSE](./LICENSE).