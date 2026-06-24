"""
backend.modules -- Core backend modules for Lytrize.

Packages:
    analysis  -- Chart generation runners and the analysis registry.
    pages     -- Streamlit page definitions (home, upload, analysis, dashboard, auth).
    ui        -- UI components, CSS, column tools, data cleaner, font/theme management.
    utils     -- Performance helpers, session cache, DataFrame snapshots.

Standalone modules:
    charts.py     -- Shared palettes, chart layout, auto-insight engine.
    database.py   -- SQLite schema, auth, session CRUD, draft persistence.
    export.py     -- Self-contained HTML dashboard export engine.
"""