# Kairos — Phase 0 audit

Date: 2026-10-02. Branch: `dev/phase-0-audit`. No engine code was changed.
Python used: 3.13.12 on the owner's Windows 11 PC.

## Summary

1. **The repo holds two separate systems, and the one the README calls "the v2.0 core" is not connected to anything.** `engine/run.py` (the command the `/predict` skill runs) compares the Poisson model with the same soft bookmaker's odds. The sharp-line comparison in `engine/edge.py` is a standalone module that no command calls.
2. **The backtester does not show an edge.** It picks bets using Pinnacle's *closing* price but stakes them at a Bet365 price taken earlier, so it uses information that did not exist at bet time. Its "CLV" column is positive by arithmetic, not by evidence. When I select bets with Pinnacle's price from the same moment as the Bet365 price, 1,378 bets shrink to 31 across ten league-seasons, and those 31 show CLV of −4.4% (95% interval −9.8% to +0.3%).
3. **Even with the look-ahead, the pooled return is not distinguishable from zero**: +2.5% ROI on 1,378 bets, 95% interval −5.2% to +10.1%.
4. **The ledger cannot answer whether Kairos beats the closing line.** 54 predictions are logged, 3 are settled through the tool, and there are zero usable CLV observations.
5. All four test suites pass (108 checks). The tests cover the arithmetic of the building blocks well and do not cover the things listed above.

Terms used below: *fair price* means a bookmaker's odds with the margin removed. *CLV* (closing-line value) means how much better the price you took was than the fair price at kickoff. *ROI* is profit divided by total staked.

---

## 1. How the system actually works (traced from code)

### Path A — the model path (what the CLI and the `/predict` skill run)

`python engine/run.py spec.json` → `run.build_prediction` (`engine/run.py:147`):

1. `_validate_spec` checks confidence, bankroll, odds > 1.0, and `lambdas` > 0. It does not check `strengths` or `elo` inputs.
2. `_resolve_lambdas` gets expected goals from one of: direct `lambdas`, `strengths` (`elo.strengths_to_lambdas`), or `elo` (`elo.elo_to_lambdas`).
3. `modifiers.lam_home_mult` / `lam_away_mult` multiply the expected goals (`run.py:153-155`). There is no limit on their size.
4. `poisson.full_markets` builds a Dixon-Coles score matrix (rho −0.10 by default) and derives 1X2, O/U 1.5/2.5/3.5 and BTTS.
5. `monte_carlo.simulate` runs 30,000 simulated matches. The result is returned in the output and used for nothing else.
6. For each market in the spec, `market.market_view` removes the margin **from the same bookmaker's odds that were typed in**, and `kelly.size_bet` computes EV = model probability × odds − 1, then applies the gates: EV ≥ 3%, confidence ≥ 45, quarter-Kelly × confidence/100, 5% cap. `kelly.cap_total_exposure` scales stakes down to 15% of bankroll in total.
7. `_sensitivity` re-prices the best bet under ±15% changes to expected goals. If EV falls below 3% anywhere on that grid the verdict becomes "SPECULATIVE".
8. `report.render_card` formats the result.

So in Path A the only source of "value" is the model disagreeing with the soft bookmaker. The model's inputs are numbers Claude chooses from web reading. No sharp price is involved.

### Path B — the sharp-line path (what has been used by hand since June)

- `sources/odds_api.fetch_raw` downloads odds from The Odds API and caches them.
- `odds_api.parse_event` turns one event into `{book: {home, draw, away}}` (1X2 only).
- `edge.sharp_fair` picks Pinnacle if present (else Betfair, else Marathonbet, else an average of every book) and removes the margin with the power method.
- `edge.value_vs_sharp` computes EV = SportyBet odds × sharp fair probability − 1 and flags EV > 3%.
- `report.render_sharp_card` formats rows of that kind.

**None of Path B is reachable from a command.** `run.py` does not import `edge`. `report.py`'s CLI only renders Path A cards. Every sharp-line read this year was a hand-written `python -c` one-liner or a throwaway script (the pattern is written down in `CLAUDE.md`). The glitch check, the totals/handicap parsing and the Asian-line maths used in those sessions live outside the repo.

