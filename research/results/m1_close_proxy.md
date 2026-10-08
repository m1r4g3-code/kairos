# M1: closing-price proxies against Pinnacle's close

Development seasons, 183427 matches, commit 7bbb37c+dirty. 1X2 bets, power de-vig.

## B0 (Bet365 +3%)

2976 bets, 2889 with a Pinnacle close.

| Proxy close | Bets with both | CLV by proxy | CLV by Pinnacle | Proxy minus Pinnacle | 95% interval | Correlation | Per-bet error (RMSE) | Same sign | Passes |
|---|---|---|---|---|---|---|---|---|---|
| Avg | 1130 | +1.12% | +1.88% | -0.76% | -0.97% to -0.56% | 0.957 | 3.60 pts | 88.9% | no |
| B365 | 1129 | -3.21% | +1.88% | -5.09% | -5.50% to -4.68% | 0.852 | 8.67 pts | 70.3% | no |
| BFE | 9 | -5.93% | -5.85% | -0.07% | -3.63% to +3.48% | 0.939 | 5.13 pts | 100.0% | yes |

## best of books +3%

9269 bets, 9008 with a Pinnacle close.

| Proxy close | Bets with both | CLV by proxy | CLV by Pinnacle | Proxy minus Pinnacle | 95% interval | Correlation | Per-bet error (RMSE) | Same sign | Passes |
|---|---|---|---|---|---|---|---|---|---|
| Avg | 2518 | +3.06% | +3.74% | -0.68% | -0.82% to -0.54% | 0.965 | 3.58 pts | 91.3% | no |
| B365 | 2516 | +1.30% | +3.75% | -2.44% | -2.71% to -2.17% | 0.881 | 7.39 pts | 79.6% | no |
| BFE | 156 | +2.58% | +2.69% | -0.12% | -0.60% to +0.37% | 0.950 | 3.11 pts | 93.6% | yes |
