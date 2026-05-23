"""
modules/analysis/distribution.py -- Distribution histogram runner.
=================================================================

Produces one histogram + box-plot marginal per selected numeric column.
The box-plot marginal sits above the histogram and lets users quickly spot
skew, quartiles, and outliers alongside the frequency distribution.

Each chart is coloured with a different palette entry so a dashboard
containing multiple distribution charts is visually distinguishable at a glance.

Bug fixed in this version
-------------------------
The function docstring for run_distribution() was placed AFTER several
executable statements (the sample call and the toast). Python only recognises
a string literal as a docstring when it is the *first* statement of a
function/class/module body — placing code before it means
``run_distribution.__doc__`` was silently ``None``, breaking any tooling or
help() call that relies on it. The docstring is now the first statement.
"""

import streamlit as st
import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols
from modules.utils.perf import sample_for_histogram


def run_distribution(df, x_cols=None, y_cols=None, palette=None, **kwargs):
    """
    Generate histogram + box-plot marginal charts for numeric columns.

    One histogram per column in x_cols. Large datasets are sampled down to
    50 K rows before plotting to keep the Plotly JSON payload manageable;
    a toast notification informs the user when sampling occurs.

    Args:
        df:      Working DataFrame.
        x_cols:  Numeric columns to plot. Defaults to the first 6 numeric cols.
        y_cols:  Optional list containing one categorical column for colour-split.
                 When provided, each histogram bar is split by category value,
                 each category gets its own colour, and a legend is shown.
        palette: List of hex colour strings.
        **kwargs: Extra kwargs silently ignored (runner protocol).

    Returns:
        list of (title: str, fig: Figure) -- one entry per column in x_cols.
    """
    # Sample large datasets to keep the Plotly JSON payload manageable.
    # Histogram shape is statistically robust at 50 K rows for most distributions.
    df, was_sampled = sample_for_histogram(df)
    if was_sampled:
        st.toast("⚡ Distribution chart: sampled 50,000 rows for performance.", icon="⚡")

    charts    = []
    num       = x_cols or _num_cols()[:6]   # Cap default at 6 to avoid overwhelming output.
    pal       = palette or COLORS
    color_col = y_cols[0] if y_cols else None  # y_cols carries the optional "Colour by" column.

    for i, col in enumerate(num):
        if color_col and color_col in df.columns:
            # ── Colour-split histogram ────────────────────────────────────────
            # One trace per unique category value; overlaid so shapes stay legible.
            fig = px.histogram(
                df,
                x=col,
                color=color_col,
                nbins=35,            # 35 bins is a good default for most real-world datasets.
                marginal="box",      # Box plot above the histogram shows quartiles and outliers.
                barmode="overlay",   # Overlay keeps bars legible when split by category.
                opacity=0.75,
                title=f"Distribution: {col} by {color_col}",
                color_discrete_sequence=pal,
            )
        else:
            # ── Single-colour histogram (no colour split selected) ────────────
            fig = px.histogram(
                df,
                x=col,
                nbins=35,            # 35 bins is a sensible default for most datasets.
                marginal="box",      # Box plot above the histogram for quartile visibility.
                title=f"Distribution: {col}",
                color_discrete_sequence=[pal[i % len(pal)]],
            )

        fig.update_layout(**chart_layout())
        label = f"Dist: {col} by {color_col}" if color_col else f"Dist: {col}"
        charts.append((label, fig))

    return charts
