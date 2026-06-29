"""modules/ui/chart_settings.py -- Shared chart setting schema and Plotly adapters."""


from __future__ import annotations


import copy
import functools
import json
import re
from typing import Any


import streamlit as st


from modules.charts import clean_insight_text
from modules.ui.font_manager import inject_font_preview_css, font_select


COLORSCALES_DIVERGING  = ["RdBu", "RdYlBu", "PRGn", "PiYG", "BrBG", "Spectral"]
COLORSCALES_SEQUENTIAL = ["Blues", "Viridis", "Plasma", "Magma", "Cividis",
                           "YlOrRd", "YlGnBu", "Greens", "Oranges", "Purples"]
COLORSCALES_ALL        = COLORSCALES_DIVERGING + COLORSCALES_SEQUENTIAL




FONT_STACK_MAP: dict[str, str] = {
    "Inter": "Inter, 'Inter-Variable', 'Helvetica Neue', Arial, sans-serif",
    "Source Sans 3": "'Source Sans 3', 'Liberation Sans', Arimo, Arial, sans-serif",
    "Noto Sans": "'Noto Sans', 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
    "DejaVu Sans": "'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
    "Lato": "Lato, 'DejaVu Sans', 'Liberation Sans', Arial, sans-serif",
    "Ubuntu": "Ubuntu, 'DejaVu Sans', 'Liberation Sans', sans-serif",
    "Arial": "Arial, 'Liberation Sans', Arimo, 'DejaVu Sans', sans-serif",
    "Calibri": "Calibri, Carlito, 'Liberation Sans', 'DejaVu Sans', sans-serif",
    "Verdana": "Verdana, 'DejaVu Sans', Geneva, sans-serif",
    "Oswald": "Oswald, 'DejaVu Sans', Arial, sans-serif",
    "Barlow Condensed": "'Barlow Condensed', 'DejaVu Sans', Arial, sans-serif",
    "Noto Serif": "'Noto Serif', 'DejaVu Serif', 'Liberation Serif', Times, serif",
    "DejaVu Serif": "'DejaVu Serif', 'Liberation Serif', Times, serif",
    "EB Garamond": "'EB Garamond', 'DejaVu Serif', 'Liberation Serif', Georgia, serif",
    "Georgia": "Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
    "Times New Roman": "'Times New Roman', 'Liberation Serif', Tinos, 'DejaVu Serif', serif",
    "Fira Code": "'Fira Code', 'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
    "DejaVu Sans Mono": "'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
    "JetBrains Mono": "'JetBrains Mono', 'DejaVu Sans Mono', 'Liberation Mono', Consolas, monospace",
    "Liberation Mono": "'Liberation Mono', 'DejaVu Sans Mono', Consolas, monospace",
    "Courier New": "'Courier New', 'Liberation Mono', 'DejaVu Sans Mono', monospace",
    "Comic Sans MS": "'Comic Sans MS', 'Comic Sans', cursive, sans-serif",
    "Impact": "Impact, 'Arial Narrow', 'DejaVu Sans', sans-serif",
    "Trebuchet MS": "'Trebuchet MS', 'Liberation Sans', Ubuntu, sans-serif",
    "Helvetica": "'Helvetica Neue', Helvetica, Arial, 'Liberation Sans', sans-serif",
    "Palatino Linotype": "'Palatino Linotype', 'Book Antiqua', Palatino, 'Liberation Serif', serif",
    "Candara": "'Candara', 'Segoe UI', 'Liberation Sans', Arial, sans-serif",
    "Corbel": "'Corbel', 'Segoe UI', 'Liberation Sans', Arial, sans-serif",
    "Constantia": "'Constantia', Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
    "Lucida Console": "'Lucida Console', 'Lucida Sans Typewriter', 'Liberation Mono', monospace",
    "Consolas": "'Consolas', 'Liberation Mono', 'Courier New', monospace",
    "Sora": "Sora, 'Sora Medium', 'Sora SemiBold', sans-serif",
    "Cambria": "'Cambria', Georgia, 'DejaVu Serif', 'Liberation Serif', serif",
}




def resolve_font_stack(font_name: str) -> str:
    """Resolve a clean font name to a highly compatible CSS system font stack."""
    return FONT_STACK_MAP.get(font_name, font_name)




CHART_TYPE_SETTINGS: dict[str, dict[str, Any]] = {
    "categorical": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "subtitle", "axes_labels", "legend_labels",
                    "show_value_labels", "label_position", "bar_gap", "bar_mode"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "descriptive": {
        "has_axes": False, "has_legend": False,
        "controls": ["title"],
        "typography": ["family", "font_style", "header"],
    },
    "statistical": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "subtitle", "axes_labels", "legend_labels",
                    "show_value_labels", "label_position", "bar_gap", "bar_mode"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "distribution": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "subtitle", "axes_labels", "legend_labels",
                    "histogram_bins", "histogram_opacity", "bar_mode"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "correlation": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "heatmap_colorscale", "colorbar_range", "colorbar_title",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick"],
    },
    "time_series": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "subtitle", "axes_labels", "legend_labels",
                    "line_width", "line_shape", "show_markers", "line_fill",
                    "show_value_labels"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "scatter_plot": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "subtitle", "axes_labels", "legend_labels",
                    "marker_opacity", "marker_size", "show_value_labels",
                    "line_width", "show_markers", "line_fill"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "matrix_table": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "table_font_size", "table_font_color",
                    "table_header_font_size", "table_header_color",
                    "table_row_height", "table_header_height",
                    "table_index_align", "table_data_align", "table_show_footer",
                    "table_gradient_cells", "table_show_row_totals",
                    "table_stripe_even_color", "table_stripe_odd_color",
                    "table_number_format", "table_show_borders",
                    "row_index_header"],
        "typography": ["family", "font_style", "header", "subtitle"],
    },
    "matrix_heatmap": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "heatmap_colorscale", "colorbar_range", "colorbar_title",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color",
                    "heatmap_font_size", "heatmap_header_size",
                    "heatmap_cell_height", "heatmap_header_height"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick"],
    },
    "map_plot": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "show_colorbar", "colorbar_title",
                    "colorbar_range", "heatmap_colorscale",
                    "marker_opacity", "marker_size"],
        "typography": ["family", "font_style", "header", "subtitle"],
    },
    "pie_chart": {
        "has_axes": False, "has_legend": True,
        "controls": ["title", "subtitle", "legend_labels",
                    "donut_hole", "pie_textinfo", "pull_slices",
                    "pie_rotation", "pie_direction"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "legend_title", "legend_item"],
    },
}




def get_chart_type_capabilities(chart_type: str) -> dict[str, Any]:
    return CHART_TYPE_SETTINGS.get(chart_type, {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle"],
        "typography": ["family", "font_style", "header", "subtitle"],
    })




def has_control(chart_type: str, control: str) -> bool:
    return control in get_chart_type_capabilities(chart_type).get("controls", [])




def has_typography(chart_type: str, typo_category: str) -> bool:
    return typo_category in get_chart_type_capabilities(chart_type).get("typography", [])




