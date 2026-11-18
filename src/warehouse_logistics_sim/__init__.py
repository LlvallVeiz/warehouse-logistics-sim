"""Warehouse logistics simulator: layout, inventory, picking, simulation, reporting.

End-to-end simulation of a picker-to-parts warehouse: single-block layout
with front/back cross aisles, ABC inventory analysis, EOQ / reorder-point
planning, slotting by cube-per-order index, order-picking routing heuristics
(S-shape, largest gap, return, nearest neighbour, 2-opt), batch and zone
picking, a discrete-event shift simulation, and Markdown/HTML reporting.
"""

__version__ = "1.0.0"

from warehouse_logistics_sim.errors import ValidationError

__all__ = ["__version__", "ValidationError"]
