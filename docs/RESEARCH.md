# Research notes — warehouse-logistics-sim

How the warehouse science in this package was chosen, what each formula
is, and where it comes from. Every claim below is tied to a source that
was actually checked during this build (2026-11-18); nothing is cited
from memory alone. Where a textbook is cited without a URL, the edition
and chapter are given so the claim can be checked in print.

## 1. Why order picking dominates warehouse cost

Order picking — retrieving items from storage to satisfy customer orders
— is the most labour-intensive warehouse activity. De Koster, Le-Duc &
Roodbergen (2007) put its cost at "as much as 55% of the total warehouse
operating expense" and review the four design/control decisions that
drive it: layout, storage assignment (slotting), routing, and order
batching/zoning. This package implements all four, which is why the
simulation, the routing comparison and the slotting evaluation exist as
separate components instead of one hard-coded heuristic.

Source: de Koster, R., Le-Duc, T. & Roodbergen, K. J., "Design and control
of warehouse order picking: A literature review", *European Journal of
Operational Research* 182(2), 2007, pp. 481–501.
https://doi.org/10.1016/j.ejor.2006.07.009

## 2. Layout: single-block warehouse with two cross aisles

The layout model is the standard one in the picking literature: parallel
aisles served by a front and a back cross aisle, with the depot (packing /
shipping) on the front cross aisle. Travel distance between two points is
the shorter of the front-cross-aisle route and the back-cross-aisle route,
or a straight walk when both points share an aisle. This is the same
geometry the ERIM "Calc. Order Picking Time" tool uses for its routing
strategies.

Source: Erasmus Research Institute of Management (ERIM), Material
Handling Forum, "Routing strategies".
https://www.erim.eur.nl/material-handling-forum/research-education/tools/calc-order-picking-time/what-to-do/routing-strategies/

## 3. Routing heuristics: S-shape, largest gap, return, optimal

* **S-shape (traversal):** every aisle with picks is traversed entirely,
  alternating entry ends, so the route snakes through the warehouse.
  Best when the number of picks per aisle is high.
* **Largest gap:** in each aisle the picker skips the largest gap —
  between two adjacent picks, or between a pick and a cross aisle — and
  enters from one or both ends accordingly. Best when picks per aisle
  are few. The last aisle is traversed entirely.
* **Return:** the picker enters each aisle from the front, walks to the
  farthest pick, and returns to the front.
* **Optimal:** the shortest possible route; Ratliff & Rosenthal (1983)
  showed it is solvable in polynomial time for a rectangular warehouse,
  and it typically looks like a mixture of S-shape and largest gap.

The literature reports that the best heuristic is on average about 5%
over the optimal solution (de Koster et al. 2007, citing Hall 1993 and
Petersen 1997). This package does not implement the Ratliff–Rosenthal
optimal algorithm; instead it offers **nearest neighbour** plus a
**2-opt** improvement (Lin & Kernighan 1973) as the near-optimal
reference: on the medium demo scenario 2-opt beats S-shape by 3.2% in
total distance (24,367.7 m vs 25,166.3 m), which is consistent with that
~5% band.

Sources: ERIM, "Short explanation on routing strategies".
https://www.erim.eur.nl/material-handling-forum/research-education/tools/calc-order-picking-time/what-to-do/short-explanation-on-routing-strategies/
Ratliff, H. D. & Rosenthal, A. S., "Order-picking in a rectangular
warehouse: a solvable case of the traveling salesman problem",
*Operations Research* 31(3), 1983, pp. 507–521.
https://doi.org/10.1287/opre.31.3.507
Lin, S. & Kernighan, B. W., "An effective heuristic algorithm for the
traveling-salesman problem", *Operations Research* 21(2), 1973,
pp. 498–516.
Roodbergen, K. J. & de Koster, R., "Routing order pickers in a warehouse
with a middle aisle", *European Journal of Operational Research*, 1998
(as cited in de Koster et al. 2007).

## 4. ABC analysis (Pareto)

