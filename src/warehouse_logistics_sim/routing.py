"""Order-picking routing heuristics for a single-block warehouse.

Implemented heuristics (de Koster, Le-Duc & Roodbergen 2007; Roodbergen &
de Koster 1998; Ratliff & Rosenthal 1983 — see docs/RESEARCH.md):

* ``s_shape`` — traverse every aisle with picks entirely, alternating
  entry ends, so the route snakes through the warehouse.
* ``largest_gap`` — in each aisle, skip the largest gap between adjacent
  picks (or between a pick and a cross aisle); enter from one or both ends
  as the gap dictates. The last aisle is traversed entirely.
* ``return`` — enter every aisle from the front, walk to the farthest pick,
  return to the front.
* ``nearest_neighbor`` — greedy: always walk to the nearest unvisited pick.
* ``two_opt`` — nearest-neighbour tour improved by 2-opt edge swaps
  (Lin & Kernighan 1973 style local search on the aisle-aware metric).

Every heuristic returns an explicit waypoint list; the route distance is
always computed from that list with ``layout.path_distance``, so all
strategies are compared on exactly the same cost model.
"""

from __future__ import annotations

from dataclasses import dataclass

from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.layout import Point, WarehouseLayout
from warehouse_logistics_sim.orders import Order

STRATEGIES = ("s_shape", "largest_gap", "return", "nearest_neighbor", "two_opt")


@dataclass
class RouteResult:
    strategy: str
    waypoints: list[Point]
    distance_m: float
    travel_time_s: float
    pick_time_s: float
    setup_time_s: float
    num_lines: int
    num_picks: int  # distinct bins visited

    @property
    def total_time_s(self) -> float:
        return self.travel_time_s + self.pick_time_s + self.setup_time_s


def _group_by_aisle(picks: list[Point]) -> dict[int, list[Point]]:
    grouped: dict[int, list[Point]] = {}
    for point in picks:
        if point.aisle is None:
            raise ValidationError("pick points must belong to an aisle")
        grouped.setdefault(point.aisle, []).append(point)
    for aisle_points in grouped.values():
        aisle_points.sort(key=lambda p: p.y)
    return grouped


def _time_model(
    layout: WarehouseLayout,
    waypoints: list[Point],
    num_lines: int,
    speed_m_per_s: float,
    pick_time_per_line_s: float,
    setup_time_s: float,
) -> tuple[float, float]:
    distance = layout.path_distance(waypoints)
    return distance, distance / speed_m_per_s


