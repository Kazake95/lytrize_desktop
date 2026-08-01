"""modules/analysis/__init__.py -- Analysis registry & configuration layer."""


import uuid
from typing import Optional

import streamlit as st


from modules.analysis.descriptive  import run_descriptive
from modules.analysis.statistical  import run_statistical
from modules.analysis.distribution import run_distribution
from modules.analysis.correlation  import run_correlation
from modules.analysis.categorical  import run_categorical
from modules.analysis.pie_chart    import run_pie_chart
from modules.analysis.time_series  import run_time_series
from modules.analysis.outlier       import run_outlier, OUTLIER_HELP
from modules.analysis.scatter_plot  import run_scatter_plot
from modules.analysis.matrix_table  import run_matrix_heatmap, run_matrix_table
from modules.analysis.map_plot      import run_map_plot
from modules.analysis.data_quality  import run_data_quality
from modules.analysis.insights      import generate_insights


from modules.charts import PALETTES, num_cols as _num_cols, cat_cols as _cat_cols, dt_cols as _dt_cols




ANALYSIS_OPTIONS = [
    {"id": "descriptive",  "icon": "🗂️", "name": "Descriptive",      "desc": "Summary statistics"},
    {"id": "statistical",  "icon": "📐", "name": "Statistical",       "desc": "Mean, std, min, max"},
    {"id": "distribution", "icon": "📊", "name": "Distribution",      "desc": "Histograms & boxplots"},
    {"id": "correlation",  "icon": "🔗", "name": "Correlation",       "desc": "Correlation matrix"},
    {"id": "categorical",  "icon": "🏷️", "name": "Categorical Bar",   "desc": "Bar charts"},
    {"id": "pie_chart",    "icon": "🍩", "name": "Pie & Donut",       "desc": "Share of total"},
    {"id": "time_series",  "icon": "⏱️", "name": "Time Series",       "desc": "Trends over time"},
    {"id": "scatter_plot", "icon": "📉",  "name": "Scatter Plot",      "desc": "Variable relationships"},
    {"id": "matrix_heatmap", "icon": "🔲", "name": "Matrix Heatmap",   "desc": "Cross-tab heatmap"},
    {"id": "matrix_table",   "icon": "📋", "name": "Pivot Table",      "desc": "Cross-tab table"},
    {"id": "map_plot",     "icon": "🗺️", "name": "Map Plot",          "desc": "Geographic scatter"},
]
_RUNNERS = {
    "descriptive":  run_descriptive,
    "statistical":  run_statistical,
    "distribution": run_distribution,
    "correlation":  run_correlation,
    "categorical":  run_categorical,
    "pie_chart":    run_pie_chart,
    "time_series":  run_time_series,
    "outlier":      run_outlier,
    "scatter_plot": run_scatter_plot,
    "matrix_heatmap": run_matrix_heatmap,
    "matrix_table":   run_matrix_table,
    "map_plot":     run_map_plot,
    "data_quality": run_data_quality,
}


_NEEDS_AXES = {"statistical", "distribution", "correlation", "categorical",
               "pie_chart", "time_series", "scatter_plot", "matrix_heatmap", "matrix_table", "map_plot"}


_NO_FORM = set()