### The ledger

`ledger.log_prediction` appends to `ledger/predictions.jsonl`; `ledger.record_result` appends to `ledger/results.jsonl`; `ledger.compute_calibration` joins them by id and reports Brier score, hit rate, ROI, average CLV and five probability buckets. Nothing calls `log_prediction` automatically; logging is a manual step in the protocol.

### The backtester

`python engine/backtest.py <league> <season>` downloads one Football-Data.co.uk CSV and, for every match outcome, bets 1 unit when Bet365 odds × Pinnacle fair probability − 1 exceeds a threshold (`backtest.py:57-74`).

---

## 2. Test results

Run from `engine/` on 2026-10-02:

| Suite | Checks passed | Failed | README says |
|---|---|---|---|
| `test_engine.py` | 53 | 0 | 52 |
| `test_ledger.py` | 13 | 0 | 12 |
| `test_edge.py` | 28 | 0 | 27 |
| `test_sources.py` | 14 | 0 | 13 |
| **Total** | **108** | **0** | **104** |

Python 3.13 is what is installed here; CI tests 3.10, 3.11 and 3.12 only.

---

## 3. Backtest results

### 3a. The existing backtester, as shipped

Ten league-seasons (England, Spain, Germany, Italy, France top divisions; 2023/24 and 2024/25), 3,504 matches. Rows at the +2% threshold:

| League-season | Bets | ROI | Profit (u) | "avg CLV" as printed |
|---|---|---|---|---|
| E0 2324 | 137 | +17.9% | +24.50 | +9.9% |
| E0 2425 | 140 | −3.4% | −4.79 | +9.9% |
| SP1 2324 | 150 | −10.2% | −15.33 | +8.8% |
| SP1 2425 | 170 | +9.1% | +15.52 | +10.2% |
| D1 2324 | 125 | −1.0% | −1.20 | +9.7% |
| D1 2425 | 119 | +12.4% | +14.72 | +9.5% |
| I1 2324 | 119 | −13.1% | −15.56 | +9.8% |
| I1 2425 | 152 | +4.1% | +6.25 | +10.5% |
| F1 2324 | 136 | +11.9% | +16.22 | +11.2% |
| F1 2425 | 130 | −4.5% | −5.84 | +10.4% |
| **Pooled** | **1,378** | **+2.5%** | **+34.49** | **+10.0%** |

Five seasons are positive and five negative. The higher thresholds (5%, 8%, 10%) have 15–82 bets per season and ROI from −19% to +88%, which is noise at that sample size.

### 3b. Why these numbers are not evidence

**Look-ahead.** `SHARP_COLS` tries `PSCH/PSCD/PSCA` first (`backtest.py:28`). Those are Pinnacle's closing odds. The soft price is `B365H/D/A`, Bet365's pre-match odds, collected earlier. The backtest therefore asks "which early Bet365 prices turned out to be better than where Pinnacle finished?", which nobody can know when placing the bet.

**The CLV column is positive by construction.** It is `soft / sharp_closing − 1` using raw closing odds, margin included (`backtest.py:69`), computed only on bets that were selected because soft odds beat the closing fair price. Any selected bet has a positive value here by definition. Measured against the fair closing price instead, the same bets show +6.7%, still inflated by the same selection.

**No interval, no holdout.** One unit flat per bet, every season in-sample, no confidence interval, and hit rate printed as a column.

### 3c. Diagnostic: the same rule without look-ahead

Scratch script (not in the repo) over the same ten cached files. Rule B selects with Pinnacle's pre-match odds (`PSH/PSD/PSA`), the same snapshot as the Bet365 price. CLV is measured against the fair closing price. Intervals are 95%, bootstrapped by match, 4,000 resamples.

