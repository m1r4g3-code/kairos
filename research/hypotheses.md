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

### A4. Same-match exposure and Kelly shrinkage (written 2026-10-02, before any A4 run; A3 still running)

**Idea (docs/research.md, proposal A4).** Two parts.

*Part 1, same-match grouping (audit 5a #11).* Bets on one match are not
independent. The combined stake on one match is capped at the single-bet cap
(5% of bankroll). This is the rule already written in `knowledge/staking-kelly.md`
("correlated bets count once"), so it ships as a defect fix with unit tests. It
changes no probability and needs no data test.

*Part 2, shrink the edge before Kelly.* The baseline's bets claimed +5.4% and
kept +2.3% at the close. Kelly on the claimed edge over-bets. Shrunk Kelly
multiplies the claimed edge by k before sizing, where k = mean CLV / mean
claimed edge over the development B0 1X2 bets (computed in the run, not chosen
by hand).

**What is run (development B0 1X2 bets).** 2,000 bootstrap bankroll paths, each
resampling whole matches with replacement to the original count and betting
them in sequence from a bankroll of 100. Three staking rules:
- flat: 1 unit per bet (the owner's current practice);
- quarter Kelly on the claimed edge, 5% cap (what `kelly.py` does today);
- quarter Kelly on the shrunk edge, 5% cap, same-match grouping.
Reported for each: median final bankroll, 5th percentile of final bankroll,
median and 95th percentile of the worst drawdown.

**Choice rule on development data.** Shrunk Kelly goes to the holdout only if,
against quarter Kelly on the claimed edge, its 95th-percentile drawdown is
smaller and its median final bankroll is not lower.

**Holdout rule.** Same comparison on the holdout B0 bets.

**Expected.** Fails its own rule. Shrinking makes every stake smaller, so
drawdown falls, but if the edge is real the median final bankroll falls too.
Quarter Kelly on a 5.4% claim is roughly 0.6 Kelly on a true 2.3%, which is
still below full Kelly. Stated before the run: the flat-stake result is the one
that matters to the owner, because no Kelly rule should be used until the edge
is established on SportyBet.

**A3 result (2026-10-02, `research/results/a3_development.md` and `a3_holdout.md`).**
- *T1 killed on development data, as expected.* Over 2.5 fitted from the 1X2
  price alone: log loss 0.68096 against Bet365's own 0.67616, difference
  +0.00479 (+0.00369 to +0.00590), 39,399 matches. Its probability sits 4.09
  points from Pinnacle's on average. A 1X2 price cannot price totals. Not taken
  to the holdout.
- *T2 survived on development data and on the holdout.* Home-covers probability
  on half-line handicaps, fitted from Pinnacle's 1X2 and over 2.5. Development
  (8,966 matches): derived minus Bet365's own +0.00020 (-0.00038 to +0.00079);
  derived minus Pinnacle's own +0.00049 (+0.00001 to +0.00097). Holdout (2,134
  matches, first and only holdout read so far, 39 files logged in
  `research/holdout_access.jsonl`): derived minus Bet365's own +0.00053
  (-0.00056 to +0.00163); derived minus Pinnacle's own -0.00007 (-0.00089 to
  +0.00074). Mean gap to Pinnacle's own probability: 0.68 points on development
  data, 0.57 on the holdout.
- **Merged:** `engine/derive.py`. What the result supports: the fit is about as
  accurate as a bookmaker's own handicap price. What it does not support: that
  a small gap between a soft book's handicap price and the derived price is
  value. The derived probability is off Pinnacle's by about 0.6 points on
  average, which is over 1% of expected value at even money.
- Quarter lines and whole lines were tested by arithmetic only (unit tests), not
  against results.

**A4 result (2026-10-02, `research/results/a4_development.md`, commit `715e417`).**
- Part 1 (one match, one position) shipped as a defect fix with tests.
- Part 2 failed its rule on development data, as expected; the holdout was not
  read for it. Shrink factor 0.437 (mean CLV +2.34% over mean claimed +5.35%).
  Median final bankroll from 100 over 2,976 bets: flat 1 unit 270.9, quarter
  Kelly on the claimed edge 217.8, quarter Kelly on the shrunk edge 143.7.
  95th-percentile worst drawdown: 93.1%, 41.7%, 20.7%. Shrinking halves the
  drawdown and also cuts the growth, so it does not meet "no loss of median
  growth". `kelly.shrunk_stake_fraction` exists but nothing calls it.
- Worth noting for the owner: with flat 1-unit stakes on a 100-unit bankroll,
  one path in twenty lost 93% of its peak at some point, even though the same
  bets had a positive average return. These bets average odds near 5.

### A5. Team ratings blended with the market (written 2026-10-02, before any A5 run)

**Idea (docs/research.md, proposal A5).** A goal-based team rating, blended with
Pinnacle's price by a fitted weight. Built with the standard library only.

