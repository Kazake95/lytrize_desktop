"""modules/analysis/insights.py — Auto-Insights Engine"""


from __future__ import annotations


import numpy as np
import pandas as pd




def _n(v, precision: int = 1) -> str:
    """Format a number in human-readable short form."""
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
    """Format part/whole as a rounded percentage string, e.g. '34.7 %'."""
    try:
        if whole == 0:
            return "—"
        return f"{part / whole * 100:.{precision}f}%"
    except Exception:
        return "—"




def _skew_description(skew: float) -> str:
    """Translate a skewness value into a plain-English shape description."""
    if abs(skew) < 0.2:
        return "roughly symmetric — the average and median are close"
    if abs(skew) < 0.8:
        tail = "right" if skew > 0 else "left"
        return f"slightly skewed {tail} — most values are typical, but a few outliers pull the average {'up' if skew > 0 else 'down'}"
    if skew > 0:
        return "right-skewed — a small number of very high values inflate the average above what a typical row shows"
    return "left-skewed — a small number of very low values drag the average below the typical row"




def _correlation_strength_word(r: float) -> str:
    """Plain-English strength word from |r| value (no stats knowledge assumed)."""
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




def _insights_statistical(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    **kwargs,
) -> list[str]:
    """Insights for the Statistical aggregation chart."""
    insights: list[str] = []
    num    = y_cols or list(df.select_dtypes("number").columns)
    grp    = x_cols[0] if x_cols else None
    agg_lbl = agg.title()


    if grp and grp in df.columns:
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


            insights.append(
                f"🏆 **Top** — {grp}: **{top_cat}** → {metric} {agg_lbl}: **{_n(top_val)}** "
                f"({_pct(top_val, total)} of total)"
            )
            if n >= 3:
                mid_idx = n // 2
                mid_cat = str(agg_s.index[mid_idx])
                mid_val = float(agg_s.iloc[mid_idx])
                insights.append(
                    f"📊 **Middle** — {grp}: **{mid_cat}** → {metric} {agg_lbl}: **{_n(mid_val)}** "
                    f"({_pct(mid_val, total)} of total)"
                )
            insights.append(
                f"🔻 **Lowest** — {grp}: **{bot_cat}** → {metric} {agg_lbl}: **{_n(bot_val)}** "
                f"({_pct(bot_val, total)} of total)"
            )


            if bot_val > 0:
                ratio = top_val / bot_val
                if ratio >= 3:
                    insights.append(
                        f"🔍 The gap between top and bottom is **{ratio:.1f}×** — "
                        f"worth investigating what drives the difference between "
                        f"**{top_cat}** and **{bot_cat}**."
                    )
            elif top_val > 0:
                insights.append(
                    f"⚠️ **{bot_cat}** has a zero or near-zero {metric} — check whether data is missing."
                )


            if top_share > 0.5:
                insights.append(
                    f"⚠️ **{top_cat}** alone accounts for more than half of all {metric} — "
                    f"the total is heavily driven by this one group."
                )


    else:
        vals = {c: float(df[c].agg(agg)) for c in num if c in df.columns}
        stds = {c: float(df[c].std())    for c in num if c in df.columns}
        if not vals:
            return []


        agg_lbl_lower = agg_lbl.lower()


        if len(vals) == 1:
            col, val = next(iter(vals.items()))
            insights.append(
                f"📊 The bar chart shows the **{agg_lbl_lower}** of **{col}** "
                f"across the entire dataset — the result is **{_n(val)}**."
            )
        else:
            sorted_vals = sorted(vals.items(), key=lambda kv: abs(kv[1]), reverse=True)
            top_col, top_val = sorted_vals[0]
            bot_col, bot_val = sorted_vals[-1]


            metric_summary = ", ".join(
                f"**{c}** = {_n(v)}" for c, v in sorted_vals
            )
            insights.append(
                f"📊 The bar chart shows the **{agg_lbl_lower}** for each selected metric: "
                f"{metric_summary}."
            )
            insights.append(
                f"💡 **{top_col}** has the highest {agg_lbl_lower} ({_n(top_val)}); "
                f"**{bot_col}** has the lowest ({_n(bot_val)})."
            )


        most_variable = max(stds, key=stds.get) if stds else None
        if most_variable:
            cv = stds[most_variable] / abs(vals[most_variable]) if vals.get(most_variable) else 0
            if cv > 0.4:
                insights.append(
                    f"⚠️ **{most_variable}** varies considerably across rows — "
                    f"its spread is {cv * 100:.0f}% of its average. "
                    f"This may mean the {agg_lbl_lower} is heavily influenced by a few extreme values."
                )


    return insights




