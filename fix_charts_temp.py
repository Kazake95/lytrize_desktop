import sys

filepath = sys.argv[1]
with open(filepath, 'r') as f:
    lines = f.readlines()

def find_index(lines, target):
    for i, line in enumerate(lines):
        if target in line:
            return i
    raise ValueError(f"Target not found: {target}")

scatter_start = find_index(lines, '    elif chart_type in ("scatter", "scatter_plot") or "scatter:" in tl:')
scatter_end = find_index(lines, '    elif chart_type == "map_plot" or "map:" in tl:')

new_scatter = r'''    elif chart_type in ("scatter", "scatter_plot") or "scatter:" in tl:
        try:
            cols_match = re.search(r"Scatter:\s*(.+?)\s+vs\s+(.+?)(\s|$|·|—)", title)
            x_col = cols_match.group(1).strip() if cols_match else "X"
            y_col = cols_match.group(2).strip() if cols_match else "Y"


            has_ols    = False
            has_lowess = False
            ols_slope  = None
            for _t in fig.data:
                _mode = str(getattr(_t, "mode", ""))
                _name = str(getattr(_t, "name", "")).lower()
                if "lines" in _mode and "markers" not in _mode:
                    if "ols" in _name or "=" in _name or "trendline" in _name:
                        has_ols = True
                        _slope_m = re.search(r"y\s*=\s*([+-]?[\d.]+)x", _name)
                        if _slope_m:
                            try: ols_slope = float(_slope_m.group(1))
                            except Exception: pass
                    else:
                        has_lowess = True


            r_match = re.search(r"r\s*=\s*([+-]?\d+\.\d+)", title)
            r_val   = float(r_match.group(1)) if r_match Tutor else None


            scatter_trace = next(
                (t for t in fig.data if "markers" in str(getattr(t, "mode", ""))), None)


            if r_val is not None:
                strength  = "strong" if abs(r_val) >= 0.7 else "moderate" if abs(r_val) >= 0.4 else "weak"
                direction = "positive" if r_val > 0 else "negative"
                insights.append(
                    f"{_named(x_col)} and {_named(y_col)} show a {strength} {direction} "
                    f"relationship."
                )
                if abs(r_val) >= 0.7:
                    insights.append(
                        "When one goes up, the other reliably follows — the link is quite predictable."
                    )
                elif abs(r_val) >= 0.4:
                    insights.append(
                        "There is a visible link, but it will not be perfect — other factors likely influence the outcome."
                    )
                else:
                    insights.append(
                        "The points are widely scattered, so the connection between these two variables is weak."
                    )


            if has_ols:
                if ols_slope is not None:
                    direction_word = "increases" if ols_slope > 0 else "decreases"
                    insights.append(
                        f"On average, as {_named(x_col)} rises by one unit, {_named(y_col)} tends to {direction_word} by about {abs(ols_slope):.3g}."
                    )
                else:
                    insights.append("A straight trendline is fitted to show the overall direction.")
                insights.append(
                    "Points that fall far from this line are different from the general pattern and may be worth a closer look."
                )


            if has_lowess:
                insights.append(
                    "A smooth trendline is fitted — it bends to follow the local shape of the data."
                )
                insights.append(
                    f"Where the line flattens, {_named(y_col)} stops changing much even when {_named(x_col)} changes — a possible saturation or threshold."
                )


            if not has_ols and not has_lowess and r_val is None:
                insights.append(
                    f"Add a trendline to see whether there is a clear relationship between {_named(x_col)} and {_named(y_col)}."
                )


            if scatter_trace:
                n_pts = len(getattr(scatter_trace, "x", []) or [])
                if n_pts:
                    insights.append(f"Chart shows {n_pts:,} data points.")
                    if n_pts >= 7_000:
                        insights.append(
                            "Large sample — dense overplotting may hide structure. "
                            "Try colouring by a category column to separate groups."
                        )


        except Exception:
            pass


        if not insights:
            insights.append(
                f"Explore the relationship between the X and Y axes — add a trendline to see the pattern."
            )

'''

map_start = find_index(lines, '    elif chart_type == "map_plot" or "map:" in tl:')
map_end = find_index(lines, '    elif chart_type in ("matrix_heatmap", "matrix_table") or "matrix" in tl:')

new_map = r'''    elif chart_type == "map_plot" or "map:" in tl:
        pass  # No auto-insights for map charts

'''

matrix_start = find_index(lines, '    elif chart_type in ("matrix_heatmap", "matrix_table") or "matrix" in tl:')
matrix_end = find_index(lines, '    elif (chart_type == "statistical"')

new_matrix = r'''    elif chart_type in ("matrix_heatmap", "matrix_table") or "matrix" in tl:
        pass  # No auto-insights for matrix charts

'''

new_content = (
    "".join(lines[:scatter_start])
    + new_scatter
    + "".join(lines[scatter_end:map_start])
    + new_map
    + "".join(lines[map_end:matrix_start])
    + new_matrix
    + "".join(lines[matrix_end:])
)

with open(filepath, 'w') as f:
    f.write(new_content)

print("Done")
