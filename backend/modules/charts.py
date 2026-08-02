"""modules/charts.py -- Shared chart utilities, palettes, and the auto-insight engine."""
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
        auto  = st.session_state.get(f"auto_insights_{uid}", [])
        ctype = st.session_state.get(f"chart_type_{uid}", "")
        try:
            out.append({
                "uid":           uid,
                "title":         title,
                "fig_json":      pio.to_json(fig),
                "desc":          desc,
                "auto_insights": clean_insights(auto),
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
    """Serialise the active chart list to a JSON string for database storage."""
    out = []
    for chart in charts:
        uid, title, fig = chart[:3]
        desc          = st.session_state.get(f"desc_{uid}", "")
        auto_insights = clean_insights(st.session_state.get(f"auto_insights_{uid}", []))
        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        meta          = _json_safe(st.session_state.get(f"chart_meta_{uid}", {}))
        try:
            out.append({
                "uid":           uid,
                "title":         title,
                "fig_json":      pio.to_json(fig),
                "desc":          desc,
                "auto_insights": auto_insights,
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


def clean_insight_text(text) -> str:
    """Strip markdown bold markers and normalise spacing from insight text."""
    s = str(text or "")
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = s.replace("__", "")
    s = s.replace("  ·  ", " · ")
    return s.strip()


def clean_insights(insights) -> list:
    """Clean a list of insight strings, removing empty entries."""
    return [s for s in (clean_insight_text(i) for i in (insights or [])) if s]


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


def generate_chart_insights(chart_type: str, title: str, fig,
                             col_descriptions: dict = None) -> list:
    """Produce plain-English observations from a Plotly figure."""
    insights = []
    tl = title.lower()
    col_desc = col_descriptions or {}

    def _named(col: str) -> str:
        desc = col_desc.get(col, "").strip()
        if desc:
            short = desc[:55] + "…" if len(desc) > 55 else desc
            return f"{col} ({short})"
        return col

    def _primary_col_from_title() -> str:
        for prefix in ("Dist: ", "TS: ", "Outliers: ", "Trend: ",
                       "Counts: ", "Time Series: "):
            if title.startswith(prefix):
                return title[len(prefix):]
        return ""

    def _cols_in_title() -> list:
        return [c for c in col_desc if c and c.lower() in tl and col_desc[c].strip()]

    def _append_desc_context():
        relevant = _cols_in_title()
        for col in relevant:
            desc = col_desc[col].strip()
            if desc and col not in " ".join(insights):
                insights.append(f"Column context — {col}: {desc}")

    # ----- distribution -----
    if chart_type == "distribution" or "dist:" in tl:
        try:
            arr = _as_number_series(fig.data[0].x)
            if arr.empty:
                return []
            col = _primary_col_from_title() or "this column"
            mean, median, std = arr.mean(), arr.median(), arr.std()
            skew = float(arr.skew())

            insights.append(
                f"{_named(col)} centres around {_fmt_num(median)} "
                f"(median). The average is {_fmt_num(mean)}, "
                f"with a typical spread of ±{_fmt_num(std)}."
            )

            if abs(skew) > 1.5:
                if skew > 0:
                    insights.append(
                        "A small number of unusually high values are pulling the average "
                        "above the typical case — the median is the more reliable benchmark here."
                    )
                else:
                    insights.append(
                        "A few very low values are dragging the average down — "
                        "the median gives a fairer picture of the typical record."
                    )
            elif abs(skew) > 0.5:
                direction = "higher" if skew > 0 else "lower"
                insights.append(
                    f"The distribution leans slightly {direction}, "
                    "so averages and medians tell a similar but not identical story."
                )
            else:
                insights.append(
                    "Values are symmetrically distributed — the average and median "
                    "are close, making either a reliable summary."
                )

            q1, q3 = arr.quantile(0.25), arr.quantile(0.75)
            iqr = q3 - q1
            n_out = int(((arr < q1 - 1.5 * iqr) | (arr > q3 + 1.5 * iqr)).sum())
            if n_out > 0:
                pct_out = n_out / len(arr) * 100
                insights.append(
                    f"{n_out:,} {_plural(n_out, 'value')} ({pct_out:.1f}%) "
                    f"{'sits' if n_out == 1 else 'sit'} outside the normal range — "
                    "check these before using totals or averages in reports."
                )

            p10, p90 = arr.quantile(0.10), arr.quantile(0.90)
            insights.append(
                f"The middle 80% of records fall between "
                f"{_fmt_num(p10)} and {_fmt_num(p90)}."
            )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

    # ----- correlation -----
    elif chart_type == "correlation" or "correlation" in tl:
        try:
            z        = fig.data[0].z
            x_labels = _as_list(getattr(fig.data[0], "x", None))
            y_labels = _as_list(getattr(fig.data[0], "y", None)) or x_labels
            if z is not None:
                best = None
                for r, row in enumerate(z):
                    for c, val in enumerate(row):
                        if r == c or val is None:
                            continue
                        try:
                            fv = float(val)
                        except Exception:
                            continue
                        if abs(fv) >= 1:
                            continue
                        if best is None or abs(fv) > abs(best[0]):
                            left  = str(y_labels[r]) if r < len(y_labels) else f"Column {r+1}"
                            right = str(x_labels[c]) if c < len(x_labels) else f"Column {c+1}"
                            best  = (fv, left, right)
                if best:
                    strength  = ("strong" if abs(best[0]) >= 0.7
                                 else "moderate" if abs(best[0]) >= 0.4 else "weak")
                    direction = ("tend to rise together"   if best[0] > 0
                                 else "move in opposite directions")
                    insights.append(
                        f"{_named(best[1])} and {_named(best[2])} show the "
                        f"strongest link: {strength} ({best[0]:+.2f}) — they {direction}."
                    )
                    if abs(best[0]) >= 0.7:
                        insights.append(
                            "A correlation above 0.7 is worth investigating for a "
                            "cause-and-effect relationship, though correlation alone "
                            "does not prove causation."
                        )
                else:
                    insights.append(
                        "No clear relationship stands out. "
                        "The selected columns appear largely independent of each other."
                    )

            try:
                strong_pairs, total_pairs = 0, 0
                for r, row in enumerate(z):
                    for c_idx, val in enumerate(row):
                        if r >= c_idx or val is None:
                            continue
                        try:
                            fv = float(val)
                            total_pairs += 1
                            if abs(fv) >= 0.6:
                                strong_pairs += 1
                        except Exception as exc:
                            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                            pass
                if total_pairs > 1:
                    insights.append(
                        f"{strong_pairs} of {total_pairs} column pairs "
                        f"{'has' if strong_pairs == 1 else 'have'} a correlation "
                        "above 0.6 — scan the darkest cells for the most actionable links."
                    )
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass

            insights.append(
                "Correlation shows association, not causation — use it as a lead for deeper investigation."
            )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

    # ----- outlier -----
    elif chart_type == "outlier" or "outlier" in tl:
        try:
            col = _primary_col_from_title() or "this column"
            outlier_trace = next(
                (t for t in fig.data
                 if "outlier" in str(getattr(t, "name", "")).lower()), None)
            normal_trace = next(
                (t for t in fig.data
                 if "normal" in str(getattr(t, "name", "")).lower()), None)

            total_pts = sum(
                len(getattr(t, "y", None) or []) for t in fig.data
                if getattr(t, "y", None) is not None
            )

            if outlier_trace and len(getattr(outlier_trace, "y", []) or []) > 0:
                n    = len(outlier_trace.y)
                vals = _as_number_series(outlier_trace.y)
                pct  = n / total_pts * 100 if total_pts > 0 else 0
                if not vals.empty:
                    insights.append(
                        f"{_named(col)} has {n:,} {_plural(n, 'outlier')} "
                        f"({pct:.1f}% of records), ranging from "
                        f"{_fmt_num(vals.min())} to {_fmt_num(vals.max())}."
                    )
                else:
                    insights.append(
                        f"{_named(col)}: {n:,} {_plural(n, 'outlier')} detected "
                        f"({pct:.1f}% of records)."
                    )
                if pct > 10:
                    insights.append(
                        "Over 10% of records are flagged — this may indicate a "
                        "measurement scale issue, data-entry errors, or a genuine "
                        "multi-modal distribution. Review before computing averages."
                    )
                elif n > 5:
                    insights.append(
                        "Check these rows individually — they could be data-entry "
                        "mistakes or legitimately exceptional events worth noting."
                    )
                else:
                    insights.append(
                        "A small number of outliers. Inspect each one; a single "
                        "extreme value can shift averages and totals significantly."
                    )
            else:
                insights.append(
                    f"No outliers detected in {_named(col)} — the data looks clean."
                )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

    # ----- time series -----
    elif chart_type == "time_series" or "ts:" in tl or "trend" in tl:
        try:
            col = _primary_col_from_title() or "the metric"
            y = _as_number_series(fig.data[0].y)
            x_vals = _as_list(getattr(fig.data[0], "x", None))
            if len(y) >= 2:
                trend = ("increased" if y.iloc[-1] > y.iloc[0]
                         else "decreased" if y.iloc[-1] < y.iloc[0] else "stayed flat")
                pct = ((y.iloc[-1] - y.iloc[0]) / abs(y.iloc[0]) * 100
                       if y.iloc[0] != 0 else 0)
                insights.append(
                    f"{_named(col)} {trend} overall — "
                    f"from {_fmt_num(y.iloc[0])} to {_fmt_num(y.iloc[-1])} "
                    f"({_fmt_pct(pct)} change from first to last period)."
                )

                peak_i = int(y.reset_index(drop=True).idxmax())
                low_i  = int(y.reset_index(drop=True).idxmin())
                peak_x = f" at {_fmt_label(x_vals[peak_i])}" if peak_i < len(x_vals) else ""
                low_x  = f" at {_fmt_label(x_vals[low_i])}"  if low_i  < len(x_vals) else ""
                insights.append(
                    f"Peak: {_fmt_num(y.max())}{peak_x}. "
                    f"Lowest: {_fmt_num(y.min())}{low_x}. "
                    f"The range spans {_fmt_num(y.max() - y.min())}."
                )

                cv = y.std() / abs(y.mean()) if y.mean() != 0 else 0
                if cv > 0.5:
                    insights.append(
                        "High variability across periods — look for recurring "
                        "seasonal patterns or one-off spikes before using this trend "
                        "for forecasting."
                    )
                elif cv < 0.1:
                    insights.append(
                        "Very consistent across periods — a reliable baseline for benchmarking or targets."
                    )
                else:
                    insights.append(
                        "Moderate variability — look for repeating peaks or dips that could signal seasonality."
                    )
        except Exception:
            insights.append(
                "Look for repeating peaks or dips; those often point to "
                "seasonality or operating patterns."
            )

    # ----- categorical / pie -----
    elif (chart_type in ("categorical", "pie_chart")
          or any(k in tl for k in ("count", "bar", "pie", "donut"))):
        try:
            data = fig.data[0]
            is_horiz = getattr(data, "orientation", "v") == "h"
            if is_horiz:
                vals = [v for v in _as_list(getattr(data, "x", None)) if v is not None]
                xs   = _as_list(getattr(data, "y", None))
            elif (hasattr(data, "y") and data.y is not None
                  and not isinstance(data.y[0] if len(data.y) else 0, str)):
                vals = [v for v in _as_list(data.y) if v is not None]
                xs   = _as_list(getattr(data, "x", None))
            elif hasattr(data, "values") and data.values is not None:
                vals = _as_list(data.values)
                xs   = _as_list(getattr(data, "labels", None))
            else:
                vals = [v for v in _as_list(getattr(data, "x", None))
                        if isinstance(v, (int, float))]
                xs   = _as_list(getattr(data, "y", None))

            if vals:
                vals    = [float(v) for v in vals]
                total   = sum(v for v in vals if v)
                top_i   = vals.index(max(vals))
                bot_i   = vals.index(min(vals))
                top_cat = xs[top_i] if xs and top_i < len(xs) else str(top_i)
                bot_cat = xs[bot_i] if xs and bot_i < len(xs) else str(bot_i)
                top_pct = (max(vals) / total * 100) if total else 0

                cat_col = next((c for c in col_desc if c.lower() in tl), "")
                cat_ctx = f" ({col_desc[cat_col].strip()[:50]})" if cat_col and col_desc.get(cat_col) else ""
                insights.append(
                    f"{top_cat}{cat_ctx} leads at {_fmt_num(max(vals))}, "
                    f"representing {top_pct:.1f}% of the total."
                )

                n_cats = len(vals)
                if n_cats > 1:
                    sorted_vals = sorted(vals, reverse=True)
                    if len(sorted_vals) > 1 and sorted_vals[1]:
                        ratio = sorted_vals[0] / sorted_vals[1]
                        if ratio >= 2:
                            insights.append(
                                f"The top category is {ratio:.1f}× the second — "
                                "a clear leader with a significant gap."
                            )
                        elif ratio >= 1.1:
                            insights.append(
                                f"The leader is {ratio:.1f}× the next category — "
                                "a meaningful but not extreme gap."
                            )

                    even_pct      = 100 / n_cats
                    concentration = max(vals) / total * 100
                    if concentration > 2.5 * even_pct:
                        insights.append(
                            f"Highly concentrated — a single category holds "
                            f"{top_pct:.0f}% of the total across {n_cats} options. "
                            "This creates dependency risk."
                        )
                    elif concentration < 1.5 * even_pct:
                        insights.append(
                            f"Values are evenly spread across {n_cats} categories "
                            "— no single category dominates."
                        )

                    if total and min(vals) > 0:
                        bot_pct = (min(vals) / total * 100)
                        if max(vals) / max(min(vals), 1) >= 3:
                            insights.append(
                                f"Lowest: **{bot_cat}** at {_fmt_num(min(vals))} ({bot_pct:.1f}%) — "
                                "a significant gap from the top; worth investigating if this is expected."
                            )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

    # ----- scatter -----
    elif chart_type in ("scatter", "scatter_plot") or "scatter:" in tl:
        try:
            cols_match = re.search(r"Scatter:\s*(.+?)\s+vs\s+(.+?)(\s|$|·|—)", title)
            x_col = cols_match.group(1).strip() if cols_match else "X"
            y_col = cols_match.group(2).strip() if cols_match else "Y"

            # Read trendline metadata from fig._lytrize_trendline (set by
            # scatter_plot._add_trendline).  This is the single source of
            # truth — it contains the actual computed values rather than
            # relying on regex-parsing trace names.
            _tl_meta = getattr(fig, "_lytrize_trendline", None) or {}
            _tl_active = _tl_meta.get("active", False)
            _tl_type   = _tl_meta.get("type", "")
            _tl_n_pts  = _tl_meta.get("n_points", 0)

            # Fallback: detect trendline from trace names (for charts
            # generated before _lytrize_trendline was introduced).
            if not _tl_active:
                for _t in fig.data:
                    _mode = str(getattr(_t, "mode", ""))
                    _name = str(getattr(_t, "name", "")).lower()
                    if "lines" in _mode and "markers" not in _mode:
                        if "trend" in _name or "=" in _name:
                            _tl_active = True
                            _tl_type = "ols" if "=" in _name else "lowess"
                            break

            # Read r from title (set by scatter_plot runner)
            r_match = re.search(r"r\s*=\s*([+-]?\d+\.\d+)", title)
            r_val   = float(r_match.group(1)) if r_match else None

            scatter_trace = next(
                (t for t in fig.data if "markers" in str(getattr(t, "mode", ""))), None)

            # ── Trendline overview (the main insight) ──
            if _tl_active and _tl_type == "ols":
                slope     = _tl_meta.get("slope")
                intercept = _tl_meta.get("intercept")
                r_sq      = _tl_meta.get("r_squared")
                r_tl      = _tl_meta.get("r_value")
                std_err   = _tl_meta.get("std_err")
                within_1s = _tl_meta.get("within_one_sigma")

                # Use trendline's own r if available (more precise), else title r
                _r = r_tl if r_tl is not None else r_val

                if _r is not None:
                    strength  = "strong" if abs(_r) >= 0.7 else "moderate" if abs(_r) >= 0.4 else "weak"
                    direction = "positive" if _r > 0 else "negative"
                    insights.append(
                        f"{_named(x_col)} and {_named(y_col)} show a {strength} {direction} "
                        f"link (r = {_r:+.3f})."
                    )

                if r_sq is not None:
                    insights.append(
                        f"The trendline explains **{r_sq * 100:.1f}%** of the variance "
                        f"in {_named(y_col)} (R² = {r_sq:.3f})."
                    )

                if slope is not None:
                    direction_word = "increases" if slope > 0 else "decreases"
                    insights.append(
                        f"On average, each 1-unit increase in {_named(x_col)} is associated with "
                        f"{_named(y_col)} {direction_word}ing by {abs(slope):.3g}."
                    )

                if intercept is not None:
                    insights.append(
                        f"When {_named(x_col)} is near zero, {_named(y_col)} is approximately "
                        f"{intercept:,.3g} (the intercept)."
                    )

                if within_1s is not None and _tl_n_pts > 0:
                    pct_close = within_1s / _tl_n_pts * 100
                    insights.append(
                        f"About **{pct_close:.0f}%** of points ({within_1s:,} of {_tl_n_pts:,}) "
                        f"fall within one standard error of the trendline — "
                        f"{'a tight fit suggesting the line is a reliable summary.' if pct_close >= 68 else 'moderate scatter around the line.' if pct_close >= 50 else 'wide scatter — the line shows direction but individual predictions will vary.'}"
                    )

                if _r is not None and abs(_r) >= 0.7:
                    insights.append(
                        "A strong link suggests a predictable pattern — when one moves, the other usually follows. "
                        "Check whether this is a direct cause or influenced by a third factor."
                    )
                elif _r is not None and abs(_r) >= 0.4:
                    insights.append(
                        "A moderate link exists. The two variables tend to move together, "
                        "but other factors also play a role."
                    )
                elif _r is not None:
                    insights.append(
                        "The link is weak — these variables move largely on their own. "
                        "A curved or more complex pattern may still be present."
                    )

            elif _tl_active and _tl_type == "lowess":
                r_sq_raw = _tl_meta.get("r_squared_raw")
                insights.append(
                    f"A LOWESS smooth trendline is fitted, following the natural shape of the data. "
                    f"Where it bends, the relationship between {_named(x_col)} and {_named(y_col)} changes."
                )
                if r_sq_raw is not None:
                    insights.append(
                        f"The smoothed line explains roughly **{r_sq_raw * 100:.0f}%** of the "
                        f"variance — a higher percentage means the curve captures the pattern well."
                    )
                insights.append(
                    f"Where the line flattens, {_named(y_col)} stops responding to {_named(x_col)} — "
                    "a potential saturation or threshold effect."
                )

            elif not _tl_active and r_val is not None:
                # No trendline fitted, but we have correlation from the title
                strength  = "strong" if abs(r_val) >= 0.7 else "moderate" if abs(r_val) >= 0.4 else "weak"
                direction = "positive" if r_val > 0 else "negative"
                insights.append(
                    f"{_named(x_col)} and {_named(y_col)} show a {strength} {direction} "
                    f"correlation (r = {r_val:+.3f}). Add a trendline to quantify the relationship."
                )

            elif not _tl_active:
                insights.append(
                    f"No trendline fitted yet. Add a straight line to quantify the overall direction, "
                    "or a smooth line to reveal curved patterns."
                )

            # ── Data point summary ──
            if scatter_trace:
                n_pts = len(getattr(scatter_trace, "x", []) or [])
                if n_pts:
                    insights.append(f"Chart shows {n_pts:,} data points.")
                    if n_pts >= 7_000:
                        insights.append(
                            "Large sample — dense overplotting may hide structure. "
                            "Try colouring by a category column to separate groups."
                        )

        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

        if not insights:
            insights.append(
                f"Scatter plot generated. Explore the relationship between the "
                "X and Y axes — add a trendline to reveal the pattern."
            )

    # ----- map -----
    elif chart_type == "map_plot" or "map:" in tl:
        pass  # No auto-insights for map charts

    # ----- matrix -----
    elif chart_type in ("matrix_heatmap", "matrix_table") or "matrix" in tl:
        pass  # No auto-insights for matrix heatmaps/tables

    # ----- statistical -----
    elif (chart_type == "statistical"
          or any(k in tl for k in ("mean", "std", "min", "max"))):
        try:
            data   = fig.data[0]
            vals   = _as_number_series(getattr(data, "y", []))
            labels = _as_list(getattr(data, "x", None))
            if not vals.empty:
                top_i     = int(vals.reset_index(drop=True).idxmax())
                bot_i     = int(vals.reset_index(drop=True).idxmin())
                top_label = labels[top_i] if top_i < len(labels) else "The highest item"
                bot_label = labels[bot_i] if bot_i < len(labels) else "The lowest item"
                insights.append(
                    f"{_named(top_label)} is the highest at {_fmt_num(vals.max())}; "
                    f"{_named(bot_label)} is the lowest at {_fmt_num(vals.min())}."
                )
                val_range = vals.max() - vals.min()
                if val_range > 0:
                    insights.append(
                        f"The gap between top and bottom is {_fmt_num(val_range)} — "
                        f"a {val_range / vals.min() * 100:.0f}% difference from the lowest."
                        if vals.min() != 0 else
                        f"The gap between top and bottom is {_fmt_num(val_range)}."
                    )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass
        if not insights:
            insights.append(
                "Compare the largest and smallest values first — "
                "they usually explain the main story."
            )

    # ----- data quality -----
    elif (chart_type == "data_quality"
          or any(k in tl for k in ("missing", "duplicate", "quality"))):
        try:
            data = fig.data[0]
            if hasattr(data, "labels") and hasattr(data, "values"):
                labels = list(data.labels)
                vals   = [float(v) for v in data.values]
                total  = sum(vals)
                details = [
                    f"{label}: {_fmt_num(val)} ({val/total*100:.1f}%)"
                    for label, val in zip(labels, vals)
                ]
                if details:
                    insights.append("Data quality split — " + "; ".join(details) + ".")
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass
        insights.append(
            "Resolve missing or duplicate rows before using these charts for decisions."
        )

    if col_desc:
        mentioned = " ".join(insights).lower()
        for col, desc in col_desc.items():
            if col and desc.strip() and col.lower() in tl and desc.strip().lower() not in mentioned:
                insights.append(f"Column context — {col}: {desc.strip()}")

    return clean_insights(insights)