ABC classifies SKUs by annual usage value (annual demand x unit cost),
sorted descending: class A is the first 80% of cumulative value, B the
next 15% (up to 95%), C the rest. The 80/20 pattern behind it is the
Pareto principle: a small share of SKUs carries most of the value — the
usual textbook split is ~20% of SKUs / ~80% of value for A, ~30% / ~15%
for B, ~50% / ~5% for C. The demo catalogue reproduces this closely:
18 of 48 SKUs (37.5%) hold 81.1% of value in class A, 16 hold 14.3% in
B, 14 hold 4.6% in C — the A share is wider than the textbook 20%
because the demo demand curve is Zipf with exponent 1, not because the
rule differs.

Sources: Pareto, V., *Cours d'économie politique*, 1896 (Pareto
principle); Northline Logistics, "Inventory Optimization: ABC Analysis
in Modern Distribution", 2025.
https://www.northlinelogic.com/blog/inventory-optimization-abc-analysis
Helm WMS, "ABC Analysis — Key Industry Terms".
https://helmwms.com/glossary/abc-analysis

## 5. EOQ, safety stock, reorder point

* **EOQ (Harris 1913, also called the Wilson formula):**
  Q\* = sqrt(2·D·S / H), with D = annual demand, S = ordering cost per
  order, H = holding cost per unit per year. It minimises the annual
  variable cost (D/Q)·S + (Q/2)·H. Assumptions: constant known demand,
  constant lead time, no quantity discounts, full deliveries.
* **Safety stock:** SS = z · sqrt(L·σd² + d²·σL²), with d = mean daily
  demand, σd = daily demand standard deviation, L = mean lead time
  (days), σL = lead-time standard deviation, z = standard-normal
  quantile of the target cycle service level (1.645 for 95%, 2.326
  for 99%). With constant lead time this reduces to z·σd·sqrt(L).
* **Reorder point:** ROP = d·L + SS.

Sources: Harris, F. W., "How many parts to make at once", *Factory, The
Magazine of Management* 10(2), 1913, pp. 135–136; Silver, E. A., Pyke,
D. F. & Peterson, R., *Inventory Management and Production Planning and
Scheduling*, 3rd ed., Wiley, 1998 (EOQ, safety stock and reorder-point
theory); Cleverence, "Guide: inventory model formulas (EOQ, safety
stock, reorder point)" (formula cross-check).
https://www.cleverence.com/articles/for-business/inventory-model-formulas-5827/

## 6. Slotting and the cube-per-order index (COI)

Slotting puts fast movers near the depot. The cube-per-order index
ranks SKUs by unit volume divided by annual picks: a small item picked
often belongs close to the depot; a bulky item picked rarely belongs
far away. Minimising the pick-weighted distance to the depot is the
accepted objective for manual picking slotting; the standard treatment
is in Tompkins et al., *Facilities Planning* (4th ed., Wiley, 2010),
ch. 6–7 (warehouse layout, storage and order picking). The package
quantifies the gain instead of asserting it: on the medium demo
scenario COI slotting cuts expected travel per pick from 20.62 m
(random placement) to 8.63 m — a 58.1% improvement.

Source: Tompkins, J. A., White, J. A., Bozer, Y. A. & Tanchoco, J. M. A.,
*Facilities Planning*, 4th ed., Wiley, 2010.

## 7. Order profiles: Zipf popularity and right-skewed order sizes

Real order lines are heavily skewed: a few SKUs appear in most orders
and most orders are small. The generator uses a Zipf distribution over
SKUs ranked by annual demand (probability proportional to 1/rank) and a
right-skewed order-size distribution (mode 2 lines, tail to 12). Zipf's
law is the standard model for such rank-frequency skew.

Source: Zipf, G. K., *Human Behavior and the Principle of Least Effort*,
Addison-Wesley, 1949.

## 8. Batch and zone picking

Batch picking groups several orders into one tour, amortising depot
travel over more lines; zone picking splits an order by aisle zone so
zones are picked in parallel. Both are standard operating policies
reviewed in de Koster et al. (2007, §5–6). The simulation batches FIFO
up to a configurable order/line cap; zone splitting is provided as a
library function and exercised in tests.

