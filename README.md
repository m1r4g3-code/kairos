<div align="center">

# ⚡ KAIROS

**A predictor "mech suit" for an LLM — turn a bookmaker screenshot into calibrated, value-first football picks.**

[![Version](https://img.shields.io/badge/version-2.0.0-blueviolet.svg)](https://github.com/m1r4g3-code/kairos/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#)
[![Tests](https://img.shields.io/badge/tests-387%20passing-success.svg)](#testing)
[![CI](https://github.com/m1r4g3-code/kairos/actions/workflows/tests.yml/badge.svg)](https://github.com/m1r4g3-code/kairos/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](#license)

*Kairos (καιρός) — the opportune moment; the right time to act.*

</div>

---

## What is Kairos?

Kairos is **not a betting app and not an ML service.** It is a self-contained operating framework — **knowledge + reasoning protocols + a zero-dependency math toolkit + a feedback ledger + a backtest harness** — that an LLM *wears* to operate as a disciplined, well-calibrated football predictor.

There are no trained models, no servers and no background jobs. The Python here keeps the **probabilities honest** (calibration), the **staking safe** (Kelly with hard caps) and the **claims testable** (a walk-forward backtest with holdout seasons). One optional free API key (The Odds API) is needed for live sharp prices; everything else runs offline.

> **Workflow:** drop a bookmaker screenshot → the odds and fixtures are read off it → the soft price is compared with the sharp bookmaker's fair price → out comes a ranked set of **value bets with stakes**, or a disciplined **pass**.

### Recommend-only by design

Kairos **never places bets, stores credentials, or moves money.** It outputs picks and stakes; a human places them. Automating a bookmaker account violates their terms of service and creates a credential liability, so that path is deliberately excluded.

---

## Status of the evidence (read this first)

**Kairos does not claim an edge.** On the seasons held back for testing, its core strategy showed none. What has been measured so far:

| Question | Answer | Where |
|---|---|---|
| Does "bet where a soft book beats Pinnacle's fair price by 3%" pick good prices in history? | Over 2,976 bets (22 leagues, 2012–2024, Bet365 as the soft book) the closing-line value was **+2.3%** (95% interval +1.9 to +2.8). | [`docs/backtest-baseline.md`](docs/backtest-baseline.md) |
| Did it make money in that history? | Return per bet **+6.0%**, interval **−1.2% to +13.4%**. The interval includes zero. | same |
| Where does it come from? | Almost none from the five biggest leagues (CLV +0.8%, interval includes zero). | same |
| Does it hold on seasons kept aside (2024/25 and 2025/26)? | **No.** 169 bets, closing-line value **−0.1%** (−1.9 to +1.6). The edge seen in 2012–2024 was not there in the most recent seasons. | [`docs/engine-improvements.md`](docs/engine-improvements.md) |
| Is that proof for a different bookmaker today? | **No.** The two historical prices may not have been collected at the same minute, soft bookmakers limit winning accounts, and the live bookmaker has not been measured. A forward price census is running to measure it. | [`harness/census.py`](harness/census.py) |
| Does a team-rating model add anything to the sharp price? | No. Blended with Pinnacle's price, a goal-based rating got a fitted weight of 0.000 over 93,025 matches; a shots-based rating for totals lost 4.5% to the close. | [`docs/engine-improvements.md`](docs/engine-improvements.md) |
| Does an LLM beat the sharp closing price? | Public evidence says no. | [`docs/research.md`](docs/research.md) |

An earlier backtester in this repo ([`engine/backtest.py`](engine/backtest.py)) selected bets with the *closing* price and staked them at an earlier price. That is look-ahead; its output is not evidence and it now says so when run. The full audit is in [`docs/audit.md`](docs/audit.md).

---

## How it works

1. **Sharp-line comparison (the core).** Pull odds from many bookmakers via [The Odds API](https://the-odds-api.com), take Pinnacle's price, remove the margin (power method) to get a fair probability, and flag a soft book's price only when it pays more than that by a threshold. Without Pinnacle, at least three other bookmakers are needed for a consensus; one or two soft books are never treated as a reference. → [`engine/edge.py`](engine/edge.py)
2. **Cousin markets from the sharp line.** Fit expected goals to Pinnacle's 1X2 and total, then price other goal lines, Asian handicaps (with correct quarter-line settlement), double chance and draw-no-bet. On held-out seasons the fitted handicap price was as accurate as Bet365's own; a totals price fitted from 1X2 alone was not and is not offered. → [`engine/derive.py`](engine/derive.py)
3. **Model path (secondary).** A Poisson / Dixon-Coles engine turns expected goals into every market, with judgment modifiers bounded to ±20% and a fragility test on every candidate bet. → [`engine/run.py`](engine/run.py)
4. **Backtest harness.** Walk-forward over 183,000 matches, holdout seasons fixed in advance, every variant written down before it is run. → [`harness/`](harness/), [`research/hypotheses.md`](research/hypotheses.md)

```
Soft book 1.95 (51%)   vs   Pinnacle fair (54%)   →   +6% claimed edge
```

> **Honest ceiling:** in the backtest less than half of a claimed edge survived to the closing price. Soft-vs-sharp value is fragile: bookmakers limit winners, lines move, margins are thin. Profit is never guaranteed.

---

## Core principles (the four hard rules)

1. **Value is the only reason to bet.** `EV = (probability × decimal_odds) − 1`. If the edge doesn't beat the *de-vigged* market price, it's a pass — even on a likely outcome at short odds.
2. **Pass beats forcing.** When the analytical layers conflict, the default is **no bet**. A session of mostly passes is the system working correctly.
3. **Fractional Kelly, hard-capped.** Stake is a function of edge *and* odds, scaled by confidence, capped (≤5% of bankroll per match). Never chase losses.
4. **Calibration over vibes.** Probability numbers come from the math engine, not gut feel. Judgment *bounds-adjusts* the math; it never invents percentages.

---

## The anatomy — a 19-layer stack (L0 → L19)

| # | Layer | # | Layer |
|---|-------|---|-------|
| L0 | Raw reality (data atoms) | L10 | **Market intelligence** ⟵ gate |
| L1 | Feature engineering | L11 | Advanced stats (xG family) |
| L2 | Team strength | L12 | Simulation (Monte Carlo) |
| L3 | Player impact | L13 | Probability + calibration |
| L4 | Lineup / availability | L14 | Uncertainty / confidence |
| L5 | Tactical matchup | L15 | **Value detection** ⟵ gate |
| L6 | Form (opponent-adjusted) | L16 | **Staking (Kelly)** ⟵ gate |
| L7 | Context & traps | L17 | **Contradiction / decision** ⟵ gate |
| L8 | Venue / home advantage | L18 | God-mode signals (ref / manager / news) |
| L9 | Environment (weather/pitch) | L19 | Feedback & calibration loop |

Full reference: [`knowledge/00-layer-stack.md`](knowledge/00-layer-stack.md). The layer stack describes the reasoning framework; the measured results above are what the numbers support today.

---

## Repository layout

```
Kairos/
├── KAIROS.md                # operating charter — loaded first every session
├── knowledge/               # the anatomy, playbooks and priors
├── protocols/               # step-by-step reasoning runbooks
├── core/                    # sport-agnostic, reusable by other agents (stdlib only)
│   ├── staking.py            #   EV + fractional Kelly + caps (one event = one position)
│   ├── devig.py              #   de-vig: proportional, power, Shin
│   ├── ledger.py             #   predictions → results → Brier / ROI / CLV; pluggable settlement
│   ├── metrics.py            #   log loss, Brier, RPS, buckets, bootstrap intervals
│   ├── runlog.py             #   append-only log of every variant run
│   └── test_core.py          #   12 checks, including "imports no football code"
├── engine/                  # football: math + data adapters (kelly/market/ledger are shims to core)
│   ├── constants.py          #   all tunable parameters in one place
│   ├── config.py             #   .env loader (Odds API key); gitignored secret
│   ├── settle.py             #   football settlement rules for the ledger
│   ├── edge.py               #   sharp-line comparison (the core)
│   ├── derive.py             #   goal lines, Asian handicaps, double chance from the sharp line
│   ├── poisson.py            #   Poisson + Dixon-Coles → score matrix → markets
│   ├── elo.py                #   Elo / strengths → expected goals
│   ├── monte_carlo.py        #   simulation check (same rho as the analytic engine)
│   ├── run.py                #   model-path orchestrator (+ fragility test)
│   ├── report.py             #   plain-English card renderer
│   ├── backtest.py           #   OLD backtester, has look-ahead, kept for reference only
│   ├── sources/              #   odds_api (needs key), clubelo, footballdata,
│   │                         #   understat (parser only; live fetch disabled, robots.txt)
│   ├── fixtures/             #   made-up *_sample.* files so tests run offline
│   └── test_*.py             #   117 + 19 + 37 + 16 checks
├── harness/                 # the trustworthy backtest (stdlib only)
│   ├── fd_fetch.py           #   polite, resumable download of Football-Data files
│   ├── fd_data.py            #   loader: PreMatch / Post split, holdout guard
│   ├── walk.py               #   walk-forward runner + leak check
│   ├── score.py              #   settles bets, CLV, collects forecasts
│   ├── ratings.py            #   online team ratings + log pool (tested, not adopted)
│   ├── strategies.py         #   baseline and variants
│   ├── run_baseline.py run_a1.py … run_a56.py run_b0_holdout.py
│   ├── census.py             #   forward log of soft-book prices against Pinnacle
│   └── test_harness.py       #   117 checks
├── paper/                   # forward paper-trading loop (Phase 4): main.py, jobs, feeds
│   └── test_paper.py         #   offline tests with fake feeds, clock and Claude
├── research/                # holdout.json, hypotheses.md, runs.jsonl, results/
├── docs/                    # audit, research review, backtest baseline, improvements
├── ledger/                  # predictions, results, census
└── output-templates/        # the report format emitted in chat
```

---

## Quickstart

Requires **Python 3.10+** and nothing else.

```bash
python engine/test_engine.py              # → ALL TESTS PASSED
python engine/edge.py                     # sharp-line demo on made-up prices
python engine/derive.py                   # cousin-market demo
python engine/run.py engine/example_spec.json   # model path

# the backtest (downloads ~570 small CSV files once, slowly; resumable)
python harness/fd_fetch.py
python harness/run_baseline.py
```

Live sharp odds need one free signup: copy `.env.example` to `.env` and add the key. The free tier is 500 credits a month; a UK+EU 1X2 request costs 2.

---

## The feedback loop

```bash
python engine/ledger.py result <prediction_id> <home|draw|away> <closing_odds>
python engine/ledger.py                   # Brier, ROI, CLV, raw-vs-adjusted, buckets
python harness/census.py summary          # soft-book gap share and CLV
```

A result for an unknown id, or a second result for the same id, is refused. **Closing-line value** is the primary measure; win rate is not reported as a headline.

---

## Testing

**387 deterministic checks** across seven suites, run on every push via [GitHub Actions](.github/workflows/tests.yml) (Python 3.10 / 3.11 / 3.12). Everything runs offline against made-up fixtures — no network, no key.

```bash
python engine/test_engine.py    # math, de-vig, derive, staking, orchestration
python engine/test_ledger.py    # persistence, settling, result validation
python engine/test_edge.py      # sharp reference, parsers, event matching
python engine/test_sources.py   # data-adapter parsers
python harness/test_harness.py  # loader, walk-forward, leak tests, ratings, census
python core/test_core.py        # the sport-agnostic package on a non-football market
python paper/test_paper.py      # paper trading: restarts, budget, closes, settlement, judgment
```

The harness leak tests check that a strategy never sees a result dated on or after the day its odds were collected, and that scrambling every result and closing price changes no decision.

---

## ⚠️ Responsible gambling & disclaimer

This project is for **educational and research purposes**. Betting involves financial risk and **no system — including this one — guarantees profit**. The measured results above do not establish a profitable strategy.

- **18+ (or the legal age in your jurisdiction). Bet only what you can afford to lose.**
- Kairos is **recommend-only**; the user is solely responsible for any wager they place.
- If gambling stops being fun, seek help (e.g. BeGambleAware, GamCare, or your local service).

Data: historical results and odds come from [Football-Data.co.uk](https://www.football-data.co.uk) and are not redistributed here; the repo stores only checksums.

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE).

<div align="center">
<sub>Built as a reasoning framework, not a black box — every number is auditable against the market.</sub>
</div>
