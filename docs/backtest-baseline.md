# Phase 2: the backtest harness and the Kairos v2 baseline

Written 2026-10-02 on branch `dev/phase-2-backtest`. Every number here comes from
`research/results/baseline_tables.md` or `research/results/slices.md`, which are
written by `harness/run_baseline.py` (commit `34aabe4`) and `harness/run_slices.py`
(commit `1bcf4d8`). The holdout seasons have not been opened.

## Summary

1. **The harness exists and passes its leak tests.** It walks 183,427 matches from
   22 leagues, 2000/01 to 2024/25, in the order the odds were collected. Scrambling
   every result and closing price changed 0 decisions. Cutting the history short
   changed 0 decisions.
2. **It reproduces the Phase 0 diagnostic exactly:** 31 bets, return −5.9%, CLV −4.4%
   on the ten audited league-seasons.
3. **On the full development data the baseline does better than Phase 0 suggested.**
   Kairos v2 as shipped (Bet365 against Pinnacle's fair price at the same collection,
   +3% threshold) placed 2,976 1X2 bets. Closing-line value was **+2.3%** (95% interval
   +1.9 to +2.8). Return per bet was **+6.0%** (−1.2 to +13.4). The interval on the
   return includes zero.
4. **The five big leagues carry none of it.** In E0, SP1, D1, I1 and F1 the CLV was
   +0.8% (−0.5 to +2.3) on 333 bets. In the other 17 leagues it was +2.5% (+2.1 to +3.0)
   on 2,643 bets. Phase 0 looked only at the big five, in two recent seasons.
5. **Less than half the claimed edge survives to the close.** The bets claimed +5.4% on
   average and kept +2.3%.
6. **This is still not proof for SportyBet.** Bet365 is a stand-in. Three limits apply
   and are set out in section 6: the two prices may not have been collected at the same
   minute, Bet365 limits winning accounts, and the holdout has not been used.

## 1. What was built

| File | Job |
|---|---|
| `harness/fd_fetch.py` | Downloads Football-Data files one at a time with a pause. Can be killed and restarted. Writes `research/data_manifest.json` (checksum, size, columns of each file). |
| `harness/fd_data.py` | Loads a file into `PreMatch` (teams, date, pre-match prices) and `Post` (result, statistics, closing prices). Refuses holdout seasons. |
| `harness/walk.py` | Walk-forward runner and the leak check. |
| `harness/metrics.py` | Log loss, Brier, RPS, calibration buckets, bootstrap intervals. Knows nothing about football. |
| `harness/score.py` | Settles bets, computes CLV, collects forecasts. |
| `harness/strategies.py` | The baseline. It calls the shipped `edge.sharp_fair` and `edge.value_vs_sharp`. |
| `harness/run_baseline.py`, `run_slices.py` | Produce the result files. |
| `harness/runlog.py` | Appends every variant run to `research/runs.jsonl`. |
| `harness/census.py` | The SportyBet gap census (section 7). |
| `harness/test_harness.py` | 85 checks. Added to the CI workflow. |
| `research/holdout.json` | The holdout seasons, committed before any download. |
| `research/hypotheses.md` | Each variant, written before it was run. |

Everything is standard library. No dependency was added.

To run it:

```
python harness/fd_fetch.py        # once; over an hour, resumable
python harness/test_harness.py
python harness/run_baseline.py    # about 21 minutes, most of it the leak audit
python harness/run_slices.py
```

## 2. Data

- **Source:** Football-Data.co.uk main-league files. 567 files downloaded, about one
  every 8 seconds. Five do not exist (the fifth English tier before 2005/06).
- **Leagues (22):** England five tiers, Scotland four, Germany two, Italy two, Spain two,
  France two, Netherlands, Belgium, Portugal, Turkey, Greece.
- **Seasons:** 2000/01 to 2025/26. Pinnacle pre-match and closing 1X2 prices start in
  2012/13. Pinnacle over/under 2.5 prices start in 2019/20.
- **Development data:** 183,427 matches. 93,025 have a Pinnacle pre-match 1X2 price and
  91,739 of those have a Pinnacle closing price. 39,469 have a Pinnacle over/under price.
- **Not used:** the "extra leagues" files (Argentina, Brazil and others). They carry
  closing prices only, so a bet-time comparison cannot be made without look-ahead.
- The files are in `data/`, which is gitignored. The manifest with checksums is committed.

