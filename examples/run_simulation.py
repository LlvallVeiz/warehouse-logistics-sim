"""Run the medium demo scenario and print its shift KPIs.

Usage (from the project root):
    python examples/run_simulation.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from warehouse_logistics_sim.scenarios import load_scenario
from warehouse_logistics_sim.simulation import run_simulation


def main() -> None:
    scenario = load_scenario(Path(__file__).resolve().parent / "scenarios" / "medium.json")
    result = run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, scenario.config
    )
    kpi = result.kpi_table()
    print(f"Scenario: {scenario.name} ({len(scenario.orders)} orders, "
          f"{result.config.num_pickers} pickers, strategy {result.strategy})")
    for key, value in kpi.items():
        print(f"  {key}: {value}")


if __name__ == "__main__":
    main()
