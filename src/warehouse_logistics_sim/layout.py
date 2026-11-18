"""Warehouse layout model: single-block picker-to-parts warehouse.

Geometry (after the standard model in de Koster, Le-Duc & Roodbergen 2007):
a rectangular block of parallel aisles, served by a front cross aisle
(y = 0) and a back cross aisle (y = aisle_length). The depot (packing /
shipping) sits on the front cross aisle. A picker walks along aisles and
cross aisles; the travel distance between two points is the shortest
aisle-aware path: either via the front cross aisle or via the back cross
aisle, or straight along the aisle when both points are in the same aisle.

Coordinates: aisle ``i`` sits at ``x = i * aisle_spacing``; slot ``j`` of an
aisle sits at ``y = (j + 0.5) * aisle_length / slots_per_aisle``.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from warehouse_logistics_sim.errors import ValidationError


@dataclass(frozen=True)
class Point:
    """A walkable point: ``x``/``y`` in metres, ``aisle`` index or None.

    The depot has ``aisle=None``; every bin has an aisle index.
    """

    x: float
    y: float
    aisle: int | None = None


@dataclass
class Bin:
    """One storage slot (bin) inside an aisle."""

    bin_id: str
    aisle: int
    slot: int
    x: float
    y: float
    capacity_units: int
    sku_id: str | None = None
    quantity: int = 0

    @property
    def point(self) -> Point:
        return Point(self.x, self.y, self.aisle)

    def to_dict(self) -> dict:
        return {
            "bin_id": self.bin_id,
            "aisle": self.aisle,
            "slot": self.slot,
            "x": self.x,
            "y": self.y,
            "capacity_units": self.capacity_units,
            "sku_id": self.sku_id,
            "quantity": self.quantity,
        }


@dataclass
class WarehouseLayout:
    """A single-block warehouse layout with bins, depot and distances."""

    name: str
    num_aisles: int
    aisle_length: float  # metres, front cross aisle (y=0) to back (y=L)
    aisle_spacing: float  # metres between adjacent aisle centrelines
    slots_per_aisle: int
    depot_x: float = 0.0
    bin_capacity_units: int = 100
    bins: dict[str, Bin] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("layout name must not be empty")
        if self.num_aisles < 1:
            raise ValidationError("num_aisles must be >= 1")
        if self.aisle_length <= 0:
            raise ValidationError("aisle_length must be > 0")
        if self.aisle_spacing <= 0:
            raise ValidationError("aisle_spacing must be > 0")
        if self.slots_per_aisle < 1:
            raise ValidationError("slots_per_aisle must be >= 1")
        if self.bin_capacity_units < 1:
            raise ValidationError("bin_capacity_units must be >= 1")
        if not (0.0 <= self.depot_x <= (self.num_aisles - 1) * self.aisle_spacing):
            raise ValidationError(
                f"depot_x {self.depot_x} must lie within the aisle span "
                f"[0, {(self.num_aisles - 1) * self.aisle_spacing}]"
            )
        if not self.bins:
            self.bins = self._build_bins()

    def _build_bins(self) -> dict[str, Bin]:
        bins: dict[str, Bin] = {}
        for aisle in range(self.num_aisles):
            x = aisle * self.aisle_spacing
            for slot in range(self.slots_per_aisle):
                y = (slot + 0.5) * self.aisle_length / self.slots_per_aisle
                bin_id = f"A{aisle + 1:02d}-S{slot + 1:02d}"
                bins[bin_id] = Bin(
                    bin_id=bin_id,
                    aisle=aisle,
                    slot=slot,
                    x=x,
                    y=y,
                    capacity_units=self.bin_capacity_units,
                )
        return bins

    # -- basic geometry ----------------------------------------------------
    @property
    def depot(self) -> Point:
        return Point(self.depot_x, 0.0, None)

    @property
    def width(self) -> float:
        return (self.num_aisles - 1) * self.aisle_spacing

    @property
    def total_bins(self) -> int:
        return len(self.bins)

    def aisle_x(self, aisle: int) -> float:
        if not 0 <= aisle < self.num_aisles:
            raise ValidationError(f"aisle {aisle} out of range 0..{self.num_aisles - 1}")
        return aisle * self.aisle_spacing

    def bin_position(self, aisle: int, slot: int) -> Point:
        if not 0 <= aisle < self.num_aisles:
            raise ValidationError(f"aisle {aisle} out of range 0..{self.num_aisles - 1}")
        if not 0 <= slot < self.slots_per_aisle:
            raise ValidationError(f"slot {slot} out of range 0..{self.slots_per_aisle - 1}")
        return Point(
            self.aisle_x(aisle),
            (slot + 0.5) * self.aisle_length / self.slots_per_aisle,
            aisle,
        )

    def distance(self, p1: Point, p2: Point) -> float:
        """Shortest aisle-aware walking distance (metres) between two points.

        Same aisle: straight along the aisle. Otherwise the shorter of the
        front-cross-aisle route and the back-cross-aisle route.
        """
        if p1.aisle is not None and p1.aisle == p2.aisle:
            return abs(p1.y - p2.y)
        via_front = p1.y + p2.y + abs(p1.x - p2.x)
        via_back = (self.aisle_length - p1.y) + (self.aisle_length - p2.y) + abs(p1.x - p2.x)
        return min(via_front, via_back)

    def path_distance(self, waypoints: list[Point]) -> float:
        """Total walking distance along an ordered waypoint list (depot excluded)."""
        total = 0.0
        prev = self.depot
        for point in waypoints:
            total += self.distance(prev, point)
            prev = point
        total += self.distance(prev, self.depot)
        return total

    def bins_by_depot_distance(self) -> list[Bin]:
        """All bins sorted by walking distance from the depot (nearest first)."""
        return sorted(self.bins.values(), key=lambda b: self.distance(self.depot, b.point))

    def bins_in_aisle(self, aisle: int) -> list[Bin]:
        return [b for b in self.bins.values() if b.aisle == aisle]

    # -- serialisation ------------------------------------------------------
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "num_aisles": self.num_aisles,
            "aisle_length": self.aisle_length,
            "aisle_spacing": self.aisle_spacing,
            "slots_per_aisle": self.slots_per_aisle,
            "depot_x": self.depot_x,
            "bin_capacity_units": self.bin_capacity_units,
            "bins": [b.to_dict() for b in self.bins.values()],
        }

    @classmethod
    def from_dict(cls, data: dict) -> "WarehouseLayout":
        try:
            layout = cls(
                name=data["name"],
                num_aisles=int(data["num_aisles"]),
                aisle_length=float(data["aisle_length"]),
                aisle_spacing=float(data["aisle_spacing"]),
                slots_per_aisle=int(data["slots_per_aisle"]),
                depot_x=float(data.get("depot_x", 0.0)),
                bin_capacity_units=int(data.get("bin_capacity_units", 100)),
            )
        except KeyError as exc:
            raise ValidationError(f"layout JSON is missing required key: {exc}") from exc
        for entry in data.get("bins", []):
            bin_id = entry["bin_id"]
            if bin_id in layout.bins:
                layout.bins[bin_id].sku_id = entry.get("sku_id")
                layout.bins[bin_id].quantity = int(entry.get("quantity", 0))
        return layout

    @classmethod
    def load_json(cls, path: str | Path) -> "WarehouseLayout":
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise ValidationError(f"layout file not found: {path}") from exc
        except json.JSONDecodeError as exc:
            raise ValidationError(f"layout file is not valid JSON: {exc}") from exc
        if not isinstance(data, dict):
            raise ValidationError("layout JSON must be an object")
        return cls.from_dict(data)

    def summary(self) -> dict:
        return {
            "name": self.name,
            "aisles": self.num_aisles,
            "aisle_length_m": self.aisle_length,
            "aisle_spacing_m": self.aisle_spacing,
            "slots_per_aisle": self.slots_per_aisle,
            "total_bins": self.total_bins,
            "width_m": self.width,
            "depot_x_m": self.depot_x,
            "bins_with_stock": sum(1 for b in self.bins.values() if b.quantity > 0),
        }
