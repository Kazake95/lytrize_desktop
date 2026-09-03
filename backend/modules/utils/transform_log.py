"""modules/utils/transform_log.py — Records column-structural transforms
(add calculated column, remove column, rename column, dtype conversion) as
a small ordered recipe, and replays that recipe against a freshly
re-uploaded raw DataFrame so saved charts/KPIs can be regenerated.

Deliberately scoped to *structural* operations only (ones that change
which columns exist / what they're called / what dtype they are).
Row-value cleaning done in modules/ui/data_cleaner.py (text clean,
find & replace, numeric clean) is NOT logged here -- those don't affect
whether a chart's or KPI's referenced column still exists, which is the
specific failure mode this module protects against. See README note in
CONTRIBUTOR.md / PR description for the follow-up if row-value replay is
wanted later.
"""

import json
import logging

import pandas as pd
import streamlit as st

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Recording
# ---------------------------------------------------------------------------
def log_transform(op: str, **params) -> None:
    """Append a structural transform op to st.session_state.transform_log.

    Call this immediately after the mutation has been applied successfully
    (mirrors how chart_meta is written after a chart is generated).
    """
    entry = {"op": op, **params}
    st.session_state.setdefault("transform_log", [])
    st.session_state.transform_log.append(entry)


def get_transform_log_json() -> str:
    """Serialise the current transform log for DB persistence."""
    try:
        return json.dumps(st.session_state.get("transform_log", []), ensure_ascii=False)
    except Exception as exc:
        log.warning("get_transform_log_json: failed to serialise: %s", exc)
        return "[]"


def set_transform_log_from_json(raw_json: str) -> None:
    """Load a stored transform log JSON string into session_state."""
    try:
        st.session_state.transform_log = json.loads(raw_json) if raw_json else []
    except Exception as exc:
        log.warning("set_transform_log_from_json: failed to parse: %s", exc)
        st.session_state.transform_log = []


# ---------------------------------------------------------------------------
# Replay
# ---------------------------------------------------------------------------
def replay_transform_log(df: pd.DataFrame, transform_log: list) -> tuple[pd.DataFrame, list[str]]:
    """Re-apply a saved list of structural transforms to a freshly
    uploaded raw DataFrame.

    Returns (new_df, warnings). Each op is best-effort: a failed op is
    skipped (with a human-readable warning appended) rather than aborting
    the whole replay, so one bad step doesn't block the rest.
    """
    # Local imports to avoid a circular import at module load time --
    # column_manager.py / column_tools.py only import *this* module inside
    # their own handler functions, never at top level.
    from modules.ui.column_manager import (
        _safe_formula_eval, compute_date_diff, compute_date_extract,
    )
    from modules.ui.column_tools import convert_series_dtype

    df = df.copy()
    warnings: list[str] = []

    for step in (transform_log or []):
        op = step.get("op")
        try:
            if op == "rename_column":
                src, dst = step.get("from"), step.get("to")
                if src not in df.columns:
                    warnings.append(f"Rename skipped: column '{src}' not found in the new file.")
                    continue
                if dst in df.columns:
                    warnings.append(
                        f"Rename skipped: target name '{dst}' already exists in the new file."
                    )
                    continue
                df = df.rename(columns={src: dst})

            elif op == "remove_column":
                col = step.get("col")
                if col in df.columns:
                    df = df.drop(columns=[col])
                # Already absent -- nothing to do, not worth a warning.

            elif op == "convert_dtype":
                col, new_dtype = step.get("col"), step.get("new_dtype")
                if col not in df.columns:
                    warnings.append(f"Dtype conversion skipped: column '{col}' not found in the new file.")
                    continue
                df[col] = convert_series_dtype(df[col], new_dtype)

            elif op == "add_formula_col":
                new_col, formula = step.get("new_col"), step.get("formula")
                df[new_col] = _safe_formula_eval(df, formula)

            elif op == "add_date_diff":
                new_col = step.get("new_col")
                col_a   = step.get("col_a")
                col_b   = step.get("col_b")
                use_today = step.get("use_today", False)
                unit    = step.get("unit")
                if col_a not in df.columns or (col_b and col_b not in df.columns):
                    missing = col_a if col_a not in df.columns else col_b
                    warnings.append(f"'{new_col}' skipped: column '{missing}' not found in the new file.")
                    continue
                df[new_col] = compute_date_diff(df, col_a, col_b, use_today, unit)

            elif op == "add_date_extract":
                new_col, source_col, part = step.get("new_col"), step.get("source_col"), step.get("part")
                if source_col not in df.columns:
                    warnings.append(f"'{new_col}' skipped: column '{source_col}' not found in the new file.")
                    continue
                df[new_col] = compute_date_extract(df, source_col, part)

            else:
                warnings.append(f"Unrecognised transform step '{op}' skipped.")

        except Exception as exc:
            label = step.get("new_col") or step.get("col") or step.get("from") or op
            warnings.append(f"'{label}' failed to reapply: {exc}")
            log.warning("replay_transform_log: step %s failed: %s", step, exc)

    return df, warnings
