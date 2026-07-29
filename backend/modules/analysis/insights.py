"""modules/analysis/insights.py — Enterprise-Grade Auto-Insights Engine

Produces plain-English, first-view chart summaries for non-technical users.
Every insight function returns a ``list[str]`` where each string may contain
``**bold**`` Markdown (stripped by ``clean_insight_text`` at render time).

Public API (imported by other modules):
    - generate_insights(analysis_type, df, uid, **kwargs) -> list[str]
    - outlier_insights(col, info) -> list[str]
"""

from __future__ import annotations
import logging

import numpy as np
import pandas as pd


# ═══════════════════════════════════════════════════════════════════════════════
#  FORMATTING HELPERS
# ═══════════════════════════════════════════════════════════════════════════════


def _n(v, precision: int = 1) -> str:
    """Format a number in human-readable short form (e.g. 1.2M, 3.4B)."""
    try:
        v = float(v)
        if abs(v) >= 1_000_000_000:
            return f"{v / 1_000_000_000:,.{precision}f}B"
        if abs(v) >= 1_000_000:
            return f"{v / 1_000_000:,.{precision}f}M"
        if abs(v) >= 1_000:
            return f"{v:,.{precision}f}"
        if v != 0 and abs(v) < 0.01:
            return f"{v:.3g}"
        return f"{v:,.{precision}f}"
    except Exception:
        return str(v)


def _pct(part: float, whole: float, precision: int = 1) -> str:
    """Format part/whole as a rounded percentage string, e.g. '34.7%'."""
    try:
        if whole == 0:
            return "—"
        return f"{part / whole * 100:.{precision}f}%"
    except Exception:
        return "—"


def _col_ref(col: str, col_descriptions: dict | None = None) -> str:
    """Return the human-friendly description for a column if available.
    
    Falls back to the original column name when no description is provided
    or the column is not in the descriptions map.
    """
    if not col_descriptions:
        return col
    desc = col_descriptions.get(col, "").strip()
    return desc if desc else col


def _get_col_descriptions() -> dict | None:
    """Safely fetch column descriptions from Streamlit session state."""
    try:
        import streamlit as st
        return st.session_state.get("col_descriptions") or None
    except Exception:
        return None


def _plural(count, singular: str, plural: str = None) -> str:
    """Return singular or plural noun based on count."""
    return singular if int(count) == 1 else (plural or f"{singular}s")


# Cache for column descriptions to avoid repeated session_state lookups
_COL_DESC_CACHE: dict = {}


# ═══════════════════════════════════════════════════════════════════════════════
#  ENTERPRISE HELPERS — plain-English language for non-technical users
# ═══════════════════════════════════════════════════════════════════════════════


def _skew_description(skew: float) -> str:
    """Translate a skewness value into a plain-English shape description."""
    if abs(skew) < 0.2:
        return "roughly symmetric — values are evenly balanced around the middle"
    if abs(skew) < 0.8:
        tail = "right" if skew > 0 else "left"
        pull = "up" if skew > 0 else "down"
        return (
            f"slightly skewed {tail} — most values are typical, "
            f"but a few unusually {'high' if skew > 0 else 'low'} values pull the average {pull}"
        )
    if skew > 0:
        return (
            "heavily right-skewed — a small number of very high values inflate "
            "the average above what a typical row shows. The median is a more reliable benchmark."
        )
    return (
        "heavily left-skewed — a small number of very low values drag the average "
        "below the typical row. The median is a more reliable benchmark."
    )


def _correlation_strength_word(r: float) -> str:
    """Plain-English strength word from |r| value."""
    r = abs(r)
    if r >= 0.9:
        return "almost perfectly"
    if r >= 0.7:
        return "strongly"
    if r >= 0.4:
        return "moderately"
    if r >= 0.2:
        return "weakly"
    return "barely at all"


def _correlation_direction_phrase(r: float) -> str:
    """Plain-English description of correlation direction."""
    if r > 0:
        return "together — when one goes up, the other tends to go up too"
    return "in opposite directions — when one goes up, the other tends to fall"


def _gap_word(ratio: float) -> str:
    """Describe a ratio as a gap severity in plain English."""
    if ratio >= 10:
        return "extreme"
    if ratio >= 5:
        return "wide"
    if ratio >= 3:
        return "notable"
    if ratio >= 1.5:
        return "moderate"
    return "narrow"


def _concentration_word(top_share: float, n_cats: int) -> str:
    """Describe how concentrated a distribution is."""
    if n_cats <= 1:
        return "single category"
    even_share = 1.0 / n_cats
    if top_share > 2.5 * even_share:
        return "highly concentrated"
    if top_share > 1.5 * even_share:
        return "somewhat top-heavy"
    if top_share < 1.2 * even_share:
        return "evenly spread"
    return "relatively balanced"


def _trend_word(change_pct: float) -> str:
    """Describe a percentage change as an English trend."""
    if change_pct > 50:
        return "grew sharply"
    if change_pct > 15:
        return "grew noticeably"
    if change_pct > 3:
        return "grew slightly"
    if change_pct > -3:
        return "remained roughly stable"
    if change_pct > -15:
        return "declined slightly"
    if change_pct > -50:
        return "declined noticeably"
    return "declined sharply"


def _variability_word(cv: float) -> str:
    """Describe a coefficient of variation as variability level."""
    if cv > 0.5:
        return "highly variable"
    if cv > 0.2:
        return "somewhat variable"
    if cv > 0.05:
        return "moderately stable"
    return "very consistent"


