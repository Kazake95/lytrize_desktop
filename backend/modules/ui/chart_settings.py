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
                    "colorbar_range", "colorbar_title",
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
                    "table_index_align", "table_data_align",
                    "table_stripe_even_color", "table_stripe_odd_color",
                    "table_number_format",
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




def _safe_get_font_attr(font_obj, attr: str, default=None):
    """Safely get an attribute from a font object (which could be None, dict, or Plotly object)."""
    if font_obj is None:
        return default
    try:
        val = getattr(font_obj, attr, None)
        return val if val is not None else default
    except Exception:
        return default




def _apply_font_only(fig, meta: dict | None, chart_type: str = ""):
    """Lightweight font-only post-processor — no deepcopy, no trace iteration.

    Only touches ``fig.layout.title.font`` and ``fig.layout.font`` so that
    font-family / size / colour changes for the (suppressed) title and subtitle
    are reflected without the cost of a full ``apply_chart_display_options``.
    Returns the same figure object (mutated in-place).
    """
    if not meta:
        return fig
    text_style = meta.get("text_style", {})
    if not isinstance(text_style, dict) or not text_style:
        return fig
    ts = merge_text_style(text_style)

    _raw_family  = str(ts.get("family", "Inter"))
    _font_family = resolve_font_stack(_raw_family)

    _hdr_family_raw = str(ts.get("header_family") or _raw_family)
    if _hdr_family_raw == "Inter" and _raw_family not in ("Inter", ""):
        _hdr_family_raw = _raw_family
    _hdr_family = resolve_font_stack(_hdr_family_raw)
    _hdr_size   = int(ts.get("header_size", 28))
    _hdr_color  = str(ts.get("header_color", "#6163df"))

    _sub_family_raw = str(ts.get("subtitle_family") or _raw_family)
    if _sub_family_raw == "Inter" and _raw_family not in ("Inter", ""):
        _sub_family_raw = _raw_family
    _sub_family = resolve_font_stack(_sub_family_raw)
    _sub_size   = int(ts.get("subtitle_size", 11))
    _sub_color  = str(ts.get("subtitle_color", "#64748b"))

    _fs_lower = str(ts.get("font_style", "Normal")).lower()
    _weight = "bold" if "bold" in _fs_lower else "normal"
    _style  = "italic" if "italic" in _fs_lower else "normal"

    try:
        fig.update_layout(
            title=dict(
                text="",
                font=dict(size=_hdr_size, color=_hdr_color, family=_hdr_family),
            ),
            font=dict(family=_font_family, weight=_weight, style=_style),
        )
    except Exception:
        pass
    return fig


