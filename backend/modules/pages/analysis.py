"""modules/pages/analysis.py -- Analysis selection and chart generation page."""


import uuid, json
import streamlit as st
import streamlit.components.v1 as _comp
from modules.database import log_activity, save_draft, update_session_db, get_session_meta
from modules.utils.session_cache import make_json_safe
from modules.analysis import (
    ANALYSIS_OPTIONS, _NEEDS_AXES, _NO_FORM,
    render_config_panel, _collect_kwargs, _run,
    render_config_panel_scoped, _collect_kwargs_scoped,
    _WIDGET_SPEC, _collect_widget_state, _collect_widget_state_scoped,
)
from modules.analysis.descriptive import run_descriptive
from modules.analysis.data_quality import run_data_quality
from modules.charts import (
    charts_to_json,
    clean_insight_text,
    generate_chart_insights,
    apply_hover_format,
)
from modules.ui.css import inject_footer, render_logo
from modules.ui.chart_settings import (
    apply_chart_display_options,
    compute_meta_hash,
    render_chart_settings_controls,
)




def _shadow_notes_sync() -> None:
    """Copy all live desc_{uid} widget values into st.session_state._notes_shadow."""
    shadow = st.session_state.setdefault("_notes_shadow", {})
    for k, v in list(st.session_state.items()):
        if k.startswith("desc_") and k not in ("desc_add", "desc_close"):
            shadow[k[5:]] = v
    for uid, note in shadow.items():
        key = f"desc_{uid}"
        if note and key not in st.session_state:
            st.session_state[key] = note




def _sync_one_note(uid: str) -> None:
    """on_change callback for a single notes text_area."""
    val = st.session_state.get(f"desc_{uid}", "")
    shadow = st.session_state.setdefault("_notes_shadow", {})
    shadow[uid] = val
    st.session_state[f"desc_{uid}"] = val




def _autosave() -> None:
    """Persist chart/notes state to the database on each navigation or edit."""
    _shadow_notes_sync()
    _persist_draft()
    eid  = st.session_state.get("editing_session_id")
    uid  = st.session_state.get("user_id")
    name = st.session_state.get("editing_session_name", "Session")
    kpis_json = "[]"
    if eid and uid:
        try:
            if "kpis" in st.session_state:
                kpis_json = json.dumps(st.session_state["kpis"])
                st.session_state["_cached_kpis_json"] = kpis_json
            elif "_cached_kpis_json" in st.session_state:
                kpis_json = st.session_state["_cached_kpis_json"]
            else:
                try:
                    sm = get_session_meta(eid, uid)
                    kpis_json = sm.get("kpis_json", "[]") if sm else "[]"
                except Exception:
                    pass
                st.session_state["_cached_kpis_json"] = kpis_json


            update_session_db(
                eid, name,
                charts_to_json(st.session_state.get("charts", [])),
                st.session_state.get("selected_analyses", []),
                uid,
                dashboard_title    = st.session_state.get("dashboard_title", ""),
                kpis_json          = kpis_json,
                layout_mode        = st.session_state.get("layout_mode", "portrait"),
                grid_order_json    = json.dumps(st.session_state.get("grid_order", [])),
                grid_fullwidth_json= json.dumps(st.session_state.get("grid_fullwidth", {})),
            )
            try:
                st.toast("✅ Auto-saved", icon="✅")
            except Exception:
                pass
        except Exception:
            pass




def _restore_edit_notes() -> None:
    """Re-seed desc_{uid} keys for all charts in the current editing session."""
    if st.session_state.get("_analysis_notes_loaded"):
        shadow = st.session_state.get("_notes_shadow", {})
        for uid, note in shadow.items():
            key = f"desc_{uid}"
            if note and not st.session_state.get(key):
                st.session_state[key] = note
        return


    eid = st.session_state.get("editing_session_id")
    uid = st.session_state.get("user_id")
    if not eid or not uid:
        st.session_state["_analysis_notes_loaded"] = True
        return
    from modules.database import get_session_charts
    try:
        saved = get_session_charts(eid, uid)
        for chart_uid, _title, _fig, desc, _auto, _ctype, _meta in saved:
            note_key = f"desc_{chart_uid}"
            shadow_val = st.session_state.get("_notes_shadow", {}).get(chart_uid, "")
            restore_val = shadow_val or desc
            if restore_val and not st.session_state.get(note_key):
                st.session_state[note_key] = restore_val
                st.session_state.setdefault("_notes_shadow", {})[chart_uid] = restore_val
    except Exception:
        pass
    st.session_state["_analysis_notes_loaded"] = True




