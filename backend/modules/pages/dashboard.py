"""modules/pages/dashboard.py -- Dashboard view, editing, saving, and PDF export."""
import json, copy, datetime
import pandas as pd
import streamlit as st
import streamlit.components.v1 as _comp  # used for live preview iframe
from html import escape
import re


from modules.database import (
    log_activity,
    save_session_db, update_session_db,
    get_session_charts, get_session_meta,
    clear_draft, save_draft,
)
from modules.charts import charts_to_json, clean_insight_text, _fmt_num, apply_hover_format
from modules.export import generate_html_report
from modules.ui.css import inject_footer, render_logo
from modules.ui.chart_settings import (
    apply_chart_display_options,
    compute_meta_hash,
    default_text_style as _shared_default_text_style,
    merge_text_style as _shared_merge_text_style,
    render_chart_settings_controls,
)
from modules.ui.font_manager import inject_font_preview_css, font_select, get_font_stack


def _render_section_preview(label: str, font: str, style: str, size: int, color: str) -> None:
    """Render a single-line styled preview for a dashboard text section."""
    font_stack = get_font_stack(font)
    styles = [
        f"font-family:{font_stack}",
        f"font-size:{size}px",
        f"color:{color}",
    ]
    if "Bold" in style:
        styles.append("font-weight:bold")
    if "Italic" in style:
        styles.append("font-style:italic")
    if "Underline" in style:
        styles.append("text-decoration:underline")
    st.markdown(
        f'<div style="{";".join(styles)};padding:0.4rem 0.8rem;'
        f'background:var(--secondary-background-color,#1a1f3a);'
        f'border-radius:6px;border:1px solid var(--border-color,#2c3564);'
        f'line-height:1.5;">{label}</div>',
        unsafe_allow_html=True,
    )




def _dash_sync_notes() -> None:
    """Snapshot all live desc_{uid} note values into _notes_shadow."""
    shadow = st.session_state.setdefault("_notes_shadow", {})
    for k, v in list(st.session_state.items()):
        if k.startswith("desc_") and isinstance(v, str):
            shadow[k[5:]] = v
def _persist():
    """Persist the current dashboard draft to the database."""
    uid = st.session_state.get("user_id")
    if not uid:
        return
    _chart_meta_raw = {}
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
                _chart_meta_raw[_k] = _safe_v
            elif isinstance(_v, (str, int, float, bool, list, tuple)):
                try:
                    json.dumps(_v, ensure_ascii=False)
                    _chart_meta_raw[_k] = _v
                except (TypeError, ValueError, OverflowError):
                    _chart_meta_raw[_k] = str(_v)
            else:
                _chart_meta_raw[_k] = str(_v)
    chart_meta_json = json.dumps(_chart_meta_raw, ensure_ascii=False)


    save_draft(
        user_id              = uid,
        page                 = "dashboard",
        charts_json          = charts_to_json(st.session_state.get("charts", [])),
        file_name            = st.session_state.get("file_name", ""),
        editing_session_id   = st.session_state.get("editing_session_id"),
        editing_session_name = st.session_state.get("editing_session_name"),
        editing_file_name    = st.session_state.get("editing_file_name", ""),
        dashboard_title      = st.session_state.get("dashboard_title", ""),
        kpis_json            = json.dumps(st.session_state.get("kpis", [])),
        chart_meta_json      = chart_meta_json,
        layout_mode          = st.session_state.get("layout_mode", "portrait"),
    )