## 3. Holdout

Recorded in `research/holdout.json` and committed (`2481b4f`) before the first download.

- **Holdout:** season 2025/26 for all 22 leagues, and 2024/25 for the 17 leagues other
  than E0, SP1, D1, I1, F1. That is 39 files.
- **Not holdout:** the ten league-seasons examined in Phase 0.
- **2026/27** is in progress and is reserved as forward data. It was not downloaded.
- The loader raises an error on a holdout season unless given a written reason, and logs
  the read to `research/holdout_access.jsonl`. That file does not exist: no holdout
  row has been read. Only checksums, line counts and column names were recorded.

I did not run the baseline on the holdout. Its numbers there will be computed in the
same run as the first finished improvement, so each look at the holdout answers a
question that was fixed in advance.

## 4. Walk-forward rule and the leakage proof

**The rule.** Football-Data collects prices on Friday afternoon for Friday-to-Monday
games and on Tuesday afternoon for Tuesday-to-Thursday games. The runner groups matches
into those collection windows. It asks for every decision in a window first, scores
them, and only then shows the results to the strategy. A Sunday bet is therefore decided
without Saturday's results, because the price it takes was collected on Friday. This is
stricter than "nothing after kickoff".

**Four defences:**

1. **Separate types.** A strategy is handed `PreMatch`, which has no result, statistic
   or closing price in it. A test checks the field list and checks that no closing number
   reaches it.
2. **Order test.** A spy strategy records every result it is shown. No result dated on
   or after a collection day was visible when that window was decided.
3. **Scramble test on the real data.** All results and closing prices were shuffled
   between matches and the baseline was re-run. Decisions changed: **0** of 183,427
   matches, for two strategy settings.
4. **Truncation test on the real data.** The history was cut off at several points
   and re-run. Decisions changed: **0**. The same check catches a deliberately leaky test
   strategy that fits on the whole history, so the check itself works.

The baseline does not learn from results, so tests 3 and 4 are easy for it to pass. They
matter in Phase 3, when rating models that do learn are added. `walk.leak_check` runs on
any strategy.

**What the tests cannot prove:** that Football-Data's Bet365 and Pinnacle prices were
recorded at the same minute. See section 6.

## 5. Baseline results (development data)

Baseline B0 is Kairos v2 as shipped: Pinnacle's pre-match price with the margin removed
by the power method, a bet where Bet365 pays more than that fair price by +3%, one unit
flat. CLV is the price taken times Pinnacle's fair closing probability, minus 1.
Intervals are 95%, from 2,000 bootstrap resamples of whole matches.

### 5a. Bets

| Market | Bets | Return per bet | 95% interval | CLV | 95% interval | Mean odds |
|---|---|---|---|---|---|---|
| 1X2 | 2,976 | +6.0% | −1.2 to +13.4 | +2.3% | +1.9 to +2.8 | 4.98 |
| Over/under 2.5 | 110 | +24.8% | +3.6 to +48.1 | +4.3% | +2.7 to +5.9 | 2.50 |
| Both | 3,086 | +6.7% | +0.0 to +14.4 | +2.4% | +2.0 to +2.8 | 4.89 |

- 1X2 profit was +179.79 units on 2,976 bets. 2,889 of them had a closing price.
- The over/under sample is 110 bets from five seasons. Its return interval is 44 points
  wide. Treat it as a small sample.
- With the proportional de-vig, 1X2 CLV reads +4.1% (+3.7 to +4.5). The sign does not
  depend on the de-vig method; the size does.
- 2,976 bets is 1.07% of the outcomes priced by both books. At +2% it is 4,986 bets.

**By season, 1X2:**

| Season | Bets | Return per bet | CLV | 95% interval |
|---|---|---|---|---|
| 2012/13 | 143 | +17.2% | +0.9% | −1.0 to +2.7 |
| 2013/14 | 194 | +7.4% | +2.2% | +0.5 to +4.0 |
| 2014/15 | 213 | +7.4% | +2.0% | +0.6 to +3.5 |
| 2015/16 | 270 | +11.0% | +4.3% | +2.7 to +6.1 |
| 2016/17 | 268 | +4.7% | +2.1% | +0.8 to +3.5 |
| 2017/18 | 301 | −12.6% | +2.8% | +1.3 to +4.4 |
| 2018/19 | 457 | +14.5% | +2.8% | +1.8 to +3.8 |
| 2019/20 | 349 | +0.4% | +3.0% | +1.7 to +4.3 |
| 2020/21 | 234 | −1.0% | +1.8% | +0.2 to +3.5 |
| 2021/22 | 231 | +19.7% | +0.6% | −0.8 to +2.1 |
| 2022/23 | 155 | +2.3% | +2.5% | +0.8 to +4.3 |
| 2023/24 | 152 | +5.1% | +1.2% | −0.8 to +3.2 |
| 2024/25 (five leagues only) | 9 | −15.2% | −5.9% | −15.6 to +3.5 |