| Threshold | Rule | Bets | ROI (95% interval) | CLV vs fair close (95% interval) |
|---|---|---|---|---|
| EV > 0% | A: select on closing (as shipped) | 2,165 | +0.2% (−5.6, +5.9) | +4.6% (+4.4, +4.8) |
| EV > 0% | B: select on same-time price | 185 | +7.8% (−15.4, +32.7) | +0.0% (−1.3, +1.3) |
| EV > 2% | A | 1,378 | +2.5% (−5.2, +10.1) | +6.7% (+6.4, +7.0) |
| EV > 2% | B | 31 | −5.9% (−66.0, +65.3) | −4.4% (−9.8, +0.3) |
| EV > 5% | A | 670 | +3.7% (−8.2, +15.4) | +10.2% (+9.7, +10.7) |
| EV > 5% | B | 3 | −100% | −11.0% (−30.8, −0.7) |

Mean margin in the data: Bet365 5.48%, Pinnacle pre-match 3.52%, Pinnacle closing 2.94%.

What this says:

- At a single moment in time, Bet365 beat Pinnacle's fair price by more than 2% on 31 of 10,512 outcomes. Nearly all of the 1,378 "value bets" in 3a exist only because the two prices were taken at different times.
- The 31 honest bets did not beat the closing line. Their CLV is negative on average. That fits the rule already in `CLAUDE.md` that a big gap is more often a stale or wrong price than a gift.
- Rule A's ROI interval includes zero at every threshold.

Limits of this diagnostic: it is Bet365, not SportyBet; it is 1X2 in five top leagues only; 31 bets is far too few to conclude anything about returns. It is a reason to distrust 3a, not a baseline. Phase 2 is where a proper one gets built.

---

## 4. What is strong

- **The building-block maths is correct where I checked it.** The Dixon-Coles adjustment has the standard form and the matrix is renormalised after truncation. Kelly and EV formulas are right. Power de-vig sums to 1 on normal inputs.
- **The discipline rules are sound and written down**: EV gate, confidence floor, fractional Kelly, per-bet and total caps, "a large edge is a mistake until proven otherwise", pass as a valid outcome.
- **The sensitivity check in `run.py`** is a good idea: it catches value that depends on a guessed input.
- **The ledger writes safely**: append-only, flush and fsync, duplicate ids auto-versioned, corrupt lines skipped and counted.
- **Zero dependencies, offline tests, CI on three Python versions.** Easy to run on this PC.
- **Secrets are handled correctly.** `.env` is ignored and has never been committed (`git log --all -- .env` is empty). Only `.env.example` is tracked.
- **The right idea is present.** Comparing a soft book with a sharp one is the only approach in this repo with a plausible route to positive CLV. The problem is that it is unproven and unwired, not that it is the wrong idea.

---

## 5. What is weak, fragile, untested or wrong

Each item marked **[verified]** was reproduced by running code on 2026-10-02. Others are from reading the code.

### 5a. Things that produce wrong numbers

