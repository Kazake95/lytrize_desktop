"""Tests for Map Plot cases 4-5: value-column tooltip + size-by-value tick box."""
import re

import numpy as np
import pandas as pd
import pytest

import modules.analysis.map_plot as mp
from modules.analysis.map_plot import run_map_plot
from modules.ui.chart_settings import apply_chart_display_options


@pytest.fixture(autouse=True)
def _force_tile_path(monkeypatch):
    monkeypatch.setattr(mp, "_tiles_online", lambda: True)


def _df(n=40, seed=7):
    rng = np.random.default_rng(seed)
    return pd.DataFrame({
        "lat": 38.0 + rng.normal(0, 4, n),
        "lon": -95.0 + rng.normal(0, 8, n),
        "city": [f"city_{i % 6}" for i in range(n)],
        "is_fraud": (rng.random(n) < 0.3).astype(int),
        "amt": rng.uniform(1, 100, n).round(2),
    })


def _one_fig(df, **kw):
    out = run_map_plot(df, lat_col="lat", lon_col="lon", **kw)
    assert out, "run_map_plot returned no figure"
    return out[0][1]


# --------------------------------------------------------------------------
# Case 4 — value column shows in the hover tooltip
# --------------------------------------------------------------------------

def test_case4_value_col_in_hover():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud", location_col="city",
                   value_col="amt", agg_func="mean")
    tr = fig.data[0]
    # Aggregated value column must be part of the hover configuration
    # (customdata feeds the tooltip fields built from hover_data).
    assert tr.customdata is not None, "aggregated value missing from hover data"
    cd = np.asarray(tr.customdata)
    assert cd.ndim == 2 and cd.shape[1] >= 2, (
        "hover must carry value + colour column data"
    )
    assert "MEAN(amt)" in (fig.layout.title.text or "")


def test_case4_value_not_sized_by_default():
    df = _df()
    fig = _one_fig(df, value_col="amt")
    tr = fig.data[0]
    size = tr.marker.size
    assert not hasattr(size, "__len__"), (
        "value column must not drive marker size unless 'Size by value' is ticked"
    )


# --------------------------------------------------------------------------
# Case 5 — size-by-value tick box
# --------------------------------------------------------------------------

def test_case5_size_by_value_sets_array_sizes():
    df = _df()
    fig = _one_fig(df, value_col="amt", size_by_value=True)
    tr = fig.data[0]
    size = list(np.asarray(tr.marker.size).ravel())
    assert len(size) == len(df), "per-point sizes required"
    assert len(set(size)) > 1, "sizes must vary with the value column"
    assert fig._lytrize_meta.get("value_sized") is True


