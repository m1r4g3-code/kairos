# A5 ratings model, development data

Commit `4dc2be8`. Market: Pinnacle pre-match, power de-vig, 1x2. Differences are log loss minus the market's on the same matches; positive means worse than the market.

| k | Matches | Model log loss | Market log loss |
|---|---|---|---|
| 0.02 | 93025 | 1.02178 | 1.00355 |
| 0.04 | 93025 | 1.02666 | 1.00355 |
| 0.08 | 93025 | 1.04677 | 1.00355 |

Chosen k: 0.02. Model minus market: +0.01823 (+0.01706 to +0.01940).

Log-pool weight on the model: **0.0000** (95% interval 0.0000 to 0.0096), 93025 matches.
Walk-forward blend minus market: +0.00000 (+0.00000 to +0.00000).
Weights by season (fitted on earlier seasons): 1314 0.000, 1415 0.000, 1516 0.000, 1617 0.000, 1718 0.000, 1819 0.000, 1920 0.000, 2021 0.000, 2122 0.000, 2223 0.000, 2324 0.000, 2425 0.000

Registered choice rule: killed on development data; holdout not read
