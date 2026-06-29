# Contributing to Lytrize

Thank you for your interest in contributing! This guide covers the architecture, setup, and conventions you need to work on Lytrize effectively.

---

## Quick start for developers

### 1. Clone the repository

```bash
git clone https://github.com/Kazake95/lytrize_desktop.git
cd lytrize_desktop
```

### 2. Create a virtual environment

```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Run the app

```bash
# Start the launcher (PySide6 GUI)
python desktop/launcher.py

# Or run the Streamlit backend directly:
streamlit run backend/app.py --server.port 8501 --server.address 127.0.0.1
```

### 5. Run tests (if any)

```bash
python -m pytest
```

---

## Architecture overview

```
┌─────────────────────────────────────────────────────────────┐
│                     desktop/ (PySide6 launcher)             │
│  gui.py    — Main launcher window, system tray, browser      │
│              selection, Streamlit subprocess management      │
│  launcher.py — Entry point                                  │
└──────────────────────┬──────────────────────────────────────┘
                       │  subprocess
                       ▼
┌─────────────────────────────────────────────────────────────┐
│                    backend/ (Streamlit app)                  │
│  app.py          — Entry point, routing, session restore,   │
│                    Plotly offline config, CSS injection      │
│  config.py       — Shared constants (APP_HOST, APP_PORT)    │
│                                                              │
│  modules/                                                    │
│    charts.py     — Palettes, chart_layout(), insight engine  │
│    database.py   — SQLite CRUD, auth, session save/restore   │
│    export.py     — Self-contained HTML dashboard export      │
│                                                              │
│    pages/        — Streamlit page implementations            │
│      home.py         — Home/welcome + session list           │
│      upload.py       — File upload, column classifier        │
│      analysis.py     — Chart card grid + generation          │
│      dashboard.py    — Drag-and-drop dashboard builder       │
│      auth.py         — Profile, sign-in/out, account mgmt    │
│                                                              │
│    ui/           — Shared UI components                      │
│      css.py          — Glassmorphism CSS, footer/logo        │
│      column_tools.py — Column type classification UI        │
│      column_manager.py — Column name / type management       │
│      data_cleaner.py   — Missing value / outlier handling    │
│      chart_settings.py — Per-chart settings panel            │
│      font_manager.py   — Font family / style picker          │
│      theme_tokens.py   — Design tokens (colours, radii)     │
│                                                              │
│    utils/        — Pure data helpers                         │
│      perf.py          — dtype opt, CSV/Excel readers, sampling│
│      session_cache.py — Parquet snapshots for tab refresh    │
└─────────────────────────────────────────────────────────────┘
```

### Data flow

1. Launcher starts Streamlit, opens browser with app URL.
2. `app.py` bootstraps SQLite, restores draft, routes to page.
3. Upload page loads file → perf reader → column classifier → session_state.
4. Analysis page renders chart cards → `_run()` dispatches to type.
5. Charts stored as Plotly JSON in `st.session_state` + draft DB.
6. Dashboard arranges charts, adds KPIs, optionally exports.

---

## Project structure

```
lytrize_desktop/
├── backend/
│   ├── app.py                 # Streamlit entry point + routing
│   ├── config.py              # APP_HOST, APP_PORT, APP_NAME
│   ├── assets/                # Icons, fonts, welcome banner
│   │   ├── lytrize.png / .ico
│   │   └── fonts/             # Inter (embedded) + 50+ system font families
│   ├── modules/
│   │   ├── __init__.py
│   │   ├── charts.py          # PALETTES, chart_layout(), insights
│   │   ├── database.py        # All DB operations, auth, sessions
│   │   ├── export.py          # HTML dashboard export
│   │   ├── analysis/          # 10 chart-type runners
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
│   └── .streamlit/
│       └── config.toml
├── desktop/
│   ├── gui.py                 # PySide6 launcher window
│   └── launcher.py            # Entry point
├── packaging/
│   ├── deb/                   # Debian package files
│   │   ├── DEBIAN/control
│   │   ├── usr/local/bin/lytrize
│   │   └── usr/share/applications/lytrize.desktop
│   └── rpm/                   # RPM package files
│       ├── lytrize.spec
│       ├── usr/local/bin/lytrize
│       └── usr/share/applications/lytrize.desktop
├── service/
│   └── lytrize.service        # systemd user service
├── requirements.txt
├── build.sh                   # Build script
├── build_rpm.sh               # RPM build script
├── .gitignore
├── README.md
└── CONTRIBUTING.md
```

---

## Backend modules in detail

| Module | Purpose | Key exports |
|--------|---------|--------------|
| `charts.py` | Palettes, default layouts, insight engine | `PALETTES`, `chart_layout()`, `generate_chart_insights()`, `charts_to_json()` |
| `database.py` | SQLite schema + all DB I/O, auth, sessions | `init_db()`, `save_session_db()`, `get_draft()`, `login_user()`, `register_user()` |
| `export.py` | Render charts to self-contained HTML | `generate_html_report()` |
| `analysis/__init__.py` | Registry mapping `aid → runner`, config widget rendering | `ANALYSIS_OPTIONS`, `_RUNNERS`, `render_config_panel()`, `_run()` |
| `ui/css.py` | Global CSS injection, footer/logo helpers | `inject_css()`, `inject_footer()`, `render_logo()` |
| `utils/perf.py` | Fast readers, dtype optimisation, sampling | `read_csv_fast()`, `optimize_dtypes()`, `sample_for_plot()` |

---

## Adding a new analysis type

1. Create `backend/modules/analysis/<new_type>.py` with a `run_<new_type>(df, **kwargs)` function returning a list of `(title, fig)` tuples.
2. Import the runner in `backend/modules/analysis/__init__.py` and add it to `_RUNNERS` and `ANALYSIS_OPTIONS`.
3. Add a widget config branch in `render_config_panel()` and a collector branch in `_collect_kwargs()`.
4. Add insight logic in `generate_chart_insights()` in `modules/charts.py` if the chart type needs custom insight generation.
5. Add the chart card to `pages/analysis.py` — append to `_CARD_LAYOUT` dict with `aid`, label, icon, description.

---

## Making UI changes

- **CSS:** Edit `modules/ui/css.py` for app-wide styles. Per-page styling lives inline in `modules/pages/*.py`. Avoid external CSS frameworks.
- **Streamlit widgets:** Use `st.columns()` for layout, `st.expander()` for grouped controls. Keep widget keys unique with per-page prefixes.
- **New page:** Create file in `modules/pages/`, add route in `app.py` `page_dashboard()`, and set `st.session_state.page` to switch to it.

## Code style & conventions

- **Python version:** 3.11+.
- **Docstrings:** Google-style (Args/Returns/Raises). Module-level docstrings explain scope and design rules.
- **Naming:** `snake_case` for functions/variables, `PascalCase` for classes, `UPPER_SNAKE` for constants.
- **Streamlit session_state keys:** Prefixed to avoid collisions (e.g. `_cfg_{aid}_{key}`, `auto_insights_{uid}`).
- **Error handling:** Catch and log — never crash the UI. Use `log.warning()` / `log.error()` with context.
- **Performance:** Use `@st.cache_resource` for one-per-process assets, `@st.cache_data` for computed data. Avoid per-rerun disk I/O.
- **CSS/HTML:** Keep strings escaped via `_h()`. Do not inject unescaped user input.

---

## Session state keys (reference)

| Key | Set when | Description |
|-----|----------|-------------|
| `user_id` | app.py bootstrap | Integer guest or real account ID |
| `username` | app.py bootstrap | Display name |
| `is_guest` | app.py bootstrap | Bool |
| `df` | upload page | Active DataFrame |
| `col_descriptions` | upload page | `{col: desc}` from column classifier |
| `num_cols`, `cat_cols`, `dt_cols` | upload page | Confirmed column types |
| `charts` | analysis page | `[(uid, title, fig), ...]` |
| `page` | app.py routing | `"home"\|"upload"\|"analysis"\|"dashboard"\|"profile"` |
| `editing_session_id` | home edit | Integer session being edited |
| `view_session_id` | home view | Integer session being viewed |
| `_restore_to_page` | app.py | Internal: resume page after draft restore |

---

## Database schema

- `users` — accounts (PBKDF2 password hashes, guest flag).
- `sessions` — saved dashboards (charts as JSON, KPIs, grid layout).
- `draft_sessions` — auto-save per user (PRIMARY KEY user_id).
- `user_activity` — append-only audit log.
- `login_tokens` — 7-day persistent tokens for auto-login.

Migrations are handled with `ALTER TABLE ... ADD COLUMN` wrapped in try/except inside `init_db()`.

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

The build scripts create an isolated venv inside the package,
bundle assets and fonts, and install the desktop entry + launcher
under `/usr/local/bin/` and `/usr/share/applications/`.

---

## Testing

Run the backend in isolation with a dummy file:

```bash
streamlit run backend/app.py
```

Use `test_commands.txt` in the repo root for manual smoke-test
commands. Automated test suite TBD.

---

## Pull request process

1. Open an issue first describing the bug or feature.
2. Keep PRs focused — one change per PR.
3. Update README.md / CONTRIBUTING.md if behaviour changes.
4. Ensure the app runs: `streamlit run backend/app.py`.
5. Mention testing steps in the PR description.

---

## Known issues

1. No dedicated PNG download button — users must use browser DevTools to capture the exported HTML page as an image.
2. Some CSS colour values in the generated HTML export lack fallback values when a theme key is missing.
3. No automated test suite — manual smoke-testing is required after changes.
4. Streamlit reruns trigger full-page refreshes, which can be slow for datasets over 300 MB.
---

## Current development

1. Dedicated chrome ext. to download a full page screeshot of dashboard html.
2. Working stable Light theme mode.
---

## License

See [LICENSE](./LICENSE).