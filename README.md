# warehouse-logistics-sim

End-to-end warehouse + logistics simulator in pure Python (standard
library only): define a warehouse layout, plan inventory (ABC, EOQ,
safety stock, reorder point), slot SKUs by cube-per-order index,
generate realistic orders, route picking tours with five heuristics,
simulate a full picking shift with parallel pickers, and produce
Markdown/HTML reports plus CSV exports.

## Background

Order picking is the most labour-intensive warehouse activity — de Koster,
Le-Duc & Roodbergen (2007) estimate it at up to 55% of total warehouse
operating expense. Four decisions drive its cost: layout, storage
assignment (slotting), routing, and batching/zoning. This package models
all four so their trade-offs can be measured on the same orders:

- **Layout** — single-block warehouse: parallel aisles, front and back
  cross aisles, depot on the front cross aisle. Travel distance is the
  aisle-aware shortest path (via the front or the back cross aisle).
- **Inventory** — ABC (Pareto) classification by annual usage value;
  EOQ (Harris 1913); safety stock and reorder point from a target cycle
  service level (z-score).
- **Slotting** — cube-per-order index (volume / picks): fast, small
  movers go to the bins nearest the depot. The gain is measured, not
  asserted (see below).
- **Picking** — S-shape, largest gap, return, nearest neighbour, and
  2-opt routing; single-order, batch, and zone picking.
- **Simulation** — discrete-event shift simulation: orders arrive over
  the shift, parallel pickers take FIFO batches, stock is decremented
  per line, replenishment (EOQ after lead time) is scheduled when a SKU
  hits its reorder point. KPIs: pick rate, distance, cycle time, fill
  rate, picker utilisation, backlog.

Theory, formulas and sources: [`docs/RESEARCH.md`](docs/RESEARCH.md).

## Project structure

```text
warehouse-logistics-sim/
├── src/warehouse_logistics_sim/
│   ├── layout.py       # warehouse geometry, bins, aisle-aware distances
│   ├── inventory.py    # SKU, ABC, EOQ, safety stock, reorder point
│   ├── slotting.py     # cube-per-order index slotting + evaluation
│   ├── orders.py       # realistic order generator (Zipf popularity)
│   ├── routing.py      # S-shape, largest gap, return, NN, 2-opt
│   ├── picking.py      # batch picking, zone picking, strategy comparison
│   ├── simulation.py   # discrete-event shift simulation + KPIs
│   ├── report.py       # Markdown/HTML reports, CSV export
│   ├── scenarios.py    # built-in demo catalogue + JSON scenario loading
│   ├── cli.py          # subcommands: layout, inventory, abc, simulate,
│   │                   #   compare-strategies, report, batch
│   └── __main__.py
├── tests/              # pytest, 69 tests (hand-computed references)
├── examples/
│   ├── scenarios/      # small.json, medium.json, batch.json
│   ├── run_simulation.py / run_compare.py / run_abc_slotting.py
│   ├── output/         # report.md, report.html, simulation.csv (real runs)
│   └── RESULTS.md
├── docs/RESEARCH.md
├── pyproject.toml  requirements.txt  LICENSE (MIT)
└── CHANGELOG.md
```

## Installation

Python 3.10+; no third-party runtime dependencies.

```bash
git clone https://github.com/LlvallVeiz/warehouse-logistics-sim.git
cd warehouse-logistics-sim
pip install -e .            # or: pip install -r requirements.txt
# without installing, run from the project root with:
PYTHONPATH=src python -m warehouse_logistics_sim --help
```

## Usage

```bash
# Layout summary of the built-in demo warehouse (8 aisles, 96 bins, 48 SKUs)
warehouse-logistics-sim layout

# EOQ / safety stock / reorder point per SKU (95% service level)
warehouse-logistics-sim inventory

# ABC classification
warehouse-logistics-sim abc

# One shift simulation (360 orders, 4 pickers, S-shape, seed 42)
warehouse-logistics-sim --scenario examples/scenarios/medium.json simulate

# Route the same orders with all five heuristics and compare
warehouse-logistics-sim --scenario examples/scenarios/medium.json compare-strategies

# Full run: simulation + comparison + slotting evaluation + reports
warehouse-logistics-sim --scenario examples/scenarios/medium.json report --out-dir examples/output

# Several scenarios in one batch file
warehouse-logistics-sim batch --file examples/scenarios/batch.json

# Custom shift: 6 pickers, batches of 6 orders, 2-opt routing
warehouse-logistics-sim --pickers 6 --batch-orders 6 --strategy two_opt simulate
```

Scenario files are JSON: `layout` (aisles, length, spacing, slots,
depot), optional `skus`, `n_orders`, `seed`, and `simulation` settings
(pickers, batch caps, strategy, speed, pick/setup times, service level,
replenishment on/off). See `examples/scenarios/medium.json`.

## Example output (real runs, seed 42)