def compute_meta_hash(meta: dict | None) -> str:
    if not meta:
        return ""
    relevant = {}
    for key in ("custom_title", "subtitle", "x_label", "y_label",
                "legend_title", "legend_names", "display_options",
                "colorbar_zmin", "colorbar_zmax", "show_auto_insights",
                "hidden_insights"):
        if key in meta:
            relevant[key] = meta[key]
            

    if "text_style" in meta:
        ts = meta["text_style"]
        if isinstance(ts, dict):
            relevant["text_style"] = {k: v for k, v in ts.items()}
            

    return json.dumps(relevant, sort_keys=True, default=str)




def default_text_style() -> dict:
    return {
        "family":             "Inter",
        "font_style":         "Normal",
        "header_size":        28,
        "header_color":       "#6163df",
        "header_family":      "Inter",
        "header_font_style":  "Normal",
        "subtitle_size":      11,
        "subtitle_color":     "#64748b",
        "subtitle_family":    "Inter",
        "subtitle_font_style":"Normal",
        "legend_title_size":  12,
        "legend_title_color": "#cbd5e1",
        "legend_item_size":   11,
        "legend_item_color":  "#e2e8f0",
        "axis_title_size":    12,
        "axis_title_color":   "#cbd5e1",
        "axis_tick_size":     10,
        "axis_tick_color":    "#94a3b8",
        "legend_bgcolor":     "rgba(0,0,0,0)",
    }




def available_font_families() -> list[str]:
    """Return system font families from a clean, curated list of Linux-friendly open-source fonts."""
    return [
        "Inter",
        "Sora",
        "Source Sans 3",
        "Noto Sans",
        "DejaVu Sans",
        "Lato",
        "Ubuntu",
        "Arial",
        "Calibri",
        "Verdana",
        "Oswald",
        "Barlow Condensed",
        "Noto Serif",
        "DejaVu Serif",
        "EB Garamond",
        "Georgia",
        "Times New Roman",
        "Fira Code",
        "DejaVu Sans Mono",
        "JetBrains Mono",
        "Liberation Mono",
        "Courier New",
        "Comic Sans MS",
        "Impact",
        "Trebuchet MS",
        "Helvetica",
        "Palatino Linotype",
        "Candara",
        "Corbel",
        "Constantia",
        "Lucida Console",
        "Consolas",
        "Cambria",
    ]




def _wrap_html_style(text: str, style: str) -> str:
    text = str(text or "")
    style = str(style or "").lower()
    if text == "" or style in ("", "normal"):
        return text
    text = re.sub(r"</?(?:b|i|u)>", "", text)
    if "bold" in style:
        text = f"<b>{text}</b>"
    if "italic" in style:
        text = f"<i>{text}</i>"
    if "underline" in style:
        text = f"<u>{text}</u>"
    return text




def merge_text_style(raw: dict | None) -> dict:
    style = default_text_style()
    if not isinstance(raw, dict):
        return style
    for key, value in raw.items():
        if key in style and value not in (None, ""):
            style[key] = value
    return style




def trace_capabilities(fig, chart_type: str = "") -> dict[str, Any]:
    types = {str(getattr(t, "type", "")).lower() for t in getattr(fig, "data", [])}
    return {
        "has_bar":       "bar" in types or "histogram" in types,
        "has_histogram": "histogram" in types,
        "has_scatter":   "scatter" in types or "scattergl" in types,
        "has_line":      any(
            "lines" in str(getattr(t, "mode", "") or "").lower()
            for t in getattr(fig, "data", [])
        ),
        "has_pie":       bool(types & {"pie", "sunburst", "treemap"}),
        "has_heatmap":   bool(types & {"heatmap", "choropleth", "scattermapbox", "scattermap"}) or chart_type == "matrix_heatmap",
        "has_table":     "table" in types or chart_type == "matrix_table",
        "has_legend":    sum(
            1 for t in getattr(fig, "data", []) if getattr(t, "name", None)
        ) > 1,
    }




def _float_or_none(value) -> float | None:
    try:
        text = str(value).strip()
        return float(text) if text else None
    except Exception:
        return None




def _option_index(options: list[str], value: str, default: str) -> int:
    try:
        return options.index(value)
    except ValueError:
        try:
            return options.index(default)
        except ValueError:
            return 0




