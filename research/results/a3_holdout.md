# A3 cousin-market pricing, holdout data

Commit `99a42d3`. 13575 matches loaded. Differences are log loss of the derived price minus the bookmaker's own, on the same matches; positive means the derived price is worse.

| Test | Matches | Derived | Pinnacle's own | Bet365's own | Derived minus Pinnacle | Derived minus Bet365 | Mean gap to Pinnacle | Verdict |
|---|---|---|---|---|---|---|---|---|
| T2 handicap (half lines) from 1X2 and total | 2134 | 0.69256 | 0.69264 | 0.69203 | -0.00007 (-0.00089 to +0.00074) | +0.00053 (-0.00056 to +0.00163) | 0.57 points | survives |
