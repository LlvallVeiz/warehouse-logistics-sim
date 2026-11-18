# Changelog

## 1.0.0 — 2026-11-18

Initial release.

- Layout: single-block warehouse (aisles, bins, depot), aisle-aware
  distances via front/back cross aisles, JSON load/save.
- Inventory: SKU model, ABC (Pareto) analysis, EOQ, safety stock and
  reorder point with z-scores from the target cycle service level.
- Slotting: cube-per-order index assignment and before/after evaluation
  of expected travel per pick.
- Orders: realistic generator — Zipf SKU popularity, right-skewed order
  sizes, seeded and replayable.
- Routing: S-shape, largest gap, return, nearest neighbour, 2-opt, all
  scored on the same waypoint/distance model.
- Picking: FIFO batch picking (order/line caps), zone splitting,
  same-orders strategy comparison.
- Simulation: discrete-event shift simulation with parallel pickers,
  stock decrement, stockouts, EOQ replenishment after lead time, and
  KPIs (pick rate, distance, cycle time, fill rate, utilisation, backlog).
- Reporting: Markdown + HTML reports, per-order CSV export, batch mode
  over several scenarios.
- CLI: `layout`, `inventory`, `abc`, `simulate`, `compare-strategies`,
  `report`, `batch`.
- Docs: `docs/RESEARCH.md` with checked sources; README with real run
  outputs.
- Tests: 69 pytest tests, all passing, including hand-computed
  references for routing distances, EOQ, safety stock and ABC classes.