def apply_chart_display_options(
    fig,
    meta: dict | None,
    chart_type: str = "",
    *,
    _inplace: bool = False,
):
    meta = meta or {}
    opts = meta.get("display_options", {})
    if not isinstance(opts, dict):
        opts = {}
    f2 = fig if _inplace else copy.deepcopy(fig)


    try:
        text_style = meta.get("text_style", {})
        ts = merge_text_style(text_style)
        

        _raw_family  = str(ts.get("family", "Inter"))
        _font_family = resolve_font_stack(_raw_family)
        _font_style  = str(ts.get("font_style", "Normal"))


        if "show_legend" in opts:
            f2.update_layout(showlegend=bool(opts["show_legend"]))
        if "bar_gap" in opts:
            f2.update_layout(bargap=float(opts["bar_gap"]))
        if opts.get("bar_mode"):
            f2.update_layout(barmode=str(opts["bar_mode"]))


        show_labels = bool(opts.get("show_value_labels", False))
        label_pos   = opts.get("label_position", "outside")


        for tr in f2.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            mode  = str(getattr(tr, "mode", "") or "")


            if ttype == "bar":
                tr.textposition = label_pos if show_labels else "none"
                if show_labels and opts.get("value_label_color"):
                    try:
                        tr.textfont = dict(getattr(tr, "textfont", None) or {}, color=str(opts["value_label_color"]))
                    except Exception:
                        pass


            if ttype in ("scatter", "scattergl") and "lines" in mode:
                if show_labels:
                    if "text" not in mode:
                        tr.mode = mode + "+text"
                    tr.textposition = "top center"
                    if opts.get("value_label_color"):
                        try:
                            tr.textfont = dict(
                                getattr(tr, "textfont", None) or {},
                                color=str(opts["value_label_color"]),
                            )
                        except Exception:
                            pass
                else:
                    tr.mode = (
                        mode.replace("+text", "").replace("text+", "").replace("text", "")
                    ) or "lines"


            if ttype == "histogram":
                nbins = opts.get("histogram_bins")
                if nbins:
                    tr.nbinsx = int(nbins)
                if opts.get("histogram_opacity") is not None:
                    tr.opacity = float(opts["histogram_opacity"])


            if ttype in ("scatter", "scattergl", "scattermap", "scattermapbox"):
                if opts.get("marker_opacity") is not None and hasattr(tr, "marker"):
                    tr.marker.opacity = float(opts["marker_opacity"])
                if opts.get("marker_size") is not None and hasattr(tr, "marker"):
                    tr.marker.size = int(opts["marker_size"])
                if "lines" in mode:
                    if opts.get("line_width") is not None:
                        tr.line.width = int(opts["line_width"])
                    if opts.get("line_shape"):
                        tr.line.shape = str(opts["line_shape"])
                    fill = opts.get("line_fill", "none")
                    tr.fill = fill if fill and fill != "none" else "none"
                if "markers" in mode and opts.get("show_markers") is False:
                    tr.mode = (
                        mode.replace("+markers", "")
                            .replace("markers+", "")
                            .replace("markers", "lines")
                    )


            if ttype in ("pie", "sunburst", "treemap"):
                if opts.get("donut_hole") is not None and hasattr(tr, "hole"):
                    tr.hole = float(opts["donut_hole"])
                if opts.get("pie_textinfo"):
                    tr.textinfo = str(opts["pie_textinfo"])
                if opts.get("pull_slices") is not None and ttype == "pie":
                    tr.pull = float(opts["pull_slices"])
                if opts.get("pie_rotation") is not None and hasattr(tr, "rotation"):
                    tr.rotation = int(opts["pie_rotation"])
                if opts.get("pie_direction") and hasattr(tr, "direction"):
                    tr.direction = str(opts["pie_direction"])
                _pie_lbl_clr = opts.get("pie_label_color")
                _pie_lbl_sz  = opts.get("pie_label_size")
                if _pie_lbl_clr or _pie_lbl_sz:
                    for _pf_attr in ("insidetextfont", "outsidetextfont", "textfont"):
                        if hasattr(tr, _pf_attr):
                            _pf = getattr(tr, _pf_attr, None)
                            _upd = {}
                            if _pie_lbl_clr and _pie_lbl_clr != "auto":
                                _upd["color"] = _pie_lbl_clr
                            if _pie_lbl_sz:
                                _upd["size"] = int(_pie_lbl_sz)
                            if _upd:
                                try:
                                    if isinstance(_pf, dict):
                                        _pf.update(_upd)
                                    else:
                                        for _k, _v in _upd.items():
                                            setattr(_pf, _k, _v)
                                except Exception:
                                    pass


            if ttype in ("heatmap", "choropleth"):
                if opts.get("heatmap_colorscale"):
                    tr.colorscale = str(opts["heatmap_colorscale"])
                zmin_val = _float_or_none(opts.get("colorbar_zmin"))
                zmax_val = _float_or_none(opts.get("colorbar_zmax"))
                if zmin_val is not None:
                    tr.zmin = zmin_val
                if zmax_val is not None:
                    tr.zmax = zmax_val
                show_text = opts.get("heatmap_show_text")
                if show_text is False:
                    tr.text         = None
                    tr.texttemplate = None
                else:
                    prec = int(opts.get("heatmap_annotation_precision", 2))
                    existing_tmpl = getattr(tr, "texttemplate", None)
                    if isinstance(existing_tmpl, str) and "%{z" in existing_tmpl:
                        import re as _re
                        tr.texttemplate = _re.sub(
                            r"%\{z:[^}]*\}", f"%{{z:.{prec}f}}", existing_tmpl
                        ) if "%{z:" in existing_tmpl else f"%{{z:.{prec}f}}"
                    else:
                        fmt = f"{{:.{prec}f}}"
                        z_raw = getattr(tr, "z", None)
                        z_arr = None
                        try:
                            import numpy as _np, base64 as _b64
                            import pandas as _pd
                            if isinstance(z_raw, dict) and "bdata" in z_raw:
                                _dtype_map = {
                                    "f8": "<f8", "f4": "<f4",
                                    "i4": "<i4", "i8": "<i8",
                                }
                                _dtype = _np.dtype(
                                    _dtype_map.get(z_raw.get("dtype", "f8"), z_raw.get("dtype", "<f8"))
                                )
                                _shape = tuple(
                                    int(s) for s in str(z_raw.get("shape", "")).split(",") if s.strip()
                                )
                                _arr = _np.frombuffer(_b64.b64decode(z_raw["bdata"]), dtype=_dtype)
                                z_arr = _arr.reshape(_shape) if _shape else _arr
                            elif isinstance(z_raw, _pd.DataFrame):
                                z_arr = z_raw.values
                            elif z_raw is not None:
                                z_arr = z_raw
                        except Exception:
                            pass
                        if z_arr is not None:
                            new_text = []
                            for row in z_arr:
                                new_row = []
                                for v in row:
                                    try:
                                        new_row.append(fmt.format(float(v)))
                                    except (TypeError, ValueError):
                                        new_row.append(str(v) if v is not None else "")
                                new_text.append(new_row)
                            tr.text = new_text
                            tr.texttemplate = "%{text}"
                ann_size       = opts.get("heatmap_annotation_size")
                ann_color_mode = opts.get("heatmap_annotation_color", "auto")
                if ann_color_mode == "auto":
                    try:
                        z_vals = [v for row in (tr.z or []) for v in (row or []) if v is not None]
                        if z_vals:
                            z_mid   = (min(z_vals) + max(z_vals)) / 2
                            z_range = max(z_vals) - min(z_vals) or 1
                            norm_mid = (z_mid - min(z_vals)) / z_range
                            ann_color = "white" if norm_mid < 0.55 else "#1e293b"
                        else:
                            ann_color = "white"
                    except Exception:
                        ann_color = "white"
                else:
                    ann_color = {"light": "white", "dark": "#1e293b"}.get(ann_color_mode)
                if ann_size is not None or ann_color is not None:
                    existing_tf = getattr(tr, "textfont", None)
                    _tf_family = getattr(existing_tf, "family", None) or None
                    new_tf: dict = {
                        "size":  getattr(existing_tf, "size",  10) or 10,
                        "color": getattr(existing_tf, "color", "white") or "white",
                    }
                    if _tf_family:
                        new_tf["family"] = _tf_family
                    if ann_size  is not None: new_tf["size"]  = int(ann_size)
                    if ann_color is not None: new_tf["color"] = ann_color
                    tr.textfont = new_tf


            if ttype == "table":
                _hdr_vals = getattr(tr.header, "values", None) or []
                _is_footer_trace = all(
                    str(v).strip() in ("", "[]", "None")
                    for v in _hdr_vals
                ) and len(_hdr_vals) > 0
                if _is_footer_trace:
                    continue


                cell_size    = int(opts.get("table_font_size", 11))
                header_size  = int(opts.get("table_header_font_size", max(cell_size, 12)))
                row_h        = int(opts.get("table_row_height", 26))
                hdr_h        = max(int(opts.get("table_header_height", 22)), header_size + 12)
                idx_align    = opts.get("table_index_align", "left")
                data_align   = opts.get("table_data_align", "right")
                

                tr.cells.font = dict(size=cell_size, color=str(opts.get("table_font_color", "#f1f5f9")), family=_font_family)
                tr.header.font = dict(size=header_size, color="white", family=_font_family)
                

                if hasattr(tr.header, "values") and tr.header.values:
                    tr.header.values = [_wrap_html_style(str(v), _font_style) for v in tr.header.values]
                if hasattr(tr.cells, "values") and tr.cells.values:
                    tr.cells.values = [
                        [_wrap_html_style(str(v), _font_style) for v in col]
                        for col in tr.cells.values
                    ]


                tr.cells.height  = row_h
                tr.header.height = hdr_h
                if hasattr(tr.cells, "align") and hasattr(tr.header, "values"):
                    n_hdr_cols = len(tr.header.values) if tr.header.values else 0
                    if n_hdr_cols > 1:
                        tr.cells.align  = [idx_align] + [data_align] * (n_hdr_cols - 1)
                        tr.header.align = [idx_align] + ["center"] * (n_hdr_cols - 1)


                hdr_color = opts.get("table_header_color")
                if hdr_color and hasattr(tr.header, "values"):
                    n_hdr = len(tr.header.values) if tr.header.values else 0
                    if n_hdr > 0:
                        new_hdr_fills = [hdr_color] * n_hdr
                        tr.header.fill.color = new_hdr_fills


                hdr_text_color = opts.get("table_header_text_color")
                if hdr_text_color and hasattr(tr.header, "font"):
                    try:
                        tr.header.font.color = str(hdr_text_color)
                    except Exception:
                        pass


                stripe_even = opts.get("table_stripe_even_color")
                stripe_odd  = opts.get("table_stripe_odd_color")
                if (stripe_even or stripe_odd) and hasattr(tr.cells, "values"):
                    n_rows = len(tr.cells.values[0]) if tr.cells.values else 0
                    _even = stripe_even or "#1e293b"
                    _odd  = stripe_odd  or "#0f172a"
                    n_cols_t = len(tr.cells.values)
                    tr.cells.fill.color = [
                        [_even if ri % 2 == 0 else _odd for ri in range(n_rows)]
                        for _ in range(n_cols_t)
                    ]
                elif opts.get("table_gradient_cells") is False:
                    n_rows = len(tr.cells.values[0]) if tr.cells.values else 0
                    flat_fills = ["#1e293b" if i % 2 == 0 else "#0f172a" ]
                    tr.cells.fill.color = [flat_fills] * len(tr.cells.values)


            if hasattr(tr, "textfont") and tr.textfont:
                tr.textfont.family = _font_family


        _leg_title = meta.get("legend_title", "")
        if _leg_title:
            f2.update_layout(legend_title_text=_leg_title)


        _fs_lower = _font_style.lower()
        _weight = "normal"
        _style = "normal"
        if "bold" in _fs_lower:
            _weight = "bold"
        if "italic" in _fs_lower:
            _style = "italic"
        _font_style_dict = dict(family=_font_family, weight=_weight, style=_style)
        

        f2.update_layout(
            font=_font_style_dict,
            title=dict(font=_font_style_dict),
            legend=dict(
                title=dict(font=_font_style_dict),
                font=_font_style_dict,
            ),
        )
        

        f2.update_xaxes(
            title=dict(font=_font_style_dict),
            tickfont=_font_style_dict,
        )
        f2.update_yaxes(
            title=dict(font=_font_style_dict),
            tickfont=_font_style_dict,
        )


        show_footer  = opts.get("table_show_footer", True)
        table_traces = [
            t for t in f2.data
            if str(getattr(t, "type", "")).lower() == "table"
        ]
        _footer_trs = [
            t for t in table_traces
            if all(str(v).strip() in ("", "[]", "None")
                   for v in (getattr(t.header, "values", None) or []))
            and len(getattr(t.header, "values", None) or []) > 0
        ]
        if _footer_trs:
            footer_tr = _footer_trs[0]
            if not show_footer:
                footer_tr.cells.height  = 0
                footer_tr.header.height = 0
            else:
                if (footer_tr.cells.height or 0) == 0:
                    footer_tr.cells.height  = 28
                    footer_tr.header.height = 0


        text_style = meta.get("text_style", {})
        if isinstance(text_style, dict) and text_style:
            ts = merge_text_style(text_style)


            _hdr_family_raw = str(ts.get("header_family", _raw_family))
            _hdr_family     = resolve_font_stack(_hdr_family_raw)
            _hdr_style      = str(ts.get("header_font_style", "Normal"))
            _hdr_size       = int(ts.get("header_size", 28))
            _hdr_color      = str(ts.get("header_color", "#6163df"))


            _sub_family_raw = str(ts.get("subtitle_family", _raw_family))
            _sub_family     = resolve_font_stack(_sub_family_raw)
            _sub_style      = str(ts.get("subtitle_font_style", "Normal"))
            _sub_size       = int(ts.get("subtitle_size", 11))
            _sub_color      = str(ts.get("subtitle_color", "#64748b"))


            _ax_title_size  = int(ts.get("axis_title_size", 12))
            _ax_title_color = str(ts.get("axis_title_color", "#cbd5e1"))
            _ax_tick_size   = int(ts.get("axis_tick_size", 10))
            _ax_tick_color  = str(ts.get("axis_tick_color", "#94a3b8"))
            _leg_title_size  = int(ts.get("legend_title_size", 12))
            _leg_title_color = str(ts.get("legend_title_color", "#cbd5e1"))
            _leg_item_size   = int(ts.get("legend_item_size", 11))
            _leg_item_color  = str(ts.get("legend_item_color", "#e2e8f0"))


            for tr in f2.data:
                ttype = str(getattr(tr, "type", "") or "").lower()
                if ttype == "table":
                    continue
                for font_attr in ("textfont", "insidetextfont", "outsidetextfont"):
                    if hasattr(tr, font_attr):
                        existing_font = getattr(tr, font_attr, None)
                        new_font = dict(size=getattr(existing_font, "size", 11) or 11,
                                        color=getattr(existing_font, "color", "#e2e8f0") or "#e2e8f0")
                        new_font["family"] = _font_family
                        if ttype != "heatmap":
                            tr_style = str(ts.get("font_style", "Normal"))
                            txt = getattr(tr, "text", None)
                            if txt is not None and isinstance(txt, (list, tuple)) and len(txt) <= 500:
                                tr.text = [_wrap_html_style(str(v) if v is not None else "", tr_style) for v in txt]
                        setattr(tr, font_attr, new_font)


            try:
                _title_text = f2.layout.title.text if hasattr(f2.layout, "title") and f2.layout.title else ""
                if _title_text and _hdr_style != "Normal":
                    _title_text = _wrap_html_style(str(_title_text), _hdr_style)
                f2.update_layout(
                    title=dict(
                        text=_title_text,
                        font=dict(size=_hdr_size, color=_hdr_color, family=_hdr_family),
                        subtitle=dict(
                            font=dict(size=_sub_size, color=_sub_color, family=_sub_family),
                        ),
                    ),
                )
                try:
                    _sub_obj = f2.layout.title.subtitle
                    if _sub_obj and hasattr(_sub_obj, "text") and _sub_obj.text:
                        _sub_text = _wrap_html_style(str(_sub_obj.text), _sub_style)
                        if _sub_text != _sub_obj.text:
                            f2.update_layout(title_subtitle_text=_sub_text)
                except Exception:
                    pass
            except Exception:
                pass


            _is_map_chart = chart_type in ("map_plot",) or any(
                str(getattr(t, "type", "")).lower() in ("choropleth", "scattermapbox", "scattermap")
                for t in f2.data
            )
            if not _is_map_chart:
                axis_title_font = dict(size=_ax_title_size, color=_ax_title_color, family=_font_family, weight=_weight, style=_style)
                axis_tick_font  = dict(size=_ax_tick_size,  color=_ax_tick_color,  family=_font_family, weight=_weight, style=_style)
                f2.update_xaxes(title_font=axis_title_font, tickfont=axis_tick_font)
                f2.update_yaxes(title_font=axis_title_font, tickfont=axis_tick_font)


            _leg_bgcolor = str(ts.get("legend_bgcolor", "rgba(0,0,0,0)"))
            f2.update_layout(
                legend=dict(
                    bgcolor=_leg_bgcolor,
                    title_font=dict(size=_leg_title_size, color=_leg_title_color, family=_font_family, weight=_weight, style=_style),
                    font=dict(size=_leg_item_size, color=_leg_item_color, family=_font_family, weight=_weight, style=_style),
                )
            )


        if chart_type in ("matrix_heatmap", "correlation", "map_plot"):
            if chart_type == "map_plot":
                cb_tick_sz   = int(opts.get("colorbar_tick_size", 10))
                cb_tick_col  = str(opts.get("colorbar_tick_color", "#94a3b8"))
                cb_title_sz  = int(opts.get("colorbar_title_size", 11))
                cb_title_col = str(opts.get("colorbar_title_color", "#cbd5e1"))
                cb_family    = resolve_font_stack(str(opts.get("colorbar_font_family", _raw_family)))
                cb_title     = opts.get("colorbar_title", "")
                _cb_font_suffix = dict(weight=_weight, style=_style)
                for tr in f2.data:
                    try:
                        tr.colorbar.tickfont = dict(
                            size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix)
                        if cb_title:
                            tr.colorbar.title.text = cb_title
                        tr.colorbar.title.font = dict(
                            size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix)
                    except Exception:
                        pass
                try:
                    cb_kwargs = dict(
                        tickfont=dict(size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix),
                    )
                    if cb_title:
                        cb_kwargs["title"] = dict(text=cb_title, font=dict(size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix))
                    f2.update_coloraxes(colorbar=cb_kwargs)
                except Exception:
                    pass
            else:
                for tr in f2.data:
                    ttype_for_cb = str(getattr(tr, "type", "")).lower()
                    if ttype_for_cb not in ("heatmap", "choropleth"):
                        continue
                    cell_sz      = int(opts.get("heatmap_font_size", 10))
                    hdr_sz       = int(opts.get("heatmap_header_size", 10))
                    cb_tick_sz   = int(opts.get("colorbar_tick_size", 10))
                    cb_tick_col  = str(opts.get("colorbar_tick_color", "#94a3b8"))
                    cb_title_sz  = int(opts.get("colorbar_title_size", 11))
                    cb_title_col = str(opts.get("colorbar_title_color", "#cbd5e1"))
                    cb_family    = resolve_font_stack(str(opts.get("colorbar_font_family", _raw_family)))
                    cb_title     = opts.get("colorbar_title", "")
                    _ann_sz  = opts.get("heatmap_annotation_size")
                    final_sz = int(_ann_sz) if _ann_sz is not None else cell_sz
                    _cb_font_suffix = dict(weight=_weight, style=_style)
                    try:
                        tf = getattr(tr, "textfont", None)
                        if tf is not None:
                            new_tf: dict = {
                                "size":  final_sz,
                                "color": getattr(tf, "color", "white") or "white",
                                "family": cb_family,
                            }
                            new_tf.update(_cb_font_suffix)
                            tr.textfont = new_tf
                    except Exception:
                        pass
                    f2.update_xaxes(tickfont=dict(size=hdr_sz, family=cb_family, **_cb_font_suffix))
                    f2.update_yaxes(tickfont=dict(size=hdr_sz, family=cb_family, **_cb_font_suffix))
                    try:
                        tr.colorbar.tickfont = dict(
                            size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix)
                        if cb_title:
                            tr.colorbar.title.text = cb_title
                        tr.colorbar.title.font = dict(
                            size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix)
                    except Exception:
                        pass


    except Exception:
        return fig


    return f2




