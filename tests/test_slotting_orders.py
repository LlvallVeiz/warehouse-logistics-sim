"""Tests for slotting (COI) and order generation."""

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.orders import generate_orders, zipf_weights
from warehouse_logistics_sim.slotting import (
    assign_slots,
    cube_per_order_index,
    evaluate_slotting,
    expected_travel_per_pick,
)
from tests.conftest import make_sku


def test_zipf_weights():
    weights = zipf_weights(4, 1.0)
    assert sum(weights) == pytest.approx(1.0)
    # 1, 1/2, 1/3, 1/4 normalised: first = 12/25 = 0.48.
    assert weights[0] == pytest.approx(12 / 25, rel=1e-9)
    assert weights == sorted(weights, reverse=True)
    with pytest.raises(ValidationError):
        zipf_weights(0)


def test_generate_orders_deterministic():
    skus = [make_sku(f"S{i}", annual_demand=10000.0 / i) for i in range(1, 11)]
    first = generate_orders(skus, 50, seed=7)
    second = generate_orders(skus, 50, seed=7)
    assert [(o.order_id, o.arrival_minute, [(l.sku_id, l.quantity) for l in o.lines])
            for o in first] == [
        (o.order_id, o.arrival_minute, [(l.sku_id, l.quantity) for l in o.lines])
        for o in second
    ]
    third = generate_orders(skus, 50, seed=8)
    assert first[0].lines != third[0].lines or first[0].arrival_minute != third[0].arrival_minute


def test_generate_orders_properties():
    skus = [make_sku(f"S{i}", annual_demand=10000.0 / i) for i in range(1, 11)]
    orders = generate_orders(skus, 100, seed=3, shift_minutes=480.0)
    assert len(orders) == 100
    arrivals = [o.arrival_minute for o in orders]
    assert arrivals == sorted(arrivals)
    assert all(0.0 <= a < 480.0 for a in arrivals)
    # No duplicate SKU inside one order.
    for order in orders:
        assert len({line.sku_id for line in order.lines}) == len(order.lines)
    # Popularity skew: the top SKU appears in more orders than the last one.
    counts = {s.sku_id: 0 for s in skus}
    for order in orders:
        for line in order.lines:
            counts[line.sku_id] += 1
    assert counts["S1"] > counts["S10"]


def test_generate_orders_validation():
    with pytest.raises(ValidationError):
        generate_orders([], 10)
    with pytest.raises(ValidationError):
        generate_orders([make_sku("S1")], -1)


def test_coi_ordering():
    small = make_sku("SMALL", length_m=0.1, width_m=0.1, height_m=0.1)  # 0.001 m3
    big = make_sku("BIG", length_m=1.0, width_m=1.0, height_m=1.0)      # 1 m3
    assert cube_per_order_index(small, 100.0) < cube_per_order_index(big, 100.0)
    assert cube_per_order_index(small, 100.0) == pytest.approx(0.001 / 100.0)
    with pytest.raises(ValidationError):
        cube_per_order_index(small, 0.0)


def test_assign_slots_nearest_first(small_layout):
    # Fast mover (many picks) + small cube -> nearest bin; slow bulky -> far.
    fast = make_sku("FAST", length_m=0.1, width_m=0.1, height_m=0.1)
    slow = make_sku("SLOW", length_m=1.0, width_m=1.0, height_m=1.0)
    picks = {"FAST": 1000.0, "SLOW": 10.0}
    assignments = assign_slots(small_layout, [fast, slow], picks)
    by_sku = {a.sku_id: a for a in assignments}
    assert by_sku["FAST"].bin_id == "A01-S01"  # nearest bin to depot
    assert by_sku["FAST"].distance_from_depot_m < by_sku["SLOW"].distance_from_depot_m


def test_assign_slots_too_many_skus(small_layout):
    skus = [make_sku(f"S{i}") for i in range(30)]
    picks = {s.sku_id: 10.0 for s in skus}
    with pytest.raises(ValidationError):
        assign_slots(small_layout, skus, picks)


def test_expected_travel_per_pick_hand_computed(small_layout):
    # Bin A01-S01 is 1 m from depot; A04-S06 is 20 m.
    assignment = {"A": "A01-S01", "B": "A04-S06"}
    picks = {"A": 90.0, "B": 10.0}
    assert expected_travel_per_pick(small_layout, assignment, picks) == pytest.approx(
        (90 * 1.0 + 10 * 20.0) / 100.0
    )


def test_slotting_evaluation_improves(small_layout):
    skus = [make_sku(f"S{i}", annual_demand=10000.0 / (i + 1)) for i in range(6)]
    picks = {s.sku_id: 1000.0 / (i + 1) for i, s in enumerate(skus)}
    # Deliberately bad current slotting: most-picked SKU in the farthest bin.
    far_bins = [b.bin_id for b in reversed(small_layout.bins_by_depot_distance())]
    current = {s.sku_id: far_bins[i] for i, s in enumerate(skus)}
    evaluation = evaluate_slotting(small_layout, skus, picks, current)
    assert evaluation.after_m_per_pick < evaluation.before_m_per_pick
    assert evaluation.improvement_pct > 0
    assert len(evaluation.assignments) == 6