def _clear_regen_state() -> None:
    """Remove regeneration markers so they don't accidentally bleed across nav."""
    for _k in ("_regen_uid", "_regen_type", "_regen_restore"):
        st.session_state.pop(_k, None)


def _persist_draft(page="analysis"):
    uid = st.session_state.get("user_id")
    if not uid:
        return


    df = st.session_state.get("df")
    if df is not None:
        try:
            df_sig = (
                id(df),
                df.shape,
                tuple(df.columns),
                int(df.memory_usage(deep=True).sum()) if hasattr(df, "memory_usage") else 0,
            )
            if st.session_state.get("_df_snapshot_sig") != df_sig:
                from modules.utils.session_cache import save_df_snapshot
                save_df_snapshot(uid)
                st.session_state["_df_snapshot_sig"] = df_sig
        except Exception:
            pass


    charts = st.session_state.get("charts", [])
    chart_sig = tuple((uid_t, title, id(fig)) for uid_t, title, fig in charts)
    notes_sig = hash(str(st.session_state.get("_notes_shadow", {})))
    cache_key  = ("_charts_json_cache", chart_sig, notes_sig)
    cached_cj  = st.session_state.get("_charts_json_cache_val")
    cached_sig = st.session_state.get("_charts_json_cache_sig")
    if cached_sig == cache_key and cached_cj is not None:
        charts_json = cached_cj
    else:
        charts_json = charts_to_json(charts)
        st.session_state["_charts_json_cache_val"] = charts_json
        st.session_state["_charts_json_cache_sig"] = cache_key


    chart_meta_raw = {}
    for _k in list(st.session_state.keys()):
        if _k.startswith("chart_meta_"):
            chart_meta_raw[_k] = make_json_safe(st.session_state[_k])
    chart_meta_json = json.dumps(chart_meta_raw, ensure_ascii=False)


    save_draft(
        user_id              = uid,
        page                 = page,
        charts_json          = charts_json,
        file_name            = st.session_state.get("file_name", ""),
        editing_session_id   = st.session_state.get("editing_session_id"),
        editing_session_name = st.session_state.get("editing_session_name"),
        editing_file_name    = st.session_state.get("editing_file_name", ""),
        dashboard_title      = st.session_state.get("dashboard_title", ""),
        kpis_json            = json.dumps(st.session_state.get("kpis", [])),
        chart_meta_json      = chart_meta_json,
        layout_mode           = st.session_state.get("layout_mode", "portrait"),
        col_descriptions_json = json.dumps(
            st.session_state.get("col_descriptions", {})
        ),
    )




def _add_charts(new_charts, active):
    col_descs = st.session_state.get("col_descriptions", {})
    try:
        _gen_kwargs = _collect_kwargs(active, st.session_state.get("df"))
        _widget_state = _collect_widget_state(active)
    except Exception:
        _gen_kwargs = {}
        _widget_state = {}
    for uid, title, fig in new_charts:
        st.session_state[f"chart_type_{uid}"]    = active
        st.session_state[f"auto_insights_{uid}"] = generate_chart_insights(
            active, title, fig, col_descs)
        _edit_prefix = f"_edit_{uid}_{active}_"
        for _k in list(st.session_state.keys()):
            if _k.startswith(_edit_prefix):
                del st.session_state[_k]
        _cfg_prefix = f"_cfg_{active}_"
        for _k, _v in list(st.session_state.items()):
            if _k.startswith(_cfg_prefix):
                _suffix = _k[len(_cfg_prefix):]
                st.session_state[f"_edit_{uid}_{active}_{_suffix}"] = _v
        # Persist generation snapshot in chart_meta so chart options can be
        # restored later when the user clicks "Edit Chart".
        _set_chart_meta(
            uid,
            _generation_kwargs=_gen_kwargs,
            widget_state={k: _widget_state.get(k) for k in _widget_state},
        )
    st.session_state.charts.extend(new_charts)
    st.session_state._last_analysis_type = active
    if active not in st.session_state.selected_analyses:
        st.session_state.selected_analyses.append(active)
    log_activity(st.session_state.get("user_id", 0), "analysis_run",
                 f"type={active} charts_added={len(new_charts)}")
    _persist_draft()




