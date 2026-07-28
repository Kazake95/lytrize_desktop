"""modules/analysis/descriptive.py -- Descriptive statistics table runner."""


import streamlit as st
from modules.charts import num_cols as _num_cols




def run_descriptive(df):
    """Render a descriptive statistics table for all numeric columns."""
    num = _num_cols()
    if not num:
        st.warning("No numeric columns found. Check your column classification on the upload page.")
        return []


    desc = df[num].describe().T.reset_index()


    desc.columns = [c.title() if c != "index" else "Column" for c in desc.columns]


    desc[desc.select_dtypes("number").columns] = desc.select_dtypes("number").round(4)


    st.dataframe(desc, use_container_width=True, hide_index=True)
    return []
