"""Shared fixtures for warehouse-logistics-sim tests."""

import pytest

from warehouse_logistics_sim.inventory import SKU
from warehouse_logistics_sim.layout import WarehouseLayout


@pytest.fixture()
def one_aisle_layout() -> WarehouseLayout:
    """1 aisle, L=20 m, 4 slots -> slot y = 2.5, 7.5, 12.5, 17.5."""
    return WarehouseLayout(
        name="one-aisle", num_aisles=1, aisle_length=20.0,
        aisle_spacing=3.0, slots_per_aisle=4, depot_x=0.0,
    )


@pytest.fixture()
def two_aisle_layout() -> WarehouseLayout:
    """2 aisles, spacing 5 m, L=20 m, 4 slots."""
    return WarehouseLayout(
        name="two-aisle", num_aisles=2, aisle_length=20.0,
        aisle_spacing=5.0, slots_per_aisle=4, depot_x=0.0,
    )


@pytest.fixture()
def small_layout() -> WarehouseLayout:
    """4 aisles, L=12 m, 6 slots -> slot y = 1, 3, 5, 7, 9, 11."""
    return WarehouseLayout(
        name="small", num_aisles=4, aisle_length=12.0,
        aisle_spacing=3.0, slots_per_aisle=6, depot_x=0.0,
    )


def make_sku(
    sku_id: str,
    annual_demand: float = 1000.0,
    unit_cost: float = 10.0,
    demand_std_daily: float = 0.0,
    lead_time_days: float = 5.0,
    lead_time_std_days: float = 0.0,
    order_cost: float = 50.0,
    holding_cost_per_unit_year: float | None = 2.0,
    on_hand: int = 500,
    length_m: float = 0.3,
    width_m: float = 0.2,
    height_m: float = 0.1,
) -> SKU:
    return SKU(
        sku_id=sku_id,
        name=f"Item {sku_id}",
        length_m=length_m,
        width_m=width_m,
        height_m=height_m,
        weight_kg=1.0,
        unit_cost=unit_cost,
        annual_demand=annual_demand,
        demand_std_daily=demand_std_daily,
        lead_time_days=lead_time_days,
        lead_time_std_days=lead_time_std_days,
        order_cost=order_cost,
        holding_cost_per_unit_year=holding_cost_per_unit_year,
        on_hand=on_hand,
    )
