"""modules/ui/column_manager.py"""


import streamlit as st
import numpy as np
import pandas as pd
import ast
import operator
import re

from modules.utils.session_cache import set_df, update_df




_SAFE_BIN_OPS = {
    ast.Add: operator.add,
    ast.Sub: operator.sub,
    ast.Mult: operator.mul,
    ast.Div: operator.truediv,
    ast.FloorDiv: operator.floordiv,
    ast.Mod: operator.mod,
    ast.Pow: operator.pow,
}
_SAFE_UNARY_OPS = {
    ast.UAdd: operator.pos,
    ast.USub: operator.neg,
}




def _safe_formula_eval(df: pd.DataFrame, formula: str) -> pd.Series:
    """Evaluate a derived-column formula with arithmetic only."""
    numeric_cols = set(df.select_dtypes(include=[np.number]).columns)
    column_aliases: dict[str, str] = {}


    def replace_backtick(match: re.Match) -> str:
        col = match.group(1)
        if col not in df.columns:
            raise ValueError(f"Unknown column: {col}")
        alias = f"__col_{len(column_aliases)}"
        column_aliases[alias] = col
        return alias


    expr = re.sub(r"`([^`]+)`", replace_backtick, formula.strip())
    if not expr:
        raise ValueError("Formula is empty.")


    tree = ast.parse(expr, mode="eval")


    def eval_node(node):
        if isinstance(node, ast.Expression):
            return eval_node(node.body)
        if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
            return node.value
        if isinstance(node, ast.Name):
            col = column_aliases.get(node.id, node.id)
            if col not in df.columns:
                raise ValueError(f"Unknown column: {col}")
            if col not in numeric_cols:
                raise ValueError(f"Column '{col}' is not numeric.")
            return df[col]
        if isinstance(node, ast.BinOp) and type(node.op) in _SAFE_BIN_OPS:
            return _SAFE_BIN_OPS[type(node.op)](eval_node(node.left), eval_node(node.right))
        if isinstance(node, ast.UnaryOp) and type(node.op) in _SAFE_UNARY_OPS:
            return _SAFE_UNARY_OPS[type(node.op)](eval_node(node.operand))
        raise ValueError("Only arithmetic with numeric columns and constants is allowed.")


    result = eval_node(tree)
    if np.isscalar(result):
        return pd.Series([result] * len(df), index=df.index)
    return result