def page_analysis():
    if "user_id" not in st.session_state:
        st.session_state.page = "profile"
        st.rerun()


    df         = st.session_state.get("df")
    is_editing = "editing_session_id" in st.session_state


    render_logo()


    if not st.session_state.get("_analysis_page_ready"):
        st.session_state["_analysis_page_ready"] = True
        with st.spinner("Loading analysis workspace…"):
            import time as _t; _t.sleep(0.05)


    if df is None and is_editing:
        _restore_edit_notes()
        sname  = st.session_state.get("editing_session_name", "Session")
        fname  = st.session_state.get("editing_file_name",    "the original file")
        charts = st.session_state.get("charts", [])


        if st.button("← Home"):
            _clear_regen_state()
            for k in ["editing_session_id","editing_session_name","editing_file_name"]:
                st.session_state.pop(k, None)
            st.session_state.page = "home"; st.rerun()


        st.markdown(f"## ✏️ Editing: **{sname}**")
        st.info(
            f"📂 **Re-upload needed to run new analyses.** "
            f"Upload **{fname}** to add more charts, or go to Dashboard to save what you have.")


        c1, c2 = st.columns(2)
        with c1:
            if st.button("📂 Upload Dataset to Add Charts", use_container_width=True):
                _clear_regen_state()
                _autosave()
                st.session_state.pop("_analysis_notes_loaded", None)
                st.session_state.page = "upload"; st.rerun()
        with c2:
            if st.button("📊 Go to Dashboard →", use_container_width=True):
                _clear_regen_state()
                _autosave()
                st.session_state.page = "dashboard"; st.rerun()


        _render_chart_list(charts, edit_mode=True)
        inject_footer()
        return


    if df is None:
        st.session_state.page = "upload"; st.rerun()


    if "charts"            not in st.session_state: st.session_state.charts            = []
    if "selected_analyses" not in st.session_state: st.session_state.selected_analyses = []


    _nav_c1, _nav_c2, _nav_spacer = st.columns([1, 1, 6])
    with _nav_c1:
        if st.button("← Home", use_container_width=True):
            _clear_regen_state()
            st.session_state.pop("_analysis_page_ready", None)
            st.session_state.page = "home"; st.rerun()
    with _nav_c2:
        if st.button("📂 Upload", use_container_width=True,
                     help="Go back to Upload & Transformation to re-upload or clean data"):
            _clear_regen_state()
            _shadow_notes_sync()
            st.session_state.pop("_analysis_notes_loaded", None)
            st.session_state.pop("_analysis_page_ready", None)
            st.session_state.page = "upload"; st.rerun()


    if is_editing:
        _restore_edit_notes()
        sname = st.session_state.get("editing_session_name", "Session")
        st.info(f"✏️ Edit mode -- adding charts to **{sname}**. "
                f"Click **Proceed to Dashboard** when done.")


    regen_uid  = st.session_state.get("_regen_uid")
    regen_type = st.session_state.get("_regen_type", "")
    if regen_uid and regen_type and df is not None:
        chart_entry = next(
            (c for c in st.session_state.get("charts", []) if c[0] == regen_uid), None)
        if chart_entry:
            regen_title = chart_entry[1]
            type_label  = next(
                (o["name"] for o in ANALYSIS_OPTIONS if o["id"] == regen_type),
                regen_type)
            st.markdown(f"### 🔄 Regenerate Chart — *{regen_title}* ({type_label})")
            st.caption("Adjust options below then click **Apply Changes** to replace the chart.")


            # Restore original chart options into _edit_ keys so the scoped
            # panel shows the chart's saved selections instead of hardcoded defaults.
            _edit_prefix = f"_edit_{regen_uid}_{regen_type}_"
            _restore_flag = st.session_state.get("_regen_restore", False)
            if _restore_flag:
                meta = _chart_meta(regen_uid)
                ws = meta.get("widget_state", {})
                if not ws:
                    # Backward-compat fallback: rebuild a snapshots dict from
                    # persisted generation kwargs on old charts that predate
                    # widget_state.
                    ws = {}
                    gen_kwargs = meta.get("_generation_kwargs", {})
                    if isinstance(gen_kwargs, dict) and gen_kwargs:
                        _compat_map = {
                            "statistical":    [("x", "x_cols"), ("y", "y_cols"), ("palette", "palette")],
                            "distribution":   [("x", "x_cols"), ("color", "y_cols"), ("palette", "palette")],
                            "correlation":    [("x", "x_cols"), ("y", "y_cols"), ("palette", "palette")],
                            "categorical":    [("x","x_cols"), ("y","y_cols"), ("agg","agg"), ("sort","sort_by"), ("top_n","top_n"), ("direction","direction"), ("dual_y","dual_y_col"), ("dual_y_agg","dual_y_agg"), ("palette","palette")],
                            "pie_chart":      [("x","x_cols"), ("y","y_cols"), ("agg","agg"), ("sort","sort_by"), ("top_n","top_n"), ("palette","palette")],
                            "time_series":    [("x","x_cols"), ("y","y_cols"), ("date_part","date_part"), ("agg","agg"), ("dual_y_ts","dual_y_col"), ("dual_y_agg","dual_y_agg"), ("palette","palette")],
                            "scatter_plot":   [("x_col","x_col"), ("y_col","y_col"), ("color_col","color_col"), ("size_col","size_col"), ("trendline","trendline"), ("palette","palette")],
                            "matrix_table":   [("index_col","index_col"), ("columns_col","columns_col"), ("values_col","values_col"), ("agg","agg"), ("view_type","view_type"), ("sort_rows","sort_rows"), ("top_n_rows","top_n_rows")],
                            "map_plot":       [("map_mode","map_mode"), ("lat_col","lat_col"), ("lon_col","lon_col"), ("location_col","location_col"), ("color_col","color_col"), ("value_col","value_col"), ("agg_func","agg_func"), ("map_style","map_style"), ("marker_opacity","marker_opacity"), ("invert_colorscale","invert_colorscale"), ("show_borders","show_borders"), ("geo_col","geo_col"), ("choropleth_colorscale","choropleth_colorscale"), ("choropleth_projection","choropleth_projection"), ("choropleth_scope","choropleth_scope"), ("choropleth_show_borders","choropleth_show_borders")],
                        }
                        for widget_key, gen_key in _compat_map.get(regen_type, []):
                            if gen_key in gen_kwargs:
                                _v = gen_kwargs[gen_key]
                                if _v is not None and _v != "None":
                                    ws[widget_key] = _v
                # Always refresh from saved chart options when explicitly
                # entering regenerate mode, then wipe the flag so a later
                # cancel + re-edit still re-restores from saved chart options.
                for key, _kwarg, kind in _WIDGET_SPEC.get(regen_type, []):
                    if key in ws and ws[key] is not None:
                        st.session_state[f"_edit_{regen_uid}_{regen_type}_{key}"] = ws[key]
                st.session_state.pop("_regen_restore", None)
            render_config_panel_scoped(regen_uid, regen_type, df)


            ra, rb, _ = st.columns([1, 1, 5])
            with ra:
                if st.button("✅ Apply Changes", key="regen_apply", type="primary",
                             use_container_width=True):
                    kwargs = _collect_kwargs_scoped(regen_uid, regen_type, df)
                    new_charts = _run(regen_type, df, **kwargs)
                    if new_charts:
                        # Invalidate the display-figure cache so the fragment
                        # rebuilds with the newly-generated figure instead of
                        # returning the stale cached display version.
                        for _ck in (f"_display_fig_{regen_uid}", f"_display_fig_hash_{regen_uid}",
                                    f"_display_fig_font_{regen_uid}", f"_display_fig_fonthash_{regen_uid}"):
                            st.session_state.pop(_ck, None)


                        new_fig   = new_charts[0][2]
                        new_title = new_charts[0][1]
                        st.session_state.charts = [
                            (c[0], new_title if c[0] == regen_uid else c[1],
                             new_fig  if c[0] == regen_uid else c[2])
                            for c in st.session_state.get("charts", [])
                        ]
                        st.session_state.pop(f"auto_insights_{regen_uid}", None)
                        st.session_state[f"chart_type_{regen_uid}"] = regen_type
                        # Persist the latest scoped widget state so the next
                        # edit opens with these exact selections.
                        try:
                            _new_ws = _collect_widget_state_scoped(regen_uid, regen_type)
                            _widget_spec_keys = [key for key, _kwarg, _kind in _WIDGET_SPEC.get(regen_type, [])]
                            _set_chart_meta(
                                regen_uid,
                                _generation_kwargs=_collect_kwargs_scoped(
                                    regen_uid, regen_type, st.session_state.get("df")
                                ),
                                widget_state={
                                    k: _new_ws.get(k)
                                    for k in _widget_spec_keys
                                },
                            )
                        except Exception:
                            pass
                    st.session_state.pop("_regen_uid",  None)
                    st.session_state.pop("_regen_type", None)
                    _autosave()
                    st.rerun()
            with rb:
                if st.button("✕ Cancel", key="regen_cancel", use_container_width=True):
                    st.session_state.pop("_regen_uid",  None)
                    st.session_state.pop("_regen_type", None)
                    _shadow_notes_sync()
                    st.rerun()


            st.markdown("---")


    _fname   = st.session_state.get("file_name", "dataset")
    _n_rows  = len(df)
    _n_cols  = len(df.columns)


    with st.expander(
        f"📋 Data Preview — {_fname}  ({_n_rows:,} rows × {_n_cols} columns)",
        expanded=st.session_state.get("_preview_expanded", True),
    ):
        _pb1, _pb2, _pb3, _pb4 = st.columns([1, 1, 1, 4])
        with _pb1:
            if st.button("⬆ Top 10",    key="prev_top",    use_container_width=True):
                st.session_state["_analysis_preview_mode"] = "top"
        with _pb2:
            if st.button("⬇ Bottom 10", key="prev_bot",    use_container_width=True):
                st.session_state["_analysis_preview_mode"] = "bottom"
        with _pb3:
            if st.button("🎲 Random",   key="prev_rand",   use_container_width=True):
                st.session_state["_analysis_preview_mode"] = "random"
                st.session_state["_analysis_random_seed"] = (
                    st.session_state.get("_analysis_random_seed", 0) + 1
                )
        with _pb4:
            st.caption(
                f"Showing a sample of your loaded dataset. "
                f"Columns: **{', '.join(str(c) for c in df.columns[:8])}"
                f"{'…' if _n_cols > 8 else ''}**"
            )


        _mode = st.session_state.get("_analysis_preview_mode", "top")
        try:
            if _mode == "bottom":
                _prev_df = df.tail(10)
                _label   = "Bottom 10 rows"
            elif _mode == "random":
                _prev_df = df.sample(min(10, _n_rows), random_state=None)
                _label   = "10 random rows"
            else:
                _prev_df = df.head(10)
                _label   = "Top 10 rows"
        except Exception:
            _prev_df = df.head(10)
            _label   = "Top 10 rows"


        st.caption(f"*{_label}*")
        st.dataframe(
            _prev_df,
            use_container_width=True,
            height=min(380, 38 + len(_prev_df) * 35),
        )


        _num_count = len(df.select_dtypes("number").columns)
        _cat_count = len(df.select_dtypes("object").columns)
        _dt_count  = len(df.select_dtypes("datetime").columns)
        _null_pct  = round(df.isnull().sum().sum() / max(df.size, 1) * 100, 1)
        st.caption(
            f"🔢 {_num_count} numeric  ·  🔤 {_cat_count} text  ·  "
            f"📅 {_dt_count} datetime  ·  ⚠️ {_null_pct}% missing values"
        )


    st.markdown("## 🔬 Select Analysis Type")


    active = st.session_state.get("_active_analysis")


    cols   = st.columns([1,1,1,1,1], gap="small")
    for i, opt in enumerate(ANALYSIS_OPTIONS):
        with cols[i % 5]:
            selected = opt["id"] == active
            st.markdown(
                f'<div class="ag-card" style="{"border-color:#6163df;box-shadow:0 0 0 3px rgba(97,99,223,0.18);" if selected else ""}">'
                f'<div class="ag-icon">{opt["icon"]}</div>'
                f'<div class="ag-name">{opt["name"]}</div>'
                f'<div class="ag-desc">{opt["desc"]}</div></div>',
                unsafe_allow_html=True)
            if st.button("▶ Select", key=f"btn_{opt['id']}"):
                if st.session_state.get("_active_analysis") == opt["id"]:
                    st.session_state["_active_analysis"] = None
                else:
                    st.session_state["_active_analysis"] = opt["id"]
                _shadow_notes_sync()
                st.rerun()


    if active:
        analysis_name = next(o["name"] for o in ANALYSIS_OPTIONS if o["id"] == active)
        st.markdown("---")
        _comp.html("""<script>
        setTimeout(function(){
            var els = window.parent.document.querySelectorAll('h3');
            for(var el of els){
                if(el.textContent && el.textContent.includes('Configure')){
                    el.scrollIntoView({behavior:'smooth',block:'start'});
                    break;
                }
            }
        }, 150);
        </script>""", height=0)


        if active == "descriptive":
            st.markdown("### 🗂️ Descriptive Statistics")
            run_descriptive(df)
            if st.button("✕ Close", key="desc_close"):
                st.session_state["_active_analysis"] = None
                _shadow_notes_sync()
                st.rerun()


        else:
            st.markdown(f"### ⚙️ Configure -- {analysis_name}")
            st.caption("Adjust options below. All selections are live -- no submit needed until Generate.")


            render_config_panel(active, df)


            st.write("")
            g1, g2, _ = st.columns([1, 1, 5])
            with g1:
                generate_clicked = st.button(
                    "▶ Generate Charts", key=f"gen_{active}",
                    type="primary", use_container_width=True)
            with g2:
                close_clicked = st.button(
                    "✕ Close", key=f"close_{active}",
                    use_container_width=True)


            if close_clicked:
                st.session_state["_active_analysis"] = None
                _shadow_notes_sync()
                st.rerun()


            if generate_clicked:
                kwargs = _collect_kwargs(active, df)
                new_charts = _run(active, df, **kwargs)
                if new_charts is not None:
                    if new_charts:
                        _add_charts(new_charts, active)
                    st.session_state["_active_analysis"] = None
                    _autosave()
                    st.rerun()


    if st.session_state.charts:
        st.markdown("---")
        h1, h2 = st.columns([5, 1])
        with h1:
            st.markdown(f"## 📈 Generated Charts ({len(st.session_state.charts)})")
        with h2:
            if st.button("🗑️ Clear All", key="clear_all_charts"):
                log_activity(st.session_state.get("user_id",0),"charts_cleared_all",
                             f"count={len(st.session_state.charts)}")
                st.session_state.charts = []
                st.session_state.selected_analyses = []
                st.session_state.pop("_notes_shadow", None)
                _autosave()
                st.rerun()


        _render_chart_list(st.session_state.charts, edit_mode=is_editing)


        st.write("")
        if st.button("🎯 Proceed to Dashboard →", type="primary"):
            _clear_regen_state()
            log_activity(st.session_state.get("user_id",0),"proceed_to_dashboard",
                         f"charts={len(st.session_state.charts)}")
            with st.spinner("Saving your work and preparing the dashboard…"):
                _autosave()
            st.session_state.page = "dashboard"; st.rerun()


    inject_footer()




