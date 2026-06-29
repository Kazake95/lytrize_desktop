"""modules/charts.py -- Shared chart utilities, palettes, and the auto-insight engine."""


import json
import re
import streamlit as st
import pandas as pd
import plotly.io as pio




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
            trace.hovertemplate = (
                "<b>%{x}</b><br>"
                "Value: <b>%{y:.3~s}</b>"
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




def num_cols() -> list:
    """Return the list of numeric column names confirmed by the user."""
    return st.session_state.get("num_cols", [])


def cat_cols() -> list:
    """Return the list of categorical column names confirmed by the user."""
    return st.session_state.get("cat_cols", [])


def dt_cols() -> list:
    """Return the list of date/time column names confirmed by the user."""
    return st.session_state.get("dt_cols", [])




def clean_insight_text(text) -> str:
    """Strip Markdown formatting from an auto-generated insight string."""
    s = str(text or "")
    s = re.sub(r"\*\*(.*?)\*\*", r"\1", s)
    s = s.replace("__", "")
    s = s.replace("  ·  ", " · ")
    return s.strip()




def clean_insights(insights) -> list:
    """Clean and filter a list of raw insight strings. Removes empty entries."""
    return [s for s in (clean_insight_text(i) for i in (insights or [])) if s]




def _fmt_num(value) -> str:
    """Format a number as a compact, human-readable string."""
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
    """Format a float as a percentage string with sign: 0.123 → '+12.3%'."""
    try:
        return f"{float(value):+.1f}%"
    except Exception:
        return "n/a"




def _plural(count, singular: str, plural: str = None) -> str:
    """Return singular or plural noun based on count."""
    return singular if int(count) == 1 else (plural or f"{singular}s")




def _fmt_label(value) -> str:
    """Format a value as a readable label, auto-detecting datetime strings."""
    try:
        ts = pd.to_datetime(value, errors="coerce")
        if pd.notna(ts):
            if ts.hour or ts.minute or ts.second:
                return ts.strftime("%d %b %Y %H:%M")
            return ts.strftime("%d %b %Y")
    except Exception:
        pass
    return str(value)




def _as_number_series(values) -> pd.Series:
    """Coerce any iterable of values to a numeric pd.Series, dropping non-numeric."""
    return pd.to_numeric(pd.Series(values), errors="coerce").dropna()




def _as_list(values) -> list:
    """Safely convert any value to a plain Python list. Returns [] on failure."""
    if values is None:
        return []
    try:
        return list(values)
    except Exception:
        return []




def charts_to_json(charts: list) -> str:
    """Serialise the active chart list to a JSON string for database storage."""
    out = []
    for chart in charts:
        uid, title, fig = chart[:3]
        desc          = st.session_state.get(f"desc_{uid}", "")
        auto_insights = clean_insights(st.session_state.get(f"auto_insights_{uid}", []))
        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        meta          = st.session_state.get(f"chart_meta_{uid}", {})
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
        except Exception:
            pass
    return json.dumps(out)




def generate_chart_insights(chart_type: str, title: str, fig,
                             col_descriptions: dict = None) -> list:
    """Produce plain-English observations from a Plotly figure."""
    insights = []
    tl = title.lower()
    col_desc = col_descriptions or {}




    def _named(col: str) -> str:
        """Return 'col (description)' when a description exists, else 'col'."""
        desc = col_desc.get(col, "").strip()
        if desc:
            short = desc[:55] + "…" if len(desc) > 55 else desc
            return f"{col} ({short})"
        return col


    def _primary_col_from_title() -> str:
        """Extract the primary column name from known title prefixes."""
        for prefix in ("Dist: ", "TS: ", "Outliers: ", "Trend: ",
                       "Counts: ", "Time Series: "):
            if title.startswith(prefix):
                return title[len(prefix):]
        return ""


    def _cols_in_title() -> list:
        """Return all col_description keys whose name appears in the chart title."""
        return [c for c in col_desc if c and c.lower() in tl and col_desc[c].strip()]


    def _append_desc_context():
        """Append a short 'What these columns mean' footnote for any columns"""
        relevant = _cols_in_title()
        for col in relevant:
            desc = col_desc[col].strip()
            if desc and col not in " ".join(insights):
                insights.append(f"Column context — {col}: {desc}")


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
        except Exception:
            pass


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
                        except Exception:
                            pass
                if total_pairs > 1:
                    insights.append(
                        f"{strong_pairs} of {total_pairs} column pairs "
                        f"{'has' if strong_pairs == 1 else 'have'} a correlation "
                        f"above 0.6 — scan the darkest cells for the most actionable links."
                    )
            except Exception:
                pass


            insights.append(
                "Correlation shows association, not causation — use it as a lead for deeper investigation."
            )
        except Exception:
            pass


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
                    f"No outliers detected in {_named(col)} using the standard "
                    "IQR (1.5× interquartile range) threshold. The data looks clean."
                )
        except Exception:
            pass


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
        except Exception:
            pass


    elif chart_type in ("scatter", "scatter_plot") or "scatter:" in tl:
        try:
            cols_match = re.search(r"Scatter:\s*(.+?)\s+vs\s+(.+?)(\s|$|·|—)", title)
            x_col = cols_match.group(1).strip() if cols_match else "X"
            y_col = cols_match.group(2).strip() if cols_match else "Y"


            has_ols    = False
            has_lowess = False
            ols_slope  = None
            for _t in fig.data:
                _mode = str(getattr(_t, "mode", ""))
                _name = str(getattr(_t, "name", "")).lower()
                if "lines" in _mode and "markers" not in _mode:
                    if "ols" in _name or "=" in _name or "trendline" in _name:
                        has_ols = True
                        _slope_m = re.search(r"y\s*=\s*([+-]?[\d.]+)x", _name)
                        if _slope_m:
                            try: ols_slope = float(_slope_m.group(1))
                            except Exception: pass
                    else:
                        has_lowess = True


            r_match = re.search(r"r\s*=\s*([+-]?\d+\.\d+)", title)
            r_val   = float(r_match.group(1)) if r_match else None


            scatter_trace = next(
                (t for t in fig.data if "markers" in str(getattr(t, "mode", ""))), None)


            if r_val is not None:
                strength  = "strong" if abs(r_val) >= 0.7 else "moderate" if abs(r_val) >= 0.4 else "weak"
                direction = "positive" if r_val > 0 else "negative"
                insights.append(
                    f"{_named(x_col)} and {_named(y_col)} show a {strength} {direction} "
                    f"linear correlation (r = {r_val:+.3f})."
                )
                if abs(r_val) >= 0.7:
                    insights.append(
                        "A strong correlation suggests a predictable relationship — "
                        "consider a regression model, but verify causality before acting."
                    )
                elif abs(r_val) >= 0.4:
                    insights.append(
                        "A moderate correlation exists. The relationship may be real "
                        "but is likely influenced by other variables — check for confounders."
                    )
                else:
                    insights.append(
                        "The weak linear correlation suggests these variables move largely "
                        "independently. A non-linear pattern may still exist — the LOWESS "
                        "trendline option can reveal curved relationships."
                    )


            if has_ols:
                if ols_slope is not None:
                    direction_word = "increases" if ols_slope > 0 else "decreases"
                    insights.append(
                        f"OLS trendline: each 1-unit increase in {_named(x_col)} is associated with "
                        f"{_named(y_col)} {direction_word}ing by {abs(ols_slope):.3g} on average."
                    )
                else:
                    insights.append("OLS (best-fit straight line) trendline fitted.")
                insights.append(
                    "Points far from the OLS line are outliers or high-leverage observations."
                )


            if has_lowess:
                insights.append(
                    "LOWESS trendline fitted — it follows the local shape of the data. "
                    "Bends in the curve indicate non-linear relationships a straight-line model would miss."
                )
                insights.append(
                    f"Where the LOWESS curve flattens, {_named(y_col)} stops responding to {_named(x_col)} — "
                    "a potential saturation or threshold effect."
                )


            if not has_ols and not has_lowess and r_val is None:
                insights.append(
                    f"No trendline fitted yet. Add OLS to quantify a linear relationship, "
                    "or LOWESS to reveal curved patterns."
                )


            if scatter_trace:
                n_pts = len(getattr(scatter_trace, "x", []) or [])
                if n_pts:
                    insights.append(f"Chart shows {n_pts:,} data points.")
                    if n_pts >= 7_000:
                        insights.append(
                            "Large sample — dense overplotting may hide structure. "
                            "Try colouring by a category column to separate groups."
                        )


        except Exception:
            pass


        if not insights:
            insights.append(
                f"Scatter plot generated. Explore the relationship between the "
                "X and Y axes — add a trendline to quantify the pattern."
            )


    elif chart_type == "map_plot" or "map:" in tl:
        try:
            map_trace = fig.data[0] if fig.data else None
            if map_trace:
                lats = _as_number_series(getattr(map_trace, "lat", []) or [])
                lons = _as_number_series(getattr(map_trace, "lon", []) or [])
                n_pts = len(lats)


                if n_pts:
                    insights.append(f"Map shows {n_pts:,} location point(s).")


                if len(lats) >= 2:
                    lat_spread = float(lats.max() - lats.min())
                    lon_spread = float(lons.max() - lons.min())
                    if lat_spread < 2 and lon_spread < 2:
                        insights.append(
                            "Points are geographically concentrated — zoom in "
                            "for detailed cluster analysis."
                        )
                    elif lat_spread > 50 or lon_spread > 50:
                        insights.append(
                            "Data spans a wide geographic area — "
                            "consider filtering by region for more focused analysis."
                        )


                color_col = next(
                    (c for c in col_desc if c.lower() in tl.lower()), None)
                if color_col and col_desc.get(color_col):
                    insights.append(
                        f"Colour column context — {color_col}: "
                        f"{col_desc[color_col].strip()[:80]}"
                    )
        except Exception:
            pass


    elif chart_type in ("matrix_heatmap", "matrix_table") or "matrix" in tl:
        try:
            heat_trace = next(
                (t for t in fig.data
                 if type(t).__name__.lower() == "heatmap"), None)
            tbl_trace  = next(
                (t for t in fig.data
                 if type(t).__name__.lower() == "table"), None)


            if heat_trace:
                z = heat_trace.z
                if z is not None:
                    flat = [v for row in z for v in (row or [])
                            if v is not None and not (isinstance(v, float) and v != v)]
                    flat_nums = _as_number_series(flat)
                    if not flat_nums.empty:
                        vmax = float(flat_nums.max())
                        vmin = float(flat_nums.min())
                        insights.append(
                            f"Values range from {_fmt_num(vmin)} to {_fmt_num(vmax)}. "
                            "The darkest cells show the highest aggregated values."
                        )
                        x_labels = _as_list(getattr(heat_trace, "x", None))
                        y_labels = _as_list(getattr(heat_trace, "y", None))
                        best_r, best_c, best_v = None, None, None
                        for ri, row in enumerate(z):
                            for ci, v in enumerate(row or []):
                                if v is not None and not (isinstance(v, float) and v != v):
                                    if best_v is None or float(v) > best_v:
                                        best_r, best_c, best_v = ri, ci, float(v)
                        if best_r is not None and x_labels and y_labels:
                            row_lbl = str(y_labels[best_r]) if best_r < len(y_labels) else f"Row {best_r}"
                            col_lbl = str(x_labels[best_c]) if best_c < len(x_labels) else f"Col {best_c}"
                            insights.append(
                                f"Hotspot: {row_lbl} × {col_lbl} = {_fmt_num(best_v)} — "
                                "highest aggregated value in the matrix."
                            )
                        n_total = sum(len(row or []) for row in z)
                        n_blank = sum(
                            1 for row in z for v in (row or [])
                            if v is None or (isinstance(v, float) and v != v)
                        )
                        if n_total and n_blank / n_total > 0.25:
                            insights.append(
                                f"{n_blank / n_total:.0%} of cells are empty — "
                                "sparse combinations might need more data or broader groupings."
                            )


            elif tbl_trace:
                n_rows_t = len((tbl_trace.cells.values[0] or []) if tbl_trace.cells else [])
                insights.append(
                    f"Pivot table shows {n_rows_t} row(s). "
                    "Sort by column average to find the highest-performing categories."
                )
        except Exception:
            pass


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
        except Exception:
            pass
        if not insights:
            insights.append(
                "Compare the largest and smallest values first — "
                "they usually explain the main story."
            )


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
        except Exception:
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
