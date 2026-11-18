"""Command-line interface for warehouse-logistics-sim.

Subcommands:
  layout             show a layout summary (built-in or from a scenario file)
  inventory          list SKUs with EOQ / safety stock / reorder point
  abc                ABC (Pareto) classification of the catalogue
  simulate           run one shift simulation and print KPIs
  compare-strategies route the same orders with every picking heuristic
  report             run a simulation and write Markdown/HTML/CSV reports
"""

from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

from warehouse_logistics_sim import __version__
from warehouse_logistics_sim.errors import ValidationError
from warehouse_logistics_sim.inventory import (
    abc_analysis,
    abc_summary,
    replenishment_plan,
)
from warehouse_logistics_sim.picking import compare_strategies
from warehouse_logistics_sim.report import (
    abc_to_markdown,
    generate_report,
)
from warehouse_logistics_sim.scenarios import build_scenario, load_batch, load_scenario
from warehouse_logistics_sim.simulation import SimConfig, run_simulation
from warehouse_logistics_sim.slotting import evaluate_slotting


def _scenario(args: argparse.Namespace):
    if args.scenario:
        return load_scenario(args.scenario)
    return build_scenario(
        n_orders=args.orders,
        seed=args.seed,
        config=SimConfig(
            shift_minutes=args.shift_minutes,
            num_pickers=args.pickers,
            batch_max_orders=args.batch_orders,
            batch_max_lines=args.batch_lines,
            strategy=args.strategy,
            service_level=args.service_level,
        ),
        name="cli",
    )


def _print_kpis(result) -> None:
    kpi = result.kpi_table()
    print(f"Strategy: {result.strategy} | pickers: {result.config.num_pickers} | "
          f"shift: {result.config.shift_minutes:.0f} min")
    print(f"Orders arrived:   {kpi['orders_arrived']}")
    print(f"Orders completed: {kpi['orders_completed']}")
    print(f"Orders backlogged: {kpi['orders_backlogged']}")
    print(f"Lines requested:  {kpi['lines_requested']}")
    print(f"Lines filled:     {kpi['lines_filled']}")
    print(f"Fill rate:        {kpi['fill_rate'] * 100:.1f}%")
    print(f"Pick rate:        {kpi['pick_rate_lines_per_picker_hour']:.1f} lines/picker-hour")
    print(f"Total distance:   {kpi['total_distance_m']:,.1f} m")
    print(f"Mean cycle time:  {kpi['mean_cycle_time_min']:.1f} min"
          if kpi['mean_cycle_time_min'] is not None else "Mean cycle time:  n/a")
    print(f"Picker utilisation: {kpi['picker_utilisation'] * 100:.1f}%")
    print(f"Units picked:     {kpi['total_units_picked']}")
    if result.stockouts:
        print(f"Stockouts:        {sum(result.stockouts.values())} unfilled lines "
              f"across {len(result.stockouts)} SKUs")


