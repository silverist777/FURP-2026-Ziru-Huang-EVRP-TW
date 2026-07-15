# Four-Method Unlimited-Fleet Comparison

This comparison contains all 16 combinations of four methods and four instances. The c101_21 POMO run took about 108 minutes and was therefore executed and stored separately at [`../../../log/week5/c101-21-pomo/c101_21_pomo_repair.json`](../../../log/week5/c101-21-pomo/c101_21_pomo_repair.json). It is nevertheless part of this unlimited-fleet experiment group and is included in both [`summary.md`](summary.md) and [`overview.png`](overview.png).

For c101_21, POMO + repair produced a feasible solution with all 100 customers served, distance 4833, 79 vehicles, and runtime 6507.581 seconds. This result is valid under the earlier unlimited-fleet setting, but it would violate the later shared cap of 31 vehicles and therefore must not be copied into the vehicle-limited comparison.

[`best-route-petals.png`](best-route-petals.png) shows the minimum-distance checker-feasible route set for each instance. Customers are circles, charging stations are squares, the depot is a diamond, and every depot-to-depot vehicle route forms one petal. The selected methods are PyVRP for all four instances, with distances 248, 387, 350, and 1058 respectively.
