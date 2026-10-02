# Phase 3: engine improvements log

Started 2026-10-02 on branch `dev/phase-3-engine`. One entry per proposal from
`docs/research.md`, in ranked order. The pre-registered specification and the
full result for each are in `research/hypotheses.md`; the tables are in
`research/results/`. An improvement is merged only if it passes on the holdout.

## Summary so far

| Proposal | Outcome | Holdout read? |
|---|---|---|
| Preconditions: audit section 5a defects | Fixed, with tests | no |
| A1 Checked sharp reference (skip bets where Pinnacle stands alone) | **Dropped** on development data | no |
| A2 De-vig bake-off (proportional, power, Shin) | **No change**: power, the current method, is best | no |
| A3 Price cousin markets from the sharp line | **Merged** for handicaps from 1X2 + total; **killed** for totals from 1X2 alone | yes, once |
| A4 Same-match exposure and Kelly shrinkage | Exposure fix shipped; shrinkage **dropped** | no |
| A5 Fitted ratings blended with the market | Not started (see questions) | |
| A6 Shot-and-corner ratings for totals | Not started | |
| A7 Calibration layer | Only relevant if A5 or A6 survives | |

The betting baseline (B0) is unchanged by anything merged so far: no merged item
alters which 1X2 or over/under 2.5 bets Kairos v2 selects. B0's holdout numbers
have still not been computed.

## Preconditions: defects from the audit

| Audit item | Fix | Test added |
|---|---|---|
| 5a #2 unbounded modifiers | A modifier outside 0.80–1.20 is rejected | yes |
| 5a #3 results for unknown or duplicate ids | Refused; a correction must be marked; the latest result per id counts once | yes |
| 5a #4 quarter lines priced as half lines | `poisson.over_under` refuses them; `derive.py` settles them correctly | yes |
| 5a #5 Monte Carlo ignored rho and inflated goals | Same rho as the analytic engine; mean-preserving noise; agreement is checked in every run | yes |
| 5a #6 home advantage counted twice | Understat spec no longer adds a second home boost | yes |
| 5a #7 de-vig accepted odds ≤ 1 | Rejected; the solver checks its bracket | yes |
| 5a #8 Elo floor broke the total | Total is preserved | yes |
| 5a #9 lone soft book treated as a reference | A consensus needs 3 books; the others' median is reported beside Pinnacle | yes |
| 5a #10 "speculative" rows still marked as bets | A fragile candidate has no stake and is not a bet; every candidate is tested | yes |
| 5a #11 same-match bets sized independently | One match is one position, capped at 5% | yes |
| 5b cache name ignored the market | Totals and spreads get their own cache file | |
| 5b `find_event` picked the wrong game | Accents folded; an ambiguous hint raises an error | yes |
| 5b `MIN_EDGE` defined twice | One definition | |

Also added, as the brief requires: `run.py` reports the raw (pre-judgment)
distribution beside the adjusted one, each value-table row carries `raw_prob`,
and `ledger.py` scores raw against adjusted probabilities on picks that log
both. No pick in the ledger has both yet.

## A1. Checked sharp reference — dropped

**Before:** 2,976 baseline 1X2 bets, CLV +2.3% (+1.9 to +2.8).
**Tested:** skip a bet when Pinnacle's fair probability exceeds the median of the
other bookmakers' by more than 5%, 10% or 15%.

| Gap limit | Bets flagged | CLV kept | CLV flagged | Kept minus flagged |
|---|---|---|---|---|
| 5% | 1,234 | +2.6% | +2.0% | +0.5% (−0.4 to +1.4) |
| 10% | 339 | +2.4% | +2.2% | +0.1% (−1.7 to +1.9) |
| 15% | 124 | +2.4% | +0.7% | +1.7% (−1.4 to +4.9) |

No interval excludes zero, so by the rule written beforehand the gate is dropped
and the holdout was not read. Flagged bets were not worse bets. The other books'
median is a worse forecast than Pinnacle alone (log loss +0.0005).

**After:** no change to bet selection. The defect fix (no reference from fewer
than three soft books) stays, and `edge.sharp_fair` now returns the others'
median so a session can see when Pinnacle stands alone.

## A2. De-vig bake-off — no change

Log loss on 93,025 Pinnacle pre-match 1X2 prices: power 1.00355, Shin 1.00360,
proportional 1.00380. Against power: Shin +0.00005 (+0.00002 to +0.00009),
proportional +0.00025 (+0.00014 to +0.00035). Power also led on closing prices
and on over/under. The differences sit entirely in markets with a price of 10 or
more. Power stays the default; Shin is available.

## A3. Cousin markets from the sharp line — merged in part

**Before:** the engine could not price a quarter line or an Asian handicap, and
returned the same probability for over 2.25, 2.5 and 2.75.

**After:** `engine/derive.py` fits expected goals to Pinnacle's prices and
settles any goal line or handicap correctly.

| Test | Data | Matches | Derived minus Bet365's own (log loss) | Derived minus Pinnacle's own | Verdict |
|---|---|---|---|---|---|
| Over 2.5 from 1X2 alone | development | 39,399 | +0.00479 (+0.00369 to +0.00590) | +0.00497 | killed |
| Handicap (half lines) from 1X2 + over 2.5 | development | 8,966 | +0.00020 (−0.00038 to +0.00079) | +0.00049 (+0.00001 to +0.00097) | survives |
| Handicap (half lines) from 1X2 + over 2.5 | **holdout** | 2,134 | +0.00053 (−0.00056 to +0.00163) | −0.00007 (−0.00089 to +0.00074) | survives |

How to read it: the fitted handicap price is about as accurate as a bookmaker's
own. It differs from Pinnacle's own probability by about 0.6 points on average.
That is more than 1% of expected value at even money, so a small gap between a
soft book's handicap price and the derived price is **not** evidence of value.
Use the derived price to rule bets out and to require a larger margin, not to
claim thin edges.

Limits: only half-line handicaps were tested against results. Quarter and whole
lines, other goal lines, double chance and draw-no-bet are checked by arithmetic
in unit tests. No betting test was run on derived prices.

## A4. Staking — exposure fix shipped, shrinkage dropped

Bankroll paths over the 2,976 development bets, starting from 100:

| Rule | Median final bankroll | 95th-percentile worst drawdown |
|---|---|---|
| Flat 1 unit | 270.9 | 93.1% |
| Quarter Kelly on the claimed edge | 217.8 | 41.7% |
| Quarter Kelly on the shrunk edge (×0.437), grouped by match | 143.7 | 20.7% |

Shrinking cut the drawdown and the growth, so it failed "no loss of median
growth" and was not taken to the holdout. These paths assume the historical
Bet365 edge; they are not a forecast for SportyBet.

One thing for the owner: flat stakes of 1% of the starting bankroll on bets
averaging odds near 5 gave a one-in-twenty chance of losing 93% of the peak
bankroll at some point, in a history where the average return was positive.

## What is not done yet

- A5, A6, A7.
- Separating the staking, ledger and paper-trading code from the football code
  into its own package (required by the brief before Phase 4).
- B0 on the holdout.
- The model path (`run.py`) has never been backtested: its inputs are set by
  judgment per match, so there is no history to replay.
