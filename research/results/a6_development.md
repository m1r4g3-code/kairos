# A6 ratings model, development data

Commit `4dc2be8`. Market: Pinnacle pre-match, power de-vig, ou25. Differences are log loss minus the market's on the same matches; positive means worse than the market.

| k | Matches | Model log loss | Market log loss |
|---|---|---|---|
| 0.02 | 39469 | 0.70346 | 0.67595 |
| 0.04 | 39469 | 0.71830 | 0.67595 |
| 0.08 | 39469 | 0.77432 | 0.67595 |

Chosen k: 0.02. Model minus market: +0.02751 (+0.02511 to +0.02990).

Log-pool weight on the model: **0.0176** (95% interval 0.0000 to 0.0586), 39469 matches.
Walk-forward blend minus market: +0.00003 (-0.00008 to +0.00015).
Weights by season (fitted on earlier seasons): 2021 0.039, 2122 0.048, 2223 0.048, 2324 0.051, 2425 0.021

Bets at Bet365's over/under price where model probability x price - 1 > 3%:

| | Bets | Return per bet | 95% interval | CLV | 95% interval | Mean odds |
|---|---|---|---|---|---|---|
| Model bets | 30310 | -5.1% | -6.3 to -4.0 | -4.5% | -4.6 to -4.5 | 1.99 |

Registered choice rule: killed on development data; holdout not read
