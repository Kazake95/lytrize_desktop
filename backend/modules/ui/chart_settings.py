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
        "has_axes": True, "has_legend": False,
        "controls": ["title", "subtitle", "axes_labels",
                    "show_value_labels", "label_position", "bar_gap", "bar_mode"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick"],
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
                    "heatmap_colorscale", "colorbar_title",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_tick"],
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
                    "heatmap_colorscale",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_tick"],
    },
    "map_plot": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "show_colorbar", "colorbar_title",
                    "heatmap_colorscale",
                    "marker_opacity", "marker_size"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick"],
    },
    "pie_chart": {
        "has_axes": False, "has_legend": True,
        "controls": ["title", "subtitle", "legend_labels",
                    "donut_hole", "pie_textinfo", "pull_slices",
                    "pie_rotation", "pie_direction",
                    "pie_label_size", "pie_label_color",
                    "pie_value_size", "pie_value_color"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "legend_title", "legend_item", "pie_label", "pie_value"],
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
    """Hash the full meta dict so any future key auto-invalidates the display cache."""
    if not meta:
        return ""
    return json.dumps(meta, sort_keys=True, default=str)



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
        "axis_title_size":    12,
        "axis_title_color":   "#cbd5e1",
        "axis_tick_size":     10,
        "axis_tick_color":    "#94a3b8",
        "legend_title_size":  12,
        "legend_title_color": "#cbd5e1",
        "legend_item_size":   11,
        "legend_item_color":  "#e2e8f0",
        "legend_bgcolor":     "rgba(0,0,0,0)",
        "pie_label_size":     11,
        "pie_label_color":    "#e2e8f0",
        "pie_value_size":     11,
        "pie_value_color":    "#e2e8f0",
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
        "has_heatmap":   bool(types & {"heatmap"}) or chart_type == "matrix_heatmap",
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
    matrix_view: str = "",
):
    """Apply all display options from meta to the figure.

    Parameters
    ----------
    fig : plotly.graph_objects.Figure
        The base figure to apply options to.
    meta : dict or None
        Chart metadata containing display_options and text_style.
    chart_type : str
        The chart type key (e.g. "categorical", "pie_chart").
    _inplace : bool
        If True, mutate fig in-place instead of deepcopying.
    matrix_view : str
        "heatmap" when matrix_table should render as heatmap.
    """
    meta = meta or {}
    opts = meta.get("display_options", {})
    if not isinstance(opts, dict):
        opts = {}
    f2 = fig if _inplace else copy.deepcopy(fig)

    _is_heatmap_view = chart_type == "matrix_table" and matrix_view == "heatmap"

    # Capture value label settings early (outside try so the final section can always use them)
    _show_value_labels = bool(opts.get("show_value_labels", False))
    _value_label_color = str(opts.get("value_label_color", "#ffffff")) if _show_value_labels else None
    _label_pos = opts.get("label_position", "outside")

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

    for tr in f2.data:
        ttype = str(getattr(tr, "type", "") or "").lower()
        mode  = str(getattr(tr, "mode", "") or "")

        try:
            if ttype == "bar":
                tr.textposition = _label_pos if _show_value_labels else "none"

            if ttype in ("scatter", "scattergl"):
                if _show_value_labels:
                    # Populate text with y-values if not already set
                    if getattr(tr, "text", None) is None:
                        y_vals = getattr(tr, "y", None)
                        if y_vals is not None:
                            try:
                                tr.text = [str(round(float(v), 2)) if v is not None else "" for v in y_vals]
                            except (TypeError, ValueError):
                                pass
                    if "text" not in mode:
                        tr.mode = mode + "+text"
                    tr.textposition = "top center"
                else:
                    tr.mode = (
                        mode.replace("+text", "").replace("text+", "").replace("text", "")
                    ) or ("lines+markers" if "lines" in mode and "markers" in mode else mode)

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

            if ttype in ("heatmap", "choropleth"):
                if opts.get("heatmap_colorscale"):
                    tr.colorscale = str(opts["heatmap_colorscale"])
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
                # Handle auto mode vs direct hex color
                if ann_color_mode in ("auto", "light", "dark"):
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
                else:
                    # Direct hex color from color picker
                    ann_color = ann_color_mode if ann_color_mode.startswith("#") else None
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

            # Apply font family to textfont if it exists (skip heatmap - handled separately below)
            if hasattr(tr, "textfont") and tr.textfont is not None and ttype != "heatmap":
                try:
                    tr.textfont.family = _font_family
                except Exception:
                    pass

        except Exception:
            # One bad trace must not abort the rest of the figure.
            continue

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
                        new_font["weight"] = _weight
                        new_font["style"] = _style
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
            caps = get_chart_type_capabilities(chart_type)
            if "axis_title" in caps.get("typography", []) and chart_type != "correlation":
                _ax_title_size  = int(ts.get("axis_title_size", 12))
                _ax_title_color = str(ts.get("axis_title_color", "#cbd5e1"))
                axis_title_font = dict(size=_ax_title_size, color=_ax_title_color, family=_font_family, weight=_weight, style=_style)
                f2.update_xaxes(title_font=axis_title_font)
                f2.update_yaxes(title_font=axis_title_font)
            axis_tick_font  = dict(size=_ax_tick_size,  color=_ax_tick_color,  family=_font_family, weight=_weight, style=_style)
            f2.update_xaxes(tickfont=axis_tick_font)
            f2.update_yaxes(tickfont=axis_tick_font)

        _leg_bgcolor = str(ts.get("legend_bgcolor", "rgba(0,0,0,0)"))
        f2.update_layout(
            legend=dict(
                bgcolor=_leg_bgcolor,
                title_font=dict(size=_leg_title_size, color=_leg_title_color, family=_font_family, weight=_weight, style=_style),
                font=dict(size=_leg_item_size, color=_leg_item_color, family=_font_family, weight=_weight, style=_style),
            )
        )

    # ============================================================
    # PIE CHART FONT SETTINGS - Applied after generic per-trace override
    # ============================================================
    for tr in f2.data:
        ttype = str(getattr(tr, "type", "") or "").lower()
        if ttype not in ("pie", "sunburst", "treemap"):
            continue

        _pie_lbl_clr = opts.get("pie_label_color") or ts.get("pie_label_color")
        _pie_lbl_sz  = opts.get("pie_label_size") or ts.get("pie_label_size")
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

        _pie_val_clr = opts.get("pie_value_color") or ts.get("pie_value_color")
        _pie_val_sz  = opts.get("pie_value_size") or ts.get("pie_value_size")
        if _pie_val_clr or _pie_val_sz:
            for _pf_attr in ("insidetextfont", "outsidetextfont", "textfont"):
                if hasattr(tr, _pf_attr):
                    _pf = getattr(tr, _pf_attr, None)
                    _upd = {}
                    if _pie_val_clr and _pie_val_clr != "auto":
                        _upd["color"] = _pie_val_clr
                    if _pie_val_sz:
                        _upd["size"] = int(_pie_val_sz)
                    if _upd:
                        try:
                            if isinstance(_pf, dict):
                                _pf.update(_upd)
                            else:
                                for _k, _v in _upd.items():
                                    setattr(_pf, _k, _v)
                        except Exception:
                            pass

    # ============================================================
    # COLORBAR / HEATMAP / MAP specific code
    # ============================================================
    if chart_type in ("matrix_heatmap", "correlation", "map_plot") or _is_heatmap_view:
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
            _map_cs = opts.get("heatmap_colorscale")
            if _map_cs:
                try:
                    f2.update_coloraxes(colorscale=str(_map_cs))
                except Exception:
                    pass
            _hover_prec = int(opts.get("hover_decimals", 2))
            for _tr in f2.data:
                try:
                    _ht = getattr(_tr, "hovertemplate", None)
                    if not isinstance(_ht, str) or not _ht.strip():
                        raise ValueError("no template")
                    import re as _re2
                    def _fmt(m):
                        _tok = (m.group(1) or m.group(2) or "").strip()
                        if _tok == "hovertext":
                            return "%{hovertext}"
                        if _tok in ("customdata[1]", "customdata[2]",
                                    "customdata[0]", "marker.color"):
                            return f"%{{{_tok}:.{_hover_prec}f}}"
                        return m.group(0)
                    _tr.hovertemplate = _re2.sub(
                        r"%\{([a-z.]+)(?::[^}]*)?\}|%\{([a-z]+\[[^\]]*\])\}",
                        _fmt, str(_ht),
                    )
                except Exception:
                    pass
        else:
            # Apply colorscale via update_coloraxes for px.imshow compatibility
            _map_cs = opts.get("heatmap_colorscale")
            if _map_cs:
                try:
                    f2.update_coloraxes(colorscale=str(_map_cs))
                except Exception:
                    pass

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
                _caps = get_chart_type_capabilities(chart_type)
                try:
                    f2.update_xaxes(tickfont=dict(size=_ax_tick_size, color=_ax_tick_color, family=cb_family, **_cb_font_suffix))
                    f2.update_yaxes(tickfont=dict(size=_ax_tick_size, color=_ax_tick_color, family=cb_family, **_cb_font_suffix))
                except Exception:
                    pass
                try:
                    tr.colorbar.tickfont = dict(
                        size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix)
                    if cb_title:
                        tr.colorbar.title.text = cb_title
                    tr.colorbar.title.font = dict(
                        size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix)
                except Exception:
                    pass

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
                                weight=_weight,
                                style=_style,
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
                                weight=_weight,
                                style=_style,
                            )
                            setattr(tr, font_attr, new_font)
                except Exception:
                    pass

    return f2


