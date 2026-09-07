"""modules/pages/upload.py -- File upload and column classification page."""
import logging
import json
import datetime


import streamlit as st
import numpy as np
import pandas as pd


from modules.ui.column_manager import show_column_manager
from modules.ui.column_tools   import show_dtype_transformer, show_column_classifier
from modules.ui.data_cleaner   import show_data_cleaner
from modules.ui.excel_loader   import show_excel_loader
from modules.ui.css            import inject_footer, render_logo
from modules.utils.perf        import read_csv_fast, mem_mb
from modules.utils.session_cache import set_df
from modules.analysis.data_quality import run_data_quality, count_duplicates
from modules.analysis.outlier import run_outlier_upload
from modules.utils.transform_log import replay_transform_log
from modules.utils.regenerate import regenerate_charts, regenerate_kpis, validate_columns




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
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
        "CSV or Excel (single or multi-sheet), up to 400 MB — under 300 MB recommended for best performance",
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
                          "_ul_preview_mode", "_resume_upload", "_df_snapshot_sig",
                          "_last_draft_upload_cache", "_raw_upload_shape"]:
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
            # Detach from the @st.cache_resource object so in-place
            # mutations never corrupt the shared cache.
            set_df(df.copy())
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig
            st.session_state["_resume_upload"] = True
            # Capture the RAW upload shape (before any cleaning/transformation)
            # so "Datasets Analysed" counts distinct raw datasets.
            st.session_state["_raw_upload_shape"] = (int(df.shape[0]), int(df.shape[1]))
            _clear_excel_state()
            # Clear notes shadow only if NOT in edit mode (edit mode needs to preserve notes)
            if "editing_session_id" not in st.session_state:
                st.session_state.pop("_notes_shadow", None)
            mb = mem_mb(df)
            if mb > 50:
                st.caption(f"📊 Loaded {df.shape[0]:,} rows — memory footprint: {mb:.0f} MB")
        else:
            df = st.session_state.df
            st.session_state["_raw_upload_shape"] = (int(df.shape[0]), int(df.shape[1]))
        _show_analysis_pipeline(df, uploaded.name)
    else:
        if file_changed:
            st.session_state.pop("df", None)
            _clear_excel_state(uploaded.name)
            st.session_state.file_name      = uploaded.name
            st.session_state.file_signature = file_sig
            # Clear notes shadow only if NOT in edit mode (edit mode needs to preserve notes)
            if "editing_session_id" not in st.session_state:
                st.session_state.pop("_notes_shadow", None)


        if "df" not in st.session_state:
            df = show_excel_loader(uploaded)
            if df is not None:
                set_df(df.copy())
                st.session_state["_resume_upload"] = True
                # Capture the RAW upload shape before the rerun so it isn't lost.
                st.session_state["_raw_upload_shape"] = (int(df.shape[0]), int(df.shape[1]))
                st.rerun()
        else:
            if st.button("⚙️ Edit Excel Configuration", key="_xl_edit_config"):
                st.session_state.pop("df", None)
                st.rerun()
            _show_analysis_pipeline(st.session_state.df, uploaded.name)




