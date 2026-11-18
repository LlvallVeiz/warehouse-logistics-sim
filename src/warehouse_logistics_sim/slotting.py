"""Slotting: assign SKUs to bins so fast movers sit near the depot.

The cube-per-order index (COI) ranks SKUs by ``volume / picks``: a SKU
that is picked often and is small belongs close to the depot. The classic
result (see docs/RESEARCH.md) is that slotting by pick frequency / COI
minimises expected travel distance per pick. This module assigns the
lowest-COI SKUs to the bins nearest the depot and measures the expected
travel per pick before and after the move, so the gain is quantified
instead of asserted.
"""

from __future__ import annotations

from dataclasses import dataclass

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import SKU
from warehouse_logistics_sim.layout import WarehouseLayout


def cube_per_order_index(sku: SKU, annual_picks: float) -> float:
    """COI = unit volume / annual picks (m^3 per pick). Lower is better."""
    if annual_picks <= 0:
        raise ValidationError(f"annual picks must be > 0 for SKU {sku.sku_id}")
    return sku.volume_m3 / annual_picks


@dataclass
class SlotAssignment:
    sku_id: str
    bin_id: str
    distance_from_depot_m: float
    coi: float


def assign_slots(
    layout: WarehouseLayout,
    skus: list[SKU],
    annual_picks: dict[str, float],
) -> list[SlotAssignment]:
    """Greedy COI slotting: lowest COI -> nearest bin.

    One SKU per bin; raises if there are more SKUs than bins.
    """
    if len(skus) > layout.total_bins:
        raise ValidationError(
            f"{len(skus)} SKUs do not fit in {layout.total_bins} bins"
        )
    for sku in skus:
        if sku.sku_id not in annual_picks:
            raise ValidationError(f"no annual-picks figure for SKU {sku.sku_id}")
    ranked = sorted(skus, key=lambda s: cube_per_order_index(s, annual_picks[s.sku_id]))
    nearest_bins = layout.bins_by_depot_distance()
    assignments = []
    for sku, bin_ in zip(ranked, nearest_bins):
        assignments.append(
            SlotAssignment(
                sku_id=sku.sku_id,
                bin_id=bin_.bin_id,
                distance_from_depot_m=layout.distance(layout.depot, bin_.point),
                coi=cube_per_order_index(sku, annual_picks[sku.sku_id]),
            )
        )
    return assignments


def expected_travel_per_pick(
    layout: WarehouseLayout,
    assignment: dict[str, str],
    annual_picks: dict[str, float],
) -> float:
    """Expected one-way depot-to-bin distance per pick, weighted by picks.

    ``assignment`` maps sku_id -> bin_id. Uses the aisle-aware distance
    from the depot to the bin (a round trip is twice this, so the ratio
    before/after is unaffected).
    """
    total_picks = sum(annual_picks.values())
    if total_picks <= 0:
        raise ValidationError("total annual picks must be > 0")
    weighted = 0.0
    for sku_id, bin_id in assignment.items():
        bin_ = layout.bins.get(bin_id)
        if bin_ is None:
            raise ValidationError(f"unknown bin {bin_id} in assignment")
        weighted += annual_picks.get(sku_id, 0.0) * layout.distance(layout.depot, bin_.point)
    return weighted / total_picks


@dataclass
class SlottingEvaluation:
    before_m_per_pick: float
    after_m_per_pick: float
    improvement_pct: float
    assignments: list[SlotAssignment]


def evaluate_slotting(
    layout: WarehouseLayout,
    skus: list[SKU],
    annual_picks: dict[str, float],
    current_assignment: dict[str, str],
) -> SlottingEvaluation:
    """Compare current slotting vs COI slotting on expected travel/pick."""
    before = expected_travel_per_pick(layout, current_assignment, annual_picks)
    assignments = assign_slots(layout, skus, annual_picks)
    after_map = {a.sku_id: a.bin_id for a in assignments}
    after = expected_travel_per_pick(layout, after_map, annual_picks)
    improvement = (before - after) / before * 100.0 if before > 0 else 0.0
    return SlottingEvaluation(
        before_m_per_pick=before,
        after_m_per_pick=after,
        improvement_pct=improvement,
        assignments=assignments,
    )
