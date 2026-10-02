# A3 cousin-market pricing, development data

Commit `715e417`. 183427 matches loaded. Differences are log loss of the derived price minus the bookmaker's own, on the same matches; positive means the derived price is worse.

| Test | Matches | Derived | Pinnacle's own | Bet365's own | Derived minus Pinnacle | Derived minus Bet365 | Mean gap to Pinnacle | Verdict |
|---|---|---|---|---|---|---|---|---|
| T1 over 2.5 from 1X2 only | 39399 | 0.68096 | 0.67599 | 0.67616 | +0.00497 (+0.00389 to +0.00604) | +0.00479 (+0.00369 to +0.00590) | 4.09 points | killed |
| T2 handicap (half lines) from 1X2 and total | 8966 | 0.69188 | 0.69139 | 0.69168 | +0.00049 (+0.00001 to +0.00097) | +0.00020 (-0.00038 to +0.00079) | 0.68 points | survives |
