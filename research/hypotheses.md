# Hypothesis register

Every strategy variant is written here **before** it is run. Every run is appended
to `research/runs.jsonl` by the harness, including the ones that fail. Nothing is
deleted from either file.

Rules:

1. An entry states what is run, on which data, what result is expected, and what
   result would kill it.
2. Development data only (`research/holdout.json`) until a variant is finished
   and frozen. A holdout read is logged in `research/holdout_access.jsonl`.
3. The three measures, in order: closing-line value (CLV), return per bet with a
   95% interval, calibration (log loss, Brier, buckets). Hit rate is not a measure.
4. CLV = price taken x Pinnacle's closing probability with the margin removed
   (power method) - 1. The proportional-method figure is recorded beside it.

---

## Phase 2 entries (written 2026-10-02, before the first harness run)

### B0. Baseline: Kairos v2 as shipped
- **What:** `edge.sharp_fair` on Pinnacle's pre-match price (power de-vig), then
  `edge.value_vs_sharp` against one soft bookmaker (Bet365), threshold +3%
  (`config.MIN_EDGE`), one unit flat. Markets: 1X2 and over/under 2.5 goals.
  Both prices come from the same Football-Data collection (Friday or Tuesday
  afternoon). Bet365 stands in for the owner's single SportyBet account.
- **Data:** every development league-season that has Pinnacle pre-match and
  closing prices.
