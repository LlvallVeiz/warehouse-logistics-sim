# Warehouse simulation — medium-warehouse-demo

Strategy: **s_shape** · Pickers: 4 · Shift: 480 min · Batch: up to 4 orders / 20 lines

## Key performance indicators

| KPI | Value |
| --- | --- |
| Orders arrived | 360 |
| Orders completed | 360 |
| Orders backlogged | 0 |
| Lines requested | 998 |
| Lines filled | 978 |
| Fill rate | 98.0% |
| Pick rate (lines / picker-hour) | 139.56 |
| Total distance (m) | 11,843.33 |
| Mean order cycle time (min) | 6.71 |
| Picker utilisation | 21.9% |
| Units picked | 1,653 |

## Stockouts

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

## Per-order results (first 20)

| Order | Arrival (min) | Start | Finish | Cycle (min) | Lines filled | Distance (m) |
| --- | --- | --- | --- | --- | --- | --- |
| ORD-00197 | 1.14 | 8.19 | 12.69 | 11.56 | 2/2 | 30.50 |
| ORD-00156 | 3.20 | 8.19 | 12.69 | 9.50 | 3/3 | 30.50 |
| ORD-00212 | 7.09 | 8.19 | 12.69 | 5.60 | 2/2 | 30.50 |
| ORD-00272 | 8.19 | 8.19 | 12.69 | 4.50 | 4/4 | 30.50 |
| ORD-00130 | 9.44 | 24.87 | 29.21 | 19.76 | 2/2 | 30.08 |
| ORD-00003 | 11.93 | 24.87 | 29.21 | 17.28 | 4/4 | 30.08 |
| ORD-00106 | 14.03 | 24.87 | 29.21 | 15.18 | 1/1 | 30.08 |
| ORD-00046 | 24.87 | 24.87 | 29.21 | 4.34 | 3/3 | 30.08 |
| ORD-00002 | 25.32 | 27.03 | 30.36 | 5.04 | 1/1 | 20.92 |
| ORD-00254 | 26.08 | 27.03 | 30.36 | 4.28 | 2/2 | 20.92 |
| ORD-00140 | 26.53 | 27.03 | 30.36 | 3.83 | 2/2 | 20.92 |
| ORD-00077 | 27.03 | 27.03 | 30.36 | 3.33 | 2/2 | 20.92 |
| ORD-00030 | 27.50 | 30.94 | 37.65 | 10.15 | 10/10 | 49.67 |
| ORD-00295 | 29.97 | 30.94 | 37.65 | 7.67 | 3/3 | 49.67 |
| ORD-00217 | 30.62 | 30.94 | 37.65 | 7.03 | 3/3 | 49.67 |
| ORD-00281 | 30.94 | 30.94 | 37.65 | 6.71 | 2/2 | 49.67 |
| ORD-00240 | 31.77 | 34.08 | 38.88 | 7.12 | 2/2 | 35.08 |
| ORD-00105 | 32.19 | 34.08 | 38.88 | 6.69 | 2/2 | 35.08 |
| ORD-00205 | 33.02 | 34.08 | 38.88 | 5.86 | 6/6 | 35.08 |
| ORD-00207 | 34.08 | 34.08 | 38.88 | 4.81 | 1/1 | 35.08 |

# Routing strategy comparison

Same 360 orders routed with each heuristic (identical cost model).

| Strategy | Total distance (m) | Total time (min) | Avg distance/order (m) | Avg time/order (s) |
| --- | --- | --- | --- | --- |
| two_opt **(shortest)** | 24,367.67 | 899.19 | 67.69 | 149.87 |
| nearest_neighbor | 24,732.00 | 905.27 | 68.70 | 150.88 |
| s_shape | 25,166.33 | 912.51 | 69.91 | 152.08 |
| return | 25,439.67 | 917.06 | 70.67 | 152.84 |
| largest_gap | 25,571.33 | 919.26 | 71.03 | 153.21 |