def _meta(uid):
    """Return the chart metadata dict for a given chart uid."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    return st.session_state[k]




def _set_meta(uid, **kw):
    """Update chart metadata for a given chart uid."""
    k = f"chart_meta_{uid}"
    if k not in st.session_state:
        st.session_state[k] = {}
    st.session_state[k].update(kw)




def _default_text_style() -> dict:
    """Return the default typography settings used by chart cards."""
    return _shared_default_text_style()




def _merge_text_style(raw: dict | None) -> dict:
    """Merge a stored text-style dict over the defaults."""
    return _shared_merge_text_style(raw)




def _apply_axes(fig, x_lbl, y_lbl, text_style: dict | None = None, *, _inplace: bool = False):
    try:
        f2 = fig if _inplace else copy.deepcopy(fig)
        style = _merge_text_style(text_style)
        axis_title_font = dict(
            size=int(style["axis_title_size"]),
            color=str(style["axis_title_color"]),
            family=str(style["family"]),
        )
        axis_tick_font = dict(
            size=int(style["axis_tick_size"]),
            color=str(style["axis_tick_color"]),
            family=str(style["family"]),
        )
        if x_lbl:
            f2.update_xaxes(title_text=x_lbl, title_font=axis_title_font)
        else:
            f2.update_xaxes(title_font=axis_title_font)
        if y_lbl:
            f2.update_yaxes(title_text=y_lbl, title_font=axis_title_font)
        else:
            f2.update_yaxes(title_font=axis_title_font)
        f2.update_xaxes(tickfont=axis_tick_font)
        f2.update_yaxes(tickfont=axis_tick_font)
        return f2
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning("_apply_axes: %s", e)
        return fig




def _apply_legend_names(fig, legend_names: dict, legend_title: str = "", text_style: dict | None = None, *, _inplace: bool = False):
    """Rename Plotly traces using the {original_name: custom_name} mapping stored"""
    try:
        f2 = fig if _inplace else copy.deepcopy(fig)
        style = _merge_text_style(text_style)
        legend_font = dict(
            size=int(style["legend_item_size"]),
            color=str(style["legend_item_color"]),
            family=str(style["family"]),
        )
        legend_title_font = dict(
            size=int(style["legend_title_size"]),
            color=str(style["legend_title_color"]),
            family=str(style["family"]),
        )
        if legend_names:
            for trace in f2.data:
                original = getattr(trace, "name", None)
                if original is not None and str(original) in legend_names:
                    custom = legend_names[str(original)]
                    if custom:
                        trace.name = custom
        if legend_title:
            f2.update_layout(
                legend_title_text=legend_title,
                legend=dict(font=legend_font, title=dict(font=legend_title_font)),
            )
        elif legend_title == "":
            f2.update_layout(legend=dict(font=legend_font, title=dict(font=legend_title_font)))
        return f2
    except Exception as e:
        import logging as _logging
        _logging.getLogger(__name__).warning("_apply_legend_names: %s", e)
        return fig




def _all_charts(viewing_saved):
    """Return the current chart list, enriched with metadata for the dashboard."""
    if viewing_saved:
        return st.session_state.get("_view_charts", [])
    out = []
    for uid, title, fig in st.session_state.get("charts", []):
        desc   = st.session_state.get(f"desc_{uid}", "")
        autos  = st.session_state.get(f"auto_insights_{uid}", [])
        ctype  = st.session_state.get(f"chart_type_{uid}", "")
        meta   = _meta(uid)
        out.append((uid, title, fig, desc, autos, ctype, meta))
    return out




_KPI_TYPES = [
    "Total (Sum)", "Average (Mean)", "Median", "Count (Rows)",
    "Minimum Value", "Maximum Value",
    "% of Total (category share)", "Unique Values Count",
    "Date Range", "Top Category → Value", "Bottom Category → Value",
    "% Change (Latest Month vs Prev Month)", "% Change (Latest Year vs Prev Year)",
]
_KPI_ICONS = {
    "Total (Sum)":"📜","Average (Mean)":"📊","Median":"📐","Count (Rows)":"🔢",
    "Minimum Value":"⬇️","Maximum Value":"⬆️",
    "% of Total (category share)":"📈","Unique Values Count":"🔍",
    "Date Range":"📅","Top Category → Value":"🏆","Bottom Category → Value":"📉",
    "% Change (Latest Month vs Prev Month)":"📅","% Change (Latest Year vs Prev Year)":"📅",
}




def _calc_kpi(df, kpi_type, col=None, group_col=None, metric_col=None,
              filter_col=None, filter_val=None, label=None):
    """Calculate a single KPI value from the DataFrame."""
    num_c = df.select_dtypes(include="number").columns.tolist()
    icon  = _KPI_ICONS.get(kpi_type, "📊")
    val   = "--"
    lbl   = label or kpi_type
    pfx   = sfx = ""
    try:
        if kpi_type == "Total (Sum)" and col in num_c:
            v = df[col].sum()
            val = _fmt_num(v)
            lbl = label or f"Total {col}"
        elif kpi_type == "Average (Mean)" and col in num_c:
            val = _fmt_num(df[col].mean()); lbl = label or f"Avg {col}"
        elif kpi_type == "Median" and col in num_c:
            val = _fmt_num(df[col].median()); lbl = label or f"Median {col}"
        elif kpi_type == "Count (Rows)":
            val = _fmt_num(len(df)); lbl = label or "Total Records"
        elif kpi_type == "Minimum Value" and col in num_c:
            val = _fmt_num(df[col].min()); lbl = label or f"Min {col}"
        elif kpi_type == "Maximum Value" and col in num_c:
            val = _fmt_num(df[col].max()); lbl = label or f"Max {col}"
        elif kpi_type == "Unique Values Count" and col:
            val = _fmt_num(df[col].nunique()); lbl = label or f"Unique {col}"
        elif kpi_type == "Date Range" and col:
            dates = pd.to_datetime(df[col], errors="coerce").dropna()
            if len(dates):
                val = f"{dates.min().strftime('%d %b %y')} → {dates.max().strftime('%d %b %y')}"
            lbl = label or f"Range of {col}"
        elif kpi_type == "% of Total (category share)" and col in num_c and filter_col and filter_val:
            tot = df[col].sum()
            sub = df[df[filter_col].astype(str) == str(filter_val)][col].sum()
            val = f"{sub/tot*100:.1f}" if tot else "0.0"; sfx = "%"
            lbl = label or f"{filter_val} share"
        elif kpi_type == "Top Category → Value" and group_col and metric_col in num_c:
            grp = df.groupby(group_col)[metric_col].sum()
            val = f"{grp.idxmax()}: {_fmt_num(grp.max())}"; lbl = label or f"Top {group_col}"
        elif kpi_type == "Bottom Category → Value" and group_col and metric_col in num_c:
            grp = df.groupby(group_col)[metric_col].sum()
            val = f"{grp.idxmin()}: {_fmt_num(grp.min())}"; lbl = label or f"Bottom {group_col}"
        elif kpi_type == "% Change (Latest Month vs Prev Month)" and col in num_c and filter_col:
            dates = pd.to_datetime(df[filter_col], errors="coerce")
            df2 = df.copy(); df2["_dt"] = dates; df2 = df2.dropna(subset=["_dt"])
            latest_m = df2["_dt"].dt.to_period("M").max()
            prev_m   = latest_m - 1
            cur_val  = df2[df2["_dt"].dt.to_period("M") == latest_m][col].sum()
            prev_val = df2[df2["_dt"].dt.to_period("M") == prev_m][col].sum()
            pct = (cur_val - prev_val) / abs(prev_val) * 100 if prev_val else 0
            val = f"{'+' if pct >= 0 else ''}{pct:.1f}"; sfx = "%"
            lbl = label or f"MoM {col}"
            return {"icon": icon, "label": lbl, "value": val, "prefix": pfx, "suffix": sfx,
                    "change_pct": float(pct)}
        elif kpi_type == "% Change (Latest Year vs Prev Year)" and col in num_c and filter_col:
            dates = pd.to_datetime(df[filter_col], errors="coerce")
            df2 = df.copy(); df2["_dt"] = dates; df2 = df2.dropna(subset=["_dt"])
            latest_y = df2["_dt"].dt.year.max()
            cur_val  = df2[df2["_dt"].dt.year == latest_y][col].sum()
            prev_val = df2[df2["_dt"].dt.year == (latest_y - 1)][col].sum()
            pct = (cur_val - prev_val) / abs(prev_val) * 100 if prev_val else 0
            val = f"{'+' if pct >= 0 else ''}{pct:.1f}"; sfx = "%"
            lbl = label or f"YoY {col}"
            return {"icon": icon, "label": lbl, "value": val, "prefix": pfx, "suffix": sfx,
                    "change_pct": float(pct)}
    except Exception as e:
        val = f"Err: {e}"
    return {"icon":icon,"label":lbl,"value":val,"prefix":pfx,"suffix":sfx}




def _kpi_card_html(kpi):
    """Render a KPI card as an HTML string."""
    change_pct = kpi.get("change_pct")
    arrow_html = ""
    if change_pct is not None:
        is_pos  = change_pct >= 0
        color   = "#10b981" if is_pos else "#ef4444"
        arrow   = "▲" if is_pos else "▼"
        arrow_html = (
            f'<div style="font-size:0.78rem;font-weight:700;color:{color};margin-top:3px;">'
            f'{arrow} {abs(change_pct):.1f}% vs prior period</div>'
        )
    icon   = escape(str(kpi.get("icon", "📊")))
    value  = escape(str(kpi.get("value", "--")))
    prefix = escape(str(kpi.get("prefix", "")))
    suffix = escape(str(kpi.get("suffix", "")))
    label  = escape(str(kpi.get("label", "")))


    _UNIT_META = {
        "B": ("B", "Billions",  "#8566fc"),
        "M": ("M", "Millions",  "#6163df"),
        "K": ("K", "Thousands", "#3390c8"),
    }
    full_val = f"{prefix}{value}{suffix}"
    if len(full_val) > 16:
        sz = "0.95rem"
    elif len(full_val) > 12:
        sz = "1.1rem"
    else:
        sz = "1.4rem"
    val_style = f"font-size:{sz};font-weight:800;line-height:1.05;"


    return (
        f'<div class="kpi-card" style="width:100%;box-shadow:0 2px 8px rgba(0,0,0,0.06);flex:1;">'
        f'<div style="font-size:1.2rem;line-height:1">{icon}</div>'
        f'<div style="{val_style}">{full_val}</div>'
        f'{arrow_html}'
        f'<div style="font-size:0.63rem;opacity:0.6;text-transform:uppercase;'
        f'letter-spacing:.07em;margin-top:4px;font-weight:600">{label}</div>'
        f'</div>'
    )




def _render_kpi_section(df, readonly):
    """Render the KPI management section (list, add, remove)."""
    if "kpis" not in st.session_state:
        st.session_state.kpis = []


    st.markdown("### 📌 KPI Cards")

    kpis = st.session_state.kpis
    if kpis:
        cols_per_row = 4
        rows = [kpis[i:i+cols_per_row] for i in range(0, len(kpis), cols_per_row)]
        for row in rows:
            rcols = st.columns(len(row))
            for ci, (kpi, rc) in enumerate(zip(row, rcols)):
                with rc:
                    st.markdown(_kpi_card_html(kpi), unsafe_allow_html=True)
                    if not readonly:
                        gi = kpis.index(kpi)
                        if st.button("✕", key=f"kpi_rm_{gi}", help="Remove KPI",
                                     use_container_width=True):
                            kpis.pop(gi)
                            _dash_sync_notes()
                            _persist()
                            st.rerun()
        st.write("")


    if not readonly and df is not None:
        with st.expander("➕ Add KPI from Dataset", expanded=len(kpis) == 0):
            num_c = df.select_dtypes(include="number").columns.tolist()
            cat_c = df.select_dtypes(include=["object","category"]).columns.tolist()
            all_c = df.columns.tolist()


            ka, kb = st.columns(2)
            with ka:
                ktype  = st.selectbox("KPI Type", _KPI_TYPES, key="kpi_type")
            with kb:
                klabel = st.text_input("Custom Label (leave blank for auto)",
                                       key="kpi_label",
                                       placeholder="e.g. Total Revenue")


            col = grp = met = fcol = fval = None


            simple_num = {"Total (Sum)","Average (Mean)","Median",
                          "Minimum Value","Maximum Value"}
            if ktype in simple_num:
                col = st.selectbox("Numeric column", num_c, key="kpi_col")
            elif ktype == "Unique Values Count":
                col = st.selectbox("Column", all_c, key="kpi_col2")
            elif ktype == "Date Range":
                dt_c = [c for c in all_c if any(x in c.lower() for x in
                        ("date","time","dt","year","month"))] or all_c
                col  = st.selectbox("Date column", dt_c, key="kpi_dt")
            elif ktype == "% of Total (category share)":
                p1, p2, p3 = st.columns(3)
                with p1: col  = st.selectbox("Numeric col", num_c, key="kpi_pc")
                with p2: fcol = st.selectbox("Filter col",  cat_c, key="kpi_fc") if cat_c else None
                if fcol:
                    uniq = df[fcol].dropna().unique().tolist()
                    with p3: fval = st.selectbox("Filter value", uniq, key="kpi_fv")
            elif ktype in ("Top Category → Value","Bottom Category → Value"):
                g1, g2 = st.columns(2)
                with g1: grp = st.selectbox("Category col", cat_c, key="kpi_grp") if cat_c else None
                with g2: met = st.selectbox("Metric col", num_c,   key="kpi_met") if num_c else None
            elif ktype in ("% Change (Latest Month vs Prev Month)",
                           "% Change (Latest Year vs Prev Year)"):
                dt_c = [c for c in all_c if any(x in c.lower() for x in
                        ("date","time","dt","year","month"))] or all_c
                p1, p2 = st.columns(2)
                with p1: fcol = st.selectbox("Date column",   dt_c,  key="kpi_chg_dt")
                with p2: col  = st.selectbox("Metric column", num_c, key="kpi_chg_met") if num_c else None


            if st.button("➕ Calculate & Add KPI", type="primary", key="kpi_add_btn"):
                kpi = _calc_kpi(df, ktype, col, grp, met, fcol, fval, klabel or None)
                st.session_state.kpis.append(kpi)
                _dash_sync_notes()
                _persist()
                eid = st.session_state.get("editing_session_id")
                if eid:
                    try:
                        from modules.database import update_session_db
                        update_session_db(
                            eid,
                            st.session_state.get("editing_session_name", "Session"),
                            charts_to_json(st.session_state.get("charts", [])),
                            st.session_state.get("selected_analyses", []),
                            st.session_state.get("user_id"),
                            dashboard_title = st.session_state.get("dashboard_title", ""),
                            kpis_json       = json.dumps(st.session_state.kpis),
                            layout_mode     = st.session_state.get("layout_mode", "portrait"),
                        )
                    except Exception as exc:
                        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                        pass
                st.success(f"✅ {kpi['label']}: {kpi['value']}{kpi['suffix']}")
                st.rerun()
    elif not readonly:
        st.caption("Upload a dataset and go to Analysis first to enable KPI calculation.")




def _render_layout_builder(charts):
    """Render the visual dashboard grid layout builder."""
    if not charts:
        return []


    n = len(charts)
    uid_list   = [c[0] for c in charts]
    title_map  = {c[0]: c[1] for c in charts}
    EMPTY      = "(empty)"
    opts       = [EMPTY] + [f"[{uid}] {title_map[uid][:45]}" for uid in uid_list]
    uid_of_opt = {f"[{uid}] {title_map[uid][:45]}": uid for uid in uid_list}


    if "grid_order" not in st.session_state or \
            set(st.session_state.grid_order) != set(uid_list):
        st.session_state.grid_order     = uid_list.copy()
        st.session_state.grid_fullwidth = {}


    order      = list(st.session_state.grid_order)
    full_width = dict(st.session_state.grid_fullwidth)


    st.markdown("### 🗂️ Arrange Charts in Dashboard Grid")


    grid_cols_n = st.radio(
        "Grid columns",
        [2, 3],
        index=0 if st.session_state.get("grid_cols_n", 2) == 2 else 1,
        horizontal=True,
        format_func=lambda x: f"{x}-Column Grid",
        key="grid_cols_radio",
    )
    st.session_state.grid_cols_n = grid_cols_n


    st.caption(
        f"Each row has **{grid_cols_n} slots**. "
        "Tick **Full Width** to span the first slot across the entire row.")


    assigned_uids = []
    seen = set()
    max_rows = n


    for row_i in range(max_rows):
        base      = row_i * grid_cols_n
        slot_uids = [
            order[base + s] if (base + s) < len(order) else None
            for s in range(grid_cols_n)
        ]
        slot_opts = [
            (f"[{u}] {title_map.get(u,'')[:45]}" if u and u in title_map else EMPTY)
            for u in slot_uids
        ]


        is_fw = full_width.get(slot_uids[0], False) if slot_uids[0] else False


        st.markdown(
            f'<div style="font-size:0.75rem;font-weight:700;color:#64748b;'
            f'text-transform:uppercase;letter-spacing:.06em;margin-bottom:4px">'
            f'Row {row_i + 1}</div>',
            unsafe_allow_html=True)


        col_parts = st.columns([5] * grid_cols_n + [2])
        fw_here = col_parts[-1].checkbox(
            "Full width", value=is_fw, key=f"grid_fw_{row_i}",
            help="Span first slot's chart across the entire row")


        chosen_slots = []
        for s in range(grid_cols_n):
            if fw_here and s > 0:
                col_parts[s].markdown(
                    '<div style="height:38px;display:flex;align-items:center;'
                    'background:rgba(97,99,223,0.06);border-radius:8px;'
                    'justify-content:center;font-size:0.8rem;opacity:0.5;">'
                    '← Full width →</div>', unsafe_allow_html=True)
                chosen_slots.append(EMPTY)
            else:
                chosen = col_parts[s].selectbox(
                    f"Slot {row_i + 1}{chr(65 + s)}",
                    opts,
                    index=opts.index(slot_opts[s]) if slot_opts[s] in opts else 0,
                    key=f"grid_s{s}_{row_i}",
                    label_visibility="collapsed")
                chosen_slots.append(chosen)


        lu = uid_of_opt.get(chosen_slots[0])
        if lu and lu not in seen:
            assigned_uids.append(lu)
            seen.add(lu)
            full_width[lu] = fw_here


        if not fw_here:
            for s in range(1, grid_cols_n):
                ru = uid_of_opt.get(chosen_slots[s])
                if ru and ru not in seen:
                    assigned_uids.append(ru)
                    seen.add(ru)


        if all(uid_of_opt.get(c) is None for c in chosen_slots):
            break
        if len(seen) >= n:
            break


    for uid in uid_list:
        if uid not in seen:
            assigned_uids.append(uid)


    if st.button("✅ Apply Layout", type="primary", key="apply_layout"):
        st.session_state.grid_order     = assigned_uids
        st.session_state.grid_fullwidth = full_width
        st.session_state.grid_cols_n    = grid_cols_n
        _dash_sync_notes()
        _persist()
        st.success("✅ Layout applied!")
        st.rerun()


    return assigned_uids




def _render_chart(item, idx, total, viewing_saved):
    """Render a single chart card with settings, insights, and notes."""
    uid, title, fig, desc, autos, ctype, saved_meta = \
        item if len(item) == 7 else (*item[:6], {})
    meta = saved_meta if viewing_saved else _meta(uid)
    note_key = f"desc_{uid}"
    if not viewing_saved:
        if note_key not in st.session_state or st.session_state[note_key] == "":
            shadow_val = st.session_state.get("_notes_shadow", {}).get(uid, "")
            st.session_state[note_key] = shadow_val or desc or ""


    if not viewing_saved:
        # Delegate the entire per-chart card to the isolated fragment.  This
        # covers: Chart Settings expander, Typography expander, plotly_chart,
        # auto-insights, and the notes text_area.  Grid-order buttons (⬆/⬇)
        # remain here because they mutate the shared ordered_charts list.
        from modules.ui.chart_card import render_chart_card
        chart_type = st.session_state.get(f"chart_type_{uid}", ctype or "")
        render_chart_card(
            uid, title, fig, chart_type, meta, autos,
            key_prefix="dash",
            edit_mode=not viewing_saved,
            viewing_saved=viewing_saved,
            on_meta_changed=lambda u, k, v: _set_meta(u, **{k: v}) if k != "__delete__" else None,
        )

        # Handle deferred deletion from inside the fragment.
        if st.session_state.get(f"_delete_requested_{uid}"):
            # Also invalidate the display-figure cache for this chart.
            for _ck in (f"_display_fig_{uid}", f"_display_fig_hash_{uid}",
                        f"_display_fig_font_{uid}", f"_display_fig_fonthash_{uid}"):
                st.session_state.pop(_ck, None)
            st.session_state.charts = [
                c for c in st.session_state.get("charts", []) if c[0] != uid
            ]
            if "grid_order" in st.session_state:
                st.session_state.grid_order = [u for u in st.session_state.grid_order if u != uid]
            st.session_state.pop(f"_delete_requested_{uid}", None)
            st.session_state.get("_notes_shadow", {}).pop(uid, None)
            _dash_sync_notes()
            _persist()
            st.rerun()

        # Re-read meta after any mutation the fragment may have made.
        meta = _meta(uid)

        # ------------------------------------------------------------------ #
        # Grid-order buttons (⬆ / ⬇ / 🗑) live here, outside the fragment,
        # because they mutate the shared ordered_charts list.  The fragment
        # itself also has a "✕" delete button; both call through the same
        # deferred-deletion path above.
        # ------------------------------------------------------------------ #
        if not viewing_saved and total > 1:
            _btn_cols = st.columns([1, 1, 1, 6])
            with _btn_cols[0]:
                if idx > 0 and st.button("⬆", key=f"up_{uid}", help="Move up"):
                    _cl = list(st.session_state.get("charts", []))
                    _ci = next((j for j,c in enumerate(_cl) if c[0]==uid), -1)
                    if _ci > 0:
                        _cl[_ci-1], _cl[_ci] = _cl[_ci], _cl[_ci-1]
                        st.session_state.charts = _cl
                        _go = list(st.session_state.get("grid_order", []))
                        _gi = next((j for j,u in enumerate(_go) if u==uid), -1)
                        if _gi > 0:
                            _go[_gi-1], _go[_gi] = _go[_gi], _go[_gi-1]
                            st.session_state.grid_order = _go
                        _dash_sync_notes(); _persist(); st.rerun()
            with _btn_cols[1]:
                if idx < total-1 and st.button("⬇", key=f"dn_{uid}", help="Move down"):
                    _cl = list(st.session_state.get("charts", []))
                    _ci = next((j for j,c in enumerate(_cl) if c[0]==uid), -1)
                    if _ci >= 0 and _ci < len(_cl)-1:
                        _cl[_ci], _cl[_ci+1] = _cl[_ci+1], _cl[_ci]
                        st.session_state.charts = _cl
                        _go = list(st.session_state.get("grid_order", []))
                        _gi = next((j for j,u in enumerate(_go) if u==uid), -1)
                        if _gi >= 0 and _gi < len(_go)-1:
                            _go[_gi], _go[_gi+1] = _go[_gi+1], _go[_gi]
                            st.session_state.grid_order = _go
                        _dash_sync_notes(); _persist(); st.rerun()
    else:
        # viewing_saved path: render chart without settings controls
        from modules.ui.chart_card import get_display_fig
        fig_show = get_display_fig(uid, fig, meta, ctype)
        st.plotly_chart(
            fig_show,
            use_container_width=True,
            key=f"dash_plotly_{uid}",
            config={"responsive": True, "displayModeBar": "hover", "mathjax": False},
        )
        if autos:
            with st.expander("💡 Insights", expanded=False):
                from modules.charts import clean_insight_text
                for ins in autos:
                    st.markdown(f"- {clean_insight_text(ins)}")
        live_desc = st.session_state.get(note_key, "") or (desc or "")
        if live_desc:
            safe_desc = escape(str(live_desc))
            st.markdown(
                f'<div style="background:rgba(133,102,252,0.07);border-left:3px solid #8566fc;'
                f'border-radius:6px;padding:.6rem .9rem;font-size:.87rem;margin-top:.3rem;">'
                f'<strong>Analysis Notes:</strong> {safe_desc}</div>',
                unsafe_allow_html=True,
            )








def _render_grid(ordered_charts, viewing_saved):
    total    = len(ordered_charts)
    fw       = st.session_state.get("grid_fullwidth", {})
    n_cols   = st.session_state.get("grid_cols_n", 2)
    i = 0
    while i < total:
        item     = ordered_charts[i]
        uid      = item[0]
        item_meta = item[6] if viewing_saved and len(item) > 6 else _meta(uid)
        is_fw    = fw.get(uid, False) or item_meta.get("full_width", False)


        if is_fw or i == total - 1:
            with st.container():
                _render_chart(item, i, total, viewing_saved)
            st.write("")
            i += 1
        else:
            row_items = [item]
            for s in range(1, n_cols):
                if i + s < total:
                    ni   = ordered_charts[i + s]
                    n_fw = fw.get(ni[0], False) or (
                        ni[6] if viewing_saved and len(ni) > 6 else _meta(ni[0])
                    ).get("full_width", False)
                    if not n_fw:
                        row_items.append(ni)
                    else:
                        break
                else:
                    break


            if len(row_items) > 1:
                row_cols = st.columns(len(row_items), gap="large")
                for ci, (ri, rc) in enumerate(zip(row_items, row_cols)):
                    with rc:
                        _render_chart(ri, i + ci, total, viewing_saved)
                st.write("")
                i += len(row_items)
            else:
                with st.container():
                    _render_chart(item, i, total, viewing_saved)
                st.write("")
                i += 1




def page_dashboard():
    """Main dashboard page: KPIs, layout, export, and chart management."""
    if "user_id" not in st.session_state:
        st.session_state.page = "profile"
        st.rerun()


    viewing_saved = "view_session_id" in st.session_state
    is_editing    = "editing_session_id" in st.session_state
    df            = st.session_state.get("df")


    if is_editing and "kpis" not in st.session_state:
        eid = st.session_state.editing_session_id
        sm  = get_session_meta(eid, st.session_state.get("user_id"))
        if sm:
            try:
                st.session_state.kpis = json.loads(sm.get("kpis_json", "[]"))
            except Exception:
                st.session_state.kpis = []
            if "layout_mode" not in st.session_state:
                st.session_state.layout_mode = sm.get("layout_mode", "portrait")
            if "dashboard_title" not in st.session_state:
                st.session_state.dashboard_title = sm.get("dashboard_title", "")
            if "grid_order" not in st.session_state:
                try:
                    st.session_state.grid_order = json.loads(sm.get("grid_order_json", "[]"))
                except Exception:
                    st.session_state.grid_order = []
            if "grid_fullwidth" not in st.session_state:
                try:
                    st.session_state.grid_fullwidth = json.loads(sm.get("grid_fullwidth_json", "{}"))
                except Exception:
                    st.session_state.grid_fullwidth = {}
            try:
                export_text = json.loads(sm.get("export_text_json", "{}"))
            except Exception:
                export_text = {}
            for key, val in export_text.items():
                session_key = f"ex_{key}"
                if session_key not in st.session_state:
                    st.session_state[session_key] = val
            try:
                export_colours = json.loads(sm.get("export_colours_json", "{}"))
            except Exception:
                export_colours = {}
            for key, val in export_colours.items():
                session_key = f"ex_{key}"
                if session_key not in st.session_state:
                    st.session_state[session_key] = val


    if is_editing and not st.session_state.get("_edit_notes_loaded"):
        eid    = st.session_state.editing_session_id
        loaded = get_session_charts(eid, st.session_state.get("user_id"))
        for uid, title, fig, desc, auto, ctype, meta in loaded:
            note_key = f"desc_{uid}"
            current_note = st.session_state.get(note_key, None)
            if desc and (current_note is None or current_note == ""):
                st.session_state[note_key] = desc
            meta_key = f"chart_meta_{uid}"
            if meta and not st.session_state.get(meta_key):
                st.session_state[meta_key] = meta
        st.session_state._edit_notes_loaded = True


    if viewing_saved:
        sid   = st.session_state.view_session_id
        sname = st.session_state.get("view_session_name","Saved Session")
        _session_just_loaded = (
            "_view_charts" not in st.session_state or
            st.session_state.get("_vsid") != sid
        )
        if _session_just_loaded:
            loaded = get_session_charts(sid, st.session_state.get("user_id"))
            for uid, title, fig, desc, auto, ctype, meta in loaded:
                st.session_state[f"desc_{uid}"]          = desc
                st.session_state[f"auto_insights_{uid}"] = auto
                st.session_state[f"chart_type_{uid}"]    = ctype
                st.session_state[f"chart_meta_{uid}"]    = meta
            st.session_state._view_charts = loaded
            st.session_state._vsid        = sid
        # get_session_meta() hits SQLite -- only fetch it on the same occasions
        # we already fetch the charts above (first view of this session, or
        # switching to a different saved session). Every consumer below only
        # applies its result via setdefault()/"key not in session_state", so
        # after the first load it would otherwise be a wasted DB round-trip
        # on every single rerun of this page (KPI edits, layout toggles,
        # export-text edits, etc.) for data that's never actually re-applied.
        if _session_just_loaded:
            sm = get_session_meta(sid, st.session_state.get("user_id"))
            st.session_state["_view_session_meta"] = sm
        else:
            sm = st.session_state.get("_view_session_meta")
        if sm is None:
            st.error("That saved session was not found for this account.")
            for k in ["view_session_id","_view_charts","_vsid","_view_session_meta",
                      "dashboard_title","kpis","layout_mode"]:
                st.session_state.pop(k, None)
            st.session_state.page = "home"
            st.rerun()
        st.session_state.setdefault("dashboard_title", sm["dashboard_title"])
        st.session_state.setdefault("layout_mode",     sm["layout_mode"])
        if "kpis" not in st.session_state:
            try:   st.session_state.kpis = json.loads(sm["kpis_json"])
            except Exception: st.session_state.kpis = []
        if "grid_order" not in st.session_state:
            try:
                st.session_state.grid_order = json.loads(sm.get("grid_order_json", "[]"))
            except Exception:
                st.session_state.grid_order = []
        if "grid_fullwidth" not in st.session_state:
            try:
                st.session_state.grid_fullwidth = json.loads(sm.get("grid_fullwidth_json", "{}"))
            except Exception:
                st.session_state.grid_fullwidth = {}
        try:
            export_text = json.loads(sm.get("export_text_json", "{}"))
        except Exception:
            export_text = {}
        for key, val in export_text.items():
            session_key = f"ex_{key}"
            if session_key not in st.session_state:
                st.session_state[session_key] = val
        try:
            export_colours = json.loads(sm.get("export_colours_json", "{}"))
        except Exception:
            export_colours = {}
        for key, val in export_colours.items():
            session_key = f"ex_{key}"
            if session_key not in st.session_state:
                st.session_state[session_key] = val
        df = None
    else:
        sname = f"Analysis -- {st.session_state.get('file_name','')}"


    charts = _all_charts(viewing_saved)


    render_logo()

    if st.button("← Back", key="dash_back"):
        for _k in ("_regen_uid", "_regen_type", "_regen_restore"):
            st.session_state.pop(_k, None)
        if viewing_saved:
            for k in ["view_session_id","_view_charts","_vsid","_view_session_meta",
                      "dashboard_title","kpis","layout_mode"]:
                st.session_state.pop(k, None)
            st.session_state.page = "home"
        else:
            st.session_state.page = "analysis"
        st.rerun()

    if not viewing_saved:
        ti = st.text_input("📋 Dashboard Title",
                           value=st.session_state.get("dashboard_title",""),
                           placeholder="e.g. Q1 2025 Sales Dashboard",
                           key="dbtitle")
        if ti != st.session_state.get("dashboard_title",""):
            st.session_state.dashboard_title = ti
            _persist()

    st.markdown("---")

    if not viewing_saved:
        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            def_name = st.session_state.get("editing_session_name", sname) if is_editing else sname
            st.text_input("Session name", value=def_name, key="sname_in")
        with col2:
            lo = st.radio("📐 Export Layout", ["Portrait","Landscape"],
                          index=1 if st.session_state.get("layout_mode")=="landscape" else 0,
                          horizontal=True)
            st.session_state.layout_mode = lo.lower()
        with col3:
            st.write("")
            if st.button("💾 Save", use_container_width=True):
                sname_in = st.session_state.get("sname_in", sname)
                _do_save(sname_in, charts, df)
            if is_editing and st.button("🔄 Update", use_container_width=True):
                sname_in = st.session_state.get("sname_in", sname)
                _do_update(sname_in, charts, clear_editing=False)

    st.markdown("---")


    _render_kpi_section(df, readonly=viewing_saved)


    if not charts:
        st.info("No charts yet. Go back to Analysis to generate some!")
        inject_footer()
        return


    uid_map   = {c[0]: c for c in charts}
    go_order  = st.session_state.get("grid_order", [c[0] for c in charts])
    seen_uids: set = set()
    ordered   = []
    for u in go_order:
        if u in uid_map and u not in seen_uids:
            ordered.append(uid_map[u])
            seen_uids.add(u)
    for c in charts:
        if c[0] not in seen_uids:
            ordered.append(c)
            seen_uids.add(c[0])


    if ordered:
        _export_row(ordered, sname, viewing_saved)
        st.markdown("---")


    if charts and not viewing_saved:
        with st.expander("🗂️ Arrange Dashboard Layout", expanded=False):
            _render_layout_builder(charts)
        st.markdown("---")


    st.markdown("### 📈 Dashboard")
    try:
        _render_grid(ordered, viewing_saved)
    except Exception as _render_err:
        err_msg = str(_render_err)
        if "DuplicateWidgetID" in err_msg or "duplicate" in err_msg.lower():
            st.warning(
                "⚠️ A chart appears more than once in the layout. "
                "Open **Arrange Dashboard Layout** above and make sure each "
                "chart is assigned to only one slot, then click **Apply Layout**.",
                icon=None)
        else:
            st.error(f"Dashboard render error: {err_msg}")
    inject_footer()




def _generate_export_html(
    charts: list,
    sname: str,
    viewing_saved: bool,
) -> tuple[str, str]:
    """
    Return (html_string, safe_file_name) for the export-ready dashboard.
    Pure function — does NOT render any Streamlit widgets.
    """
    orient     = st.session_state.get("layout_mode","portrait")
    kpis       = st.session_state.get("kpis",[])
    dash_title = st.session_state.get("dashboard_title","") or sname

    export_charts = []
    full_width = st.session_state.get("grid_fullwidth", {})
    for item in charts:
        uid  = item[0]
        meta = dict(item[6] if len(item)>6 else _meta(uid))
        if full_width.get(uid):
            meta["full_width"] = True
        style = _merge_text_style(meta.get("text_style", {}))
        fig  = _apply_axes(item[2], meta.get("x_label",""), meta.get("y_label",""), style)
        fig  = _apply_legend_names(fig, meta.get("legend_names", {}), meta.get("legend_title", ""), style)
        fig  = apply_chart_display_options(fig, meta, item[5] if len(item)>5 else "")
        notes = st.session_state.get(f"desc_{uid}", "") or (item[3] if len(item) > 3 else "")
        export_charts.append((uid, item[1], fig, notes, item[4] if len(item)>4 else [],
                              item[5] if len(item)>5 else "", meta))

    safe_file = re.sub(r"[^A-Za-z0-9_.-]+", "_", dash_title).strip("._") or "lytrize_report"

    _EX_DEFAULTS = {
        "ex_bg": "#121a2e", "ex_card": "#1b2245", "ex_kpi": "#1b2245",
        "ex_accent": "#6163df", "ex_border": "#2c3564", "ex_text": "#f5f7ff",
        "ex_ins_bg": "#1a2441", "ex_ins_bd": "#6163df",
        "ex_not_bg": "#1a1732", "ex_not_bd": "#8566fc",
        "ex_density": "Comfortable", "ex_radius": 12, "ex_chart_h": 400,
        "ex_width": "Auto", "ex_meta": True,
        "ex_kpi_text_color": "#f5f7ff", "ex_kpi_val_size": 14,
    }
    _density = {
        "Compact": {"gap": 14, "padding": 20},
        "Comfortable": {"gap": 24, "padding": 32},
        "Spacious": {"gap": 34, "padding": 44},
    }.get(st.session_state.get("ex_density", _EX_DEFAULTS["ex_density"]), {"gap": 24, "padding": 32})
    _width = {
        "Auto": "",
        "Narrow": "960px",
        "Wide": "1440px",
        "Full": "100%",
    }.get(st.session_state.get("ex_width", _EX_DEFAULTS["ex_width"]), "")

    export_theme = {
        "bg_color":       st.session_state.get("ex_bg",     _EX_DEFAULTS["ex_bg"]),
        "card_bg":        st.session_state.get("ex_card",   _EX_DEFAULTS["ex_card"]),
        "kpi_bg":         st.session_state.get("ex_kpi",    _EX_DEFAULTS["ex_kpi"]),
        "accent_color":   st.session_state.get("ex_accent", _EX_DEFAULTS["ex_accent"]),
        "card_border":    st.session_state.get("ex_border", _EX_DEFAULTS["ex_border"]),
        "text_color":     st.session_state.get("ex_text",   _EX_DEFAULTS["ex_text"]),
        "insight_bg":     st.session_state.get("ex_ins_bg", _EX_DEFAULTS["ex_ins_bg"]),
        "insight_border": st.session_state.get("ex_ins_bd", _EX_DEFAULTS["ex_ins_bd"]),
        "notes_bg":       st.session_state.get("ex_not_bg", _EX_DEFAULTS["ex_not_bg"]),
        "notes_border":   st.session_state.get("ex_not_bd", _EX_DEFAULTS["ex_not_bd"]),
        "card_radius":    st.session_state.get("ex_radius", _EX_DEFAULTS["ex_radius"]),
        "gap":            _density["gap"],
        "body_padding":   _density["padding"],
        "chart_height":   st.session_state.get("ex_chart_h",  _EX_DEFAULTS["ex_chart_h"]),
        "max_width":      _width,
        "show_meta":      st.session_state.get("ex_meta",     _EX_DEFAULTS["ex_meta"]),
        "kpi_text_color": st.session_state.get("ex_kpi_text_color", _EX_DEFAULTS["ex_kpi_text_color"]),
        "kpi_val_size":   st.session_state.get("ex_kpi_val_size",   _EX_DEFAULTS["ex_kpi_val_size"]),
        "title_font":    st.session_state.get("ex_title_font",   "Inter"),
        "title_style":  st.session_state.get("ex_title_style",  "Normal"),
        "title_size":   st.session_state.get("ex_title_size",   28),
        "title_color":  st.session_state.get("ex_title_color",  "#6163df"),
        "insights_font": st.session_state.get("ex_insights_font", "Inter"),
        "insights_style": st.session_state.get("ex_insights_style", "Normal"),
        "insights_size": st.session_state.get("ex_insights_size", 14),
        "insights_color": st.session_state.get("ex_insights_color", "#f5f7ff"),
        "notes_font":    st.session_state.get("ex_notes_font",    "Inter"),
        "notes_style":  st.session_state.get("ex_notes_style",  "Normal"),
        "notes_size":   st.session_state.get("ex_notes_size",   14),
        "notes_color":  st.session_state.get("ex_notes_color",   "#f5f7ff"),
    }

    html = generate_html_report(
        export_charts, sname,
        orientation=orient, kpis=kpis,
        dashboard_title=dash_title,
        grid_cols_n=st.session_state.get("grid_cols_n", 2),
        theme=export_theme,
    )
    return html, safe_file


def _export_row(charts, sname, viewing_saved):
    """Render the full export controls row: presets, customiser, preview, download."""
    dash_title = st.session_state.get("dashboard_title","") or sname
    safe_file  = re.sub(r"[^A-Za-z0-9_.-]+", "_", dash_title).strip("._") or "lytrize_report"


    _EX_DEFAULTS = {
        "ex_bg": "#121a2e", "ex_card": "#1b2245", "ex_kpi": "#1b2245",
        "ex_accent": "#6163df", "ex_border": "#2c3564", "ex_text": "#f5f7ff",
        "ex_ins_bg": "#1a2441", "ex_ins_bd": "#6163df",
        "ex_not_bg": "#1a1732", "ex_not_bd": "#8566fc",
        "ex_density": "Comfortable", "ex_radius": 12, "ex_chart_h": 400,
        "ex_width": "Auto", "ex_meta": True,
        "ex_kpi_text_color": "#f5f7ff", "ex_kpi_val_size": 14,
        "ex_title_color": "#6163df", "ex_insights_color": "#f5f7ff", "ex_notes_color": "#f5f7ff",
    }
    _PRESETS = {
        "⚡ Midnight Pulse": {
            "ex_bg": "#08111f",
            "ex_card": "#101a35",
            "ex_kpi": "#0c1530",
            "ex_accent": "#8b5cf6",#0D1325
            "ex_border": "#31406e",
            "ex_text": "#f8fbff",
            "ex_ins_bg": "#14264a",
            "ex_ins_bd": "#22d3ee",
            "ex_not_bg": "#1b1736",
            "ex_not_bd": "#f472b6",
            "ex_title_color": "#8b5cf6",
            "ex_insights_color": "#f8fbff",
            "ex_notes_color": "#f8fbff",
            "ex_kpi_text_color": "#f8fbff",
        },
        "🌊 Electric Lagoon": {
            "ex_bg": "#061a24",
            "ex_card": "#0f2437",
            "ex_kpi": "#0b1f30",
            "ex_accent": "#38bdf8",
            "ex_border": "#0ea5e9",
            "ex_text": "#ecfeff",
            "ex_ins_bg": "#123e52",
            "ex_ins_bd": "#22d3ee",
            "ex_not_bg": "#102a43",
            "ex_not_bd": "#a855f7",
            "ex_title_color": "#38bdf8",
            "ex_insights_color": "#ecfeff",
            "ex_notes_color": "#ecfeff",
            "ex_kpi_text_color": "#ecfeff",
        },
        "💖 Prism Pop": {
            "ex_bg": "#1b1030",
            "ex_card": "#251544",
            "ex_kpi": "#22113f",
            "ex_accent": "#ec4899",
            "ex_border": "#8b5cf6",
            "ex_text": "#fff7ff",
            "ex_ins_bg": "#37124d",
            "ex_ins_bd": "#f59e0b",
            "ex_not_bg": "#211638",
            "ex_not_bd": "#60a5fa",
            "ex_title_color": "#ec4899",
            "ex_insights_color": "#fff7ff",
            "ex_notes_color": "#fff7ff",
            "ex_kpi_text_color": "#fff7ff",
        },
        "☀️ Solar Flare": {
            "ex_bg": "#20130a",
            "ex_card": "#322012",
            "ex_kpi": "#2f180f",
            "ex_accent": "#f97316",
            "ex_border": "#f59e0b",
            "ex_text": "#fff7ed",
            "ex_ins_bg": "#3a2410",
            "ex_ins_bd": "#facc15",
            "ex_not_bg": "#2d1e0b",
            "ex_not_bd": "#fb7185",
            "ex_title_color": "#f97316",
            "ex_insights_color": "#fff7ed",
            "ex_notes_color": "#fff7ed",
            "ex_kpi_text_color": "#fff7ed",
        },
        "❄️ Arctic Neon": {
            "ex_bg": "#07131f",
            "ex_card": "#0f2235",
            "ex_kpi": "#0b1b2d",
            "ex_accent": "#60a5fa",
            "ex_border": "#22d3ee",
            "ex_text": "#eff6ff",
            "ex_ins_bg": "#12324b",
            "ex_ins_bd": "#38bdf8",
            "ex_not_bg": "#14213d",
            "ex_not_bd": "#34d399",
            "ex_title_color": "#60a5fa",
            "ex_insights_color": "#eff6ff",
            "ex_notes_color": "#eff6ff",
            "ex_kpi_text_color": "#eff6ff",
        },
        "🌿 Forest Electric": {
            "ex_bg": "#071a12",
            "ex_card": "#0f281b",
            "ex_kpi": "#0b2217",
            "ex_accent": "#22c55e",
            "ex_border": "#34d399",
            "ex_text": "#effaf3",
            "ex_ins_bg": "#123324",
            "ex_ins_bd": "#a3e635",
            "ex_not_bg": "#182817",
            "ex_not_bd": "#f59e0b",
            "ex_title_color": "#22c55e",
            "ex_insights_color": "#effaf3",
            "ex_notes_color": "#effaf3",
            "ex_kpi_text_color": "#effaf3",
        },
        "✨ Aurora Bright": {
            "ex_bg": "#f7fbff",
            "ex_card": "#ffffff",
            "ex_kpi": "#eefcf8",
            "ex_accent": "#14b8a6",
            "ex_border": "#b7e4d3",
            "ex_text": "#0f172a",
            "ex_ins_bg": "#e7fff5",
            "ex_ins_bd": "#22c55e",
            "ex_not_bg": "#fff7e6",
            "ex_not_bd": "#f59e0b",
            "ex_title_color": "#14b8a6",
            "ex_insights_color": "#0f172a",
            "ex_notes_color": "#0f172a",
            "ex_kpi_text_color": "#0f172a",
        },
        "🌅 Sunset Bloom": {
            "ex_bg": "#fff7fb",
            "ex_card": "#ffffff",
            "ex_kpi": "#fff0f5",
            "ex_accent": "#ec4899",
            "ex_border": "#f6b3d4",
            "ex_text": "#3f1634",
            "ex_ins_bg": "#ffe4ec",
            "ex_ins_bd": "#f43f5e",
            "ex_not_bg": "#fff6ea",
            "ex_not_bd": "#fb923c",
            "ex_title_color": "#ec4899",
            "ex_insights_color": "#3f1634",
            "ex_notes_color": "#3f1634",
            "ex_kpi_text_color": "#3f1634",
        },
        "🌊 Ocean Breeze": {
            "ex_bg": "#f4fbff",
            "ex_card": "#ffffff",
            "ex_kpi": "#e6f5ff",
            "ex_accent": "#0284c7",
            "ex_border": "#9fd7f5",
            "ex_text": "#0c4a6e",
            "ex_ins_bg": "#dff3ff",
            "ex_ins_bd": "#38bdf8",
            "ex_not_bg": "#effcf8",
            "ex_not_bd": "#14b8a6",
            "ex_title_color": "#0284c7",
            "ex_insights_color": "#0c4a6e",
            "ex_notes_color": "#0c4a6e",
            "ex_kpi_text_color": "#0c4a6e",
        },
        "🍋 Citrus Glow": {
            "ex_bg": "#fffdf3",
            "ex_card": "#ffffff",
            "ex_kpi": "#fff4cc",
            "ex_accent": "#f59e0b",
            "ex_border": "#f7d46b",
            "ex_text": "#713f12",
            "ex_ins_bg": "#fff1c2",
            "ex_ins_bd": "#f97316",
            "ex_not_bg": "#fff7e8",
            "ex_not_bd": "#ef4444",
            "ex_title_color": "#f59e0b",
            "ex_insights_color": "#713f12",
            "ex_notes_color": "#713f12",
            "ex_kpi_text_color": "#713f12",
        },
        "🌸 Blossom Pop": {
            "ex_bg": "#fff7fb",
            "ex_card": "#ffffff",
            "ex_kpi": "#ffeaf3",
            "ex_accent": "#db2777",
            "ex_border": "#f3b0cf",
            "ex_text": "#7a1f55",
            "ex_ins_bg": "#fde2ee",
            "ex_ins_bd": "#ec4899",
            "ex_not_bg": "#f4f0ff",
            "ex_not_bd": "#8b5cf6",
            "ex_title_color": "#db2777",
            "ex_insights_color": "#7a1f55",
            "ex_notes_color": "#7a1f55",
            "ex_kpi_text_color": "#7a1f55",
        },
        "🪴 Mint Fresh": {
            "ex_bg": "#f4fff7",
            "ex_card": "#ffffff",
            "ex_kpi": "#e3fcef",
            "ex_accent": "#16a34a",
            "ex_border": "#a7e6b8",
            "ex_text": "#14532d",
            "ex_ins_bg": "#dcfce7",
            "ex_ins_bd": "#22c55e",
            "ex_not_bg": "#eefcf4",
            "ex_not_bd": "#10b981",
            "ex_title_color": "#16a34a",
            "ex_insights_color": "#14532d",
            "ex_notes_color": "#14532d",
            "ex_kpi_text_color": "#14532d",
        },
    }
    if "_ex_pending" in st.session_state:
        for k, v in st.session_state["_ex_pending"].items():
            st.session_state[k] = v
        del st.session_state["_ex_pending"]


    with st.expander("🎨 Customise Export Colours", expanded=False):
        st.caption(
            "Set colours for the downloaded HTML dashboard. "
            "Changes are preview-only — they apply to the downloaded file."
        )
        st.markdown("**Quick presets:**")
        pr_cols = st.columns(len(_PRESETS))
        for i, (col, (label, vals)) in enumerate(zip(pr_cols, _PRESETS.items())):
            if col.button(label, key=f"preset_{i}", use_container_width=True):
                st.session_state["_ex_pending"] = vals
                st.rerun()


        tab_colours, tab_text, tab_layout = st.tabs(["Colours", "Text", "Layout"])
        with tab_colours:
            ec1, ec2, ec3 = st.columns(3)
            with ec1:
                ex_bg     = st.color_picker("Page background",     st.session_state.get("ex_bg",     _EX_DEFAULTS["ex_bg"]),     key="ex_bg")
                ex_card   = st.color_picker("Chart card fill",     st.session_state.get("ex_card",   _EX_DEFAULTS["ex_card"]),   key="ex_card")
                ex_kpi    = st.color_picker("KPI card fill",       st.session_state.get("ex_kpi",    _EX_DEFAULTS["ex_kpi"]),    key="ex_kpi")
                ex_kpi_text_color = st.color_picker("KPI text colour",
                    st.session_state.get("ex_kpi_text_color", _EX_DEFAULTS["ex_kpi_text_color"]),
                    key="ex_kpi_text_color",
                    help="Colour of the KPI value number and label text in the export.")
                ex_kpi_val_size   = st.slider("KPI value font size", 10, 28,
                    int(st.session_state.get("ex_kpi_val_size", _EX_DEFAULTS["ex_kpi_val_size"])),
                    key="ex_kpi_val_size",
                    help="Font size of the KPI value number in the export.")
            with ec2:
                ex_accent = st.color_picker("Accent / headings",   st.session_state.get("ex_accent", _EX_DEFAULTS["ex_accent"]), key="ex_accent")
                ex_border = st.color_picker("Card border",         st.session_state.get("ex_border", _EX_DEFAULTS["ex_border"]), key="ex_border")
                ex_text   = st.color_picker("Body text",           st.session_state.get("ex_text",   _EX_DEFAULTS["ex_text"]),   key="ex_text")
            with ec3:
                ex_ins_bg = st.color_picker("Insights background", st.session_state.get("ex_ins_bg", _EX_DEFAULTS["ex_ins_bg"]), key="ex_ins_bg")
                ex_ins_bd = st.color_picker("Insights border",     st.session_state.get("ex_ins_bd", _EX_DEFAULTS["ex_ins_bd"]), key="ex_ins_bd")
                ex_not_bg = st.color_picker("Notes background",    st.session_state.get("ex_not_bg", _EX_DEFAULTS["ex_not_bg"]), key="ex_not_bg")
                ex_not_bd = st.color_picker("Notes border",        st.session_state.get("ex_not_bd", _EX_DEFAULTS["ex_not_bd"]), key="ex_not_bd")
        with tab_text:
            inject_font_preview_css()
            font_styles_list = [
                "Normal", "Bold", "Italic", "Underline",
                "Bold Italic", "Bold Underline", "Italic Underline",
                "Bold Italic Underline",
            ]
            st.markdown("**Dashboard Title**")
            ex_title_font = font_select("Font", default=st.session_state.get("ex_title_font", "Inter"), key="ex_title_font")
            ex_title_style = st.selectbox("Style", font_styles_list, index=0, key="ex_title_style")
            ex_title_size = st.slider("Size", 10, 50, int(st.session_state.get("ex_title_size", 28)), key="ex_title_size")
            ex_title_color = st.color_picker("Colour", st.session_state.get("ex_title_color", "#6163df"), key="ex_title_color")
            _render_section_preview(
                "📊 Dashboard Preview – The quick brown fox jumps over the lazy dog",
                ex_title_font,
                ex_title_style,
                ex_title_size,
                ex_title_color,
            )
            st.markdown("**Insights**")
            ex_insights_font = font_select("Font", default=st.session_state.get("ex_insights_font", "Inter"), key="ex_insights_font")
            ex_insights_style = st.selectbox("Style", font_styles_list, key="ex_insights_style")
            ex_insights_size = st.slider("Size", 10, 50, int(st.session_state.get("ex_insights_size", 14)), key="ex_insights_size")
            ex_insights_color = st.color_picker("Colour", st.session_state.get("ex_insights_color", "#f5f7ff"), key="ex_insights_color")
            _render_section_preview(
                "💡 Insights Preview – Sample insight showing current text styling",
                ex_insights_font,
                ex_insights_style,
                ex_insights_size,
                ex_insights_color,
            )
            st.markdown("**Notes**")
            ex_notes_font = font_select("Font", default=st.session_state.get("ex_notes_font", "Inter"), key="ex_notes_font")
            ex_notes = st.selectbox("Style", font_styles_list, key="ex_notes_style")
            ex_notes_size = st.slider("Size", 10, 50, int(st.session_state.get("ex_notes_size", 14)), key="ex_notes_size")
            ex_notes_color = st.color_picker("Colour", st.session_state.get("ex_notes_color", "#f5f7ff"), key="ex_notes_color")
            _render_section_preview(
                "📝 Notes Preview – Sample notes text with your chosen formatting",
                ex_notes_font,
                ex_notes,
                ex_notes_size,
                ex_notes_color,
            )
        with tab_layout:
            density_options = ["Compact", "Comfortable", "Spacious"]
            _density_value = st.session_state.get("ex_density", _EX_DEFAULTS["ex_density"])
            if _density_value not in density_options:
                _density_value = _EX_DEFAULTS["ex_density"]
            ex_density = st.selectbox(
                "Spacing density",
                density_options,
                index=density_options.index(_density_value),
                key="ex_density",
            )
            l1, l2, l3 = st.columns(3)
            with l1:
                ex_radius = st.slider("Card radius", 0, 24, int(st.session_state.get("ex_radius", _EX_DEFAULTS["ex_radius"])), key="ex_radius")
                ex_chart_h = st.slider("Chart height", 280, 720, int(st.session_state.get("ex_chart_h", _EX_DEFAULTS["ex_chart_h"])), 20, key="ex_chart_h")
            with l2:
                width_options = ["Auto", "Narrow", "Wide", "Full"]
                _width_value = st.session_state.get("ex_width", _EX_DEFAULTS["ex_width"])
                if _width_value not in width_options:
                    _width_value = _EX_DEFAULTS["ex_width"]
                ex_width = st.selectbox(
                    "Page width",
                    width_options,
                    index=width_options.index(_width_value),
                    key="ex_width",
                )
            with l3:
                ex_meta = st.checkbox("Show generated timestamp", value=bool(st.session_state.get("ex_meta", _EX_DEFAULTS["ex_meta"])), key="ex_meta")


    _density = {
        "Compact": {"gap": 14, "padding": 20},
        "Comfortable": {"gap": 24, "padding": 32},
        "Spacious": {"gap": 34, "padding": 44},
    }.get(st.session_state.get("ex_density", _EX_DEFAULTS["ex_density"]), {"gap": 24, "padding": 32})
    _width = {
        "Auto": "",
        "Narrow": "960px",
        "Wide": "1440px",
        "Full": "100%",
    }.get(st.session_state.get("ex_width", _EX_DEFAULTS["ex_width"]), "")


    # ----- Generate the export HTML using the shared function -----
    html, safe_file = _generate_export_html(charts, sname, viewing_saved)

    # ----- Live Preview expander -----
    with st.expander("👁️ Preview Dashboard", expanded=False):
        st.caption(
            "Live preview of the download-ready HTML dashboard. "
            "Uses the current export colours, text, and layout settings. "
        )
        # Render the full export HTML inside an iframe via streamlit.components.v1
        # Height is auto-adjusted by the scrolling flag; default 700px is enough
        # for most dashboards without overwhelming the UI.
        # Use a generous height for the preview iframe so most dashboards
        # are fully visible without needing to scroll within the iframe.
        _comp.html(html, height=1200, scrolling=True)

    # ----- Download & screenshot info row -----
    c1, c2, c3 = st.columns([2, 2, 3])
    with c1:
        st.download_button("⬇️ Download HTML", html,
                           file_name=f"{safe_file}.html",
                           mime="text/html", use_container_width=True)


    with c2:
        st.info(
            "**Firefox based Browsers have**"
            " **built-in full page screenshot option**:\n\n"
            "Press **Ctrl+Shift+S** (or right-click → *Take Screenshot*) "
            "to capture the full page, then save as PNG."
        )

    with c3:
        st.info(
            "**Chromium based Browsers needs manual way**:\n\n"
            "Press **Ctrl+Shift+I** to open DevTools, then press "
            "**Ctrl+Shift+P**, type \"screenshot\", and select "
            "**Capture full size screenshot** to save the page as PNG."
        )




def _collect_export_text_json() -> str:
    """Collect the 12 export text widget values into a JSON string."""
    return json.dumps({
        "title_font":   st.session_state.get("ex_title_font",   "Inter"),
        "title_style":  st.session_state.get("ex_title_style",  "Normal"),
        "title_size":   st.session_state.get("ex_title_size",   28),
        "title_color":  st.session_state.get("ex_title_color",  "#6163df"),
        "insights_font": st.session_state.get("ex_insights_font", "Inter"),
        "insights_style": st.session_state.get("ex_insights_style", "Normal"),
        "insights_size": st.session_state.get("ex_insights_size", 14),
        "insights_color": st.session_state.get("ex_insights_color", "#f5f7ff"),
        "notes_font":    st.session_state.get("ex_notes_font",    "Inter"),
        "notes_style":  st.session_state.get("ex_notes_style",  "Normal"),
        "notes_size":   st.session_state.get("ex_notes_size",   14),
        "notes_color":  st.session_state.get("ex_notes_color",   "#f5f7ff"),
    })


def _collect_export_colours_json() -> str:
    """Collect the colour/layout widget values into a JSON string."""
    return json.dumps({
        "bg":            st.session_state.get("ex_bg",     "#121a2e"),
        "card":          st.session_state.get("ex_card",   "#1b2245"),
        "kpi":           st.session_state.get("ex_kpi",    "#1b2245"),
        "accent":        st.session_state.get("ex_accent", "#6163df"),
        "border":        st.session_state.get("ex_border", "#2c3564"),
        "text":          st.session_state.get("ex_text",   "#f5f7ff"),
        "ins_bg":        st.session_state.get("ex_ins_bg", "#1a2441"),
        "ins_bd":        st.session_state.get("ex_ins_bd", "#6163df"),
        "not_bg":        st.session_state.get("ex_not_bg", "#1a1732"),
        "not_bd":        st.session_state.get("ex_not_bd", "#8566fc"),
        "density":       st.session_state.get("ex_density",    "Comfortable"),
        "radius":        st.session_state.get("ex_radius",     12),
        "chart_h":       st.session_state.get("ex_chart_h",   400),
        "width":         st.session_state.get("ex_width",      "Auto"),
        "meta":          st.session_state.get("ex_meta",       True),
        "kpi_text_color": st.session_state.get("ex_kpi_text_color", "#f5f7ff"),
        "kpi_val_size":  st.session_state.get("ex_kpi_val_size",  14),
    })


def _do_save(sname_in, charts, df):
    """Save the current dashboard as a new session."""
    if "user_id" not in st.session_state:
        return
    sid = save_session_db(
        st.session_state.user_id, sname_in,
        st.session_state.get("file_name",""),
        df.shape[0] if df is not None else 0,
        df.shape[1] if df is not None else 0,
        st.session_state.get("selected_analyses",[]),
        charts_to_json(st.session_state.get("charts",[])),
        dashboard_title   = st.session_state.get("dashboard_title",""),
        kpis_json         = json.dumps(st.session_state.get("kpis",[])),
        layout_mode       = st.session_state.get("layout_mode","portrait"),
        grid_order_json   = json.dumps(st.session_state.get("grid_order", [])),
        grid_fullwidth_json = json.dumps(st.session_state.get("grid_fullwidth", {})),
        export_text_json  = _collect_export_text_json(),
        export_colours_json = _collect_export_colours_json(),
    )
    clear_draft(st.session_state.user_id)
    st.session_state.editing_session_id   = sid
    st.session_state.editing_session_name = sname_in
    st.session_state.pop("_edit_notes_loaded",    None)
    st.session_state.pop("_analysis_notes_loaded", None)
    st.session_state.pop("_notes_shadow",          None)
    st.toast(f"✅ Saved as '{sname_in}'!", icon="✅")
    st.rerun()




def _do_update(sname_in, charts, clear_editing=False):
    """Update the currently edited session with the current dashboard state."""
    st.session_state.pop("_edit_notes_loaded",      None)
    st.session_state.pop("_analysis_notes_loaded",  None)
    st.session_state.pop("_notes_shadow",           None)
    eid = st.session_state.editing_session_id
    update_session_db(
        eid, sname_in,
        charts_to_json(st.session_state.get("charts",[])),
        st.session_state.get("selected_analyses",[]),
        st.session_state.user_id,
        dashboard_title   = st.session_state.get("dashboard_title",""),
        kpis_json         = json.dumps(st.session_state.get("kpis",[])),
        layout_mode       = st.session_state.get("layout_mode","portrait"),
        grid_order_json   = json.dumps(st.session_state.get("grid_order", [])),
        grid_fullwidth_json = json.dumps(st.session_state.get("grid_fullwidth", {})),
        export_text_json  = _collect_export_text_json(),
        export_colours_json = _collect_export_colours_json(),
    )
    clear_draft(st.session_state.user_id)
    st.toast(f"✅ Updated '{sname_in}'!", icon="✅")
    if clear_editing:
        st.session_state.pop("editing_session_id",   None)
        st.session_state.pop("editing_session_name", None)
        st.session_state.page = "home"
        st.rerun()