**Model.** One online rating per team per league: attack a and defence d, with a
league base rate and a league home advantage. Expected goals
home = exp(base + home_adv + a_home - d_away), away = exp(base + a_away - d_home).
After each match every term moves by k x (goals - expected goals) (a gradient
step on the Poisson likelihood; league terms move at k/10). A team new to a
league starts at the mean rating of that league's three lowest-rated teams.
1X2 comes from the shipped Dixon-Coles matrix with rho = -0.10. Ratings run from
2000/01 so they are warm when Pinnacle prices begin in 2012/13.

**Tuning allowed on development data.** k from {0.02, 0.04, 0.08}, chosen by the
model's own log loss on development matches that have a Pinnacle price.

**Blend.** Log pool: p proportional to market^(1-w) x model^w, market = Pinnacle
pre-match, power de-vig. w is fitted by maximum likelihood; its 95% interval is
the likelihood-ratio interval. Walk-forward version: for each season, w is
fitted on all earlier seasons only.

**Choice rule on development data.** A5 goes to the holdout only if the
interval for w excludes zero **and** the walk-forward blend's log loss is lower
than the market's alone with the paired interval wholly below zero.

**Holdout rule.** With k and w frozen from development data, merge only if the
blend's log loss on the holdout is lower than the market's alone with the paired
interval wholly below zero.

**Expected.** Killed. Model log loss around 0.03 worse than Pinnacle; w at or
near zero (Pitcan 2026 found 0.000 over 19 Serie A seasons).

### A6. Shots-on-target ratings for totals (written 2026-10-02, before any A6 run)

**Idea (docs/research.md, proposal A6; Wheatcroft).** Shots carry more
information about future goals than goals do. Replaces Understat, whose live
feed is off limits, with the shots-on-target columns already in the files.

**Model.** The same online rating as A5, but the count being rated is shots on
target. Expected goals for a side = its expected shots on target x the league's
running goals-per-shot-on-target rate (updated after each window). Over 2.5
comes from the shipped score matrix. Same k grid, chosen by the model's own
over/under log loss on development matches with a Pinnacle over/under price.
The first ten league-matches of data per league are not forecast.

**Tests on development data (2019/20 on, where Pinnacle totals exist).**
- Log-pool weight w against Pinnacle's pre-match over/under, as in A5.
- Betting: back over or under at Bet365's pre-match price when the model's
  probability x price - 1 exceeds 3%; CLV against Pinnacle's closing total.

**Choice rule on development data.** A6 goes to the holdout only if the
interval for w excludes zero **and** the bets' CLV interval lies wholly above zero.

**Holdout rule.** Same two conditions on the holdout with k and w frozen.

**Expected.** Killed. The published effect is about 0.8% per bet against a
5-6% soft-book margin; I expect a weight near zero and negative CLV.

### B0-H. The baseline on the holdout (written 2026-10-02, to be run last in Phase 3)

Once A5 and A6 are finished, the frozen B0 (Bet365 against Pinnacle, +3%, 1X2 and
over/under 2.5) is run once on the holdout seasons. No improvement that changes
bet selection is pending, so this is an out-of-sample check of the Phase 2
finding, not a comparison.
**Expected.** 1X2 CLV positive but smaller than the development +2.3%, because
the last development seasons were weaker (2023/24: +1.2%, interval includes
zero). Roughly 250-350 bets. Return per bet not distinguishable from zero.
**What would change my view.** A CLV interval wholly below zero on the holdout
would mean the development result does not carry forward to recent seasons.

**A5 result (2026-10-02, `research/results/a5_development.md`, commit `4dc2be8`).**
Killed on development data, as expected; the holdout was not read. Best k was
0.02: model log loss 1.02178 against the market's 1.00355, difference +0.01823
(+0.01706 to +0.01940) on 93,025 matches. Fitted log-pool weight on the model:
0.0000 (interval 0.0000 to 0.0096). Every season's walk-forward weight was 0.
Caveat: the best k was the smallest on the grid, so this rating is not the best
one could build. A better rating would narrow the 0.018 gap; the published
result for a full Dixon-Coles model is also a weight of zero.

**A6 result (2026-10-02, `research/results/a6_development.md`, commit `4dc2be8`).**
Killed on development data, as expected; the holdout was not read. Best k 0.02
(again the grid edge): model over/under log loss 0.70346 against the market's
0.67595, +0.02751. Log-pool weight 0.0176 (interval 0.0000 to 0.0586): the
interval includes zero. Walk-forward blend minus market +0.00003 (-0.00008 to
+0.00015). Betting the model's opinion at Bet365's price: 30,310 bets, return
-5.1% (-6.3 to -4.0), CLV -4.5% (-4.6 to -4.5). That CLV is Bet365's margin: the
model's "value" bets were no better than random picks.

**A7 (calibration layer) is not run.** It was conditional on A5 or A6 surviving.
