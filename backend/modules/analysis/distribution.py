"""modules/analysis/distribution.py -- Distribution histogram runner."""


import streamlit as st
import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols
from modules.utils.perf import sample_for_histogram
from modules.analysis.apply_lytrize_standard import apply_lytrize_standard




def run_distribution(df, x_cols=None, y_cols=None, palette=None, **kwargs):
    """Generate histogram + box-plot marginal charts for numeric columns."""
    df, was_sampled = sample_for_histogram(df)
    if was_sampled:
        st.toast("⚡ Distribution chart: sampled 50,000 rows for performance.", icon="⚡")


    charts    = []
    num       = x_cols or _num_cols()[:6]
    pal       = palette or COLORS
    color_col = y_cols[0] if y_cols else None


    for i, col in enumerate(num):
        if color_col and color_col in df.columns:
            fig = px.histogram(
                df,
                x=col,
                color=color_col,
                nbins=35,
                marginal="box",
                barmode="overlay",
                opacity=0.75,
                title=f"Distribution: {col} by {color_col}",
                color_discrete_sequence=pal,
            )
        else:
            fig = px.histogram(
                df,
                x=col,
                nbins=35,
                marginal="box",
                title=f"Distribution: {col}",
                color_discrete_sequence=[pal[i % len(pal)]],
            )


        fig.update_layout(**chart_layout())
        label = f"Dist: {col} by {color_col}" if color_col else f"Dist: {col}"
        apply_lytrize_standard(fig, title=label, xaxis=col, yaxis="Count",
                               analysis_type="distribution")

        # Hide the marginal box-plot's subplot axes (xaxis2, yaxis2)
        # so only the main histogram shows axis ticks/grid/titles
        fig.update_xaxes(showticklabels=False, showgrid=False,
                         zeroline=False, title="", row=2, col=1)
        fig.update_yaxes(showticklabels=False, showgrid=False,
                         zeroline=False, title="", row=2, col=1)

        charts.append((label, fig))


    return charts
