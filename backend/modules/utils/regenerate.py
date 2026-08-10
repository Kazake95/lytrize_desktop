"""modules/utils/regenerate.py — Rebuilds saved charts and recomputes saved
KPIs against a freshly re-uploaded DataFrame, using the generation recipe
captured when each chart/KPI was first created (see _add_charts() in
pages/analysis.py for charts, _calc_kpi() in pages/dashboard.py for KPIs).

This is the "auto-update on re-upload" piece: it does NOT touch column
structure -- run modules.utils.transform_log.replay_transform_log() first
so calculated/renamed columns exist again before calling these.
"""

import json
import logging

import streamlit as st

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Column-reference extraction (used for the missing-column pre-check)
# ---------------------------------------------------------------------------
def _columns_referenced_by_kwargs(kwargs: dict) -> set:
    """Best-effort extraction of column names referenced by a
    _generation_kwargs dict. Keys ending in _col/_cols are treated as
    column references; everything else (palette, agg, sort_by, ...) is
    ignored."""
    cols = set()
    for key, val in (kwargs or {}).items():
        if not (key.endswith("_col") or key.endswith("_cols")):
            continue
        if val is None:
            continue
        if isinstance(val, (list, tuple)):
            cols.update(v for v in val if isinstance(v, str))
        elif isinstance(val, str):
            cols.add(val)
    return cols


def validate_columns(df) -> dict:
    """Check every saved chart's and KPI's referenced columns against the
    current DataFrame. Returns {"charts": {uid: [missing cols]},
    "kpis": {label: [missing cols]}} — only entries with actual gaps."""
    available = set(df.columns) if df is not None else set()
    report = {"charts": {}, "kpis": {}}

    for uid, title, _fig in st.session_state.get("charts", []):
        meta = st.session_state.get(f"chart_meta_{uid}", {})
        gen_kwargs = meta.get("_generation_kwargs")
        if not gen_kwargs:
            continue
        missing = sorted(c for c in _columns_referenced_by_kwargs(gen_kwargs) if c not in available)
        if missing:
            report["charts"][uid] = {"title": title, "missing": missing}

    for kpi in st.session_state.get("kpis", []):
        recipe = kpi.get("_recipe")
        if not recipe:
            continue
        refs = {recipe.get("col"), recipe.get("group_col"),
                recipe.get("metric_col"), recipe.get("filter_col")}
        missing = sorted(c for c in refs if c and c not in available)
        if missing:
            report["kpis"][kpi.get("label", "KPI")] = missing

    return report


# ---------------------------------------------------------------------------
# Chart regeneration
# ---------------------------------------------------------------------------
def regenerate_charts(df) -> dict:
    """Re-run every saved chart's generation recipe against *df*, replacing
    its figure in place (same uid, so layout/notes/position are preserved).

    Returns {"updated": [uid, ...], "skipped": {uid: reason}}.
    """
    from modules.analysis import _run
    from modules.charts import apply_hover_format

    charts = st.session_state.get("charts", [])
    result = {"updated": [], "skipped": {}}
    if not charts:
        return result

    # Group chart uids by identical (chart_type, generation kwargs) — one
    # "Generate" click in the original session could have produced several
    # charts (e.g. one per selected column) sharing the same recipe.
    groups: dict = {}
    order: list = []
    for uid, title, fig in charts:
        chart_type = st.session_state.get(f"chart_type_{uid}", "")
        meta = st.session_state.get(f"chart_meta_{uid}", {})
        gen_kwargs = meta.get("_generation_kwargs")
        if not gen_kwargs:
            result["skipped"][uid] = (
                "no saved recipe for this chart (created before auto-update "
                "was added) — regenerate it manually"
            )
            continue
        sig = (chart_type, json.dumps(gen_kwargs, sort_keys=True, default=str))
        if sig not in groups:
            groups[sig] = []
            order.append(sig)
        groups[sig].append(uid)

    new_charts_by_uid = {}
    for sig in order:
        chart_type, kwargs_json = sig
        uids = groups[sig]
        gen_kwargs = json.loads(kwargs_json)
        try:
            regenerated = _run(chart_type, df, **gen_kwargs)
        except Exception as exc:
            regenerated = None
            log.warning("regenerate_charts: _run failed for %s: %s", chart_type, exc)

        if not regenerated or len(regenerated) != len(uids):
            reason = (
                f"regenerated chart count ({len(regenerated) if regenerated else 0}) "
                f"didn't match the original ({len(uids)}) — likely a missing column; "
                f"regenerate manually"
            )
            for uid in uids:
                result["skipped"][uid] = reason
            continue

        for uid, (_new_uid, new_title, new_fig) in zip(uids, regenerated):
            apply_hover_format(new_fig)
            new_charts_by_uid[uid] = new_fig
            result["updated"].append(uid)

    if new_charts_by_uid:
        st.session_state.charts = [
            (uid, title, new_charts_by_uid.get(uid, fig))
            for uid, title, fig in charts
        ]

    return result


# ---------------------------------------------------------------------------
# KPI regeneration
# ---------------------------------------------------------------------------
def regenerate_kpis(df) -> dict:
    """Recompute every saved KPI's value against *df* using its stored
    recipe. KPIs saved before this feature existed (no "_recipe" key) are
    left untouched. Returns {"updated": [label,...], "skipped": [label,...]}."""
    from modules.pages.dashboard import _calc_kpi

    kpis = st.session_state.get("kpis", [])
    result = {"updated": [], "skipped": []}
    if not kpis:
        return result

    new_kpis = []
    for kpi in kpis:
        recipe = kpi.get("_recipe")
        if not recipe:
            result["skipped"].append(kpi.get("label", "KPI"))
            new_kpis.append(kpi)
            continue
        try:
            new_kpi = _calc_kpi(
                df,
                recipe.get("kpi_type"),
                recipe.get("col"),
                recipe.get("group_col"),
                recipe.get("metric_col"),
                recipe.get("filter_col"),
                recipe.get("filter_val"),
                recipe.get("label"),
            )
            new_kpis.append(new_kpi)
            result["updated"].append(new_kpi.get("label", "KPI"))
        except Exception as exc:
            log.warning("regenerate_kpis: failed for %s: %s", kpi.get("label"), exc)
            result["skipped"].append(kpi.get("label", "KPI"))
            new_kpis.append(kpi)

    st.session_state.kpis = new_kpis
    return result