| # | Where | Problem |
|---|---|---|
| 1 | `backtest.py:28,65,69` | Look-ahead and CLV-by-construction, section 3. **[verified]** |
| 2 | `run.py:153-155` | Modifiers are unbounded. `lam_home_mult: 3.0` is accepted and produced a "BET" at EV +81% with the maximum 5-unit stake. `KAIROS.md`, the README and `protocols/predict.md` all call them bounded. **[verified]** |
| 3 | `ledger.py:111-124, 207` | `record_result` does not check the id exists and does not reject a second result for the same id. Two results for one prediction doubled the profit and the scored-pick count. **[verified]** |
| 4 | `poisson.py:91` | Quarter lines are not handled. Over 2.25, 2.5 and 2.75 all return the identical probability; a quarter line should split the stake across the two neighbouring lines. This is the same error that produced the phantom +7.5% on Real Madrid Under in September. **[verified]** |
| 5 | `monte_carlo.py:49-50` | The simulation ignores rho, so it models a different distribution from the analytic one: draw 25.5% vs 27.9% for expected goals 1.5/1.2. The uncertainty noise also raises mean goals (1.526 vs 1.500 at confidence 45). **[verified]** |
| 6 | `sources/understat.py:89` + `elo.py:59` | Home advantage is counted twice. Two exactly average teams get 1.65 and 1.20 expected goals, a 2.85 total against a league average of 2.70. **[verified]** |
| 7 | `market.py:44` | `devig_power` accepts odds of 1.0 or below and returns `[1.0, 0.0, 0.0]` without an error. Convergence is not checked. **[verified]** |
| 8 | `elo.py:41` | The 0.15 floor on the weaker side's goals breaks the fixed total: at a 600-point gap the total becomes 3.16 instead of 2.70. **[verified]** |
| 9 | `edge.py:49-59` | With no sharp book present, "consensus" can be a single soft book and is still returned as a fair price (`n_books: 1`). With Pinnacle present there is no comparison against the other books, so a wrong Pinnacle line passes straight through. This is the cause of the +73% Craiova and +50% Shamrock mirages. **[verified]** |
| 10 | `run.py:204-216` | A "SPECULATIVE" verdict still leaves `bet: true` and a stake on the row. |
| 11 | `kelly.py:105` | Exposure is summed as if bets were independent. Home and Over 2.5 on one match, or two outcomes of the same market, are each sized at full stake. `knowledge/staking-kelly.md` says correlated bets count once. |

### 5b. Things that are fragile

- **`odds_api.fetch_raw` cache name ignores the market**, so fetching totals overwrites the 1X2 cache. Hit repeatedly in live sessions.
- **No quota tracking** for the 500 calls a month on the free Odds API tier.
- **`odds_api.find_event` matches by substring.** `("Manchester", "Chelsea")` returned Manchester United v Chelsea when Manchester City v Chelsea was also in the list; `"Malaga"` does not match `"Málaga"`. **[verified]**
- **`odds_api.parse_event` reads 1X2 only**, and treats any outcome name that is not a team as the draw. There is no parser for totals or handicaps.
- **`footballdata.download` always hits the network** even when the file is cached. Running ten seasons took over two minutes here, and the backtester cannot run offline except on the 10-row sample.
- **`config.CACHE_DIR` is `engine/fixtures`**, the same folder as the committed test fixtures. 38 cached files sit beside 3 tracked ones.
- **`MIN_EDGE` is defined twice** (`config.py` and `constants.py`), both 0.03 today.
- **`sources/clubelo.py`** uses plain http, puts the unsanitised club name into a file name, and raises on a network error although the docstring says it returns `None`.
- **`sources/understat.py`** sends a browser User-Agent to a site with no public API. Under the brief's rule this needs a terms check before it is used. I have not run it live and do not know if the page still has the data it parses.
- **Nothing in the repo is resumable or scheduled.** There is no state file, no lock, no job runner. That is expected at this stage and matters for Phase 4.

### 5c. Things the tests do not cover

- The backtester's arithmetic (the test only checks fields are present on a 10-row file).
- Modifier limits, `strengths`/`elo` input validation (a negative strength is accepted **[verified]**).
- Duplicate or unknown result ids.
- Quarter lines.
- Monte Carlo with rho ≠ 0.
- The cache-overwrite behaviour and any network failure.

### 5d. Claims in the docs that the code does not do

