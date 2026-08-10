"""modules/charts.py -- Shared chart utilities and palettes."""
import logging


import json
import re
import streamlit as st
import pandas as pd
import plotly.io as pio


from modules.utils.session_cache import session_cached  # lightweight memo helper

# ---------------------------------------------------------------------------
# JSON-safe key sanitizer
# ---------------------------------------------------------------------------
def _json_safe(obj):
    """Recursively walk obj and convert any non-JSON-safe dict keys to strings.

    Plotly meta attributes can produce tuple keys (e.g. ``{(x, y): val}``),
    which crash ``json.dumps``.  This helper guarantees every dict key in the
    output is a ``str``, ``int``, ``float``, or ``bool`` so serialisation
    always succeeds.
    """
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if not isinstance(k, (str, int, float, bool)):
                k = str(k)
            out[k] = _json_safe(v)
        return out
    if isinstance(obj, (list, tuple)):
        return [_json_safe(i) for i in obj]
    # Primitive types (str, int, float, bool, None) are safe as-is.
    # Everything else is converted to a string repr for safety.
    if obj is not None and not isinstance(obj, (str, int, float, bool)):
        return str(obj)
    return obj


# ---------------------------------------------------------------------------
# Per-chart fig_json memoization + persistence downsampling
# ---------------------------------------------------------------------------
_MAX_PERSIST_POINTS = 10_000


def _downsample_series(values, max_points: int = _MAX_PERSIST_POINTS):
    """Uniformly downsample a sequence to at most *max_points* entries.

    Keeps the first and last points so the line shape is preserved.  Used only
    for the persisted JSON payload so the database stays small; the on-screen
    figure is untouched.
    """
    if values is None:
        return values
    try:
        n = len(values)
    except TypeError:
        return values
    if n <= max_points:
        return values
    step = (n - 1) / (max_points - 1)
    idx = sorted({int(round(i * step)) for i in range(max_points)})
    return [values[i] for i in idx]


def _decode_bdata(value):
    """Decode a plotly-serialised numpy array (dict with bdata) into a list.

    ``copy.deepcopy`` on a Plotly figure turns numpy arrays into a compact
    dict like ``{'dtype': 'i1', 'bdata': 'AQID...', 'shape': '200000'}``.
    We must decode it BEFORE checking the length, otherwise `len(dict)` is ~3
    and large traces would never be downsampled.  For correctness these
    duplicates coexist with chart_settings._decode_plotly_array (that one
    lives in UI-land; this one lives in persistence-land).
    """
    if isinstance(value, (list, tuple)):
        return list(value)
    try:
        import numpy as _np
        if isinstance(value, _np.ndarray):
            return value.tolist()
    except Exception:
        pass
    if isinstance(value, dict) and "bdata" in value:
        try:
            import base64 as _b64
            import numpy as _np
            _dtype_map = {
                "f8": "<f8", "f4": "<f4", "i1": "<i1", "i2": "<i2",
                "i4": "<i4", "i8": "<i8", "u1": "<u1", "u2": "<u2",
                "u4": "<u4", "u8": "<u8", "b": "|b1",
            }
            _dtype = _np.dtype(
                _dtype_map.get(str(value.get("dtype", "f8")), str(value.get("dtype", "<f8")))
            )
            _shape = tuple(
                int(s) for s in str(value.get("shape", "")).split(",") if s.strip()
            )
            _arr = _np.frombuffer(_b64.b64decode(value["bdata"]), dtype=_dtype)
            if _shape:
                _arr = _arr.reshape(_shape)
            return _arr.tolist()
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            return None
    return None


def _downsample_fig_for_persist(fig):
    """Return a copy of *fig* with large line/scatter traces downsampled.

    Only touches the persisted copy; the live figure in session_state is never
    mutated.  Falls back to the original figure on any error.
    """
    try:
        import copy as _copy
        f2 = _copy.deepcopy(fig)
        for tr in f2.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            if ttype not in ("scatter", "scattergl"):
                continue
            mode = str(getattr(tr, "mode", "") or "")
            if "lines" not in mode and "markers" not in mode:
                continue
            y = _decode_bdata(getattr(tr, "y", None))
            if not y:
                continue
            n = len(y)
            if n <= _MAX_PERSIST_POINTS:
                continue
            idx = set(_downsample_series(list(range(n))))
            tr.y = [y[i] for i in sorted(idx)]
            x = _decode_bdata(getattr(tr, "x", None))
            if x and len(x) == n:
                tr.x = [x[i] for i in sorted(idx)]
            txt = getattr(tr, "text", None)
            if txt is not None:
                try:
                    if len(txt) == n:
                        tr.text = [txt[i] for i in sorted(idx)]
                except TypeError:
                    pass
        return f2
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        return fig


