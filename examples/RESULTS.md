# Example results

All numbers below come from real runs of the code in this repository
(2026-11-18, seed 42 unless noted). Nothing here was typed by hand.

## Medium scenario — `examples/scenarios/medium.json`

8 aisles x 20 m, 3 m spacing, 12 slots/aisle (96 bins), 48 SKUs,
360 orders, 4 pickers, S-shape, batch up to 4 orders / 20 lines,
8-hour shift, 95% service level.

```text
$ warehouse-logistics-sim --scenario examples/scenarios/medium.json simulate
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

Stockouts by SKU (slow movers with only ~2 weeks of starting stock;
supplier lead times of 3–7 days cannot land inside one shift):

| SKU | Unfilled lines |
| --- | --- |
| HOME-008 | 5 |
| SPORT-003 | 4 |
| SPORT-004 | 3 |
| TOOL-004 | 2 |
| HOME-001 | 2 |
| FOOD-003 | 1 |
| SPORT-002 | 1 |
| ELEC-009 | 1 |
| APPAREL-007 | 1 |

### Routing comparison — same 360 orders, one route per order

```text
$ warehouse-logistics-sim --scenario examples/scenarios/medium.json compare-strategies
Strategy            Total dist (m)  Total time (min)  Avg dist/order (m)  Avg time/order (s)
two_opt                    24,367.7             899.2                67.7               149.9 *
nearest_neighbor           24,732.0             905.3                68.7               150.9
s_shape                    25,166.3             912.5                69.9               152.1
return                     25,439.7             917.1                70.7               152.8
largest_gap                25,571.3             919.3                71.0               153.2
* shortest total distance
```

2-opt beats S-shape by 3.2% — inside the ~5% band the literature
reports for the best heuristic vs the optimal route.

### ABC classification

```text
Class A:  18 SKUs,  81.1% of usage value
Class B:  16 SKUs,  14.3% of usage value
Class C:  14 SKUs,   4.6% of usage value
```

Top of the table: ELEC-001 (usage value 474,240.00, 17.6%),
ELEC-002 (450,240.00, 16.7%), ELEC-005 (205,440.00, 7.6%).

### Slotting (cube-per-order index)

```text
Slotting: expected travel/pick 20.62 m -> 8.63 m (+58.1%)
```

Closest assignments: ELEC-010 -> A01-S01 (0.8 m), HOME-008 ->
A01-S02 (2.5 m), ELEC-001 -> A02-S01 (3.8 m).

### EOQ example — ELEC-001

D = 12,000/yr, S = 55, H = 9.88/yr → EOQ = √(2·12000·55/9.88) =
365.5 units; safety stock (95%) = 61.0; reorder point = 192.5.
2 of 48 SKUs start the shift at or below their reorder point.

## Small scenario — `examples/scenarios/small.json`

4 aisles x 12 m, 24 bins, 24 SKUs (catalogue truncated to fit),
60 orders, 2 pickers, largest gap, seed 7.

```text
Strategy: largest_gap | pickers: 2 | shift: 480 min
Orders arrived:   60
Orders completed: 60
Orders backlogged: 0
Lines requested:  152
Lines filled:     152
Fill rate:        100.0%
Pick rate:        143.2 lines/picker-hour
Total distance:   1,344.0 m
Mean cycle time:  12.5 min
Picker utilisation: 6.6%
Units picked:     263
```

## Batch mode — `examples/scenarios/batch.json`

```text
Scenario                Strategy            Orders  Fill %  Pick rate  Distance (m) Cycle (min)
small-largest-gap       largest_gap             60  100.0%      143.2         1,344        12.5
medium-s-shape          s_shape                360   98.0%      139.6        11,843         6.7
medium-two-opt          two_opt                360   98.0%      148.2        10,373         6.4
```

## Tests

```text
$ python -m pytest -q
69 passed in 0.35s
```

## Generated files

- `examples/output/report.md` — full KPI + stockout + per-order tables
  and the routing comparison for the medium scenario.
- `examples/output/report.html` — the same report as a standalone page.
- `examples/output/simulation.csv` — one row per order (360 rows +
  header): arrival, start, finish, cycle time, lines filled, units,
  distance.