def render_typography_controls(
    uid: str,
    fig: Any,
    chart_type: str,
    meta: dict | None,
    key_prefix: str = "analysis",
) -> dict:
    meta       = meta or {}
    text_style = merge_text_style(meta.get("text_style", {}))
    opts = dict(
        meta.get("display_options", {})
        if isinstance(meta.get("display_options", {}), dict)
        else {}
    )
    caps = trace_capabilities(fig, chart_type)
    _has_axes = any((caps.get(k) for k in ("has_bar", "has_scatter", "has_line", "has_histogram", "has_heatmap"))) or chart_type == "correlation"


    inject_font_preview_css()


    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Sizes**")
        font_styles_list = [
            "Normal", "Bold", "Italic", "Underline",
            "Bold Italic", "Bold Underline", "Italic Underline",
            "Bold Italic Underline",
        ]


        current_family = str(text_style.get("family", "Inter"))
        text_style["family"] = font_select(
            "Global / Axis Font family",
            default=current_family,
            key=f"{key_prefix}_font_{uid}",
        )
        text_style["font_style"] = st.selectbox(
            "Global / Axis Font style",
            font_styles_list,
            index=_option_index(
                font_styles_list,
                str(text_style.get("font_style", "Normal")),
                "Normal",
            ),
            key=f"{key_prefix}_font_style_{uid}",
            help="Choose a text style for axis labels, ticks, and legends.",
        )


        st.markdown("**Header (Title) Typography**")
        current_hdr_family = str(text_style.get("header_family", current_family))
        text_style["header_family"] = font_select(
            "Header Font family",
            default=current_hdr_family,
            key=f"{key_prefix}_hfont_{uid}",
        )
        text_style["header_font_style"] = st.selectbox(
            "Header Font style",
            font_styles_list,
            index=_option_index(
                font_styles_list,
                str(text_style.get("header_font_style", "Normal")),
                "Normal",
            ),
            key=f"{key_prefix}_hfont_style_{uid}",
        )
        text_style["header_size"]   = st.slider("Header size",   8, 40, int(text_style["header_size"]),   key=f"{key_prefix}_hsize_{uid}")


        st.markdown("**Subtitle Typography**")
        current_sub_family = str(text_style.get("subtitle_family", current_family))
        text_style["subtitle_family"] = font_select(
            "Subtitle Font family",
            default=current_sub_family,
            key=f"{key_prefix}_subfont_{uid}",
        )
        text_style["subtitle_font_style"] = st.selectbox(
            "Subtitle Font style",
            font_styles_list,
            index=_option_index(
                font_styles_list,
                str(text_style.get("subtitle_font_style", "Normal")),
                "Normal",
            ),
            key=f"{key_prefix}_subfont_style_{uid}",
        )
        text_style["subtitle_size"] = st.slider("Subtitle size",  8, 24, int(text_style["subtitle_size"]), key=f"{key_prefix}_ssize_{uid}")


        _non_axis_types = ("map_plot", "matrix_table")
        _show_axis_typo = _has_axes and chart_type not in _non_axis_types
        _hide_legend_controls = chart_type in (
            "matrix_table", "matrix_heatmap", "map_plot",
            "heatmap", "choropleth", "correlation",
        )
        _show_colorbar_typo = False


        if _show_axis_typo or not _hide_legend_controls:
            st.markdown("**Label Sizing**")
        if _show_axis_typo:
            text_style["axis_title_size"] = st.slider("Axis title size",  8, 24, int(text_style["axis_title_size"]), key=f"{key_prefix}_atsize_{uid}")
            text_style["axis_tick_size"]  = st.slider("Axis tick size",   8, 18, int(text_style["axis_tick_size"]),  key=f"{key_prefix}_ticksize_{uid}")
        if not _hide_legend_controls:
            text_style["legend_title_size"] = st.slider("Legend title size", 8, 20, int(text_style["legend_title_size"]), key=f"{key_prefix}_ltsz_{uid}")
            text_style["legend_item_size"]  = st.slider("Legend item size",  8, 18, int(text_style["legend_item_size"]),  key=f"{key_prefix}_lisz_{uid}")
        if _show_colorbar_typo:
            st.markdown("**Colour scale**")
            opts["colorbar_tick_size"]  = st.slider("Colorbar tick size",  8, 18,
                int(opts.get("colorbar_tick_size", 10)),
                key=f"{key_prefix}_cb_tick_sz_{uid}")
            opts["colorbar_title_size"] = st.slider("Colorbar title size", 8, 20,
                int(opts.get("colorbar_title_size", 11)),
                key=f"{key_prefix}_cb_title_sz_{uid}")
    with t2:
        st.markdown("**Colours**")
        text_style["header_color"]   = st.color_picker("Header colour",   str(text_style["header_color"]),   key=f"{key_prefix}_hcolor_{uid}")
        text_style["subtitle_color"] = st.color_picker("Subtitle colour", str(text_style["subtitle_color"]), key=f"{key_prefix}_scolor_{uid}")
        if _show_axis_typo:
            text_style["axis_title_color"] = st.color_picker("Axis title colour", str(text_style["axis_title_color"]), key=f"{key_prefix}_atcolor_{uid}")
            text_style["axis_tick_color"]  = st.color_picker("Axis tick colour",  str(text_style["axis_tick_color"]),  key=f"{key_prefix}_tickcolor_{uid}")
        if not _hide_legend_controls:
            text_style["legend_title_color"] = st.color_picker("Legend title colour", str(text_style["legend_title_color"]), key=f"{key_prefix}_ltcolor_{uid}")
            text_style["legend_item_color"]  = st.color_picker("Legend item colour",  str(text_style["legend_item_color"]),  key=f"{key_prefix}_licolor_{uid}")
            _legbg_default = str(text_style.get("legend_bgcolor", "#1e293b"))
            if _legbg_default.startswith("rgba") or _legbg_default == "transparent":
                _legbg_default = "#1e293b"
            _legbg_transparent = st.checkbox(
                "Transparent legend background",
                value=text_style.get("legend_bgcolor", "") in ("rgba(0,0,0,0)", "transparent", ""),
                key=f"{key_prefix}_legbg_transparent_{uid}",
            )
            if not _legbg_transparent:
                text_style["legend_bgcolor"] = st.color_picker(
                    "Legend background colour",
                    _legbg_default,
                    key=f"{key_prefix}_legbg_{uid}",
                )
            else:
                text_style["legend_bgcolor"] = "rgba(0,0,0,0)"
        if _show_colorbar_typo:
            opts["colorbar_tick_color"]  = st.color_picker("Colorbar tick colour",
                str(opts.get("colorbar_tick_color", "#94a3b8")),
                key=f"{key_prefix}_cb_tick_col_{uid}")
            opts["colorbar_title_color"] = st.color_picker("Colorbar title colour",
                str(opts.get("colorbar_title_color", "#cbd5e1")),
                key=f"{key_prefix}_cb_title_col_{uid}")
            opts["colorbar_font_family"] = font_select(
                "Colorbar font family",
                default=opts.get("colorbar_font_family", "Inter"),
                key=f"{key_prefix}_cb_font_fam_{uid}",
            )


    return text_style