def test_case5_manual_size_cannot_override_when_value_sized():
    df = _df()
    fig = _one_fig(df, value_col="amt", size_by_value=True)
    before = [list(np.asarray(t.marker.size).ravel()) for t in fig.data]
    meta = {"display_options": {"marker_size": 25, "marker_opacity": 0.9}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    after = [list(np.asarray(t.marker.size).ravel()) for t in fig.data]
    assert before == after, "manual M. size must not override value-driven sizes"
    assert fig.data[0].marker.opacity == pytest.approx(0.9)


def test_case5_manual_size_applies_when_not_value_sized():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    meta = {"display_options": {"marker_size": 13}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    assert int(fig.data[0].marker.size) == 13


# --------------------------------------------------------------------------
# Size-by-value via the public kwargs surface (regression guard)
# --------------------------------------------------------------------------

def test_size_by_value_kwarg_passthrough():
    df = _df()
    out = run_map_plot(
        df, lat_col="lat", lon_col="lon",
        location_col="city", value_col="amt",
        agg_func="mean", size_by_value=True,
    )
    assert out
    fig = out[0][1]
    assert fig._lytrize_meta.get("value_sized") is True


# --------------------------------------------------------------------------
# Size by value via Chart Settings > Layout display option
# --------------------------------------------------------------------------

def test_size_by_value_display_option_builds_sizes():
    df = _df()
    fig = _one_fig(df, value_col="amt")
    assert not hasattr(fig.data[0].marker.size, "__len__")
    meta = {"display_options": {"size_by_value": True}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    size = list(np.asarray(fig.data[0].marker.size).ravel())
    assert len(size) == len(df)
    assert len(set(size)) > 1


def test_size_by_value_display_option_off_restores_scalar():
    df = _df()
    fig = _one_fig(df, value_col="amt")
    apply_chart_display_options(
        fig, {"display_options": {"size_by_value": True}}, "map_plot", _inplace=True)
    apply_chart_display_options(
        fig, {"display_options": {"size_by_value": False, "marker_size": 8}},
        "map_plot", _inplace=True)
    assert not hasattr(fig.data[0].marker.size, "__len__")
    assert int(fig.data[0].marker.size) == 8


# --------------------------------------------------------------------------
# Chart Settings Colorbar controls must not create a scale on binary maps
# --------------------------------------------------------------------------

def test_colorbar_checkbox_cannot_force_scale_on_binary_map():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    meta = {"display_options": {
        "show_colorbar": True,
        "heatmap_colorscale": "YlOrRd",
        "colorbar_title": "is_fraud",
    }}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    # No coloraxis scale may appear for a binary (discrete) colour map.
    ca = fig.layout.coloraxis
    assert not (ca and getattr(ca, "showscale", None)), (
        "Colorbar checkbox must not force a colour scale onto binary maps"
    )
    for tr in fig.data:
        assert not getattr(tr.marker, "showscale", None)
        # Colours stay the flat palette endpoints, not a colourscale ramp.
        assert getattr(tr.marker, "colorscale", None) is None


def test_colorbar_still_works_for_continuous_map():
    df = _df()
    fig = _one_fig(df, color_col="amt")  # continuous -> trace-level colorbar
    meta = {"display_options": {"show_colorbar": True,
                                "heatmap_colorscale": "YlOrRd"}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    # Colourbar toggle drives the layout coloraxis for continuous maps.
    assert getattr(fig.layout.coloraxis, "showscale", None) is True
    # And the encoding tag keeps it styled as continuous.
    assert fig._lytrize_meta.get("colour_encoding") == "continuous"


# --------------------------------------------------------------------------
# Density path: cells containing ANY 1s must show as 1 (max aggregation)
# --------------------------------------------------------------------------

def test_density_binary_max_keeps_minority_cells_visible():
    import modules.analysis.map_plot as mp
    df = _df(n=6_000)
    out = run_map_plot(df, lat_col="lat", lon_col="lon", color_col="is_fraud")
    assert out
    fig = out[0][1]
    labels = {t.name for t in fig.data if t.name}
    assert "1" in labels, "cells containing fraud points must render as '1'"
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale)
    assert fig.data[0].customdata is not None
    # "Points" is an internal density helper — it must NOT appear in the
    # hover tooltip when a real colour column drives the colours.
    hd = fig.data[0].hovertemplate or ""
    assert "Points" not in hd, "Points count must be hidden when a colour column is selected"


def test_density_categorical_colour_keeps_discrete_legend():
    """Regression: the density path used to REPLACE a categorical colour
    column with the cell point count ('Points'), so the legend disappeared
    and NaN categories leaked into the hover tooltip."""
    rng = np.random.default_rng(9)
    n = 7_000  # > _MAP_SAMPLE threshold to trigger the density path
    df = pd.DataFrame({
        "lat": rng.uniform(25, 49, n),
        "lon": rng.uniform(-120, -71, n),
        "category": rng.choice(
            ["home", "work", "other", None, "park"], n, p=[0.3, 0.3, 0.2, 0.1, 0.1]
        ),
    })
    out = run_map_plot(df, lat_col="lat", lon_col="lon", color_col="category")
    assert out, "density categorical map produced no figure"
    fig = out[0][1]
    labels = {t.name for t in fig.data if t.name}
    # All four real categories must appear; NaN becomes "(unknown)".
    assert {"home", "work", "other", "park", "(unknown)"} <= labels, (
        f"density categorical map must keep a discrete category legend, got {labels}"
    )
    # No colour scale / coloraxis — this is a discrete legend.
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale)
    for tr in fig.data:
        assert getattr(tr.marker, "colorscale", None) is None
    # Hover tooltip must NOT leak "NaN" or "Points" for a categorical colour map.
    hd = fig.data[0].hovertemplate or ""
    assert "NaN" not in hd, f"hover must not show NaN, got: {hd}"
    assert "Points" not in hd, f"density must hide 'Points' when colour column drives legend, got: {hd}"


# --------------------------------------------------------------------------
# Value column + binary colour: colour stays discrete 0/1, value is tooltip/size only
# --------------------------------------------------------------------------

def test_value_plus_binary_colour_stays_discrete():
    df = _df()
    out = run_map_plot(
        df, lat_col="lat", lon_col="lon",
        location_col="city", value_col="amt",
        color_col="is_fraud", agg_func="mean",
    )
    assert out
    fig = out[0][1]
    labels = {t.name for t in fig.data if t.name}
    assert {"0", "1"} <= labels, f"binary colour must stay a 0/1 legend, got {labels}"
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale), \
        "value column aggregation must not turn binary colour into a colour scale"
    for tr in fig.data:
        assert getattr(tr.marker, "colorscale", None) is None
    # Aggregated value still appears in the hover configuration.
    hd = fig.data[0].hovertemplate or ""
    assert "mean(amt)" in hd


# --------------------------------------------------------------------------
# Chart Settings behaviour
# --------------------------------------------------------------------------

def test_size_by_value_works_with_string_category_colour():
    """Regression: mixed object-dtype customdata (string colour + numeric
    value) used to kill value-driven sizes via a whole-array float cast."""
    n = 400
    rng = np.random.default_rng(0)
    df = pd.DataFrame({
        "lat": rng.uniform(25, 49, n), "lon": rng.uniform(-120, -70, n),
        "city": [f"c{i % 25}" for i in range(n)],
        "category": rng.choice(["food", "travel", "home", None], n),
        "is_fraud": rng.integers(0, 2, n), "amt": rng.uniform(1, 100, n),
    })
    out = run_map_plot(df, lat_col="lat", lon_col="lon",
                       location_col="city", color_col="category",
                       value_col="is_fraud", agg_func="sum")
    fig = out[0][1]
    meta = {"display_options": {"size_by_value": True}}
    fig2 = apply_chart_display_options(fig, meta, "map_plot")
    for tr in fig2.data:
        sz = tr.marker.size
        assert hasattr(sz, "__len__") and not isinstance(sz, str), (
            f"trace '{tr.name}': size_by_value must build per-point sizes "
            "even when a string colour column is present"
        )
        assert max(sz) > min(sz)


def test_nan_like_category_strings_show_unknown():
    n = 200
    rng = np.random.default_rng(1)
    df = pd.DataFrame({
        "lat": rng.uniform(25, 49, n), "lon": rng.uniform(-120, -70, n),
        "city": [f"c{i % 10}" for i in range(n)],
        "category": ["NaN"] * n,  # literal nan-like strings from a CSV
        "is_fraud": rng.integers(0, 2, n),
    })
    out = run_map_plot(df, lat_col="lat", lon_col="lon",
                       location_col="city", color_col="category",
                       value_col="is_fraud", agg_func="sum")
    fig = out[0][1]
    labels = {t.name for t in fig.data if t.name}
    assert labels == {"(unknown)"}, (
        f"nan-like strings must render as '(unknown)', got {labels}"
    )
    hd = fig.data[0].hovertemplate or ""
    assert "NaN" not in hd


def test_hover_keeps_string_category_no_float_format():
    """Regression: the hover_decimals rewriter float-formatted EVERY
    customdata token — the string colour category rendered as 'NaN'."""
    n = 200
    rng = np.random.default_rng(2)
    df = pd.DataFrame({
        "lat": rng.uniform(25, 49, n), "lon": rng.uniform(-120, -70, n),
        "city": [f"c{i % 10}" for i in range(n)],
        "category": rng.choice(["food", "travel", "home"], n),
        "is_fraud": rng.integers(0, 2, n),
    })
    out = run_map_plot(df, lat_col="lat", lon_col="lon",
                       location_col="city", color_col="category",
                       value_col="is_fraud", agg_func="sum")
    fig = out[0][1]
    fig2 = apply_chart_display_options(fig, {"display_options": {}}, "map_plot")
    ht = fig2.data[0].hovertemplate or ""
    # Numeric value column keeps 2-decimal formatting...
    assert "sum(is_fraud)=%{customdata[" in ht and ":.2f}" in ht
    # ...but the string colour token must NOT be float-formatted.
    assert re.search(r"category=%\{customdata\[\d+\]\}", ht), (
        f"string colour token must stay unformatted, got: {ht}"
    )


def test_m_opacity_slider_applies_to_map_markers():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    meta = {"display_options": {"marker_opacity": 0.5}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    assert fig.data[0].marker.opacity == pytest.approx(0.5), (
        "Chart Settings 'M. opacity' slider must always apply to map markers"
    )


def test_cb_controls_style_category_legend_on_discrete_map():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    meta = {"display_options": {
        "colorbar_title": "Fraud",
        "colorbar_title_size": 15,
        "colorbar_title_color": "#ff0000",
        "colorbar_tick_size": 13,
        "colorbar_tick_color": "#00ff00",
    }}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    leg = fig.layout.legend
    assert getattr(leg.title, "text", None) == "Fraud", (
        "CB title must style the category legend title on discrete maps"
    )
    assert leg.title.font.size == 15
    assert leg.title.font.color == "#ff0000"
    assert leg.font.size == 13
    assert leg.font.color == "#00ff00"


def test_cb_controls_work_without_encoding_tag():
    """Saved/reloaded figures lose the _lytrize_meta tag — the CB controls
    must still style the category legend via figure inspection fallback."""
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    del fig._lytrize_meta  # simulate serialisation round-trip
    assert not hasattr(fig, "_lytrize_meta")
    meta = {"display_options": {
        "colorbar_title": "Fraud",
        "colorbar_tick_size": 12,
        "colorbar_tick_color": "#123456",
        "heatmap_colorscale": "Blues",
    }}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    leg = fig.layout.legend
    assert getattr(leg.title, "text", None) == "Fraud"
    assert leg.font.size == 12
    assert leg.font.color == "#123456"
    assert all(isinstance(tr.marker.color, str) for tr in fig.data)


def test_colorscale_dropdown_recolours_category_legend():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    before = [str(tr.marker.color) for tr in fig.data]
    meta = {"display_options": {"heatmap_colorscale": "Blues"}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    after = [str(tr.marker.color) for tr in fig.data]
    assert before != after, "Colorscale dropdown must recolour category legends"
    # Solid colours per trace, never a colour scale.
    for tr in fig.data:
        assert isinstance(tr.marker.color, str)
        assert not getattr(tr.marker, "showscale", None)
        assert getattr(tr.marker, "colorscale", None) is None
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale)


def test_size_by_value_noop_without_value_column():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")  # no value column
    before = getattr(fig.data[0].marker, "size", None)
    meta = {"display_options": {"size_by_value": True}}
    apply_chart_display_options(fig, meta, "map_plot", _inplace=True)
    after = getattr(fig.data[0].marker, "size", None)
    assert before == after, "size_by_value must be a no-op when no value column exists"

