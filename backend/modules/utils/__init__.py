"""
backend.modules.utils -- Utility helpers for the Lytrize backend.

Modules:
    perf.py          -- DataFrame dtype optimisation, CSV/Excel readers,
                       plot sampling, render-budget guards, cached pivot tables.
    session_cache.py -- Per-user DataFrame parquet snapshot save/load
                       for cross-rerun persistence and tab-refresh recovery.
"""