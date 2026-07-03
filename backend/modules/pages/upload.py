"""modules/pages/upload.py -- File upload and column classification page."""


import streamlit as st
import pandas as pd
from html import escape


from modules.ui.column_manager import show_column_manager
from modules.ui.column_tools   import show_dtype_transformer, show_column_classifier
from modules.ui.data_cleaner   import show_data_cleaner
from modules.ui.excel_loader   import show_excel_loader
from modules.ui.css            import inject_footer, render_logo
from modules.utils.perf        import read_csv_fast, mem_mb
from modules.analysis.data_quality import run_data_quality
from modules.analysis.outlier import run_outlier_upload




def _is_excel(name: str) -> bool:
    """Return True when the filename has an Excel extension."""
    return name.lower().endswith((".xlsx", ".xls"))




def _uploaded_signature(uploaded) -> str:
    """Return a stable string that uniquely identifies this upload within a session."""
    import hashlib


    file_id = getattr(uploaded, "file_id", None)
    size    = getattr(uploaded, "size", 0) or 0


    if file_id:
        return f"{uploaded.name}:{size}:{file_id}"


    content_suffix = ""
    if size > 0 and size < 10_000_000:
        try:
            uploaded.seek(0)
            head = uploaded.read(65536)
            uploaded.seek(max(0, size - 65536))
            tail = uploaded.read(65536)
            content_hash = hashlib.md5(head + tail).hexdigest()[:12]
            content_suffix = f":{content_hash}"
        except Exception:
            pass
        finally:
            uploaded.seek(0)


    return f"{uploaded.name}:{size}{content_suffix}"




@st.cache_resource(show_spinner=False, max_entries=1)
def _read_csv_cached(file_sig: str, _uploaded_file) -> pd.DataFrame:
    """Parse and dtype-optimise a CSV file."""
    import io
    _uploaded_file.seek(0)
    file_bytes = _uploaded_file.read()
    return read_csv_fast(io.BytesIO(file_bytes))




def page_upload():
    render_logo()


    st.session_state["_last_viewed_page"] = "upload"




    if st.button("← Home"):
        st.session_state.page = "home"
        st.session_state.pop("_last_viewed_page", None)
        st.session_state.pop("_resume_upload", None)
        st.rerun()


    st.markdown("## 📂 Upload Dataset")


    if "editing_session_id" in st.session_state:
        fname = st.session_state.get("editing_file_name", "the original file")
        if st.session_state.get("_edit_needs_reupload"):
            st.session_state.pop("_edit_needs_reupload", None)
            st.warning(
                f"✏️ **Editing session: \"{st.session_state.get('editing_session_name', '')}\"**\n\n"
                f"The original dataset (**{fname}**) needs to be re-uploaded to add or "
                f"modify charts. Your existing charts and settings are preserved — "
                f"just upload the same file and you'll be taken straight to the analysis.",
                icon="⚠️",
            )
        else:
            st.info(
                f"✏️ **Edit mode** — Remember to re-upload the same file **{fname}** to add more charts to the saved session."
            )


    uploaded = st.file_uploader(
        "CSV or Excel (single or multi-sheet) — up to 400 MB",
        type=["csv", "xlsx"],
        key="main_file_uploader",
    )


    if (not uploaded) and ("df" in st.session_state) and st.session_state.get("df") is not None:
        _resumed_name = st.session_state.get("file_name") or "your dataset"
        

        if st.session_state.get("_resume_upload") or st.session_state.get("_last_viewed_page") == "upload":
            _show_analysis_pipeline(st.session_state["df"], _resumed_name)
            inject_footer()
            return


        st.info(
            f"📂 **{_resumed_name}** is still loaded from your last session. "
            "You can continue cleaning and transforming, or upload a new file above to replace it.",
            icon=None,
        )
        _col_resume, _col_clear = st.columns([2, 1])
        with _col_resume:
            if st.button("▶ Continue with current dataset", key="_resume_dataset",
                         type="primary", use_container_width=True):
                st.session_state["_resume_upload"] = True
                st.rerun()
        with _col_clear:
            if st.button("🗑 Start fresh (clear dataset)", key="_clear_dataset",
                         use_container_width=True):
                for k in ["df", "file_name", "file_signature", "_dq_charts", "_dq_sig",
                          "_ul_preview_mode", "_resume_upload", "_df_snapshot_sig", "_last_draft_upload_cache"]:
                    st.session_state.pop(k, None)
                st.rerun()
        inject_footer()
        return


    if not uploaded:
        inject_footer()
        return


    is_excel     = _is_excel(uploaded.name)
    file_sig     = _uploaded_signature(uploaded)
    file_changed = (
        st.session_state.get("file_name")      != uploaded.name or
        st.session_state.get("file_signature") != file_sig
    )
    st.session_state.pop("_resume_upload", None)


    if not is_excel:
        if "df" not in st.session_state or file_changed:
            with st.spinner("Reading and optimising file…"):
                df = _read_csv_cached(file_sig, uploaded)
            st.session_state.df             = df
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig
            st.session_state["_resume_upload"] = True
            _clear_excel_state()
            mb = mem_mb(df)
            if mb > 50:
                st.caption(f"📊 Loaded {df.shape[0]:,} rows — memory footprint: {mb:.0f} MB")
        else:
            df = st.session_state.df
        _show_analysis_pipeline(df, uploaded.name)
    else:
        if file_changed:
            st.session_state.pop("df", None)
            _clear_excel_state(uploaded.name)
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig


        if "df" not in st.session_state:
            df = show_excel_loader(uploaded)
            if df is not None:
                st.session_state.df = df
                st.session_state["_resume_upload"] = True
                st.rerun()
        else:
            if st.button("⚙️ Edit Excel Configuration", key="_xl_edit_config"):
                st.session_state.pop("df", None)
                st.rerun()
            _show_analysis_pipeline(st.session_state.df, uploaded.name)