| Claim | Where | What the code does |
|---|---|---|
| "tests-104 passing"; 52/12/27/13 | README badge, lines 119, 188 | 108; 53/13/28/14 |
| Python 3.10+ (badge), 3.11+ (quickstart) | README lines 8, 131 | `pyproject.toml` says ≥3.10; CI runs 3.10–3.12; this PC runs 3.13 |
| Version 2.0.0 | README badge | `pyproject.toml` says 0.2.0 |
| "There are no API keys" | README line 24 | The sharp-line module needs an Odds API key (README line 156 says so) |
| "bounded qualitative modifiers" | README 144, KAIROS.md, predict.md | Unbounded (5a #2) |
| "Monte Carlo cross-check" | README 144 | Computed, never compared with anything (section 1, step 5) |
| Low confidence "widens the Monte Carlo tails and shrinks stakes automatically" | `protocols/predict.md` | Stakes shrink through Kelly scaling only; the simulation does not feed staking |
| Sharp-line comparison is "the v2.0 core" | README | Not called by any command (section 1) |
| Backtester lets you "prove the edge" | README line 40 | It cannot (section 3) |
| `market.py` offers "multiplicative/Shin alternatives" | `knowledge/market-reading.md` | No Shin method; "multiplicative" is an alias of proportional |
| Each prediction is logged "automatically at report time" | `ledger/calibration.md` | Nothing calls `log_prediction` |
| "Any line" O/U, Asian handicaps, correct score from the simulation | `knowledge/00-layer-stack.md` L12 | Three O/U lines, no handicaps, no quarter lines |
| `.env.example` lists the keys | `.env.example` | Lists `ODDS_API_KEY` only; `config.py` also reads `THE_ODDS_API_KEY` and `OPENWEATHER_API_KEY` (the latter is used by no module) |
| User's style is big Double Chance accumulators | `CLAUDE.md` (untracked) | Out of date since the move to value singles on 2026-09-26 |

---

## 6. What the ledger really shows

Output of `python engine/ledger.py` on 2026-10-02:

| Measure | Value |
|---|---|
| Predictions logged | 54 |
| Results recorded | 3 |
| Pending | 51 |
| Picks scored | 3 |
| Brier score | 0.1265 (3 picks) |
| Staked bets settled | 1 (lost; −0.59 units) |
| CLV observations | 0 |

Reading the 54 lines directly:

- **38 are passes, 10 bets, 5 speculative, 1 lean.** Ten carry a stake.
- **29 of 54 are USL competitions** and most of the rest are amateur or regional leagues (NPL Victoria, Austrian Regionalliga, Finnish fourth tier). `CLAUDE.md` now lists all of these as "no sharp line, always skip". Almost the whole ledger comes from Path A in early June.
- **The staked picks claim EVs of +47%, +39%, +56%, +48%, +19%, +15%, +12%, +7%.** By the project's own rule those are model errors, not edges. None of the eight has a recorded result.
- **Two entries are in-play bets**, which the project now rules out.
- **Five later entries were written by hand in a different shape** (a `result` field on the prediction, no `my_prob`). `compute_calibration` ignores them. Three of those have outcomes: two wins that were legs of one accumulator, and the Argentina loss.
- **One closing price exists** (Argentina, taken at 1.18, closing recorded as 1.43). It sits in the wrong field so it is not counted, and a move that large on a 1.18 favourite looks like an entry error. I have not verified it.
- **The accumulators from August and September are not in the ledger at all**, including the 13-leg win and the 12-of-13 loss. They exist only as chat history and one markdown file.
- **No entry has a bet-time timestamp, a sharp price at bet time, or a closing sharp price.** `ts` is a date.

Conclusion: the ledger shows that the loop can run. It contains no information about whether any Kairos method beats the closing line, and it cannot in its current shape.

---

## 7. What I did not check

- **Whether Claude Code can run unattended from a Windows scheduled task on this PC.** `claude` 2.1.287 is installed at `~/.local/bin/claude`; I did not test a headless run, login persistence, or behaviour after a reboot. The brief requires this before Phase 4 is designed.
- **Terms of use** for The Odds API, Football-Data.co.uk, Understat and Club Elo.
- **When Football-Data.co.uk collects its pre-match odds.** My reading of section 3 assumes Bet365 and Pinnacle pre-match columns are taken at the same time and closing columns at kickoff. That matches my memory of their notes file; I did not re-read it this session.
- **Live behaviour of the Understat and Club Elo adapters** (parser tests run on saved samples only).
- **The Odds API's current coverage** and remaining monthly quota.
- **CI status on GitHub.** I ran the suites locally only.
- **`report.py` line by line** beyond its structure and its CLI path.
- **Any market other than 1X2** in historical data. Football-Data files also carry O/U 2.5 and Asian handicap columns; I did not use them.
- **SportyBet's own historical prices.** No source for these exists in the repo.
