"""modules/ui/chart_settings.py -- Shared chart setting schema and Plotly adapters."""


from __future__ import annotations
import logging


import copy
import functools
import json
import re
from typing import Any


import streamlit as st


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
        "controls": ["title", "axes_labels",
                    "show_value_labels", "label_position", "bar_gap", "bar_mode", "line_width"],
        "typography": ["family", "font_style", "header",
                      "axis_title", "axis_tick"],
    },
    "descriptive": {
        "has_axes": False, "has_legend": False,
        "controls": ["title"],
        "typography": ["family", "font_style", "header"],
    },
    "statistical": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "axes_labels", "legend_labels",
                    "show_value_labels", "label_position", "bar_gap", "bar_mode"],
        "typography": ["family", "font_style", "header",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "distribution": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "axes_labels", "legend_labels",
                    "histogram_bins", "histogram_opacity", "bar_mode"],
        "typography": ["family", "font_style", "header",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "correlation": {
        "has_axes": False, "has_legend": False,
        "controls": ["title",
                    "heatmap_colorscale", "colorbar_title",
                    "colorbar_tick_size", "colorbar_tick_color",
                    "colorbar_title_size", "colorbar_title_color",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color"],
        "typography": ["family", "font_style", "header",
                      "axis_tick"],
    },
    "time_series": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "axes_labels", "legend_labels",
                    "line_width", "line_shape", "show_markers", "line_fill",
                    "show_value_labels"],
        "typography": ["family", "font_style", "header",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "scatter_plot": {
        "has_axes": True, "has_legend": True,
        "controls": ["title", "axes_labels", "legend_labels",
                    "marker_opacity", "marker_size", "show_value_labels",
                    "line_width", "show_markers", "line_fill", "render_mode"],
        "typography": ["family", "font_style", "header",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "matrix_table": {
        "has_axes": False, "has_legend": False,
        "controls": ["title",
                    "table_font_size", "table_font_color",
                    "table_header_font_size", "table_header_color",
                    "table_row_height", "table_header_height",
                    "table_index_align", "table_data_align",
                    "table_stripe_even_color", "table_stripe_odd_color",
                    "table_number_format"],
        "typography": ["family", "font_style", "header"],
    },
    "matrix_heatmap": {
        "has_axes": False, "has_legend": False,
        "controls": ["title",
                    "heatmap_colorscale", "colorbar_title",
                    "colorbar_tick_size", "colorbar_tick_color",
                    "colorbar_title_size", "colorbar_title_color",
                    "heatmap_show_text", "heatmap_annotation_precision",
                    "heatmap_annotation_size", "heatmap_annotation_color"],
        "typography": ["family", "font_style", "header",
                      "axis_tick"],
    },
    "map_plot": {
        "has_axes": False, "has_legend": False,
        "controls": ["title",
                    "show_colorbar", "colorbar_title",
                    "colorbar_tick_size", "colorbar_tick_color",
                    "colorbar_title_size", "colorbar_title_color",
                    "heatmap_colorscale",
                    "marker_opacity", "marker_size"],
        "typography": ["family", "font_style", "header"],
    },
    "pie_chart": {
        "has_axes": False, "has_legend": True,
        "controls": ["title", "legend_labels",
                "donut_hole", "pie_textinfo", "pull_slices",
                "pie_rotation", "pie_direction",
                "pie_value_size", "pie_value_color"],
        "typography": ["family", "font_style", "header",
                      "legend_title", "legend_item"],
    },
}


# ---------------------------------------------------------------------------
# Compact-layout constants
# ---------------------------------------------------------------------------

# Controls moved behind the "Advanced" popover per chart type (opt-in).
# If a chart type is absent here, ALL its controls stay in the main view.
CONTROLS_ADVANCED: dict[str, list[str]] = {
    "categorical":    ["bar_gap"],
    "statistical":    ["bar_gap"],
    "distribution":   ["histogram_opacity"],
    "correlation":    ["heatmap_annotation_precision", "heatmap_annotation_color",
                       "colorbar_tick_size", "colorbar_tick_color",
                       "colorbar_title_size", "colorbar_title_color"],
    "time_series":    ["line_shape", "line_fill"],
    "scatter_plot":   ["line_width", "show_markers", "line_fill", "render_mode"],
    "matrix_table":   ["table_index_align", "table_data_align",
                       "table_stripe_even_color", "table_stripe_odd_color",
                       "table_number_format", "table_header_height"],
    "matrix_heatmap": ["heatmap_annotation_precision", "heatmap_annotation_color",
                       "colorbar_tick_size", "colorbar_tick_color",
                       "colorbar_title_size", "colorbar_title_color"],
    "map_plot":       ["marker_opacity", "marker_size",
                       "colorbar_tick_size", "colorbar_tick_color",
                       "colorbar_title_size", "colorbar_title_color"],
    "pie_chart":      ["pie_rotation", "pie_direction", "pull_slices",
                       "pie_value_size", "pie_value_color"],
}

# Control metadata: control_name -> {type, label, key_suffix, ...params}
# Used by the compact auto-column renderer. Keyed on control NAME so any
# new chart type just declares its controls list and the renderer handles it.
_CONTROL_META: dict[str, dict] = {
    # Checkboxes
    "show_value_labels": {"t": "check", "l": "Value labels", "k": "svl", "d": False},
    "show_markers":      {"t": "check", "l": "Markers", "k": "sm", "d": True},
    "show_colorbar":     {"t": "check", "l": "Colorbar", "k": "scb", "d": True},
    "heatmap_show_text": {"t": "check", "l": "Annotations", "k": "hst", "d": True},
    # Selects
    "label_position":      {"t": "select", "l": "Label pos", "k": "lpos", "o": ["outside", "inside", "auto"], "d": "outside"},
    "bar_mode":            {"t": "select", "l": "Bar mode", "k": "bmode", "o": ["group", "stack", "relative", "overlay"], "d": "group"},
    "line_shape":          {"t": "select", "l": "Line shape", "k": "ls", "o": ["linear", "spline", "hv", "vh", "hvh", "vhv"], "d": "linear"},
    "line_fill":           {"t": "select", "l": "Fill", "k": "lf", "o": ["none", "tozeroy", "tozerox", "tonexty", "tonextx"], "d": "none"},
    "pie_textinfo":        {"t": "select", "l": "Text info", "k": "pti", "o": ["label", "percent", "value", "label+percent", "label+value"], "d": "label+percent"},
    "pie_direction":       {"t": "select", "l": "Direction", "k": "pd", "o": ["clockwise", "counterclockwise"], "d": "clockwise"},
    "table_index_align":   {"t": "select", "l": "Index align", "k": "tia", "o": ["left", "center", "right"], "d": "left"},
    "table_data_align":    {"t": "select", "l": "Data align", "k": "tda", "o": ["left", "center", "right"], "d": "right"},
    "table_number_format": {"t": "select", "l": "Num format", "k": "tnf", "o": [",.2f", ",.1f", ",.0f", ".2f", ".1f", ".0f"], "d": ",.2f"},
    "heatmap_colorscale":  {"t": "select", "l": "Colorscale", "k": "cs", "o": "COLORSCALES_ALL", "d": "RdBu"},
    # Colorbar controls
    "colorbar_title":           {"t": "text", "l": "CB title", "k": "cbt", "d": ""},
    "colorbar_tick_size":       {"t": "slider", "l": "CB tick sz", "k": "cbts", "lo": 6, "hi": 18, "d": 10, "s": 1},
    "colorbar_tick_color":      {"t": "color", "l": "CB tick clr", "k": "cbtc", "d": "#94a3b8"},
    "colorbar_title_size":      {"t": "slider", "l": "CB title sz", "k": "cbtsz", "lo": 8, "hi": 24, "d": 11, "s": 1},
    "colorbar_title_color":     {"t": "color", "l": "CB title clr", "k": "cbtclr", "d": "#cbd5e1"},
    # Sliders
    "bar_gap":                      {"t": "slider", "l": "Bar gap", "k": "bgap", "lo": 0.0, "hi": 1.0, "d": 0.28, "s": 0.01},
    "histogram_bins":               {"t": "slider", "l": "Bins", "k": "hbins", "lo": 5, "hi": 200, "d": 30, "s": 1},
    "histogram_opacity":            {"t": "slider", "l": "Opacity", "k": "hop", "lo": 0.1, "hi": 1.0, "d": 0.8, "s": 0.05},
    "line_width":                   {"t": "slider", "l": "Line width", "k": "lw", "lo": 1, "hi": 10, "d": 2, "s": 1},
    "marker_opacity":               {"t": "slider", "l": "M. opacity", "k": "mo", "lo": 0.1, "hi": 1.0, "d": 0.8, "s": 0.05},
    "marker_size":                  {"t": "slider", "l": "M. size", "k": "ms", "lo": 2, "hi": 30, "d": 6, "s": 1},
    "donut_hole":                   {"t": "slider", "l": "Donut", "k": "dh", "lo": 0.0, "hi": 0.9, "d": 0.0, "s": 0.05},
    "pull_slices":                  {"t": "slider", "l": "Pull", "k": "ps", "lo": 0.0, "hi": 0.5, "d": 0.0, "s": 0.01},
    "pie_rotation":                 {"t": "slider", "l": "Rotation", "k": "pr", "lo": 0, "hi": 360, "d": 0, "s": 1},
    "pie_label_size":               {"t": "slider", "l": "Label sz", "k": "pls", "lo": 6, "hi": 24, "d": 11, "s": 1},
    "pie_value_size":               {"t": "slider", "l": "Value sz", "k": "pvs", "lo": 6, "hi": 24, "d": 11, "s": 1},
    "render_mode":                  {"t": "select", "l": "Render mode", "k": "rm", "o": ["svg", "webgl"], "d": "svg"},
    "heatmap_annotation_precision": {"t": "slider", "l": "Precision", "k": "hap", "lo": 0, "hi": 10, "d": 2, "s": 1},
    "heatmap_annotation_size":      {"t": "slider", "l": "Ann sz", "k": "has", "lo": 6, "hi": 24, "d": 10, "s": 1},
    "table_font_size":              {"t": "slider", "l": "Font sz", "k": "tfs", "lo": 8, "hi": 24, "d": 11, "s": 1},
    "table_header_font_size":       {"t": "slider", "l": "Hdr font", "k": "thfs", "lo": 8, "hi": 24, "d": 12, "s": 1},
    "table_row_height":             {"t": "slider", "l": "Row h", "k": "trh", "lo": 16, "hi": 60, "d": 26, "s": 1},
    "table_header_height":          {"t": "slider", "l": "Hdr h", "k": "thh", "lo": 16, "hi": 60, "d": 28, "s": 1},
    # Colors
    "pie_label_color":              {"t": "color", "l": "Label", "k": "plc", "d": "#e2e8f0"},
    "pie_value_color":              {"t": "color", "l": "Value", "k": "pvc", "d": "#e2e8f0"},
    "table_font_color":             {"t": "color", "l": "Font", "k": "tfc", "d": "#f1f5f9"},
    "table_header_color":           {"t": "color", "l": "Header", "k": "thc", "d": "#6163df"},
    "table_stripe_even_color":      {"t": "color", "l": "Even", "k": "tsec", "d": "#1e293b"},
    "table_stripe_odd_color":       {"t": "color", "l": "Odd", "k": "tsoc", "d": "#0f172a"},
    "heatmap_annotation_color":     {"t": "color", "l": "Ann color", "k": "hac", "d": "#ffffff"},
    # Text
    "row_index_header":             {"t": "text", "l": "Row index", "k": "rih", "d": ""},
}


def _render_control(control: str, opts: dict, uid: str, key_prefix: str) -> None:
    """Render a single control widget. Updates opts in-place."""
    m = _CONTROL_META.get(control)
    if not m:
        return
    _key = f"{key_prefix}_{m['k']}_{uid}"

    # Special case: heatmap_annotation_color has auto/light/dark modes
    if control == "heatmap_annotation_color":
        _ac = opts.get(control, "auto")
        if _ac in ("auto", "light"):
            _default = "#ffffff"
        elif _ac == "dark":
            _default = "#1e293b"
        else:
            _default = _ac if str(_ac).startswith("#") else "#ffffff"
        opts[control] = st.color_picker(
            m["l"], value=_default, key=_key,
            help="Auto adapts to cell values")
        return

    _val = opts.get(control, m["d"])
    if m["t"] == "check":
        opts[control] = st.checkbox(m["l"], value=bool(_val), key=_key)
    elif m["t"] == "select":
        _options = COLORSCALES_ALL if m["o"] == "COLORSCALES_ALL" else m["o"]
        _idx = _options.index(_val) if _val in _options else 0
        opts[control] = st.selectbox(m["l"], _options, index=_idx, key=_key)
    elif m["t"] == "slider":
        if isinstance(m["lo"], int) and isinstance(m["hi"], int):
            opts[control] = st.slider(
                m["l"], m["lo"], m["hi"], int(_val), m["s"], key=_key)
        else:
            opts[control] = st.slider(
                m["l"], m["lo"], m["hi"], float(_val), m["s"], key=_key)
    elif m["t"] == "color":
        opts[control] = st.color_picker(m["l"], value=str(_val), key=_key)
    elif m["t"] == "text":
        opts[control] = st.text_input(m["l"], value=str(_val), key=_key)


def _render_in_rows(controls: list[str], per_row: int,
                    opts: dict, uid: str, key_prefix: str) -> None:
    """Render a list of controls in rows of *per_row* columns."""
    for i in range(0, len(controls), per_row):
        _row = controls[i:i + per_row]
        _cols = st.columns(len(_row))
        for j, c in enumerate(_row):
            with _cols[j]:
                _render_control(c, opts, uid, key_prefix)


def get_chart_type_capabilities(chart_type: str) -> dict[str, Any]:
    return CHART_TYPE_SETTINGS.get(chart_type, {
        "has_axes": False, "has_legend": False,
        "controls": ["title"],
        "typography": ["family", "font_style", "header"],
    })



def has_control(chart_type: str, control: str) -> bool:
    return control in get_chart_type_capabilities(chart_type).get("controls", [])



def has_typography(chart_type: str, typo_category: str) -> bool:
    return typo_category in get_chart_type_capabilities(chart_type).get("typography", [])


def is_dual_axis_chart(fig) -> bool:
    """Detect if a figure has dual Y-axes (secondary_y traces)."""
    try:
        yaxis_count = sum(1 for tr in getattr(fig, 'data', []) if getattr(tr, 'yaxis', None) == 'y2')
        return yaxis_count > 0
    except Exception:
        return False


def _safe_get_secondary_traces(fig):
    """Get traces on secondary Y-axis safely."""
    try:
        return [tr for tr in getattr(fig, 'data', []) if getattr(tr, 'yaxis', None) == 'y2']
    except Exception:
        return []



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



def _decode_plotly_array(value):
    """Decode a Plotly trace array back into a plain Python list.

    ``copy.deepcopy`` on a Plotly figure serialises numpy arrays into a
    compact dict like ``{'dtype': 'i1', 'bdata': 'AQID...', 'shape': '12'}``.
    Iterating that dict yields string keys, so ``float(v)`` fails and value
    labels silently disappear.  This helper normalises ndarray / dict /
    list / tuple back to a list of scalars.
    """
    if value is None:
        return None
    if isinstance(value, dict) and "bdata" in value:
        try:
            import base64 as _b64
            import numpy as _np
            _dtype_map = {
                "f8": "<f8", "f4": "<f4", "i1": "<i1", "i2": "<i2",
                "i4": "<i4", "i8": "<i8", "u1": "<u1", "u2": "<u2",
                "u4": "<u4", "u8": "<u8", "b": "|b1",
            }
            _dtype = _np.dtype(
                _dtype_map.get(str(value.get("dtype", "f8")), str(value.get("dtype", "<f8")))
            )
            _shape = tuple(
                int(s) for s in str(value.get("shape", "")).split(",") if s.strip()
            )
            _arr = _np.frombuffer(_b64.b64decode(value["bdata"]), dtype=_dtype)
            if _shape:
                _arr = _arr.reshape(_shape)
            return _arr.tolist()
        except Exception as exc:
            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
            return None
    if isinstance(value, (list, tuple)):
        return list(value)
    return value


def _apply_font_only(fig, meta: dict | None, chart_type: str = ""):
    """Lightweight typography-only post-processor -- no deepcopy, no O(points)
    per-trace textfont loop.

    Applies header / global font, axis tick+title fonts, legend title+item
    fonts and pie label/value fonts via O(1) layout updates.  Returns the same
    figure object (mutated in-place).
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

    _fs_lower = str(ts.get("font_style", "Normal")).lower()
    _weight = "bold" if "bold" in _fs_lower else "normal"
    _style  = "italic" if "italic" in _fs_lower else "normal"
    _font_style_dict = dict(family=_font_family, weight=_weight, style=_style)

    try:
        fig.update_layout(
            title=dict(text="", font=dict(size=_hdr_size, color=_hdr_color, family=_hdr_family)),
            font=_font_style_dict,
            legend=dict(
                bgcolor=str(ts.get("legend_bgcolor", "rgba(0,0,0,0)")),
                title=dict(font=dict(size=int(ts.get("legend_title_size", 12)),
                                     color=str(ts.get("legend_title_color", "#cbd5e1")),
                                     family=_font_family, weight=_weight, style=_style)),
                font=dict(size=int(ts.get("legend_item_size", 11)),
                          color=str(ts.get("legend_item_color", "#e2e8f0")),
                          family=_font_family, weight=_weight, style=_style),
            ),
        )
        axis_title_font = dict(size=int(ts.get("axis_title_size", 12)),
                               color=str(ts.get("axis_title_color", "#cbd5e1")),
                               family=_font_family, weight=_weight, style=_style)
        axis_tick_font  = dict(size=int(ts.get("axis_tick_size", 10)),
                               color=str(ts.get("axis_tick_color", "#94a3b8")),
                               family=_font_family, weight=_weight, style=_style)
        fig.update_xaxes(title_font=axis_title_font, tickfont=axis_tick_font)
        fig.update_yaxes(title_font=axis_title_font, tickfont=axis_tick_font)
    except Exception as exc:
        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
        pass

    # Pie label/value fonts are per-trace but pie charts have few slices, so a
    # light loop here is cheap and keeps pie typography live.
    _pie_lbl_sz  = ts.get("pie_label_size")
    _pie_lbl_clr = ts.get("pie_label_color")
    _pie_val_sz  = ts.get("pie_value_size")
    _pie_val_clr = ts.get("pie_value_color")
    if _pie_lbl_sz or _pie_lbl_clr or _pie_val_sz or _pie_val_clr:
        for tr in fig.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            if ttype not in ("pie", "sunburst", "treemap"):
                continue
            for _pf_attr in ("insidetextfont", "outsidetextfont", "textfont"):
                _pf = getattr(tr, _pf_attr, None)
                if _pf is None:
                    continue
                _upd = {}
                if _pie_lbl_sz:
                    _upd["size"] = int(_pie_lbl_sz)
                if _pie_lbl_clr and _pie_lbl_clr != "auto":
                    _upd["color"] = _pie_lbl_clr
                if _upd:
                    try:
                        if isinstance(_pf, dict):
                            _pf.update(_upd)
                        else:
                            for _k, _v in _upd.items():
                                setattr(_pf, _k, _v)
                    except Exception as exc:
                        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                "header_family", "header_font_style"):
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
        If True, mutate fig in-place instead of copying.
    matrix_view : str
        "heatmap" when matrix_table should render as heatmap.
    """
    meta = meta or {}
    opts = meta.get("display_options", {})
    if not isinstance(opts, dict):
        opts = {}
    f2 = fig if _inplace else copy.deepcopy(fig)
    
    # Fast path for scatter plots with only font/axis changes — skip deep trace iteration
    _is_scatter = chart_type == "scatter_plot"
    _scatter_fast = (
        _is_scatter
        and not opts.get("show_value_labels")
        and not opts.get("marker_opacity")
        and not opts.get("marker_size")
        and not opts.get("line_width")
        and not opts.get("line_fill")
    )

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

    # Fast path: skip trace iteration for simple scatter font/axis changes
    if not _scatter_fast:
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
                            y_vals = _decode_plotly_array(getattr(tr, "y", None))
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
                            except Exception as exc:
                                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                        except Exception as exc:
                            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                    except Exception as exc:
                        logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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

    _x_label = meta.get("x_label", "")
    _y_label = meta.get("y_label", "")
    _y2_label = meta.get("y2_label", "")

    def _safe_update_xaxes(fig, **kwargs):
        """Update xaxes, falling back without row/col if figure lacks subplots."""
        try:
            fig.update_xaxes(**kwargs)
        except Exception as exc:
            if "make_subplots" in str(exc):
                kwargs.pop("row", None)
                kwargs.pop("col", None)
                fig.update_xaxes(**kwargs)
            else:
                raise

    def _safe_update_yaxes(fig, **kwargs):
        """Update yaxes, falling back without row/col if figure lacks subplots."""
        try:
            fig.update_yaxes(**kwargs)
        except Exception as exc:
            if "make_subplots" in str(exc):
                kwargs.pop("row", None)
                kwargs.pop("col", None)
                fig.update_yaxes(**kwargs)
            else:
                raise

    if _x_label:
        _safe_update_xaxes(f2, title=dict(text=_x_label, font=_font_style_dict), row=1, col=1)
    else:
        _safe_update_xaxes(f2, title=dict(font=_font_style_dict), row=1, col=1)
        
    if _y_label:
        if is_dual_axis_chart(f2):
            _safe_update_yaxes(f2, title=dict(text=_y_label, font=_font_style_dict), secondary_y=False, row=1, col=1)
        else:
            _safe_update_yaxes(f2, title=dict(text=_y_label, font=_font_style_dict), row=1, col=1)
    else:
        if is_dual_axis_chart(f2):
            _safe_update_yaxes(f2, title=dict(font=_font_style_dict), secondary_y=False, row=1, col=1)
        else:
            _safe_update_yaxes(f2, title=dict(font=_font_style_dict), row=1, col=1)
        
    if _y2_label:
        _safe_update_yaxes(f2, title=dict(text=_y2_label, font=_font_style_dict), secondary_y=True, row=1, col=1)
    elif is_dual_axis_chart(f2):
        _safe_update_yaxes(f2, title=dict(font=_font_style_dict), secondary_y=True, row=1, col=1)

    text_style = meta.get("text_style", {})
    if isinstance(text_style, dict) and text_style:
        ts = merge_text_style(text_style)

        # The global "family" is the master control.  Header
        # fonts follow it unless explicitly customized to a non-default.
        _hdr_family_raw = str(ts.get("header_family") or _raw_family)
        if _hdr_family_raw == "Inter" and _raw_family not in ("Inter", ""):
            _hdr_family_raw = _raw_family
        _hdr_family     = resolve_font_stack(_hdr_family_raw)
        _hdr_style      = str(ts.get("header_font_style", "Normal"))
        _hdr_size       = int(ts.get("header_size", 28))
        _hdr_color      = str(ts.get("header_color", "#6163df"))

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
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass

        # The title is rendered in the HTML preview area (chart_card ctrl[0]),
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
                    # Apply universal font family and style
                    _upd["family"] = _font_family
                    _upd["weight"] = _weight
                    _upd["style"] = _style
                    if _upd:
                        try:
                            if isinstance(_pf, dict):
                                _pf.update(_upd)
                            else:
                                for _k, _v in _upd.items():
                                    setattr(_pf, _k, _v)
                        except Exception as exc:
                            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                    # Apply universal font family and style
                    _upd["family"] = _font_family
                    _upd["weight"] = _weight
                    _upd["style"] = _style
                    if _upd:
                        try:
                            if isinstance(_pf, dict):
                                _pf.update(_upd)
                            else:
                                for _k, _v in _upd.items():
                                    setattr(_pf, _k, _v)
                        except Exception as exc:
                            logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                    pass
            try:
                cb_kwargs = dict(
                    tickfont=dict(size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix),
                )
                if cb_title:
                    cb_kwargs["title"] = dict(text=cb_title, font=dict(size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix))
                f2.update_coloraxes(colorbar=cb_kwargs)
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass
            _map_cs = opts.get("heatmap_colorscale")
            if _map_cs:
                try:
                    f2.update_coloraxes(colorscale=str(_map_cs))
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                    pass
        else:
            # Apply colorscale via update_coloraxes for px.imshow compatibility
            _map_cs = opts.get("heatmap_colorscale")
            if _map_cs:
                try:
                    f2.update_coloraxes(colorscale=str(_map_cs))
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                    pass

            # Build colorbar config for correlation/matrix_heatmap
            cb_tick_sz   = int(opts.get("colorbar_tick_size", 10))
            cb_tick_col  = str(opts.get("colorbar_tick_color", "#94a3b8"))
            cb_title_sz  = int(opts.get("colorbar_title_size", 11))
            cb_title_col = str(opts.get("colorbar_title_color", "#cbd5e1"))
            cb_family    = resolve_font_stack(str(opts.get("colorbar_font_family", _raw_family)))
            cb_title     = opts.get("colorbar_title", "")
            _cb_font_suffix = dict(weight=_weight, style=_style)
            
            cb_kwargs = dict(
                tickfont=dict(size=cb_tick_sz, color=cb_tick_col, family=cb_family, **_cb_font_suffix),
            )
            if cb_title:
                cb_kwargs["title"] = dict(text=cb_title, font=dict(size=cb_title_sz, color=cb_title_col, family=cb_family, **_cb_font_suffix))
            
            try:
                f2.update_coloraxes(colorbar=cb_kwargs)
            except Exception as exc:
                logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                pass

            for tr in f2.data:
                ttype_for_cb = str(getattr(tr, "type", "")).lower()
                if ttype_for_cb not in ("heatmap", "choropleth"):
                    continue
                cell_sz      = int(opts.get("heatmap_font_size", 10))
                _ann_sz  = opts.get("heatmap_annotation_size")
                final_sz = int(_ann_sz) if _ann_sz is not None else cell_sz
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
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
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
                except Exception as exc:
                    logging.getLogger(__name__).debug("Suppressed error: %s", exc, exc_info=True)
                    pass

    return f2


# ---------------------------------------------------------------------------
# Public renderer API (imported by chart_card.py / analysis.py / dashboard.py)
# ---------------------------------------------------------------------------
def render_chart_settings_controls(uid: str, title: str, fig, chart_type: str,
                                   meta: dict, *,
                                   key_prefix: str = "analysis",
                                   show_text_style: bool = False,
                                   matrix_view: str = "") -> dict:
    """Render the Chart Settings for a single chart (compact column layout).

    Returns a dict of changed meta keys so the caller can persist them.
    Uses _render_control / _render_in_rows for auto-grouped multi-column rows.
    """
    opts = dict(meta.get("display_options", {}))
    result: dict[str, Any] = {}
    stype = chart_type

    if stype == "matrix_table" and matrix_view == "heatmap":
        stype = "matrix_heatmap"

    caps = get_chart_type_capabilities(stype)
    controls = caps.get("controls", [])
    _adv = set(CONTROLS_ADVANCED.get(stype, []))

    def _is_main(c):
        return c in controls and c not in _adv and c in _CONTROL_META

    # ---- title (full width) ----------------------------------------------
    nt = st.text_input(
        "Chart title",
        value=meta.get("custom_title", title),
        key=f"{key_prefix}_title_{uid}",
    )
    if nt != meta.get("custom_title", title):
        result["custom_title"] = nt

    # ---- axes labels (adaptive: 2 or 3 columns for dual-axis charts) -----
    if caps.get("has_axes", False):
        _is_dual = is_dual_axis_chart(fig)
        if _is_dual:
            # Dual-axis: X-axis | Y-axis (left) | Y-axis (right)
            _ac = st.columns(3)
            with _ac[0]:
                xl = st.text_input(
                    "X-axis", value=meta.get("x_label", ""),
                    key=f"{key_prefix}_xl_{uid}",
                )
            with _ac[1]:
                yl = st.text_input(
                    "Y-axis (left)", value=meta.get("y_label", ""),
                    key=f"{key_prefix}_yl_{uid}",
                )
            with _ac[2]:
                y2l = st.text_input(
                    "Y-axis (right)", value=meta.get("y2_label", ""),
                    key=f"{key_prefix}_y2l_{uid}",
                )
            if xl != meta.get("x_label", ""):
                result["x_label"] = xl
            if yl != meta.get("y_label", ""):
                result["y_label"] = yl
            if y2l != meta.get("y2_label", ""):
                result["y2_label"] = y2l
        else:
            # Single-axis: X-axis | Y-axis
            _ac = st.columns(2)
            with _ac[0]:
                xl = st.text_input(
                    "X-axis", value=meta.get("x_label", ""),
                    key=f"{key_prefix}_xl_{uid}",
                )
            with _ac[1]:
                yl = st.text_input(
                    "Y-axis", value=meta.get("y_label", ""),
                    key=f"{key_prefix}_yl_{uid}",
                )
            if xl != meta.get("x_label", ""):
                result["x_label"] = xl
            if yl != meta.get("y_label", ""):
                result["y_label"] = yl

    # ---- legend title (full width) ---------------------------------------
    if caps.get("has_legend", False):
        _leg_title = st.text_input(
            "Legend title", value=meta.get("legend_title", ""),
            key=f"{key_prefix}_leg_title_{uid}",
        )
        if _leg_title != meta.get("legend_title", ""):
            result["legend_title"] = _leg_title

    # ---- main controls grouped by widget type -----------------------------
    _main = [c for c in controls if _is_main(c)]

    # Checkboxes (4 per row)
    _checks = [c for c in _main if _CONTROL_META[c]["t"] == "check"]
    _render_in_rows(_checks, 4, opts, uid, key_prefix)

    # Selects (2 per row)
    _sels = [c for c in _main if _CONTROL_META[c]["t"] == "select"]
    _render_in_rows(_sels, 2, opts, uid, key_prefix)

    # Sliders (2 per row)
    _slis = [c for c in _main if _CONTROL_META[c]["t"] == "slider"]
    _render_in_rows(_slis, 2, opts, uid, key_prefix)

    # Colors (3 per row)
    _cols = [c for c in _main if _CONTROL_META[c]["t"] == "color"]
    _render_in_rows(_cols, 3, opts, uid, key_prefix)

    # Text (full width)
    _txts = [c for c in _main if _CONTROL_META[c]["t"] == "text"]
    for c in _txts:
        _render_control(c, opts, uid, key_prefix)

    # ---- advanced popover -------------------------------------------------
    _adv_present = [c for c in controls if c in _adv and c in _CONTROL_META]
    if _adv_present:
        with st.popover("⚙️ Advanced"):
            for c in _adv_present:
                _render_control(c, opts, uid, key_prefix)

    result["display_options"] = opts
    return result


def render_typography_controls(uid: str, fig, chart_type: str,
                               meta: dict, *, key_prefix: str = "analysis") -> dict:
    """Render the Typography controls for a single chart (compact layout).

    Returns a dict of typography key-value pairs (flat dict, NOT {"text_style": ...}).
    Global row: font family, style, header size, header color, header font.
    Per-element (axis, legend, pie) in an Advanced popover.
    """
    text_style = dict(meta.get("text_style", {}))
    # Only inject essential fonts by default - full font list loaded when user opens font picker
    inject_font_preview_css(["Inter", "Sora"])
    caps = get_chart_type_capabilities(chart_type)
    typo = caps.get("typography", [])

    # ---- global row 1: Font family | Font style (2 columns) ---------------
    _r1 = st.columns(2)
    with _r1[0]:
        fam = font_select(
            "Font family",
            text_style.get("family", "Inter"),
            key=f"{key_prefix}_font_{uid}",
        )
        if fam != text_style.get("family"):
            text_style["family"] = fam
    with _r1[1]:
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

    # ---- global row 2: Header size | Header color (2 cols) ---------------
    _r2 = st.columns(2)
    with _r2[0]:
        _hs = st.number_input(
            "Header size", 10, 60,
            int(text_style.get("header_size", 28)), 1,
            key=f"{key_prefix}_hsize_{uid}",
        )
        if _hs != text_style.get("header_size"):
            text_style["header_size"] = _hs
    with _r2[1]:
        _hc = st.color_picker(
            "Header color",
            text_style.get("header_color", "#6163df"),
            key=f"{key_prefix}_hcolor_{uid}",
        )
        if _hc != text_style.get("header_color"):
            text_style["header_color"] = _hc

    # ---- global row 3: Header font | Header font style (2 cols) -----------
    _r3 = st.columns(2)
    with _r3[0]:
        _hfam = font_select(
            "Header font",
            text_style.get("header_family", text_style.get("family", "Inter")),
            key=f"{key_prefix}_hfont_{uid}",
        )
        if _hfam != text_style.get("header_family", text_style.get("family", "Inter")):
            text_style["header_family"] = _hfam
    with _r3[1]:
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
        if _hfstyle != text_style.get("header_font_style"):
            text_style["header_font_style"] = _hfstyle

    # ---- advanced: per-element typography ---------------------------------
    _has_adv = any(t in typo for t in
                   ["axis_tick", "axis_title", "legend_title",
                    "legend_item", "pie_label", "pie_value"])
    if _has_adv:
        with st.popover("⚙️ Advanced"):
            # Axis tick
            if "axis_tick" in typo:
                st.caption("Axis ticks")
                _tc = st.columns(2)
                with _tc[0]:
                    _ats = st.number_input(
                        "Tick size", 6, 18,
                        int(text_style.get("axis_tick_size", 10)), 1,
                        key=f"{key_prefix}_atsize_{uid}",
                    )
                    if _ats != text_style.get("axis_tick_size"):
                        text_style["axis_tick_size"] = _ats
                with _tc[1]:
                    _atc = st.color_picker(
                        "Tick color",
                        text_style.get("axis_tick_color", "#94a3b8"),
                        key=f"{key_prefix}_atcolor_{uid}",
                    )
                    if _atc != text_style.get("axis_tick_color"):
                        text_style["axis_tick_color"] = _atc

            # Axis title
            if "axis_title" in typo and chart_type != "correlation":
                st.caption("Axis titles")
                _ac = st.columns(2)
                with _ac[0]:
                    _axs = st.number_input(
                        "Title size", 8, 24,
                        int(text_style.get("axis_title_size", 12)), 1,
                        key=f"{key_prefix}_ax_titlesize_{uid}",
                    )
                    if _axs != text_style.get("axis_title_size"):
                        text_style["axis_title_size"] = _axs
                with _ac[1]:
                    _axc = st.color_picker(
                        "Title color",
                        text_style.get("axis_title_color", "#cbd5e1"),
                        key=f"{key_prefix}_ax_titlecolor_{uid}",
                    )
                    if _axc != text_style.get("axis_title_color"):
                        text_style["axis_title_color"] = _axc

            # Legend
            if "legend_title" in typo or "legend_item" in typo:
                st.caption("Legend")
                _lc = st.columns(2)
                with _lc[0]:
                    _lts = st.number_input(
                        "Title size", 8, 24,
                        int(text_style.get("legend_title_size", 12)), 1,
                        key=f"{key_prefix}_ltsize_{uid}",
                    )
                    if _lts != text_style.get("legend_title_size"):
                        text_style["legend_title_size"] = _lts
                with _lc[1]:
                    _ltc = st.color_picker(
                        "Title color",
                        text_style.get("legend_title_color", "#cbd5e1"),
                        key=f"{key_prefix}_ltcolor_{uid}",
                    )
                    if _ltc != text_style.get("legend_title_color"):
                        text_style["legend_title_color"] = _ltc
                _lc2 = st.columns(2)
                with _lc2[0]:
                    _lis = st.number_input(
                        "Item size", 8, 20,
                        int(text_style.get("legend_item_size", 11)), 1,
                        key=f"{key_prefix}_lisize_{uid}",
                    )
                    if _lis != text_style.get("legend_item_size"):
                        text_style["legend_item_size"] = _lis
                with _lc2[1]:
                    _lic = st.color_picker(
                        "Item color",
                        text_style.get("legend_item_color", "#e2e8f0"),
                        key=f"{key_prefix}_licolor_{uid}",
                    )
                    if _lic != text_style.get("legend_item_color"):
                        text_style["legend_item_color"] = _lic

            # Pie label
            if "pie_label" in typo:
                st.caption("Pie labels")
                _pc = st.columns(2)
                with _pc[0]:
                    _pls = st.number_input(
                        "Label size", 8, 24,
                        int(text_style.get("pie_label_size", 11)), 1,
                        key=f"{key_prefix}_plsize_{uid}",
                    )
                    if _pls != text_style.get("pie_label_size"):
                        text_style["pie_label_size"] = _pls
                with _pc[1]:
                    _plc = st.color_picker(
                        "Label color",
                        text_style.get("pie_label_color", "#e2e8f0"),
                        key=f"{key_prefix}_plcolor_{uid}",
                    )
                    if _plc != text_style.get("pie_label_color"):
                        text_style["pie_label_color"] = _plc

            # Pie value
            if "pie_value" in typo:
                st.caption("Pie values")
                _vc = st.columns(2)
                with _vc[0]:
                    _pvs = st.number_input(
                        "Value size", 8, 24,
                        int(text_style.get("pie_value_size", 11)), 1,
                        key=f"{key_prefix}_pvsize_{uid}",
                    )
                    if _pvs != text_style.get("pie_value_size"):
                        text_style["pie_value_size"] = _pvs
                with _vc[1]:
                    _pvc = st.color_picker(
                        "Value color",
                        text_style.get("pie_value_color", "#e2e8f0"),
                        key=f"{key_prefix}_pvcolor_{uid}",
                    )
                    if _pvc != text_style.get("pie_value_color"):
                        text_style["pie_value_color"] = _pvc

    return text_style