_WIDGET_SPEC = {
    "statistical": [
        ("x", "x_cols", "scalar"),
        ("y", "y_cols", "list"),
        ("palette", "palette", "palette"),
    ],
    "distribution": [
        ("x", "x_cols", "list"),
        ("color", "y_cols", "scalar"),
        ("palette", "palette", "palette"),
    ],
    "correlation": [
        ("x", "x_cols", "list"),
        ("palette", "palette", "palette"),
    ],
    "categorical": [
        ("x", "x_cols", "list"),
        ("y", "y_cols", "list"),
        ("agg", "agg", "scalar"),
        ("sort", "sort_by", "scalar_map"),
        ("top_n", "top_n", "number"),
        ("direction", "direction", "scalar"),
        ("dual_y", "dual_y_col", "scalar"),
        ("dual_y_agg", "dual_y_agg", "scalar"),
        ("palette", "palette", "palette"),
    ],
    "pie_chart": [
        ("x", "x_cols", "list"),
        ("y", "y_cols", "list"),
        ("agg", "agg", "scalar"),
        ("sort", "sort_by", "scalar_map"),
        ("top_n", "top_n", "number"),
        ("palette", "palette", "palette"),
    ],
    "time_series": [
        ("x", "x_cols", "scalar"),
        ("y", "y_cols", "list"),
        ("date_part", "date_part", "scalar"),
        ("agg", "agg", "scalar"),
        ("dual_y_ts", "dual_y_col", "scalar"),
        ("dual_y_agg", "dual_y_agg", "scalar"),
        ("palette", "palette", "palette"),
    ],
    "scatter_plot": [
        ("x_col", "x_col", "scalar"),
        ("y_col", "y_col", "scalar"),
        ("color_col", "color_col", "scalar"),
        ("size_col", "size_col", "scalar"),
        ("trendline", "trendline", "scalar"),
        ("palette", "palette", "palette"),
    ],
    "matrix_heatmap": [
        ("index_col", "index_col", "scalar"),
        ("columns_col", "columns_col", "scalar"),
        ("values_col", "values_col", "scalar"),
        ("agg", "agg", "scalar"),
        ("sort_rows", "sort_rows", "scalar_map"),
        ("top_n_rows", "top_n_rows", "number"),
    ],
    "matrix_table": [
        ("index_col", "index_col", "scalar"),
        ("columns_col", "columns_col", "scalar"),
        ("values_col", "values_col", "scalar"),
        ("agg", "agg", "scalar"),
        ("sort_rows", "sort_rows", "scalar_map"),
        ("top_n_rows", "top_n_rows", "number"),
    ],
    "map_plot": [
        ("map_mode", "map_mode", "scalar"),
        ("lat_col", "lat_col", "scalar"),
        ("lon_col", "lon_col", "scalar"),
        ("location_col", "location_col", "scalar"),
        ("color_col", "color_col", "scalar"),
        ("value_col", "value_col", "scalar"),
        ("agg_func", "agg_func", "scalar"),
        ("map_style", "map_style", "scalar"),
        ("marker_opacity", "marker_opacity", "number"),
        ("invert_colorscale", "invert_colorscale", "bool"),
        ("show_borders", "show_borders", "bool"),
        ("geo_col", "geo_col", "scalar"),
        ("choropleth_colorscale", "choropleth_colorscale", "scalar"),
        ("choropleth_projection", "choropleth_projection", "scalar"),
        ("choropleth_scope", "choropleth_scope", "scalar"),
        ("choropleth_show_borders", "choropleth_show_borders", "bool"),
    ],
}


def _collect_widget_state(aid: str, uid: Optional[str] = None) -> dict:
    """Capture current widget values for an analysis type.

    Pass `uid` to read from the uid-scoped keys used by the "regenerate
    chart" panel; omit it to read from the plain per-analysis-type keys used
    when first configuring a new chart.
    """
    state = {}
    key_fn = (lambda key: _sk_uid(uid, aid, key)) if uid is not None else (lambda key: _sk(aid, key))
    for key, _kwarg, kind in _WIDGET_SPEC.get(aid, []):
        wkey = key_fn(key)
        if wkey in st.session_state:
            state[key] = st.session_state[wkey]
    return state


_AGG_FUNCS = {
    "Avg": "mean",
    "Sum":        "sum",
    "Median":     "median",
    "Count":      "count",
    "Min":        "min",
    "Max":        "max",
}


_DATE_PARTS = {
    "None":           None,
    "Year":           "Y",
    "Quarter":        "Q",
    "Month (number)": "M",
    "Month Name":     "month_name",
    "Weekday Name":   "weekday_name",
    "Day":            "D",
    "Hour":           "H",
}




def _sk(aid: str, key: str) -> str:
    """Build a namespaced session_state key for a widget inside analysis `aid`."""
    return f"_cfg_{aid}_{key}"




def _g(aid: str, key: str, default=None):
    """Read a widget value from session_state, falling back to `default`."""
    return st.session_state.get(_sk(aid, key), default)




