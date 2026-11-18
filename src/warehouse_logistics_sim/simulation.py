"""Shift simulation: parallel pickers, order queue, stock, replenishment, KPIs.

Model: a discrete-event simulation of one picking shift.

* Orders arrive over the shift (arrival minutes from the order generator).
* ``num_pickers`` identical pickers work in parallel. When a picker is
  free and orders are waiting, they take the next batch (FIFO, up to the
  batch caps) and work it as one tour with the chosen routing strategy.
* Stock is decremented as lines are picked; a line whose SKU is out of
  stock (or short) counts as unfilled and contributes to the fill rate.
* Optional replenishment: at the start of a batch, any SKU at or below its
  reorder point (and without an inbound order) triggers an inbound of EOQ
  units arriving after its lead time.
* KPIs: pick rate (lines per picker-hour), total distance, mean order cycle
  time, fill rate, picker utilisation, backlog at shift end.
"""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import SKU, eoq, reorder_point
from warehouse_logistics_sim.layout import Point, WarehouseLayout
from warehouse_logistics_sim.orders import Order
from warehouse_logistics_sim.picking import batch_orders, pick_batch


@dataclass
class SimConfig:
    shift_minutes: float = 480.0  # 8-hour shift
    num_pickers: int = 4
    batch_max_orders: int = 4
    batch_max_lines: int = 20
    strategy: str = "s_shape"
    speed_m_per_s: float = 1.0
    pick_time_per_line_s: float = 8.0
    setup_time_s: float = 60.0
    service_level: float = 0.95
    replenish: bool = True

    def __post_init__(self) -> None:
        if self.shift_minutes <= 0:
            raise ValidationError("shift_minutes must be > 0")
        if self.num_pickers < 1:
            raise ValidationError("num_pickers must be >= 1")
        if self.batch_max_orders < 1 or self.batch_max_lines < 1:
            raise ValidationError("batch caps must be >= 1")
        if self.speed_m_per_s <= 0 or self.pick_time_per_line_s < 0 or self.setup_time_s < 0:
            raise ValidationError("speed/pick/setup parameters must be valid")
        if not 0.0 < self.service_level < 1.0:
            raise ValidationError("service_level must be in (0, 1)")


@dataclass
class OrderResult:
    order_id: str
    arrival_minute: float
    start_minute: float | None
    finish_minute: float | None
    lines_requested: int
    lines_filled: int
    distance_m: float
    units_picked: int

    @property
    def cycle_time_min(self) -> float | None:
        if self.finish_minute is None:
            return None
        return self.finish_minute - self.arrival_minute

    @property
    def completed(self) -> bool:
        return self.finish_minute is not None


@dataclass
class SimResult:
    config: SimConfig
    strategy: str
    order_results: list[OrderResult] = field(default_factory=list)
    total_distance_m: float = 0.0
    total_lines_requested: int = 0
    total_lines_filled: int = 0
    total_units_picked: int = 0
    total_picker_busy_min: float = 0.0
    stockouts: dict[str, int] = field(default_factory=dict)
    final_stock: dict[str, int] = field(default_factory=dict)

    @property
    def orders_completed(self) -> int:
        return sum(1 for r in self.order_results if r.completed)

    @property
    def orders_backlogged(self) -> int:
        return sum(1 for r in self.order_results if not r.completed)

    @property
    def fill_rate(self) -> float:
        if self.total_lines_requested == 0:
            return 1.0
        return self.total_lines_filled / self.total_lines_requested

    @property
    def pick_rate_lines_per_picker_hour(self) -> float:
        hours = self.total_picker_busy_min / 60.0
        if hours <= 0:
            return 0.0
        return self.total_lines_filled / hours

    @property
    def picker_utilisation(self) -> float:
        capacity = self.config.num_pickers * self.config.shift_minutes
        return self.total_picker_busy_min / capacity if capacity > 0 else 0.0

    @property
    def mean_cycle_time_min(self) -> float | None:
        cycles = [r.cycle_time_min for r in self.order_results if r.cycle_time_min is not None]
        return sum(cycles) / len(cycles) if cycles else None

    def kpi_table(self) -> dict[str, float | int | None]:
        return {
            "orders_arrived": len(self.order_results),
            "orders_completed": self.orders_completed,
            "orders_backlogged": self.orders_backlogged,
            "lines_requested": self.total_lines_requested,
            "lines_filled": self.total_lines_filled,
            "fill_rate": self.fill_rate,
            "pick_rate_lines_per_picker_hour": self.pick_rate_lines_per_picker_hour,
            "total_distance_m": self.total_distance_m,
            "mean_cycle_time_min": self.mean_cycle_time_min,
            "picker_utilisation": self.picker_utilisation,
            "total_units_picked": self.total_units_picked,
        }