def _font_only_hash(meta: dict | None) -> str:
    """Compute a hash that only covers font-related meta keys.

    This is used by the multi-level cache to detect "only fonts changed"
    without busting on structural display options.
    """
    if not meta:
        return ""
    text_style = meta.get("text_style", {})
    if not isinstance(text_style, dict):
        return ""
    relevant = {}
    for key in ("family", "font_style", "header_size", "header_color",
                "header_family", "header_font_style", "subtitle_size",
                "subtitle_color", "subtitle_family", "subtitle_font_style"):
        if key in text_style:
            relevant[key] = text_style[key]
    return json.dumps(relevant, sort_keys=True, default=str)


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


        # Capture value label settings early
        _show_value_labels = bool(opts.get("show_value_labels", False))
        _value_label_color = str(opts.get("value_label_color", "#ffffff")) if _show_value_labels else None
        _label_pos = opts.get("label_position", "outside")


        if "show_legend" in opts:
            f2.update_layout(showlegend=bool(opts["show_legend"]))
        if "bar_gap" in opts:
            f2.update_layout(bargap=float(opts["bar_gap"]))
        if opts.get("bar_mode"):
            f2.update_layout(barmode=str(opts["bar_mode"]))


        for tr in f2.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            mode  = str(getattr(tr, "mode", "") or "")


            if ttype == "bar":
                tr.textposition = _label_pos if _show_value_labels else "none"


            if ttype in ("scatter", "scattergl") and "lines" in mode:
                if _show_value_labels:
                    if "text" not in mode:
                        tr.mode = mode + "+text"
                    tr.textposition = "top center"
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
                    _tf_family = _safe_get_font_attr(existing_tf, "family", None)
                    new_tf: dict = {
                        "size":  _safe_get_font_attr(existing_tf, "size", 10) or 10,
                        "color": _safe_get_font_attr(existing_tf, "color", "white") or "white",
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


            # Apply font family to textfont if it exists
            if hasattr(tr, "textfont") and tr.textfont is not None:
                try:
                    tr.textfont.family = _font_family
                except Exception:
                    pass


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


        text_style = meta.get("text_style", {})
        if isinstance(text_style, dict) and text_style:
            ts = merge_text_style(text_style)


            # The global "family" is the master control.  Header / subtitle
            # fonts follow it unless explicitly customized to a non-default.
            _hdr_family_raw = str(ts.get("header_family") or _raw_family)
            if _hdr_family_raw == "Inter" and _raw_family not in ("Inter", ""):
                _hdr_family_raw = _raw_family
            _hdr_family     = resolve_font_stack(_hdr_family_raw)
            _hdr_style      = str(ts.get("header_font_style", "Normal"))
            _hdr_size       = int(ts.get("header_size", 28))
            _hdr_color      = str(ts.get("header_color", "#6163df"))


            _sub_family_raw = str(ts.get("subtitle_family") or _raw_family)
            if _sub_family_raw == "Inter" and _raw_family not in ("Inter", ""):
                _sub_family_raw = _raw_family
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


            # Process text fonts with safe None handling
            for tr in f2.data:
                ttype = str(getattr(tr, "type", "") or "").lower()
                if ttype == "table":
                    continue
                
                # Skip bar/scatter with value labels - we'll handle them separately at the end
                if ttype == "bar" and _show_value_labels:
                    continue
                if ttype in ("scatter", "scattergl") and _show_value_labels:
                    continue
                
                try:
                    for font_attr in ("textfont", "insidetextfont", "outsidetextfont"):
                        if hasattr(tr, font_attr):
                            existing_font = getattr(tr, font_attr, None)
                            _existing_size = _safe_get_font_attr(existing_font, "size", 11) or 11
                            _existing_color = _safe_get_font_attr(existing_font, "color", "#e2e8f0") or "#e2e8f0"
                            new_font = dict(size=_existing_size, color=_existing_color)
                            new_font["family"] = _font_family
                            if ttype != "heatmap":
                                tr_style = str(ts.get("font_style", "Normal"))
                                txt = getattr(tr, "text", None)
                                if txt is not None and isinstance(txt, (list, tuple)) and len(txt) <= 500:
                                    tr.text = [_wrap_html_style(str(v) if v is not None else "", tr_style) for v in txt]
                            setattr(tr, font_attr, new_font)
                except Exception:
                    pass


            # The title/subtitle are rendered in the HTML preview area (chart_card ctrl[0]),
            # so the Plotly native title is suppressed here to avoid the duplicate.
            # Font settings are still applied to other chart elements.
            f2.update_layout(
                title=dict(
                    text="",
                    font=dict(size=_hdr_size, color=_hdr_color, family=_hdr_family),
                ),
            )


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
                                "color": _safe_get_font_attr(tf, "color", "white") or "white",
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

    # ============================================================
    # APPLY VALUE LABEL COLOR LAST - This ensures it always wins
    # ============================================================
    if _show_value_labels and _value_label_color:
        for tr in f2.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            
            if ttype == "bar":
                try:
                    for font_attr in ("textfont", "insidetextfont", "outsidetextfont"):
                        if hasattr(tr, font_attr):
                            existing = getattr(tr, font_attr, None)
                            new_font = dict(
                                size=_safe_get_font_attr(existing, "size", 11) or 11,
                                color=_value_label_color,
                                family=_font_family,
                            )
                            setattr(tr, font_attr, new_font)
                except Exception:
                    pass
            
            elif ttype in ("scatter", "scattergl"):
                try:
                    for font_attr in ("textfont",):
                        if hasattr(tr, font_attr):
                            existing = getattr(tr, font_attr, None)
                            new_font = dict(
                                size=_safe_get_font_attr(existing, "size", 11) or 11,
                                color=_value_label_color,
                                family=_font_family,
                            )
                            setattr(tr, font_attr, new_font)
                except Exception:
                    pass

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
    sub = st.text_input(
        "Subtitle", value=meta.get("subtitle", ""),
        placeholder="Optional", key=f"{key_prefix}_sub_{uid}",
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
            else:
                if "value_label_color" not in opts:
                    opts["value_label_color"] = "#ffffff"
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
                "Bar mode",
                bar_modes,
                index=_option_index(bar_modes, opts.get("bar_mode", "group"), "group"),
                key=f"{key_prefix}_bar_mode_{uid}",
                disabled=not has_multiple_bars,
            )
        elif caps["has_histogram"]:
            opts["histogram_bins"] = st.slider(
                "Number of bins", 5, 200,
                int(opts.get("histogram_bins", 30)), 5,
                key=f"{key_prefix}_hist_bins_{uid}",
            )
            opts["histogram_opacity"] = st.slider(
                "Opacity", 0.1, 1.0,
                float(opts.get("histogram_opacity", 0.8)), 0.05,
                key=f"{key_prefix}_hist_opacity_{uid}",
            )
            has_multiple_hist = sum(
                1 for t in getattr(fig, "data", [])
                if str(getattr(t, "type", "")).lower() == "histogram"
            ) >= 2
            hist_modes = ["stack", "overlay", "group"]
            opts["bar_mode"] = st.selectbox(
                "Histogram mode",
                hist_modes,
                index=_option_index(hist_modes, opts.get("bar_mode", "stack"), "stack"),
                key=f"{key_prefix}_hist_mode_{uid}",
                disabled=not has_multiple_hist,
            )


        # Only show scatter/line value labels when there are no bar traces
        # (bar traces have their own value labels control above, so we avoid duplicates)
        if (caps["has_scatter"] or caps["has_line"]) and not caps["has_bar"]:
            opts["show_value_labels"] = st.checkbox(
                "Value labels",
                value=bool(opts.get("show_value_labels", False)),
                key=f"{key_prefix}_scatter_labels_{uid}",
            )
            if opts["show_value_labels"]:
                opts["value_label_color"] = st.color_picker(
                    "Value label colour",
                    value=str(opts.get("value_label_color", "#ffffff")),
                    key=f"{key_prefix}_scatter_vl_color_{uid}",
                )
            else:
                if "value_label_color" not in opts:
                    opts["value_label_color"] = "#ffffff"
            if "lines" in str(getattr(next((t for t in getattr(fig, "data", []) if "lines" in str(getattr(t, "mode", ""))), None), "mode", "")):
                opts["line_width"] = st.slider(
                    "Line width", 1, 8,
                    int(opts.get("line_width", 2)), 1,
                    key=f"{key_prefix}_line_width_{uid}",
                )
                opts["line_shape"] = st.selectbox(
                    "Line shape",
                    ["linear", "spline", "hv", "vh", "hvh", "vhv"],
                    index=_option_index(
                        ["linear", "spline", "hv", "vh", "hvh", "vhv"],
                        opts.get("line_shape", "linear"), "linear"
                    ),
                    key=f"{key_prefix}_line_shape_{uid}",
                )
                opts["line_fill"] = st.selectbox(
                    "Line fill",
                    ["none", "tozeroy", "tozerox", "tonexty", "tonextx"],
                    index=_option_index(
                        ["none", "tozeroy", "tozerox", "tonexty", "tonextx"],
                        opts.get("line_fill", "none"), "none"
                    ),
                    key=f"{key_prefix}_line_fill_{uid}",
                )
            opts["marker_size"] = st.slider(
                "Marker size", 2, 20,
                int(opts.get("marker_size", 6)), 1,
                key=f"{key_prefix}_marker_size_{uid}",
            )
            opts["marker_opacity"] = st.slider(
                "Marker opacity", 0.1, 1.0,
                float(opts.get("marker_opacity", 0.8)), 0.05,
                key=f"{key_prefix}_marker_opacity_{uid}",
            )


    with s2:
        if caps["has_pie"]:
            opts["donut_hole"] = st.slider(
                "Donut hole size", 0.0, 0.9,
                float(opts.get("donut_hole", 0)), 0.05,
                key=f"{key_prefix}_donut_{uid}",
            )
            opts["pie_textinfo"] = st.selectbox(
                "Text info",
                ["label+percent", "label", "percent", "value", "label+value", "none"],
                index=_option_index(
                    ["label+percent", "label", "percent", "value", "label+value", "none"],
                    opts.get("pie_textinfo", "label+percent"), "label+percent"
                ),
                key=f"{key_prefix}_pie_textinfo_{uid}",
            )
            opts["pull_slices"] = st.slider(
                "Pull slices", 0.0, 0.3,
                float(opts.get("pull_slices", 0)), 0.02,
                key=f"{key_prefix}_pull_{uid}",
            )
            opts["pie_rotation"] = st.slider(
                "Rotation", 0, 360,
                int(opts.get("pie_rotation", 0)), 5,
                key=f"{key_prefix}_rotation_{uid}",
            )
            opts["pie_direction"] = st.selectbox(
                "Direction",
                ["clockwise", "counterclockwise"],
                index=_option_index(
                    ["clockwise", "counterclockwise"],
                    opts.get("pie_direction", "clockwise"), "clockwise"
                ),
                key=f"{key_prefix}_direction_{uid}",
            )


        if caps["has_heatmap"] and chart_type != "correlation":
            opts["heatmap_colorscale"] = st.selectbox(
                "Colorscale",
                COLORSCALES_ALL,
                index=_option_index(
                    COLORSCALES_ALL,
                    opts.get("heatmap_colorscale", "RdBu"), "RdBu"
                ),
                key=f"{key_prefix}_colorscale_{uid}",
            )
            cs1, cs2 = st.columns(2)
            with cs1:
                opts["colorbar_zmin"] = st.text_input(
                    "Min value", value=str(opts.get("colorbar_zmin", "")),
                    placeholder="Auto", key=f"{key_prefix}_zmin_{uid}",
                )
            with cs2:
                opts["colorbar_zmax"] = st.text_input(
                    "Max value", value=str(opts.get("colorbar_zmax", "")),
                    placeholder="Auto", key=f"{key_prefix}_zmax_{uid}",
                )
            opts["heatmap_show_text"] = st.checkbox(
                "Show cell values",
                value=opts.get("heatmap_show_text", True),
                key=f"{key_prefix}_heatmap_text_{uid}",
            )
            if opts["heatmap_show_text"]:
                opts["heatmap_annotation_size"] = st.slider(
                    "Annotation size", 8, 18,
                    int(opts.get("heatmap_annotation_size", 10)), 1,
                    key=f"{key_prefix}_ann_size_{uid}",
                )
                opts["heatmap_annotation_precision"] = st.slider(
                    "Decimal places", 0, 4,
                    int(opts.get("heatmap_annotation_precision", 2)), 1,
                    key=f"{key_prefix}_ann_prec_{uid}",
                )
                opts["heatmap_annotation_color"] = st.selectbox(
                    "Annotation colour",
                    ["auto", "light", "dark"],
                    index=_option_index(
                        ["auto", "light", "dark"],
                        opts.get("heatmap_annotation_color", "auto"), "auto"
                    ),
                    key=f"{key_prefix}_ann_color_{uid}",
                )


        if chart_type == "correlation" or chart_type == "matrix_heatmap":
            opts["heatmap_font_size"] = st.slider(
                "Cell font size", 8, 14,
                int(opts.get("heatmap_font_size", 10)), 1,
                key=f"{key_prefix}_hm_font_sz_{uid}",
            )
            opts["heatmap_header_size"] = st.slider(
                "Header font size", 8, 14,
                int(opts.get("heatmap_header_size", 10)), 1,
                key=f"{key_prefix}_hm_hdr_sz_{uid}",
            )
            opts["colorbar_title"] = st.text_input(
                "Colorbar title", value=opts.get("colorbar_title", ""),
                placeholder="Optional", key=f"{key_prefix}_cb_title_{uid}",
            )


        if caps["has_table"] or chart_type == "matrix_table":
            st.markdown("**Table styling**")
            opts["table_font_size"] = st.slider(
                "Cell font size", 8, 16,
                int(opts.get("table_font_size", 11)), 1,
                key=f"{key_prefix}_t_font_sz_{uid}",
            )
            opts["table_header_font_size"] = st.slider(
                "Header font size", 8, 16,
                int(opts.get("table_header_font_size", 12)), 1,
                key=f"{key_prefix}_t_hdr_sz_{uid}",
            )
            opts["table_row_height"] = st.slider(
                "Row height", 18, 50,
                int(opts.get("table_row_height", 26)), 2,
                key=f"{key_prefix}_t_row_h_{uid}",
            )
            opts["table_header_height"] = st.slider(
                "Header height", 18, 50,
                int(opts.get("table_header_height", 28)), 2,
                key=f"{key_prefix}_t_hdr_h_{uid}",
            )
            opts["table_font_color"] = st.color_picker(
                "Cell text colour",
                value=str(opts.get("table_font_color", "#f1f5f9")),
                key=f"{key_prefix}_t_font_col_{uid}",
            )
            opts["table_header_color"] = st.color_picker(
                "Header background colour",
                value=str(opts.get("table_header_color", "#6163df")),
                key=f"{key_prefix}_t_hdr_col_{uid}",
            )
            ta1, ta2 = st.columns(2)
            with ta1:
                opts["table_index_align"] = st.selectbox(
                    "Index column align", ["left", "center", "right"],
                    index=_option_index(["left", "center", "right"], opts.get("table_index_align", "left"), "left"),
                    key=f"{key_prefix}_t_idx_align_{uid}",
                )
            with ta2:
                opts["table_data_align"] = st.selectbox(
                    "Data columns align", ["left", "center", "right"],
                    index=_option_index(["left", "center", "right"], opts.get("table_data_align", "right"), "right"),
                    key=f"{key_prefix}_t_data_align_{uid}",
                )
            opts["table_stripe_even_color"] = st.color_picker(
                "Even row colour",
                value=str(opts.get("table_stripe_even_color", "#1e293b")),
                key=f"{key_prefix}_t_stripe_even_{uid}",
            )
            opts["table_stripe_odd_color"] = st.color_picker(
                "Odd row colour",
                value=str(opts.get("table_stripe_odd_color", "#0f172a")),
                key=f"{key_prefix}_t_stripe_odd_{uid}",
            )
            opts["table_number_format"] = st.selectbox(
                "Number format",
                [",.0f", ",.1f", ",.2f", ",.3f", ".0%", ".1%", ".2%"],
                index=_option_index(
                    [",.0f", ",.1f", ",.2f", ",.3f", ".0%", ".1%", ".2%"],
                    opts.get("table_number_format", ",.2f"), ",.2f"
                ),
                key=f"{key_prefix}_t_num_fmt_{uid}",
            )


        if chart_type == "map_plot":
            opts["show_colorbar"] = st.checkbox(
                "Show colour bar",
                value=opts.get("show_colorbar", True),
                key=f"{key_prefix}_map_cb_{uid}",
            )
            opts["colorbar_title"] = st.text_input(
                "Colorbar title", value=opts.get("colorbar_title", ""),
                placeholder="Optional", key=f"{key_prefix}_map_cb_title_{uid}",
            )


    _legend_names_raw = meta.get("legend_names", {})
    if _legend_names_raw and isinstance(_legend_names_raw, dict) and caps["has_legend"]:
        st.markdown("**Custom legend labels**")
        _legend_names = dict(_legend_names_raw)
        for tr in getattr(fig, "data", []):
            _name = getattr(tr, "name", None)
            if _name and str(_name).strip():
                _new_name = st.text_input(
                    f"Rename: {_name}",
                    value=_legend_names.get(_name, ""),
                    key=f"{key_prefix}_leg_name_{uid}_{_name}",
                )
                if _new_name.strip():
                    _legend_names[_name] = _new_name
                elif _name in _legend_names:
                    del _legend_names[_name]
        opts["legend_names"] = _legend_names


    _show_auto_insights = bool(meta.get("show_auto_insights", True))
    _hidden_insights = list(meta.get("hidden_insights", []) or [])


    if auto_insights:
        with st.expander("💡 Auto-Insights", expanded=_show_auto_insights):
            st.caption("AI-generated observations. Hide any that don't apply.")
            for i, insight in enumerate(auto_insights):
                _key = f"{key_prefix}_insight_{uid}_{i}"
                _is_hidden = insight in _hidden_insights
                _checked = st.checkbox(insight, value=not _is_hidden, key=_key)
                if not _checked and insight not in _hidden_insights:
                    _hidden_insights.append(insight)
                elif _checked and insight in _hidden_insights:
                    _hidden_insights.remove(insight)
    elif chart_type not in ("descriptive", "map_plot", "matrix_table", "matrix_heatmap"):
        st.caption("No auto-insights generated for this chart.")


    result = {
        "custom_title": nt,
        "subtitle": sub,
        "x_label": xl,
        "y_label": yl,
        "legend_title": meta.get("legend_title", ""),
        "legend_names": opts.get("legend_names", {}),
        "display_options": opts,
        "show_auto_insights": _show_auto_insights,
        "hidden_insights": _hidden_insights,
    }


    if show_text_style:
        result["text_style"] = render_typography_controls(
            uid, fig, chart_type, meta, key_prefix=key_prefix,
        )


    return result