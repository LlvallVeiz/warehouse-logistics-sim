"""Built-in scenarios: a deterministic demo catalogue and JSON scenario files.

The default catalogue has 48 SKUs across 6 categories. Annual demand is
Zipf-like (a few fast movers, a long slow tail) so ABC analysis, slotting
and order generation all exercise realistic skew. Stock is set to roughly
two weeks of demand so a one-shift simulation fills nearly everything
while still exposing reorder needs.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass, field
from pathlib import Path

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import SKU
from warehouse_logistics_sim.layout import Point, WarehouseLayout
from warehouse_logistics_sim.orders import generate_orders
from warehouse_logistics_sim.simulation import SimConfig

_CATEGORIES = [
    ("ELEC", "electronics", 12),
    ("HOME", "home goods", 10),
    ("TOOL", "tools", 8),
    ("APPAREL", "apparel", 8),
    ("FOOD", "dry food", 6),
    ("SPORT", "sports", 4),
]


def default_skus() -> list[SKU]:
    """48 SKUs with Zipf-like demand, varied sizes, costs and lead times."""
    skus: list[SKU] = []
    rank = 0
    for prefix, category, count in _CATEGORIES:
        for i in range(1, count + 1):
            rank += 1
            demand = 12000.0 / rank  # Zipf s=1: rank 1 ~12000/yr, rank 48 ~250/yr
            unit_cost = round(4.0 + 96.0 * ((rank * 37) % 100) / 100.0, 2)
            length = round(0.15 + 0.35 * ((rank * 13) % 10) / 10.0, 2)
            width = round(0.12 + 0.28 * ((rank * 29) % 10) / 10.0, 2)
            height = round(0.08 + 0.30 * ((rank * 7) % 10) / 10.0, 2)
            skus.append(
                SKU(
                    sku_id=f"{prefix}-{i:03d}",
                    name=f"{category.title()} item {i}",
                    length_m=length,
                    width_m=width,
                    height_m=height,
                    weight_kg=round(0.2 + 4.8 * ((rank * 11) % 10) / 10.0, 2),
                    unit_cost=unit_cost,
                    annual_demand=round(demand, 1),
                    demand_std_daily=round(math.sqrt(demand / 365.0) * 1.5, 2),
                    lead_time_days=3.0 + (rank % 5),
                    lead_time_std_days=1.0,
                    order_cost=40.0 + (rank % 4) * 15.0,
                    holding_cost_per_unit_year=None,  # 25% of unit cost
                    on_hand=int(round(demand / 365.0 * 14)),  # ~2 weeks of stock
                    category=category,
                )
            )
    return skus


def default_layout() -> WarehouseLayout:
    """8 aisles x 20 m, 3 m spacing, 12 slots per aisle = 96 bins."""
    return WarehouseLayout(
        name="demo-warehouse",
        num_aisles=8,
        aisle_length=20.0,
        aisle_spacing=3.0,
        slots_per_aisle=12,
        depot_x=0.0,
        bin_capacity_units=200,
    )


def small_layout() -> WarehouseLayout:
    """4 aisles x 12 m, 3 m spacing, 6 slots per aisle = 24 bins."""
    return WarehouseLayout(
        name="small-warehouse",
        num_aisles=4,
        aisle_length=12.0,
        aisle_spacing=3.0,
        slots_per_aisle=6,
        depot_x=0.0,
        bin_capacity_units=200,
    )


@dataclass
class Scenario:
    """Everything one run needs: layout, SKUs, stock assignment, orders, config."""

    layout: WarehouseLayout
    skus: list[SKU]
    bin_by_sku: dict[str, Point]  # sku_id -> bin point
    orders: list = field(default_factory=list)
    config: SimConfig = field(default_factory=SimConfig)
    name: str = "scenario"

    @property
    def annual_picks(self) -> dict[str, float]:
        """Annual picks per SKU implied by the generated orders, scaled to a year."""
        counts: dict[str, float] = {s.sku_id: 0.0 for s in self.skus}
        for order in self.orders:
            for line in order.lines:
                counts[line.sku_id] = counts.get(line.sku_id, 0.0) + 1.0
        # Scale one shift's picks to a year (250 working days). SKUs with
        # no picks in this shift still get a floor of 1 pick/year so COI
        # slotting can rank them (they sort to the far bins, as intended).
        return {sku_id: max(count * 250.0, 1.0) for sku_id, count in counts.items()}


def build_scenario(
    layout: WarehouseLayout | None = None,
    skus: list[SKU] | None = None,
    n_orders: int = 120,
    seed: int = 42,
    config: SimConfig | None = None,
    name: str = "demo",
) -> Scenario:
    """Build a scenario: assign SKUs to bins (random initial slotting),
    then generate orders."""
    import random

    layout = layout or default_layout()
    skus = skus or default_skus()
    config = config or SimConfig()
    if len(skus) > layout.total_bins:
        # Small layouts cannot hold the full catalogue: keep the most
        # popular SKUs (the list is already demand-ranked) that fit.
        skus = skus[: layout.total_bins]
    rng = random.Random(seed)
    bins = list(layout.bins.values())
    rng.shuffle(bins)  # deliberately *unslotted* start: random placement
    bin_by_sku = {}
    for sku, bin_ in zip(skus, bins):
        bin_.sku_id = sku.sku_id
        bin_.quantity = sku.on_hand
        bin_by_sku[sku.sku_id] = bin_.point
    orders = generate_orders(
        skus, n_orders, seed=seed, shift_minutes=config.shift_minutes
    )
    return Scenario(
        layout=layout, skus=skus, bin_by_sku=bin_by_sku,
        orders=orders, config=config, name=name,
    )


def load_scenario(path: str | Path) -> Scenario:
    """Load a scenario JSON file (see examples/scenarios/)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"scenario file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"scenario file is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise ValidationError("scenario JSON must be an object")
    layout = WarehouseLayout.from_dict(data["layout"]) if "layout" in data else default_layout()
    skus = [SKU.from_dict(s) for s in data.get("skus", [])] or default_skus()
    if len(skus) > layout.total_bins:
        # A small layout cannot hold the full catalogue: keep the most
        # popular SKUs (the list is already demand-ranked) that fit.
        skus = skus[: layout.total_bins]
    sim = data.get("simulation", {})
    config = SimConfig(
        shift_minutes=float(sim.get("shift_minutes", 480.0)),
        num_pickers=int(sim.get("num_pickers", 4)),
        batch_max_orders=int(sim.get("batch_max_orders", 4)),
        batch_max_lines=int(sim.get("batch_max_lines", 20)),
        strategy=str(sim.get("strategy", "s_shape")),
        speed_m_per_s=float(sim.get("speed_m_per_s", 1.0)),
        pick_time_per_line_s=float(sim.get("pick_time_per_line_s", 8.0)),
        setup_time_s=float(sim.get("setup_time_s", 60.0)),
        service_level=float(sim.get("service_level", 0.95)),
        replenish=bool(sim.get("replenish", True)),
    )
    scenario = build_scenario(
        layout=layout,
        skus=skus,
        n_orders=int(data.get("n_orders", 120)),
        seed=int(data.get("seed", 42)),
        config=config,
        name=data.get("name", path.stem),
    )
    # Honour explicit bin assignments in the file, if any.
    for entry in data.get("bin_assignments", []):
        sku_id = entry["sku_id"]
        bin_ = layout.bins.get(entry["bin_id"])
        if bin_ is None:
            raise ValidationError(f"unknown bin {entry['bin_id']} in scenario")
        for old in layout.bins.values():
            if old.sku_id == sku_id:
                old.sku_id = None
                old.quantity = 0
        scenario.bin_by_sku[sku_id] = bin_.point
        bin_.sku_id = sku_id
    return scenario


def load_batch(path: str | Path) -> list[dict]:
    """Load a batch file: a JSON list of scenario objects (or paths)."""
    path = Path(path)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValidationError(f"batch file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValidationError(f"batch file is not valid JSON: {exc}") from exc
    if not isinstance(data, list):
        raise ValidationError("batch JSON must be a list of scenario objects")
    return data
