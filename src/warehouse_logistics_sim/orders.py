"""Order generation: realistic orders with Zipf-distributed SKU popularity.

Empirical order profiles (see docs/RESEARCH.md): a small share of SKUs
appears in most order lines (Pareto/Zipf-like popularity), order sizes are
right-skewed (many small orders, few large ones), and quantities per line
are mostly 1. All randomness is seeded, so a scenario replays exactly.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import SKU

# Order-size distribution: (lines, weight). Right-skewed, mode at 2 lines.
LINE_COUNT_WEIGHTS: list[tuple[int, float]] = [
    (1, 0.18),
    (2, 0.26),
    (3, 0.20),
    (4, 0.14),
    (5, 0.09),
    (6, 0.06),
    (8, 0.04),
    (10, 0.02),
    (12, 0.01),
]

# Quantity per line: mostly 1, sometimes more.
QUANTITY_WEIGHTS: list[tuple[int, float]] = [(1, 0.62), (2, 0.22), (3, 0.10), (5, 0.06)]


def zipf_weights(n: int, exponent: float = 1.0) -> list[float]:
    """Zipf weights 1/rank**exponent, normalised to sum 1."""
    if n < 1:
        raise ValidationError("zipf_weights needs n >= 1")
    if exponent < 0:
        raise ValidationError("Zipf exponent must be >= 0")
    raw = [1.0 / (rank**exponent) for rank in range(1, n + 1)]
    total = sum(raw)
    return [w / total for w in raw]


@dataclass
class OrderLine:
    sku_id: str
    quantity: int

    def __post_init__(self) -> None:
        if self.quantity < 1:
            raise ValidationError("order line quantity must be >= 1")


@dataclass
class Order:
    order_id: str
    arrival_minute: float  # minutes after shift start
    lines: list[OrderLine] = field(default_factory=list)

    @property
    def total_units(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def num_lines(self) -> int:
        return len(self.lines)


def _weighted_choice(rng: random.Random, options: list[tuple[int, float]]) -> int:
    values, weights = zip(*options)
    return rng.choices(values, weights=weights, k=1)[0]


def generate_orders(
    skus: list[SKU],
    n_orders: int,
    seed: int = 42,
    zipf_exponent: float = 1.0,
    shift_minutes: float = 480.0,
    hourly_profile: list[float] | None = None,
) -> list[Order]:
    """Generate ``n_orders`` realistic orders.

    SKU popularity follows a Zipf distribution over SKUs ranked by annual
    demand (most popular first). Arrival minutes follow ``hourly_profile``
    (one weight per hour of the shift; uniform if None).
    """
    if not skus:
        raise ValidationError("generate_orders needs at least one SKU")
    if n_orders < 0:
        raise ValidationError("n_orders must be >= 0")
    if shift_minutes <= 0:
        raise ValidationError("shift_minutes must be > 0")
    rng = random.Random(seed)
    ranked = sorted(skus, key=lambda s: s.annual_demand, reverse=True)
    weights = zipf_weights(len(ranked), zipf_exponent)

    n_hours = max(1, int(shift_minutes // 60))
    if hourly_profile is None:
        hourly_profile = [1.0] * n_hours
    if len(hourly_profile) != n_hours:
        raise ValidationError(
            f"hourly_profile must have {n_hours} entries, got {len(hourly_profile)}"
        )
    if any(w < 0 for w in hourly_profile) or sum(hourly_profile) <= 0:
        raise ValidationError("hourly_profile weights must be non-negative with positive sum")

    orders: list[Order] = []
    for i in range(n_orders):
        hour = rng.choices(range(n_hours), weights=hourly_profile, k=1)[0]
        arrival = hour * 60.0 + rng.uniform(0.0, 60.0)
        arrival = min(arrival, shift_minutes - 0.01)
        n_lines = _weighted_choice(rng, LINE_COUNT_WEIGHTS)
        n_lines = min(n_lines, len(ranked))
        chosen = rng.choices(ranked, weights=weights, k=n_lines)
        # De-duplicate SKUs inside one order, keeping first occurrence.
        seen: dict[str, OrderLine] = {}
        for sku in chosen:
            if sku.sku_id not in seen:
                seen[sku.sku_id] = OrderLine(
                    sku_id=sku.sku_id,
                    quantity=_weighted_choice(rng, QUANTITY_WEIGHTS),
                )
        orders.append(
            Order(order_id=f"ORD-{i + 1:05d}", arrival_minute=arrival, lines=list(seen.values()))
        )
    orders.sort(key=lambda o: o.arrival_minute)
    return orders