def _confidence_note(n: int, n_total: int = None) -> str | None:
    """Return a confidence/caution note for small samples, or None if fine."""
    if n < 5:
        return (
            f"⚠️ Caution: this is based on only **{n}** data "
            f"{_plural(n, 'point')} — too few for reliable conclusions. "
            f"Treat these findings as indicative, not definitive."
        )
    if n < 20:
        return (
            f"🔍 Based on **{n}** {_plural(n, 'point')} — "
            f"a small sample. Patterns may change with more data."
        )
    if n_total and n < n_total * 0.1:
        return (
            f"🔍 This group represents only {_pct(n, n_total)} of "
            f"the total data — the average may shift with more records."
        )
    return None


def _quality_warning(df: pd.DataFrame, cols: list) -> str | None:
    """Return a warning if any input column has > 10% missing values."""
    for col in cols:
        if col not in df.columns:
            continue
        missing_pct = df[col].isna().mean()
        if missing_pct > 0.10:
            return (
                f"⚠️ **{col}** has **{missing_pct:.0%}** missing values — "
                f"these were excluded from the calculation. Conclusions are based "
                f"on the {1 - missing_pct:.0%} that have data."
            )
    return None


def _data_context(df: pd.DataFrame) -> str | None:
    """Produce a 'What the data covers' footer insight."""
    n_rows = len(df)
    n_cols = len(df.columns)
    null_pct = round(df.isnull().sum().sum() / max(df.size, 1) * 100, 1)
    context = (
        f"📊 This chart is built from **{n_rows:,} rows** across "
        f"**{n_cols} {_plural(n_cols, 'column')}**"
    )
    if null_pct > 0:
        context += f", with **{null_pct}%** missing cells"
    return context + "."


def _period_label(date_part: str | None) -> str:
    """Human-readable period name for time series grouping."""
    if not date_part:
        return "period"
    labels = {
        "Y": "year",
        "Q": "quarter",
        "M": "month",
        "month_name": "month of the year",
        "D": "day",
        "weekday_name": "day of the week",
        "H": "hour",
        "W": "week",
    }
    return labels.get(date_part, date_part)


# ═══════════════════════════════════════════════════════════════════════════════
#  CHART INSIGHT FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════