# ---------------------------------------------------------------------------
# Public renderer API (imported by chart_card.py / analysis.py / dashboard.py)
# ---------------------------------------------------------------------------
def render_chart_settings_controls(uid: str, title: str, fig, chart_type: str,
                                   meta: dict, auto_insights: list[str], *,
                                   key_prefix: str = "analysis",
                                   show_text_style: bool = False,
                                   matrix_view: str = "") -> dict:
    """Render the Chart Settings expander for a single chart.

    Returns a dict of changed meta keys so the caller can persist them.
    """
    opts = dict(meta.get("display_options", {}))
    result: dict[str, Any] = {}
    stype = chart_type

    if stype == "matrix_table" and matrix_view == "heatmap":
        stype = "matrix_heatmap"

    caps = get_chart_type_capabilities(stype)

    # ---- title / subtitle ------------------------------------------------
    nt = st.text_input(
        "Chart title",
        value=meta.get("custom_title", title),
        key=f"{key_prefix}_title_{uid}",
    )
    if nt != meta.get("custom_title", title):
        result["custom_title"] = nt
    sub = st.text_input(
        "Subtitle",
        value=meta.get("subtitle", ""),
        key=f"{key_prefix}_subtitle_{uid}",
    )
    if sub != meta.get("subtitle", ""):
        result["subtitle"] = sub

    # ---- axes labels (only for charts with axes) -------------------------
    if caps.get("has_axes", False):
        xl = st.text_input(
            "X-axis label",
            value=meta.get("x_label", ""),
            key=f"{key_prefix}_xl_{uid}",
        )
        if xl != meta.get("x_label", ""):
            result["x_label"] = xl
        yl = st.text_input(
            "Y-axis label",
            value=meta.get("y_label", ""),
            key=f"{key_prefix}_yl_{uid}",
        )
        if yl != meta.get("y_label", ""):
            result["y_label"] = yl

    # ---- legend title (only for charts with legend) ----------------------
    if caps.get("has_legend", False):
        _leg_title = st.text_input(
            "Legend title",
            value=meta.get("legend_title", ""),
            key=f"{key_prefix}_leg_title_{uid}",
        )
        if _leg_title != meta.get("legend_title", ""):
            result["legend_title"] = _leg_title

    # ---- display options -------------------------------------------------
    controls = caps.get("controls", [])

    if "show_value_labels" in controls:
        opts["show_value_labels"] = st.checkbox(
            "Show value labels",
            value=bool(opts.get("show_value_labels", False)),
            key=f"{key_prefix}_svl_{uid}",
        )
    if "label_position" in controls:
        _lp = opts.get("label_position", "outside")
        opts["label_position"] = st.selectbox(
            "Label position",
            ["outside", "inside", "auto"],
            index=0 if _lp == "outside" else 1 if _lp == "inside" else 2,
            key=f"{key_prefix}_lpos_{uid}",
        )
    if "bar_gap" in controls:
        opts["bar_gap"] = st.slider(
            "Bar gap", 0.0, 1.0, float(opts.get("bar_gap", 0.28)), 0.01,
            key=f"{key_prefix}_bgap_{uid}",
        )
    if "bar_mode" in controls:
        _bm = opts.get("bar_mode", "group")
        opts["bar_mode"] = st.selectbox(
            "Bar mode",
            ["group", "stack", "relative", "overlay"],
            index=["group", "stack", "relative", "overlay"].index(_bm)
            if _bm in ("group", "stack", "relative", "overlay") else 0,
            key=f"{key_prefix}_bmode_{uid}",
        )
    if "histogram_bins" in controls:
        opts["histogram_bins"] = st.slider(
            "Histogram bins", 5, 200, int(opts.get("histogram_bins", 30)), 1,
            key=f"{key_prefix}_hbins_{uid}",
        )
    if "histogram_opacity" in controls:
        opts["histogram_opacity"] = st.slider(
            "Opacity", 0.1, 1.0, float(opts.get("histogram_opacity", 0.8)), 0.05,
            key=f"{key_prefix}_hop_{uid}",
        )
    if "line_width" in controls:
        opts["line_width"] = st.slider(
            "Line width", 1, 10, int(opts.get("line_width", 2)), 1,
            key=f"{key_prefix}_lw_{uid}",
        )
    if "line_shape" in controls:
        _ls = opts.get("line_shape", "linear")
        opts["line_shape"] = st.selectbox(
            "Line shape",
            ["linear", "spline", "hv", "vh", "hvh", "vhv"],
            index=["linear", "spline", "hv", "vh", "hvh", "vhv"].index(_ls)
            if _ls in ("linear", "spline", "hv", "vh", "hvh", "vhv") else 0,
            key=f"{key_prefix}_ls_{uid}",
        )
    if "show_markers" in controls:
        opts["show_markers"] = st.checkbox(
            "Show markers",
            value=bool(opts.get("show_markers", True)),
            key=f"{key_prefix}_sm_{uid}",
        )
    if "line_fill" in controls:
        _lf = opts.get("line_fill", "none")
        opts["line_fill"] = st.selectbox(
            "Fill",
            ["none", "tozeroy", "tozerox", "tonexty", "tonextx"],
            index=["none", "tozeroy", "tozerox", "tonexty", "tonextx"].index(_lf)
            if _lf in ("none", "tozeroy", "tozerox", "tonexty", "tonextx") else 0,
            key=f"{key_prefix}_lf_{uid}",
        )
    if "marker_opacity" in controls:
        opts["marker_opacity"] = st.slider(
            "Marker opacity", 0.1, 1.0, float(opts.get("marker_opacity", 0.8)), 0.05,
            key=f"{key_prefix}_mo_{uid}",
        )
    if "marker_size" in controls:
        opts["marker_size"] = st.slider(
            "Marker size", 2, 30, int(opts.get("marker_size", 6)), 1,
            key=f"{key_prefix}_ms_{uid}",
        )
    if "donut_hole" in controls:
        opts["donut_hole"] = st.slider(
            "Donut hole", 0.0, 0.9, float(opts.get("donut_hole", 0.0)), 0.05,
            key=f"{key_prefix}_dh_{uid}",
        )
    if "pie_textinfo" in controls:
        _pti = opts.get("pie_textinfo", "label+percent")
        opts["pie_textinfo"] = st.selectbox(
            "Text info",
            ["label", "percent", "value", "label+percent", "label+value"],
            index=["label", "percent", "value", "label+percent", "label+value"].index(_pti)
            if _pti in ("label", "percent", "value", "label+percent", "label+value") else 3,
            key=f"{key_prefix}_pti_{uid}",
        )
    if "pull_slices" in controls:
        opts["pull_slices"] = st.slider(
            "Pull slices", 0.0, 0.5, float(opts.get("pull_slices", 0.0)), 0.01,
            key=f"{key_prefix}_ps_{uid}",
        )
    if "pie_rotation" in controls:
        opts["pie_rotation"] = st.slider(
            "Rotation", 0, 360, int(opts.get("pie_rotation", 0)), 1,
            key=f"{key_prefix}_pr_{uid}",
        )
    if "pie_direction" in controls:
        _pd = opts.get("pie_direction", "clockwise")
        opts["pie_direction"] = st.selectbox(
            "Direction",
            ["clockwise", "counterclockwise"],
            index=0 if _pd == "clockwise" else 1,
            key=f"{key_prefix}_pd_{uid}",
        )
    if "pie_label_size" in controls:
        opts["pie_label_size"] = st.slider(
            "Pie label size", 6, 24,
            int(opts.get("pie_label_size", 11)), 1,
            key=f"{key_prefix}_pls_{uid}",
        )
    if "pie_label_color" in controls:
        opts["pie_label_color"] = st.color_picker(
            "Pie label color",
            value=opts.get("pie_label_color", "#e2e8f0"),
            key=f"{key_prefix}_plc_{uid}",
        )
    if "pie_value_size" in controls:
        opts["pie_value_size"] = st.slider(
            "Pie value size", 6, 24,
            int(opts.get("pie_value_size", 11)), 1,
            key=f"{key_prefix}_pvs_{uid}",
        )
    if "pie_value_color" in controls:
        opts["pie_value_color"] = st.color_picker(
            "Pie value color",
            value=opts.get("pie_value_color", "#e2e8f0"),
            key=f"{key_prefix}_pvc_{uid}",
        )
    if "heatmap_colorscale" in controls:
        _cs = opts.get("heatmap_colorscale", "RdBu")
        opts["heatmap_colorscale"] = st.selectbox(
            "Colorscale",
            COLORSCALES_ALL,
            index=COLORSCALES_ALL.index(_cs) if _cs in COLORSCALES_ALL else 0,
            key=f"{key_prefix}_cs_{uid}",
        )
    if "heatmap_show_text" in controls:
        opts["heatmap_show_text"] = st.checkbox(
            "Show annotations",
            value=bool(opts.get("heatmap_show_text", True)),
            key=f"{key_prefix}_hst_{uid}",
        )
    if "heatmap_annotation_precision" in controls:
        opts["heatmap_annotation_precision"] = st.slider(
            "Annotation precision", 0, 10,
            int(opts.get("heatmap_annotation_precision", 2)), 1,
            key=f"{key_prefix}_hap_{uid}",
        )
    if "heatmap_annotation_size" in controls:
        opts["heatmap_annotation_size"] = st.slider(
            "Annotation size", 6, 24,
            int(opts.get("heatmap_annotation_size", 10)), 1,
            key=f"{key_prefix}_has_{uid}",
        )
    if "heatmap_annotation_color" in controls:
        _ac = opts.get("heatmap_annotation_color", "auto")
        if _ac == "auto":
            _default_ann_color = "#ffffff"
        elif _ac == "light":
            _default_ann_color = "#ffffff"
        elif _ac == "dark":
            _default_ann_color = "#1e293b"
        else:
            _default_ann_color = _ac if _ac.startswith("#") else "#ffffff"
        
        _ann_color = st.color_picker(
            "Annotation color",
            value=_default_ann_color,
            key=f"{key_prefix}_hac_{uid}",
            help="Choose annotation text color. 'auto' mode will adapt based on cell values.",
        )
        # Store the selected color directly
        opts["heatmap_annotation_color"] = _ann_color
    if "table_font_size" in controls:
        opts["table_font_size"] = st.slider(
            "Table font size", 8, 24,
            int(opts.get("table_font_size", 11)), 1,
            key=f"{key_prefix}_tfs_{uid}",
        )
    if "table_font_color" in controls:
        opts["table_font_color"] = st.color_picker(
            "Table font color",
            value=opts.get("table_font_color", "#f1f5f9"),
            key=f"{key_prefix}_tfc_{uid}",
        )
    if "table_header_font_size" in controls:
        opts["table_header_font_size"] = st.slider(
            "Header font size", 8, 24,
            int(opts.get("table_header_font_size", 12)), 1,
            key=f"{key_prefix}_thfs_{uid}",
        )
    if "table_header_color" in controls:
        opts["table_header_color"] = st.color_picker(
            "Header color",
            value=opts.get("table_header_color", "#6163df"),
            key=f"{key_prefix}_thc_{uid}",
        )
    if "table_row_height" in controls:
        opts["table_row_height"] = st.slider(
            "Row height", 16, 60,
            int(opts.get("table_row_height", 26)), 1,
            key=f"{key_prefix}_trh_{uid}",
        )
    if "table_header_height" in controls:
        opts["table_header_height"] = st.slider(
            "Header height", 16, 60,
            int(opts.get("table_header_height", 28)), 1,
            key=f"{key_prefix}_thh_{uid}",
        )
    if "table_index_align" in controls:
        _ia = opts.get("table_index_align", "left")
        opts["table_index_align"] = st.selectbox(
            "Index align",
            ["left", "center", "right"],
            index=["left", "center", "right"].index(_ia)
            if _ia in ("left", "center", "right") else 0,
            key=f"{key_prefix}_tia_{uid}",
        )
    if "table_data_align" in controls:
        _da = opts.get("table_data_align", "right")
        opts["table_data_align"] = st.selectbox(
            "Data align",
            ["left", "center", "right"],
            index=["left", "center", "right"].index(_da)
            if _da in ("left", "center", "right") else 2,
            key=f"{key_prefix}_tda_{uid}",
        )
    if "table_stripe_even_color" in controls:
        opts["table_stripe_even_color"] = st.color_picker(
            "Stripe even color",
            value=opts.get("table_stripe_even_color", "#1e293b"),
            key=f"{key_prefix}_tsec_{uid}",
        )
    if "table_stripe_odd_color" in controls:
        opts["table_stripe_odd_color"] = st.color_picker(
            "Stripe odd color",
            value=opts.get("table_stripe_odd_color", "#0f172a"),
            key=f"{key_prefix}_tsoc_{uid}",
        )
    if "table_number_format" in controls:
        _nf = opts.get("table_number_format", ",.2f")
        opts["table_number_format"] = st.selectbox(
            "Number format",
            [",.2f", ",.1f", ",.0f", ".2f", ".1f", ".0f"],
            index=[",.2f", ",.1f", ",.0f", ".2f", ".1f", ".0f"].index(_nf)
            if _nf in (",.2f", ",.1f", ",.0f", ".2f", ".1f", ".0f") else 0,
            key=f"{key_prefix}_tnf_{uid}",
        )
    if "row_index_header" in controls:
        opts["row_index_header"] = st.text_input(
            "Row index header",
            value=opts.get("row_index_header", ""),
            key=f"{key_prefix}_rih_{uid}",
        )
    if "show_colorbar" in controls:
        opts["show_colorbar"] = st.checkbox(
            "Show colorbar",
            value=bool(opts.get("show_colorbar", True)),
            key=f"{key_prefix}_scb_{uid}",
        )

    result["display_options"] = opts
    return result


