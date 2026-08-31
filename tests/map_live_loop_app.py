import sys
sys.path.insert(0, r"g:\port-apps\coding\workspace\lytrize_desktop\backend")

import streamlit as st
import pandas as pd
from modules.analysis.map_plot import run_map_plot

df = pd.DataFrame({
    "lat": [40.71, 34.05, 41.88, 29.76, 37.77],
    "lon": [-74.01, -118.24, -87.63, -95.37, -122.42],
    "city": ["NYC", "LA", "CHI", "HOU", "SF"],
    "sales": [100, 250, 90, 310, 180],
})
st.session_state["df"] = df

UID = "t1"
KP = "analysis"
TITLE = "Map: Locations"
fig = run_map_plot(df, lat_col="lat", lon_col="lon", color_col="sales",
                   value_col="sales", map_style="OpenStreetMap (Dark)")[0][1]

st.session_state.setdefault(f"chart_meta_{UID}", {})
st.session_state[f"chart_type_{UID}"] = "map_plot"

from modules.ui.chart_card import render_chart_card

meta = st.session_state[f"chart_meta_{UID}"]
render_chart_card(
    UID, TITLE, fig, "map_plot", meta,
    key_prefix=KP, edit_mode=True, viewing_saved=False,
    on_meta_changed=lambda u, k, v: st.session_state[f"chart_meta_{u}"].update({k: v}),
)

# Report what the card actually rendered (the cached display figure).
fig_show = st.session_state.get(f"_display_fig_{UID}")
if fig_show is not None:
    try:
        ca = fig_show.layout.coloraxis
        meta_now = st.session_state.get(f"chart_meta_{UID}", {})
        opts = meta_now.get("display_options", {})
        st.session_state["_live_result"] = {
            "show_colorbar": opts.get("show_colorbar", "ABSENT"),
            "colorscale": opts.get("heatmap_colorscale", "ABSENT"),
            "cb_title": opts.get("colorbar_title", "ABSENT"),
            "applied_showscale": ca.showscale,
            "applied_cs0": (ca.colorscale[0][1] if ca.colorscale else None),
            "applied_title": ca.colorbar.title.text,
        }
    except Exception as e:
        st.session_state["_live_result"] = {"error": repr(e)}