def _sk_uid(uid: str, aid: str, key: str) -> str:
    """Namespaced key scoped to a specific chart uid for the regenerate panel."""
    return f"_edit_{uid}_{aid}_{key}"




def _g_uid(uid: str, aid: str, key: str, default=None):
    return st.session_state.get(_sk_uid(uid, aid, key), default)




def _ensure_single_choice_state(key: str, options, default):
    """Normalize legacy list state so a selectbox can safely reuse the key."""
    current = st.session_state.get(key, default)
    if isinstance(current, list):
        current = next((v for v in current if v in options and v not in (None, "")), default)
    if current not in options:
        current = default
    st.session_state[key] = current




def _single_choice_value(value, default=None):
    """Return a scalar value or None from selectbox/multiselect-compatible state."""
    if isinstance(value, list):
        value = next((v for v in value if v not in (None, "")), default)
    return None if value in (None, "") else value




def _render_config_panel_body(aid: str, df, sk) -> None:
    """Shared widget-rendering body for render_config_panel, parametrized by
    a `sk(key)` function that builds the right session_state key -- plain
    per-analysis-type keys for a new chart, or uid-scoped keys when
    reconfiguring an existing chart via the "regenerate" panel."""
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"

    if aid == "descriptive":
        st.info("No configuration needed -- outputs a full stats table.")

    elif aid == "statistical":
        c1, c2, c3 = st.columns(3)
        with c1:
            _ensure_single_choice_state(sk("x"), [NONE] + cat, NONE)
            st.selectbox("Group by (optional)", [NONE] + cat, key=sk("x"))
        with c2: st.multiselect("Metrics", num, default=num[:4], key=sk("y"))
        with c3:
            if aid not in ("matrix_heatmap", "matrix_table", "map_plot"):
                st.selectbox("🎨 Palette", list(PALETTES.keys()), key=sk("palette"))


    elif aid == "distribution":
        c1, c2, c3 = st.columns(3)
        with c1: st.multiselect("Numeric columns", num, default=num[:4], key=sk("x"))
        with c2:
            _ensure_single_choice_state(sk("color"), [NONE] + cat, NONE)
            st.selectbox("Colour by (optional)", [NONE] + cat, key=sk("color"))
        with c3:
            if aid not in ("matrix_heatmap", "matrix_table", "map_plot"):
                st.selectbox("🎨 Palette", list(PALETTES.keys()), key=sk("palette"))


    elif aid == "correlation":
        st.multiselect("Columns", num, default=num, key=sk("x"))


    elif aid == "pie_chart":
        c1, c2, c3, c4, c5, c6 = st.columns(6)
        with c1:
            st.multiselect("Dimensions", cat, default=cat[:2], key=sk("x"),
                           help="Columns to split the data by")
        with c2:
            st.multiselect("Metrics", num, key=sk("y"),
                           help="Values to aggregate (optional)")
        with c3:
            st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"),
                         help="How to combine multiple metric values")
        with c4:
            st.selectbox("Sort", ["Value ↓","Value ↑","Category A→Z","Category Z→A"],
                         key=sk("sort"), help="Order of wedge display")
        with c5:
            st.selectbox("Palette", list(PALETTES.keys()), key=sk("palette"),
                         help="Color scheme for the chart")
        with c6:
            st.number_input("Top N", min_value=0, max_value=200, step=1, value=0,
                            key=sk("top_n"), help="Max slices to show (0 = all categories)")

    elif aid == "categorical":
        c1, c2, c3, c4, c5, c6, c7, c8 = st.columns(8)
        with c1:
            st.selectbox("Dimension", cat, key=sk("x"),
                         help="Column to split the data by")
        with c2:
            st.selectbox("Metric", num, key=sk("y"),
                         help="Value to aggregate (optional)")
        with c3:
            st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"),
                         help="How to combine multiple metric values")
        with c4:
            st.selectbox(
                "📊 Direction",
                ["Vertical (Column chart)", "Horizontal (Bar chart)"],
                key=sk("direction"),
                help="Vertical = column chart. Horizontal = bar chart.")
        with c5:
            st.number_input("Top N", min_value=0, max_value=200, step=1, value=0,
                            key=sk("top_n"), help="Max bars to show (0 = show all)")
        with c6:
            dual_opts = [NONE] + list(num)
            st.selectbox("Secondary Y-Axis", dual_opts, key=sk("dual_y"),
                         help="None = disabled.")
        with c7:
            st.selectbox("Secondary Agg", list(_AGG_FUNCS.keys()),
                         key=sk("dual_y_agg"),
                         help="Aggregation for secondary Y-axis metric")
        with c8:
            st.selectbox("Palette", list(PALETTES.keys()), key=sk("palette"),
                         help="Color scheme for the chart")


    elif aid == "time_series":
        dt_candidates = dt if dt else all_cols
        c1, c2, c3, c4, c5, c6, c7 = st.columns(7)
        with c1:
            default_dt = dt_candidates[0] if dt_candidates else NONE
            _ensure_single_choice_state(sk("x"), [NONE] + dt_candidates, default_dt)
            st.selectbox("Date / Time", [NONE] + dt_candidates, key=sk("x"))
        with c2: st.selectbox("Primary metric", num, index=0 if num else None, key=sk("y"))
        with c3: st.selectbox("Date grouping", list(_DATE_PARTS.keys()), key=sk("date_part"))
        with c4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        with c5:
            dual_opts_ts = [NONE] + list(num)
            st.selectbox("Secondary Y-Axis", dual_opts_ts, key=sk("dual_y_ts"))
        with c6:
            st.selectbox("Secondary Agg", list(_AGG_FUNCS.keys()), key=sk("dual_y_agg"))
        with c7:
            st.selectbox("Palette", list(PALETTES.keys()), key=sk("palette"))


    elif aid == "scatter_plot":
        sp1, sp2, sp3, sp4, sp5, sp6 = st.columns(6)
        with sp1: st.selectbox("X Axis", [NONE] + num, key=sk("x_col"))
        with sp2: st.selectbox("Y Axis", [NONE] + num, key=sk("y_col"))
        with sp3: st.selectbox("Colour", [NONE] + cat, key=sk("color_col"))
        with sp4: st.selectbox("Size", [NONE] + num, key=sk("size_col"))
        with sp5: st.selectbox("Trendline", ["None", "ols", "lowess"], key=sk("trendline"))
        with sp6:
            if aid not in ("matrix_heatmap", "matrix_table", "map_plot"):
                st.selectbox("🎨 Palette", list(PALETTES.keys()), key=sk("palette"))


    elif aid == "matrix_heatmap":
        mt1, mt2, mt3, mt4, mt5, mt6 = st.columns(6)
        with mt1: st.selectbox("Row (Index column)", [NONE] + cat, key=sk("index_col"))
        with mt2: st.selectbox("Column dimension", [NONE] + cat, key=sk("columns_col"))
        with mt3: st.selectbox("Value column", [NONE] + num, key=sk("values_col"))
        with mt4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        with mt5: st.selectbox("Sort rows by", ["Value ↓", "Value ↑", "Category A→Z", "Category Z→A"],
                               key=sk("sort_rows"),
                               help="Sort index rows by their aggregated value or alphabetically")
        with mt6: st.number_input("Top N rows (0 = all)", min_value=0, max_value=500,
                                  step=5, value=0, key=sk("top_n_rows"),
                                  help="Limit to the top N rows after sorting. 0 shows all rows.")

    elif aid == "matrix_table":
        mt1, mt2, mt3, mt4, mt5, mt6 = st.columns(6)
        with mt1: st.selectbox("Row (Index column)", [NONE] + cat, key=sk("index_col"))
        with mt2: st.selectbox("Column dimension", [NONE] + cat, key=sk("columns_col"))
        with mt3: st.selectbox("Value column", [NONE] + num, key=sk("values_col"))
        with mt4: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg"))
        with mt5: st.selectbox("Sort rows by", ["Value ↓", "Value ↑", "Category A→Z", "Category Z→A"],
                               key=sk("sort_rows"),
                               help="Sort index rows by their aggregated value or alphabetically")
        with mt6: st.number_input("Top N rows (0 = all)", min_value=0, max_value=500,
                                  step=5, value=0, key=sk("top_n_rows"),
                                  help="Limit to the top N rows after sorting. 0 shows all rows.")

    elif aid == "map_plot":
        from modules.analysis.map_plot import _CHOROPLETH_SCALES, _PROJECTIONS, _SCOPES, detect_geo_column
        _map_mode_opts = ["Scatter (Lat/Lon)", "Choropleth (Location Names)"]
        _df_sig = f"{df.shape}_{list(df.columns)}"
        _geo_cache_key = "_detected_geo_col"
        _geo_sig_key   = "_detected_geo_sig"
        if (st.session_state.get(_geo_sig_key) != _df_sig
                or _geo_cache_key not in st.session_state):
            st.session_state[_geo_cache_key] = detect_geo_column(df)
            st.session_state[_geo_sig_key]   = _df_sig
        _detected_geo  = st.session_state[_geo_cache_key]
        _default_mode  = 1 if _detected_geo else 0
        _mode = st.session_state.get(sk("map_mode"), _map_mode_opts[_default_mode])
        if _mode == "Scatter (Lat/Lon)":
            mp1, mp2, mp3, mp4, mp5, mp6, mp7, mp8, mp9, mp10, mp11 = st.columns(11)
            with mp1: st.selectbox("Mode", _map_mode_opts, index=_default_mode, key=sk("map_mode"))
            with mp2: st.selectbox("Latitude", [NONE] + num, key=sk("lat_col"))
            with mp3: st.selectbox("Longitude", [NONE] + num, key=sk("lon_col"))
            with mp4: st.selectbox("Location", [NONE] + cat, key=sk("location_col"))
            with mp5: st.selectbox("Colour", [NONE] + cat + num, key=sk("color_col"))
            with mp6: st.selectbox("Value", [NONE] + num, key=sk("value_col"))
            with mp7: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg_func"))
            with mp8: st.selectbox("Style", ["carto-positron", "open-street-map", "carto-darkmatter"],
                                   key=sk("map_style"))
            with mp9: st.slider("Opacity", 0.3, 1.0, 0.82, 0.05, key=sk("marker_opacity"))
            with mp10: st.checkbox("Invert", key=sk("invert_colorscale"))
            with mp11: st.checkbox("Borders", value=True, key=sk("show_borders"))
        else:
            _all_cols_str = [c for c in df.columns if df[c].dtype == object]
            _geo_default_idx = (_all_cols_str.index(_detected_geo)
                                if _detected_geo and _detected_geo in _all_cols_str else 0)
            cg0, cg1, cg2, cg3, cg4, cg5, cg6 = st.columns(7)
            with cg0: st.selectbox("Mode", _map_mode_opts, index=_default_mode, key=sk("map_mode"))
            with cg1: st.selectbox("Location", _all_cols_str if _all_cols_str else df.columns.tolist(),
                                   index=_geo_default_idx, key=sk("geo_col"))
            with cg2: st.selectbox("Value", [NONE] + num, key=sk("value_col"))
            with cg3: st.selectbox("Aggregation", list(_AGG_FUNCS.keys()), key=sk("agg_func"))
            with cg4: st.selectbox("Scale", _CHOROPLETH_SCALES, key=sk("choropleth_colorscale"))
            with cg5: st.selectbox("Projection", _PROJECTIONS, key=sk("choropleth_projection"))
            with cg6: st.selectbox("Scope", _SCOPES, key=sk("choropleth_scope"))
            # Borders checkbox placed below columns to avoid overflow
            st.checkbox("Borders", value=True, key=sk("choropleth_show_borders"))


