"""modules/analysis/descriptive.py -- Descriptive statistics table runner."""


import streamlit as st
from modules.charts import num_cols as _num_cols




def run_descriptive(df):
    """Render a descriptive statistics table for all numeric columns."""
    num = _num_cols()
    if not num:
        st.warning("No numeric columns found. Check your column classification on the upload page.")
        return []

    # Cache the describe() result by _df_version + column list so it only
    # recomputes when the DataFrame actually changes.  For large files
    # (>100K rows), describe() on the full frame is very expensive.
    _df_ver = st.session_state.get("_df_version", 0)
    _desc_key = "_desc_stats_cache"
    _desc_ver_key = "_desc_stats_cache_ver"
    _cols_key = tuple(num)
    _cache_sig = (_df_ver, _cols_key)

    if st.session_state.get(_desc_ver_key) != _cache_sig or _desc_key not in st.session_state:
        # For very large files, describe() on a 100K sample is representative
        # enough for the summary table and avoids scanning 300 MB of data.
        if len(df) > 100_000:
            desc = df[num].sample(min(100_000, len(df)), random_state=42).describe().T.reset_index()
        else:
            desc = df[num].describe().T.reset_index()

        desc.columns = [c.title() if c != "index" else "Column" for c in desc.columns]

        # Round numeric columns — compute the mask once instead of twice
        _num_desc_cols = desc.select_dtypes("number").columns
        desc[_num_desc_cols] = desc[_num_desc_cols].round(4)

        st.session_state[_desc_key] = desc
        st.session_state[_desc_ver_key] = _cache_sig
    else:
        desc = st.session_state[_desc_key]

    st.dataframe(desc, use_container_width=True, hide_index=True)
    return []