def _fig_json_cached(uid: str, fig) -> str:
    """Return the persisted JSON for a chart, memoized by figure object id.

    Figures are immutable once created (regeneration builds a new object), so
    caching by ``id(fig)`` means unchanged charts are never re-serialized --
    only newly generated charts pay the ``pio.to_json`` cost once.
    """
    cache = st.session_state.setdefault("_fig_json_cache", {})
    entry = cache.get(uid)
    if entry and entry[0] == id(fig):
        return entry[1]
    try:
        persist_fig = _downsample_fig_for_persist(fig)
        js = pio.to_json(persist_fig)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        js = "{}"
    cache[uid] = (id(fig), js)
    return js


def _invalidate_fig_json(uid: str) -> None:
    """Drop the cached JSON for a chart (call when its figure is replaced)."""
    cache = st.session_state.get("_fig_json_cache")
    if cache:
        cache.pop(uid, None)


# ---------------------------------------------------------------------------
# Cached charts->JSON helper (Phase 3: debounced autosave)
# ---------------------------------------------------------------------------
@session_cached
def _charts_json_cached(chart_uids_tuple, notes_hash):
    """Recompute charts_json only when the chart set or notes change."""
    from modules.ui.chart_settings import compute_meta_hash  # local to avoid circular
    # Rebuild the list from session_state live (charts tuple covers identity).
    charts = st.session_state.get("charts", [])
    # Attach fresh meta so the serialized payload is always up-to-date.
    out = []
    for uid, title, fig in charts:
        meta  = _json_safe(st.session_state.get(f"chart_meta_{uid}", {}))
        desc  = st.session_state.get(f"desc_{uid}", "")
        ctype = st.session_state.get(f"chart_type_{uid}", "")
        try:
            out.append({
                "uid":           uid,
                "title":         title,
                "fig_json":      pio.to_json(fig),
                "desc":          desc,
                "chart_type":    ctype,
                "meta":          meta,
            })
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass
    return json.dumps(out)


def charts_json_cached() -> str:
    """Return memoised charts JSON; only serialises when things actually change."""
    charts = st.session_state.get("charts", [])
    chart_sig = tuple(uid for uid, _, _ in charts)
    notes_sig = hash(str(st.session_state.get("_notes_shadow", {})))
    return _charts_json_cached(chart_sig, notes_sig)


# ---------------------------------------------------------------------------
# Persistent save wrappers (use the cached JSON)
# ---------------------------------------------------------------------------
def charts_to_json(charts: list) -> str:
    """Serialise the active chart list to a JSON string for database storage.

    Uses a per-chart memoized ``fig_json`` so unchanged figures are never
    re-serialized, and downsamples large line/scatter traces so the persisted
    payload stays small (fixes the CPU/RAM blow-up on every autosave).
    """
    out = []
    for chart in charts:
        uid, title, fig = chart[:3]
        desc          = st.session_state.get(f"desc_{uid}", "")
        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        meta          = _json_safe(st.session_state.get(f"chart_meta_{uid}", {}))
        try:
            out.append({
                "uid":           uid,
                "title":         title,
                "fig_json":      _fig_json_cached(uid, fig),
                "desc":          desc,
                "chart_type":    chart_type,
                "meta":          meta,
            })
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass
    return json.dumps(out)


# ---------------------------------------------------------------------------
# Existing utilities (unchanged)
# ---------------------------------------------------------------------------
COLORS = ["#6163df", "#8566fc", "#3390c8", "#f59e0b",
          "#ef4444", "#10b981", "#ec4899", "#f97316"]


DANGER = ["#bbf7d0", "#fbbf24", "#ef4444"]


