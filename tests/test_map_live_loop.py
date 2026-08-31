import sys, io, traceback
sys.path.insert(0, r"g:\port-apps\coding\workspace\lytrize_desktop")
sys.path.insert(0, r"g:\port-apps\coding\workspace\lytrize_desktop\backend")
out = io.StringIO()
def p(*a): print(*a, file=out)

# ---------- Part 1: live widget loop (Streamlit AppTest) ----------
try:
    from streamlit.testing.v1 import AppTest
    at = AppTest.from_file(
        r"g:\port-apps\coding\workspace\lytrize_desktop\tests\map_live_loop_app.py",
        default_timeout=120)
    at.run()
    p("app exception:", at.exception)
    r = at.session_state["_live_result"]
    cb = at.checkbox(key="analysis_scb_t1"); cb.uncheck()
    at.selectbox(key="analysis_cs_t1").set_value("Viridis")
    at.text_input(key="analysis_cbt_t1").set_value("Revenue")
    at.run()
    r2 = at.session_state["_live_result"]
    p("after toggle:", r2)
    ok = (r2["show_colorbar"] is False and r2["applied_showscale"] is False
          and r2["colorscale"] == "Viridis" and r2["applied_cs0"] == "#440154"
          and r2["cb_title"] == "Revenue" and r2["applied_title"] == "Revenue")
    p("LIVE LOOP:", "PASS" if ok else "FAIL")
except Exception:
    p("LIVE LOOP harness error (AppTest may be unavailable):")
    traceback.print_exc(file=out)

# ---------- Part 2: 3 map styles + legacy normalization ----------
try:
    import pandas as pd
    from modules.analysis.map_plot import (
        run_map_plot, _tiles_online, MAP_STYLES, _normalize_map_style)
    p("tiles_online:", _tiles_online())
    p("normalize legacy:", {s: _normalize_map_style(s) for s in (
        "carto-positron", "carto-darkmatter", "open-street-map", "white-bg",
        "satellite", "esri-imagery")})
    df = pd.DataFrame({
        "lat": [40.71, 34.05, 41.88], "lon": [-74.01, -118.24, -87.63],
        "city": ["NYC", "LA", "CHI"], "sales": [100, 250, 90],
    })
    for style in MAP_STYLES:
        _, fig = run_map_plot(df, lat_col="lat", lon_col="lon",
                              color_col="sales", value_col="sales",
                              map_style=style)[0]
        t = fig.data[0]
        layers = list(getattr(fig.layout.mapbox, "layers", None) or ())
        src = layers[0].source[0] if layers else None
        p(f"style={style}: trace={t.type}, mapbox.style={fig.layout.mapbox.style}, "
          f"layer_tiles={src}")
    # offline fallback
    import modules.analysis.map_plot as mp
    mp._tiles_online_cache = False
    for style in MAP_STYLES:
        _, fig = mp.run_map_plot(df, lat_col="lat", lon_col="lon",
                                 color_col="sales", value_col="sales",
                                 map_style=style)[0]
        p(f"offline {style}: {fig.data[0].type}, land="
          f"{getattr(fig.layout.geo, 'landcolor', None)}")
    mp._tiles_online_cache = None
except Exception:
    traceback.print_exc(file=out)

open(r"g:\port-apps\coding\workspace\lytrize_desktop\_live_out.txt", "w").write(out.getvalue())
