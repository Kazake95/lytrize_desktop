"""modules/utils/session_cache.py — Per-user DataFrame parquet snapshot helpers."""


import logging
import os
from pathlib import Path
from typing import Optional


import pandas as pd
import streamlit as st


log = logging.getLogger(__name__)


_MAX_SNAPSHOT_BYTES = 512 * 1_048_576




def df_cache_path(user_id: int) -> Path:
    """Return the path for the per-user DataFrame parquet snapshot."""
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
        pass


    return base / f"df_{user_id}.parquet"




def save_df_snapshot(user_id: int, df=None) -> None:
    """Persist a DataFrame to a parquet snapshot. Pass df explicitly when calling from a thread."""
    if df is None:
        df = st.session_state.get("df")
    if df is None:
        return


    path = df_cache_path(user_id)
    try:
        df.to_parquet(str(path), index=False, engine="pyarrow", compression="snappy")
        try:
            path.chmod(0o600)
        except Exception:
            pass
    except Exception as exc:
        log.warning(
            "save_df_snapshot: failed to write parquet for user %s "
            "(shape=%s, path=%s): %s",
            user_id,
            getattr(df, "shape", "?"),
            path,
            exc,
        )




def load_df_snapshot(user_id: int) -> Optional[pd.DataFrame]:
    """Restore the DataFrame from the parquet snapshot written by save_df_snapshot."""
    path = df_cache_path(user_id)


    if not path.exists():
        return None


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
        pass


    try:
        return pd.read_parquet(str(path), engine="pyarrow")
    except Exception as exc:
        log.warning(
            "load_df_snapshot: failed to read parquet for user %s "
            "(path=%s): %s",
            user_id,
            path,
            exc,
        )
        return None
