# A1 on development data

Commit `dc71f36`. 183427 matches, 2976 baseline 1X2 bets, 13 of them with fewer than 3 other bookmakers (kept, not checkable).

| | Bets | Return per bet | 95% interval | CLV | 95% interval | Mean odds |
|---|---|---|---|---|---|---|
| All baseline bets | 2976 | +6.0% | -1.2 to +13.4 | +2.3% | +1.9 to +2.8 | 4.98 |
| gap limit 5%: kept | 1742 | +3.7% | -5.6 to +12.2 | +2.6% | +2.1 to +3.1 | 4.60 |
| gap limit 5%: flagged | 1234 | +9.4% | -2.3 to +21.4 | +2.0% | +1.3 to +2.8 | 5.51 |
| gap limit 5%: CLV kept minus flagged | | | | +0.5% | -0.4 to +1.4 | |
| gap limit 10%: kept | 2637 | +4.7% | -2.7 to +12.3 | +2.4% | +1.9 to +2.8 | 4.59 |
| gap limit 10%: flagged | 339 | +16.4% | -13.5 to +49.7 | +2.2% | +0.5 to +4.0 | 8.01 |
| gap limit 10%: CLV kept minus flagged | | | | +0.1% | -1.7 to +1.9 | |
| gap limit 15%: kept | 2852 | +5.4% | -1.4 to +12.3 | +2.4% | +2.0 to +2.8 | 4.72 |
| gap limit 15%: flagged | 124 | +21.8% | -38.5 to +90.9 | +0.7% | -2.6 to +4.0 | 10.93 |
| gap limit 15%: CLV kept minus flagged | | | | +1.7% | -1.4 to +4.9 | |

## Reference forecasts (92178 matches)

| Forecaster | Log loss | Brier | Calibration error | Log loss minus Pinnacle alone | 95% interval |
|---|---|---|---|---|---|
| pinnacle_alone | 1.0037 | 0.6005 | 0.12% | - | - |
| others_median[excl B365] | 1.0042 | 0.6008 | 0.15% | +0.00050 | +0.00031 to +0.00068 |
| checked_blend[r=5%] | 1.0038 | 0.6005 | 0.12% | +0.00006 | -0.00002 to +0.00014 |
| checked_blend[r=10%] | 1.0037 | 0.6005 | 0.13% | +0.00001 | -0.00003 to +0.00005 |
| checked_blend[r=15%] | 1.0037 | 0.6005 | 0.12% | +0.00000 | -0.00003 to +0.00003 |

Registered choice rule picks: none
