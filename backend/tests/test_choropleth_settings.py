"""Tests for Choropleth Map chart-settings (merged Colorscale + colorbar controls)."""
from __future__ import annotations

import pandas as pd
import pytest

import modules.analysis.map_plot as mp
from modules.ui.chart_settings import (
    _detect_map_encoding,
    apply_chart_display_options,
)


@pytest.fixture(autouse=True)
def _offline_map(monkeypatch):
    """Force the offline (non-scatter_mapbox) path — choropleth doesn't need tiles."""
    monkeypatch.setattr(mp, "_tiles_online", lambda: True)


def _df():
    """Synthetic US-state dataset that resolves via the US-state map."""
    states = ["CA", "NY", "TX", "FL", "IL", "OH", "PA", "GA", "NC", "MI"]
    vals = list(range(10, 10 * 10 + 1, 10))  # 10..100
    return pd.DataFrame({"state": states, "value": vals})


def _one_choropleth(**kw):
    out = mp.run_map_plot(_df(), geo_col="state", value_col="value",
                          agg_func="sum", **kw)
    assert out, "run_map_plot returned no figure"
    return out[0][1]


def test_detect_map_encoding_choropleth_is_continuous():
    fig = _one_choropleth()
    assert str(fig.data[0].type).lower() == "choropleth"
    assert _detect_map_encoding(fig) == "continuous"


def test_choropleth_meta_tag_continuous():
    fig = _one_choropleth()
    assert fig._lytrize_meta.get("colour_encoding") == "continuous"


def test_colorbar_toggle_controls_layout_coloraxis():
    fig = _one_choropleth()
    # ON
    meta = {"display_options": {"show_colorbar": True}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    assert fig.layout.coloraxis.showscale is True
    # OFF
    meta = {"display_options": {"show_colorbar": False}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    assert fig.layout.coloraxis.showscale is False


def test_colorbar_title_ticks_and_colors_reach_coloraxis():
    fig = _one_choropleth()
    meta = {"display_options": {
        "show_colorbar": True,
        "colorbar_title": "Total",
        "colorbar_tick_size": 13,
        "colorbar_tick_color": "#00ff00",
        "colorbar_title_size": 17,
        "colorbar_title_color": "#ff00ff",
    }}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    cb = fig.layout.coloraxis.colorbar
    assert cb.title.text == "Total"
    assert cb.title.font.size == 17
    assert cb.title.font.color == "#ff00ff"
    assert cb.tickfont.size == 13
    assert cb.tickfont.color == "#00ff00"


def test_colorscale_merges_into_choropleth():
    fig = _one_choropleth(choropleth_colorscale="Viridis")
    before = str(fig.layout.coloraxis.colorscale)
    meta = {"display_options": {"heatmap_colorscale": "YlOrRd",
                                "show_colorbar": True}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    after = str(fig.layout.coloraxis.colorscale)
    assert before != after, "Colorscale dropdown must change the choropleth scale"


def test_typography_propagates_to_colorbar_font():
    fig = _one_choropleth()
    meta = {
        "display_options": {"show_colorbar": True, "colorbar_title": "Total"},
        "text_style": {"family": "Georgia", "font_style": "Bold"},
    }
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    cb = fig.layout.coloraxis.colorbar
    # The colorbar tickfont inherits the global family + weight.
    assert "Georgia" in (cb.tickfont.family or "")
    bold = cb.tickfont.to_plotly_json().get("weight")
    if bold is None:
        weights = {getattr(cb.tickfont, "weight", None)}
        bold = "bold" if ("bold" in weights or weights == {None}) else None
    assert bold in ("bold", None)
    # The colorbar title font should also be tied to the global family.
    title_family = getattr(cb.title.font, "family", "") or ""
    assert "Georgia" in title_family