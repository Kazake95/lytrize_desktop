"""modules/ui/chart_card.py -- Per-chart card rendered inside an isolated @st.fragment.

Isolating each chart behind its own fragment means that tweaking Chart 8's
typography slider only reruns Chart 8's fragment — Chart 1..7 and the rest of
the page (nav, preview, config panel, KPIs) stay inert.  This is the single
largest win in the Power BI-class responsiveness plan.

Public surface
~~~~~~~~~~~~~~
* render_chart_card(...)  -- drop-in replacement for the per-chart block that
                            used to live in analysis._render_chart_list and
                            dashboard._render_chart.
* _apply_axes / _apply_legend_names duplicate the logic in dashboard.py
  (kept local intentionally -- see note below).
"""

from __future__ import annotations

import copy
import html
import re
from typing import Any

import streamlit as st

from modules.ui.chart_settings import default_text_style as _default_text_style

# ---------------------------------------------------------------------------
# Axis / legend helpers.
#
# NOTE (2026): these were previously reimplemented from scratch here, in
# export.py, and in dashboard.py, with a stray comment claiming this file
# "re-exports" them from dashboard.py (it never did). The typography DEFAULTS
# are now deduplicated -- _default_text_style() above is just an alias for
# the single canonical dict in chart_settings.default_text_style(), so all
# three call sites always agree on default font/size/colour values.
#
# _apply_axes / _apply_legend_names themselves are still kept as separate
# local copies in chart_card.py, dashboard.py, and export.py, because their
# behaviour has quietly diverged over time (e.g. dashboard.py's version logs
# failures and supports an `_inplace` flag; export.py's version has slightly
# different empty-legend-title handling for HTML report generation). Merging
# those three into one shared function is a real improvement but needs a
# human to confirm which behaviour is "correct" for each call site and to
# test chart rendering + report export before/after -- flagging this instead
# of guessing, to avoid silently changing report/chart output.
# ---------------------------------------------------------------------------
def _apply_axes(fig, x_lbl, y_lbl, text_style: dict | None = None, *, _inplace: bool = False):
    """Apply axis labels + tick fonts.  Kept here so chart_card is self-contained."""
    try:
        f2 = fig if _inplace else copy.deepcopy(fig)
        style = _default_text_style()
        if isinstance(text_style, dict):
            for _k, _v in text_style.items():
                if _v not in (None, ""):
                    style[_k] = _v
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
    except Exception:
        return fig


def _apply_legend_names(fig, legend_names: dict, legend_title: str = "",
                       text_style: dict | None = None, *, _inplace: bool = False):
    """Rename Plotly traces using the {original_name: custom_name} mapping."""
    try:
        f2 = fig if _inplace else copy.deepcopy(fig)
        style = _default_text_style()
        if isinstance(text_style, dict):
            for _k, _v in text_style.items():
                if _v not in (None, ""):
                    style[_k] = _v
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
        if legend_title is not None:
            f2.update_layout(
                legend_title_text=legend_title,
                legend=dict(font=legend_font, title=dict(font=legend_title_font)),
            )
        return f2
    except Exception:
        return fig


# ---------------------------------------------------------------------------
# Display-figure cache helper (Phase 2: shared, memoized)
# ---------------------------------------------------------------------------
from modules.ui.chart_settings import (
    apply_chart_display_options,
    compute_meta_hash,
    _apply_font_only,
    _font_only_hash,
)


import hashlib


def _fig_signature(fig) -> str:
    """Return a fast, content-aware signature for a Plotly figure.

    The md5 of the figure's JSON is deterministic for a given figure state and
    changes automatically when the figure is regenerated.  This is used as part
    of the display-figure cache key so that changing the *base* figure (e.g.
    after Edit Chart → Apply Changes) immediately busts the cache even when
    the display meta (title, labels, palette …) is unchanged.
    """
    try:
        j = fig.to_json()
        return hashlib.md5(j.encode("utf-8", "ignore")).hexdigest()[:16]
    except Exception:
        return str(id(fig))