def render_chart_settings_controls(
    uid: str,
    title: str,
    fig,
    chart_type: str,
    meta: dict,
    auto_insights,
    *,
    key_prefix: str,
    show_text_style: bool = True,
) -> dict:
    caps = trace_capabilities(fig, chart_type)
    opts = dict(
        meta.get("display_options", {})
        if isinstance(meta.get("display_options", {}), dict)
        else {}
    )


    nt = st.text_input(
        "Chart Title",
        value=meta.get("custom_title", "") or title,
        key=f"{key_prefix}_title_{uid}",
    )
    a, b = st.columns(2)
    with a:
        sub = st.text_input(
            "Subtitle", value=meta.get("subtitle", ""),
            placeholder="Optional", key=f"{key_prefix}_sub_{uid}",
        )
    with b:
        _legend_applicable = caps["has_legend"] and chart_type not in ("matrix_heatmap",)
        show_legend = st.checkbox(
            "Show legend",
            value=bool(opts.get("show_legend", True)),
            key=f"{key_prefix}_legend_show_{uid}",
            disabled=not _legend_applicable,
        )


    c, d = st.columns(2)
    _has_axes = any((caps.get(k) for k in ("has_bar", "has_scatter", "has_line", "has_histogram", "has_heatmap"))) or chart_type == "correlation"
    if chart_type == "matrix_table":
        with c:
            xl = st.text_input("Row Index Header", value=meta.get("x_label", ""), key=f"{key_prefix}_x_{uid}")
        yl = meta.get("y_label", "")
    elif chart_type == "matrix_heatmap":
        with c:
            xl = st.text_input("Row Index Header",      value=meta.get("x_label", ""), key=f"{key_prefix}_x_{uid}")
        with d:
            yl = st.text_input("Column Dimension Header", value=meta.get("y_label", ""), key=f"{key_prefix}_y_{uid}")
    elif chart_type == "map_plot":
        xl = meta.get("x_label", "")
        yl = meta.get("y_label", "")
    elif _has_axes:
        with c:
            xl = st.text_input("X-Axis Label", value=meta.get("x_label", ""), key=f"{key_prefix}_x_{uid}")
        with d:
            yl = st.text_input("Y-Axis Label", value=meta.get("y_label", ""), key=f"{key_prefix}_y_{uid}")
    else:
        xl = meta.get("x_label", "")
        yl = meta.get("y_label", "")


    st.markdown("**Chart-specific options**")
    s1, s2 = st.columns(2)


    with s1:
        if caps["has_bar"] and not caps["has_histogram"]:
            opts["show_value_labels"] = st.checkbox(
                "Value labels",
                value=bool(opts.get("show_value_labels", False)),
                key=f"{key_prefix}_bar_labels_{uid}",
            )
            if opts["show_value_labels"]:
                opts["value_label_color"] = st.color_picker(
                    "Value label colour",
                    value=str(opts.get("value_label_color", "#ffffff")),
                    key=f"{key_prefix}_vl_color_{uid}",
                )
            label_positions = ["outside", "inside", "auto"]
            opts["label_position"] = st.selectbox(
                "Label position", label_positions,
                index=_option_index(label_positions, opts.get("label_position", "outside"), "outside"),
                key=f"{key_prefix}_bar_label_pos_{uid}",
            )
            opts["bar_gap"] = st.slider(
                "Bar spacing", 0.0, 0.8,
                float(opts.get("bar_gap", 0.28)), 0.05,
                key=f"{key_prefix}_bar_gap_{uid}",
            )
            has_multiple_bars = sum(
                1 for t in getattr(fig, "data", [])
                if str(getattr(t, "type", "")).lower() == "bar"
            ) >= 2
            bar_modes = ["group", "stack", "overlay", "relative"]
            opts["bar_mode"] = st.selectbox(
                "Bar mode", bar_modes,
                index=_option_index(bar_modes, opts.get("bar_mode", "group"), "group"),
                key=f"{key_prefix}_bar_mode_{uid}",
                disabled=not has_multiple_bars,
            )


        if caps["has_histogram"]:
            opts["histogram_bins"] = st.slider(
                "Bins", 5, 120, int(opts.get("histogram_bins", 35)),
                key=f"{key_prefix}_hist_bins_{uid}",
            )
            opts["histogram_opacity"] = st.slider(
                "Opacity", 0.15, 1.0, float(opts.get("histogram_opacity", 0.75)), 0.05,
                key=f"{key_prefix}_hist_opacity_{uid}",
            )


        if caps["has_scatter"]:
            opts["marker_opacity"] = st.slider(
                "Marker opacity", 0.1, 1.0,
                float(opts.get("marker_opacity", 0.75)), 0.05,
                key=f"{key_prefix}_marker_opacity_{uid}",
            )
            opts["marker_size"] = st.slider(
                "Marker size", 3, 28, int(opts.get("marker_size", 8)),
                key=f"{key_prefix}_marker_size_{uid}",
            )


        if caps["has_heatmap"]:
            if chart_type == "matrix_heatmap":
                opts["heatmap_header_size"] = st.slider(
                    "Axis label size", 8, 18,
                    int(opts.get("heatmap_header_size", 10)),
                    key=f"{key_prefix}_mh_hdr_sz_{uid}",
                )
                opts["heatmap_cell_height"] = st.slider(
                    "Row height (px)", 20, 60,
                    int(opts.get("heatmap_cell_height", 30)),
                    key=f"{key_prefix}_mh_row_h_{uid}",
                )
            _cs_idx = _option_index(COLORSCALES_ALL, opts.get("heatmap_colorscale", ""), "RdBu")
            opts["heatmap_colorscale"] = st.selectbox(
                "Colour scale", COLORSCALES_ALL, index=_cs_idx,
                key=f"{key_prefix}_heatmap_cs_{uid}",
            )
            if chart_type in ("matrix_heatmap", "correlation"):
                z1, z2 = st.columns(2)
                with z1:
                    opts["colorbar_zmin"] = st.text_input(
                        "Scale min", value=str(opts.get("colorbar_zmin", "")),
                        placeholder="Auto", key=f"{key_prefix}_cb_min_{uid}",
                    )
                with z2:
                    opts["colorbar_zmax"] = st.text_input(
                        "Scale max", value=str(opts.get("colorbar_zmax", "")),
                        placeholder="Auto", key=f"{key_prefix}_cb_max_{uid}",
                    )
            else:
                opts.setdefault("colorbar_zmin", "")
                opts.setdefault("colorbar_zmax", "")
            opts["colorbar_title"] = st.text_input(
                "Colour bar title", value=str(opts.get("colorbar_title", "")),
                key=f"{key_prefix}_cb_title_{uid}",
            )


        if caps["has_table"]:
            opts["table_font_size"] = st.slider(
                "Cell text size", 9, 18, int(opts.get("table_font_size", 11)),
                key=f"{key_prefix}_table_font_{uid}",
            )
            opts["table_font_color"] = st.color_picker(
                "Cell text colour",
                value=str(opts.get("table_font_color", "#f1f5f9")),
                key=f"{key_prefix}_table_font_color_{uid}",
            )
            opts["table_header_font_size"] = st.slider(
                "Header text size", 9, 20, int(opts.get("table_header_font_size", 12)),
                key=f"{key_prefix}_table_hdr_font_{uid}",
            )
            opts["table_row_height"] = st.slider(
                "Row height (px)", 18, 48, int(opts.get("table_row_height", 26)),
                key=f"{key_prefix}_table_row_h_{uid}",
            )
            opts["table_header_height"] = st.slider(
                "Header height (px)", 22, 60, int(opts.get("table_header_height", 22)),
                key=f"{key_prefix}_table_hdr_h_{uid}",
            )
            opts["table_index_align"] = st.selectbox(
                "Index column align", ["left", "center", "right"],
                index=["left","center","right"].index(opts.get("table_index_align","left")),
                key=f"{key_prefix}_table_idx_align_{uid}",
            )
            opts["table_data_align"] = st.selectbox(
                "Data cells align", ["right", "center", "left"],
                index=["right","center","left"].index(opts.get("table_data_align","right")),
                key=f"{key_prefix}_table_data_align_{uid}",
            )
            st.markdown("**Header colours**")
            opts["table_header_color"] = st.color_picker(
                "Header background",
                value=str(opts.get("table_header_color", "#4f46e5")),
                key=f"{key_prefix}_table_hdr_color_{uid}",
            )
            opts["table_header_text_color"] = st.color_picker(
                "Header text colour",
                value=str(opts.get("table_header_text_color", "#ffffff")),
                key=f"{key_prefix}_table_hdr_text_color_{uid}",
            )
            sc1, sc2 = st.columns(2)
            with sc1:
                opts["table_stripe_even_color"] = st.color_picker(
                    "Even rows",
                    value=str(opts.get("table_stripe_even_color", "#1e293b")),
                    key=f"{key_prefix}_table_stripe_even_{uid}",
                )
            with sc2:
                opts["table_stripe_odd_color"] = st.color_picker(
                    "Odd rows",
                    value=str(opts.get("table_stripe_odd_color", "#0f172a")),
                    key=f"{key_prefix}_table_stripe_odd_{uid}",
                )
            _fmt_options = ["auto", "integer", "2dp", "4dp", "kmb", "percent"]
            _fmt_labels  = {
                "auto": "Auto (original)", "integer": "Integer (1,234)",
                "2dp": "2 decimal (1,234.56)", "4dp": "4 decimal (1,234.5678)",
                "kmb": "K / M / B (1.2K, 3.4M)", "percent": "Percent (12.3%)",
            }
            opts["table_number_format"] = st.selectbox(
                "Number format",
                _fmt_options,
                index=_option_index(_fmt_options, opts.get("table_number_format", "auto"), "auto"),
                format_func=lambda x: _fmt_labels.get(x, x),
                key=f"{key_prefix}_table_num_fmt_{uid}",
            )


    with s2:
        if caps["has_line"]:
            opts["line_width"] = st.slider(
                "Line width", 1, 8, int(opts.get("line_width", 2)),
                key=f"{key_prefix}_line_width_{uid}",
            )
            if chart_type != "scatter_plot":
                line_shapes = ["linear", "spline", "hv", "vh"]
                opts["line_shape"] = st.selectbox(
                    "Line shape", line_shapes,
                    index=_option_index(line_shapes, opts.get("line_shape", "linear"), "linear"),
                    key=f"{key_prefix}_line_shape_{uid}",
                )
            opts["show_markers"] = st.checkbox(
                "Show markers",
                value=bool(opts.get("show_markers", True)),
                key=f"{key_prefix}_line_markers_{uid}",
            )
            fill_opts   = ["none", "tozeroy", "tonexty"]
            fill_labels = {"none": "No fill", "tozeroy": "Fill to zero", "tonexty": "Fill to next trace"}
            opts["line_fill"] = st.selectbox(
                "Area fill", fill_opts,
                index=_option_index(fill_opts, opts.get("line_fill", "none"), "none"),
                format_func=lambda x: fill_labels.get(x, x),
                key=f"{key_prefix}_line_fill_{uid}",
            )


        if caps["has_pie"]:
            opts["donut_hole"] = st.slider(
                "Donut hole", 0.0, 0.7,
                float(opts.get("donut_hole", 0.0)), 0.05,
                key=f"{key_prefix}_donut_{uid}",
            )
            pie_opts = ["label+percent", "label+value", "percent", "label", "value"]
            opts["pie_textinfo"] = st.selectbox(
                "Slice labels", pie_opts,
                index=_option_index(pie_opts, opts.get("pie_textinfo", "label+percent"), "label+percent"),
                key=f"{key_prefix}_pie_text_{uid}",
            )
            opts["pull_slices"] = st.slider(
                "Slice separation", 0.0, 0.12,
                float(opts.get("pull_slices", 0.0)), 0.01,
                key=f"{key_prefix}_pie_pull_{uid}",
            )
            opts["pie_rotation"] = st.slider(
                "First-slice rotation °", 0, 359,
                int(opts.get("pie_rotation", 0)),
                key=f"{key_prefix}_pie_rot_{uid}",
            )
            pie_dirs = ["clockwise", "counterclockwise"]
            opts["pie_direction"] = st.selectbox(
                "Slice direction", pie_dirs,
                index=_option_index(pie_dirs, opts.get("pie_direction", "clockwise"), "clockwise"),
                key=f"{key_prefix}_pie_dir_{uid}",
            )
            st.markdown("**Data label styling**")
            _current_pie_label_color = str(opts.get("pie_label_color", "#f1f5f9"))
            if _current_pie_label_color.lower() in ("auto", ""):
                _current_pie_label_color = "#f1f5f9"
            opts["pie_label_color"] = st.color_picker(
                "Label colour",
                value=_current_pie_label_color,
                key=f"{key_prefix}_pie_label_color_{uid}",
            )
            opts["pie_label_size"] = st.slider(
                "Label size", 8, 20, int(opts.get("pie_label_size", 11)),
                key=f"{key_prefix}_pie_label_sz_{uid}",
            )


        if caps["has_heatmap"] and chart_type not in ("map_plot",):
            _has_existing_text = any(
                getattr(t, "text", None) is not None
                for t in getattr(fig, "data", [])
                if str(getattr(t, "type", "")).lower() == "heatmap"
            )
            _heatmap_checkbox_disabled = (
                False if chart_type in ("correlation", "matrix_heatmap")
                else (not _has_existing_text and not opts.get("heatmap_show_text"))
            )
            opts["heatmap_show_text"] = st.checkbox(
                "Show cell values",
                value=bool(opts.get("heatmap_show_text", _has_existing_text)),
                key=f"{key_prefix}_heatmap_txt_{uid}",
                disabled=_heatmap_checkbox_disabled,
            )
            _text_active = bool(opts.get("heatmap_show_text", _has_existing_text))
            opts["heatmap_annotation_precision"] = st.slider(
                "Value decimal places", 0, 4,
                int(opts.get("heatmap_annotation_precision", 2)),
                key=f"{key_prefix}_heatmap_prec_{uid}",
                disabled=not _text_active,
            )
            opts["heatmap_annotation_size"] = st.slider(
                "Cell text size", 7, 18,
                int(opts.get("heatmap_annotation_size", 10)),
                key=f"{key_prefix}_heatmap_ann_sz_{uid}",
                disabled=not _text_active,
            )
            ann_color_opts   = ["auto", "light", "dark"]
            ann_color_labels = {"auto": "Auto (white)", "light": "Force light", "dark": "Force dark"}
            opts["heatmap_annotation_color"] = st.selectbox(
                "Annotation colour", ann_color_opts,
                index=_option_index(ann_color_opts, opts.get("heatmap_annotation_color", "auto"), "auto"),
                format_func=lambda x: ann_color_labels.get(x, x),
                key=f"{key_prefix}_heatmap_ann_col_{uid}",
                disabled=not _text_active,
            )
        if chart_type in ("matrix_heatmap", "correlation", "map_plot"):
            opts["colorbar_tick_size"] = st.slider(
                "Colorbar tick size", 8, 16,
                int(opts.get("colorbar_tick_size", 10)),
                key=f"{key_prefix}_cb_tick_sz_{uid}",
            )
            opts["colorbar_tick_color"] = st.color_picker(
                "Colorbar tick colour",
                value=str(opts.get("colorbar_tick_color", "#94a3b8")),
                key=f"{key_prefix}_cb_tick_col_{uid}",
            )
            opts["colorbar_title_size"] = st.slider(
                "Colorbar title size", 8, 16,
                int(opts.get("colorbar_title_size", 11)),
                key=f"{key_prefix}_cb_title_sz_{uid}",
            )
            opts["colorbar_title_color"] = st.color_picker(
                "Colorbar title colour",
                value=str(opts.get("colorbar_title_color", "#cbd5e1")),
                key=f"{key_prefix}_cb_title_col_{uid}",
            )
            opts["colorbar_font_family"] = font_select(
                "Colorbar font family",
                default=opts.get("colorbar_font_family", "Inter"),
                key=f"{key_prefix}_cb_family_{uid}",
            )


        if caps["has_table"]:
            opts["table_show_borders"] = st.checkbox(
                "Show cell borders",
                value=bool(opts.get("table_show_borders", True)),
                key=f"{key_prefix}_table_borders_{uid}",
            )
            opts["table_gradient_cells"] = st.checkbox(
                "Conditional cell gradient",
                value=bool(opts.get("table_gradient_cells", True)),
                key=f"{key_prefix}_table_grad_{uid}",
            )


    legend_inputs    = {}
    new_legend_title = meta.get("legend_title", "")
    trace_names, seen = [], set()
    for trace in getattr(fig, "data", []):
        raw = getattr(trace, "name", None)
        if raw is not None and str(raw) not in seen:
            seen.add(str(raw))
            trace_names.append(str(raw))


    if len(trace_names) > 1:
        st.markdown("**Legend labels**")
        new_legend_title = st.text_input(
            "Legend Title", value=meta.get("legend_title", ""),
            key=f"{key_prefix}_legend_title_{uid}",
        )
        saved_legend = meta.get("legend_names", {})
        cols = st.columns(min(len(trace_names), 3))
        for i, name in enumerate(trace_names):
            with cols[i % len(cols)]:
                legend_inputs[name] = st.text_input(
                    f"Label for: {name}", value=saved_legend.get(name, ""),
                    placeholder=name, key=f"{key_prefix}_legend_{uid}_{i}",
                )


    if chart_type != "map_plot":
        show_ai = st.checkbox(
            "Show auto-insights in export",
            value=meta.get("show_auto_insights", True),
            key=f"{key_prefix}_show_ai_{uid}",
        )
    else:
        show_ai = False
    hidden     = set(meta.get("hidden_insights", []))
    new_hidden = set()
    if auto_insights and show_ai:
        st.markdown("**Insights included in export**")
        for i, ins in enumerate(auto_insights):
            label = clean_insight_text(ins)
            if not st.checkbox(
                label[:80] + ("..." if len(label) > 80 else ""),
                value=i not in hidden,
                key=f"{key_prefix}_ins_{uid}_{i}",
            ):
                new_hidden.add(i)


    text_style = merge_text_style(meta.get("text_style", {}))


    return {
        "custom_title":       nt,
        "subtitle":           sub,
        "x_label":            xl,
        "y_label":            yl,
        "show_auto_insights": show_ai,
        "hidden_insights":    list(new_hidden),
        "legend_title":       new_legend_title,
        "legend_names":       {k: v for k, v in legend_inputs.items() if str(v).strip()},
        "text_style":         text_style,
        "display_options":    opts | {"show_legend": show_legend},
        "colorbar_zmin":      opts.get("colorbar_zmin", ""),
        "colorbar_zmax":      opts.get("colorbar_zmax", ""),
    }