def _save_upload_snapshot(df, file_name: str) -> None:
    """Persist df parquet + minimal draft immediately after upload if modified."""
    uid = st.session_state.get("user_id")
    if not uid:
        return
    try:
        df_sig = (id(df), df.shape, tuple(df.columns))
        sig_changed = st.session_state.get("_df_snapshot_sig") != df_sig
        

        draft_cache_key = ("_draft_upload_cache", file_name, df_sig)
        if st.session_state.get("_last_draft_upload_cache") != draft_cache_key or sig_changed:
            from modules.utils.session_cache import save_df_snapshot
            from modules.database import save_draft
            import json as _json
            import threading
            

            if sig_changed:
                threading.Thread(
                    target=save_df_snapshot,
                    args=(uid,),
                    daemon=True
                ).start()
                st.session_state["_df_snapshot_sig"] = df_sig
                

            save_draft(
                user_id               = uid,
                page                  = "upload",
                charts_json           = "[]",
                file_name             = file_name,
                col_descriptions_json = _json.dumps(
                    st.session_state.get("col_descriptions", {})
                ),
            )
            st.session_state["_last_draft_upload_cache"] = draft_cache_key
    except Exception:
        pass




def _show_analysis_pipeline(df: pd.DataFrame, file_name: str):
    _save_upload_snapshot(df, file_name)
    st.markdown("---")
    _n_rows = df.shape[0]
    _n_cols = df.shape[1]
    st.success(f"✅ **{file_name}** — {_n_rows:,} rows × {_n_cols} columns")


    with st.expander("📋 Data Preview", expanded=True):
        _pb1, _pb2, _pb3, _pb4 = st.columns([1, 1, 1, 4])
        with _pb1:
            if st.button("⬆ Top 10",    key="ul_prev_top",  use_container_width=True):
                st.session_state["_ul_preview_mode"] = "top"
        with _pb2:
            if st.button("⬇ Bottom 10", key="ul_prev_bot",  use_container_width=True):
                st.session_state["_ul_preview_mode"] = "bottom"
        with _pb3:
            if st.button("🎲 Random",   key="ul_prev_rand", use_container_width=True):
                st.session_state["_ul_preview_mode"] = "random"
                st.session_state["_ul_random_seed"] = (
                    st.session_state.get("_ul_random_seed", 0) + 1
                )
        with _pb4:
            _num_c = len(df.select_dtypes("number").columns)
            _cat_c = len(df.select_dtypes("object").columns)
            _dt_c  = len(df.select_dtypes("datetime").columns)
            _null  = round(df.isnull().sum().sum() / max(df.size, 1) * 100, 1)
            st.caption(
                f"🔢 {_num_c} numeric  ·  🔤 {_cat_c} text  ·  "
                f"📅 {_dt_c} datetime  ·  ⚠️ {_null}% missing"
            )


        _ul_mode = st.session_state.get("_ul_preview_mode", "top")
        _ul_rand_seed = st.session_state.get("_ul_random_seed", 0) if _ul_mode == "random" else 0
        _cache_key = ("ul_preview", _n_rows, _n_cols, _ul_mode, _ul_rand_seed)
        if st.session_state.get("_ul_preview_cache_key") != _cache_key:
            try:
                if _ul_mode == "bottom":
                    _prev_df = df.tail(10)
                    _lbl = "Bottom 10 rows"
                elif _ul_mode == "random":
                    _prev_df = df.sample(min(10, _n_rows), random_state=None)
                    _lbl = "10 random rows"
                else:
                    _prev_df = df.head(10)
                    _lbl = "Top 10 rows"
            except Exception:
                _prev_df = df.head(10)
                _lbl = "Top 10 rows"
            st.session_state["_ul_preview_cache"] = (_prev_df, _lbl)
            st.session_state["_ul_preview_cache_key"] = _cache_key
        else:
            _prev_df, _lbl = st.session_state.get("_ul_preview_cache", (df.head(10), "Top 10 rows"))


        st.caption(f"*{_lbl}*")
        st.dataframe(_prev_df, use_container_width=True, height=min(380, 38 + len(_prev_df) * 35))


    with st.expander("📖 Describe Your Columns (optional)", expanded=False):
        st.markdown("Describe what each column means for better auto-insights.")
        col_descs = st.session_state.get("col_descriptions", {})
        for col in df.columns:
            col_descs[col] = st.text_input(
                f"`{col}`",
                value=col_descs.get(col, ""),
                key=f"coldesc_{col}",
                placeholder="e.g. 'Total revenue in USD'",
            )
        if st.button("💾 Save Column Descriptions", key="save_col_descs"):
            st.session_state.col_descriptions = col_descs
            st.success("✅ Saved.")


    with st.expander("🧹 Data Quality Summary", expanded=False):
        st.info("Check the box below to run a data quality analysis.")
        if st.checkbox("🔍 Enable Data Quality Diagnostics", key="_enable_dq_run"):
            with st.spinner("Analyzing data quality metrics..."):
                if len(df) > 100_000:
                    st.warning("⚠️ Large dataset detected. Analyzing a representative 100,000-row sample for speed.")
                    dq_df = df.sample(n=100_000, random_state=42)
                else:
                    dq_df = df
                dq_charts = run_data_quality(dq_df)


                if dq_charts:
                    st.markdown("#### Data Quality Summaries")
                    for title, fig in dq_charts:
                        if title == "Duplicate Rows Summary":
                            unique_rows = int(dq_df.drop_duplicates().shape[0])
                            duplicate_rows = len(dq_df) - unique_rows
                            st.markdown(
                                f"**Duplicate rows:** {duplicate_rows:,} duplicate row(s) / "
                                f"{unique_rows:,} unique row(s)."
                            )
                        else:
                            st.plotly_chart(fig, use_container_width=True)
                else:
                    st.info("No data quality issues were detected.")


    with st.expander("🔍 Outlier Detection", expanded=False):
        st.info("Check the box below to run outlier analysis across numeric columns.")
        if st.checkbox("📊 Enable Outlier Scanners", key="_enable_outlier_run"):
            with st.spinner("Calculating outlier boundaries..."):
                if len(df) > 100_000:
                    st.warning("⚠️ Large dataset detected. Scanning a representative 100,000-row sample for speed.")
                    outlier_df = df.sample(n=100_000, random_state=42)
                else:
                    outlier_df = df
                run_outlier_upload(outlier_df)


    with st.expander("🧩 Column Manager", expanded=False):
        df = show_column_manager(df)


    with st.expander("🔢 Data-type Transformer", expanded=False):
        df = show_dtype_transformer(df)


    with st.expander("🧼 Data Cleaner", expanded=False):
        df = show_data_cleaner(df)


    with st.expander("💾 Save Cleaned Data as CSV", expanded=False):
        st.caption("Download the current (cleaned) dataset as a CSV file.")
        

        if st.checkbox("⚙️ Prepare CSV Download File", key="_enable_csv_export"):
            import io as _io, datetime as _dt


            _csv_col1, _csv_col2 = st.columns([2, 1])
            with _csv_col1:
                _default_name = (
                    st.session_state.get("file_name", "cleaned_data")
                    .replace(".csv", "")
                    .replace(".xlsx", "")
                    .replace(".xls", "")
                )
                _csv_filename = st.text_input(
                    "File name",
                    value=f"{_default_name}_cleaned",
                    placeholder="e.g. my_dataset_cleaned",
                    key="csv_export_filename",
                )
            with _csv_col2:
                all_cols_for_idx = ["None (default integer index)"] + list(df.columns)
                _csv_index_choice = st.selectbox(
                    "Index column (optional)",
                    options=all_cols_for_idx,
                    index=0,
                    key="csv_export_index",
                )


            _fname = (_csv_filename.strip() or "cleaned_data").rstrip(".csv") + ".csv"
            _use_col_as_idx = (
                _csv_index_choice
                if _csv_index_choice != "None (default integer index)"
                else None
            )


            with st.spinner("Generating export file (this can take a moment for large datasets)..."):
                _export_df = df.set_index(_use_col_as_idx) if _use_col_as_idx else df
                _csv_bytes = _export_df.to_csv(index=bool(_use_col_as_idx)).encode("utf-8")


            st.download_button(
                label="⬇️ Download",
                data=_csv_bytes,
                file_name=_fname,
                mime="text/csv",
                key="csv_export_download_btn",
                use_container_width=True,
            )
            st.caption(
                f"📊 {len(df):,} rows × {len(df.columns)} columns — "
                f"{len(_csv_bytes)/1024/1024:.1f} MB"
            )
        else:
            st.info("Check the box above to generate the download link for your dataset.")


    with st.expander("🧠 Classify Columns & Proceed to Analysis", expanded=False):
        show_column_classifier(df)




def _clear_excel_state(new_file_name: str = "") -> None:
    keys_to_delete = [
        k for k in list(st.session_state.keys())
        if k.startswith("_xl_sheets_") and (
            not new_file_name or new_file_name not in k
        )
    ]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state.pop("_unified_table_info", None)