- **Forecast under test:** Pinnacle pre-match, power de-vig (the "sharp fair
  probability" Kairos reports).
- **Expected:** very few bets (the Phase 0 diagnostic found 0.3% of outcomes at
  +2% on ten league-seasons). CLV interval includes zero or sits below it.
  Return-per-bet interval far too wide to conclude anything. Forecast is well
  calibrated but slightly worse than the closing price.
- **This is the reference.** It is not tuned. Later variants are compared to it.

### R1. Reference forecasts (no bets)
- Bet365 pre-match, proportional de-vig. Market average (`Avg`) pre-match,
  proportional de-vig. Pinnacle closing, power de-vig (a bar, not a strategy).
- **Expected:** log loss ordering closing < Pinnacle pre-match < average < Bet365,
  with small gaps.

### S1. Threshold sensitivity, one soft book
- **What:** B0 at thresholds 0%, 2% and 5% (B0 itself is 3%).
- **Expected:** bet count falls quickly with the threshold; CLV does not improve
  with the threshold (a bigger gap between Bet365 and Pinnacle at the same moment
  is more likely a stale or mistaken Bet365 price that Pinnacle has not followed,
  or a Pinnacle move Bet365 has not followed; the data will say which).
- **Purpose:** description only. No threshold is chosen from this.

### S2. Best price among named soft bookmakers
- **What:** B0 with the soft price replaced by the best price across every named
  bookmaker in the file (no Pinnacle, no exchange, no Max/Avg columns), at
  thresholds 0%, 2%, 3% and 5%.
- **Why:** the published results (Kaunitz et al., Buchdahl) come from taking the
  best of many bookmakers. This measures how much of the effect needs many books.
- **Expected:** many more bets than B0. CLV at or slightly above zero. Return per
  bet positive in early seasons and weaker in recent ones. Not predicted with
  confidence.
- **Caveat known in advance:** the set of named bookmakers in the files changes
  over the years, and a best-of-several price cannot be taken by someone with
  one account. This is a ceiling, not a plan.
- **Purpose:** description only. Nothing is selected from this in Phase 2.

---

## Added 2026-10-02 after the first full baseline run

The B0 prediction above was wrong: across 22 leagues and 12 to 13 seasons the
baseline placed 2,976 1X2 bets with CLV above zero (`research/results/baseline_tables.md`).
The three entries below only cut the same B0 1X2 bets into groups. They are
written after seeing the per-league and per-season tables, so they are **post hoc
descriptions**, not tests, and nothing is selected from them.

### S3. B0 bets by size of the claimed edge
- **What:** B0 1X2 bets grouped by claimed EV: 3-5%, 5-10%, 10-15%, 15%+.
- **Why:** CLAUDE.md's rule "a huge edge is a bug". A data error or a stale price
  shows up as a large claimed edge.
- **Expected:** CLV rises with the band up to about 10%. Above 15% the return per
  bet is no better, or worse, than in the lower bands.

### S4. B0 bets by league group and era
- **What:** (a) E0, SP1, D1, I1, F1 against the other 17 leagues; (b) first-tier
  leagues against lower tiers; (c) seasons 1213-1718 against 1819-2425.
  Also the share of outcomes that qualify in each group.
- **Expected:** CLV near zero in the five big leagues and positive elsewhere
  (already visible league by league). No confident prediction on era.

### S5. B0 bets by price taken
- **What:** odds under 2.5, 2.5-5, 5-10, 10 and over. CLV by both de-vig methods.
- **Why:** the bets average odds near 5. If the result lives only in longshots it
  leans on the de-vig method being right in the tail.
- **Expected:** most bets and most of the CLV at odds above 5; the two de-vig
  methods disagree most there.

---

## Phase 3 entries

### A1. Checked sharp reference (written 2026-10-02, before any A1 run)

**Idea (docs/research.md, proposal A1).** A bet is suspect when Pinnacle stands
alone: Pinnacle rates the selection clearly more likely than the other
bookmakers do. That was the shape of the Craiova and Shamrock mirages.

**Definitions.**
- Start from the B0 1X2 bets (Bet365 against Pinnacle pre-match, +3%).
- *Others* = named soft bookmakers in the file other than Bet365 (no Pinnacle, no
  exchange, no Max/Avg). At least 3 are needed; with fewer the bet is "unchecked"
  and is kept.
- *Gap* = Pinnacle fair probability for the selection / median of the others'
  fair probabilities (each de-vigged by the power method) - 1.
- *Gate G(r)*: skip the bet when gap > r. Grid, fixed now: r = 5%, 10%, 15%.
- *Checked blend forecast*: Pinnacle's fair probabilities, except when any
  selection's gap is beyond +/- r, in which case the normalised geometric mean
  of Pinnacle and the others' median.

**Development analysis.** For each r: bets, CLV and return of kept and flagged
bets, and the CLV difference (kept minus flagged) with a match-clustered
bootstrap interval. Log loss of Pinnacle alone, the others' median alone, and
the checked blend, on matches with at least 3 others.

**Choice rule on development data.** Take the largest r whose flagged group has
at least 30 bets and whose CLV difference interval lies wholly above zero. If no
r qualifies, A1's gate is dropped here and the holdout is not read for it.

**Holdout rule (only if an r was chosen).** Merge the gate only if, on the
holdout, the CLV difference interval lies wholly above zero and the checked
blend's log loss is not worse than Pinnacle alone (the interval of the
difference does not lie wholly above zero). The B0 holdout numbers are computed
in the same run.

**Expected.** Not confident. Two stories pull opposite ways. If Pinnacle alone
means Pinnacle is wrong, flagged bets have lower CLV. If Pinnacle alone means
Pinnacle moved first and the soft books lag, flagged bets have higher CLV and
the gate would remove the best bets. The S3 slice (claimed edge of 15%+ had
lower CLV) leans to the first story for large gaps. Guess: flagged CLV is lower
at r = 15% and no different at r = 5%.