def _save_upload_snapshot(df, file_name: str) -> None:
    """Persist df parquet + minimal draft immediately after upload if modified.

    Runs on the main Streamlit script-run thread. The parquet write itself is
    handed off to a background thread (disk I/O), but the DataFrame reference
    and every `st.session_state` read/write happens here first --
    `st.session_state` is bound to this thread's ScriptRunContext and must
    never be touched from the spawned thread.
    """
    uid = st.session_state.get("user_id")
    if not uid:
        return

    # ── FAST-PATH: Skip entirely if the DataFrame version hasn't changed ──
    # This is the single most important optimisation for large files:
    # df.memory_usage(deep=True) is O(rows×cols) and must NEVER run on every
    # rerun.  The _df_version counter is bumped by set_df()/update_df() and
    # is the authoritative signal that the DataFrame content has changed.
    _df_ver = st.session_state.get("_df_version", 0)
    _last_ver = st.session_state.get("_df_snapshot_version", -1)
    if _df_ver == _last_ver:
        return  # DataFrame unchanged since last snapshot — nothing to do

    try:
        df_sig = (
            df.shape,
            tuple(df.columns),
            tuple(str(dt) for dt in df.dtypes),
        )
        sig_changed = st.session_state.get("_df_snapshot_sig") != df_sig

        draft_cache_key = ("_draft_upload_cache", file_name, df_sig)
        if st.session_state.get("_last_draft_upload_cache") != draft_cache_key or sig_changed:
            from modules.utils.session_cache import save_df_snapshot
            from modules.database import save_draft
            import threading

            if sig_changed:
                # Skip if a save for this exact signature is already in
                # flight -- avoids piling up concurrent parquet writers (and
                # concurrent SQLite writers downstream) when the signature
                # changes across several reruns in quick succession.
                if st.session_state.get("_df_snapshot_inflight_sig") != df_sig:
                    st.session_state["_df_snapshot_inflight_sig"] = df_sig
                    # Capture the DataFrame reference on the main thread now
                    # and pass it explicitly -- save_df_snapshot() must not
                    # fall back to reading st.session_state from the
                    # background thread itself.
                    df_ref = df
                    threading.Thread(
                        target=save_df_snapshot,
                        args=(uid, df_ref),
                        daemon=True,
                    ).start()
                st.session_state["_df_snapshot_sig"] = df_sig
                st.session_state.pop("_df_snapshot_inflight_sig", None)

            save_draft(
                user_id               = uid,
                page                  = "upload",
                charts_json           = "[]",
                file_name             = file_name,
                editing_file_name     = st.session_state.get("editing_file_name", ""),
            )
            st.session_state["_last_draft_upload_cache"] = draft_cache_key

    except Exception as exc:
        # This failure means the user's draft/snapshot did NOT persist --
        # log loudly enough to actually show up in streamlit.log rather than
        # only at DEBUG level, since silently swallowing it is a data-loss
        # risk the user would otherwise never learn about.
        logging.getLogger(__name__).warning(
            "Failed to save upload snapshot/draft for user %s: %s",
            uid, exc, exc_info=True,
        )
    finally:
        # Always record the version we checked against, even on error, so
        # we don't retry the (expensive) signature computation every rerun.
        st.session_state["_df_snapshot_version"] = _df_ver




def _auto_update_on_reupload(df: pd.DataFrame, file_name: str) -> pd.DataFrame:
    """When re-uploading a file for a session that's being edited: replay
    the saved column transforms (renames/calculated columns/dtype changes),
    then regenerate every chart and KPI against the refreshed data.

    Runs once per (session, upload) pair -- guarded so it doesn't re-fire
    on every widget rerun while the user keeps editing.
    """
    eid = st.session_state.get("editing_session_id")
    if not eid:
        return df

    guard_key = f"_auto_regen_done_{eid}_{st.session_state.get('file_signature')}"
    if st.session_state.get(guard_key):
        return df
    st.session_state[guard_key] = True

    report_lines = []

    transform_log = st.session_state.get("transform_log", [])
    if transform_log:
        df, warnings = replay_transform_log(df, transform_log)
        set_df(df)
        applied = len(transform_log) - len(warnings)
        if applied:
            report_lines.append(("success", f"Reapplied {applied} saved column change(s) from the previous version of this dataset."))
        for w in warnings:
            report_lines.append(("warning", w))

    if st.session_state.get("charts") or st.session_state.get("kpis"):
        pre_check = validate_columns(df)
        chart_result = regenerate_charts(df)
        kpi_result = regenerate_kpis(df)

        if chart_result["updated"]:
            report_lines.append(("success", f"Auto-updated {len(chart_result['updated'])} chart(s) with the new data."))
        for uid, reason in chart_result["skipped"].items():
            title = next((t for u, t, _f in st.session_state.get("charts", []) if u == uid), uid)
            report_lines.append(("warning", f"Chart '{title}': {reason}."))

        if kpi_result["updated"]:
            report_lines.append(("success", f"Auto-updated {len(kpi_result['updated'])} KPI(s) with the new data."))
        if kpi_result["skipped"]:
            report_lines.append((
                "warning",
                f"{len(kpi_result['skipped'])} KPI(s) predate auto-update and were left as-is "
                f"(remove & re-add them to enable auto-refresh): {', '.join(kpi_result['skipped'])}."
            ))

        for uid, info in pre_check["charts"].items():
            report_lines.append((
                "warning",
                f"Chart '{info['title']}' references column(s) not in the new file: {', '.join(info['missing'])}."
            ))
        for label, missing in pre_check["kpis"].items():
            report_lines.append((
                "warning",
                f"KPI '{label}' references column(s) not in the new file: {', '.join(missing)}."
            ))

    st.session_state["_last_auto_update_report"] = report_lines
    return df


