"""
modules/ui/chart_settings.py -- Shared chart setting schema and Plotly adapters.

This module is the single place for dashboard/analysis chart presentation
options.  Pages render the controls here; exporters and preview renderers call
apply_chart_display_options() so saved metadata behaves consistently.

"""

from __future__ import annotations

import copy
import functools
import re
import subprocess
from typing import Any

import streamlit as st

from modules.charts import clean_insight_text

# ── Colorscale catalogue ──────────────────────────────────────────────────────
COLORSCALES_DIVERGING  = ["RdBu", "RdYlBu", "PRGn", "PiYG", "BrBG", "Spectral"]
COLORSCALES_SEQUENTIAL = ["Blues", "Viridis", "Plasma", "Magma", "Cividis",
                           "YlOrRd", "YlGnBu", "Greens", "Oranges", "Purples"]
COLORSCALES_ALL        = COLORSCALES_DIVERGING + COLORSCALES_SEQUENTIAL


# ── Chart-type settings schema ────────────────────────────────────────────────
# Each analysis type has a dedicated set of capabilities and allowed controls.
# This replaces the unreliable trace_capabilities() runtime detection for UI.
#
# To add controls for a new analysis type, simply add an entry here.
#
# Fields:
#   has_axes:    Does this chart type have cartesian X/Y axes?
#   has_legend:  Does it show a per-trace legend?
#   controls:    List of UI control names to show in the chart settings panel.
#   typography:  List of typography option categories to show.

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
        "typography": ["family", "font_style", "header", "subtitle"],
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
                    "line_width", "line_shape", "show_markers", "line_fill"],
        "typography": ["family", "font_style", "header", "subtitle",
                      "axis_title", "axis_tick", "legend_title", "legend_item"],
    },
    "matrix_table": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "table_font_size", "table_font_color",
                    "table_header_font_size", "table_row_height", "table_header_height",
                    "table_index_align", "table_data_align", "table_show_footer",
                    "table_gradient_cells", "table_show_row_totals",
                    "row_index_header", "column_dimension_header"],
        "typography": ["family", "font_style", "header", "subtitle"],
    },
    "map_plot": {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle",
                    "show_colorbar", "colorbar_title",
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


# ── Helper functions for chart-type-based capability detection ─────────────────

def get_chart_type_capabilities(chart_type: str) -> dict[str, Any]:
    \"\"\"
    Return capabilities dict for a given chart type.

    This is the REPLACEMENT for trace_capabilities() when chart_type is known.
    It uses the declarative CHART_TYPE_SETTINGS schema instead of runtime
    trace inspection, making it deterministic and correct for every chart type.
    Keys returned: has_axes, has_legend, controls, typography
    \"\"\"
    return CHART_TYPE_SETTINGS.get(chart_type, {
        "has_axes": False, "has_legend": False,
        "controls": ["title", "subtitle"],
        "typography": ["family", "font_style", "header", "subtitle"],
    })


def has_control(chart_type: str, control: str) -> bool:
    \"\"\"Check if a control is valid for this chart type.\"\"\"
    return control in get_chart_type_capabilities(chart_type).get("controls", [])


def has_typography(chart_type: str, typo_category: str) -> bool:
    \"\"\"Check if a typography category is valid for this chart type.\"\"\"
    return typo_category in get_chart_type_capabilities(chart_type).get("typography", [])


def compute_meta_hash(meta: dict | None) -> str:
    \"\"\"
    Compute a deterministic hash of chart display metadata.

    Used for cache invalidation — when the hash changes, the chart figure
    needs to be rebuilt.  Only fields that affect the rendered figure are included.
    \"\"\"
    if not meta:
        return ""
    relevant = {}
    for key in ("custom_title", "subtitle", "x_label", "y_label",
                "legend_title", "legend_names", "text_style",
                "display_options", "colorbar_zmin", "colorbar_zmax",
                "show_auto_insights", "hidden_insights"):
        if key in meta:
            relevant[key] = meta[key]
    return json.dumps(relevant, sort_keys=True, default=str)


def default_text_style() -> dict:
    return {
        "family":             "Inter, system-ui, sans-serif",
        "font_style":         "Normal",
        "header_size":        28,
        "header_color":       "#6163df",
        "subtitle_size":      11,
        "subtitle_color":     "#64748b",
        "legend_title_size":  12,
        "legend_title_color": "#cbd5e1",
        "legend_item_size":   11,
        "legend_item_color":  "#e2e8f0",
        "axis_title_size":    12,
        "axis_title_color":   "#cbd5e1",
        "axis_tick_size":     10,
        "axis_tick_color":    "#94a3b8",
    }


def _system_font_families() -> list[str]:
    try:
        output = subprocess.check_output(
            ["fc-list", "-f", "%{family}\n"],
            stderr=subprocess.DEVNULL,
            text=True,
        )
        families = []
        for line in output.splitlines():
            for family in re.split(r",\s*", line.strip()):
                if family and family not in families:
                    families.append(family)
                if len(families) >= 120:
                    break
            if len(families) >= 120:
                break
        if families:
            return families
    except Exception:
        pass
    return [
        "Inter", "Roboto", "Open Sans", "Arial", "Helvetica", "Verdana",
        "DejaVu Sans", "Liberation Sans", "Noto Sans", "Sans-Serif",
        "Georgia", "Times New Roman", "Courier New", "Monospace",
    ]


@functools.lru_cache(maxsize=1)
def available_font_families() -> list[str]:
    return _system_font_families()


def _wrap_html_style(text: str, style: str) -> str:
    text = str(text or "")
    style = str(style or "").lower()
    if text == "" or style in ("", "normal"):
        return text
    # Strip any existing simple inline tags before applying the selected style.
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
        "has_heatmap":   bool(types & {"heatmap", "choropleth", "scattermapbox", "scattermap"}),
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


# ── Apply ─────────────────────────────────────────────────────────────────────

def apply_chart_display_options(
    fig,
    meta: dict | None,
    chart_type: str = "",
    *,
    _inplace: bool = False,
):
    """Return a figure with chart-type-specific display metadata applied.

    Args:
        _inplace: When True the caller has already deep-copied ``fig`` and we
                  can mutate it directly, avoiding a second expensive deepcopy.
                  Callers that pass the original (un-copied) figure must leave
                  this False (the default).
    """
    meta = meta or {}
    opts = meta.get("display_options", {})
    if not isinstance(opts, dict):
        opts = {}
    # Skip the deepcopy when the caller guarantees the figure is already a
    # private copy (e.g. analysis._render_chart_list which deepcopies first).
    f2 = fig if _inplace else copy.deepcopy(fig)

    try:
        # ── Layout-level options ──────────────────────────────────────────────
        if "show_legend" in opts:
            f2.update_layout(showlegend=bool(opts["show_legend"]))
        if "bar_gap" in opts:
            f2.update_layout(bargap=float(opts["bar_gap"]))
        if opts.get("bar_mode"):
            f2.update_layout(barmode=str(opts["bar_mode"]))

        # ── Per-trace options ─────────────────────────────────────────────────
        show_labels = bool(opts.get("show_value_labels", False))
        label_pos   = opts.get("label_position", "outside")

        for tr in f2.data:
            ttype = str(getattr(tr, "type", "") or "").lower()
            mode  = str(getattr(tr, "mode", "") or "")

            if ttype == "bar":
                tr.textposition = label_pos if show_labels else "none"

            # Apply value labels to line traces in dual-axis charts.
            # Requires mode to include "text"; "lines+markers" alone does not show labels.
            if ttype in ("scatter", "scattergl") and "lines" in mode:
                if show_labels:
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

            if ttype == "heatmap":
                if opts.get("heatmap_colorscale"):
                    tr.colorscale = str(opts["heatmap_colorscale"])
                show_text = opts.get("heatmap_show_text")
                if show_text is False:
                    tr.text         = None
                    tr.texttemplate = None
                prec = opts.get("heatmap_annotation_precision")
                if prec is not None and getattr(tr, "texttemplate", None) is not None:
                    tr.texttemplate = f"%{{text:.{int(prec)}f}}"
                ann_size       = opts.get("heatmap_annotation_size")
                ann_color_mode = opts.get("heatmap_annotation_color", "auto")
                if ann_color_mode == "auto":
                    # Pick whichever of white vs dark-navy has better perceived
                    # contrast.  We use the midpoint of the colorscale range as a
                    # proxy for average cell brightness — simple but effective.
                    try:
                        z_vals = [v for row in (tr.z or []) for v in (row or []) if v is not None]
                        if z_vals:
                            z_mid   = (min(z_vals) + max(z_vals)) / 2
                            z_range = max(z_vals) - min(z_vals) or 1
                            # Normalise 0-1; values above 0.55 tend to be light cells
                            norm_mid = (z_mid - min(z_vals)) / z_range
                            ann_color = "white" if norm_mid < 0.55 else "#1e293b"
                        else:
                            ann_color = "white"
                    except Exception:
                        ann_color = "white"
                else:
                    ann_color = {"light": "white", "dark": "#1e293b"}.get(ann_color_mode)
                if ann_size is not None or ann_color is not None:
                    existing_font = dict(getattr(tr, "textfont", None) or {})
                    if ann_size  is not None: existing_font["size"]  = int(ann_size)
                    if ann_color is not None: existing_font["color"] = ann_color
                    tr.textfont = existing_font

            if ttype == "table":
                # The matrix table uses TWO go.Table traces: trace[0] is the
                # main data table, trace[1] is the footer (column totals).
                # The footer trace has an all-empty header (height=0 to hide it).
                # Applying data styling to the footer trace makes its invisible
                # header visible and corrupts alignment — skip it here.
                # Footer visibility is handled separately below.
                _hdr_vals = getattr(tr.header, "values", None) or []
                _is_footer_trace = all(
                    str(v).strip() in ("", "[]", "None")
                    for v in _hdr_vals
                ) and len(_hdr_vals) > 0
                if _is_footer_trace:
                    continue  # leave footer trace untouched; handled in footer block

                cell_size    = int(opts.get("table_font_size", 11))
                header_size  = int(opts.get("table_header_font_size", max(cell_size, 12)))
                row_h        = int(opts.get("table_row_height", 26))
                hdr_h        = int(opts.get("table_header_height", 34))
                idx_align    = opts.get("table_index_align", "left")
                data_align   = opts.get("table_data_align", "right")
                _cell_font = dict(getattr(tr.cells, "font", None) or {})
                _cell_font["size"]  = cell_size
                _cell_font["color"] = str(opts.get("table_font_color") or _cell_font.get("color") or "#f1f5f9")
                tr.cells.font   = _cell_font
                tr.header.font  = dict(size=header_size, color="white",
                                       family="Inter, system-ui, sans-serif")
                tr.cells.height  = row_h
                tr.header.height = hdr_h
                if hasattr(tr.cells, "align") and hasattr(tr.header, "values"):
                    n_hdr_cols = len(tr.header.values) if tr.header.values else 0
                    if n_hdr_cols > 1:
                        tr.cells.align  = [idx_align] + [data_align] * (n_hdr_cols - 1)
                        tr.header.align = [idx_align] + ["center"] * (n_hdr_cols - 1)
                # Toggle gradient cells
                if opts.get("table_gradient_cells") is False:
                    n_rows = len(tr.cells.values[0]) if tr.cells.values else 0
                    flat_fills = ["#1e293b" if i % 2 == 0 else "#0f172a" for i in range(n_rows)]
                    tr.cells.fill_color = [flat_fills] * max(len(tr.cells.values), 1)
                # Toggle row totals column — remove from both main and footer trace
                if opts.get("table_show_row_totals") is False:
                    try:
                        vals_list = list(tr.cells.values)
                        hdr_list  = list(tr.header.values)
                        if len(vals_list) > 1 and "Total" in str(hdr_list[-1]):
                            tr.cells.values  = vals_list[:-1]
                            tr.header.values = hdr_list[:-1]
                            cw = list(tr.columnwidth or [])
                            if cw:
                                tr.columnwidth = cw[:-1]
                            # Also remove from footer trace so column widths match
                            _all_tables = [t for t in f2.data
                                           if str(getattr(t,"type","")).lower()=="table"]
                            if len(_all_tables) >= 2:
                                _ft = _all_tables[1]
                                _fv = list(_ft.cells.values)
                                if _fv:
                                    _ft.cells.values = _fv[:-1]
                                _fcw = list(_ft.columnwidth or [])
                                if _fcw:
                                    _ft.columnwidth = _fcw[:-1]
                    except Exception:
                        pass

        # ── Colorbar visibility (map plots + heatmaps) ───────────────────────
        if "show_colorbar" in opts:
            _show_cb = bool(opts["show_colorbar"])
            for tr in f2.data:
                if hasattr(tr, "showscale"):
                    try:
                        tr.showscale = _show_cb
                    except Exception:
                        pass

        # ── Colorbar / colour-axis ────────────────────────────────────────────
        zmin = _float_or_none(opts.get("colorbar_zmin", ""))
        zmax = _float_or_none(opts.get("colorbar_zmax", ""))
        if zmin is not None or zmax is not None:
            for tr in f2.data:
                if hasattr(tr, "zmin"):
                    if zmin is not None: tr.zmin = zmin
                    if zmax is not None: tr.zmax = zmax
            f2.update_coloraxes(cmin=zmin, cmax=zmax)
        if opts.get("colorbar_title"):
            f2.update_coloraxes(
                colorbar=dict(title=dict(text=str(opts["colorbar_title"])))
            )

        # For map plots, legend_title is used as the colourbar label.
        _legend_title = meta.get("legend_title", "")
        if _legend_title and chart_type == "map_plot":
            for tr in f2.data:
                if hasattr(tr, "colorbar"):
                    try:
                        tr.colorbar.title = dict(text=str(_legend_title))
                    except Exception:
                        pass

        # ── Table footer visibility ───────────────────────────────────────────
        show_footer  = opts.get("table_show_footer", True)
        table_traces = [
            t for t in f2.data
            if str(getattr(t, "type", "")).lower() == "table"
        ]
        if len(table_traces) >= 2:
            footer_tr = table_traces[1]
            if not show_footer:
                footer_tr.cells.height  = 0
                footer_tr.header.height = 0
            else:
                if (footer_tr.cells.height or 0) == 0:
                    footer_tr.cells.height  = 28
                    footer_tr.header.height = 0

        # ── Typography / text_style ──────────────────────────────────────────
        text_style = meta.get("text_style", {})
        if isinstance(text_style, dict) and text_style:
            ts = merge_text_style(text_style)
            _font_family = str(ts.get("family", "Inter, system-ui, sans-serif"))
            # Title / header font
            _hdr_size  = int(ts.get("header_size", 28))
            _hdr_color = str(ts.get("header_color", "#6163df"))
            # Subtitle is set via annotation — handled in export; skip here
            # Axis labels
            _ax_title_size  = int(ts.get("axis_title_size", 12))
            _ax_title_color = str(ts.get("axis_title_color", "#cbd5e1"))
            _ax_tick_size   = int(ts.get("axis_tick_size", 10))
            _ax_tick_color  = str(ts.get("axis_tick_color", "#94a3b8"))
            # Legend
            _leg_title_size  = int(ts.get("legend_title_size", 12))
            _leg_title_color = str(ts.get("legend_title_color", "#cbd5e1"))
            _leg_item_size   = int(ts.get("legend_item_size", 11))
            _leg_item_color  = str(ts.get("legend_item_color", "#e2e8f0"))

            # Apply to axes — skip for map/choropleth: those layouts have no
            # cartesian axes; update_xaxes/yaxes calls are silently ignored.
            _is_map_chart = chart_type in ("map_plot",) or any(
                str(getattr(t, "type", "")).lower() in ("choropleth", "scattermapbox", "scattermap")
                for t in f2.data
            )
            if not _is_map_chart:
                axis_title_font = dict(size=_ax_title_size, color=_ax_title_color, family=_font_family)
                axis_tick_font  = dict(size=_ax_tick_size,  color=_ax_tick_color,  family=_font_family)
                f2.update_xaxes(title_font=axis_title_font, tickfont=axis_tick_font)
                f2.update_yaxes(title_font=axis_title_font, tickfont=axis_tick_font)

            # Apply to legend
            f2.update_layout(
                legend=dict(
                    title_font=dict(size=_leg_title_size, color=_leg_title_color, family=_font_family),
                    font=dict(size=_leg_item_size, color=_leg_item_color, family=_font_family),
                )
            )

            # Apply font family globally (affects all text not set above)
            f2.update_layout(font=dict(family=_font_family))

            # Apply font-style tags to titles and axis labels if the target
            # renderer supports HTML markup.
            _font_style = str(ts.get("font_style", "Normal"))
            try:
                title_text = getattr(f2.layout.title, "text", None)
                if title_text:
                    f2.update_layout(title=dict(text=_wrap_html_style(title_text, _font_style)))
            except Exception:
                pass
            for axis_name in ("xaxis", "yaxis"):
                axis_obj = getattr(f2.layout, axis_name, None)
                if axis_obj is None:
                    continue
                try:
                    axis_title = getattr(axis_obj.title, "text", None)
                    if axis_title:
                        axis_obj.title.text = _wrap_html_style(axis_title, _font_style)
                except Exception:
                    pass
            try:
                legend_title = getattr(f2.layout.legend.title, "text", None)
                if legend_title:
                    f2.update_layout(legend=dict(title=dict(text=_wrap_html_style(legend_title, _font_style))))
            except Exception:
                pass

            # Apply to colorbar if present (heatmap / choropleth)
            for tr in f2.data:
                if hasattr(tr, "colorbar") and tr.colorbar is not None:
                    try:
                        cb = dict(tr.colorbar) if tr.colorbar else {}
                        tf = dict(cb.get("tickfont") or {})
                        tf["size"]   = _ax_tick_size
                        tf["color"]  = _ax_tick_color
                        tf["family"] = _font_family
                        tr.colorbar.tickfont = tf
                    except Exception:
                        pass

    except Exception:
        return fig

    return f2


# ── Typography controls (separate expander) ────────────────────────────────────

def render_typography_controls(
    uid: str,
    fig: Any,
    chart_type: str,
    meta: dict | None,
    key_prefix: str = "analysis",
) -> dict:
    """Render typography-only controls and return text_style dict."""
    meta = meta or {}
    text_style = merge_text_style(meta.get("text_style", {}))
    caps = trace_capabilities(fig, chart_type)
    _has_axes = any((caps.get(k) for k in ("has_bar", "has_scatter", "has_line", "has_histogram")))

    t1, t2 = st.columns(2)
    with t1:
        st.markdown("**Sizes**")
        font_options = available_font_families()
        current_family = str(text_style.get("family", "Inter"))
        if current_family not in font_options:
            font_options = [current_family] + font_options
        text_style["family"] = st.selectbox(
            "Font family",
            font_options,
            index=font_options.index(current_family),
            key=f"{key_prefix}_font_{uid}",
        )
        text_style["font_style"] = st.selectbox(
            "Font style",
            [
                "Normal", "Bold", "Italic", "Underline",
                "Bold Italic", "Bold Underline", "Italic Underline",
                "Bold Italic Underline",
            ],
            index=_option_index(
                [
                    "Normal", "Bold", "Italic", "Underline",
                    "Bold Italic", "Bold Underline", "Italic Underline",
                    "Bold Italic Underline",
                ],
                str(text_style.get("font_style", "Normal")),
                "Normal",
            ),
            key=f"{key_prefix}_font_style_{uid}",
            help="Choose a text style for chart titles, axis labels, and legends.",
        )
        text_style["header_size"]   = st.slider("Header size",   14, 40, int(text_style["header_size"]),   key=f"{key_prefix}_hsize_{uid}")
        text_style["subtitle_size"] = st.slider("Subtitle size",  8, 24, int(text_style["subtitle_size"]), key=f"{key_prefix}_ssize_{uid}")
        # Axis typography is irrelevant for non-cartesian charts
        _show_axis_typo = _has_axes and chart_type not in ("map_plot", "matrix_table")
        # Hide legend colour/size controls for chart types whose legend is a
        # colour-bar rather than per-trace entries (pie/donut, heatmap, choropleth,
        # map plots, matrix tables).  These controls have no real effect for them.
        _hide_legend_controls = chart_type in (
            "matrix_table", "map_plot", "pie", "heatmap", "choropleth", "correlation"
        )
        if _show_axis_typo:
            text_style["axis_title_size"] = st.slider("Axis title size",  8, 24, int(text_style["axis_title_size"]), key=f"{key_prefix}_atsize_{uid}")
            text_style["axis_tick_size"]  = st.slider("Axis tick size",   8, 18, int(text_style["axis_tick_size"]),  key=f"{key_prefix}_ticksize_{uid}")
        if not _hide_legend_controls:
            text_style["legend_title_size"] = st.slider("Legend title size", 8, 20, int(text_style["legend_title_size"]), key=f"{key_prefix}_ltsz_{uid}")
            text_style["legend_item_size"] = st.slider("Legend item size", 8, 18, int(text_style["legend_item_size"]), key=f"{key_prefix}_lisz_{uid}")
    with t2:
        st.markdown("**Colours**")
        text_style["header_color"]   = st.color_picker("Header colour",   str(text_style["header_color"]),   key=f"{key_prefix}_hcolor_{uid}")
        text_style["subtitle_color"] = st.color_picker("Subtitle colour", str(text_style["subtitle_color"]), key=f"{key_prefix}_scolor_{uid}")
        if _show_axis_typo:
            text_style["axis_title_color"] = st.color_picker("Axis title colour", str(text_style["axis_title_color"]), key=f"{key_prefix}_atcolor_{uid}")
            text_style["axis_tick_color"]  = st.color_picker("Axis tick colour",  str(text_style["axis_tick_color"]),  key=f"{key_prefix}_tickcolor_{uid}")
        if not _hide_legend_controls:
            text_style["legend_title_color"] = st.color_picker("Legend title colour", str(text_style["legend_title_color"]), key=f"{key_prefix}_ltcolor_{uid}")
            text_style["legend_item_color"] = st.color_picker("Legend item colour", str(text_style["legend_item_color"]), key=f"{key_prefix}_licolor_{uid}")

    return text_style


# ── Render controls ───────────────────────────────────────────────────────────

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
    """Render controls and return a complete metadata update dict."""
    caps = trace_capabilities(fig, chart_type)
    opts = dict(
        meta.get("display_options", {})
        if isinstance(meta.get("display_options", {}), dict)
        else {}
    )

    # ── Title / subtitle / axis labels ────────────────────────────────────────
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
        show_legend = st.checkbox(
            "Show legend",
            value=bool(opts.get("show_legend", True)),
            key=f"{key_prefix}_legend_show_{uid}",
            disabled=not caps["has_legend"],
        )

    c, d = st.columns(2)
    # Axis labels: only show for charts that actually use cartesian axes
    _has_axes = any((caps.get(k) for k in ("has_bar", "has_scatter", "has_line", "has_histogram")))
    # Correlation and pie/donut/treemap charts do not need X/Y axis inputs
    if chart_type == "matrix_table":
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

    # ── Chart-specific options ────────────────────────────────────────────────
    st.markdown("**Chart-specific options**")
    s1, s2 = st.columns(2)

    with s1:
        # Bar (non-histogram)
        if caps["has_bar"] and not caps["has_histogram"]:
            opts["show_value_labels"] = st.checkbox(
                "Value labels",
                value=bool(opts.get("show_value_labels", False)),
                key=f"{key_prefix}_bar_labels_{uid}",
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
            # bar_mode existed in apply_chart_display_options but was never exposed — fixed
            bar_modes = ["group", "stack", "overlay", "relative"]
            opts["bar_mode"] = st.selectbox(
                "Bar mode", bar_modes,
                index=_option_index(bar_modes, opts.get("bar_mode", "group"), "group"),
                key=f"{key_prefix}_bar_mode_{uid}",
                help="group = side-by-side  ·  stack = stacked  ·  overlay = overlaid  ·  relative = diverging stack",
            )

        # Histogram
        if caps["has_histogram"]:
            opts["histogram_bins"] = st.slider(
                "Bins", 5, 120, int(opts.get("histogram_bins", 35)),
                key=f"{key_prefix}_hist_bins_{uid}",
            )
            opts["histogram_opacity"] = st.slider(
                "Opacity", 0.15, 1.0, float(opts.get("histogram_opacity", 0.75)), 0.05,
                key=f"{key_prefix}_hist_opacity_{uid}",
            )

        # Scatter
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

        # Heatmap — colour scale + range (left column)
        if caps["has_heatmap"]:
            # For map plots, expose a colorbar (legend scale) visibility toggle.
            # The colorbar on choropleth/scattermapbox can be blocked by the map tiles.
            if chart_type == "map_plot":
                opts["show_colorbar"] = st.checkbox(
                    "Show colour scale bar",
                    value=bool(opts.get("show_colorbar", True)),
                    key=f"{key_prefix}_colorbar_show_{uid}",
                    help="Toggle the colour legend/scale bar on map plots.",
                )
            _cs_idx = _option_index(COLORSCALES_ALL, opts.get("heatmap_colorscale", ""), "RdBu")
            opts["heatmap_colorscale"] = st.selectbox(
                "Colour scale", COLORSCALES_ALL, index=_cs_idx,
                key=f"{key_prefix}_heatmap_cs_{uid}",
                help=(
                    "Diverging (RdBu, RdYlBu …) — best for correlation / mean centred at 0. "
                    "Sequential (Blues, Viridis …) — best for counts and sums."
                ),
            )
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
            opts["colorbar_title"] = st.text_input(
                "Colour bar title", value=str(opts.get("colorbar_title", "")),
                key=f"{key_prefix}_cb_title_{uid}",
            )

        # Table — Excel-pivot-style granular controls (left column)
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
                "Header height (px)", 22, 60, int(opts.get("table_header_height", 34)),
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

    with s2:
        # Line
        if caps["has_line"]:
            opts["line_width"] = st.slider(
                "Line width", 1, 8, int(opts.get("line_width", 2)),
                key=f"{key_prefix}_line_width_{uid}",
            )
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

        # Pie / Donut
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
                help="Rotates which value starts at the 12-o'clock position.",
            )
            pie_dirs = ["clockwise", "counterclockwise"]
            opts["pie_direction"] = st.selectbox(
                "Slice direction", pie_dirs,
                index=_option_index(pie_dirs, opts.get("pie_direction", "clockwise"), "clockwise"),
                key=f"{key_prefix}_pie_dir_{uid}",
            )

        # Heatmap — cell annotations (right column)
        if caps["has_heatmap"]:
            _has_existing_text = any(
                getattr(t, "text", None) is not None
                for t in getattr(fig, "data", [])
                if str(getattr(t, "type", "")).lower() == "heatmap"
            )
            # Allow re-enabling annotations for correlation charts even if none were
            # generated at creation time (correlation matrices often suppress
            # annotations by default for size reasons but we want the user to
            # control precision / font / colour here).
            _heatmap_checkbox_disabled = False if chart_type == "correlation" else (not _has_existing_text and not opts.get("heatmap_show_text"))
            opts["heatmap_show_text"] = st.checkbox(
                "Show cell values",
                value=bool(opts.get("heatmap_show_text", _has_existing_text)),
                key=f"{key_prefix}_heatmap_txt_{uid}",
                disabled=_heatmap_checkbox_disabled,
                help=(
                    "Annotations suppressed at generation time for large matrices (> 18 × 18) "
                    "to prevent browser lag — re-enable with caution."
                ) if not _has_existing_text and chart_type != "correlation" else "",
            )
            _text_active = bool(opts.get("heatmap_show_text", _has_existing_text))
            opts["heatmap_annotation_precision"] = st.slider(
                "Value decimal places", 0, 4,
                int(opts.get("heatmap_annotation_precision", 2)),
                key=f"{key_prefix}_heatmap_prec_{uid}",
                disabled=not _text_active,
            )
            opts["heatmap_annotation_size"] = st.slider(
                "Annotation font size", 7, 18,
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

        # Table — footer toggle (right column)
        if caps["has_table"]:
            _has_footer = sum(
                1 for t in getattr(fig, "data", [])
                if str(getattr(t, "type", "")).lower() == "table"
            ) >= 2
            opts["table_show_footer"] = st.checkbox(
                "Show column totals footer",
                value=bool(opts.get("table_show_footer", True)),
                key=f"{key_prefix}_table_footer_{uid}",
                disabled=not _has_footer,
                help=(
                    "Show/hide the 'Total' summary row at the bottom of the pivot table."
                    if _has_footer else
                    "No footer trace in this chart."
                ),
            )
            opts["table_gradient_cells"] = st.checkbox(
                "Conditional cell gradient",
                value=bool(opts.get("table_gradient_cells", True)),
                key=f"{key_prefix}_table_grad_{uid}",
                help="Apply a subtle per-column colour gradient to data cells (like Excel conditional formatting).",
            )
            opts["table_show_row_totals"] = st.checkbox(
                "Show row totals column",
                value=bool(opts.get("table_show_row_totals", True)),
                key=f"{key_prefix}_table_row_tot_{uid}",
                help="Show a 'Total ▸' column summing each row.",
            )

    # ── Legend label overrides ────────────────────────────────────────────────
    legend_inputs    = {}
    new_legend_title = meta.get("legend_title", "")
    trace_names, seen = [], set()
    for trace in getattr(fig, "data", []):
        raw = getattr(trace, "name", None)
        if raw is not None and str(raw) not in seen:
            seen.add(str(raw))
            trace_names.append(str(raw))

    # Map plots: always show Legend Title (the colourbar title) regardless of trace count.
    if chart_type == "map_plot":
        new_legend_title = st.text_input(
            "Colour Bar Title", value=meta.get("legend_title", ""),
            key=f"{key_prefix}_legend_title_{uid}",
            help="Label shown on the map colour scale bar.",
        )
    elif len(trace_names) > 1:
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

    # ── Auto-insights visibility ──────────────────────────────────────────────
    # Map plots don't support auto-insights — hide the option entirely.
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

    # ── Typography (now rendered separately in analysis.py) ──────────────────
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
        # Surface top-level for cache invalidation — colorbar range is read from
        # opts in apply_chart_display_options so it must also be in the meta root.
        "colorbar_zmin":      opts.get("colorbar_zmin", ""),
        "colorbar_zmax":      opts.get("colorbar_zmax", ""),
    }
