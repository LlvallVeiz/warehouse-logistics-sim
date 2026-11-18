"""Tests for the layout model: geometry, distances, validation."""

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.layout import Point, WarehouseLayout


def test_bin_positions(small_layout):
    assert small_layout.total_bins == 24
    first = small_layout.bins["A01-S01"]
    assert (first.x, first.y) == (0.0, 1.0)
    last = small_layout.bins["A04-S06"]
    assert (last.x, last.y) == (9.0, 11.0)
    assert small_layout.width == 9.0


def test_same_aisle_distance(small_layout):
    p1 = Point(0.0, 1.0, 0)
    p2 = Point(0.0, 9.0, 0)
    assert small_layout.distance(p1, p2) == pytest.approx(8.0)


def test_depot_distance(small_layout):
    depot = small_layout.depot
    assert small_layout.distance(depot, Point(0.0, 1.0, 0)) == pytest.approx(1.0)
    # Aisle 3, slot 6 (x=9, y=11): front 0+11+9=20, back 12+1+9=22 -> 20.
    assert small_layout.distance(depot, Point(9.0, 11.0, 3)) == pytest.approx(20.0)


def test_cross_aisle_distance_chooses_shorter(small_layout):
    # (0,11) -> (9,1): front 11+1+9=21, back 1+11+9=21 -> 21.
    assert small_layout.distance(Point(0.0, 11.0, 0), Point(9.0, 1.0, 3)) == pytest.approx(21.0)
    # (0,1) -> (9,1): front 1+1+9=11, back 11+11+9=31 -> 11.
    assert small_layout.distance(Point(0.0, 1.0, 0), Point(9.0, 1.0, 3)) == pytest.approx(11.0)


def test_path_distance_single_pick(small_layout):
    # Depot -> (0,1) -> depot = 2 m.
    assert small_layout.path_distance([Point(0.0, 1.0, 0)]) == pytest.approx(2.0)


def test_bins_by_depot_distance(small_layout):
    nearest = small_layout.bins_by_depot_distance()
    assert nearest[0].bin_id == "A01-S01"
    distances = [small_layout.distance(small_layout.depot, b.point) for b in nearest]
    assert distances == sorted(distances)


def test_layout_validation():
    with pytest.raises(ValidationError):
        WarehouseLayout("x", 0, 10.0, 3.0, 4)
    with pytest.raises(ValidationError):
        WarehouseLayout("x", 2, -1.0, 3.0, 4)
    with pytest.raises(ValidationError):
        WarehouseLayout("x", 2, 10.0, 3.0, 0)
    with pytest.raises(ValidationError):
        WarehouseLayout("x", 2, 10.0, 3.0, 4, depot_x=99.0)


def test_layout_roundtrip(tmp_path):
    layout = WarehouseLayout("rt", 2, 10.0, 3.0, 2)
    layout.bins["A01-S01"].sku_id = "SKU-1"
    layout.bins["A01-S01"].quantity = 7
    path = tmp_path / "layout.json"
    import json

    path.write_text(json.dumps(layout.to_dict()), encoding="utf-8")
    loaded = WarehouseLayout.load_json(path)
    assert loaded.name == "rt"
    assert loaded.total_bins == 4
    assert loaded.bins["A01-S01"].sku_id == "SKU-1"
    assert loaded.bins["A01-S01"].quantity == 7


def test_load_json_errors(tmp_path):
    with pytest.raises(ValidationError):
        WarehouseLayout.load_json(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("{not json", encoding="utf-8")
    with pytest.raises(ValidationError):
        WarehouseLayout.load_json(bad)