def _apply_upload_filters(df: pd.DataFrame, search_text: str, col_filters: dict) -> np.ndarray:
    """Apply the global text search + per-column filters built by the Full
    Table view. Returns a **boolean numpy mask** (not a filtered DataFrame)
    so callers can paginate with ``df.iloc[mask]`` without ever materialising
    a full copy of a large dataset. Pure function so it's testable without
    Streamlit widgets."""
    n = len(df)

    # FAST-PATH: no filters at all — return an all-True mask without building
    # a 12.7M-element boolean Series or copying the DataFrame.
    if not search_text and not col_filters:
        return np.ones(n, dtype=bool)

    mask = np.ones(n, dtype=bool)

    if search_text:
        text_cols = df.select_dtypes(include=["object", "category"]).columns
        if len(text_cols):
            needle = search_text.lower()
            sub_mask = np.zeros(n, dtype=bool)
            for c in text_cols:
                sub_mask |= df[c].astype(str).str.lower().str.contains(needle, na=False, regex=False).to_numpy()
            mask &= sub_mask

    for col, spec in col_filters.items():
        if col not in df.columns:
            continue
        kind = spec.get("kind")
        val  = spec.get("value")
        if kind == "numeric" and val is not None:
            lo, hi = val
            mask &= df[col].between(lo, hi).to_numpy()
        elif kind == "categorical" and val:
            mask &= df[col].astype(str).isin([str(v) for v in val]).to_numpy()
        elif kind == "text_contains" and val:
            mask &= df[col].astype(str).str.lower().str.contains(val.lower(), na=False, regex=False).to_numpy()
        elif kind == "date" and val is not None:
            start, end = val
            parsed = pd.to_datetime(df[col], errors="coerce")
            mask &= ((parsed >= pd.Timestamp(start)) & (parsed <= pd.Timestamp(end) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))).to_numpy()
        elif kind == "bool" and val != "All":
            mask &= (df[col] == (val == "True")).to_numpy()

    return mask


