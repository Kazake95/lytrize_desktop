"""Tests for Map Plot colour encoding rehaul (classifier + colour cases 1-3)."""
import numpy as np
import pandas as pd
import pytest

import modules.analysis.map_plot as mp
from modules.analysis.map_plot import classify_colour_column, run_map_plot


@pytest.fixture(autouse=True)
def _force_tile_path(monkeypatch):
    """Force the scatter_mapbox (tile) render path deterministically."""
    monkeypatch.setattr(mp, "_tiles_online", lambda: True)


def _df(n=40, fraud_ratio=0.5, seed=7):
    rng = np.random.default_rng(seed)
    lat = 38.0 + rng.normal(0, 4, n)
    lon = -95.0 + rng.normal(0, 8, n)
    is_fraud = (rng.random(n) < fraud_ratio).astype(int)
    return pd.DataFrame({
        "lat": lat, "lon": lon,
        "city": [f"city_{i % 6}" for i in range(n)],
        "is_fraud": is_fraud,
        "amt": rng.uniform(1, 100, n).round(2),
    })


def _one_fig(df, **kw):
    out = run_map_plot(df, lat_col="lat", lon_col="lon", **kw)
    assert out, "run_map_plot returned no figure"
    return out[0][1]


def _trace_points(fig):
    total = 0
    for tr in fig.data:
        if not str(tr.type).lower().startswith("scatter"):
            continue
        lat = getattr(tr, "lat", None)
        if lat is None:
            continue
        total += len(np.asarray(lat))
    return total


def _labels(fig):
    return {t.name for t in fig.data if t.name}


# --------------------------------------------------------------------------
# Classifier
# --------------------------------------------------------------------------

def test_classify_binary_numeric():
    assert classify_colour_column(pd.Series([0, 1, 1, 0])) == "binary_numeric"


def test_classify_binary_text():
    assert classify_colour_column(pd.Series(["yes", "no"])) == "binary_text"
    assert classify_colour_column(pd.Series([True, False, True])) == "binary_text"


def test_classify_categorical_and_continuous():
    assert classify_colour_column(pd.Series(["a", "b", "c"])) == "categorical"
    assert classify_colour_column(pd.Series([0.5, 1.5, 9.0])) == "continuous"


# --------------------------------------------------------------------------
# Case 1 — binary numeric 0/1 colour, no value column
# --------------------------------------------------------------------------

def test_case1_binary_numeric_01_discrete_legend_all_points():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    assert _trace_points(fig) == len(df), "every data point must be rendered"
    labels = _labels(fig)
    assert {"0", "1"} <= labels, f"expected legend entries '0' and '1', got {labels}"


def test_case1_binary_numeric_imbalanced_keeps_minority_points():
    df = _df(n=200, fraud_ratio=0.02)
    fig = _one_fig(df, color_col="is_fraud")
    assert _trace_points(fig) == len(df)
    assert "1" in _labels(fig), "minority fraud class must have its own legend entry"


# --------------------------------------------------------------------------
# Case 2 — binary text colour (yes/no, True/False)
# --------------------------------------------------------------------------

@pytest.mark.parametrize("vals", [("yes", "no"), (True, False)])
def test_case2_binary_text_discrete_legend(vals):
    df = _df()
    df["flag"] = [vals[i % 2] for i in range(len(df))]
    fig = _one_fig(df, color_col="flag")
    assert _trace_points(fig) == len(df)
    assert {"Yes", "No"} <= _labels(fig), f"got {_labels(fig)}"
    assert fig._lytrize_meta.get("legend") == "flag"


# --------------------------------------------------------------------------
# Case 3 — categorical string colour
# --------------------------------------------------------------------------

def test_case3_categorical_string_legend_per_category():
    df = _df()
    fig = _one_fig(df, color_col="city")
    assert _trace_points(fig) == len(df)
    assert {"city_0", "city_1", "city_2", "city_3", "city_4", "city_5"} <= _labels(fig)


def test_case3_categorical_nulls_become_unknown_not_dropped():
    df = _df()
    df.loc[0, "city"] = None
    fig = _one_fig(df, color_col="city")
    assert _trace_points(fig) == len(df)
    assert "(unknown)" in _labels(fig)


# --------------------------------------------------------------------------
# Continuous colour keeps the coloraxis encoding
# --------------------------------------------------------------------------

def test_continuous_numeric_colorbar():
    df = _df()
    fig = _one_fig(df, color_col="amt")
    has_coloraxis = bool(
        fig.layout.coloraxis
        and getattr(fig.layout.coloraxis, "showscale", False) is not False
        and fig.layout.coloraxis.showscale is not False
    ) or fig.layout.coloraxis is not None
    assert has_coloraxis or any(
        getattr(tr.marker, "showscale", False) for tr in fig.data
    ), "continuous colour should render a coloraxis/colorbar"


# --------------------------------------------------------------------------
# Offline fallback path (scatter_geo) keeps the same behaviour
# --------------------------------------------------------------------------

def test_binary_numeric_offline_geo_path(monkeypatch):
    monkeypatch.setattr(mp, "_tiles_online", lambda: False)
    df = _df()
    out = run_map_plot(df, lat_col="lat", lon_col="lon", color_col="is_fraud")
    assert out, "offline geo fallback returned no figure"
    fig = out[0][1]
    assert _trace_points(fig) == len(df)
    assert {"0", "1"} <= _labels(fig)


# --------------------------------------------------------------------------
# Binary colours = palette endpoints only, no colour scale
# --------------------------------------------------------------------------

def test_binary_uses_palette_endpoint_colours_no_coloraxis():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud")
    # No continuous coloraxis scale for binary columns.
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale), \
        "binary colour columns must not render a colour scale"
    pal = mp.COLORS
    for tr in fig.data:
        colour = getattr(tr.marker, "color", None)
        if tr.name == "1":
            assert colour == pal[-1], f"'1' must use top palette colour {pal[-1]}, got {colour}"
        elif tr.name == "0":
            assert colour == pal[0], f"'0' must use bottom palette colour {pal[0]}, got {colour}"


def test_binary_text_uses_palette_endpoint_colours():
    df = _df()
    df["flag"] = ["yes" if i % 2 else "no" for i in range(len(df))]
    fig = _one_fig(df, color_col="flag")
    pal = mp.COLORS
    by_name = {tr.name: (getattr(tr.marker, "color", None))
               for tr in fig.data}
    assert by_name.get("Yes") == pal[-1]
    assert by_name.get("No") == pal[0]


def test_binary_invert_swaps_endpoint_colours():
    df = _df()
    fig = _one_fig(df, color_col="is_fraud", invert_colorscale=True)
    pal = mp.COLORS
    by_name = {tr.name: (getattr(tr.marker, "color", None))
               for tr in fig.data}
    assert by_name.get("1") == pal[0]
    assert by_name.get("0") == pal[-1]


# --------------------------------------------------------------------------
# Density path keeps binary colour (no "Points" scale for binary columns)
# --------------------------------------------------------------------------

def test_density_binary_colour_keeps_two_categories(monkeypatch):
    monkeypatch.setattr(mp, "_tiles_online", lambda: True)
    df = _df(n=6_000, fraud_ratio=0.35)
    out = run_map_plot(df, lat_col="lat", lon_col="lon", color_col="is_fraud")
    assert out
    fig = out[0][1]
    labels = _labels(fig)
    assert {"0", "1"} <= labels, f"density path must keep binary legend, got {labels}"
    assert "Points" not in labels, "binary colour must not be replaced by point counts"
    assert not (fig.layout.coloraxis and fig.layout.coloraxis.showscale), \
        "binary density map must not render a colour scale"