Medium scenario — 8 aisles x 20 m, 96 bins, 48 SKUs, 360 orders, 4 pickers,
S-shape routing, batch of up to 4 orders / 20 lines:

```text
Strategy: s_shape | pickers: 4 | shift: 480 min
Orders arrived:   360
Orders completed: 360
Orders backlogged: 0
Lines requested:  998
Lines filled:     978
Fill rate:        98.0%
Pick rate:        139.6 lines/picker-hour
Total distance:   11,843.3 m
Mean cycle time:  6.7 min
Picker utilisation: 21.9%
Units picked:     1653
Stockouts:        20 unfilled lines across 9 SKUs
```

The 98% fill rate is honest, not a bug: slow SKUs start the shift with
only ~2 weeks of stock (a handful of units), and supplier lead times of
3–7 days mean no replenishment can land inside one 8-hour shift.

Routing comparison — same 360 orders, one route per order:

| Strategy | Total distance (m) | Total time (min) | Avg distance/order (m) |
| --- | --- | --- | --- |
| two_opt | 24,367.7 | 899.2 | 67.7 |
| nearest_neighbor | 24,732.0 | 905.3 | 68.7 |
| s_shape | 25,166.3 | 912.5 | 69.9 |
| return | 25,439.7 | 917.1 | 70.7 |
| largest_gap | 25,571.3 | 919.3 | 71.0 |

2-opt beats S-shape by 3.2% — inside the ~5% band the literature
reports for the best heuristic vs optimal.

ABC classification (annual usage value):

| Class | SKUs | Share of usage value |
| --- | --- | --- |
| A | 18 | 81.1% |
| B | 16 | 14.3% |
| C | 14 | 4.6% |

Slotting (cube-per-order index), random placement vs COI placement:

| | Expected travel per pick |
| --- | --- |
| Before (random) | 20.62 m |
| After (COI) | 8.63 m |
| Improvement | +58.1% |

EOQ example — `ELEC-001` (D = 12,000/yr, S = 55, H = 9.88/yr):
EOQ = √(2·12000·55 / 9.88) = **365.5 units**, safety stock (95%) =
**61.0**, reorder point = **192.5**.

Small scenario — 4 aisles, 24 bins, 60 orders, 2 pickers, largest gap:
fill rate 100%, pick rate 143.2 lines/picker-hour, 1,344.0 m total,
mean cycle time 12.5 min, utilisation 6.6%.

Batch mode (`examples/scenarios/batch.json`):

| Scenario | Strategy | Orders | Fill % | Pick rate | Distance (m) | Cycle (min) |
| --- | --- | --- | --- | --- | --- | --- |
| small-largest-gap | largest_gap | 60 | 100.0% | 143.2 | 1,344 | 12.5 |
| medium-s-shape | s_shape | 360 | 98.0% | 139.6 | 11,843 | 6.7 |
| medium-two-opt | two_opt | 360 | 98.0% | 148.2 | 10,373 | 6.4 |

Full reports from the medium run are in `examples/output/`
(`report.md`, `report.html`, `simulation.csv`).

## Design decisions

- **Stdlib only.** No numpy/pandas: the whole model is arithmetic over
  small collections, and zero dependencies keeps the project installable
  anywhere.
- **One cost model for all strategies.** Every heuristic returns an
  explicit waypoint list and its distance is computed by
  `layout.path_distance`, so comparisons cannot favour one heuristic
  through a different cost function.
- **Deterministic scenarios.** All randomness is seeded; the same seed
  reproduces identical orders and KPIs (asserted in tests).
- **2-opt as the near-optimal reference**, not the Ratliff–Rosenthal
  exact algorithm — simpler, general, and within a few percent of the
  heuristics it is compared against.
- **Replenishment in days.** Lead times are supplier lead times (days),
  so they only matter across shifts; inside one shift a stockout stays a
  stockout, which the fill rate reports honestly.

## Limitations & future work

- Single-block layout only (no middle cross aisle, no multi-block).
- No congestion, picker blocking, or forklift traffic.
- Constant walking speed and pick times; no fatigue or learning curves.
- No exact optimal routing (Ratliff–Rosenthal) and no dynamic
  re-slotting during a shift.
- Inventory is single-echelon with no supplier capacity constraints.
- Future: middle-aisle layouts, congestion model, order-batching
  optimisation (seed/ Clarke–Wright style), ABC-XYZ analysis, and a
  web dashboard over the simulation CSV.

## Tests

```bash
python -m pytest -q     # 69 tests, all passing
```

Tests include hand-computed references (S-shape 35.0 m on a 1-aisle
example, EOQ √(600000) = 774.5967, safety stock 73.5601 at 95%,
ABC on values 800/150/40/10), cross-checks (2-opt ≤ nearest neighbour,
total cost minimal at EOQ), and CLI smoke tests for every subcommand.

## License

MIT — see [LICENSE](LICENSE).
