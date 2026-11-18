"""Order batching, zone picking, and strategy comparison.

* Batch picking groups several orders into one tour (up to a line or order
  cap), which amortises the depot travel over more lines.
* Zone picking splits an order's lines by aisle zone so each zone is picked
  independently (here evaluated as separate sub-routes).
* ``compare_strategies`` routes the same set of orders with every
  heuristic so the comparison is apples-to-apples.
"""

from __future__ import annotations

from dataclasses import dataclass

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.layout import Point, WarehouseLayout
from warehouse_logistics_sim.orders import Order
from warehouse_logistics_sim.routing import STRATEGIES, RouteResult, route_picks


def batch_orders(
    orders: list[Order],
    max_orders_per_batch: int = 4,
    max_lines_per_batch: int = 20,
) -> list[list[Order]]:
    """Greedy FIFO batching: fill each batch up to both caps."""
    if max_orders_per_batch < 1 or max_lines_per_batch < 1:
        raise ValidationError("batch caps must be >= 1")
    batches: list[list[Order]] = []
    current: list[Order] = []
    current_lines = 0
    for order in orders:
        if (
            current
            and (len(current) >= max_orders_per_batch or current_lines + order.num_lines > max_lines_per_batch)
        ):
            batches.append(current)
            current, current_lines = [], 0
        current.append(order)
        current_lines += order.num_lines
    if current:
        batches.append(current)
    return batches


def zone_of_bin(point: Point, num_zones: int, num_aisles: int) -> int:
    """Zone index for a bin point: aisles split evenly into ``num_zones`` zones."""
    if num_zones < 1:
        raise ValidationError("num_zones must be >= 1")
    if point.aisle is None:
        raise ValidationError("zone needs an aisle point")
    zone_size = max(1, -(-num_aisles // num_zones))  # ceil division
    return min(point.aisle // zone_size, num_zones - 1)


def zone_split(
    order: Order,
    bin_by_sku: dict[str, Point],
    num_zones: int,
    num_aisles: int,
) -> dict[int, list[Point]]:
    """Split an order's pick points by zone."""
    zones: dict[int, list[Point]] = {}
    for line in order.lines:
        point = bin_by_sku.get(line.sku_id)
        if point is None:
            raise ValidationError(f"SKU {line.sku_id} has no bin assigned")
        zones.setdefault(zone_of_bin(point, num_zones, num_aisles), []).append(point)
    return zones


@dataclass
class BatchResult:
    batch_id: str
    order_ids: list[str]
    route: RouteResult


def pick_batch(
    layout: WarehouseLayout,
    batch: list[Order],
    bin_by_sku: dict[str, Point],
    strategy: str,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> BatchResult:
    """Route one batch (union of its orders' pick points)."""
    if not batch:
        raise ValidationError("pick_batch needs a non-empty batch")
    picks: list[Point] = []
    seen: set[tuple[float, float]] = set()
    total_lines = 0
    for order in batch:
        total_lines += order.num_lines
        for line in order.lines:
            point = bin_by_sku.get(line.sku_id)
            if point is None:
                raise ValidationError(f"SKU {line.sku_id} has no bin assigned")
            key = (point.x, point.y)
            if key not in seen:
                seen.add(key)
                picks.append(point)
    route = route_picks(
        layout, picks, strategy, total_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s
    )
    return BatchResult(
        batch_id=batch[0].order_id + f"+{len(batch) - 1}" if len(batch) > 1 else batch[0].order_id,
        order_ids=[o.order_id for o in batch],
        route=route,
    )


@dataclass
class StrategyComparisonRow:
    strategy: str
    total_distance_m: float
    total_time_s: float
    avg_distance_per_order_m: float
    avg_time_per_order_s: float
    total_lines: int


def compare_strategies(
    layout: WarehouseLayout,
    orders: list[Order],
    bin_by_sku: dict[str, Point],
    strategies: list[str] | None = None,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> list[StrategyComparisonRow]:
    """Route the same orders with every strategy; return one row per strategy."""
    if not orders:
        raise ValidationError("compare_strategies needs at least one order")
    strategies = list(strategies or STRATEGIES)
    for strategy in strategies:
        if strategy not in STRATEGIES:
            raise ValidationError(f"unknown routing strategy {strategy!r}")
    rows: list[StrategyComparisonRow] = []
    for strategy in strategies:
        total_distance = 0.0
        total_time = 0.0
        total_lines = 0
        for order in orders:
            picks = [bin_by_sku[line.sku_id] for line in order.lines]
            route = route_picks(
                layout, picks, strategy, order.num_lines,
                speed_m_per_s, pick_time_per_line_s, setup_time_s,
            )
            total_distance += route.distance_m
            total_time += route.total_time_s
            total_lines += order.num_lines
        rows.append(
            StrategyComparisonRow(
                strategy=strategy,
                total_distance_m=total_distance,
                total_time_s=total_time,
                avg_distance_per_order_m=total_distance / len(orders),
                avg_time_per_order_s=total_time / len(orders),
                total_lines=total_lines,
            )
        )
    return rows