def _insights_distribution(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
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


        shape_desc = _skew_description(skew)
        insights.append(
            f"📊 **{col}** — typical values range from **{_n(q1)}** to **{_n(q3)}** "
            f"(the middle 50%). Median: **{_n(med)}**, Average: **{_n(mean)}**."
        )
        insights.append(
            f"💡 Shape: {shape_desc}."
        )


        if med != 0 and abs(mean - med) > 0.25 * abs(med):
            direction = "higher" if mean > med else "lower"
            puller = "high" if mean > med else "low"
            insights.append(
                f"🔍 Average ({_n(mean)}) is notably {direction} than the median ({_n(med)}) — "
                f"a few extreme {puller} values are skewing the average. "
                f"Use the median as the more reliable benchmark."
            )


        if iqr > 0:
            lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
            n_out  = int(((s < lo) | (s > hi)).sum())
            if n_out > 0:
                pct_out = n_out / len(s) * 100
                severity = "a small number of" if pct_out < 2 else "some" if pct_out < 10 else "many"
                insights.append(
                    f"⚠️ There are {severity} unusual values in **{col}** "
                    f"({n_out:,} rows, {_pct(n_out, len(s))}) — "
                    f"these sit far outside the typical range. "
                    f"Use the Outlier Detection tool on the upload page to check them."
                )


    return insights




def _insights_correlation(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
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


    strong_pos = [(a, b, r) for a, b, r in by_abs if r > 0.3]
    if strong_pos:
        a, b, r = strong_pos[0]
        insights.append(
            f"💡 **{a}** and **{b}** move {_correlation_strength_word(r)} "
            f"{_correlation_direction_phrase(r)}."
        )


    strong_neg = [(a, b, r) for a, b, r in by_abs if r < -0.3]
    if strong_neg:
        a, b, r = strong_neg[0]
        insights.append(
            f"📉 **{a}** and **{b}** move {_correlation_strength_word(r)} "
            f"in **opposite directions** — when one rises, the other tends to fall."
        )


    weak_pairs = [(a, b, r) for a, b, r in pairs if abs(r) < 0.1]
    if len(weak_pairs) >= 2:
        insights.append(
            f"🔍 **{len(weak_pairs)} column pair(s)** show almost no relationship — "
            f"those columns appear to change independently of one another."
        )


    redundant = [(a, b, r) for a, b, r in pairs if r > 0.9]
    if redundant:
        a, b, r = redundant[0]
        insights.append(
            f"✅ **{a}** and **{b}** move almost perfectly together "
            f"— they may be measuring the same underlying thing in different units. "
            f"You may only need one of them in a predictive model."
        )


    return insights




def _insights_categorical(
    df: pd.DataFrame,
    x_cols=None,
    y_cols=None,
    agg: str = "mean",
    top_n=None,
    **kwargs,
) -> list[str]:
    """Insights for Categorical Bar/Column charts."""
    insights: list[str] = []
    dims    = x_cols or []
    metrics = y_cols
    agg_lbl = agg.title()


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


                top_cat  = str(agg_s.index[0])
                top_val  = float(agg_s.iloc[0])
                n_cats   = len(agg_s)
                top_share = top_val / total


                insights.append(
                    f"🏆 **{top_cat}** leads in {metric} — "
                    f"{_n(top_val)}, which is {_pct(top_val, total)} of the total."
                )


                if top_share > 0.5:
                    insights.append(
                        f"⚠️ **{top_cat}** alone makes up more than half of all {metric}. "
                        f"This heavy concentration means the overall total is very sensitive to "
                        f"what happens in this one category."
                    )


                if n_cats >= 5:
                    top3_share = float(agg_s.iloc[:3].sum()) / total
                    tail       = "the remaining categories are relatively minor." if top3_share > 0.8 \
                                 else "the remaining categories still carry significant weight."
                    insights.append(
                        f"📊 The top 3 categories account for **{top3_share * 100:.0f}%** of "
                        f"total {metric} — {tail}"
                    )


                if n_cats >= 2:
                    bot_val = float(agg_s.iloc[-1])
                    if bot_val > 0:
                        ratio = top_val / bot_val
                        if ratio >= 5:
                            bot_cat = str(agg_s.index[-1])
                            insights.append(
                                f"🔍 The performance gap is large: **{top_cat}** is "
                                f"**{ratio:.0f}×** higher than **{bot_cat}** — "
                                f"investigate what differentiates top from bottom."
                            )


        else:
            vc        = df[col].value_counts()
            n_total   = int(vc.sum())
            top_cat   = str(vc.index[0])
            top_count = int(vc.iloc[0])
            n_unique  = len(vc)


            insights.append(
                f"🏆 **{top_cat}** is the most common value in **{col}** — "
                f"{top_count:,} rows ({_pct(top_count, n_total)})."
            )


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
    **kwargs,
) -> list[str]:
    """Insights for Pie / Donut charts."""
    insights: list[str] = []
    dims    = x_cols or []
    metrics = y_cols


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


                insights.append(
                    f"🏆 **{top_cat}** is the largest slice, making up "
                    f"**{_pct(top_val, total)}** of total {metric}."
                )


                if n_cats >= 3:
                    top3_share = float(agg_s.iloc[:3].sum()) / total
                    insights.append(
                        f"📊 The top 3 categories together account for "
                        f"**{top3_share * 100:.0f}%** of all {metric}."
                    )


                if share > 0.6:
                    rest_n = n_cats - 1
                    insights.append(
                        f"⚠️ With {_pct(top_val, total)}, **{top_cat}** dominates — "
                        f"the other {rest_n} {'category' if rest_n == 1 else 'categories'} "
                        f"share only {_pct(total - top_val, total)} combined."
                    )
                elif share < 0.25 and n_cats >= 4:
                    insights.append(
                        f"✅ No single category dominates — values are relatively spread across "
                        f"all {n_cats} categories, which suggests a diversified mix."
                    )
        else:
            vc        = df[col].value_counts()
            total     = int(vc.sum())
            top_cat   = str(vc.index[0])
            top_count = int(vc.iloc[0])
            n_cats    = len(vc)
            share     = top_count / total if total else 0


            insights.append(
                f"🏆 **{top_cat}** is the most common — "
                f"{_pct(top_count, total)} of all {n_cats} categories."
            )


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


    for metric in num[:2]:
        if metric not in temp.columns:
            continue


        try:
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
                insights.append(
                    f"📈 **{peak_period}** had the highest {metric} ({_n(g.max())}); "
                    f"**{trough_period}** had the lowest ({_n(g.min())})."
                )
                rng = g.max() - g.min()
                if g.mean() != 0:
                    cv = float(g.std()) / abs(float(g.mean()))
                    if cv > 0.35:
                        insights.append(
                            f"⚠️ **{metric}** varies significantly across periods "
                            f"(range: {_n(g.min())} → {_n(g.max())}) — "
                            f"the pattern may be seasonal or driven by a specific event."
                        )


            else:
                ts = temp.sort_values("_dt").groupby("_dt")[metric].agg(agg)
                if len(ts) < 2:
                    continue


                first_val = float(ts.iloc[0])
                last_val  = float(ts.iloc[-1])


                if first_val != 0:
                    change = (last_val - first_val) / abs(first_val)
                    icon   = "📈" if change > 0 else "📉"
                    word   = "increased" if change > 0 else "decreased"
                    insights.append(
                        f"{icon} **{metric}** {word} by "
                        f"**{abs(change) * 100:.1f}%** overall "
                        f"(from {_n(first_val)} to {_n(last_val)})."
                    )


                peak_dt   = ts.idxmax()
                trough_dt = ts.idxmin()
                peak_date   = str(peak_dt.date())   if hasattr(peak_dt,   "date") else str(peak_dt)
                trough_date = str(trough_dt.date()) if hasattr(trough_dt, "date") else str(trough_dt)
                insights.append(
                    f"🔍 Highest point: **{_n(ts.max())}** on {peak_date}; "
                    f"lowest: **{_n(ts.min())}** on {trough_date}."
                )


                mean_val = float(ts.mean())
                std_val  = float(ts.std())
                if mean_val != 0:
                    cv = std_val / abs(mean_val)
                    if cv > 0.35:
                        insights.append(
                            f"⚠️ **{metric}** fluctuates considerably over time "
                            f"(the spread is {cv * 100:.0f}% of the average). "
                            f"This may point to seasonal patterns or irregular events."
                        )
                    elif cv < 0.05:
                        insights.append(
                            f"✅ **{metric}** is remarkably stable over time "
                            f"— values stay close to {_n(mean_val)} with very little variation."
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


    insights.append(
        f"💡 **{x_col}** and **{y_col}** move {strength} {direction} (r ≈ {r:.2f})."
    )


    if abs(r) >= 0.5:
        if r > 0:
            insights.append(
                f"✅ Higher **{x_col}** tends to go with higher **{y_col}** — "
                f"knowing one gives a useful clue about the other."
            )
        else:
            insights.append(
                f"🔍 Higher **{x_col}** tends to go with lower **{y_col}** — "
                f"a trade-off relationship: when one rises, the other falls."
            )
    elif abs(r) < 0.15:
        insights.append(
            f"🔍 **{x_col}** and **{y_col}** appear unrelated here — "
            f"changes in one do not reliably predict changes in the other."
        )


    if color_col and color_col in df.columns:
        try:
            group_means = df.groupby(color_col)[[x_col, y_col]].mean()
            if len(group_means) > 1:
                top_g = str(group_means[y_col].idxmax())
                bot_g = str(group_means[y_col].idxmin())
                insights.append(
                    f"📊 By group: **{top_g}** has the highest average {y_col} "
                    f"({_n(float(group_means.loc[top_g, y_col]))}); "
                    f"**{bot_g}** has the lowest "
                    f"({_n(float(group_means.loc[bot_g, y_col]))})."
                )
        except Exception:
            pass


    if size_col and size_col in df.columns:
        insights.append(
            f"🔍 Marker **size** reflects **{size_col}** — larger dots = higher values. "
            f"Hover over any dot to see its exact value."
        )


    return insights




def _insights_matrix(
    df: pd.DataFrame,
    index_col: str = None,
    columns_col: str = None,
    values_col: str = None,
    agg: str = "mean",
    view_type: str = "Heatmap",
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


    if view_type and "heatmap" in str(view_type).lower():
        insights.append(
            f"📊 Each cell shows the **{agg.title()}** of **{values_col}** "
            f"for a given **{index_col}** × **{columns_col}** combination. "
            f"Darker/warmer cells = higher values."
        )
    else:
        insights.append(
            f"📊 Each cell shows the **{agg.title()}** of **{values_col}** "
            f"for a given **{index_col}** × **{columns_col}** combination."
        )


    insights.append(
        f"🏆 **Highest cell:** {index_col} = **{top_idx[0]}** × {columns_col} = **{top_idx[1]}** → {_n(top_val)}"
    )
    insights.append(
        f"🔻 **Lowest cell:** {index_col} = **{bot_idx[0]}** × {columns_col} = **{bot_idx[1]}** → {_n(bot_val)}"
    )


    spread = top_val - bot_val
    if spread > 0:
        insights.append(
            f"🔍 Value range: **{_n(bot_val)}** to **{_n(top_val)}**. "
            f"{'Wide range — colour contrast carries real signal.' if spread / max(abs(top_val), abs(bot_val), 1) > 0.5 else 'Narrow range — cells are more similar than the colour may suggest.'}"
        )


    return insights




def _insights_map(
    df: pd.DataFrame,
    lat_col: str = None,
    lon_col: str = None,
    location_col: str = None,
    color_col: str = None,
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


        insights.append(f"📍 **{n_pts:,} location{'s' if n_pts != 1 else ''}** plotted on this map.")


        if color_col and color_col in df.columns:
            n_groups = int(df[color_col].nunique())
            insights.append(
                f"🎨 Points coloured by **{color_col}** ({n_groups} distinct {'value' if n_groups == 1 else 'values'}). "
                f"Look for geographic clustering by colour — hover any dot for exact details."
            )
        else:
            insights.append(
                f"🔍 Dense clusters = highest activity; sparse areas have little or no data."
            )


        if location_col and location_col in df.columns:
            try:
                top_loc = df[location_col].value_counts().index[0]
                top_cnt = int(df[location_col].value_counts().iloc[0])
                insights.append(
                    f"🏆 **{top_loc}** has the most data points ({top_cnt:,} rows) — "
                    f"zoom into that area first for the richest detail."
                )
            except Exception:
                pass


    except Exception:
        pass


    return insights




def outlier_insights(col: str, info: dict) -> list[str]:
    """Generate plain-English outlier insights from an IQR result dict."""
    n   = int(info["out_count"])
    pct = info["pct"]
    lo  = info["lo"]
    hi  = info["hi"]
    q1  = info["q1"]
    q3  = info["q3"]


    if n == 0:
        return [
            f"✅ No unusual values found in **{col}** — the numbers look clean here.",
        ]


    severity = (
        "a very small number of"  if pct < 1
        else "some"               if pct < 5
        else "a notable share of"
    )


    return [
        f"⚠️ **{n:,} {'value' if n == 1 else 'values'}** ({pct}%) in **{col}** are unusually high or low — "
        f"{severity} your data falls outside the expected range.",


        f"🔍 The expected range for **{col}** is roughly **{_n(lo)}** to **{_n(hi)}**. "
        f"The middle 50% of typical values sit between {_n(q1)} and {_n(q3)}.",


        f"💡 Unusual values often signal data-entry errors, one-off events, or genuine extremes — "
        f"investigate each flagged row before including it in analysis or reporting.",
    ]




_FN_MAP: dict = {
    "statistical":  _insights_statistical,
    "distribution": _insights_distribution,
    "correlation":  _insights_correlation,
    "categorical":  _insights_categorical,
    "pie_chart":    _insights_pie,
    "time_series":  _insights_time_series,
    "scatter_plot": _insights_scatter,
    "matrix_table": _insights_matrix,
    "map_plot":     _insights_map,
}




def generate_insights(
    analysis_type: str,
    df: pd.DataFrame,
    uid: str,
    **kwargs,
) -> list[str]:
    """Generate plain-English insights for one chart and store them in session_state."""
    try:
        fn = _FN_MAP.get(analysis_type)
        if fn is None:
            return []


        insights: list[str] = fn(df, **kwargs) or []


        if not insights:
            n_rows = len(df)
            n_cols = len(df.columns)
            insights = [
                f"💡 Chart generated from **{n_rows:,} row{'s' if n_rows != 1 else ''}** "
                f"across **{n_cols} column{'s' if n_cols != 1 else ''}**."
            ]


        try:
            import streamlit as st
            st.session_state[f"auto_insights_{uid}"] = insights
        except Exception:
            pass


        return insights


    except Exception:
        return []