**Not testable on this data, shipped as a defect fix instead (audit 5a #9):** no
fallback to a consensus of fewer than 3 soft books.

**A1 result (2026-10-02, `research/results/a1_development.md`, commit `dc71f36`).**
Dropped on development data; the holdout was not read. No gap limit met the
choice rule. CLV of kept minus flagged bets: +0.5% (-0.4 to +1.4) at 5%, +0.1%
(-1.7 to +1.9) at 10%, +1.7% (-1.4 to +4.9) at 15%. All three intervals include
zero. Flagged bets still had positive CLV at 5% and 10%, so the gate would have
removed bets no worse than the ones it kept. The checked blend's log loss is
indistinguishable from Pinnacle alone (+0.00001 at 10%), and the other books'
median is worse than Pinnacle (+0.0005, interval above zero). My guess for 15%
pointed the right way (flagged CLV +0.7% against +2.4%) but 124 bets cannot
establish it. The defect fix (no reference from fewer than 3 soft books) stays.

### A2. De-vig bake-off (written 2026-10-02, before any A2 run)

**Idea (docs/research.md, proposal A2).** Kairos removes Pinnacle's margin with
the power method. Add Shin's method and compare proportional, power and Shin.

**What is run.** For every development match with a Pinnacle price, each method
turns the price into probabilities and is scored by log loss against the result.
Four price sets: 1X2 pre-match, 1X2 closing, over/under 2.5 pre-match and
closing. Differences are paired by match against the power method, with a 95%
interval. Also split by the longest price in the market (under 5, 5 to 10, 10
and over) and by league. No walk is needed: each forecast uses only that
match's own price.

**Choice rule on development data.** The candidate is the method with the
lowest log loss on 1X2 pre-match prices (the reference Kairos bets against). It
goes to the holdout only if its paired difference against power lies wholly
below zero. Otherwise power stays and the holdout is not read.

**Holdout rule.** Adopt the candidate only if, on the holdout 1X2 pre-match
prices, its paired difference against power again lies wholly below zero.

**Expected.** Differences of a few ten-thousandths. Proportional worst, because
it leaves too much probability on longshots. Power and Shin close together.
Guess: power stays.

**A2 result (2026-10-02, `research/results/a2_development.md`, commit `429ac1b`).**
Power stays; the holdout was not read. Power had the lowest log loss on all four
price sets. On 1X2 pre-match (93,025 matches): proportional minus power +0.00025
(+0.00014 to +0.00035), Shin minus power +0.00005 (+0.00002 to +0.00009). The
whole difference is in markets with a longshot: where the longest price is 10 or
more, proportional is worse by +0.00265 and Shin by +0.00073; where it is under
5 the three are identical to five decimals. Shin is now available in
`market.py` but is not the default. Seven Pinnacle rows in 265,000 have a margin
above 12% (data errors, e.g. over/under 1.06 and 1.81); they were left in.

### A3. Price cousin markets from the sharp line (written 2026-10-02, before any A3 run)

**Idea (docs/research.md, proposal A3).** Fit expected goals for each side to
Pinnacle's prices, then read other markets off the score matrix: other goal
lines, Asian handicaps (with correct quarter-line settlement), double chance.

**Fit.** Dixon-Coles score matrix with rho fixed at -0.10 (the shipped default;
not tuned). Two fits:
- *F1*: expected goals chosen so the matrix reproduces Pinnacle's fair 1X2
  (power de-vig). Uses no totals price.
- *F2*: expected goals chosen so the matrix reproduces Pinnacle's fair
  home-minus-away margin and Pinnacle's fair over 2.5 probability.

**Tests on development data, seasons 2019/20 on (when the files carry
Pinnacle and Bet365 totals and handicap prices).**
- *T1 (the test named in the research):* F1's over-2.5 probability, scored by
  log loss against Pinnacle's own over/under price and Bet365's own (both power
  de-vig), on the same matches.
- *T2:* F2's probability that the home side covers the pre-match Asian handicap
  line, on matches where that line is a half line (no push, so log loss is
  defined), against Pinnacle's own handicap price and Bet365's own.
- *T3 (arithmetic, no data):* quarter-line settlement and double chance are
  checked by unit tests against hand-worked cases.

**Kill rules.** T1: the 1X2-only fit is killed as a way to price totals if its
log loss is worse than Bet365's own (paired interval wholly above zero). T2: the
1X2-plus-total fit is killed as a way to price handicaps if its log loss is
worse than Bet365's own.

**Holdout rule.** A fit that survives on development data is re-run on the
holdout and kept only if it is again not worse than Bet365's own price.

**Expected.** T1 killed: a 1X2 price says little about total goals, so the
derived over/under will be clearly worse than both bookmakers' own. T2
survives: once the total is pinned to Pinnacle's, the handicap price should be
close to Pinnacle's own and no worse than Bet365's.

**What survives regardless.** Quarter-line settlement is a correctness fix
(audit 5a #4) and ships with unit tests whatever the data says.