CLV was above zero in 12 of 13 seasons. The number of bets has fallen since 2018/19.
No single season's return is distinguishable from zero.

**By league, 1X2** (full table with return intervals in `baseline_tables.md`):

| League | Bets | Return per bet | CLV | 95% interval |
|---|---|---|---|---|
| E0 | 90 | +35.8% | −0.6% | −3.1 to +2.0 |
| SP1 | 62 | −7.7% | −0.1% | −3.3 to +3.2 |
| F1 | 81 | +1.6% | +0.7% | −1.9 to +3.4 |
| D1 | 50 | −15.5% | +2.0% | −0.8 to +5.0 |
| I1 | 50 | −23.5% | +3.6% | −0.1 to +7.6 |
| E1 | 166 | +31.5% | +2.7% | +1.0 to +4.4 |
| E2 | 303 | +2.3% | +1.0% | −0.0 to +2.0 |
| E3 | 358 | +8.9% | +2.2% | +1.3 to +3.1 |
| EC | 297 | +23.7% | +2.7% | +1.2 to +4.2 |
| SC0 | 66 | −17.1% | +4.1% | +1.6 to +6.9 |
| SC1 | 67 | −7.9% | −0.1% | −2.6 to +2.2 |
| SC2 | 117 | +19.2% | +2.6% | −0.8 to +6.2 |
| SC3 | 128 | −1.5% | +6.9% | +4.2 to +9.8 |
| D2 | 80 | −31.2% | +2.4% | +0.3 to +4.6 |
| I2 | 130 | +7.3% | +2.9% | +1.5 to +4.4 |
| SP2 | 196 | +9.2% | +2.7% | +1.0 to +4.4 |
| F2 | 141 | +16.6% | +2.5% | +0.9 to +4.3 |
| N1 | 119 | +3.4% | +0.5% | −2.1 to +2.9 |
| B1 | 93 | −3.3% | +1.6% | −0.8 to +4.0 |
| P1 | 85 | −16.0% | +3.2% | +0.3 to +6.3 |
| T1 | 127 | +16.2% | +4.0% | +1.6 to +6.5 |
| G1 | 170 | −16.9% | +3.9% | +1.3 to +6.7 |

Per-league returns swing from −31% to +36% on samples of 50 to 358 bets. They are noise
at this size. CLV is the steadier reading.

### 5b. Forecast quality

The baseline's forecast is Pinnacle's pre-match price with the margin removed.

| Market | Matches | Log loss | Brier (0 to 2) | RPS | Calibration error |
|---|---|---|---|---|---|
| 1X2 | 93,025 | 1.0035 | 0.6003 | 0.2045 | 0.12% |
| Over/under 2.5 | 39,469 | 0.6759 | 0.4831 | 0.2416 | 0.20% |

**Calibration buckets, 1X2** (each match contributes three outcomes):

| Forecast | Outcomes | Mean forecast | Happened | Gap (points) |
|---|---|---|---|---|
| 0–10% | 7,160 | 7.0% | 6.7% | −0.3 |
| 10–20% | 30,160 | 15.9% | 15.8% | −0.1 |
| 20–30% | 110,069 | 26.0% | 26.0% | −0.0 |
| 30–40% | 58,517 | 34.1% | 34.1% | +0.0 |
| 40–50% | 35,477 | 44.7% | 44.5% | −0.2 |
| 50–60% | 20,070 | 54.5% | 54.8% | +0.2 |
| 60–70% | 10,064 | 64.4% | 64.1% | −0.3 |
| 70–80% | 5,071 | 74.4% | 75.9% | +1.5 |
| 80–90% | 2,233 | 83.9% | 85.1% | +1.2 |
| 90–100% | 254 | 91.8% | 91.3% | −0.5 |

