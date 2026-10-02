# A4 staking rules on the baseline's bets, development data

Commit `715e417`. 2976 baseline 1X2 bets on 2972 matches. Mean claimed edge +5.35%, mean CLV +2.34%, shrink factor used 0.437. Bankroll starts at 100. 2000 bootstrap paths.

| Staking rule | Median final bankroll | 5th percentile final | Median worst drawdown | 95th percentile worst drawdown | Paths ending below the start | Actual order: final | Actual order: worst drawdown |
|---|---|---|---|---|---|---|---|
| flat 1 unit | 270.9 | 71.8 | 40.9% | 93.1% | 7% | 279.8 | 43.5% |
| quarter Kelly, claimed edge | 217.8 | 108.8 | 26.3% | 41.7% | 4% | 227.3 | 22.1% |
| quarter Kelly, shrunk edge, grouped | 143.7 | 106.2 | 12.4% | 20.7% | 3% | 146.4 | 10.0% |

Registered rule (smaller 95th-percentile drawdown and no lower median final bankroll than quarter Kelly on the claimed edge): fails