def render_typography_controls(uid: str, fig, chart_type: str,
                               meta: dict, *, key_prefix: str = "analysis") -> dict:
    """Render the Typography expander for a single chart.

    Returns a dict of typography key-value pairs (flat dict, NOT {"text_style": ...}).
    """
    text_style = dict(meta.get("text_style", {}))

    inject_font_preview_css()
    fam = font_select(
        "Font family",
        text_style.get("family", "Inter"),
        key=f"{key_prefix}_font_{uid}",
    )
    if fam != text_style.get("family"):
        text_style["family"] = fam

    fs = st.selectbox(
        "Font style",
        ["Normal", "Bold", "Italic", "Bold Italic", "Underline"],
        index=["Normal", "Bold", "Italic", "Bold Italic", "Underline"].index(
            text_style.get("font_style", "Normal")
        ) if text_style.get("font_style", "Normal") in (
            "Normal", "Bold", "Italic", "Bold Italic", "Underline"
        ) else 0,
        key=f"{key_prefix}_fstyle_{uid}",
    )
    if fs != text_style.get("font_style"):
        text_style["font_style"] = fs

    c1, c2 = st.columns(2)
    with c1:
        _hs = st.number_input(
            "Header size", 10, 60,
            int(text_style.get("header_size", 28)), 1,
            key=f"{key_prefix}_hsize_{uid}",
        )
        if _hs != text_style.get("header_size"):
            text_style["header_size"] = _hs
        _hc = st.color_picker(
            "Header color",
            text_style.get("header_color", "#6163df"),
            key=f"{key_prefix}_hcolor_{uid}",
        )
        if _hc != text_style.get("header_color"):
            text_style["header_color"] = _hc
        _hfam = font_select(
            "Header font family",
            text_style.get("header_family", text_style.get("family", "Inter")),
            key=f"{key_prefix}_hfont_{uid}",
        )
        if _hfam != text_style.get("header_family", text_style.get("family", "Inter")):
            text_style["header_family"] = _hfam
        _hfstyle = st.selectbox(
            "Header font style",
            ["Normal", "Bold", "Italic", "Bold Italic", "Underline"],
            index=["Normal", "Bold", "Italic", "Bold Italic", "Underline"].index(
                text_style.get("header_font_style", "Normal")
            ) if text_style.get("header_font_style", "Normal") in (
                "Normal", "Bold", "Italic", "Bold Italic", "Underline"
            ) else 0,
            key=f"{key_prefix}_hfont_style_{uid}",
        )
        if _hfstyle != text_style.get("header_font_style", "Normal"):
            text_style["header_font_style"] = _hfstyle
    with c2:
        _ss = st.number_input(
            "Subtitle size", 8, 40,
            int(text_style.get("subtitle_size", 11)), 1,
            key=f"{key_prefix}_ssize_{uid}",
        )
        if _ss != text_style.get("subtitle_size"):
            text_style["subtitle_size"] = _ss
        _sc = st.color_picker(
            "Subtitle color",
            text_style.get("subtitle_color", "#64748b"),
            key=f"{key_prefix}_scolor_{uid}",
        )
        if _sc != text_style.get("subtitle_color"):
            text_style["subtitle_color"] = _sc
        _sfam = font_select(
            "Subtitle font family",
            text_style.get("subtitle_family", text_style.get("family", "Inter")),
            key=f"{key_prefix}_subfont_{uid}",
        )
        if _sfam != text_style.get("subtitle_family", text_style.get("family", "Inter")):
            text_style["subtitle_family"] = _sfam
        _sfstyle = st.selectbox(
            "Subtitle font style",
            ["Normal", "Bold", "Italic", "Bold Italic", "Underline"],
            index=["Normal", "Bold", "Italic", "Bold Italic", "Underline"].index(
                text_style.get("subtitle_font_style", "Normal")
            ) if text_style.get("subtitle_font_style", "Normal") in (
                "Normal", "Bold", "Italic", "Bold Italic", "Underline"
            ) else 0,
            key=f"{key_prefix}_subfont_style_{uid}",
        )
        if _sfstyle != text_style.get("subtitle_font_style", "Normal"):
            text_style["subtitle_font_style"] = _sfstyle

    caps = get_chart_type_capabilities(chart_type)
    if "axis_tick" in caps.get("typography", []):
        _ats = st.number_input(
            "Axis tick size", 6, 18,
            int(text_style.get("axis_tick_size", 10)), 1,
            key=f"{key_prefix}_atsize_{uid}",
        )
        if _ats != text_style.get("axis_tick_size"):
            text_style["axis_tick_size"] = _ats
        _atc = st.color_picker(
            "Axis tick color",
            text_style.get("axis_tick_color", "#94a3b8"),
            key=f"{key_prefix}_atcolor_{uid}",
        )
        if _atc != text_style.get("axis_tick_color"):
            text_style["axis_tick_color"] = _atc

    if "axis_title" in caps.get("typography", []) and chart_type != "correlation":
        _ax_title_sz = st.number_input(
            "Axis title size", 8, 24,
            int(text_style.get("axis_title_size", 12)), 1,
            key=f"{key_prefix}_ax_titlesize_{uid}",
        )
        if _ax_title_sz != text_style.get("axis_title_size"):
            text_style["axis_title_size"] = _ax_title_sz
        _ax_title_col = st.color_picker(
            "Axis title color",
            text_style.get("axis_title_color", "#cbd5e1"),
            key=f"{key_prefix}_ax_titlecolor_{uid}",
        )
        if _ax_title_col != text_style.get("axis_title_color"):
            text_style["axis_title_color"] = _ax_title_col

    if "legend_title" in caps.get("typography", []) or "legend_item" in caps.get("typography", []):
        _lts = st.number_input(
            "Legend title size", 8, 24,
            int(text_style.get("legend_title_size", 12)), 1,
            key=f"{key_prefix}_ltsize_{uid}",
        )
        if _lts != text_style.get("legend_title_size"):
            text_style["legend_title_size"] = _lts
        _ltc = st.color_picker(
            "Legend title color",
            text_style.get("legend_title_color", "#cbd5e1"),
            key=f"{key_prefix}_ltcolor_{uid}",
        )
        if _ltc != text_style.get("legend_title_color"):
            text_style["legend_title_color"] = _ltc
        _lis = st.number_input(
            "Legend item size", 8, 20,
            int(text_style.get("legend_item_size", 11)), 1,
            key=f"{key_prefix}_lisize_{uid}",
        )
        if _lis != text_style.get("legend_item_size"):
            text_style["legend_item_size"] = _lis
        _lic = st.color_picker(
            "Legend item color",
            text_style.get("legend_item_color", "#e2e8f0"),
            key=f"{key_prefix}_licolor_{uid}",
        )
        if _lic != text_style.get("legend_item_color"):
            text_style["legend_item_color"] = _lic

    if "pie_label" in caps.get("typography", []):
        _pls = st.number_input(
            "Pie label size", 8, 24,
            int(text_style.get("pie_label_size", 11)), 1,
            key=f"{key_prefix}_plsize_{uid}",
        )
        if _pls != text_style.get("pie_label_size"):
            text_style["pie_label_size"] = _pls
        _plc = st.color_picker(
            "Pie label color",
            text_style.get("pie_label_color", "#e2e8f0"),
            key=f"{key_prefix}_plcolor_{uid}",
        )
        if _plc != text_style.get("pie_label_color"):
            text_style["pie_label_color"] = _plc

    if "pie_value" in caps.get("typography", []):
        _pvs = st.number_input(
            "Pie value size", 8, 24,
            int(text_style.get("pie_value_size", 11)), 1,
            key=f"{key_prefix}_pvsize_{uid}",
        )
        if _pvs != text_style.get("pie_value_size"):
            text_style["pie_value_size"] = _pvs
        _pvc = st.color_picker(
            "Pie value color",
            text_style.get("pie_value_color", "#e2e8f0"),
            key=f"{key_prefix}_pvcolor_{uid}",
        )
        if _pvc != text_style.get("pie_value_color"):
            text_style["pie_value_color"] = _pvc

    return text_style