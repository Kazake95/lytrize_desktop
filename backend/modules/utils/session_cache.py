"""
modules/utils/session_cache.py — Per-user DataFrame parquet snapshot helpers.

WHY THIS MODULE EXISTS
----------------------
The DataFrame snapshot (a parquet file written to XDG_RUNTIME_DIR or
XDG_CACHE_HOME) lets a loaded dataset survive a browser tab change or
WebSocket reconnect.  It is written after every autosave and read back
during token validation in app.py.

Previously this logic lived in app.py, which caused a circular import:

    app.py → modules/pages/analysis.py → app._save_df_snapshot (lazy import)

Moving the helpers here gives both app.py and pages/analysis.py a clean,
stable import path with no cycles.

PUBLIC API
----------
    df_cache_path(user_id)  → Path
    save_df_snapshot(user_id) → None
    load_df_snapshot(user_id) → pd.DataFrame | None
"""

import logging
import os
from pathlib import Path

import pandas as pd
import streamlit as st

log = logging.getLogger(__name__)

# Maximum parquet file size (bytes) we are willing to load back into memory.
# Files larger than this indicate an unexpectedly large dataset that might
# exhaust RAM; skip the load and let the user re-upload instead.
_MAX_SNAPSHOT_BYTES = 512 * 1_048_576  # 512 MB


def df_cache_path(user_id: int) -> Path:
    """
    Return the path for the per-user DataFrame parquet snapshot.

    Location priority:
      1. $XDG_RUNTIME_DIR/lytrize/   (RAM-backed tmpfs on most distros)
      2. $XDG_CACHE_HOME/lytrize/    (falls back to ~/.cache/lytrize/)

    The directory is created with mode 0700 so only the owning user
    can list or read its contents.
    """
    runtime = os.environ.get("XDG_RUNTIME_DIR")
    if runtime:
        base = Path(runtime) / "lytrize"
    else:
        cache_home = os.environ.get("XDG_CACHE_HOME", str(Path.home() / ".cache"))
        base = Path(cache_home) / "lytrize"

    base.mkdir(parents=True, exist_ok=True)
    try:
        base.chmod(0o700)
    except Exception:
        pass  # Non-fatal: directory may be on a filesystem that ignores chmod.

    return base / f"df_{user_id}.parquet"


def save_df_snapshot(user_id: int) -> None:
    """
    Persist the live DataFrame from st.session_state to a parquet snapshot.

    Called from _persist_draft() on every autosave so the dataset survives
    a browser change (new WebSocket session → empty server-side session_state).

    Silent no-ops when:
      - No DataFrame is loaded (st.session_state["df"] is absent or None).
      - Parquet serialisation fails (e.g. unsupported dtype).
        In the latter case a warning is logged so the issue can be diagnosed
        without ever surfacing an error to the user.
    """
    df = st.session_state.get("df")
    if df is None:
        return  # Nothing to save; not an error.

    path = df_cache_path(user_id)
    try:
        df.to_parquet(str(path), index=False)
        try:
            path.chmod(0o600)  # Readable by owner only.
        except Exception:
            pass
    except Exception as exc:
        # Log the failure so it shows up in `journalctl` / the terminal, but
        # never raise — a failed snapshot must not break the analysis flow.
        log.warning(
            "save_df_snapshot: failed to write parquet for user %s "
            "(shape=%s, path=%s): %s",
            user_id,
            getattr(df, "shape", "?"),
            path,
            exc,
        )


def load_df_snapshot(user_id: int) -> pd.DataFrame | None:
    """
    Restore the DataFrame from the parquet snapshot written by save_df_snapshot.

    Returns the DataFrame on success, or None in any of these cases:
      - Snapshot file does not exist (first launch, or tmpfs was cleared on reboot).
      - File size exceeds _MAX_SNAPSHOT_BYTES (safety guard against OOM).
      - Deserialisation fails (e.g. file corrupt, dtype mismatch after a schema
        change, or truncated write from a previous crash).

    None causes the caller to skip the draft restore gracefully rather than
    showing a broken analysis page.
    """
    path = df_cache_path(user_id)

    if not path.exists():
        return None  # Normal on first launch or after a reboot (tmpfs cleared).

    # Guard against loading a snapshot that would exceed available RAM.
    try:
        file_bytes = path.stat().st_size
        if file_bytes > _MAX_SNAPSHOT_BYTES:
            log.warning(
                "load_df_snapshot: snapshot for user %s is %.0f MB — "
                "exceeds %.0f MB limit; skipping to avoid OOM. "
                "User will need to re-upload.",
                user_id,
                file_bytes / 1_048_576,
                _MAX_SNAPSHOT_BYTES / 1_048_576,
            )
            return None
    except Exception:
        pass  # stat() failure is non-fatal; attempt the read anyway.

    try:
        return pd.read_parquet(str(path))
    except Exception as exc:
        log.warning(
            "load_df_snapshot: failed to read parquet for user %s "
            "(path=%s): %s",
            user_id,
            path,
            exc,
        )
        return None