## 9. Validation strategy

* **Hand-computed values:** S-shape route on a 1-aisle example = 35.0 m
  (2.5 + 15 + 17.5); 2-aisle S-shape = 50.0 m; largest-gap 2-aisle =
  55.0 m (all derived step by step in `tests/test_routing.py`).
  EOQ for D=12000, S=50, H=2 is sqrt(600000) = 774.5967, and the total
  annual cost at EOQ is 1549.1934, lower than at Q/2 or 2Q.
  Safety stock for d=100/day, σd=20, L=5 days at 95% is 73.5601 and
  ROP is 573.5601. ABC on values 800/150/40/10 gives A={800}, B={150},
  C={40, 10}.
* **Cross-checks:** 2-opt never returns a longer tour than nearest
  neighbour (asserted on random pick sets); total annual cost is minimal
  at EOQ; simulation with ample stock has fill rate 1.0, with zero stock
  has fill rate 0.0; the same seed reproduces identical KPIs.
* **Consistency:** every strategy is compared on the same waypoint /
  distance model (`layout.path_distance`), so the strategy comparison
  cannot favour one heuristic through a different cost function.
* **Limits of the model (honest):** single-block layout only (no middle
  cross aisle); no congestion or picker blocking; travel speed and pick
  times are constant; replenishment lead times are in whole days, so
  supplier lead times longer than a shift never land inside the shift;
  the "optimal" reference is 2-opt, not the Ratliff–Rosenthal exact
  algorithm.

## References

1. de Koster, R., Le-Duc, T. & Roodbergen, K. J. "Design and control of
   warehouse order picking: A literature review." *European Journal of
   Operational Research* 182(2), 2007, pp. 481–501.
   https://doi.org/10.1016/j.ejor.2006.07.009
2. Erasmus Research Institute of Management (ERIM), Material Handling
   Forum. "Routing strategies."
   https://www.erim.eur.nl/material-handling-forum/research-education/tools/calc-order-picking-time/what-to-do/routing-strategies/
3. ERIM, Material Handling Forum. "Short explanation on routing strategies."
   https://www.erim.eur.nl/material-handling-forum/research-education/tools/calc-order-picking-time/what-to-do/short-explanation-on-routing-strategies/
4. Ratliff, H. D. & Rosenthal, A. S. "Order-picking in a rectangular
   warehouse: a solvable case of the traveling salesman problem."
   *Operations Research* 31(3), 1983, pp. 507–521.
   https://doi.org/10.1287/opre.31.3.507
5. Lin, S. & Kernighan, B. W. "An effective heuristic algorithm for the
   traveling-salesman problem." *Operations Research* 21(2), 1973,
   pp. 498–516.
6. Roodbergen, K. J. & de Koster, R. "Routing order pickers in a
   warehouse with a middle aisle." *European Journal of Operational
   Research*, 1998.
7. Harris, F. W. "How many parts to make at once." *Factory, The
   Magazine of Management* 10(2), 1913, pp. 135–136.
8. Silver, E. A., Pyke, D. F. & Peterson, R. *Inventory Management and
   Production Planning and Scheduling.* 3rd ed., Wiley, 1998.
9. Tompkins, J. A., White, J. A., Bozer, Y. A. & Tanchoco, J. M. A.
   *Facilities Planning.* 4th ed., Wiley, 2010.
10. Pareto, V. *Cours d'économie politique.* 1896.
11. Zipf, G. K. *Human Behavior and the Principle of Least Effort.*
    Addison-Wesley, 1949.
12. Northline Logistics. "Inventory Optimization: ABC Analysis in Modern
    Distribution." 2025.
    https://www.northlinelogic.com/blog/inventory-optimization-abc-analysis
13. Helm WMS. "ABC Analysis — Key Industry Terms."
    https://helmwms.com/glossary/abc-analysis
14. Cleverence. "Guide: inventory model formulas (EOQ, safety stock,
    reorder point)."
    https://www.cleverence.com/articles/for-business/inventory-model-formulas-5827/
