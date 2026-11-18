"""ABC classification + COI slotting evaluation on the medium scenario.

Usage (from the project root):
    python examples/run_abc_slotting.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from warehouse_logistics_sim.inventory import abc_analysis, abc_summary
from warehouse_logistics_sim.scenarios import load_scenario
from warehouse_logistics_sim.slotting import evaluate_slotting


def main() -> None:
    scenario = load_scenario(Path(__file__).resolve().parent / "scenarios" / "medium.json")
    results = abc_analysis(scenario.skus)
    summary = abc_summary(results)
    print("ABC classes (by annual usage value):")
    for cls in ("A", "B", "C"):
        info = summary[cls]
        print(f"  Class {cls}: {info['count']:>2} SKUs, {info['value_share'] * 100:.1f}% of value")
    current = {
        sku.sku_id: next(b.bin_id for b in scenario.layout.bins.values() if b.sku_id == sku.sku_id)
        for sku in scenario.skus
    }
    evaluation = evaluate_slotting(
        scenario.layout, scenario.skus, scenario.annual_picks, current
    )
    print(f"Slotting: {evaluation.before_m_per_pick:.2f} m/pick (random) -> "
          f"{evaluation.after_m_per_pick:.2f} m/pick (COI) "
          f"= {evaluation.improvement_pct:+.1f}%")
    print("Top 5 COI assignments (closest to depot):")
    for a in evaluation.assignments[:5]:
        print(f"  {a.sku_id} -> {a.bin_id} ({a.distance_from_depot_m:.1f} m, COI {a.coi:.6f})")


if __name__ == "__main__":
    main()