def _render_full_table_filters(df: pd.DataFrame) -> np.ndarray:
    """Render the filter UI for the Full Table preview mode and return a
    **boolean numpy mask** of matching rows (not a filtered DataFrame).
    Filter widgets are opt-in per column (via a multiselect) so wide
    datasets don't render dozens of filter controls at once.

    For large datasets (>100k rows) the categorical unique-value scan is
    performed on a sample so the widget renders in O(sample) instead of
    O(rows). The cached mask is a lightweight numpy bool array — never a
    full copy of the DataFrame.
    """
    all_cols = df.columns.tolist()
    n_rows = len(df)
    _LARGE = n_rows > 100_000

    fc1, fc2 = st.columns([2, 1])
    with fc1:
        search_text = st.text_input(
            "🔎 Search all text columns", key="_ul_filter_search",
            placeholder="Type to search across every text/category column…",
        )
    with fc2:
        if st.button("♻️ Clear Filters", key="_ul_clear_filters", use_container_width=True):
            for k in list(st.session_state.keys()):
                if k.startswith("_ul_filter_"):
                    del st.session_state[k]
            st.session_state.pop("_ul_filter_cols", None)
            st.rerun()

    filter_cols = st.multiselect(
        "Add a filter for specific column(s)",
        all_cols, key="_ul_filter_cols",
        placeholder="Choose column(s) to filter…",
    )

    col_filters = {}
    if filter_cols:
        grid = st.columns(3)
        for i, col in enumerate(filter_cols):
            series = df[col]
            with grid[i % 3]:
                if pd.api.types.is_datetime64_any_dtype(series):
                    valid = series.dropna()
                    if len(valid):
                        lo_d, hi_d = valid.min().date(), valid.max().date()
                        dkey = f"_ul_filter_date_{col}"
                        cur = st.session_state.get(dkey)
                        if isinstance(cur, tuple) and len(cur) == 2 and (cur[0] < lo_d or cur[1] > hi_d):
                            st.session_state[dkey] = (lo_d, hi_d)
                        rng = st.date_input(f"📅 {col}", value=(lo_d, hi_d),
                                             min_value=lo_d, max_value=hi_d, key=dkey)
                        if isinstance(rng, tuple) and len(rng) == 2:
                            col_filters[col] = {"kind": "date", "value": rng}
                elif pd.api.types.is_bool_dtype(series):
                    choice = st.selectbox(f"☑ {col}", ["All", "True", "False"], key=f"_ul_filter_bool_{col}")
                    col_filters[col] = {"kind": "bool", "value": choice}
                elif pd.api.types.is_numeric_dtype(series):
                    valid = series.dropna()
                    if len(valid) and valid.min() != valid.max():
                        lo_v, hi_v = float(valid.min()), float(valid.max())
                        nkey = f"_ul_filter_num_{col}"
                        cur = st.session_state.get(nkey)
                        if isinstance(cur, tuple) and len(cur) == 2 and (cur[0] < lo_v or cur[1] > hi_v):
                            st.session_state[nkey] = (lo_v, hi_v)
                        rng = st.slider(f"🔢 {col}", min_value=lo_v, max_value=hi_v,
                                         value=(lo_v, hi_v), key=nkey)
                        col_filters[col] = {"kind": "numeric", "value": rng}
                    else:
                        st.caption(f"🔢 {col}: single value, nothing to filter")
                else:
                    # ── Categorical / text column ─────────────────────────
                    # For large datasets, estimate nunique on a sample so the
                    # widget renders in O(100k) instead of O(12.7M).
                    if _LARGE:
                        _sample_series = series.dropna().sample(
                            min(100_000, len(series)), random_state=42
                        )
                        nunique = int(_sample_series.nunique(dropna=True))
                    else:
                        nunique = int(series.nunique(dropna=True))

                    if nunique <= 200:
                        # Sample-based estimate says few unique values — still
                        # need the real list for the multiselect options.
                        opts = sorted(series.dropna().astype(str).unique().tolist())
                        picked = st.multiselect(f"🔤 {col}", opts, key=f"_ul_filter_cat_{col}")
                        if picked:
                            col_filters[col] = {"kind": "categorical", "value": picked}
                    else:
                        txt = st.text_input(f"🔤 {col} contains…", key=f"_ul_filter_cat_text_{col}")
                        if txt:
                            col_filters[col] = {"kind": "text_contains", "value": txt}

    filter_sig = (
        search_text,
        tuple(sorted((c, json.dumps(f["value"], default=str)) for c, f in col_filters.items())),
    )
    cache_key = ("_ul_full_filtered", st.session_state.get("_df_version", 0), filter_sig)
    if st.session_state.get("_ul_full_filter_cache_key") != cache_key:
        mask = _apply_upload_filters(df, search_text, col_filters)
        # Cache the lightweight boolean mask — NOT a full DataFrame copy.
        st.session_state["_ul_full_filter_cache"] = mask
        st.session_state["_ul_full_filter_cache_key"] = cache_key
    else:
        mask = st.session_state["_ul_full_filter_cache"]

    return mask