def cmd_layout(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    summary = scenario.layout.summary()
    print(f"Layout: {summary['name']}")
    print(f"Aisles: {summary['aisles']} x {summary['aisle_length_m']:.1f} m, "
          f"spacing {summary['aisle_spacing_m']:.1f} m, width {summary['width_m']:.1f} m")
    print(f"Slots per aisle: {summary['slots_per_aisle']}, total bins: {summary['total_bins']}")
    print(f"Depot x: {summary['depot_x_m']:.1f} m, bins with stock: {summary['bins_with_stock']}")
    print(f"SKUs: {len(scenario.skus)}, orders: {len(scenario.orders)}")
    return 0


def cmd_inventory(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    plans = replenishment_plan(scenario.skus, args.service_level)
    print(f"{'SKU':<12}{'On hand':>9}{'EOQ':>9}{'Safety':>9}{'ROP':>9}{'Reorder?':>9}")
    for plan in plans:
        print(f"{plan.sku_id:<12}{plan.on_hand:>9}{plan.eoq:>9.1f}"
              f"{plan.safety_stock:>9.1f}{plan.reorder_point:>9.1f}"
              f"{'YES' if plan.needs_reorder else 'no':>9}")
    print(f"\n{sum(p.needs_reorder for p in plans)} of {len(plans)} SKUs at or below reorder point.")
    return 0


def cmd_abc(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    results = abc_analysis(scenario.skus)
    summary = abc_summary(results)
    for cls in ("A", "B", "C"):
        info = summary[cls]
        print(f"Class {cls}: {info['count']:>3} SKUs, {info['value_share'] * 100:5.1f}% of usage value")
    print()
    print(f"{'SKU':<12}{'Usage value':>14}{'Share':>8}{'Cumulative':>12}{'Class':>7}")
    for r in results:
        print(f"{r.sku_id:<12}{r.annual_usage_value:>14,.2f}{r.share * 100:>7.1f}%"
              f"{r.cumulative_share * 100:>11.1f}%{r.abc_class:>7}")
    if args.markdown:
        print()
        print(abc_to_markdown(results))
    return 0


def cmd_simulate(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    result = run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, scenario.config
    )
    _print_kpis(result)
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    rows = compare_strategies(
        scenario.layout, scenario.orders, scenario.bin_by_sku,
        speed_m_per_s=scenario.config.speed_m_per_s,
        pick_time_per_line_s=scenario.config.pick_time_per_line_s,
        setup_time_s=scenario.config.setup_time_s,
    )
    print(f"Routing the same {len(scenario.orders)} orders with each strategy:")
    print(f"{'Strategy':<18}{'Total dist (m)':>16}{'Total time (min)':>18}"
          f"{'Avg dist/order (m)':>20}{'Avg time/order (s)':>20}")
    best = min(rows, key=lambda r: r.total_distance_m)
    for row in sorted(rows, key=lambda r: r.total_distance_m):
        mark = " *" if row is best else ""
        print(f"{row.strategy:<18}{row.total_distance_m:>16,.1f}"
              f"{row.total_time_s / 60.0:>18,.1f}{row.avg_distance_per_order_m:>20,.1f}"
              f"{row.avg_time_per_order_s:>20,.1f}{mark}")
    print("\n* shortest total distance")
    return 0


def cmd_report(args: argparse.Namespace) -> int:
    scenario = _scenario(args)
    result = run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, scenario.config
    )
    comparison = compare_strategies(
        scenario.layout, scenario.orders, scenario.bin_by_sku,
        speed_m_per_s=scenario.config.speed_m_per_s,
        pick_time_per_line_s=scenario.config.pick_time_per_line_s,
        setup_time_s=scenario.config.setup_time_s,
    )
    paths = generate_report(result, comparison, args.out_dir, title=f"Warehouse simulation — {scenario.name}")
    _print_kpis(result)
    print()
    for label, path in paths.items():
        print(f"Wrote {label}: {path}")
    # Slotting evaluation goes to stdout as well.
    current = {sku.sku_id: next(b.bin_id for b in scenario.layout.bins.values()
                                if b.sku_id == sku.sku_id) for sku in scenario.skus}
    evaluation = evaluate_slotting(
        scenario.layout, scenario.skus, scenario.annual_picks, current
    )
    print()
    print(f"Slotting: expected travel/pick {evaluation.before_m_per_pick:.2f} m -> "
          f"{evaluation.after_m_per_pick:.2f} m "
          f"({evaluation.improvement_pct:+.1f}%)")
    return 0


def cmd_batch(args: argparse.Namespace) -> int:
    """Run several scenarios from a batch JSON file and print a KPI table."""
    entries = load_batch(args.file)
    print(f"{'Scenario':<24}{'Strategy':<18}{'Orders':>8}{'Fill %':>8}"
          f"{'Pick rate':>11}{'Distance (m)':>14}{'Cycle (min)':>12}")
    for entry in entries:
        if isinstance(entry, str):
            scenario = load_scenario(entry)
        else:
            with tempfile.NamedTemporaryFile(
                "w", suffix=".json", delete=False, encoding="utf-8"
            ) as fh:
                json.dump(entry, fh)
                tmp = Path(fh.name)
            try:
                scenario = load_scenario(tmp)
            finally:
                tmp.unlink(missing_ok=True)
        result = run_simulation(
            scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, scenario.config
        )
        kpi = result.kpi_table()
        cycle = f"{kpi['mean_cycle_time_min']:>12.1f}" if kpi['mean_cycle_time_min'] is not None else " " * 12
        print(f"{scenario.name:<24}{result.strategy:<18}{kpi['orders_arrived']:>8}"
              f"{kpi['fill_rate'] * 100:>7.1f}%"
              f"{kpi['pick_rate_lines_per_picker_hour']:>11.1f}"
              f"{kpi['total_distance_m']:>14,.0f}{cycle}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="warehouse-logistics-sim",
        description="End-to-end warehouse + logistics simulator (layout, inventory, "
                    "picking routes, shift simulation, reports).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    parser.add_argument("--scenario", default=None,
                        help="scenario JSON file (default: built-in demo scenario)")
    parser.add_argument("--orders", type=int, default=120,
                        help="orders to generate for the built-in scenario (default 120)")
    parser.add_argument("--seed", type=int, default=42, help="random seed (default 42)")
    parser.add_argument("--shift-minutes", type=float, default=480.0)
    parser.add_argument("--pickers", type=int, default=4)
    parser.add_argument("--batch-orders", type=int, default=4)
    parser.add_argument("--batch-lines", type=int, default=20)
    parser.add_argument("--strategy", default="s_shape",
                        choices=["s_shape", "largest_gap", "return",
                                 "nearest_neighbor", "two_opt"])
    parser.add_argument("--service-level", type=float, default=0.95)
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("layout", help="show layout summary").set_defaults(func=cmd_layout)
    sub.add_parser("inventory", help="EOQ / safety stock / reorder point per SKU").set_defaults(func=cmd_inventory)
    abc_p = sub.add_parser("abc", help="ABC (Pareto) classification")
    abc_p.add_argument("--markdown", action="store_true", help="also print a Markdown table")
    abc_p.set_defaults(func=cmd_abc)
    sub.add_parser("simulate", help="run one shift simulation").set_defaults(func=cmd_simulate)
    sub.add_parser("compare-strategies", help="route the same orders with every heuristic").set_defaults(func=cmd_compare)
    rep_p = sub.add_parser("report", help="simulate and write Markdown/HTML/CSV reports")
    rep_p.add_argument("--out-dir", default="examples/output", help="output directory")
    rep_p.set_defaults(func=cmd_report)
    batch_p = sub.add_parser("batch", help="run several scenarios from a batch JSON file")
    batch_p.add_argument("--file", required=True, help="batch JSON file")
    batch_p.set_defaults(func=cmd_batch)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except ValidationError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