def route_s_shape(
    layout: WarehouseLayout,
    picks: list[Point],
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """S-shape (traversal): fully traverse each aisle with picks, alternating ends."""
    if not picks:
        raise ValidationError("s_shape needs at least one pick")
    grouped = _group_by_aisle(picks)
    waypoints: list[Point] = []
    for k, aisle in enumerate(sorted(grouped)):
        aisle_points = grouped[aisle]
        waypoints.extend(aisle_points if k % 2 == 0 else list(reversed(aisle_points)))
    distance, travel = _time_model(layout, waypoints, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s)
    return RouteResult(
        strategy="s_shape",
        waypoints=waypoints,
        distance_m=distance,
        travel_time_s=travel,
        pick_time_s=num_lines * pick_time_per_line_s,
        setup_time_s=setup_time_s,
        num_lines=num_lines,
        num_picks=len(picks),
    )


def route_return(
    layout: WarehouseLayout,
    picks: list[Point],
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """Return: enter each aisle from the front, walk to the farthest pick, return."""
    if not picks:
        raise ValidationError("return needs at least one pick")
    grouped = _group_by_aisle(picks)
    waypoints: list[Point] = []
    for aisle in sorted(grouped):
        waypoints.extend(grouped[aisle])  # ascending y; return is implicit
    distance, travel = _time_model(layout, waypoints, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s)
    return RouteResult(
        strategy="return",
        waypoints=waypoints,
        distance_m=distance,
        travel_time_s=travel,
        pick_time_s=num_lines * pick_time_per_line_s,
        setup_time_s=setup_time_s,
        num_lines=num_lines,
        num_picks=len(picks),
    )


def route_largest_gap(
    layout: WarehouseLayout,
    picks: list[Point],
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """Largest gap: skip the largest unvisited stretch inside each aisle.

    For every aisle except the last visited one, the largest gap — between
    two adjacent picks, or between a pick and a cross aisle — is not
    traversed. If the gap touches an end, the aisle is entered from the
    other end only; if it is internal, the aisle is entered from both ends.
    The last aisle is traversed entirely, entered from the nearer end.
    """
    if not picks:
        raise ValidationError("largest_gap needs at least one pick")
    grouped = _group_by_aisle(picks)
    aisles = sorted(grouped)
    waypoints: list[Point] = []
    length = layout.aisle_length
    for idx, aisle in enumerate(aisles):
        points = grouped[aisle]
        is_last = idx == len(aisles) - 1
        if is_last:
            # Traverse fully; enter from the nearer end given where we are.
            prev_y = waypoints[-1].y if waypoints else 0.0
            if prev_y > length / 2:
                waypoints.extend(reversed(points))
            else:
                waypoints.extend(points)
            continue
        ys = [p.y for p in points]
        gaps = [(ys[0] - 0.0, "front")] + [
            (ys[i + 1] - ys[i], "internal", i) for i in range(len(ys) - 1)
        ] + [(length - ys[-1], "back")]
        largest = max(gaps, key=lambda g: g[0])
        if largest[1] == "front":
            # Biggest gap at the front: enter from the back only.
            waypoints.extend(reversed(points))
        elif largest[1] == "back":
            # Biggest gap at the back: enter from the front only.
            waypoints.extend(points)
        else:
            split = largest[2]
            front_part = points[: split + 1]
            back_part = points[split + 1 :]
            waypoints.extend(front_part)
            # Exit to the back cross aisle, then re-enter from the back.
            waypoints.append(Point(layout.aisle_x(aisle), length, aisle))
            waypoints.extend(reversed(back_part))
    distance, travel = _time_model(layout, waypoints, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s)
    return RouteResult(
        strategy="largest_gap",
        waypoints=waypoints,
        distance_m=distance,
        travel_time_s=travel,
        pick_time_s=num_lines * pick_time_per_line_s,
        setup_time_s=setup_time_s,
        num_lines=num_lines,
        num_picks=len(picks),
    )


def route_nearest_neighbor(
    layout: WarehouseLayout,
    picks: list[Point],
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """Greedy nearest neighbour starting at the depot."""
    if not picks:
        raise ValidationError("nearest_neighbor needs at least one pick")
    remaining = list(picks)
    waypoints: list[Point] = []
    current = layout.depot
    while remaining:
        nxt = min(remaining, key=lambda p: layout.distance(current, p))
        waypoints.append(nxt)
        remaining.remove(nxt)
        current = nxt
    distance, travel = _time_model(layout, waypoints, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s)
    return RouteResult(
        strategy="nearest_neighbor",
        waypoints=waypoints,
        distance_m=distance,
        travel_time_s=travel,
        pick_time_s=num_lines * pick_time_per_line_s,
        setup_time_s=setup_time_s,
        num_lines=num_lines,
        num_picks=len(picks),
    )


def _tour_distance(layout: WarehouseLayout, tour: list[Point]) -> float:
    return layout.path_distance(tour)


def route_two_opt(
    layout: WarehouseLayout,
    picks: list[Point],
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
    max_passes: int = 50,
) -> RouteResult:
    """2-opt improvement of the nearest-neighbour tour (depot fixed at both ends)."""
    if not picks:
        raise ValidationError("two_opt needs at least one pick")
    start = route_nearest_neighbor(
        layout, picks, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s
    )
    tour = list(start.waypoints)
    best = _tour_distance(layout, tour)
    improved = True
    passes = 0
    while improved and passes < max_passes:
        improved = False
        passes += 1
        for i in range(len(tour) - 1):
            for j in range(i + 1, len(tour)):
                candidate = tour[:i] + list(reversed(tour[i : j + 1])) + tour[j + 1 :]
                dist = _tour_distance(layout, candidate)
                if dist < best - 1e-9:
                    tour, best = candidate, dist
                    improved = True
    distance, travel = _time_model(layout, tour, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s)
    return RouteResult(
        strategy="two_opt",
        waypoints=tour,
        distance_m=distance,
        travel_time_s=travel,
        pick_time_s=num_lines * pick_time_per_line_s,
        setup_time_s=setup_time_s,
        num_lines=num_lines,
        num_picks=len(picks),
    )


_ROUTERS = {
    "s_shape": route_s_shape,
    "largest_gap": route_largest_gap,
    "return": route_return,
    "nearest_neighbor": route_nearest_neighbor,
    "two_opt": route_two_opt,
}


def route_picks(
    layout: WarehouseLayout,
    picks: list[Point],
    strategy: str,
    num_lines: int,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """Route a set of pick points with the named strategy."""
    if strategy not in _ROUTERS:
        raise ValidationError(f"unknown routing strategy {strategy!r}; choose from {sorted(_ROUTERS)}")
    return _ROUTERS[strategy](
        layout, picks, num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s
    )


def route_order(
    layout: WarehouseLayout,
    order: Order,
    bin_by_sku: dict[str, Point],
    strategy: str,
    speed_m_per_s: float = 1.0,
    pick_time_per_line_s: float = 8.0,
    setup_time_s: float = 60.0,
) -> RouteResult:
    """Route one order: its lines map to bin points via ``bin_by_sku``."""
    picks: list[Point] = []
    for line in order.lines:
        point = bin_by_sku.get(line.sku_id)
        if point is None:
            raise ValidationError(f"SKU {line.sku_id} has no bin assigned")
        picks.append(point)
    return route_picks(
        layout, picks, strategy, order.num_lines, speed_m_per_s, pick_time_per_line_s, setup_time_s
    )
