# Sub-protocol — value-scan.md (L15)

> Convert "who wins" into "is there a bet." Being right is not enough — the edge must beat the de-vigged price. Most selections on most slips are **not** value; that is normal and correct.

## The calculation (done by `engine/kelly.py`, audited here)

For each selection:
```
my_prob     = model probability (from the score matrix)
fair_prob   = de-vigged market probability (engine/market.py)
edge        = my_prob - fair_prob
EV per unit = my_prob * decimal_odds - 1
```
A selection is **value** only if `EV >= +3%` (default `MIN_EDGE`) **and** confidence ≥ floor.

## Ranking
Rank candidate bets by **EV**, then by edge, then by confidence. Present the best one as the headline; list runners-up only if they're independent (not the same outcome via another market).

## The "suspect myself first" rule (critical)
A *large* edge is more often a mistake than a gift:
1. If my prob diverges hugely from the de-vigged market, **stop** and ask why.
2. Did the market already price team news I missed (late injury, rotation, a drifting line)? → re-enrich (L4/L10).
3. Is my λ off (wrong league baseline, double-counted a modifier)? → re-check the spec.
4. Only after ruling those out is it a genuine value bet. The market is sharp; respect it.

## Market-specific notes
- **1X2:** the bread-and-butter; watch the draw — engines that under/over-rate draws bleed money here.
- **Double Chance / DNB:** lower variance, lower odds; value is rarer because the vig compounds. Useful for high-confidence-but-low-edge spots.
- **O/U & BTTS:** driven by total λ and the goal environment (`tactics-playbook.md`, weather). Often more beatable than 1X2 because casual money distorts them.
- **Correct score / handicaps:** high overround — demand a bigger edge or skip.
- **High-overround markets:** raise the effective edge threshold; the price is stacked against me.

## Output of this step
A ranked value table:
```
market   selection  odds   my%   fair%  edge   EV     -> verdict
1x2      home       2.10   55.0  47.6   +7.4   +15.5% -> VALUE
ou_2.5   over       1.95   48.0  51.3   -3.3   -6.4%  -> no
btts     yes        1.80   58.0  55.6   +2.4   +4.4%  -> thin (below 3%? -> pass)
```
Hand the value rows to the contradiction gate (`contradiction-check.md`) before they become recommendations.