The forecast is well calibrated. The largest gaps are for strong favourites (70–90%),
which won 1.2 to 1.5 points more often than forecast. Per-league and per-season tables,
and the over/under buckets, are in `baseline_tables.md`.

**Against other readings of the market, on the same matches:**

| Forecaster | 1X2 log loss (91,648 matches) | Difference from baseline | 95% interval |
|---|---|---|---|
| Baseline: Pinnacle pre-match, power | 1.0032 | | |
| Bet365 pre-match, proportional | 1.0044 | +0.0011 | +0.0009 to +0.0014 |
| Market average pre-match, proportional | 1.0042 | +0.0010 | +0.0007 to +0.0012 |
| Pinnacle closing, power (a bar, not a strategy) | 1.0001 | −0.0031 | −0.0036 to −0.0026 |

The ordering is as predicted: closing price best, then Pinnacle pre-match, then the
average and Bet365. The gap from the baseline to the closing price, 0.0031, is the room
any pre-match improvement has to work in. The over/under table shows the same ordering
with a gap of 0.0025.

### 5c. Sensitivity variants (registered before the run, not tuned)

**1X2:**

| Soft price | Threshold | Bets | Return per bet | 95% interval | CLV | 95% interval |
|---|---|---|---|---|---|---|
| Bet365 | 0% | 15,418 | +1.2% | −1.3 to +3.7 | +0.4% | +0.3 to +0.5 |
| Bet365 | 2% | 4,986 | +1.4% | −3.5 to +6.6 | +1.7% | +1.3 to +1.9 |
| Bet365 | 3% (baseline) | 2,976 | +6.0% | −1.2 to +13.4 | +2.3% | +1.9 to +2.8 |
| Bet365 | 5% | 1,147 | +8.0% | −4.8 to +21.3 | +3.6% | +2.8 to +4.4 |
| Best of named books | 0% | 41,269 | +1.5% | +0.2 to +2.9 | +1.3% | +1.2 to +1.4 |
| Best of named books | 2% | 15,062 | +2.5% | −0.3 to +5.3 | +3.0% | +2.8 to +3.2 |
| Best of named books | 3% | 9,269 | +4.9% | +1.3 to +8.6 | +4.0% | +3.7 to +4.2 |
| Best of named books | 5% | 3,778 | +10.3% | +3.5 to +17.0 | +6.1% | +5.6 to +6.5 |

- CLV rises with the threshold. I predicted it would not. That prediction was wrong.
- Taking the best price among several bookmakers gives three times the bets and a return
  interval that excludes zero at +3% and +5%. This matches the published studies. It
  needs accounts at several bookmakers.
- For over/under the files name only one soft bookmaker (Bet365), so "best of" is the
  same as the baseline there.

### 5d. Slices of the baseline's 1X2 bets (post hoc)

These were written down after seeing the league table, so they describe; they do not test.

| Group | Bets | Return per bet | 95% interval | CLV | 95% interval | Share of outcomes |
|---|---|---|---|---|---|---|
| E0, SP1, D1, I1, F1 | 333 | +2.7% | −22.0 to +29.6 | +0.8% | −0.5 to +2.3 | 0.47% |
| Other 17 leagues | 2,643 | +6.5% | −0.7 to +14.1 | +2.5% | +2.1 to +3.0 | 1.27% |
| First-tier leagues (11) | 993 | −2.3% | −16.4 to +11.0 | +2.2% | +1.3 to +3.1 | 0.77% |
| Lower tiers (11) | 1,983 | +10.2% | +2.0 to +18.4 | +2.4% | +1.9 to +2.9 | 1.32% |
| 2012/13 to 2017/18 | 1,389 | +4.3% | −6.0 to +14.6 | +2.6% | +1.9 to +3.2 | 1.01% |
| 2018/19 to 2024/25 | 1,587 | +7.6% | −2.2 to +17.8 | +2.1% | +1.5 to +2.7 | 1.12% |

| Claimed edge | Bets | Return per bet | CLV | 95% interval |
|---|---|---|---|---|
| 3–5% | 1,829 | +4.8% | +1.6% | +1.1 to +2.0 |
| 5–10% | 967 | +6.6% | +3.1% | +2.2 to +4.0 |
| 10–15% | 132 | +21.4% | +7.5% | +4.2 to +10.8 |
| 15% and over | 48 | +0.4% | +3.4% | −2.0 to +8.7 |