def _chart_meta(uid) -> dict:
    """Read chart meta from session_state (same structure as dashboard._meta)."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    return st.session_state[k]




def _set_chart_meta(uid, **kw) -> None:
    """Write chart meta to session_state."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    st.session_state[k].update(kw)




def _render_chart_list(charts, edit_mode=False):
    """Render chart cards with full settings, insights, and notes in edit mode.

    Each card is wrapped in its own @st.fragment so interactions on one chart
    do NOT rerun the rest of the page.  See modules/ui/chart_card.py.
    """
    from modules.ui.chart_card import render_chart_card

    for uid, title, fig in charts:
        meta = _chart_meta(uid)

        # Resolve chart type; the fragment handles everything else
        chart_type = st.session_state.get(f"chart_type_{uid}", "")

        # ------------------------------------------------------------------ #
        # Hand off to the isolated fragment -- everything inside runs in its
        # own rerun scope, so other charts stay frozen when this one changes.
        # ------------------------------------------------------------------ #
        render_chart_card(
            uid, title, fig, chart_type, meta,
            auto_insights=st.session_state.get(f"auto_insights_{uid}", []),
            key_prefix="analysis",
            edit_mode=edit_mode,
            viewing_saved=False,
            on_meta_changed=lambda u, k, v: _set_chart_meta(u, **{k: v}) if k != "__delete__" else None,
        )

        # Actual list deletion is handled here on the next full run; a fragment
        # cannot mutate the list it is iterating over.
        if st.session_state.get(f"_delete_requested_{uid}"):
            st.session_state.charts = [
                c for c in st.session_state.get("charts", []) if c[0] != uid
            ]
            st.session_state.pop(f"_delete_requested_{uid}", None)
            st.session_state.pop(f"_regen_uid", None)
            st.session_state.get("_notes_shadow", {}).pop(uid, None)
            log_activity(st.session_state.get("user_id", 0), "chart_deleted",
                         f"title='{title}' (fragment)")
            _autosave()
            st.rerun()

        st.markdown("---")
