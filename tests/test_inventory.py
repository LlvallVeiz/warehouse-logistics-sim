"""Tests for inventory: EOQ, safety stock, reorder point, ABC.

Hand-computed references:
* EOQ: D=12000, S=50, H=2 -> sqrt(2*12000*50/2) = sqrt(600000) = 774.5967.
  Total annual cost at EOQ = (D/Q)*S + (Q/2)*H = 774.5967 + 774.5967 = 1549.1934.
* Safety stock: d=100/day, sigma_d=20, L=5 days, z(95%)=1.6448536269514722
  -> SS = 1.6448536269514722 * 20 * sqrt(5) = 73.5601.
  ROP = 100*5 + SS = 573.5601.
* ABC: values 800/150/40/10 (total 1000) -> A={800}, B={150}, C={40, 10}.
"""

import math

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import (
    abc_analysis,
    abc_summary,
    eoq,
    replenishment_plan,
    reorder_point,
    safety_stock,
    total_annual_cost,
    z_score,
)
from tests.conftest import make_sku

Z_95 = 1.6448536269514722


def test_z_score():
    assert z_score(0.95) == pytest.approx(Z_95, rel=1e-9)
    assert z_score(0.99) == pytest.approx(2.3263478740408408, rel=1e-9)
    with pytest.raises(ValidationError):
        z_score(1.0)
    with pytest.raises(ValidationError):
        z_score(0.0)


def test_eoq_hand_computed():
    sku = make_sku("A", annual_demand=12000.0, order_cost=50.0, holding_cost_per_unit_year=2.0)
    assert eoq(sku) == pytest.approx(math.sqrt(600000.0), rel=1e-9)
    assert eoq(sku) == pytest.approx(774.5966692, rel=1e-6)


def test_total_annual_cost_minimum_at_eoq():
    sku = make_sku("A", annual_demand=12000.0, order_cost=50.0, holding_cost_per_unit_year=2.0)
    q = eoq(sku)
    assert total_annual_cost(sku, q) == pytest.approx(1549.1934, rel=1e-4)
    # Any other lot size costs more.
    assert total_annual_cost(sku, q * 2) > total_annual_cost(sku, q)
    assert total_annual_cost(sku, q / 2) > total_annual_cost(sku, q)


def test_safety_stock_and_rop_hand_computed():
    sku = make_sku(
        "A", annual_demand=36500.0, demand_std_daily=20.0,
        lead_time_days=5.0, lead_time_std_days=0.0,
    )
    expected_ss = Z_95 * 20.0 * math.sqrt(5.0)
    assert safety_stock(sku, 0.95) == pytest.approx(expected_ss, rel=1e-9)
    assert safety_stock(sku, 0.95) == pytest.approx(73.5601, rel=1e-4)
    assert reorder_point(sku, 0.95) == pytest.approx(500.0 + expected_ss, rel=1e-9)


def test_safety_stock_with_lead_time_variability():
    # sigma_LTD = sqrt(L*sigma_d^2 + d^2*sigma_L^2)
    # d=10, sigma_d=2, L=4, sigma_L=1 -> sqrt(4*4 + 100*1) = sqrt(116).
    sku = make_sku(
        "A", annual_demand=3650.0, demand_std_daily=2.0,
        lead_time_days=4.0, lead_time_std_days=1.0,
    )
    expected = Z_95 * math.sqrt(116.0)
    assert safety_stock(sku, 0.95) == pytest.approx(expected, rel=1e-9)


def test_eoq_zero_demand():
    sku = make_sku("A", annual_demand=0.0)
    assert eoq(sku) == 0.0
    assert total_annual_cost(sku, 10.0) == 0.0


def test_abc_hand_computed():
    skus = [
        make_sku("S1", annual_demand=80.0, unit_cost=10.0),   # value 800
        make_sku("S2", annual_demand=15.0, unit_cost=10.0),   # value 150
        make_sku("S3", annual_demand=4.0, unit_cost=10.0),    # value 40
        make_sku("S4", annual_demand=1.0, unit_cost=10.0),    # value 10
    ]
    results = abc_analysis(skus)
    by_id = {r.sku_id: r for r in results}
    assert by_id["S1"].abc_class == "A"
    assert by_id["S1"].cumulative_share == pytest.approx(0.80)
    assert by_id["S2"].abc_class == "B"
    assert by_id["S2"].cumulative_share == pytest.approx(0.95)
    assert by_id["S3"].abc_class == "C"
    assert by_id["S4"].abc_class == "C"
    summary = abc_summary(results)
    assert summary["A"]["count"] == 1
    assert summary["A"]["value_share"] == pytest.approx(0.80)
    assert summary["B"]["count"] == 1
    assert summary["C"]["count"] == 2


def test_abc_validation():
    with pytest.raises(ValidationError):
        abc_analysis([])
    with pytest.raises(ValidationError):
        abc_analysis([make_sku("A", annual_demand=0.0)])


def test_replenishment_plan_flags_low_stock():
    low = make_sku("LOW", annual_demand=36500.0, demand_std_daily=20.0,
                   lead_time_days=5.0, on_hand=10)
    high = make_sku("HIGH", annual_demand=365.0, on_hand=10000)
    plans = {p.sku_id: p for p in replenishment_plan([low, high], 0.95)}
    assert plans["LOW"].needs_reorder is True
    assert plans["LOW"].reorder_point == pytest.approx(500.0 + Z_95 * 20 * math.sqrt(5), rel=1e-9)
    assert plans["HIGH"].needs_reorder is False
    assert plans["LOW"].eoq > 0


def test_sku_validation():
    with pytest.raises(ValidationError):
        make_sku("X", length_m=0.0)
    with pytest.raises(ValidationError):
        make_sku("X", annual_demand=-5.0)
    with pytest.raises(ValidationError):
        make_sku("X", on_hand=-1)
