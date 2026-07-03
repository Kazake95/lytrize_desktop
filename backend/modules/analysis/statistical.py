"""modules/analysis/statistical.py -- Statistical aggregation chart runner."""


import pandas as pd
import plotly.express as px
from modules.charts import chart_layout, COLORS, num_cols as _num_cols
from modules.analysis.apply_lytrize_standard import apply_lytrize_standard



def run_statistical(df, x_cols=None, y_cols=None, palette=None, **kwargs):
    """Generate statistical aggregation bar charts with Mean, Min, Max, Std always shown."""
    charts = []
    num = y_cols or _num_cols()
    grp = x_cols[0] if x_cols else None
    pal = palette or COLORS

    if grp and grp in df.columns:
        # With Group by: 
        # - If single metric: ONE chart with x=group values, grouped bars=Mean/Min/Max/Std
        # - If multiple metrics: ONE chart per metric with x=group values, grouped bars=Mean/Min/Max/Std
        
        if len(num) == 1:
            # Single metric: One chart with group values on x-axis, 4 bars per group (Mean/Min/Max/Std)
            metric = num[0]
            stats = df.groupby(grp)[metric].agg(['mean', 'min', 'max', 'std']).reset_index()
            stats.columns = [grp, 'Mean', 'Min', 'Max', 'Std Dev']
            
            # Melt for grouped bar chart
            stats_melted = stats.melt(id_vars=[grp], value_vars=['Mean', 'Min', 'Max', 'Std Dev'],
                                      var_name='Statistic', value_name='Value')
            
            fig = px.bar(
                stats_melted, x=grp, y='Value', color='Statistic',
                title=f"Statistics of {metric} by {grp}",
                color_discrete_sequence=pal, text_auto=".2f",
                barmode='group')
            fig.update_layout(**chart_layout())
            apply_lytrize_standard(fig, title=f"Statistics of {metric} by {grp}",
                                   xaxis=grp, yaxis="Value",
                                   analysis_type="statistical")
            charts.append((f"Statistics of {metric} by {grp}", fig))
        else:
            # Multiple metrics: One chart per metric
            for metric in num:
                stats = df.groupby(grp)[metric].agg(['mean', 'min', 'max', 'std']).reset_index()
                stats.columns = [grp, 'Mean', 'Min', 'Max', 'Std Dev']
                
                # Melt for grouped bar chart
                stats_melted = stats.melt(id_vars=[grp], value_vars=['Mean', 'Min', 'Max', 'Std Dev'],
                                          var_name='Statistic', value_name='Value')
                
                fig = px.bar(
                    stats_melted, x=grp, y='Value', color='Statistic',
                    title=f"Statistics of {metric} by {grp}",
                    color_discrete_sequence=pal, text_auto=".2f",
                    barmode='group')
                fig.update_layout(**chart_layout())
                apply_lytrize_standard(fig, title=f"Statistics of {metric} by {grp}",
                                       xaxis=grp, yaxis="Value",
                                       analysis_type="statistical")
                charts.append((f"Statistics of {metric} by {grp}", fig))
    else:
        # Without Group by: Create one chart with all metrics and their Mean, Min, Max, Std
        all_stats = []
        for metric in num:
            stats = df[metric].agg(['mean', 'min', 'max', 'std'])
            for stat_name, stat_val in stats.items():
                all_stats.append({
                    'Column': metric,
                    'Statistic': stat_name,
                    'Value': stat_val
                })
        
        stats_df = pd.DataFrame(all_stats)
        
        fig = px.bar(
            stats_df, x='Column', y='Value', color='Statistic',
            title="Statistical Summary",
            color_discrete_sequence=pal, text_auto=".2f",
            barmode='group')
        fig.update_layout(**chart_layout())
        apply_lytrize_standard(fig, title="Statistical Summary",
                               xaxis="Column", yaxis="Value",
                               analysis_type="statistical")
        charts.append(("Statistical Summary", fig))

    return charts