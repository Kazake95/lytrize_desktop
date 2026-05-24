"""
modules/pages/home.py -- Home page.

Performance note
----------------
The welcome banner image (~285 KB PNG) is base64-encoded once per process
via _banner_data_uri() and cached with @st.cache_resource. Without caching,
the raw disk read + base64 encoding ran on every Streamlit rerun (every user
interaction on this page). The resource cache pins the encoded string in
memory for the lifetime of the server process, eliminating ~10 ms of I/O
per render with zero functional change.
"""
import base64
import getpass
import json

import streamlit as st
from html import escape
from pathlib import Path

from modules.database import (
    log_activity,
    get_user_sessions, get_session_charts, get_session_meta,
    rename_session_db, delete_session_db,
)
from modules.ui.css import inject_footer, render_logo
from modules.analysis import ANALYSIS_OPTIONS

# ── Image for the right column ────────────────────────────────────────────────
RIGHT_IMAGE_PATH = Path(__file__).resolve().parents[2] / "assets" / "welcome-banner.png"
USE_RIGHT_IMAGE  = True


@st.cache_resource(show_spinner=False)
def _banner_data_uri() -> str:
    """
    Load and base64-encode the welcome banner image exactly once per process.

    @st.cache_resource stores the result in the server process's memory for
    the entire lifetime of the Streamlit server — no re-reads on reruns.
    Returns an empty string if the file is absent or unreadable (the
    <img> element is simply omitted in that case).
    """
    try:
        data = base64.b64encode(RIGHT_IMAGE_PATH.read_bytes()).decode("ascii")
        return f"data:image/png;base64,{data}"
    except Exception:
        return ""


