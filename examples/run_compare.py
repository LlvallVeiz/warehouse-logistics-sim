"""Compare all five routing heuristics on the same medium-scenario orders.

Usage (from the project root):
    python examples/run_compare.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from warehouse_logistics_sim.picking import compare_strategies
from warehouse_logistics_sim.scenarios import load_scenario


def main() -> None:
    scenario = load_scenario(Path(__file__).resolve().parent / "scenarios" / "medium.json")
    rows = compare_strategies(scenario.layout, scenario.orders, scenario.bin_by_sku)
    print(f"Same {len(scenario.orders)} orders, one route per order:")
    for row in sorted(rows, key=lambda r: r.total_distance_m):
        print(f"  {row.strategy:<18} total {row.total_distance_m:>10,.1f} m  "
              f"avg {row.avg_distance_per_order_m:>7,.1f} m/order  "
              f"{row.total_time_s / 60:.1f} min total")


if __name__ == "__main__":
    main()
