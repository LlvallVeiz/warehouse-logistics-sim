"""Tests for the shift simulation: determinism, fill rate, backlog, stockouts."""

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.orders import Order, OrderLine
from warehouse_logistics_sim.scenarios import build_scenario, default_skus, small_layout
from warehouse_logistics_sim.simulation import SimConfig, run_simulation
from tests.conftest import make_sku


def _run(n_orders=60, **kwargs):
    scenario = build_scenario(layout=small_layout(), n_orders=n_orders, seed=11)
    config = SimConfig(**kwargs)
    return run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, config
    )


def test_simulation_deterministic():
    first = _run()
    second = _run()
    assert first.kpi_table() == second.kpi_table()
    assert [r.finish_minute for r in first.order_results] == [
        r.finish_minute for r in second.order_results
    ]


def test_simulation_kpis_sane():
    result = _run(num_pickers=4)
    kpi = result.kpi_table()
    assert kpi["orders_arrived"] == 60
    assert kpi["orders_completed"] + kpi["orders_backlogged"] == 60
    assert kpi["fill_rate"] == pytest.approx(1.0)
    assert 0.0 < kpi["picker_utilisation"] <= 1.0
    assert kpi["pick_rate_lines_per_picker_hour"] > 0
    assert kpi["total_distance_m"] > 0
    assert kpi["mean_cycle_time_min"] > 0
    # Per-order invariants.
    for r in result.order_results:
        if r.completed:
            assert r.finish_minute >= r.start_minute >= r.arrival_minute
            assert r.lines_filled == r.lines_requested


def test_simulation_backlog_when_overloaded():
    # One picker, 200 orders: the shift cannot clear them all.
    result = _run(200, num_pickers=1, batch_max_orders=1, batch_max_lines=4)
    assert result.orders_backlogged > 0
    assert result.orders_completed < 200


def test_simulation_stockout_when_no_stock():
    skus = default_skus()
    for sku in skus:
        sku.on_hand = 0
    scenario = build_scenario(layout=small_layout(), skus=skus, n_orders=20, seed=3)
    config = SimConfig(replenish=False)
    result = run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, config
    )
    assert result.fill_rate == pytest.approx(0.0)
    assert sum(result.stockouts.values()) > 0
    assert result.total_lines_filled == 0


def test_simulation_replenishment_arrives():
    # One SKU, tiny lead time (0.01 day ~ 14 min), stock for one line only.
    sku = make_sku("ONLY", annual_demand=3650.0, demand_std_daily=1.0,
                   lead_time_days=0.01, lead_time_std_days=0.0,
                   order_cost=10.0, holding_cost_per_unit_year=1.0, on_hand=1)
    layout = small_layout()
    bin_by_sku = {sku.sku_id: layout.bins["A01-S01"].point}
    orders = [
        Order(f"ORD-{i:05d}", arrival_minute=float(i * 60),
              lines=[OrderLine("ONLY", 1)])
        for i in range(6)
    ]
    config = SimConfig(num_pickers=1, batch_max_orders=1, batch_max_lines=1,
                       replenish=True, service_level=0.95)
    result = run_simulation(layout, [sku], bin_by_sku, orders, config)
    # Replenishment (EOQ ~ 270 units) lands after ~14 min, so later orders fill.
    assert result.total_lines_filled > 1
    config_no_repl = SimConfig(num_pickers=1, batch_max_orders=1, batch_max_lines=1,
                               replenish=False, service_level=0.95)
    result_no_repl = run_simulation(layout, [sku], bin_by_sku, orders, config_no_repl)
    assert result_no_repl.total_lines_filled == 1
    assert result.total_lines_filled > result_no_repl.total_lines_filled


def test_simulation_config_validation():
    with pytest.raises(ValidationError):
        SimConfig(num_pickers=0)
    with pytest.raises(ValidationError):
        SimConfig(shift_minutes=0)
    with pytest.raises(ValidationError):
        SimConfig(service_level=1.5)


def test_simulation_empty_skus():
    scenario = build_scenario(layout=small_layout(), n_orders=5, seed=1)
    with pytest.raises(ValidationError):
        run_simulation(scenario.layout, [], scenario.bin_by_sku, scenario.orders)