PALETTES = {
    "🔵 Default Blue-Purple": [
        "#6163df", "#8566fc", "#3390c8", "#f59e0b",
        "#ef4444", "#10b981", "#ec4899", "#f97316"
    ],
    "🌈 Vibrant": [
        "#e63946", "#f4a261", "#2a9d8f", "#457b9d",
        "#e9c46a", "#264653", "#a8dadc", "#f1faee"
    ],
    "🍃 Nature Green": [
        "#2d6a4f", "#40916c", "#52b788", "#74c69d",
        "#95d5b2", "#b7e4c7", "#d8f3dc", "#1b4332"
    ],
    "🌅 Warm Sunset": [
        "#e76f51", "#f4a261", "#e9c46a", "#264653",
        "#2a9d8f", "#e63946", "#f1faee", "#457b9d"
    ],
    "🩷 Pink & Coral": [
        "#ff6b6b", "#feca57", "#48dbfb", "#ff9ff3",
        "#54a0ff", "#5f27cd", "#01abc6", "#ff9f43"
    ],
    "🌊 Ocean Blues": [
        "#03045e", "#0077b6", "#00b4d8", "#90e0ef",
        "#caf0f8", "#023e8a", "#0096c7", "#ade8f4"
    ],
    "🟣 Monochrome Purple": [
        "#3c096c", "#5a189a", "#7b2fbe", "#9d4edd",
        "#c77dff", "#e0aaff", "#240046", "#10002b"
    ],
    "🔆 Pastel Light": [
        "#ffadad", "#ffd6a5", "#fdffb6", "#caffbf",
        "#9bf6ff", "#a0c4ff", "#bdb2ff", "#ffc6ff"
    ],
    "✨ Neo Mint": [
        "#14b8a6", "#06b6d4", "#22c55e", "#a3e635",
        "#f59e0b", "#fb7185", "#818cf8", "#0f766e"
    ],
    "⚡ Tech Neon": [
        "#00d1ff", "#7c3aed", "#22c55e", "#f97316",
        "#eab308", "#ec4899", "#38bdf8", "#1d4ed8"
    ],
    "🏙️ Urban Slate": [
        "#0f172a", "#334155", "#475569", "#14b8a6",
        "#3b82f6", "#8b5cf6", "#f59e0b", "#f43f5e"
    ],
    "🌇 Sunset Pro": [
        "#f97316", "#fb7185", "#f59e0b", "#7c3aed",
        "#2563eb", "#14b8a6", "#e11d48", "#0f172a"
    ],
    "🌌 Aurora Glow": [
        "#22c55e", "#06b6d4", "#3b82f6", "#8b5cf6",
        "#ec4899", "#f43f5e", "#f59e0b", "#14b8a6"
    ],
    "💼 Luxe Indigo": [
        "#1e3a8a", "#4338ca", "#6366f1", "#0f766e",
        "#14b8a6", "#d97706", "#db2777", "#334155"
    ],
    "🍊 Tropical Punch": [
        "#f97316", "#f43f5e", "#22c55e", "#06b6d4",
        "#3b82f6", "#a855f7", "#eab308", "#14b8a6"
    ],
    "🎯 Executive Accent": [
        "#1d4ed8", "#0f766e", "#7c3aed", "#d97706",
        "#be123c", "#2563eb", "#059669", "#334155"
    ],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def chart_layout(height: int | None = None) -> dict:
    """Return a dict of Plotly layout kwargs used by every chart in Lytrize."""
    layout = dict(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=20, r=20, t=48, b=20),
        bargap=0.28,
        bargroupgap=0.1,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=True),
        hovermode="closest",
        hoverlabel=dict(
            bgcolor="rgba(18, 26, 45, 0.96)",
            bordercolor="rgba(133, 102, 252, 0.30)",
            font=dict(size=13, color="#f5f7ff", family="Inter, system-ui, sans-serif"),
            namelength=-1,
        ),
    )
    if height is not None:
        layout["height"] = int(height)
    return layout


