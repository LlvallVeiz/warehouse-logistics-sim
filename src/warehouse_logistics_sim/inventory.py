"""Inventory model: SKUs, ABC (Pareto) analysis, EOQ, reorder point,
safety stock.

Formulas (standard textbook forms, see docs/RESEARCH.md):

* Annual usage value = annual demand x unit cost.
* ABC: SKUs sorted by usage value descending; class A = first 80% of
  cumulative value, B = next 15% (up to 95%), C = the rest (Pareto rule).
* EOQ (Harris 1913 / Wilson): Q* = sqrt(2 * D * S / H), D = annual demand,
  S = ordering cost per order, H = holding cost per unit per year.
* Safety stock: SS = z * sqrt(L * sigma_d^2 + d^2 * sigma_L^2), with
  d = mean daily demand, sigma_d = daily demand std, L = mean lead time
  (days), sigma_L = lead-time std, z = NormalDist inv_cdf(service level).
* Reorder point: ROP = d * L + SS.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from statistics import NormalDist

from warehouse_logistics_sim.errors import ValidationError

_NORMAL = NormalDist()

A_CUT = 0.80
B_CUT = 0.95


def z_score(service_level: float) -> float:
    """z for a cycle service level in (0, 1); e.g. 0.95 -> 1.6449."""
    if not 0.0 < service_level < 1.0:
        raise ValidationError(f"service_level must be in (0, 1), got {service_level}")
    return _NORMAL.inv_cdf(service_level)


@dataclass
class SKU:
    """One stock-keeping unit with demand, cost and replenishment data."""

    sku_id: str
    name: str
    length_m: float
    width_m: float
    height_m: float
    weight_kg: float
    unit_cost: float  # currency per unit
    annual_demand: float  # units per year
    demand_std_daily: float = 0.0  # std of daily demand (units/day)
    lead_time_days: float = 7.0
    lead_time_std_days: float = 0.0
    order_cost: float = 50.0  # currency per replenishment order
    holding_cost_per_unit_year: float | None = None  # if None: 25% of unit cost
    on_hand: int = 0
    category: str = "general"

    def __post_init__(self) -> None:
        if not self.sku_id:
            raise ValidationError("sku_id must not be empty")
        for attr in ("length_m", "width_m", "height_m"):
            if getattr(self, attr) <= 0:
                raise ValidationError(f"{attr} must be > 0 for SKU {self.sku_id}")
        if self.weight_kg < 0:
            raise ValidationError(f"weight_kg must be >= 0 for SKU {self.sku_id}")
        if self.unit_cost < 0 or self.annual_demand < 0:
            raise ValidationError(f"unit_cost and annual_demand must be >= 0 for SKU {self.sku_id}")
        if self.demand_std_daily < 0 or self.lead_time_days <= 0 or self.lead_time_std_days < 0:
            raise ValidationError(f"demand/lead-time parameters invalid for SKU {self.sku_id}")
        if self.order_cost < 0:
            raise ValidationError(f"order_cost must be >= 0 for SKU {self.sku_id}")
        if self.holding_cost_per_unit_year is not None and self.holding_cost_per_unit_year < 0:
            raise ValidationError(f"holding cost must be >= 0 for SKU {self.sku_id}")
        if self.on_hand < 0:
            raise ValidationError(f"on_hand must be >= 0 for SKU {self.sku_id}")

    @property
    def volume_m3(self) -> float:
        return self.length_m * self.width_m * self.height_m

    @property
    def holding_cost(self) -> float:
        """Holding cost per unit per year (25% of unit cost by default)."""
        if self.holding_cost_per_unit_year is not None:
            return self.holding_cost_per_unit_year
        return 0.25 * self.unit_cost

    @property
    def annual_usage_value(self) -> float:
        return self.annual_demand * self.unit_cost

    @property
    def daily_demand(self) -> float:
        return self.annual_demand / 365.0

    def to_dict(self) -> dict:
        return {
            "sku_id": self.sku_id,
            "name": self.name,
            "length_m": self.length_m,
            "width_m": self.width_m,
            "height_m": self.height_m,
            "weight_kg": self.weight_kg,
            "unit_cost": self.unit_cost,
            "annual_demand": self.annual_demand,
            "demand_std_daily": self.demand_std_daily,
            "lead_time_days": self.lead_time_days,
            "lead_time_std_days": self.lead_time_std_days,
            "order_cost": self.order_cost,
            "holding_cost_per_unit_year": self.holding_cost_per_unit_year,
            "on_hand": self.on_hand,
            "category": self.category,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "SKU":
        try:
            return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})
        except TypeError as exc:
            raise ValidationError(f"invalid SKU record {data.get('sku_id')}: {exc}") from exc


def eoq(sku: SKU) -> float:
    """Economic order quantity Q* = sqrt(2*D*S/H)."""
    if sku.annual_demand <= 0 or sku.holding_cost <= 0:
        return 0.0
    return math.sqrt(2.0 * sku.annual_demand * sku.order_cost / sku.holding_cost)


def safety_stock(sku: SKU, service_level: float = 0.95) -> float:
    """SS = z * sqrt(L*sigma_d^2 + d^2*sigma_L^2)."""
    z = z_score(service_level)
    variance = (
        sku.lead_time_days * sku.demand_std_daily**2
        + sku.daily_demand**2 * sku.lead_time_std_days**2
    )
    return z * math.sqrt(variance)


def reorder_point(sku: SKU, service_level: float = 0.95) -> float:
    """ROP = d * L + SS."""
    return sku.daily_demand * sku.lead_time_days + safety_stock(sku, service_level)


def total_annual_cost(sku: SKU, quantity: float) -> float:
    """Annual variable cost at lot size Q: (D/Q)*S + (Q/2)*H."""
    if quantity <= 0:
        raise ValidationError("lot size must be > 0")
    if sku.annual_demand <= 0:
        return 0.0
    return (sku.annual_demand / quantity) * sku.order_cost + (quantity / 2.0) * sku.holding_cost


@dataclass
class ABCResult:
    sku_id: str
    annual_usage_value: float
    share: float  # share of total usage value
    cumulative_share: float
    abc_class: str  # "A", "B" or "C"


def abc_analysis(
    skus: list[SKU], a_cut: float = A_CUT, b_cut: float = B_CUT
) -> list[ABCResult]:
    """Classify SKUs by annual usage value (Pareto 80/95 cut-offs)."""
    if not skus:
        raise ValidationError("abc_analysis needs at least one SKU")
    if not 0.0 < a_cut < b_cut < 1.0:
        raise ValidationError("cut-offs must satisfy 0 < a_cut < b_cut < 1")
    total = sum(s.annual_usage_value for s in skus)
    if total <= 0:
        raise ValidationError("total annual usage value must be > 0")
    ordered = sorted(skus, key=lambda s: s.annual_usage_value, reverse=True)
    results: list[ABCResult] = []
    cumulative = 0.0
    for sku in ordered:
        share = sku.annual_usage_value / total
        cumulative += share
        results.append(
            ABCResult(
                sku_id=sku.sku_id,
                annual_usage_value=sku.annual_usage_value,
                share=share,
                cumulative_share=cumulative,
                abc_class="C",  # assigned below from the pre-add cumulative
            )
        )
    # Class is decided by the cumulative share *before* the SKU is added:
    # the SKU that first takes the cumulative past 80% still belongs to A,
    # the one that first takes it past 95% still belongs to B.
    cumulative = 0.0
    for result in results:
        if cumulative < a_cut:
            result.abc_class = "A"
        elif cumulative < b_cut:
            result.abc_class = "B"
        else:
            result.abc_class = "C"
        cumulative = result.cumulative_share
    return results


def abc_summary(results: list[ABCResult]) -> dict[str, dict]:
    """Per-class counts and value shares."""
    summary: dict[str, dict] = {}
    for cls in ("A", "B", "C"):
        members = [r for r in results if r.abc_class == cls]
        summary[cls] = {
            "count": len(members),
            "value_share": sum(r.share for r in members),
        }
    return summary


@dataclass
class ReplenishmentPlan:
    sku_id: str
    eoq: float
    safety_stock: float
    reorder_point: float
    annual_cost_at_eoq: float
    on_hand: int
    needs_reorder: bool


def replenishment_plan(skus: list[SKU], service_level: float = 0.95) -> list[ReplenishmentPlan]:
    """EOQ + safety stock + reorder point for every SKU."""
    plans = []
    for sku in skus:
        q = eoq(sku)
        ss = safety_stock(sku, service_level)
        rop = reorder_point(sku, service_level)
        plans.append(
            ReplenishmentPlan(
                sku_id=sku.sku_id,
                eoq=q,
                safety_stock=ss,
                reorder_point=rop,
                annual_cost_at_eoq=total_annual_cost(sku, q) if q > 0 else 0.0,
                on_hand=sku.on_hand,
                needs_reorder=sku.on_hand <= rop,
            )
        )
    return plans
