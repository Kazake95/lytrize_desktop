"""modules/analysis/statistical.py -- Statistical aggregation chart runner."""


import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols
from modules.analysis.apply_lytrize_standard import apply_lytrize_standard




def run_statistical(df, x_cols=None, y_cols=None, agg="mean", palette=None, **kwargs):
    """Generate statistical aggregation bar charts."""
    charts    = []
    num       = y_cols or _num_cols()
    grp       = x_cols[0] if x_cols else None
    agg_label = agg.title()
    pal       = palette or COLORS


    if grp and grp in df.columns:
        for metric in num:
            agg_vals = df.groupby(grp)[metric].agg(agg).reset_index()
            agg_vals.columns = [grp, f"{agg_label} {metric}"]
            fig = px.bar(
                agg_vals, x=grp, y=f"{agg_label} {metric}",
                title=f"{agg_label} of {metric} by {grp}",
                color=grp, color_discrete_sequence=pal, text_auto=".2f")
            fig.update_layout(**chart_layout())
            apply_lytrize_standard(fig, title=f"{agg_label} of {metric} by {grp}",
                                   xaxis=grp, yaxis=f"{agg_label} {metric}",
                                   analysis_type="statistical")
            charts.append((f"{agg_label} by {grp}", fig))


    else:
        summary = df[num].agg(agg).reset_index()
        summary.columns = ["Column", agg_label]
        fig = px.bar(
            summary, x="Column", y=agg_label,
            title=f"{agg_label} Overview",
            color="Column", color_discrete_sequence=pal, text_auto=".2f")
        fig.update_layout(**chart_layout())
        apply_lytrize_standard(fig, title=f"{agg_label} Overview",
                               xaxis="Column", yaxis=agg_label,
                               analysis_type="statistical")
        charts.append((f"{agg_label} Values", fig))


        stds = df[num].std().reset_index()
        stds.columns = ["Column", "Std Dev"]
        fig2 = px.bar(
            stds, x="Column", y="Std Dev",
            title="Standard Deviation",
            color="Column", color_discrete_sequence=pal, text_auto=".2f")
        fig2.update_layout(**chart_layout())
        apply_lytrize_standard(fig2, title="Standard Deviation",
                               xaxis="Column", yaxis="Std Dev",
                               analysis_type="statistical")
        charts.append(("Standard Deviation", fig2))


    return charts
