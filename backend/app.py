"""app.py -- Lytrize Desktop application entry point."""
import logging


import warnings
import json
import os


warnings.filterwarnings("ignore", category=DeprecationWarning)


try:
    import plotly.io as _pio
    _pio.renderers.default = "browser"
    _pio.config.mathjax = None
except (AttributeError, Exception):
    pass

try:
    import plotly.offline as _poff
    _poff._DEFAULT_INCLUDE_PLOTLYJS = "inline"
except Exception as exc:
    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
    pass


import streamlit as st


st.set_page_config(
    page_title="Lytrize",
    page_icon="assets/lytrize.ico",
    layout="wide",
    initial_sidebar_state="collapsed",
)


from modules.database              import init_db, get_draft, get_or_create_local_user
from modules.ui.css                import inject_css
from modules.pages.auth            import page_profile
from modules.pages.home            import page_home
from modules.pages.upload          import page_upload
from modules.pages.analysis        import page_analysis
from modules.pages.dashboard       import page_dashboard
from modules.utils.session_cache   import save_df_snapshot, load_df_snapshot, set_df




@st.cache_resource(show_spinner=False)
def _init_db_once():
    """Initialise the local SQLite database. Runs exactly once per process."""
    init_db()




def _restore_draft(user_id: int) -> None:
    """Reload an in-progress analysis session from the local DB into session_state."""
    import plotly.io as pio


    draft = get_draft(user_id)
    if not draft:
        return


    st.session_state.file_name       = draft.get("file_name", "")
    st.session_state.dashboard_title = draft.get("dashboard_title", "")
    st.session_state.layout_mode     = draft.get("layout_mode", "portrait")


    try:
        st.session_state.kpis = json.loads(draft.get("kpis_json", "[]"))
    except Exception:
        st.session_state.kpis = []


    if draft.get("editing_session_id"):
        st.session_state.editing_session_id   = draft["editing_session_id"]
        st.session_state.editing_session_name = draft.get("editing_session_name", "")
        st.session_state.editing_file_name   = draft.get("editing_file_name", "")


    try:
        charts_raw = json.loads(draft.get("charts_json", "[]"))
        # Store raw chart data for lazy deserialization — figures are only
        # parsed from JSON when first accessed, avoiding the cost of
        # deserializing every chart on every startup.
        st.session_state["_draft_charts_raw"] = charts_raw
        charts = []
        for item in charts_raw:
            uid      = item.get("uid", "")
            title    = item.get("title", "")
            fig_json = item.get("fig_json", "")
            try:
                fig = pio.from_json(fig_json)
                charts.append((uid, title, fig))
                st.session_state[f"desc_{uid}"]          = item.get("desc", "")
                st.session_state[f"chart_type_{uid}"]    = item.get("chart_type", "")
                st.session_state[f"chart_meta_{uid}"]    = item.get("meta", {})
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass
        if charts:
            st.session_state.charts = charts
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass


    try:
        meta_map = json.loads(draft.get("chart_meta_json", "{}"))
        current_chart_uids = {c[0] for c in st.session_state.get("charts", [])}
        for k, v in meta_map.items():
            if k.startswith("chart_meta_"):
                uid = k[11:]
                if uid in current_chart_uids:
                    existing = st.session_state.get(k, {})
                    if isinstance(existing, dict) and isinstance(v, dict):
                        existing.update(v)
                        st.session_state[k] = existing
                    elif k not in st.session_state:
                        st.session_state[k] = v
            elif k not in st.session_state:
                st.session_state[k] = v
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass


    df = load_df_snapshot(user_id)
    if df is not None:
        set_df(df)


    # Always start at the home page on restart — the user navigates to
    # analysis/dashboard manually.  The draft is cleared after restore so
    # the next restart starts fresh instead of re-entering the last session.
    from modules.database import clear_draft
    clear_draft(user_id)


def main() -> None:
    _init_db_once()
    inject_css()


    url_page       = st.query_params.get("p", "")
    url_session_id = st.query_params.get("sid", "")
    url_nav        = st.query_params.get("nav", "")


    if "user_id" not in st.session_state:
        local_user = get_or_create_local_user()
        if local_user["id"] is None:
            st.info("⏳ Setting up your workspace… please wait.", icon="🔧")
            st.rerun()
        st.session_state.user_id  = local_user["id"]
        st.session_state.username = local_user["username"]
        _restore_draft(local_user["id"])


    if "page" not in st.session_state:
        restore_page = st.session_state.pop("_restore_to_page", None)
        st.session_state.page = restore_page if restore_page else "home"


    if "user_id" in st.session_state and url_nav == "home":
        for k in [
            "view_session_id", "_view_charts", "_vsid", "_view_session_meta",
            "_view_session_id_loaded", "dashboard_title", "kpis", "layout_mode",
        ]:
            st.session_state.pop(k, None)
        st.session_state.page = "home"
        st.query_params.pop("nav", None)


    st.query_params["p"] = st.session_state.page
    if st.session_state.get("view_session_id"):
        st.query_params["sid"] = st.session_state.view_session_id
    else:
        st.query_params.pop("sid", None)


    if "_current_rendered_page" not in st.session_state:
        st.session_state["_current_rendered_page"] = st.session_state.page
        st.session_state["_last_page_navigated_from"] = None
    elif st.session_state["_current_rendered_page"] != st.session_state.page:
        st.session_state["_last_page_navigated_from"] = st.session_state["_current_rendered_page"]
        st.session_state["_current_rendered_page"] = st.session_state.page


    current_page = st.session_state.page
    p = current_page
    if   p == "home":      page_home()
    elif p == "upload":    page_upload()
    elif p == "analysis":  page_analysis()
    elif p == "dashboard": page_dashboard()
    elif p == "profile":   page_profile()
    else:
        st.session_state.page = "home"
        st.rerun()




if __name__ == "__main__":
    main()