def show_column_manager(df):
    """Add Column / Remove Column / Rename Column UI shown on the upload page."""
    st.markdown("---")
    st.markdown("## 🛠️ Column Manager")
    

    tab_add, tab_remove, tab_rename = st.tabs([
        "➕ Add Column",
        "🗑️ Remove Column",
        "✏️ Rename Column"
    ])


    with tab_add:
        num_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        a1, a2 = st.columns(2)
        with a1: new_col_name = st.text_input("New column name", key="new_col_name")
        with a2:
            calc_type = st.selectbox("Calculation type", [
                "Custom formula (use col names)", "Column × Column", "Column ÷ Column",
                "Column + Column", "Column − Column", "Extract Date/Time Part",
                "Date Difference"
            ], key="calc_type")


        formula_str = date_col = part_to_extract = None


        if calc_type == "Custom formula (use col names)":
            formula_str = st.text_input("Formula", key="custom_formula", placeholder="e.g. Sales / Units")
        elif calc_type in ("Column × Column", "Column ÷ Column", "Column + Column", "Column − Column"):
            op_map = {"Column × Column":"*","Column ÷ Column":"/","Column + Column":"+","Column − Column":"-"}
            op = op_map[calc_type]
            b1, b2 = st.columns(2)
            with b1: col_a = st.selectbox("First", num_cols, key="col_a")
            with b2: col_b = st.selectbox("Second", num_cols, key="col_b")
            formula_str = f"`{col_a}` {op} `{col_b}`"
        elif calc_type == "Date Difference":
            # Detect existing date-like columns (datetime types + parseable object columns)
            date_like_cols = []
            for col in df.columns:
                if pd.api.types.is_datetime64_any_dtype(df[col]):
                    date_like_cols.append(col)
                elif pd.api.types.is_object_dtype(df[col]):
                    try:
                        sample = df[col].dropna().head(20).astype(str)
                        pd.to_datetime(sample, errors="coerce")
                        # Accept if at least 50% parseable
                        if pd.to_datetime(sample, errors="coerce").notna().sum() >= len(sample) * 0.5:
                            date_like_cols.append(col)
                    except Exception:
                        pass
            if not date_like_cols:
                st.warning("No date-like columns found in the dataset. Parsing any column as string.")
                date_like_cols = df.columns.tolist()

            b1, b2 = st.columns(2)
            with b1:
                date_col_a = st.selectbox("Start Date Column", date_like_cols, key="dd_col_a")
            with b2:
                dd_target = st.radio("End date", ["Another column", "Today's date"], key="dd_target",
                                     horizontal=True)

            date_col_b = None
            if dd_target == "Another column":
                date_col_b = st.selectbox(
                    "End Date Column",
                    [c for c in date_like_cols if c != date_col_a],
                    key="dd_col_b",
                )

            diff_unit = st.selectbox("Difference unit", [
                "Days", "Months", "Years", "Age (Years from DOB vs Today)",
                "Previous Year (subtract 1 year)", "Previous Month (subtract 1 month)",
            ], key="dd_unit")
            formula_str = "date_diff_placeholder"

        elif calc_type == "Extract Date/Time Part":
            b1, b2 = st.columns(2)
            with b1: date_col = st.selectbox("Source Date Column", df.columns, key="date_col")
            with b2: part_to_extract = st.selectbox("Part to Extract",
                ["Date (YYYY-MM-DD)", "Year", "Quarter", "Month (Number)", "Month Name", "Week Number",
                 "Day", "Weekday Name", "Hour (12h AM/PM)", "Hour (24h)"], key="date_part_ext")
            formula_str = "date_extraction_placeholder"
            st.session_state["_date_extract_params"] = {
                "date_col": date_col,
                "part": part_to_extract,
                "new_col_name": new_col_name.strip(),
            }

        if st.button("➕ Add Column", key="btn_add_col"):
            if not new_col_name.strip() or not formula_str:
                st.error("Fill all fields.")
            else:
                try:
                    if calc_type == "Date Difference":
                        def _parse_series(series: pd.Series) -> pd.Series:
                            """Parse a Series to datetime, coercing errors to NaT."""
                            return pd.to_datetime(series.astype(str).str.strip(), errors="coerce")

                        series_a = _parse_series(df[date_col_a])

                        if dd_target == "Today's date":
                            end = pd.Timestamp.today()
                            series_b = pd.Series([end] * len(df), index=df.index)
                        else:
                            series_b = _parse_series(df[date_col_b])

                        null_count_a = int(series_a.isna().sum())
                        null_count_b = int(series_b.isna().sum())
                        total_null = null_count_a + null_count_b
                        if total_null:
                            st.warning(
                                f"⚠️ {null_count_a} value(s) in `{date_col_a}` and "
                                f"{null_count_b} in end date could not be parsed "
                                f"and will produce NaN in the new column."
                            )

                        if diff_unit == "Days":
                            result = (series_b - series_a).dt.days
                        elif diff_unit == "Months":
                            result = (series_b.dt.year - series_a.dt.year) * 12 + (
                                series_b.dt.month - series_a.dt.month
                            )
                            # Day-of-month adjustment: subtract 1 if end day < start day
                            adj = (series_b.dt.day < series_a.dt.day).astype(int)
                            result = result - adj
                        elif diff_unit == "Years":
                            raw_years = (series_b.dt.year - series_a.dt.year) + (
                                (series_b.dt.month - series_a.dt.month) / 12.0
                            ) + (
                                (series_b.dt.day - series_a.dt.day) / 365.0
                            )
                            result = raw_years
                            # For display, keep as float (round to 2dp) — user can see fractional years
                        elif diff_unit == "Age (Years from DOB vs Today)":
                            # Age uses today as end date
                            end = pd.Timestamp.today()
                            series_b = pd.Series([end] * len(df), index=df.index)
                            raw_years = (series_b.dt.year - series_a.dt.year) + (
                                (series_b.dt.month - series_a.dt.month) / 12.0
                            ) + (
                                (series_b.dt.day - series_a.dt.day) / 365.0
                            )
                            result = raw_years
                        elif diff_unit == "Previous Year (subtract 1 year)":
                            result = series_a - pd.DateOffset(years=1)
                        elif diff_unit == "Previous Month (subtract 1 month)":
                            result = series_a - pd.DateOffset(months=1)
                        else:
                            result = (series_b - series_a).dt.days

                        df[new_col_name.strip()] = result

                    elif calc_type == "Extract Date/Time Part":
                        _params = st.session_state.get("_date_extract_params", {})
                        _date_col = _params.get("date_col") or date_col
                        _part = _params.get("part") or part_to_extract
                        raw = df[_date_col]


                        def _parse_datetime_robust(series: pd.Series) -> pd.Series:
                            s = series.astype(str).str.strip()
                            result = pd.to_datetime(s, errors="coerce")


                            remaining = result.isna() & series.notna()
                            if not remaining.any():
                                return result


                            normalised = (
                                s[remaining]
                                .str.upper()
                                .str.replace(r"([AP]M)$", r" \1", regex=True)
                                .str.replace(r"\s{2,}", " ", regex=True)
                            )
                            result[remaining] = pd.to_datetime(
                                "1970-01-01 " + normalised, errors="coerce"
                            )


                            remaining = result.isna() & series.notna()
                            if not remaining.any():
                                return result


                            for fmt in (
                                "%I:%M %p", "%I:%M:%S %p",
                                "%I:%M%p",  "%I:%M:%S%p",
                                "%I %p",
                                "%m/%d/%Y %I:%M %p", "%d/%m/%Y %I:%M %p",
                                "%m/%d/%Y %H:%M",    "%d/%m/%Y %H:%M",
                            ):
                                still = result.isna() & series.notna()
                                if not still.any():
                                    break
                                try:
                                    attempt = pd.to_datetime(
                                        s[still], format=fmt, errors="coerce"
                                    )
                                    result[still] = attempt
                                except Exception:
                                    pass


                            return result


                        temp_dates = _parse_datetime_robust(raw)


                        null_count = int(temp_dates.isna().sum())
                        if null_count:
                            st.warning(
                                f"⚠️ {null_count} value(s) in `{date_col}` could not be parsed "
                                f"as a date/time and will produce NaN in the new column."
                            )


                        mapping = {
                            "Date (YYYY-MM-DD)": temp_dates.dt.date,
                            "Year":              temp_dates.dt.year,
                            "Quarter":           temp_dates.dt.quarter,
                            "Month (Number)":    temp_dates.dt.month,
                            "Month Name":        temp_dates.dt.month_name(),
                            "Week Number":       temp_dates.dt.isocalendar().week.astype("Int64"),
                            "Day":               temp_dates.dt.day,
                            "Weekday Name":      temp_dates.dt.day_name(),
                            "Hour (12h AM/PM)":  temp_dates.dt.strftime("%-I %p"),
                            "Hour (24h)":        temp_dates.dt.hour,
                        }
                        df[new_col_name.strip()] = mapping[_part]
                    else:
                        df[new_col_name.strip()] = _safe_formula_eval(df, formula_str)
                    update_df(df)
                    if "_date_extract_params" in st.session_state:
                        del st.session_state["_date_extract_params"]
                    st.success(f"✅ Added {new_col_name.strip()}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")


    with tab_remove:
        col_to_del = st.selectbox("Select column to remove", df.columns.tolist(), key="col_to_del")
        confirm = st.checkbox(f"Confirm removal of **{col_to_del}**", key="confirm_del")
        if st.button("🗑️ Remove", key="btn_del_col", disabled=not confirm):
            df = df.drop(columns=[col_to_del])
            set_df(df)
            for k in ["num_cols", "cat_cols"]:
                if k in st.session_state:
                    st.session_state[k] = [c for c in st.session_state[k] if c != col_to_del]
            st.success(f"✅ Removed {col_to_del}")
            st.rerun()


    with tab_rename:
        col_to_rename = st.selectbox("Select column to rename", df.columns.tolist(), key="col_to_rename")
        new_name_input = st.text_input("New column name", key="rename_new_name_val", placeholder="e.g. Sales_USD")
        

        new_name_clean = new_name_input.strip()
        is_disabled = not new_name_clean or new_name_clean == col_to_rename


        if st.button("✏️ Rename Column", key="btn_rename_col", disabled=is_disabled):
            if new_name_clean in df.columns:
                st.error(f"Error: A column named '{new_name_clean}' already exists in your dataset.")
            else:
                try:
                    df = df.rename(columns={col_to_rename: new_name_clean})
                    set_df(df)


                    if "num_cols" in st.session_state:
                        st.session_state["num_cols"] = [
                            new_name_clean if c == col_to_rename else c
                            for c in st.session_state["num_cols"]
                        ]
                    if "cat_cols" in st.session_state:
                        st.session_state["cat_cols"] = [
                            new_name_clean if c == col_to_rename else c
                            for c in st.session_state["cat_cols"]
                        ]


                    if "col_descriptions" in st.session_state:
                        col_descs = st.session_state["col_descriptions"]
                        if col_to_rename in col_descs:
                            col_descs[new_name_clean] = col_descs.pop(col_to_rename)
                            st.session_state["col_descriptions"] = col_descs

                    st.success(f"✅ Renamed '{col_to_rename}' to '{new_name_clean}'")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error renaming column: {e}")


    return st.session_state.df