def run_simulation(
    layout: WarehouseLayout,
    skus: list[SKU],
    bin_by_sku: dict[str, Point],
    orders: list[Order],
    config: SimConfig | None = None,
) -> SimResult:
    """Run one shift. Deterministic given the same orders and config."""
    config = config or SimConfig()
    if not skus:
        raise ValidationError("run_simulation needs at least one SKU")
    stock = {s.sku_id: s.on_hand for s in skus}
    rop = {s.sku_id: reorder_point(s, config.service_level) for s in skus}
    eoq_qty = {s.sku_id: max(1, round(eoq(s))) for s in skus}
    lead_min = {s.sku_id: s.lead_time_days * 24 * 60 for s in skus}

    # Inbound replenishments: heap of (arrival_minute, sku_id, qty).
    inbound: list[tuple[float, str, int]] = []
    inbound_pending: set[str] = set()

    def apply_inbound(now: float) -> None:
        while inbound and inbound[0][0] <= now:
            _, sku_id, qty = heapq.heappop(inbound)
            stock[sku_id] += qty
            inbound_pending.discard(sku_id)

    def maybe_reorder(now: float) -> None:
        if not config.replenish:
            return
        for sku_id, qty in stock.items():
            if qty <= rop[sku_id] and sku_id not in inbound_pending:
                heapq.heappush(inbound, (now + lead_min[sku_id], sku_id, eoq_qty[sku_id]))
                inbound_pending.add(sku_id)

    result = SimResult(config=config, strategy=config.strategy)
    for order in orders:
        result.order_results.append(
            OrderResult(
                order_id=order.order_id,
                arrival_minute=order.arrival_minute,
                start_minute=None,
                finish_minute=None,
                lines_requested=order.num_lines,
                lines_filled=0,
                distance_m=0.0,
                units_picked=0,
            )
        )
    result_by_id = {r.order_id: r for r in result.order_results}

    # Picker availability (minutes); event-driven over batches.
    picker_free = [0.0] * config.num_pickers
    waiting = sorted(orders, key=lambda o: o.arrival_minute)
    batches = batch_orders(waiting, config.batch_max_orders, config.batch_max_lines)

    for batch in batches:
        earliest_arrival = max(o.arrival_minute for o in batch)
        picker_idx = min(range(config.num_pickers), key=lambda i: picker_free[i])
        start = max(earliest_arrival, picker_free[picker_idx])
        if start >= config.shift_minutes:
            break  # shift over: remaining batches are backlog
        apply_inbound(start)
        maybe_reorder(start)
        batch_result = pick_batch(
            layout, batch, bin_by_sku, config.strategy,
            config.speed_m_per_s, config.pick_time_per_line_s, config.setup_time_s,
        )
        duration_min = batch_result.route.total_time_s / 60.0
        finish = start + duration_min
        # Stock check per line at pick time (one clean pass).
        batch_lines_filled = 0
        batch_units_picked = 0
        for order in batch:
            order_result = result_by_id[order.order_id]
            order_result.start_minute = start
            order_result.finish_minute = finish
            order_result.distance_m = batch_result.route.distance_m / len(batch)
            filled = 0
            units = 0
            for line in order.lines:
                if stock.get(line.sku_id, 0) >= line.quantity:
                    stock[line.sku_id] -= line.quantity
                    filled += 1
                    units += line.quantity
                else:
                    result.stockouts[line.sku_id] = result.stockouts.get(line.sku_id, 0) + 1
            order_result.lines_filled = filled
            order_result.units_picked = units
            batch_lines_filled += filled
            batch_units_picked += units
        result.total_lines_requested += sum(o.num_lines for o in batch)
        result.total_lines_filled += batch_lines_filled
        result.total_units_picked += batch_units_picked
        result.total_distance_m += batch_result.route.distance_m
        result.total_picker_busy_min += duration_min
        picker_free[picker_idx] = finish

    result.final_stock = dict(stock)
    return result
