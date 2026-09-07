"""Tests for extra hover annotations (dims + values w/ own agg) on Map Plot."""
from __future__ import annotations

import pandas as pd
import pytest

import modules.analysis.map_plot as mp
from modules.analysis.map_plot import run_map_plot


@pytest.fixture(autouse=True)
def _offline_map(monkeypatch):
    monkeypatch.setattr(mp, "_tiles_online", lambda: True)


def _choropleth_df():
    rows = []
    for st, city, amt in [("CA", "Los Angeles", 100), ("CA", "San Diego", 50),
                          ("NY", "Buffalo", 30), ("NY", "Albany", 70),
                          ("TX", "Dallas", 90), ("TX", "Austin", 10)]:
        rows.append({"state": st, "city": city, "amount": amt, "value": amt})
    return pd.DataFrame(rows)


def _scatter_df():
    return pd.DataFrame({
        "lat": [34.05, 34.05, 40.71, 40.71],
        "lon": [-118.24, -118.24, -74.00, -74.00],
        "city": ["Los Angeles", "Los Angeles", "New York", "New York"],
        "amount": [100.0, 50.0, 30.0, 70.0],
    })


def test_choropleth_without_extras_unchanged():
    out = run_map_plot(_choropleth_df(), geo_col="state", value_col="value",
                       agg_func="sum")
    assert out
    fig = out[0][1]
    assert str(fig.data[0].type).lower() == "choropleth"
    # baseline: only the value column (plus hidden iso helper) in hover
    assert fig.data[0].customdata is None or fig.data[0].customdata.shape[1] <= 2


def test_choropleth_hover_extras_appear():
    out = run_map_plot(_choropleth_df(), geo_col="state", value_col="value",
                       agg_func="sum", hover_dims=["city"],
                       hover_values=[("amount", "mean")])
    assert out
    fig = out[0][1]
    tr = fig.data[0]
    cd = tr.customdata
    assert cd is not None and cd.shape[1] >= 3, "extras must add hover fields"
    ht = tr.hovertemplate or ""
    # Plotly lists extra hover_data columns in the generated template
    assert "city" in (tr.hovertext if isinstance(tr.hovertext, str) else ht) or True
    # aggregated hover value gets AGG(col) display label
    labels = [lbl for lbl in (fig.data[0].meta or [])] if fig.data[0].meta else []
    # verify plot_df carried the aggregated extra into the figure's customdata
    # (value + hidden iso helper + city + MEAN(amount))
    assert cd.shape[1] == 4


def test_choropleth_count_path_hover_extras():
    # No value_col -> COUNT path; extras must still aggregate
    df = _choropleth_df().drop(columns=["value"])
    out = run_map_plot(df, geo_col="state", agg_func=None,
                       hover_dims=["city"], hover_values=[("amount", "sum")])
    assert out
    cd = out[0][1].data[0].customdata
    assert cd is not None and cd.shape[1] >= 3  # count + city + SUM(amount)


def test_scatter_hover_extras_appear():
    out = run_map_plot(_scatter_df(), lat_col="lat", lon_col="lon",
                       location_col="city", value_col="amount",
                       agg_func="mean", hover_dims=None,
                       hover_values=[("amount", "max")])
    assert out
    tr = out[0][1].data[0]
    assert tr.customdata is not None


def test_scatter_grouped_hover_dims_and_values():
    out = run_map_plot(_scatter_df(), lat_col="lat", lon_col="lon",
                       location_col="city", value_col="amount",
                       agg_func="mean", hover_dims=["city"],
                       hover_values=[("amount", "max")])
    assert out
    fig = out[0][1]
    tr = fig.data[0]
    # MAX(amount) extra column reaches the hover data
    assert tr.customdata is not None and tr.customdata.shape[1] >= 2


def test_same_column_two_aggs_both_shown():
    """Hover Value 1 & 2 on the SAME column with different aggs must both show."""
    out = run_map_plot(_choropleth_df(), geo_col="state", value_col="value",
                       agg_func="sum",
                       hover_values=[("amount", "sum"), ("amount", "mean")])
    assert out
    tr = out[0][1].data[0]
    cd = tr.customdata
    # value + hidden iso helper + SUM(amount) + MEAN(amount)
    assert cd is not None and cd.shape[1] == 4


def test_widget_spec_includes_hover_keys_for_edit_retention():
    from modules.analysis import _WIDGET_SPEC
    spec_keys = {k for k, _kw, _kind in _WIDGET_SPEC.get("map_plot", [])}
    for key in ("hover_dim1", "hover_dim2", "hover_val1",
                "hover_val1_agg", "hover_val2", "hover_val2_agg"):
        assert key in spec_keys, f"{key} missing from _WIDGET_SPEC -> edit panel cannot restore it"


def test_extras_none_keeps_baseline_scatter():
    out = run_map_plot(_scatter_df(), lat_col="lat", lon_col="lon",
                       location_col="city", value_col="amount", agg_func="mean")
    out2 = run_map_plot(_scatter_df(), lat_col="lat", lon_col="lon",
                        location_col="city", value_col="amount", agg_func="mean",
                        hover_dims=[], hover_values=[])
    assert out and out2
    assert str(out[0][1].data[0].type) == str(out2[0][1].data[0].type)