def get_display_fig(uid: str, base_fig, meta: dict, chart_type: str, *,
                    force: bool = False,
                    matrix_view: str = ""):
    """Return the *display-ready* figure, recomputed only when meta or base_fig changes.

    Cache key combines ``compute_meta_hash(meta)`` with a figure signature.
    Figure signature is cached by object identity to avoid expensive repeated
    ``fig.to_json()`` calls on every fragment rerun.

    Cache keys live in ``st.session_state`` so they survive fragment reruns.
    """
    cache_key   = f"_display_fig_{uid}"
    hash_key    = f"_display_fig_hash_{uid}"
    sig_key     = f"_display_fig_sig_{uid}"
    obj_id_key  = f"_display_fig_objid_{uid}"
    font_hash_key = f"_display_fig_font_hash_{uid}"

    # Cache figure signature by object identity to avoid repeated to_json()
    current_obj_id = id(base_fig)
    cached_obj_id  = st.session_state.get(obj_id_key)
    if cached_obj_id == current_obj_id:
        fig_sig = st.session_state.get(sig_key, "")
    else:
        fig_sig = _fig_signature(base_fig)
        st.session_state[sig_key]    = fig_sig
        st.session_state[obj_id_key] = current_obj_id

    cache_hash  = compute_meta_hash(meta) + "|" + fig_sig

    if not force and st.session_state.get(hash_key) == cache_hash:
        return st.session_state.get(cache_key, base_fig)

    # Fast path: if only fonts changed, use lightweight font-only updater
    # instead of expensive full apply_chart_display_options() with deepcopy
    meta_hash = compute_meta_hash(meta)
    font_hash = _font_only_hash(meta)
    cached_font_hash = st.session_state.get(font_hash_key)
    
    if (not force and 
        cached_font_hash is not None and 
        cached_font_hash != font_hash and
        st.session_state.get(f"_display_fig_full_hash_{uid}") == meta_hash):
        # Only fonts changed - use fast path
        fig = _apply_font_only(base_fig, meta, chart_type)
        st.session_state[cache_key] = fig
        st.session_state[hash_key]  = cache_hash
        st.session_state[font_hash_key] = font_hash
        return fig

    # Full update needed
    fig = apply_chart_display_options(base_fig, meta, chart_type, _inplace=False, matrix_view=matrix_view)
    st.session_state[cache_key] = fig
    st.session_state[hash_key]  = cache_hash
    st.session_state[f"_display_fig_full_hash_{uid}"] = meta_hash
    st.session_state[font_hash_key] = font_hash
    return fig


