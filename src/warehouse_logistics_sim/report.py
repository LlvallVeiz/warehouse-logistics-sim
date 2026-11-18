"""Reporting: Markdown + HTML reports and CSV exports from simulation results."""

from __future__ import annotations

import csv
from pathlib import Path

from warehouse_logistics_sim.inventory import ABCResult
from warehouse_logistics_sim.picking import StrategyComparisonRow
from warehouse_logistics_sim.simulation import SimResult
from warehouse_logistics_sim.slotting import SlottingEvaluation

_CSS = """body{font-family:system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
margin:2rem auto;max-width:900px;padding:0 1rem;color:#1a1a1a}
h1,h2{color:#0b3d5c}table{border-collapse:collapse;width:100%;margin:1rem 0}
th,td{border:1px solid #ccc;padding:.4rem .6rem;text-align:left}
th{background:#eef4f8}tr:nth-child(even){background:#f8f8f8}
.kpi{font-size:1.05rem}.good{color:#1a7f37}.warn{color:#b25e09}"""


def _fmt(value: float | int | None, decimals: int = 2) -> str:
    if value is None:
        return "n/a"
    if isinstance(value, int):
        return f"{value:,}"
    return f"{value:,.{decimals}f}"


def simulation_to_markdown(result: SimResult, title: str = "Warehouse simulation report") -> str:
    kpi = result.kpi_table()
    lines = [f"# {title}", ""]
    lines.append(f"Strategy: **{result.strategy}** · Pickers: {result.config.num_pickers} · "
                 f"Shift: {result.config.shift_minutes:.0f} min · "
                 f"Batch: up to {result.config.batch_max_orders} orders / {result.config.batch_max_lines} lines")
    lines.append("")
    lines.append("## Key performance indicators")
    lines.append("")
    lines.append("| KPI | Value |")
    lines.append("| --- | --- |")
    lines.append(f"| Orders arrived | {_fmt(kpi['orders_arrived'], 0)} |")
    lines.append(f"| Orders completed | {_fmt(kpi['orders_completed'], 0)} |")
    lines.append(f"| Orders backlogged | {_fmt(kpi['orders_backlogged'], 0)} |")
    lines.append(f"| Lines requested | {_fmt(kpi['lines_requested'], 0)} |")
    lines.append(f"| Lines filled | {_fmt(kpi['lines_filled'], 0)} |")
    lines.append(f"| Fill rate | {kpi['fill_rate'] * 100:.1f}% |")
    lines.append(f"| Pick rate (lines / picker-hour) | {_fmt(kpi['pick_rate_lines_per_picker_hour'])} |")
    lines.append(f"| Total distance (m) | {_fmt(kpi['total_distance_m'])} |")
    lines.append(f"| Mean order cycle time (min) | {_fmt(kpi['mean_cycle_time_min'])} |")
    lines.append(f"| Picker utilisation | {kpi['picker_utilisation'] * 100:.1f}% |")
    lines.append(f"| Units picked | {_fmt(kpi['total_units_picked'], 0)} |")
    lines.append("")
    if result.stockouts:
        lines.append("## Stockouts")
        lines.append("")
        lines.append("| SKU | Unfilled lines |")
        lines.append("| --- | --- |")
        for sku_id, count in sorted(result.stockouts.items(), key=lambda kv: -kv[1]):
            lines.append(f"| {sku_id} | {count} |")
        lines.append("")
    lines.append("## Per-order results (first 20)")
    lines.append("")
    lines.append("| Order | Arrival (min) | Start | Finish | Cycle (min) | Lines filled | Distance (m) |")
    lines.append("| --- | --- | --- | --- | --- | --- | --- |")
    for r in result.order_results[:20]:
        lines.append(
            f"| {r.order_id} | {_fmt(r.arrival_minute)} | "
            f"{_fmt(r.start_minute) if r.start_minute is not None else '—'} | "
            f"{_fmt(r.finish_minute) if r.finish_minute is not None else '—'} | "
            f"{_fmt(r.cycle_time_min) if r.cycle_time_min is not None else '—'} | "
            f"{r.lines_filled}/{r.lines_requested} | {_fmt(r.distance_m)} |"
        )
    return "\n".join(lines) + "\n"


