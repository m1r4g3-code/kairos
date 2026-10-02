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