def page_home():
    render_logo()
    is_guest = st.session_state.get("is_guest", False)

    # ── Two-column layout: left = banner + KPIs + button; right = image ───────
    if USE_RIGHT_IMAGE:
        left_col, right_col = st.columns([1, 1], gap="small")
    else:
        left_col, right_col = st.columns([2, 1])
        right_col.empty()

    with left_col:
        # ── Welcome banner ────────────────────────────────────────────────────
        local_user   = getpass.getuser() or "Local user"
        display_name = escape(local_user)

        st.markdown(
            f'<div class="welcome-banner">'
            f'<div style="font-size:0.7rem;font-weight:700;letter-spacing:0.12em;'
            f'text-transform:uppercase;opacity:0.75;margin-bottom:0.35rem;">DASHBOARD OVERVIEW</div>'
            f'<div style="font-size:2rem;font-weight:800;font-family:\'Sora\',sans-serif;'
            f'letter-spacing:-0.03em;margin-bottom:0.35rem;">'
            f'Welcome, {display_name} 👋</div>'
            f'<div style="font-size:0.9rem;opacity:0.88;line-height:1.55;text-align:center;">'
            f'Your data workspace is ready. '
            f'Upload a dataset or pick up where you left off ✌️</div>'
            f'</div>',
            unsafe_allow_html=True,
        )

        # ── KPI cards ─────────────────────────────────────────────────────────
        sessions     = get_user_sessions(st.session_state["user_id"])
        unique_files = len(set(s[2] for s in sessions)) if sessions else 0

        m1, m2, m3 = st.columns(3, gap="medium")
        for col, icon, val, lbl in [
            (m1, "📁", len(sessions),           "Saved Sessions"),
            (m2, "🗂️", unique_files,             "Datasets Analysed"),
            (m3, "🔬", len(ANALYSIS_OPTIONS),   "Available Analyses"),
        ]:
            with col:
                st.markdown(
                    f'<div class="kpi-card">'
                    f'  <div class="kpi-icon">{icon}</div>'
                    f'  <div class="kpi-body">'
                    f'    <div class="kpi-val">{val}</div>'
                    f'    <div class="kpi-lbl">{lbl}</div>'
                    f'  </div></div>',
                    unsafe_allow_html=True,
                )

        st.markdown("<div style='margin-top:0.85rem'></div>", unsafe_allow_html=True)

        # ── Start New Analysis button ──────────────────────────────────────────
        if st.button("🚀 Start New Analysis", type="primary"):
            if not is_guest:
                log_activity(st.session_state["user_id"], "new_analysis_started")
            # Clear all analysis state so the upload page starts fresh.
            for k in ["editing_session_id", "editing_session_name", "editing_file_name",
                      "df", "charts", "selected_analyses", "dashboard_title", "kpis",
                      "layout_mode", "_view_charts", "view_session_id"]:
                st.session_state.pop(k, None)
            st.session_state.page = "upload"
            st.rerun()

    if USE_RIGHT_IMAGE:
        with right_col:
            # _banner_data_uri() is cached — the disk read + base64 encoding
            # happens only once per process, not on every Streamlit rerun.
            uri = _banner_data_uri()
            if uri:
                st.markdown(
                    f'<img src="{uri}" '
                    'style="width:100%;height:auto;border-radius:0.9rem;padding-top:1.5rem;display:block;" '
                    'draggable="false" '
                    'alt="Lytrize welcome illustration">',
                    unsafe_allow_html=True,
                )

    # ── Previous Sessions section ──────────────────────────────────────────────
    st.markdown("---")
    st.markdown('<div class="sec-label">📁 Previous Sessions</div>', unsafe_allow_html=True)

    if not sessions:
        st.info("No saved sessions yet. Start your first analysis above!")
    else:
        for s in sessions[:20]:
            sid, sname, fname, rows, cols, atypes, created = s

            # name | View | Edit | Rename | Delete
            sa, sb, sc, sd, se = st.columns([3, 1, 1, 1, 1])

            with sa:
                st.markdown(
                    f'<div class="sess-card"><b>{escape(str(sname))}</b><br>'
                    f'<span style="opacity:.65;font-size:.8rem;">'
                    f'{escape(str(fname or ""))} &nbsp;· &nbsp; {rows}×{cols}</span></div>',
                    unsafe_allow_html=True,
                )

            with sb:
                if st.button("View", key=f"v_{sid}"):
                    st.session_state.view_session_id = sid
                    st.session_state.page = "dashboard"
                    st.rerun()

            with sc:
                if st.button("✏️ Edit", key=f"e_{sid}", help="Add/modify charts"):
                    # Load saved charts + metadata into live session state so the
                    # user can add/modify charts exactly as in a new analysis.
                    sm     = get_session_meta(sid, st.session_state.get("user_id"))
                    loaded = get_session_charts(sid, st.session_state.get("user_id"))
                    charts = []
                    for uid, title, fig, desc, auto, ctype, meta in loaded:
                        st.session_state[f"desc_{uid}"]          = desc
                        st.session_state[f"auto_insights_{uid}"] = auto
                        st.session_state[f"chart_type_{uid}"]    = ctype
                        st.session_state[f"chart_meta_{uid}"]    = meta
                        charts.append((uid, title, fig))
                    st.session_state.charts               = charts
                    st.session_state.editing_session_id   = sid
                    st.session_state.editing_session_name = sname
                    st.session_state.editing_file_name    = fname
                    st.session_state.file_name            = fname
                    if sm:
                        st.session_state.dashboard_title = sm.get("dashboard_title", "")
                        st.session_state.layout_mode     = sm.get("layout_mode", "portrait")
                        try:
                            st.session_state.kpis = json.loads(sm.get("kpis_json", "[]"))
                        except Exception:
                            st.session_state.kpis = []
                    # Clear stale df: without this the upload page shows a
                    # "continue with current dataset" banner that hides the
                    # re-upload warning for edit mode.
                    st.session_state.pop("df", None)
                    st.session_state.pop("file_signature", None)
                    st.session_state._edit_needs_reupload = True
                    st.session_state.page = "upload"
                    st.rerun()

            with sd:
                if st.button("✏ Rename", key=f"rn_{sid}", help="Rename this session"):
                    st.session_state[f"_renaming_{sid}"] = True
                    st.rerun()

            with se:
                if st.button("🗑️", key=f"d_{sid}", help="Delete session"):
                    st.session_state[f"_confirm_del_{sid}"] = True
                    st.rerun()

            # ── Inline rename form ─────────────────────────────────────────
            if st.session_state.get(f"_renaming_{sid}"):
                new_name = st.text_input(
                    "New session name", value=sname, key=f"rn_input_{sid}"
                )
                rc1, rc2 = st.columns(2)
                with rc1:
                    if st.button("Save name", key=f"rn_save_{sid}", type="primary"):
                        if new_name.strip():
                            rename_session_db(sid, new_name.strip(),
                                              st.session_state.get("user_id"))
                        st.session_state.pop(f"_renaming_{sid}", None)
                        st.rerun()
                with rc2:
                    if st.button("Cancel", key=f"rn_cancel_{sid}"):
                        st.session_state.pop(f"_renaming_{sid}", None)
                        st.rerun()

            # ── Inline delete confirmation ────────────────────────────────
            # BUG NOTE: use get() not pop() here.
            # pop() removes the key on the rerun that *shows* the dialog, so by
            # the time the user clicks "Confirm delete" the key is already gone
            # and the confirmation block never renders. We pop() explicitly only
            # inside each action branch.
            if st.session_state.get(f"_confirm_del_{sid}", False):
                ca, cb = st.columns(2)
                with ca:
                    if st.button("✅ Confirm delete", key=f"cd_{sid}"):
                        st.session_state.pop(f"_confirm_del_{sid}", None)
                        deleted = delete_session_db(sid, st.session_state.get("user_id"))
                        if not deleted:
                            st.error(
                                "Could not delete this session. It may already be gone "
                                "or a backup import left a stale row mapping."
                            )
                        for key in (
                            "editing_session_id", "editing_session_name",
                            "editing_file_name", "view_session_id",
                            "_view_charts", "_view_session_id_loaded",
                        ):
                            st.session_state.pop(key, None)
                        st.session_state.pop("_backup_sessions", None)
                        for key in list(st.session_state.keys()):
                            if key.startswith("bk_sel_"):
                                st.session_state.pop(key, None)
                        st.rerun()
                with cb:
                    if st.button("Cancel", key=f"cx_{sid}"):
                        st.session_state.pop(f"_confirm_del_{sid}", None)
                        st.rerun()

    inject_footer()
