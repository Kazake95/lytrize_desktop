"""modules/pages/analysis.py -- Analysis selection and chart generation page."""


import uuid, json
import streamlit as st
import streamlit.components.v1 as _comp
from modules.database import log_activity, save_draft, update_session_db, get_session_meta
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




def _persist_draft(page="analysis"):
    uid = st.session_state.get("user_id")
    if not uid:
        return


    df = st.session_state.get("df")
    if df is not None:
        try:
            df_sig = (id(df), df.shape, tuple(df.columns), hash(tuple(df.columns.tolist())))
            if st.session_state.get("_df_snapshot_sig") != df_sig:
                from modules.utils.session_cache import save_df_snapshot
                save_df_snapshot(uid)
                st.session_state["_df_snapshot_sig"] = df_sig
        except Exception:
            pass


    charts = st.session_state.get("charts", [])
    chart_sig = tuple(uid_t for uid_t, _, _ in charts)
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
            _v = st.session_state[_k]
            if isinstance(_v, dict):
                _safe_v = {}
                for _mk, _mv in _v.items():
                    try:
                        json.dumps(_mv, ensure_ascii=False)
                        _safe_v[_mk] = _mv
                    except (TypeError, ValueError, OverflowError):
                        _safe_v[_mk] = str(_mv)
                chart_meta_raw[_k] = _safe_v
            elif isinstance(_v, (str, int, float, bool, list, tuple)):
                try:
                    json.dumps(_v, ensure_ascii=False)
                    chart_meta_raw[_k] = _v
                except (TypeError, ValueError, OverflowError):
                    chart_meta_raw[_k] = str(_v)
            else:
                chart_meta_raw[_k] = str(_v)
    chart_meta_json = json.dumps(chart_meta_raw, ensure_ascii=False)


    save_draft(
        user_id              = uid,
        page                 = page,
        charts_json          = charts_json,
        file_name            = st.session_state.get("file_name", ""),
        editing_session_id   = st.session_state.get("editing_session_id"),
        editing_session_name = st.session_state.get("editing_session_name"),
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
                _autosave()
                st.session_state.pop("_analysis_notes_loaded", None)
                st.session_state.page = "upload"; st.rerun()
        with c2:
            if st.button("📊 Go to Dashboard →", use_container_width=True):
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
            st.session_state.pop("_analysis_page_ready", None)
            st.session_state.page = "home"; st.rerun()
    with _nav_c2:
        if st.button("📂 Upload", use_container_width=True,
                     help="Go back to Upload & Transformation to re-upload or clean data"):
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
                        st.session_state.pop(f"_fig_cache_{regen_uid}", None)
                        st.session_state.pop(f"_fig_cache_meta_{regen_uid}", None)


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
                            _set_chart_meta(
                                regen_uid,
                                _generation_kwargs=_collect_kwargs_scoped(
                                    regen_uid, regen_type, st.session_state.get("df")
                                ),
                                widget_state={
                                    k: _new_ws.get(k)
                                    for k in _WIDGET_SPEC.get(regen_type, {})
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
    """Render chart cards with full settings, insights, and notes in edit mode."""
    col_descs = st.session_state.get("col_descriptions", {})
    for uid, title, fig in charts:
        meta = _chart_meta(uid)


        _ctype_apply   = st.session_state.get(f"chart_type_{uid}", "")
        _meta_view     = meta.get("_matrix_view", "")
        if not _meta_view:
            _lytrize_l = getattr(fig, "_lytrize_meta", {}) or {}
            _meta_view = _lytrize_l.get("matrix_view", "")
            if _meta_view:
                _set_chart_meta(uid, _matrix_view=_meta_view)
                meta = st.session_state.get(f"chart_meta_{uid}", {})


        display_title = meta.get("custom_title") or title
        df_available  = st.session_state.get("df") is not None
        _ts          = meta.get("text_style") or {}
        

        _hdr_size   = int(st.session_state.get(f"analysis_hsize_{uid}", _ts.get("header_size", 28)))
        _hdr_color  = str(st.session_state.get(f"analysis_hcolor_{uid}", _ts.get("header_color", "#6163df")))
        _hdr_family = str(st.session_state.get(f"analysis_hfont_{uid}", _ts.get("header_family", "Inter, system-ui, sans-serif")))
        _hdr_style  = str(st.session_state.get(f"analysis_hfont_style_{uid}", _ts.get("header_font_style", "Normal"))).lower()


        _sub_size   = int(st.session_state.get(f"analysis_ssize_{uid}", _ts.get("subtitle_size", 11)))
        _sub_color  = str(st.session_state.get(f"analysis_scolor_{uid}", _ts.get("subtitle_color", "#64748b")))
        _sub_family = str(st.session_state.get(f"analysis_subfont_{uid}", _ts.get("subtitle_family", "Inter, system-ui, sans-serif")))
        _sub_style  = str(st.session_state.get(f"analysis_subfont_style_{uid}", _ts.get("subtitle_font_style", "Normal"))).lower()


        _hdr_weight = "700" if "bold" in _hdr_style or _hdr_style == "normal" else "normal"
        _hdr_italic = "italic" if "italic" in _hdr_style else "normal"
        _hdr_decor  = "underline" if "underline" in _hdr_style else "none"


        _sub_weight = "bold" if "bold" in _sub_style else "normal"
        _sub_italic = "italic" if "italic" in _sub_style else "normal"
        _sub_decor  = "underline" if "underline" in _sub_style else "none"


        ctrl = st.columns([9, 2, 1])
        with ctrl[0]:
            st.markdown(
                f'<div style="font-size:{_hdr_size}px; font-family:\'{_hdr_family}\'; '
                f'font-weight:{_hdr_weight}; font-style:{_hdr_italic}; text-decoration:{_hdr_decor}; '
                f'color:{_hdr_color}; margin-bottom:0.2rem;">'
                f'{display_title}</div>',
                unsafe_allow_html=True)
            if meta.get("subtitle"):
                st.markdown(
                    f'<div style="font-size:{_sub_size}px; font-family:\'{_sub_family}\'; '
                    f'font-weight:{_sub_weight}; font-style:{_sub_italic}; text-decoration:{_sub_decor}; '
                    f'color:{_sub_color}; margin-top:-4px; margin-bottom:4px;">'
                    f'{meta["subtitle"]}</div>',
                    unsafe_allow_html=True)
        with ctrl[1]:
            chart_type = st.session_state.get(f"chart_type_{uid}", "")
            if chart_type and chart_type not in ("descriptive", "data_quality"):
                if df_available:
                    if st.button("🔄 Edit Chart", key=f"regen_btn_{uid}",
                                 use_container_width=True,
                                 help="Re-run this chart with new columns / settings"):
                        st.session_state._regen_uid  = uid
                        st.session_state._regen_type = chart_type
                        st.session_state["_regen_restore"] = True
                        _shadow_notes_sync()
                        st.rerun()
                else:
                    st.button("🔄 Edit Chart", key=f"regen_btn_{uid}",
                              use_container_width=True, disabled=True,
                              help="Upload the original dataset first to regenerate this chart")
        with ctrl[2]:
            if st.button("✕", key=f"del_{uid}", help="Remove this chart"):
                log_activity(st.session_state.get("user_id",0),"chart_deleted",f"title='{title}'")
                st.session_state.charts = [c for c in st.session_state.charts if c[0] != uid]
                st.session_state.pop("_regen_uid", None)
                st.session_state.get("_notes_shadow", {}).pop(uid, None)
                _autosave()
                st.rerun()


        _cache_key       = f"_fig_cache_{uid}"
        _cache_meta_key  = f"_fig_cache_meta_{uid}"
        _cached_fig      = st.session_state.get(_cache_key)
        _cached_hash = st.session_state.get(_cache_meta_key, "")


        chart_type    = st.session_state.get(f"chart_type_{uid}", "")
        auto_insights = st.session_state.get(f"auto_insights_{uid}")
        if auto_insights is None:
            auto_insights = generate_chart_insights(chart_type, title, fig, col_descs)
            st.session_state[f"auto_insights_{uid}"] = auto_insights


        _settings_col, _chart_col = st.columns([1, 2])
        with _settings_col:
            st.caption(
                "✨ **Live Preview** — changes appear instantly on the chart →",
                unsafe_allow_html=False,
            )
            _stype_for_settings = chart_type
            if chart_type == "matrix_table" and _meta_view == "heatmap":
                _stype_for_settings = "matrix_heatmap"
            with st.expander("⚙️ Chart Settings", expanded=False):
                updates = render_chart_settings_controls(
                    uid, title, fig, _stype_for_settings, meta, auto_insights,
                    key_prefix="analysis",
                    show_text_style=False,
                )
                _set_chart_meta(uid, **updates)
                if updates.get("custom_title"):
                    st.session_state.charts = [
                        (c[0], updates["custom_title"] if c[0] == uid else c[1], c[2])
                        for c in st.session_state.get("charts", [])
                    ]


            from modules.ui.chart_settings import render_typography_controls
            with st.expander("🎨 Typography", expanded=False):
                text_style = render_typography_controls(
                    uid, fig, _stype_for_settings, meta,
                    key_prefix="analysis",
                )
                _set_chart_meta(uid, text_style=text_style)


        meta       = _chart_meta(uid)
        _post_hash = compute_meta_hash(meta)


        _need_rebuild = (_cached_fig is None or _cached_hash != _post_hash)


        with _chart_col:
            _chart_type_for_opts = _ctype_apply
            if _ctype_apply == "matrix_table" and _meta_view == "heatmap":
                _chart_type_for_opts = "matrix_heatmap"


            if _need_rebuild:
                import copy as _acopy
                fig_show = _acopy.deepcopy(fig)


                xl = meta.get("x_label", "")
                yl = meta.get("y_label", "")
                if _ctype_apply == "matrix_table":
                    for _tr in fig_show.data:
                        if not (hasattr(_tr, "header") and hasattr(_tr, "cells")):
                            continue
                        _hdr_vals = list(_tr.header.values) if _tr.header.values else []
                        _is_footer = all(str(v).strip() in ("", "[]", "None") for v in _hdr_vals) and _hdr_vals
                        if _is_footer:
                            continue
                        if xl and _hdr_vals:
                            _hdr_vals[0] = f"<b>{xl}</b>"
                            _tr.header.values = _hdr_vals
                        break
                elif _chart_type_for_opts == "matrix_heatmap":
                    pass
                else:
                    if xl: fig_show.update_xaxes(title_text=xl)
                    if yl: fig_show.update_yaxes(title_text=yl)


                # In edit/preview mode, the chart title is already shown
                # as an HTML header in the left column. Suppress the
                # Plotly-embedded title to avoid duplicates.
                fig_show.update_layout(title_text="")


                stored_legend    = meta.get("legend_names", {})
                stored_trace_idx = meta.get("trace_names", {})
                for _ti, _trace in enumerate(fig_show.data):
                    _orig = getattr(_trace, "name", None)
                    if _orig is None:
                        continue
                    renamed = stored_legend.get(str(_orig)) or stored_trace_idx.get(str(_ti))
                    if renamed:
                        _trace.name = renamed


                _leg_title = meta.get("legend_title", "")
                if _leg_title:
                    fig_show.update_layout(legend_title_text=_leg_title)


                fig_show = apply_chart_display_options(fig_show, meta, _chart_type_for_opts, _inplace=True)


                st.session_state[_cache_key]     = fig_show
                st.session_state[_cache_meta_key] = _post_hash
            else:
                fig_show = _cached_fig


            is_horiz = any(getattr(t, "orientation", "v") == "h"
                           for t in fig_show.data if hasattr(t, "orientation"))
            _skip_axis_post = (_ctype_apply == "matrix_table" and _meta_view != "heatmap")
            if not _skip_axis_post:
                if is_horiz:
                    fig_show.update_yaxes(automargin=True)
                    fig_show.update_layout(margin=dict(l=120, r=20, t=28, b=20))
                else:
                    fig_show.update_xaxes(tickangle=-35, automargin=True)
                    fig_show.update_yaxes(automargin=True)
                    fig_show.update_layout(margin=dict(l=20, r=20, t=28, b=80))


            apply_hover_format(fig_show)


            _chart_type_now = st.session_state.get(f"chart_type_{uid}", "")
            _is_table = _chart_type_now == "matrix_table" and _meta_view != "heatmap"
            if _is_table:
                st.markdown(
                    '<div style="max-height:540px;overflow-y:auto;overflow-x:hidden;'
                    'border:1px solid rgba(100,116,139,0.2);border-radius:6px;'
                    'padding-bottom:4px;">',
                    unsafe_allow_html=True,
                )
            st.plotly_chart(
                fig_show,
                use_container_width=True,
                key=f"plotly_{uid}",
                config={
                    "responsive": True,
                    "displayModeBar": "hover",
                    "mathjax": False,
                },
            )
            if _is_table:
                st.markdown("</div>", unsafe_allow_html=True)


        st.markdown("---")
        if auto_insights:
            with st.expander("💡 Auto-Insights", expanded=False):
                for ins in auto_insights:
                    st.markdown(f"- {clean_insight_text(ins)}")


        if f"desc_{uid}" not in st.session_state:
            st.session_state[f"desc_{uid}"] = (
                st.session_state.get("_notes_shadow", {}).get(uid, ""))
        st.text_area(
            "✍️ Analysis Notes (auto-saved to Dashboard)",
            key=f"desc_{uid}",
            on_change=_sync_one_note,
            args=(uid,),
            placeholder="Add your findings or observations here…")


        st.markdown("---")
