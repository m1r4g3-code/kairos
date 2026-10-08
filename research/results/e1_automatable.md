# E1: gap against Pinnacle on venues that allow automation

Commit 26eae57.

## E1a: Betfair Exchange pre-match price, development seasons

1752 matches carry both a Pinnacle and an exchange pre-match price. Bet where the price after commission beats Pinnacle's fair price by 3%.

| Commission | Bets | CLV | 95% interval | Return per bet | 95% interval |
|---|---|---|---|---|---|
| bfe[0% commission] | 248 | +1.3% | -0.7% to +3.5% | -3.2% | -30.4% to +26.2% |
| bfe[2% commission] | 114 | +1.8% | -1.7% to +5.4% | -6.6% | -51.2% to +44.4% |
| bfe[5% commission] | 37 | +0.9% | -6.9% to +9.4% | -54.7% | -100.0% to +22.3% |

## E1b: prices in the paper loop's snapshots

72 matches snapshotted between 3 and 8 October 2026 (six second-tier leagues). Counts of single prices beating Pinnacle's fair price. No liquidity information: an exchange price in the feed may have very little money behind it.

| Book | Commission assumed | Prices | Above fair | Above fair by 3% | Above fair after commission | By 3% after commission |
|---|---|---|---|---|---|---|
| matchbook | 4% | 213 | 42 | 8 | 9 | 2 |
| smarkets | 2% | 210 | 18 | 3 | 10 | 1 |
| betfair_ex_uk | 5% | 210 | 40 | 4 | 3 | 1 |
| betfair_ex_eu | 5% | 210 | 39 | 4 | 3 | 1 |
| williamhill | 0% | 210 | 1 | 0 | 1 | 0 |
| onexbet | 0% | 207 | 6 | 3 | 6 | 3 |
| betway | 0% | 195 | 1 | 0 | 1 | 0 |