def simulation_to_html(result: SimResult, title: str = "Warehouse simulation report") -> str:
    md = simulation_to_markdown(result, title)
    # Minimal Markdown -> HTML for the tables/headers this report uses.
    html_lines = ["<!DOCTYPE html>", "<html lang=\"en\">", "<head>",
                  f"<meta charset=\"utf-8\"><title>{title}</title>",
                  f"<style>{_CSS}</style>", "</head>", "<body>"]
    in_table = False
    for line in md.splitlines():
        if line.startswith("# "):
            html_lines.append(f"<h1>{line[2:]}</h1>")
        elif line.startswith("## "):
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<h2>{line[3:]}</h2>")
        elif line.startswith("|"):
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if set(cells) <= {"---"}:
                continue
            if not in_table:
                html_lines.append("<table>")
                in_table = True
                tag = "th"
            else:
                tag = "td"
            html_lines.append("<tr>" + "".join(f"<{tag}>{c}</{tag}>" for c in cells) + "</tr>")
        elif line.strip():
            if in_table:
                html_lines.append("</table>")
                in_table = False
            html_lines.append(f"<p>{line}</p>")
    if in_table:
        html_lines.append("</table>")
    html_lines += ["</body>", "</html>"]
    return "\n".join(html_lines) + "\n"


def comparison_to_markdown(rows: list[StrategyComparisonRow], n_orders: int) -> str:
    lines = ["# Routing strategy comparison", "",
             f"Same {n_orders} orders routed with each heuristic (identical cost model).", "",
             "| Strategy | Total distance (m) | Total time (min) | Avg distance/order (m) | "
             "Avg time/order (s) |",
             "| --- | --- | --- | --- | --- |"]
    best = min(rows, key=lambda r: r.total_distance_m)
    for row in sorted(rows, key=lambda r: r.total_distance_m):
        mark = " **(shortest)**" if row is best else ""
        lines.append(
            f"| {row.strategy}{mark} | {_fmt(row.total_distance_m)} | "
            f"{_fmt(row.total_time_s / 60.0)} | {_fmt(row.avg_distance_per_order_m)} | "
            f"{_fmt(row.avg_time_per_order_s)} |"
        )
    return "\n".join(lines) + "\n"


def abc_to_markdown(results: list[ABCResult]) -> str:
    lines = ["# ABC analysis", "",
             "| SKU | Annual usage value | Share | Cumulative | Class |",
             "| --- | --- | --- | --- | --- |"]
    for r in results:
        lines.append(
            f"| {r.sku_id} | {_fmt(r.annual_usage_value)} | {r.share * 100:.1f}% | "
            f"{r.cumulative_share * 100:.1f}% | {r.abc_class} |"
        )
    return "\n".join(lines) + "\n"


def slotting_to_markdown(evaluation: SlottingEvaluation) -> str:
    lines = ["# Slotting evaluation (cube-per-order index)", "",
             f"Expected travel per pick before: **{_fmt(evaluation.before_m_per_pick)} m**",
             f"Expected travel per pick after: **{_fmt(evaluation.after_m_per_pick)} m**",
             f"Improvement: **{evaluation.improvement_pct:.1f}%**", "",
             "| SKU | Bin | Distance from depot (m) | COI (m³/pick) |",
             "| --- | --- | --- | --- |"]
    for a in evaluation.assignments:
        lines.append(f"| {a.sku_id} | {a.bin_id} | {_fmt(a.distance_from_depot_m)} | {a.coi:.6f} |")
    return "\n".join(lines) + "\n"


def write_orders_csv(result: SimResult, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["order_id", "arrival_min", "start_min", "finish_min",
                         "cycle_min", "lines_requested", "lines_filled",
                         "units_picked", "distance_m"])
        for r in result.order_results:
            writer.writerow([
                r.order_id,
                f"{r.arrival_minute:.2f}",
                f"{r.start_minute:.2f}" if r.start_minute is not None else "",
                f"{r.finish_minute:.2f}" if r.finish_minute is not None else "",
                f"{r.cycle_time_min:.2f}" if r.cycle_time_min is not None else "",
                r.lines_requested,
                r.lines_filled,
                r.units_picked,
                f"{r.distance_m:.2f}",
            ])
    return path


def generate_report(
    result: SimResult,
    comparison: list[StrategyComparisonRow] | None,
    out_dir: str | Path,
    title: str = "Warehouse simulation report",
) -> dict[str, Path]:
    """Write report.md, report.html and simulation.csv into ``out_dir``."""
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    md = simulation_to_markdown(result, title)
    if comparison:
        md += "\n" + comparison_to_markdown(comparison, len(result.order_results))
    md_path = out_dir / "report.md"
    md_path.write_text(md, encoding="utf-8")
    html_path = out_dir / "report.html"
    html_path.write_text(simulation_to_html(result, title), encoding="utf-8")
    csv_path = write_orders_csv(result, out_dir / "simulation.csv")
    return {"markdown": md_path, "html": html_path, "csv": csv_path}