| Price taken | Bets | Return per bet | 95% interval | CLV | 95% interval |
|---|---|---|---|---|---|
| Under 2.5 | 143 | −9.2% | −24.4 to +6.8 | +3.1% | +1.7 to +4.5 |
| 2.5 to 5 | 1,868 | +8.4% | +1.1 to +16.0 | +2.2% | +1.7 to +2.6 |
| 5 to 10 | 780 | +8.0% | −9.0 to +25.1 | +2.6% | +1.5 to +3.6 |
| 10 and over | 185 | −14.1% | −60.3 to +39.8 | +2.4% | −0.2 to +5.3 |

- The big-five result explains Phase 0. Bet365 is priced closest to Pinnacle in the
  leagues everybody watches.
- Above a 15% claimed edge the CLV falls back and its interval includes zero. That
  supports the "a huge edge is a bug" rule in `CLAUDE.md`.
- The result does not live only in longshots. The 2.5-to-5 band holds 63% of the bets
  and has positive CLV and a return interval above zero. I predicted most of the CLV
  would sit above odds of 5. That was wrong.

## 6. What this does and does not show

**It shows** that over twelve seasons a rule of "bet where Bet365 beats Pinnacle's fair
price by 3%" picked prices that Pinnacle's closing line later agreed were good, by about
2.3%, mostly outside the five big leagues.

**It does not show that Kairos has an edge on SportyBet.** Four reasons:

1. **The two prices may not be simultaneous.** Football-Data says prices are collected
   on Friday and Tuesday afternoons. It does not say Bet365 and Pinnacle are read at the
   same minute. If Pinnacle was read later than Bet365, some "value" is a Bet365 price
   that had already gone, and the CLV is inflated in the same way as in the old
   backtester, only less. The data cannot settle this. Phase 1 found that the best-known
   study of this kind had the same doubt.
2. **Bet365 is not SportyBet.** SportyBet's margin, speed and limits are unmeasured.
3. **Winners get limited.** The Phase 1 research found soft bookmakers restrict accounts
   that take these prices. A backtest has no account to restrict.
4. **The return is not established.** The 1X2 return interval is −1.2% to +13.4%. CLV of
   +2.3% predicts a return near +2%, which this sample cannot tell apart from zero.

**Correction to my earlier reports.** In Phase 0 and Phase 1 I wrote that one mainstream
bookmaker beats Pinnacle's fair price on about 0.3% of outcomes with negative CLV. That
is true for the ten league-seasons I had then. Across all 22 leagues it is 1.07% of
outcomes at +3% with positive CLV. The earlier statement was too broad.

## 7. Two approved side changes

- **Live Understat fetch disabled.** `sources/understat.py` now raises an error instead
  of fetching, because the site's `robots.txt` disallows all automated access. The
  parser and its offline tests remain. One test was added.
- **Gap census built** (`harness/census.py`, file `ledger/census.jsonl`). It logs each
  SportyBet price next to Pinnacle's fair price at that moment, and Pinnacle's price
  from a fetch within three hours of kickoff. It reports the share of prices beating
  fair value and CLV with an interval, and applies the kill rule from
  `docs/research.md` after 1,000 prices. Logging the same price twice writes one line.
  **Limit:** nothing fetches the closing price automatically until Phase 4. Until then a
  close is recorded only when a fetch happens near kickoff.
- `engine/backtest.py` was not rewritten. It now prints a warning that it has look-ahead
  and points here.

## 8. What I did not check

- Whether Football-Data's Bet365 and Pinnacle prices are collected at the same time.
- The holdout seasons, by design.
- Asian handicap columns. The loader ignores them.
- The correctness of Football-Data's prices. I did not compare them with another source.
  Bets claiming 15% or more (48 of 2,976) may include data errors.
- Whether a Bet365 price in the file could be taken for a real stake.
- Pre-2012 seasons carry no Pinnacle price and add nothing to the betting numbers. They
  are loaded for rating models in Phase 3.
- `README.md` still has the mismatches listed in the audit and does not mention the harness.
- The census has no real prices in it yet. Its tests use made-up events.

## 9. Test status

| Suite | Checks | Result |
|---|---|---|
| `engine/test_engine.py` | 53 | pass |
| `engine/test_ledger.py` | 13 | pass |
| `engine/test_edge.py` | 28 | pass |
| `engine/test_sources.py` | 16 | pass |
| `harness/test_harness.py` | 85 | pass |