# ---------------------------------------------------------------------------
# Main renderer -- this is the @st.fragment
# ---------------------------------------------------------------------------
@st.fragment(run_every=None)  # manual reruns only -- no polling
def render_chart_card(uid: str, title: str, fig, chart_type: str,
                      meta: dict,
                      *, key_prefix: str, edit_mode: bool,
                      viewing_saved: bool = False,
                      on_meta_changed=None) -> None:
    """Render a single chart card inside an isolated Streamlit fragment.

    Parameters
    ----------
    uid / title / fig / chart_type / meta:
        Standard chart identity and content.
    key_prefix:
        "analysis" or "dash_typo" to avoid widget-key collisions when the same
        chart appears on multiple pages.
    edit_mode / viewing_saved:
        Flags controlling which controls to show.
    on_meta_changed:
        Optional callback(uid, changed_key, new_value) the parent uses to
        persist/notebook the change without re-entering the fragment.

    UI layout
    ---------
    * Top bar:  Edit button | Delete button (title rendered inside Plotly).
    * Two-column body:
        - Left  (1/3): Chart Settings expander + Typography expander.
        - Right (2/3): plotly_chart + notes text_area.
    Every widget gets a stable `key` derived from uid so Streamlit's diff engine
    can recognise it across fragment reruns.
    """
    from modules.ui.chart_settings import (
        render_chart_settings_controls,
        render_typography_controls,
        resolve_font_stack,
    )

    # ------------------------------------------------------------------ #
    # Resolve title display + typography
    # ------------------------------------------------------------------ #
    # FIX: Read the title from the widget's session-state key so that typing
    # in the Chart Settings title field is reflected immediately in the
    # preview above the chart on the same fragment rerun.  The ``meta``
    # parameter is captured at fragment-entry and is stale by the time the
    # settings expander updates session_state later in this run.
    _w_title = st.session_state.get(f"{key_prefix}_title_{uid}")
    display_title = _w_title if _w_title is not None else (meta.get("custom_title") or title)
    text_style = meta.get("text_style") or {}

    # Read typography widget values from session_state (set by render_typography_controls).
    # The font-family values from the widget are raw names (e.g. "Georgia"), so we
    # resolve them to CSS font stacks (with fallbacks) via resolve_font_stack.
    _hdr_size   = int(st.session_state.get(f"{key_prefix}_hsize_{uid}",
                     text_style.get("header_size", 28)))
    _hdr_color  = str(st.session_state.get(f"{key_prefix}_hcolor_{uid}",
                     text_style.get("header_color", "#6163df")))
    _hdr_family_raw = str(st.session_state.get(f"{key_prefix}_hfont_{uid}",
                         text_style.get("header_family", "Inter")))
    _hdr_family = resolve_font_stack(_hdr_family_raw) if _hdr_family_raw else "Inter, system-ui, sans-serif"
    _hdr_style  = str(st.session_state.get(f"{key_prefix}_hfont_style_{uid}",
                     text_style.get("header_font_style", "Normal"))).lower()

    # Resolve HTML-safe style
    _hdr_weight = "700" if "bold" in _hdr_style else "400"
    _hdr_italic = "italic" if "italic" in _hdr_style else "normal"
    _hdr_decor  = "underline" if "underline" in _hdr_style else "none"

    # ------------------------------------------------------------------ #
    # Top control bar: title preview (left) + Edit / Delete buttons (right)
    # ------------------------------------------------------------------ #
    ctrl = st.columns([9, 2, 1])
    with ctrl[0]:
        # HTML title preview — uses typography controls for style.
        # _hdr_family is already a CSS font stack (e.g. "Georgia, serif"),
        # so it must NOT be wrapped in extra quotes.
        st.markdown(
            f'<div style="font-size:{_hdr_size}px;font-weight:{_hdr_weight};'
            f'font-style:{_hdr_italic};text-decoration:{_hdr_decor};'
            f'color:{_hdr_color};font-family:{_hdr_family};'
            f'margin-bottom:0.1rem;">{html.escape(str(display_title))}</div>',
            unsafe_allow_html=True,
        )
    with ctrl[1]:
        # Show Edit button whenever we are NOT in read-only (viewing_saved) mode
        # and the chart type supports regeneration.
        if not viewing_saved and chart_type and chart_type not in ("descriptive", "data_quality"):
            df_available = st.session_state.get("df") is not None
            if df_available:
                if st.button("🔄 Edit Chart", key=f"regen_btn_{key_prefix}_{uid}",
                             use_container_width=True,
                             help="Re-run this chart with new columns / settings"):
                    st.session_state._regen_uid  = uid
                    st.session_state._regen_type = chart_type
                    st.session_state["_regen_restore"] = True
                    st.session_state.page = "analysis"
                    # We are inside an @st.fragment; a plain st.rerun() would
                    # only rerun *this fragment*, leaving the parent page
                    # (page_analysis / page_dashboard) ignorant of _regen_uid
                    # and never rendering the regenerate panel.  scope="app"
                    # is required to make the app router re-enter the page.
                    st.rerun(scope="app")
            else:
                st.button("🔄 Edit Chart", key=f"regen_btn_{key_prefix}_{uid}",
                          use_container_width=True, disabled=True,
                          help="Upload the original dataset first to regenerate this chart")
    with ctrl[2]:
        if st.button("✕", key=f"del_{uid}", help="Remove this chart"):
            st.session_state[f"_delete_requested_{uid}"] = True
            # _delete_requested_ is consumed by the parent render loop which
            # runs on a full page rerun.  scope="app" ensures the parent code
            # (page_analysis or page_dashboard) actually executes.
            st.rerun(scope="app")

    # ------------------------------------------------------------------ #
    # Two-column body: settings LEFT | chart RIGHT
    # ------------------------------------------------------------------ #
    settings_col, chart_col = st.columns([1, 3])

    # ---- LEFT: settings expanders -------------------------------------- #
    with settings_col:
        if not viewing_saved:
            st.caption(
                "✨ **Live Preview** — changes appear instantly on the chart →",
                unsafe_allow_html=False,
            )
            _stype = chart_type
            _meta_view = meta.get("_matrix_view", "") or getattr(
                fig, "_lytrize_meta", {}
            ).get("matrix_view", "")

            # Chart Settings + Typography (merged into one expander with tabs
            # to minimise vertical space — the single biggest compactness win)
            with st.expander("⚙️ Chart Settings", expanded=False):
                _set_tab, _typo_tab = st.tabs(["Layout", "Typography"])
                with _set_tab:
                    updates = render_chart_settings_controls(
                        uid, title, fig, _stype, meta,
                        key_prefix=key_prefix,
                        show_text_style=False,
                        matrix_view=_meta_view,
                    )
                    # Persist any changed meta keys via callback
                    if on_meta_changed:
                        for _ckey, _cval in updates.items():
                            on_meta_changed(uid, _ckey, _cval)

                with _typo_tab:
                    # Re-read meta so we see any Chart Settings updates from
                    # this run, then merge typography updates onto the existing
                    # text_style so keys from other tabs are never dropped.
                    from modules.ui.font_manager import inject_font_preview_css
                    inject_font_preview_css()  # session-guarded; idempotent
                    _meta_for_typo = st.session_state.get(f"chart_meta_{uid}", meta)
                    text_updates = render_typography_controls(
                        uid, fig, _stype, _meta_for_typo, key_prefix=key_prefix,
                    )
                    if on_meta_changed and text_updates:
                        _merged = dict(_meta_for_typo.get("text_style", {}))
                        _merged.update(text_updates)
                        on_meta_changed(uid, "text_style", _merged)

    # ---- RIGHT: figure render + insights + notes ---------------------- #
    with chart_col:
        # Re-read meta in case settings above mutated it
        meta = st.session_state.get(f"chart_meta_{uid}", meta)

        # Use the shared memoized cache: only rebuild if meta actually changed
        fig_show = get_display_fig(uid, fig, meta, chart_type, matrix_view=_meta_view)

        # Axis post-processing that depends on the *display* meta
        _ctype_now = st.session_state.get(f"chart_type_{uid}", chart_type)
        _is_table = _ctype_now == "matrix_table"

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
            key=f"plotly_{key_prefix}_{uid}",
            config={
                "responsive": True,
                "displayModeBar": "hover",
                "mathjax": False,
            },
        )

        if _is_table:
            st.markdown("</div>", unsafe_allow_html=True)

        # Notes --------------------------------------------------------------
        note_key = f"desc_{uid}"
        if note_key not in st.session_state:
            st.session_state[note_key] = (
                st.session_state.get("_notes_shadow", {}).get(uid, "")
            )

        def _sync_note(_u=uid):
            val = st.session_state.get(f"desc_{_u}", "")
            st.session_state.setdefault("_notes_shadow", {})[_u] = val

        st.text_area(
            "✍️ Analysis Notes (auto-saved to Dashboard)",
            key=note_key,
            on_change=_sync_note,
            args=(uid,),
            placeholder="Add your findings or observations here…",
        )