def _insights_statistical(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for the Statistical aggregation chart."""
    insights: list[str] = []
    num    = y_cols or list(df.select_dtypes("number").columns)
    grp    = x_cols[0] if x_cols else None
    agg_lbl = agg.title()
    agg_lbl_lower = agg_lbl.lower()

    if grp and grp in df.columns:
        # ── Overview ──
        insights.append(
            f"📊 This chart compares the **{agg_lbl_lower}** of selected "
            f"metrics across each **{grp}** category."
        )

        for metric in num[:2]:
            if metric not in df.columns:
                continue
            agg_s = df.groupby(grp)[metric].agg(agg).sort_values(ascending=False)
            if agg_s.empty or agg_s.sum() == 0:
                continue

            total     = float(agg_s.sum())
            n         = len(agg_s)
            top_cat   = str(agg_s.index[0])
            top_val   = float(agg_s.iloc[0])
            bot_cat   = str(agg_s.index[-1])
            bot_val   = float(agg_s.iloc[-1])
            top_share = top_val / total if total else 0

            metric_ref = _col_ref(metric, col_descriptions)

            # ── Key findings ──
            insights.append(
                f"🏆 **Top** — **{top_cat}**: {metric_ref} {agg_lbl} is **{_n(top_val)}** "
                f"({_pct(top_val, total)} of total)"
            )
            if n >= 3:
                mid_idx = n // 2
                mid_cat = str(agg_s.index[mid_idx])
                mid_val = float(agg_s.iloc[mid_idx])
                insights.append(
                    f"📊 **Middle** — **{mid_cat}**: {metric_ref} {agg_lbl} is **{_n(mid_val)}** "
                    f"({_pct(mid_val, total)} of total)"
                )
            insights.append(
                f"🔻 **Lowest** — **{bot_cat}**: {metric_ref} {agg_lbl} is **{_n(bot_val)}** "
                f"({_pct(bot_val, total)} of total)"
            )

            # ── Gap analysis ──
            if bot_val > 0:
                ratio = top_val / bot_val
                if ratio >= 3:
                    gap_word = _gap_word(ratio)
                    insights.append(
                        f"🔍 The gap between top and bottom is **{_n(ratio)}×** ({gap_word}) — "
                        f"worth investigating what drives the difference between "
                        f"**{top_cat}** and **{bot_cat}**."
                    )
            elif top_val > 0:
                insights.append(
                    f"⚠️ **{bot_cat}** has a zero or near-zero {metric_ref} — "
                    f"check whether data is missing or this category genuinely has no activity."
                )

            # ── Concentration ──
            if top_share > 0.5:
                conc = _concentration_word(top_share, n)
                insights.append(
                    f"⚠️ **{top_cat}** alone accounts for more than half of all {metric_ref} "
                    f"— this is {conc}. The overall total is heavily driven by this one group."
                )

            # ── Confidence note ──
            conf = _confidence_note(n, int(total) if total != 0 else None)
            if conf:
                insights.append(conf)

    else:
        vals = {c: float(df[c].agg(agg)) for c in num if c in df.columns}
        stds = {c: float(df[c].std())    for c in num if c in df.columns}
        if not vals:
            return []

        agg_lbl_lower = agg_lbl.lower()

        # ── Overview ──
        if len(vals) == 1:
            insights.append(
                f"📊 This bar chart shows the **{agg_lbl_lower}** of a single metric "
                f"across the entire dataset."
            )
        else:
            insights.append(
                f"📊 This bar chart compares the **{agg_lbl_lower}** for each "
                f"selected metric across the entire dataset."
            )

        # ── Key findings ──
        if len(vals) == 1:
            col, val = next(iter(vals.items()))
            col_ref = _col_ref(col, col_descriptions)
            insights.append(
                f"💡 The **{agg_lbl_lower}** of **{col_ref}** across "
                f"the entire dataset is **{_n(val)}**."
            )
        else:
            sorted_vals = sorted(vals.items(), key=lambda kv: abs(kv[1]), reverse=True)
            top_col, top_val = sorted_vals[0]
            bot_col, bot_val = sorted_vals[-1]

            metric_summary = ", ".join(
                f"**{_col_ref(c, col_descriptions)}** = {_n(v)}" for c, v in sorted_vals
            )
            insights.append(
                f"💡 {agg_lbl} values: {metric_summary}."
            )
            insights.append(
                f"🏆 **{_col_ref(top_col, col_descriptions)}** has the highest {agg_lbl_lower} ({_n(top_val)}); "
                f"**{_col_ref(bot_col, col_descriptions)}** has the lowest ({_n(bot_val)})."
            )

        # ── Variability ──
        most_variable = max(stds, key=stds.get) if stds else None
        if most_variable:
            cv = stds[most_variable] / abs(vals[most_variable]) if vals.get(most_variable) else 0
            if cv > 0.4:
                var_word = _variability_word(cv)
                insights.append(
                    f"⚠️ **{_col_ref(most_variable, col_descriptions)}** is {var_word} across rows — "
                    f"its spread is {cv * 100:.0f}% of its average. "
                    f"The {agg_lbl_lower} may be heavily influenced by a few extreme values."
                )

    return insights


def _insights_distribution(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Distribution (histogram + box plot) charts."""
    insights: list[str] = []
    cols = x_cols or list(df.select_dtypes("number").columns)[:4]

    for col in cols[:3]:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) < 5:
            continue

        q1   = float(s.quantile(0.25))
        q3   = float(s.quantile(0.75))
        iqr  = q3 - q1
        med  = float(s.median())
        mean = float(s.mean())
        skew = float(s.skew())
        p10  = float(s.quantile(0.10))
        p90  = float(s.quantile(0.90))

        col_ref = _col_ref(col, col_descriptions)

        # ── Overview ──
        insights.append(
            f"📊 **{col_ref}** — this chart shows how values are spread across the range. "
            f"Think of it as a landscape: the tallest bars are where most of your data lives."
        )

        # ── Key findings: typical range ──
        insights.append(
            f"💡 Most values fall between **{_n(q1)}** and **{_n(q3)}** "
            f"(the middle 50%). The median — the value in the exact centre — is **{_n(med)}**. "
            f"The average is **{_n(mean)}**."
        )

        # ── Shape ──
        shape_desc = _skew_description(skew)
        insights.append(
            f"🔍 Shape: {shape_desc}."
        )

        # ── Mean vs median divergence ──
        if med != 0 and abs(mean - med) > 0.25 * abs(med):
            direction = "higher" if mean > med else "lower"
            puller = "high" if mean > med else "low"
            insights.append(
                f"⚠️ Average ({_n(mean)}) is notably {direction} than the median ({_n(med)}) — "
                f"a few extreme {puller} values are skewing the average. "
                f"Use the median as the more reliable benchmark for what's typical."
            )

        # ── Outlier detection ──
        if iqr > 0:
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            n_out  = int(((s < lo) | (s > hi)).sum())
            if n_out > 0:
                pct_out = n_out / len(s) * 100
                severity = (
                    "a small number of" if pct_out < 2
                    else "some" if pct_out < 10
                    else "many"
                )
                insights.append(
                    f"⚠️ There are {severity} unusual values in **{col_ref}** "
                    f"({n_out:,} rows, {_pct(n_out, len(s))}) — "
                    f"these sit far outside the typical range ({_n(lo)} to {_n(hi)}). "
                    f"Use the Outlier Detection tool on the upload page to inspect them."
                )

        # ── Percentile context ──
        if p90 > p10:
            insights.append(
                f"📊 The middle 80% of records fall between **{_n(p10)}** and **{_n(p90)}** — "
                f"this gives a practical sense of the typical high and low without being "
                f"thrown off by extremes."
            )

        # ── Data quality ──
        qwarn = _quality_warning(df, [col])
        if qwarn:
            insights.append(qwarn)

        # ── Small sample ──
        conf = _confidence_note(len(s), int(s.count()))
        if conf:
            insights.append(conf)

    return insights