def _show_analysis_pipeline(df: pd.DataFrame, file_name: str):
    if "editing_session_id" in st.session_state:
        df = _auto_update_on_reupload(df, file_name)

    report = st.session_state.pop("_last_auto_update_report", None)
    if report:
        with st.expander("🔄 Auto-update summary (re-uploaded data)", expanded=True):
            for kind, msg in report:
                (st.success if kind == "success" else st.warning)(msg)

    _save_upload_snapshot(df, file_name)
    st.markdown("---")
    _n_rows = df.shape[0]
    _n_cols = df.shape[1]
    st.success(f"✅ **{file_name}** — {_n_rows:,} rows × {_n_cols} columns")

    if _n_rows > 100_000:
        st.info(
            "ℹ️ **Large dataset detected.** All counts, summaries, and statistical "
            "thresholds (missing values, duplicates, outliers) are computed on the "
            "**full dataset** for exact accuracy. Only row-level chart rendering "
            "(heatmap, scatter backgrounds, map density) is sampled or aggregated "
            "for display speed — the underlying analysis is exact."
        )


    # ── Data Preview (fragment-isolated so button clicks don't rerun the
    # entire upload page) ──────────────────────────────────────────────────
    @st.fragment(run_every=None)
    def _render_upload_preview():
        with st.expander("📋 Data Preview", expanded=True):
            _pb1, _pb2, _pb3, _pb4, _pb5 = st.columns([1, 1, 1, 1, 3])
            with _pb1:
                if st.button("⬆ Top 10",    key="ul_prev_top",  use_container_width=True):
                    st.session_state["_ul_preview_mode"] = "top"
                    st.rerun()
            with _pb2:
                if st.button("⬇ Bottom 10", key="ul_prev_bot",  use_container_width=True):
                    st.session_state["_ul_preview_mode"] = "bottom"
                    st.rerun()
            with _pb3:
                if st.button("🎲 Random",   key="ul_prev_rand", use_container_width=True):
                    st.session_state["_ul_preview_mode"] = "random"
                    st.session_state["_ul_random_seed"] = (
                        st.session_state.get("_ul_random_seed", 0) + 1
                    )
                    st.rerun()
            with _pb4:
                if st.button("📊 Full Table", key="ul_prev_full", use_container_width=True):
                    st.session_state["_ul_preview_mode"] = "full"
                    st.rerun()
            with _pb5:
                # Cache expensive DataFrame stats by _df_version — avoids
                # O(rows×cols) isnull().sum().sum() on every rerun.
                _df_ver = st.session_state.get("_df_version", 0)
                _stats_key = "_ul_df_stats"
                _stats_ver_key = "_ul_df_stats_ver"
                if st.session_state.get(_stats_ver_key) != _df_ver or _stats_key not in st.session_state:
                    # A conversion to "date" now yields a true datetime64 dtype,
                    # but "time" yields datetime.time objects in an object-dtype
                    # column. Detect those object columns (whose values are real
                    # date/time objects) and count them as datetime, not text --
                    # mirroring the special handling in show_column_classifier.
                    # (datetime.datetime subclasses datetime.date, so this also
                    # catches columns of datetime objects.)
                    _date_like_obj = [
                        c for c in df.select_dtypes("object").columns
                        if len(df) > 0 and isinstance(
                            df[c].dropna().iloc[0],
                            (datetime.date, datetime.time)
                        )
                    ]
                    _num_c = len(df.select_dtypes("number").columns)
                    _cat_c = len(df.select_dtypes("object").columns) - len(_date_like_obj)
                    _dt_c  = len(df.select_dtypes("datetime").columns) + len(_date_like_obj)
                    # For large files, sample for null% to avoid O(rows×cols) scan
                    if _n_rows > 100_000:
                        _sample_df = df.sample(min(100_000, _n_rows), random_state=42)
                        _null = round(_sample_df.isnull().sum().sum() / max(_sample_df.size, 1) * 100, 1)
                    else:
                        _null = round(df.isnull().sum().sum() / max(df.size, 1) * 100, 1)
                    st.session_state[_stats_key] = (_num_c, _cat_c, _dt_c, _null)
                    st.session_state[_stats_ver_key] = _df_ver
                else:
                    _num_c, _cat_c, _dt_c, _null = st.session_state[_stats_key]
                st.caption(
                    f"🔢 {_num_c} numeric  ·  🔤 {_cat_c} text  ·  "
                    f"📅 {_dt_c} datetime  ·  ⚠️ {_null}% missing"
                )


            _ul_mode = st.session_state.get("_ul_preview_mode", "top")

            if _ul_mode == "full":
                st.markdown("---")
                mask = _render_full_table_filters(df)
                _n_filtered = int(mask.sum())

                pg1, pg2, pg3 = st.columns([1, 1, 2])
                with pg1:
                    page_size = st.selectbox("Rows per page", [25, 50, 100, 250, 500],
                                              index=1, key="_ul_full_page_size")
                total_pages = max(1, -(-_n_filtered // page_size))
                if st.session_state.get("_ul_full_page", 1) > total_pages:
                    st.session_state["_ul_full_page"] = total_pages
                with pg2:
                    page = st.number_input("Page", min_value=1, max_value=total_pages,
                                            step=1, key="_ul_full_page")
                with pg3:
                    st.caption(
                        f"Showing rows {min((page-1)*page_size+1, _n_filtered)}–"
                        f"{min(page*page_size, _n_filtered)} of {_n_filtered:,} filtered "
                        f"(of {_n_rows:,} total) · page {page}/{total_pages}"
                    )

                # Materialise ONLY the visible page (25–500 rows) — never the
                # full filtered dataset.
                _row_idx = np.flatnonzero(mask)
                _page_idx = _row_idx[(page-1)*page_size : page*page_size]
                page_df = df.iloc[_page_idx]
                st.dataframe(page_df, use_container_width=True, height=min(600, 38 + len(page_df) * 35))

                # LAZY download: the callable is only invoked when the user
                # actually clicks the button. Previously `data=filtered.to_csv()`
                # serialised all 12.7M rows on EVERY fragment rerun — the cause
                # of the UI freeze.
                if _n_filtered > 1_000_000:
                    st.warning(
                        f"⚠️ Downloading {_n_filtered:,} rows will produce a large CSV "
                        f"and may take a while. Click the button below to generate it."
                    )
                st.download_button(
                    "⬇️ Download filtered rows as CSV",
                    data=lambda: df.iloc[_row_idx].to_csv(index=False).encode("utf-8"),
                    file_name=f"filtered_{file_name.rsplit('.', 1)[0]}.csv",
                    mime="text/csv",
                    key="_ul_full_download",
                )
                return

            _ul_rand_seed = st.session_state.get("_ul_random_seed", 0) if _ul_mode == "random" else 0
            _df_version = st.session_state.get("_df_version", 0)
            _cache_key = ("ul_preview", _n_rows, _n_cols, _ul_mode, _ul_rand_seed, _df_version, tuple(df.columns))
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
                st.session_state["_ul_preview_cache"] = (_prev_df.copy(), _lbl)
                st.session_state["_ul_preview_cache_key"] = _cache_key
            else:
                _prev_df, _lbl = st.session_state.get("_ul_preview_cache", (df.head(10), "Top 10 rows"))


            st.caption(f"*{_lbl}*")
            st.dataframe(_prev_df, use_container_width=True, height=min(380, 38 + len(_prev_df) * 35))

    _render_upload_preview()


    # ── Data Quality (fragment-isolated) ──────────────────────────────────
    @st.fragment(run_every=None)
    def _render_data_quality():
        with st.expander("🧹 Data Quality Summary", expanded=False):
            st.info("Check the box below to run a data quality analysis.")
            if st.checkbox("🔍 Enable Data Quality Diagnostics", key="_enable_dq_run"):
                with st.spinner("Analyzing data quality metrics..."):
                    # All counts/summaries are computed on the FULL dataset.
                    # Only row-level chart rendering (heatmap) samples internally.
                    dq_charts = run_data_quality(df)


                    if dq_charts:
                        st.markdown("#### Data Quality Summaries")
                        for title, fig in dq_charts:
                            if title == "Duplicate Rows Summary":
                                duplicate_rows = count_duplicates(df)
                                unique_rows = len(df) - duplicate_rows
                                st.markdown(
                                    f"**Duplicate rows:** {duplicate_rows:,} duplicate row(s) / "
                                    f"{unique_rows:,} unique row(s)."
                                )
                            else:
                                st.plotly_chart(fig, use_container_width=True)
                    else:
                        st.info("No data quality issues were detected.")

    _render_data_quality()


    # ── Outlier Detection (fragment-isolated) ─────────────────────────────
    @st.fragment(run_every=None)
    def _render_outlier_detection():
        with st.expander("🔍 Outlier Detection", expanded=False):
            st.info("Check the box below to run outlier analysis across numeric columns.")
            if st.checkbox("📊 Enable Outlier Scanners", key="_enable_outlier_run"):
                with st.spinner("Calculating outlier boundaries..."):
                    # IQR fences/counts are computed on the FULL dataset.
                    # Only the scatter background is sampled for rendering.
                    run_outlier_upload(df)

    _render_outlier_detection()


    # ── Column Manager (fragment-isolated) ────────────────────────────────
    @st.fragment(run_every=None)
    def _render_column_manager():
        with st.expander("🧩 Column Manager", expanded=False):
            show_column_manager(df)

    _render_column_manager()


    # ── Dtype Transformer (fragment-isolated) ─────────────────────────────
    @st.fragment(run_every=None)
    def _render_dtype_transformer():
        with st.expander("🔢 Data-type Transformer", expanded=False):
            show_dtype_transformer(df)

    _render_dtype_transformer()


    # ── Data Cleaner (fragment-isolated) ─────────────────────────────────
    @st.fragment(run_every=None)
    def _render_data_cleaner():
        with st.expander("🧼 Data Cleaner", expanded=False):
            show_data_cleaner(df)

    _render_data_cleaner()


    # ── CSV Export (fragment-isolated + button-triggered so df.to_csv()
    # only runs when the user explicitly clicks "Generate", not on every
    # rerun) ──────────────────────────────────────────────────────────────
    @st.fragment(run_every=None)
    def _render_csv_export():
        with st.expander("💾 Save Cleaned Data as CSV", expanded=False):
            st.caption("Download the current (cleaned) dataset as a CSV file.")


            if st.checkbox("⚙️ Prepare CSV Download File", key="_enable_csv_export"):
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


                # Cache key based on filename, index choice, and df version
                _df_ver = st.session_state.get("_df_version", 0)
                _csv_cache_key = ("csv_export", _fname, _use_col_as_idx, _df_ver)
                _csv_cached = st.session_state.get("_csv_export_cache_key") == _csv_cache_key


                _gc1, _gc2 = st.columns([1, 2])
                with _gc1:
                    if st.button("🔄 Generate CSV", key="csv_gen_btn",
                                 type="primary", use_container_width=True):
                        with st.spinner("Generating export file (this can take a moment for large datasets)..."):
                            _export_df = df.set_index(_use_col_as_idx) if _use_col_as_idx else df
                            _csv_bytes = _export_df.to_csv(index=bool(_use_col_as_idx)).encode("utf-8")
                            st.session_state["_csv_export_bytes"] = _csv_bytes
                            st.session_state["_csv_export_cache_key"] = _csv_cache_key
                            st.session_state["_csv_export_size"] = len(_csv_bytes)
                        st.rerun()


                if _csv_cached and "_csv_export_bytes" in st.session_state:
                    _csv_bytes = st.session_state["_csv_export_bytes"]
                    _csv_size = st.session_state.get("_csv_export_size", len(_csv_bytes))
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
                        f"{_csv_size/1024/1024:.1f} MB"
                    )
                else:
                    st.info("Click **Generate CSV** above to create the download link.")
            else:
                st.info("Check the box above to generate the download link for your dataset.")

    _render_csv_export()


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