"""
modules/pages/upload.py -- File upload and column classification page.

Performance note
----------------
_uploaded_signature() previously fell back to len(uploaded.getbuffer()) when
file_id was unavailable. getbuffer() copies the entire upload into memory just
to count bytes — unnecessary since Streamlit's UploadedFile always exposes a
.size attribute. The fallback now uses .size directly, capping peak memory use
on the upload path.
"""

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
    """
    Return a stable string that uniquely identifies this upload within a session.

    Used to detect whether the user has replaced the file between reruns so we
    can clear cached state and re-parse the new file.

    Previously the fallback branch called ``uploaded.getbuffer()`` which reads
    the ENTIRE file into memory (a 500 MB CSV allocates 500 MB) solely to count
    bytes. Streamlit's UploadedFile always exposes a ``.size`` attribute, so we
    use that instead — zero extra memory cost.

    Signature components:
      - ``uploaded.name``    : filename (catches a same-size different-file swap)
      - ``uploaded.size``    : byte count from UploadedFile metadata
      - ``uploaded.file_id`` : opaque ID assigned by Streamlit per upload session
                               (present in Streamlit ≥ 1.27; omitted gracefully
                               when absent for compatibility with older builds)
    """
    file_id = getattr(uploaded, "file_id", None)
    size    = getattr(uploaded, "size", 0) or 0   # 'or 0' guards against None
    if file_id:
        # Preferred path: file_id is unique per browser upload event, so
        # name + size + file_id is unambiguous even if the same file is
        # re-uploaded after edits.
        return f"{uploaded.name}:{size}:{file_id}"
    # Fallback (older Streamlit builds without file_id): name + size is a
    # good-enough heuristic for typical desktop BI use — two different CSV
    # files with the same name and the same byte count are extremely rare.
    return f"{uploaded.name}:{size}"


@st.cache_data(show_spinner=False)
def _read_csv_cached(file_bytes: bytes, filename: str) -> pd.DataFrame:
    """
    Parse and dtype-optimise a CSV file, caching the result by raw bytes.

    Streamlit's cache_data hashes `file_bytes` so the same upload content is
    never re-parsed between reruns. The cache is invalidated automatically when
    `file_bytes` changes (i.e. the user uploads a different file).

    Args:
        file_bytes: Raw bytes of the uploaded CSV.
        filename:   Original filename (included in the cache key for safety,
                    in case two different files hash to the same byte sequence).

    Returns:
        Dtype-optimised DataFrame.
    """
    import io
    return read_csv_fast(io.BytesIO(file_bytes))


def page_upload():
    render_logo()

    if st.button("← Home"):
        st.session_state.page = "home"
        st.rerun()

    st.markdown("## 📂 Upload Dataset")

    # if st.session_state.get("is_guest", False):
    #     st.info(
    #         "⚠️ **Guest mode** — sessions are saved locally on this device. "
    #         "Sign in later to sync them to your cloud account.",
    #         icon=None,
    #     )

    if "editing_session_id" in st.session_state:
        fname = st.session_state.get("editing_file_name", "the original file")
        if st.session_state.pop("_edit_needs_reupload", False):
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
        "CSV or Excel (single or multi-sheet) — up to 500 MB",
        type=["csv", "xlsx", "xls"],
    )

    # ── Resume existing session (navigated back from Analysis) ───────────────
    # When the user clicks "Upload" from the Analysis page, the file_uploader
    # widget starts empty (Streamlit doesn't persist uploaded files across page
    # navigations). If a df is already loaded we show the existing pipeline
    # rather than leaving the user with a blank upload screen.
    if not uploaded and "df" in st.session_state and st.session_state.get("file_name"):
        _resumed_name = st.session_state["file_name"]
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
                          "_ul_preview_mode", "_resume_upload"]:
                    st.session_state.pop(k, None)
                st.rerun()

        # Render the pipeline if the user already confirmed to resume.
        if st.session_state.get("_resume_upload"):
            _show_analysis_pipeline(st.session_state["df"], _resumed_name)
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
    # Clear the resume flag now that a real file is in the widget.
    st.session_state.pop("_resume_upload", None)

    if not is_excel:
        if "df" not in st.session_state or file_changed:
            with st.spinner("Reading and optimising file…"):
                # Read the bytes once and cache by content so re-runs (widget
                # interactions, column describes, etc.) never re-parse the CSV.
                uploaded.seek(0)
                file_bytes = uploaded.read()
                df = _read_csv_cached(file_bytes, uploaded.name)
            st.session_state.df             = df
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig
            _clear_excel_state()
            mb = mem_mb(df)
            if mb > 50:
                st.caption(f"📊 Loaded {df.shape[0]:,} rows — memory footprint: {mb:.0f} MB")
        else:
            df = st.session_state.df
        _show_analysis_pipeline(df, uploaded.name)
    else:
        # ── Excel path ────────────────────────────────────────────────────────
        if file_changed:
            st.session_state.pop("df", None)
            _clear_excel_state(uploaded.name)
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig

        if "df" not in st.session_state:
            df = show_excel_loader(uploaded)
            if df is not None:
                st.session_state.df = df
                st.rerun()
        else:
            if st.button("⚙️ Edit Excel Configuration", key="_xl_edit_config"):
                st.session_state.pop("df", None)
                st.rerun()
            _show_analysis_pipeline(st.session_state.df, uploaded.name)