def _insights_correlation(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for the Correlation heatmap."""
    insights: list[str] = []
    num = list(dict.fromkeys((x_cols or []) + (y_cols or [])))
    if len(num) < 2:
        return []

    try:
        corr = df[num].corr()
    except Exception:
        return []

    pairs: list[tuple[str, str, float]] = []
    for i in range(len(num)):
        for j in range(i + 1, len(num)):
            r = corr.iloc[i, j]
            if pd.notna(r):
                pairs.append((num[i], num[j], float(r)))

    if not pairs:
        return []

    by_abs = sorted(pairs, key=lambda p: abs(p[2]), reverse=True)

    # ── Overview ──
    insights.append(
        "📊 This heatmap shows how strongly each pair of columns moves together. "
        "Strong links may help predict one column from another; weak links suggest "
        "they change independently."
    )
    insights.append(
        "💡 Correlation measures association, not causation — a strong link suggests "
        "a relationship worth investigating, but doesn't prove one column causes the other."
    )

    # ── Strongest positive ──
    strong_pos = [(a, b, r) for a, b, r in by_abs if r > 0.3]
    if strong_pos:
        a, b, r = strong_pos[0]
        strength = _correlation_strength_word(r)
        direction = _correlation_direction_phrase(r)
        a_ref = _col_ref(a, col_descriptions)
        b_ref = _col_ref(b, col_descriptions)
        insights.append(
            f"🔗 **{a_ref}** and **{b_ref}** move {strength} {direction}."
        )

    # ── Strongest negative ──
    strong_neg = [(a, b, r) for a, b, r in by_abs if r < -0.3]
    if strong_neg:
        a, b, r = strong_neg[0]
        a_ref = _col_ref(a, col_descriptions)
        b_ref = _col_ref(b, col_descriptions)
        insights.append(
            f"📉 **{a_ref}** and **{b_ref}** move {_correlation_strength_word(r)} "
            f"in **opposite directions** — when one rises, the other tends to fall. "
            f"This trade-off relationship is common in scenarios like price vs. demand."
        )

    # ── Weak/unrelated pairs ──
    weak_pairs = [(a, b, r) for a, b, r in pairs if abs(r) < 0.1]
    if len(weak_pairs) >= 2:
        insights.append(
            f"🔍 **{len(weak_pairs)} column pair(s)** show almost no relationship — "
            f"those columns appear to change independently of one another. "
            f"This means knowing one won't help you predict the other."
        )

    # ── Redundancy warning ──
    redundant = [(a, b, r) for a, b, r in pairs if r > 0.9]
    if redundant:
        a, b, r = redundant[0]
        a_ref = _col_ref(a, col_descriptions)
        b_ref = _col_ref(b, col_descriptions)
        insights.append(
            f"✅ **{a_ref}** and **{b_ref}** move almost perfectly together "
            f"(correlation ≈ {r:.2f}) — they may be measuring the same "
            f"underlying thing in different units. You may only need one "
            f"of them in a predictive model; using both could add noise."
        )

    # ── Data quality ──
    qwarn = _quality_warning(df, num[:6])
    if qwarn:
        insights.append(qwarn)

    return insights


def _insights_categorical(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    top_n=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Categorical Bar/Column charts."""
    insights: list[str] = []
    dims    = x_cols or []
    metrics = y_cols
    agg_lbl = agg.title()
    agg_lbl_lower = agg_lbl.lower()

    for col in dims[:2]:
        if col not in df.columns:
            continue

        if metrics:
            for metric in metrics[:1]:
                if metric not in df.columns:
                    continue
                agg_s = df.groupby(col)[metric].agg(agg).sort_values(ascending=False)
                total = float(agg_s.sum())
                if agg_s.empty or total == 0:
                    continue

                top_cat   = str(agg_s.index[0])
                top_val   = float(agg_s.iloc[0])
                n_cats    = len(agg_s)
                top_share = top_val / total

                metric_ref = _col_ref(metric, col_descriptions)

                # ── Overview ──
                insights.append(
                    f"📊 This chart compares **{agg_lbl_lower} {metric_ref}** "
                    f"across each **{col}** category."
                )

                # ── Key findings ──
                insights.append(
                    f"🏆 **{top_cat}** leads in {metric_ref} — "
                    f"{_n(top_val)}, which is {_pct(top_val, total)} of the total."
                )

                # ── Concentration ──
                conc = _concentration_word(top_share, n_cats)
                if top_share > 0.5:
                    insights.append(
                        f"⚠️ **{top_cat}** alone makes up more than half of all {metric_ref}. "
                        f"This heavy **{conc}** means the overall total is very sensitive to "
                        f"what happens in this one category — a risk if conditions change."
                    )
                else:
                    insights.append(
                        f"💡 Distribution is **{conc}** across {n_cats} categories."
                    )

                # ── Top3 share ──
                if n_cats >= 5:
                    top3_share = float(agg_s.iloc[:3].sum()) / total
                    if top3_share > 0.8:
                        tail = "the remaining categories are relatively minor."
                    else:
                        tail = "the remaining categories still carry significant weight."
                    insights.append(
                        f"📊 The top 3 categories account for **{top3_share * 100:.0f}%** of "
                        f"total {metric_ref} — {tail} "
                        f"Focus here for the biggest impact."
                    )

                # ── Gap analysis ──
                if n_cats >= 2:
                    bot_val = float(agg_s.iloc[-1])
                    if bot_val > 0:
                        ratio = top_val / bot_val
                        if ratio >= 5:
                            bot_cat = str(agg_s.index[-1])
                            gap_word = _gap_word(ratio)
                            insights.append(
                                f"🔍 The performance gap is {gap_word}: **{top_cat}** is "
                                f"**{ratio:.0f}×** higher than **{bot_cat}** — "
                                f"investigate what differentiates top from bottom performers."
                            )

                # ── Confidence ──
                conf = _confidence_note(n_cats, int(len(df)))
                if conf:
                    insights.append(conf)

        else:
            vc        = df[col].value_counts()
            n_total   = int(vc.sum())
            top_cat   = str(vc.index[0])
            top_count = int(vc.iloc[0])
            n_unique  = len(vc)

            col_ref = _col_ref(col, col_descriptions)

            # ── Overview ──
            insights.append(
                f"📊 This chart shows the count of rows for each **{col_ref}** category."
            )

            # ── Key findings ──
            insights.append(
                f"🏆 **{top_cat}** is the most common value in **{col_ref}** — "
                f"{top_count:,} rows ({_pct(top_count, n_total)})."
            )

            # ── High cardinality ──
            if n_unique > 20:
                insights.append(
                    f"🔍 **{col}** has {n_unique:,} distinct values. "
                    f"Consider grouping similar values to make patterns easier to see."
                )

    return insights


def _insights_pie(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    top_n=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Pie / Donut charts."""
    insights: list[str] = []
    dims    = x_cols or []
    metrics = y_cols
    agg_lbl_lower = agg.lower()

    for col in dims[:1]:
        if col not in df.columns:
            continue

        if metrics:
            for metric in metrics[:1]:
                if metric not in df.columns:
                    continue
                agg_s  = df.groupby(col)[metric].agg(agg).sort_values(ascending=False)
                total  = float(agg_s.sum())
                if total == 0 or agg_s.empty:
                    continue

                top_cat  = str(agg_s.index[0])
                top_val  = float(agg_s.iloc[0])
                n_cats   = len(agg_s)
                share    = top_val / total

                metric_ref = _col_ref(metric, col_descriptions)

                # ── Overview ──
                insights.append(
                    f"📊 This chart shows how total **{metric_ref}** is divided among "
                    f"**{col}** categories. Each slice is one category's share of the whole."
                )

                # ── Key finding ──
                insights.append(
                    f"🏆 **{top_cat}** is the largest slice, making up "
                    f"**{_pct(top_val, total)}** of total {metric_ref}."
                )

                # ── Top 3 share ──
                if n_cats >= 3:
                    top3_share = float(agg_s.iloc[:3].sum()) / total
                    insights.append(
                        f"📊 The top 3 categories together account for "
                        f"**{top3_share * 100:.0f}%** of all {metric_ref}."
                    )

                # ── Dominance analysis ──
                conc = _concentration_word(share, n_cats)
                if share > 0.6:
                    rest_n = n_cats - 1
                    insights.append(
                        f"⚠️ With {_pct(top_val, total)}, **{top_cat}** dominates "
                        f"— the other {rest_n} {_plural(rest_n, 'category')} "
                        f"share only {_pct(total - top_val, total)} combined. "
                        f"This is **{conc}** — consider whether the dominant category "
                        f"represents a strength or a single-point-of-failure risk."
                    )
                elif share < 0.25 and n_cats >= 4:
                    insights.append(
                        f"✅ No single category dominates — values are **{conc}** "
                        f"across all {n_cats} categories, which suggests a diversified mix."
                    )

        else:
            vc        = df[col].value_counts()
            total     = int(vc.sum())
            top_cat   = str(vc.index[0])
            top_count = int(vc.iloc[0])
            n_cats    = len(vc)
            share     = top_count / total if total else 0

            col_ref = _col_ref(col, col_descriptions)

            # ── Overview ──
            insights.append(
                f"📊 This chart shows how rows are split across **{col_ref}** categories."
            )

            # ── Key finding ──
            insights.append(
                f"🏆 **{top_cat}** is the most common — "
                f"{_pct(top_count, total)} of all {n_cats} categories."
            )

            # ── Top 3 share ──
            if n_cats >= 3:
                top3 = int(vc.iloc[:3].sum()) / total
                insights.append(
                    f"📊 The top 3 values together make up **{top3 * 100:.0f}%** of all entries."
                )

    return insights


def _insights_time_series(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    date_part=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Time Series line charts."""
    insights: list[str] = []
    dt_col = (x_cols or [None])[0]
    num    = y_cols or []

    if not dt_col or dt_col not in df.columns:
        return []

    try:
        temp = df.copy()
        temp["_dt"] = pd.to_datetime(temp[dt_col], errors="coerce")
        temp = temp.dropna(subset=["_dt"])
        if temp.empty:
            return []
    except Exception:
        return []

    period_name = _period_label(date_part)

    for metric in num[:2]:
        if metric not in temp.columns:
            continue

        try:
            metric_ref = _col_ref(metric, col_descriptions)

            if date_part:
                if date_part == "month_name":
                    temp["_p"] = temp["_dt"].dt.month_name()
                elif date_part == "weekday_name":
                    temp["_p"] = temp["_dt"].dt.day_name()
                else:
                    temp["_p"] = temp["_dt"].dt.to_period(date_part).astype(str)

                g = temp.groupby("_p")[metric].agg(agg)
                if g.empty:
                    continue
                peak_period   = str(g.idxmax())
                trough_period = str(g.idxmin())

                # ── Overview ──
                insights.append(
                    f"📊 This chart shows how **{metric_ref}** varies by "
                    f"**{period_name}** — look for repeating highs and lows."
                )

                # ── Key findings ──
                insights.append(
                    f"🏆 **{peak_period}** had the highest {metric_ref} ({_n(g.max())}); "
                    f"**{trough_period}** had the lowest ({_n(g.min())})."
                )

                # ── Variability ──
                rng = g.max() - g.min()
                if g.mean() != 0:
                    cv = float(g.std()) / abs(float(g.mean()))
                    var_word = _variability_word(cv)
                    if cv > 0.35:
                        insights.append(
                            f"⚠️ **{metric_ref}** is {var_word} across periods "
                            f"(range: {_n(g.min())} → {_n(g.max())}) — "
                            f"the pattern may be seasonal or driven by a specific event. "
                            f"Look for the same peaks repeating at regular intervals."
                        )
                    elif cv < 0.05:
                        insights.append(
                            f"✅ **{metric_ref}** is remarkably stable across "
                            f"{_plural(len(g), 'period')} — values stay close to "
                            f"{_n(float(g.mean()))} with very little variation. "
                            f"Useful as a reliable baseline."
                        )

            else:
                ts = temp.sort_values("_dt").groupby("_dt")[metric].agg(agg)
                if len(ts) < 2:
                    continue

                first_val = float(ts.iloc[0])
                last_val  = float(ts.iloc[-1])

                # ── Overview ──
                insights.append(
                    f"📊 This chart tracks **{metric_ref}** over time from "
                    f"the earliest to the latest data point. Look for trends, spikes, or dips."
                )

                # ── Trend ──
                if first_val != 0:
                    change = (last_val - first_val) / abs(first_val)
                    trend_word = _trend_word(change * 100)
                    icon = "📈" if change > 0 else "📉"
                    insights.append(
                        f"{icon} **{metric_ref}** {trend_word} — "
                        f"from **{_n(first_val)}** to **{_n(last_val)}** "
                        f"(a **{abs(change) * 100:.1f}%** change)."
                    )
                else:
                    insights.append(
                        f"📊 **{metric_ref}** starts at {_n(first_val)} and "
                        f"ends at {_n(last_val)}."
                    )

                # ── Peak and trough ──
                peak_dt   = ts.idxmax()
                trough_dt = ts.idxmin()
                peak_date   = str(peak_dt.date())   if hasattr(peak_dt,   "date") else str(peak_dt)
                trough_date = str(trough_dt.date()) if hasattr(trough_dt, "date") else str(trough_dt)
                insights.append(
                    f"🔍 Highest point: **{_n(ts.max())}** on {peak_date}; "
                    f"lowest: **{_n(ts.min())}** on {trough_date}."
                )

                # ── Stability ──
                mean_val = float(ts.mean())
                std_val  = float(ts.std())
                if mean_val != 0:
                    cv = std_val / abs(mean_val)
                    var_word = _variability_word(cv)
                    if cv > 0.35:
                        insights.append(
                            f"⚠️ **{metric_ref}** is {var_word} over time "
                            f"(the spread is {cv * 100:.0f}% of the average). "
                            f"This may point to seasonal patterns or irregular events — "
                            f"investigate before using this trend for forecasting."
                        )
                    elif cv < 0.05:
                        insights.append(
                            f"✅ **{metric_ref}** is very consistent over time "
                            f"— values stay close to {_n(mean_val)} with minimal variation. "
                            f"A reliable baseline for benchmarking or targets."
                        )
                    else:
                        insights.append(
                            f"💡 **{metric_ref}** shows moderate variability — "
                            f"look for repeating peaks or dips that could signal seasonality."
                        )

        except Exception:
            continue

    return insights


def _insights_scatter(
    df: pd.DataFrame,
    x_col: str = None,
    y_col: str = None,
    color_col: str = None,
    size_col: str = None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Scatter Plot charts."""
    insights: list[str] = []
    if not x_col or not y_col:
        return []

    try:
        x_s = pd.to_numeric(df[x_col], errors="coerce").dropna()
        y_s = pd.to_numeric(df[y_col], errors="coerce").dropna()
        idx = x_s.index.intersection(y_s.index)
        if len(idx) < 3:
            return []
        r = float(np.corrcoef(x_s[idx], y_s[idx])[0, 1])
        if np.isnan(r):
            return []
    except Exception:
        return []

    x_ref = _col_ref(x_col, col_descriptions)
    y_ref = _col_ref(y_col, col_descriptions)

    # ── Overview ──
    insights.append(
        f"📊 This scatter plot shows each data point as a dot, with **{x_ref}** on the "
        f"X-axis and **{y_ref}** on the Y-axis. The pattern of dots reveals whether "
        f"the two columns move together."
    )

    # ── Key finding (BUG FIX: strength and direction were undefined) ──
    strength = _correlation_strength_word(r)
    direction = _correlation_direction_phrase(r)
    insights.append(
        f"💡 **{x_ref}** and **{y_ref}** move {strength} "
        f"{direction} (correlation ≈ {r:.2f})."
    )

    # ── Directional guidance ──
    if abs(r) >= 0.5:
        if r > 0:
            insights.append(
                f"✅ Higher **{x_ref}** tends to go with higher **{y_ref}** — "
                f"knowing one gives a useful clue about the other."
            )
        else:
            insights.append(
                f"🔍 Higher **{x_ref}** tends to go with lower **{y_ref}** — "
                f"a trade-off relationship: when one rises, the other falls."
            )
    elif abs(r) < 0.15:
        insights.append(
            f"🔍 **{x_ref}** and **{y_ref}** appear unrelated here — "
            f"changes in one do not reliably predict changes in the other."
        )
    else:
        insights.append(
            f"💡 There is a modest link between **{x_ref}** and **{y_ref}** — "
            f"the relationship may exist but other factors likely play a role too."
        )

    # ── Group analysis ──
    if color_col and color_col in df.columns:
        try:
            group_means = df.groupby(color_col)[[x_col, y_col]].mean()
            if len(group_means) > 1:
                top_g = str(group_means[y_col].idxmax())
                bot_g = str(group_means[y_col].idxmin())
                insights.append(
                    f"📊 By group: **{top_g}** has the highest average {y_ref} "
                    f"({_n(float(group_means.loc[top_g, y_col]))}); "
                    f"**{bot_g}** has the lowest "
                    f"({_n(float(group_means.loc[bot_g, y_col]))})."
                )
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

    # ── Size column ──
    if size_col and size_col in df.columns:
        size_ref = _col_ref(size_col, col_descriptions)
        insights.append(
            f"🔍 Marker **size** reflects **{size_ref}** — larger dots = higher values. "
            f"Hover over any dot to see its exact value."
        )

    # ── Small sample ──
    conf = _confidence_note(len(idx))
    if conf:
        insights.append(conf)

    return insights


def _insights_matrix(
    df: pd.DataFrame,
    index_col: str = None,
    columns_col: str = None,
    values_col: str = None,
    agg: str = "mean",
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Matrix Heatmap / Pivot Table charts."""
    insights: list[str] = []
    if not index_col or not columns_col or not values_col:
        return []

    try:
        pivot = pd.pivot_table(
            df, index=index_col, columns=columns_col, values=values_col,
            aggfunc=agg, observed=True,
        )
        if pivot.empty:
            return []
    except Exception:
        return []

    flat = pivot.stack().dropna()
    if flat.empty:
        return []

    top_idx = flat.idxmax()
    bot_idx = flat.idxmin()
    top_val = float(flat.max())
    bot_val = float(flat.min())

    values_ref = _col_ref(values_col, col_descriptions)
    index_ref = _col_ref(index_col, col_descriptions)
    columns_ref = _col_ref(columns_col, col_descriptions)

    # ── Overview ──
    insights.append(
        f"📊 This chart shows the **{agg.title()}** of **{values_ref}** "
        f"for each combination of **{index_ref}** (rows) and **{columns_ref}** (columns). "
    )

    # ── Key findings ──
    insights.append(
        f"🏆 **Highest cell:** {index_ref} = **{top_idx[0]}** × "
        f"{columns_ref} = **{top_idx[1]}** → {_n(top_val)}"
    )
    insights.append(
        f"🔻 **Lowest cell:** {index_ref} = **{bot_idx[0]}** × "
        f"{columns_ref} = **{bot_idx[1]}** → {_n(bot_val)}"
    )

    # ── Range analysis ──
    spread = top_val - bot_val
    if spread > 0:
        denominator = max(abs(top_val), abs(bot_val), 1)
        relative_spread = spread / denominator
        if relative_spread > 0.5:
            spread_desc = (
                "Wide range — the colour contrast carries real signal; "
                "the brightest cells are dramatically different from the dimmest."
            )
        else:
            spread_desc = (
                "Narrow range — cells are more similar than the colour may suggest. "
                "Small differences are visually amplified."
            )
        insights.append(
            f"🔍 Value range: **{_n(bot_val)}** to **{_n(top_val)}**. {spread_desc}"
        )

    # ── Sparsity check ──
    n_total_cells = pivot.size
    n_fillable = int(flat.count()) if hasattr(flat, 'count') else len(flat)
    n_blank = n_total_cells - n_fillable
    if n_total_cells > 0 and n_blank / n_total_cells > 0.25:
        insights.append(
            f"⚠️ **{n_blank / n_total_cells:.0%}** of cells are empty — "
            f"some combinations have no data. Sparse combinations might need "
            f"more data or broader groupings to be meaningful."
        )

    return insights


def _insights_map(
    df: pd.DataFrame,
    lat_col: str = None,
    lon_col: str = None,
    location_col: str = None,
    color_col: str = None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Map Plot (geographic scatter) charts."""
    insights: list[str] = []
    if not lat_col or not lon_col:
        return []

    try:
        clean = df[[lat_col, lon_col]].dropna()
        if clean.empty:
            return []

        n_pts     = len(clean)
        lat_span  = float(clean[lat_col].max() - clean[lat_col].min())
        lon_span  = float(clean[lon_col].max() - clean[lon_col].min())
        max_span  = max(lat_span, lon_span)

        # ── Overview ──
        insights.append(
            f"📊 This map plots **{n_pts:,} location{_plural(n_pts, '')}** from your data. "
            f"Each dot represents one data point at its geographic coordinates."
        )

        # ── Geographic spread ──
        if max_span < 2:
            insights.append(
                f"🔍 Data is geographically concentrated in a small area — "
                f"zoom in for detailed cluster analysis."
            )
        elif max_span > 50:
            insights.append(
                f"🔍 Data spans a wide geographic area — "
                f"consider filtering by region for more focused analysis."
            )
        else:
            insights.append(
                f"💡 Data covers a moderate geographic area — look for regional clusters."
            )

        # ── Colour grouping ──
        if color_col and color_col in df.columns:
            n_groups = int(df[color_col].nunique())
            color_ref = _col_ref(color_col, col_descriptions)
            insights.append(
                f"🎨 Points coloured by **{color_ref}** ({n_groups} distinct "
                f"{_plural(n_groups, 'value')}). "
                f"Look for geographic clustering by colour — same-colour clusters "
                f"may reveal regional patterns. Hover any dot for exact details."
            )

        # ── Location label ──
        if location_col and location_col in df.columns:
            try:
                top_loc = df[location_col].value_counts().index[0]
                top_cnt = int(df[location_col].value_counts().iloc[0])
                insights.append(
                    f"🏆 **{top_loc}** has the most data points ({top_cnt:,} rows) — "
                    f"zoom into that area first for the richest detail."
                )
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass

    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass

    return insights


def _insights_outlier_chart(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    col_descriptions: dict | None = None,
    **kwargs,
) -> list[str]:
    """Insights for Outlier scatter charts (run via the analysis page)."""
    insights: list[str] = []
    cols = x_cols or list(df.select_dtypes("number").columns)[:6]
    if not cols:
        return []

    # ── Overview ──
    insights.append(
        "📊 These charts flag data points that fall far outside the typical range "
        "for each column. Red × marks are statistical outliers."
    )

    total_flagged = 0
    for col in cols[:4]:
        if col not in df.columns:
            continue
        s = pd.to_numeric(df[col], errors="coerce").dropna()
        if len(s) < 5:
            continue
        q1, q3 = s.quantile(0.25), s.quantile(0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
        n_out = int(((s < lo) | (s > hi)).sum())
        if n_out > 0:
            total_flagged += n_out
            pct = n_out / len(s) * 100
            severity = (
                "a small number of" if pct < 2
                else "some" if pct < 10
                else "many"
            )
            col_ref = _col_ref(col, col_descriptions)
            insights.append(
                f"⚠️ **{col_ref}**: {severity} unusual values — "
                f"**{n_out:,}** {_plural(n_out, 'point')} ({pct:.1f}%) "
                f"outside the range {_n(lo)} to {_n(hi)}."
            )

    if total_flagged == 0:
        insights.append(
            "✅ No statistical outliers detected in the selected columns — "
            "the data looks clean within standard IQR thresholds."
        )
    else:
        insights.append(
            f"💡 **{total_flagged:,}** total outlier {_plural(total_flagged, 'point')} "
            f"detected across selected columns. These may signal data-entry errors, "
            f"one-off events, or genuine extremes — investigate before including in analysis."
        )

    return insights


# ═══════════════════════════════════════════════════════════════════════════════
#  OUTLIER INSIGHTS (standalone — used by upload page)
# ═══════════════════════════════════════════════════════════════════════════════


def outlier_insights(col: str, info: dict, col_descriptions: dict | None = None) -> list[str]:
    """Generate plain-English outlier insights from an IQR result dict.

    Called directly from ``modules.analysis.outlier`` on the upload page.
    Signature preserved: (col: str, info: dict) -> list[str].
    """
    n   = int(info["out_count"])
    pct = info["pct"]
    lo  = info["lo"]
    hi  = info["hi"]
    q1  = info["q1"]
    q3  = info["q3"]

    col_ref = _col_ref(col, col_descriptions)

    if n == 0:
        return [
            f"✅ No unusual values found in **{col_ref}** — the numbers look clean here.",
        ]

    severity = (
        "a very small number of"  if pct < 1
        else "some"               if pct < 5
        else "a notable share of"
    )

    return [
        f"📊 **{col_ref}** — this column measures values across your dataset. "
        f"Unusual values are those that fall far from the typical range.",

        f"⚠️ **{n:,} {_plural(n, 'value')}** ({pct}%) in **{col_ref}** are unusually high or low — "
        f"{severity} your data falls outside the expected range.",

        f"🔍 The expected range for **{col_ref}** is roughly **{_n(lo)}** to **{_n(hi)}**. "
        f"The middle 50% of typical values sit between **{_n(q1)}** and **{_n(q3)}**.",

        f"💡 Unusual values often signal data-entry errors, one-off events, or genuine extremes — "
        f"investigate each flagged row before including it in analysis or reporting.",
    ]


# ═══════════════════════════════════════════════════════════════════════════════
#  DISPATCH — routes analysis_type to the correct insight function
# ═══════════════════════════════════════════════════════════════════════════════


_FN_MAP: dict = {
    "statistical":  _insights_statistical,
    "distribution": _insights_distribution,
    "correlation":  _insights_correlation,
    "categorical":  _insights_categorical,
    "pie_chart":    _insights_pie,
    "time_series":  _insights_time_series,
    "scatter_plot":  _insights_scatter,
    "matrix_heatmap": _insights_matrix,
    "matrix_table":   _insights_matrix,
    "map_plot":      _insights_map,
    "outlier":       _insights_outlier_chart,
}


def generate_insights(
    analysis_type: str,
    df: pd.DataFrame,
    uid: str,
    **kwargs,
) -> list[str]:
    """Generate plain-English insights for one chart and store them in session_state.

    Public API — imported by ``modules.analysis.__init__``.
    Signature: (analysis_type, df, uid, **kwargs) -> list[str]
    """
    try:
        fn = _FN_MAP.get(analysis_type)
        if fn is None:
            return []

        # Inject column descriptions from session state if not explicitly provided
        if "col_descriptions" not in kwargs:
            kwargs["col_descriptions"] = _get_col_descriptions()

        insights: list[str] = fn(df, **kwargs) or []

        # Append data context footer when insights exist
        if insights:
            context = _data_context(df)
            if context and len(insights) < 7:
                insights.append(context)

        # Fallback when no insights were generated
        if not insights:
            n_rows = len(df)
            n_cols = len(df.columns)
            insights = [
                f"💡 Chart generated from **{n_rows:,} row{_plural(n_rows, '')}** "
                f"across **{n_cols} {_plural(n_cols, 'column')}**."
            ]

        # Store to session_state for downstream consumers
        try:
            import streamlit as st
            st.session_state[f"auto_insights_{uid}"] = insights
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            pass

        return insights

    except Exception:
        return []