def apply_hover_format(fig) -> None:
    """Apply K/M/B-formatted hovertemplates to every trace in a Plotly figure."""
    for trace in fig.data:
        existing = getattr(trace, "hovertemplate", None) or ""
        if "customdata" in existing:
            continue

        ttype = type(trace).__name__.lower()

        if ttype == "bar":
            orient = getattr(trace, "orientation", "v") or "v"
            if orient == "h":
                trace.hovertemplate = (
                    "<b>%{y}</b><br>"
                    "Value: <b>%{x:.3~s}</b>"
                    "<extra></extra>"
                )
            else:
                trace.hovertemplate = (
                    "<b>%{x}</b><br>"
                    "Value: <b>%{y:.3~s}</b>"
                    "<extra></extra>"
                )

        elif ttype == "scatter":
            trace_name = getattr(trace, "name", "") or ""
            if trace_name:
                trace.hovertemplate = (
                    f"<b>{trace_name}</b><br>"
                    "%{x}<br>"
                    "Value: <b>%{y:,.2f}</b>"
                    "<extra></extra>"
                )
            else:
                trace.hovertemplate = (
                    "<b>%{x}</b><br>"
                    "Value: <b>%{y:,.2f}</b>"
                    "<extra></extra>"
                )

        elif ttype == "histogram":
            trace.hovertemplate = (
                "Range: <b>%{x}</b><br>"
                "Count: <b>%{y:.3~s}</b>"
                "<extra></extra>"
            )

        elif ttype in ("pie", "sunburst"):
            trace.hovertemplate = (
                "<b>%{label}</b><br>"
                "Value: <b>%{value:.3~s}</b><br>"
                "Share: %{percent}"
                "<extra></extra>"
            )

        elif ttype == "heatmap":
            trace.hovertemplate = (
                "%{x} × %{y}<br>"
                "r = <b>%{z:.3f}</b>"
                "<extra></extra>"
            )


def _cached_col_types():
    """Return (num_cols, cat_cols, dt_cols) with a session-state cache keyed on _df_version.
    
    Avoids three separate st.session_state.get() calls on every analysis config render.
    """
    _cache_key = "_cached_col_types"
    _ver_key   = "_cached_col_types_ver"
    _df_ver    = st.session_state.get("_df_version", 0)
    if st.session_state.get(_ver_key) == _df_ver and _cache_key in st.session_state:
        return st.session_state[_cache_key]
    result = (
        st.session_state.get("num_cols", []),
        st.session_state.get("cat_cols", []),
        st.session_state.get("dt_cols", []),
    )
    st.session_state[_cache_key] = result
    st.session_state[_ver_key]   = _df_ver
    return result


def num_cols() -> list:
    """Return the list of confirmed numeric column names."""
    return _cached_col_types()[0]


def cat_cols() -> list:
    """Return the list of confirmed categorical column names."""
    return _cached_col_types()[1]


def dt_cols() -> list:
    """Return the list of confirmed datetime column names."""
    return _cached_col_types()[2]


def _fmt_num(value) -> str:
    """Format a numeric value with K/M/B suffixes and thousand separators."""
    try:
        v = float(value)
    except Exception:
        return str(value)
    if pd.isna(v):
        return "n/a"
    sign = "-" if v < 0 else ""
    av = abs(v)
    if av >= 1_000_000_000: return f"{sign}{av / 1_000_000_000:.1f}B"
    if av >= 1_000_000:     return f"{sign}{av / 1_000_000:.1f}M"
    if av >= 1_000:         return f"{sign}{av / 1_000:.1f}K"
    if av == int(av):       return f"{int(v):,}"
    return f"{v:,.2f}"


def _fmt_pct(value) -> str:
    """Format a value as a signed percentage string."""
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return "n/a"


def _plural(count, singular: str, plural: str = None) -> str:
    """Return singular or plural form based on count."""
    return singular if int(count) == 1 else (plural or f"{singular}s")


def _fmt_label(value) -> str:
    """Format a value as a human-readable date/time label if possible."""
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.notna(ts):
            if ts.hour or ts.minute or ts.second:
                return ts.strftime("%d %b %Y %H:%M")
            return ts.strftime("%d %b %Y")
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass
    return str(value)


def _as_number_series(values) -> pd.Series:
    """Convert values to a numeric Series, coercing errors to NaN and dropping them."""
    return pd.to_numeric(pd.Series(values), errors="coerce").dropna()


def _as_list(values) -> list:
    """Convert any iterable to a list, returning an empty list on failure."""
    if values is None:
        return []
    try:
        return list(values)
    except Exception:
        return []


