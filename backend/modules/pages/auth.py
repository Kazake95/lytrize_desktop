"""
modules/pages/auth.py — .

This page keeps the independent backup/restore experience and guest-mode
information.
"""

import datetime
import json
import os
import pathlib
import streamlit as st

from modules.database import export_sessions_to_dict, import_sessions_from_dict, get_or_create_guest_user
from modules.ui.css import APP_NAME, inject_footer, render_logo


def _db_path() -> str:
    _default = str(pathlib.Path.home() / ".local" / "share" / "lytrize" / "lytrize.db")
    return os.environ.get("LYTRIZE_DB_PATH") or _default


def page_profile() -> None:
    """Render the guest profile page with backup and restore."""
    render_logo()

    if "user_id" not in st.session_state:
        guest = get_or_create_guest_user()
        st.session_state.user_id = guest.get("id")
        st.session_state.username = guest.get("username")
        st.session_state.is_guest = True


    if st.button("← Home"):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("---")

    st.markdown(
        "<div style='padding:1rem;border-radius:1rem;"
        "background:rgba(15,23,42,0.04);margin-bottom:1rem;'>"
        "<strong>Your work stays on this machine and is stored in the local Lytrize database.</strong>"
        "</div>",
        unsafe_allow_html=True,
    )

    st.markdown('<div class="sec-label">💾 Backup</div>', unsafe_allow_html=True)
    backup_card = """
<div style="background:linear-gradient(160deg,var(--surface-1),var(--surface-2));border:1px solid var(--border-subtle);border-radius:1.2rem;padding:1.25rem;margin-bottom:1rem;">
  <div style="font-weight:700;margin-bottom:0.5rem;">Export your saved sessions as a portable JSON file.</div>
  <div style="opacity:.78;font-size:0.95rem;margin-bottom:1rem;">Saves session metadata and charts. Does NOT include original CSV/Excel files.</div>
</div>
"""
    st.markdown(backup_card, unsafe_allow_html=True)
    uid = st.session_state.get("user_id")

    if st.button("📦 Prepare Backup", key="btn_backup"):
        sessions = export_sessions_to_dict(uid, username=st.session_state.get("username", "guest"), local_db_path=_db_path())
        if not sessions:
            st.warning("No saved sessions found to back up.")
        else:
            st.session_state["_backup_sessions"] = sessions

    if "_backup_sessions" in st.session_state:
        sessions = st.session_state["_backup_sessions"]
        st.markdown(f"**{len(sessions)} session(s) found.** Select which to include:")
        selected = []
        for s in sessions:
            sname = s.get("name", s.get("session_name", "Unnamed"))
            if st.checkbox(sname, value=True, key=f"bk_sel_{s.get('id', sname)}"):
                selected.append(s)
        if selected:
            payload = {
                "lytrize_backup": True,
                "version": "1.1",
                "username": st.session_state.get("username", "guest"),
                "exported_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                "sessions": selected,
            }
            data = json.dumps(payload, indent=2, default=str).encode("utf-8")
            ts = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%d_%H%M%S")
            st.download_button(
                label=f"⬇️ Save {len(selected)} session(s)",
                data=data,
                file_name=f"lytrize_backup_{ts}.json",
                mime="application/json",
            )
        else:
            st.info("Select at least one session to download.")

    st.markdown("---")
    st.markdown('<div class="sec-label">📥 Restore</div>', unsafe_allow_html=True)
    restore_card = """
<div style="background:linear-gradient(160deg,var(--surface-1),var(--surface-2));border:1px solid var(--border-subtle);border-radius:1.2rem;padding:1.25rem;margin-bottom:1rem;">
  <div style="font-weight:700;margin-bottom:0.5rem;">Import sessions from a Lytrize backup file.</div>
</div>
"""
    st.markdown(restore_card, unsafe_allow_html=True)
    uploaded = st.file_uploader("Upload backup file (.json)", type=["json"], key="backup_upload")
    if uploaded is not None:
        try:
            raw = uploaded.read()
            payload = json.loads(raw.decode("utf-8"))
            if not payload.get("lytrize_backup"):
                st.error("This does not look like a Lytrize backup file.")
            else:
                to_import = payload.get("sessions", [])
                st.info(f"Found **{len(to_import)}** session(s) in backup.")
                if st.button("📥 Import Sessions", key="btn_restore", type="primary"):
                    import_sessions_from_dict(st.session_state.get("user_id"), to_import)
                    st.success("Import complete.")
                    st.session_state.page = "home"
                    st.rerun()
        except Exception as e:
            st.error(f"Could not read backup file: {e}")

    inject_footer()
