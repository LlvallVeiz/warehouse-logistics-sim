"""Tests for batching, zone picking and strategy comparison."""

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.layout import Point
from warehouse_logistics_sim.orders import Order, OrderLine
from warehouse_logistics_sim.picking import (
    batch_orders,
    compare_strategies,
    pick_batch,
    zone_of_bin,
    zone_split,
)
from warehouse_logistics_sim.scenarios import build_scenario, small_layout


def _order(order_id, *sku_ids):
    return Order(
        order_id=order_id,
        arrival_minute=0.0,
        lines=[OrderLine(sku_id=s, quantity=1) for s in sku_ids],
    )


def test_batch_orders_caps():
    orders = [_order(f"O{i}", "A", "B") for i in range(10)]  # 2 lines each
    batches = batch_orders(orders, max_orders_per_batch=4, max_lines_per_batch=6)
    # Line cap binds first: 3 orders (6 lines) per batch.
    assert [len(b) for b in batches] == [3, 3, 3, 1]
    batches = batch_orders(orders, max_orders_per_batch=4, max_lines_per_batch=20)
    assert [len(b) for b in batches] == [4, 4, 2]


def test_batch_orders_validation():
    with pytest.raises(ValidationError):
        batch_orders([], max_orders_per_batch=0)


def test_zone_of_bin():
    assert zone_of_bin(Point(0.0, 1.0, 0), 2, 4) == 0
    assert zone_of_bin(Point(3.0, 1.0, 1), 2, 4) == 0
    assert zone_of_bin(Point(6.0, 1.0, 2), 2, 4) == 1
    assert zone_of_bin(Point(9.0, 1.0, 3), 2, 4) == 1
    with pytest.raises(ValidationError):
        zone_of_bin(Point(0.0, 1.0, None), 2, 4)


def test_zone_split():
    bin_by_sku = {
        "A": Point(0.0, 1.0, 0),
        "B": Point(9.0, 1.0, 3),
    }
    zones = zone_split(_order("O1", "A", "B"), bin_by_sku, num_zones=2, num_aisles=4)
    assert set(zones) == {0, 1}
    assert zones[0] == [Point(0.0, 1.0, 0)]
    assert zones[1] == [Point(9.0, 1.0, 3)]


def test_pick_batch_dedupes_bins():
    scenario = build_scenario(layout=small_layout(), n_orders=0, seed=1)
    sku_a, sku_b = scenario.skus[0].sku_id, scenario.skus[1].sku_id
    batch = [_order("O1", sku_a, sku_b), _order("O2", sku_a)]
    result = pick_batch(scenario.layout, batch, scenario.bin_by_sku, "s_shape")
    assert result.route.num_picks == 2  # shared bin counted once
    assert result.order_ids == ["O1", "O2"]


def test_compare_strategies_all_present():
    scenario = build_scenario(layout=small_layout(), n_orders=20, seed=5)
    rows = compare_strategies(scenario.layout, scenario.orders, scenario.bin_by_sku)
    assert {r.strategy for r in rows} == {
        "s_shape", "largest_gap", "return", "nearest_neighbor", "two_opt",
    }
    for row in rows:
        assert row.total_distance_m > 0
        assert row.total_lines == sum(o.num_lines for o in scenario.orders)
    by_strategy = {r.strategy: r for r in rows}
    assert by_strategy["two_opt"].total_distance_m <= by_strategy["nearest_neighbor"].total_distance_m + 1e-9


def test_compare_strategies_validation():
    scenario = build_scenario(layout=small_layout(), n_orders=5, seed=5)
    with pytest.raises(ValidationError):
        compare_strategies(scenario.layout, [], scenario.bin_by_sku)
    with pytest.raises(ValidationError):
        compare_strategies(scenario.layout, scenario.orders, scenario.bin_by_sku,
                           strategies=["teleport"])