def _save_upload_snapshot(df, file_name: str) -> None:
    """Persist df parquet + minimal draft immediately after upload.

    Called from _show_analysis_pipeline so the dataset survives an app
    restart even before the user reaches the analysis page.
    """
    uid = st.session_state.get("user_id")
    if not uid:
        return
    try:
        from modules.utils.session_cache import save_df_snapshot
        from modules.database import save_draft
        import json as _json
        save_df_snapshot(uid)
        save_draft(
            user_id               = uid,
            page                  = "upload",
            charts_json           = "[]",
            file_name             = file_name,
            col_descriptions_json = _json.dumps(
                st.session_state.get("col_descriptions", {})
            ),
        )
    except Exception:
        pass  # Never block the upload flow on a snapshot failure


def _show_analysis_pipeline(df: pd.DataFrame, file_name: str):
    # Persist the df snapshot and a minimal draft immediately on upload so
    # the dataset can be restored if the app is restarted before any charts
    # are generated (analysis.py also calls _persist_draft but only once
    # the user has navigated there).
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

    with st.expander("🧹 Data Quality", expanded=False):
        st.info(
            "Preview missing values and duplicate rows here, then use the "
            "cleaning controls below to remove them safely. "
            "Changes are applied immediately to the dataset.",
            icon="ℹ️",
        )
        # Run the data quality UI every time so interactive fragments
        # (missing value preview + duplicate controls) are rendered.
        dq_charts = run_data_quality(df)

        if dq_charts:
            st.markdown("#### Data Quality Summaries")
            for title, fig in dq_charts:
                if title == "Duplicate Rows Summary":
                    unique_rows = int(df.drop_duplicates().shape[0])
                    duplicate_rows = len(df) - unique_rows
                    st.markdown(
                        f"**Duplicate rows:** {duplicate_rows:,} duplicate row(s) / "
                        f"{unique_rows:,} unique row(s)."
                    )
                    st.caption(
                        "Duplicate row counts use the default pandas duplicate\n"
                        "definition and keep the first occurrence by default."
                    )
                else:
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("No data quality issues were detected in the previewed dataset.")

    with st.expander("🔍 Outlier Detection", expanded=False):
        run_outlier_upload(df)

    with st.expander("🧩 Column Manager", expanded=False):
        df = show_column_manager(df)

    with st.expander("🔢 Data-type Transformer", expanded=False):
        df = show_dtype_transformer(df)

    with st.expander("🧼 Data Cleaner", expanded=False):
        df = show_data_cleaner(df)

    with st.expander("💾 Save Cleaned Data as CSV", expanded=False):
        st.caption(
            "Download the current (cleaned) dataset as a CSV file. "
            "The file reflects all cleaning operations applied so far."
        )
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
                help="The .csv extension will be added automatically.",
            )
        with _csv_col2:
            all_cols_for_idx = ["None (default integer index)"] + list(df.columns)
            _csv_index_choice = st.selectbox(
                "Index column (optional)",
                options=all_cols_for_idx,
                index=0,
                key="csv_export_index",
                help="Choose a column to use as the CSV row index, or keep the default integer index.",
            )

        _fname = (_csv_filename.strip() or "cleaned_data").rstrip(".csv") + ".csv"
        _use_col_as_idx = (
            _csv_index_choice
            if _csv_index_choice != "None (default integer index)"
            else None
        )

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
            f"{len(_csv_bytes)/1024:.1f} KB"
        )

    with st.expander("🧠 Classify Columns & Proceed to Analysis", expanded=False):
        show_column_classifier(df)


def _clear_excel_state(new_file_name: str = "") -> None:
    """Remove per-file Excel sheet-selection state when the user changes files."""
    keys_to_delete = [
        k for k in list(st.session_state.keys())
        if k.startswith("_xl_sheets_") and (
            not new_file_name or not k.endswith(new_file_name)
        )
    ]
    for k in keys_to_delete:
        del st.session_state[k]
    st.session_state.pop("_unified_table_info", None)