def render_config_panel(aid: str, df, uid: Optional[str] = None) -> None:
    """Render configuration widgets for the analysis identified by `aid`.

    Pass `uid` to render into the uid-scoped keys used by the "regenerate
    chart" panel; omit it (the default) to render into the plain
    per-analysis-type keys used when configuring a brand-new chart.
    """
    sk = (lambda key: _sk_uid(uid, aid, key)) if uid is not None else (lambda key: _sk(aid, key))
    _render_config_panel_body(aid, df, sk)






def _collect_kwargs(aid: str, df, uid: Optional[str] = None) -> dict:
    """Read widget values from session_state and return a kwargs dict for the runner.

    Pass `uid` to read from the uid-scoped keys used by the "regenerate
    chart" panel; omit it (the default) to read from the plain
    per-analysis-type keys used when configuring a brand-new chart.
    """
    num, cat, dt, all_cols = _num_cols(), _cat_cols(), _dt_cols(), df.columns.tolist()
    NONE = "None"
    g = (lambda key, default=None: _g_uid(uid, aid, key, default)) if uid is not None \
        else (lambda key, default=None: _g(aid, key, default))

    _sort_map = {
        "Value ↓":       "Value (Desc)",
        "Value ↑":       "Value (Asc)",
        "Category A→Z":  "Category (A-Z)",
        "Category Z→A":  "Category (Z-A)",
    }

    pal_label = g("palette", list(PALETTES.keys())[0])
    kwargs    = {"palette": PALETTES.get(pal_label, list(PALETTES.values())[0])}

    if aid == "statistical":
        x = _single_choice_value(g("x", NONE), NONE)
        kwargs.update(x_cols=None if x is None else [x], y_cols=g("y", num[:4]) or num)

    elif aid == "distribution":
        color = _single_choice_value(g("color", NONE), NONE)
        kwargs.update(x_cols=g("x", num[:4]) or num[:4], y_cols=None if color is None else [color])

    elif aid == "correlation":
        kwargs.update(x_cols=g("x", num) or num)

    elif aid == "categorical":
        x        = _single_choice_value(g("x", cat[:2] if cat else NONE), cat[:2] if cat else NONE)
        y        = _single_choice_value(g("y", NONE), NONE)
        agg      = _AGG_FUNCS.get(g("agg", "Avg"), "mean")
        raw_sort = g("sort", "Value ↓")
        sort_by  = _sort_map.get(raw_sort, "Value (Desc)")
        top_n_v  = int(g("top_n", 0) or 0)
        top_n    = top_n_v if top_n_v > 0 else None
        kwargs.update(x_cols=None if x in (NONE, None, "") else [x], 
                      y_cols=None if y in (NONE, None, "") else [y], 
                      agg=agg, sort_by=sort_by, top_n=top_n)
        direction = g("direction", "Vertical (Column chart)")
        raw_dual  = g("dual_y", NONE)
        dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
        y_list = kwargs.get("y_cols") or []
        if dual_y and y_list and dual_y in y_list:
            dual_y = None
        dual_y_agg = _AGG_FUNCS.get(g("dual_y_agg", "Avg"), "mean") if dual_y else None
        kwargs.update(direction=direction, dual_y_col=dual_y, dual_y_agg=dual_y_agg)

    elif aid == "pie_chart":
        x        = g("x", cat[:2]) or cat[:2]
        y_raw    = g("y", [])
        y        = y_raw if y_raw else None
        agg      = _AGG_FUNCS.get(g("agg", "Avg"), "mean")
        raw_sort = g("sort", "Value ↓")
        sort_by  = _sort_map.get(raw_sort, "Value (Desc)")
        top_n_v  = int(g("top_n", 0) or 0)
        top_n    = top_n_v if top_n_v > 0 else None
        kwargs.update(x_cols=x, y_cols=y, agg=agg, sort_by=sort_by, top_n=top_n)

    elif aid == "scatter_plot":
        def _sp_resolve(key):
            v = g(key, NONE)
            return None if v in (NONE, None, "") else v
        kwargs.update(
            x_col=_sp_resolve("x_col"),
            y_col=_sp_resolve("y_col"),
            color_col=_sp_resolve("color_col"),
            size_col=_sp_resolve("size_col"),
            trendline=g("trendline", "None"),
        )

    elif aid == "matrix_heatmap":
        def _mh_resolve(key):
            v = g(key, NONE)
            return None if v in (NONE, None, "") else v
        _mh_sort_map = {
            "Value ↓": "value_desc", "Value ↑": "value_asc",
            "Category A→Z": "cat_asc", "Category Z→A": "cat_desc",
        }
        _mh_top_n_v = int(g("top_n_rows", 0) or 0)
        kwargs.update(
            index_col=_mh_resolve("index_col"),
            columns_col=_mh_resolve("columns_col"),
            values_col=_mh_resolve("values_col"),
            agg=_AGG_FUNCS.get(g("agg", "Avg"), "mean"),
            sort_rows=_mh_sort_map.get(g("sort_rows", "Value ↓"), "value_desc"),
            top_n_rows=_mh_top_n_v if _mh_top_n_v > 0 else None,
        )

    elif aid == "matrix_table":
        def _mt_resolve(key):
            v = g(key, NONE)
            return None if v in (NONE, None, "") else v
        _mt_sort_map = {
            "Value ↓": "value_desc", "Value ↑": "value_asc",
            "Category A→Z": "cat_asc", "Category Z→A": "cat_desc",
        }
        _mt_top_n_v = int(g("top_n_rows", 0) or 0)
        kwargs.update(
            index_col=_mt_resolve("index_col"),
            columns_col=_mt_resolve("columns_col"),
            values_col=_mt_resolve("values_col"),
            agg=_AGG_FUNCS.get(g("agg", "Avg"), "mean"),
            sort_rows=_mt_sort_map.get(g("sort_rows", "Value ↓"), "value_desc"),
            top_n_rows=_mt_top_n_v if _mt_top_n_v > 0 else None,
        )

    elif aid == "map_plot":
        def _mp_resolve(key):
            v = g(key, NONE)
            return None if v in (NONE, None, "") else v
        _mp_mode = g("map_mode", "Scatter (Lat/Lon)")
        if _mp_mode == "Choropleth (Location Names)":
            kwargs.update(
                geo_col=_mp_resolve("geo_col"),
                value_col=_mp_resolve("value_col"),
                agg_func=_AGG_FUNCS.get(g("agg_func", "Sum"), "sum"),
                invert_colorscale=bool(g("invert_colorscale", False)),
                choropleth_colorscale=g("choropleth_colorscale", "Blues"),
                choropleth_projection=g("choropleth_projection", "natural earth"),
                choropleth_scope=g("choropleth_scope", "world"),
                choropleth_show_borders=bool(g("choropleth_show_borders", True)),
            )
        else:
            kwargs.update(
                lat_col=_mp_resolve("lat_col"),
                lon_col=_mp_resolve("lon_col"),
                location_col=_mp_resolve("location_col"),
                value_col=_mp_resolve("value_col"),
                size_col=_mp_resolve("size_col"),
                color_col=_mp_resolve("color_col"),
                agg_func=_AGG_FUNCS.get(g("agg_func", "Avg"), "mean"),
                invert_colorscale=bool(g("invert_colorscale", False)),
                map_style=g("map_style", "carto-positron"),
                marker_opacity=float(g("marker_opacity", 0.82)),
            )

    elif aid == "time_series":
        x         = _single_choice_value(g("x", NONE), NONE)
        y         = _single_choice_value(g("y", num[0] if num else NONE), num[0] if num else NONE)
        agg       = _AGG_FUNCS.get(g("agg", "Avg"), "mean")
        date_part = _DATE_PARTS.get(g("date_part", "None"))
        raw_dual  = g("dual_y_ts", NONE)
        dual_y    = None if (not raw_dual or raw_dual == NONE) else raw_dual
        if dual_y and dual_y in ([y] if y else []):
            dual_y = None
        dual_y_agg = _AGG_FUNCS.get(g("dual_y_agg", "Avg"), "mean") if dual_y else None
        kwargs.update(x_cols=None if x in (NONE, None, "") else [x], y_cols=[y] if y else [], agg=agg,
                      date_part=date_part, dual_y_col=dual_y, dual_y_agg=dual_y_agg)

    return kwargs


def _run(aid: str, df, **kwargs):
    """Dispatch to the correct runner and return a list of (uid, title, fig) tuples."""
    fn = _RUNNERS.get(aid)
    if not fn:
        return []


    try:
        raw = fn(df) if aid in ("descriptive", "data_quality") else fn(df, **kwargs)


        results = []
        for title, fig in raw:
            uid = str(uuid.uuid4())[:8]


            generate_insights(aid, df, uid, **kwargs)


            results.append((uid, title, fig))


        return results


    except Exception as e:
        st.error(f"Analysis error ({aid}): {e}")
        return []