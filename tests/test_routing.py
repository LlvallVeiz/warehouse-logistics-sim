"""Tests for routing heuristics with hand-computed distances.

Geometry used (1 aisle, L=20 m, slots at y = 2.5, 7.5, 12.5, 17.5):
picks at y=2.5 and y=17.5, depot at (0, 0):
* S-shape:  2.5 (depot->2.5) + 15 (2.5->17.5) + 17.5 (17.5->depot) = 35.0
* Return:    same 35.0 (enter front, farthest pick, back to front).
* Largest gap: in a multi-aisle case the internal gap is skipped (see
  test_largest_gap_two_aisles); a single-aisle warehouse has only a "last"
  aisle, which is traversed entirely, so it equals S-shape (35.0).
* Nearest neighbour: 35.0.

Two-aisle case (spacing 5 m), picks (0, 2.5) and (5, 17.5):
* S-shape: 2.5 + 25 + 22.5 = 50.0.
"""

import pytest

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.layout import Point
from warehouse_logistics_sim.routing import (
    STRATEGIES,
    route_largest_gap,
    route_nearest_neighbor,
    route_picks,
    route_return,
    route_s_shape,
    route_two_opt,
)

PICKS_1AISLE = [Point(0.0, 2.5, 0), Point(0.0, 17.5, 0)]
PICKS_2AISLE = [Point(0.0, 2.5, 0), Point(5.0, 17.5, 1)]


def test_s_shape_one_aisle(one_aisle_layout):
    route = route_s_shape(one_aisle_layout, PICKS_1AISLE, num_lines=2)
    assert route.distance_m == pytest.approx(35.0)
    assert route.travel_time_s == pytest.approx(35.0)  # 1 m/s
    assert route.total_time_s == pytest.approx(35.0 + 2 * 8.0 + 60.0)


def test_return_one_aisle(one_aisle_layout):
    route = route_return(one_aisle_layout, PICKS_1AISLE, num_lines=2)
    assert route.distance_m == pytest.approx(35.0)


def test_largest_gap_one_aisle(one_aisle_layout):
    # A single-aisle warehouse has only a "last" aisle, which largest gap
    # traverses entirely, so it equals S-shape here.
    route = route_largest_gap(one_aisle_layout, PICKS_1AISLE, num_lines=2)
    assert route.distance_m == pytest.approx(35.0)


def test_largest_gap_two_aisles(two_aisle_layout):
    # Aisle 0: picks at 2.5 and 17.5, gaps 2.5/15/2.5 -> skip the internal gap:
    #   2.5 + 17.5 (to back end) + 2.5 (back end to 17.5) = 22.5 within aisle 0.
    # Aisle 1 (last): single pick at 7.5, entered from the back (prev y 17.5):
    #   (0,17.5)->(5,7.5) via back = 2.5+12.5+5 = 20; (5,7.5)->depot = 12.5.
    # Total: 2.5 + 17.5 + 2.5 + 20 + 12.5 = 55.0.
    picks = [Point(0.0, 2.5, 0), Point(0.0, 17.5, 0), Point(5.0, 7.5, 1)]
    route = route_largest_gap(two_aisle_layout, picks, num_lines=3)
    assert route.distance_m == pytest.approx(55.0)
    # S-shape on the same picks is shorter here (50.0): largest gap is not
    # always best when picks cluster at both ends of an aisle.
    assert route_s_shape(two_aisle_layout, picks, num_lines=3).distance_m == pytest.approx(50.0)


def test_nearest_neighbor_one_aisle(one_aisle_layout):
    route = route_nearest_neighbor(one_aisle_layout, PICKS_1AISLE, num_lines=2)
    assert route.distance_m == pytest.approx(35.0)


def test_s_shape_two_aisles(two_aisle_layout):
    route = route_s_shape(two_aisle_layout, PICKS_2AISLE, num_lines=2)
    assert route.distance_m == pytest.approx(50.0)


def test_two_opt_never_worse_than_nn(two_aisle_layout):
    import random

    rng = random.Random(1)
    picks = [
        Point(float(a * 5), rng.choice([2.5, 7.5, 12.5, 17.5]), a)
        for a in rng.choices([0, 1], k=8)
    ]
    nn = route_nearest_neighbor(two_aisle_layout, picks, num_lines=8)
    opt = route_two_opt(two_aisle_layout, picks, num_lines=8)
    assert opt.distance_m <= nn.distance_m + 1e-9
    assert sorted((p.x, p.y) for p in opt.waypoints) == sorted((p.x, p.y) for p in picks)


def test_all_strategies_visit_every_pick(two_aisle_layout):
    for strategy in STRATEGIES:
        route = route_picks(two_aisle_layout, PICKS_2AISLE, strategy, num_lines=2)
        assert route.num_picks == 2
        assert route.distance_m > 0
        # Every pick appears exactly once as a waypoint (largest gap may
        # add cross-aisle end waypoints, so compare the pick subset).
        pick_set = {(p.x, p.y) for p in PICKS_2AISLE}
        assert pick_set <= {(p.x, p.y) for p in route.waypoints}


def test_routing_validation(one_aisle_layout):
    with pytest.raises(ValidationError):
        route_picks(one_aisle_layout, [], "s_shape", num_lines=0)
    with pytest.raises(ValidationError):
        route_picks(one_aisle_layout, PICKS_1AISLE, "teleport", num_lines=2)
    with pytest.raises(ValidationError):
        route_picks(one_aisle_layout, [Point(0.0, 2.5, None)], "s_shape", num_lines=1)


def test_route_time_scales_with_speed(one_aisle_layout):
    slow = route_s_shape(one_aisle_layout, PICKS_1AISLE, num_lines=2, speed_m_per_s=0.5)
    fast = route_s_shape(one_aisle_layout, PICKS_1AISLE, num_lines=2, speed_m_per_s=2.0)
    assert slow.travel_time_s == pytest.approx(4 * fast.travel_time_s)  # 0.5 vs 2.0 m/s
