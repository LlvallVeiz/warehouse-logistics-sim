"""Tests for reports, scenarios and the CLI."""

import csv

import pytest

from warehouse_logistics_sim.cli import main
from warehouse_logistics_sim.picking import compare_strategies
from warehouse_logistics_sim.report import (
    comparison_to_markdown,
    generate_report,
    simulation_to_html,
    simulation_to_markdown,
    write_orders_csv,
)
from warehouse_logistics_sim.scenarios import (
    build_scenario,
    default_layout,
    load_scenario,
    small_layout,
)
from warehouse_logistics_sim.simulation import run_simulation


def _sim_result():
    scenario = build_scenario(layout=default_layout(), n_orders=30, seed=9)
    result = run_simulation(
        scenario.layout, scenario.skus, scenario.bin_by_sku, scenario.orders, scenario.config
    )
    return scenario, result


def test_markdown_report_contains_kpis():
    _, result = _sim_result()
    md = simulation_to_markdown(result, "Test report")
    assert "# Test report" in md
    assert "Fill rate" in md
    assert "Pick rate" in md
    assert "| Orders arrived | 30 |" in md


def test_html_report_is_valid_skeleton():
    _, result = _sim_result()
    html = simulation_to_html(result, "Test report")
    assert html.startswith("<!DOCTYPE html>")
    assert "<table>" in html
    assert "Fill rate" in html
    assert html.rstrip().endswith("</html>")


def test_comparison_markdown_marks_shortest():
    scenario, _ = _sim_result()
    rows = compare_strategies(scenario.layout, scenario.orders, scenario.bin_by_sku)
    md = comparison_to_markdown(rows, len(scenario.orders))
    assert "**(shortest)**" in md
    assert md.count("**(shortest)**") == 1


def test_csv_export_row_count(tmp_path):
    _, result = _sim_result()
    path = write_orders_csv(result, tmp_path / "sim.csv")
    with path.open(newline="", encoding="utf-8") as fh:
        rows = list(csv.reader(fh))
    assert rows[0][0] == "order_id"
    assert len(rows) == len(result.order_results) + 1


def test_generate_report_writes_three_files(tmp_path):
    _, result = _sim_result()
    paths = generate_report(result, None, tmp_path)
    assert paths["markdown"].exists()
    assert paths["html"].exists()
    assert paths["csv"].exists()
    assert paths["markdown"].read_text(encoding="utf-8").startswith("#")


def test_load_scenario_small(tmp_path):
    scenario = load_scenario("examples/scenarios/small.json")
    assert scenario.layout.name == "small-warehouse"
    assert len(scenario.skus) == 24  # truncated to fit 24 bins
    assert len(scenario.orders) == 60
    assert scenario.config.strategy == "largest_gap"


def test_load_scenario_medium():
    scenario = load_scenario("examples/scenarios/medium.json")
    assert len(scenario.skus) == 48
    assert len(scenario.orders) == 360


def test_load_scenario_errors(tmp_path):
    with pytest.raises(Exception):
        load_scenario(tmp_path / "missing.json")
    bad = tmp_path / "bad.json"
    bad.write_text("[1,2]", encoding="utf-8")
    with pytest.raises(Exception):
        load_scenario(bad)


def test_cli_layout(capsys):
    assert main(["layout"]) == 0
    assert "Layout: demo-warehouse" in capsys.readouterr().out


def test_cli_inventory(capsys):
    assert main(["inventory"]) == 0
    out = capsys.readouterr().out
    assert "ELEC-001" in out
    assert "Reorder?" in out


def test_cli_abc(capsys):
    assert main(["abc"]) == 0
    out = capsys.readouterr().out
    assert "Class A:" in out
    assert "Class C:" in out


def test_cli_simulate(capsys):
    assert main(["simulate"]) == 0
    out = capsys.readouterr().out
    assert "Fill rate:" in out
    assert "Pick rate:" in out


def test_cli_compare(capsys):
    assert main(["compare-strategies"]) == 0
    out = capsys.readouterr().out
    assert "s_shape" in out
    assert "two_opt" in out
    assert "shortest" in out


def test_cli_report(tmp_path, capsys):
    assert main(["report", "--out-dir", str(tmp_path)]) == 0
    out = capsys.readouterr().out
    assert "Wrote markdown" in out
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "report.html").exists()
    assert (tmp_path / "simulation.csv").exists()


def test_cli_batch(capsys):
    assert main(["batch", "--file", "examples/scenarios/batch.json"]) == 0
    out = capsys.readouterr().out
    assert "small-largest-gap" in out
    assert "medium-s-shape" in out
    assert "medium-two-opt" in out


def test_cli_invalid_scenario(capsys):
    assert main(["--scenario", "nope.json", "layout"]) == 2
    assert "error:" in capsys.readouterr().err


def test_cli_with_scenario_file(capsys):
    assert main(["--scenario", "examples/scenarios/small.json", "simulate"]) == 0
    assert "Fill rate:" in capsys.readouterr().out
