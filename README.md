<div align="center">

# ⚡ KAIROS

**A predictor "mech suit" for an LLM — turn a bookmaker screenshot into calibrated, value-first football picks.**

[![Version](https://img.shields.io/badge/version-2.0.0-blueviolet.svg)](https://github.com/m1r4g3-code/kairos/releases)
[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#)
[![Tests](https://img.shields.io/badge/tests-104%20passing-success.svg)](#testing)
[![CI](https://github.com/m1r4g3-code/kairos/actions/workflows/tests.yml/badge.svg)](https://github.com/m1r4g3-code/kairos/actions/workflows/tests.yml)
[![License](https://img.shields.io/badge/license-MIT-lightgrey.svg)](#license)

*Kairos (καιρός) — the opportune moment; the right time to act.*

</div>

---

## What is Kairos?

Kairos is **not a betting app and not an ML service.** It is a self-contained operating framework — **knowledge + reasoning protocols + a zero-dependency math toolkit + a feedback ledger** — that an LLM *wears* to operate as a disciplined, well-calibrated football predictor.

There are no API keys, no trained models, no servers, and no background jobs. The reasoning engine is the model itself; the Python in this repo exists only to keep the **probabilities honest** (calibration) and the **staking safe** (Kelly with hard caps).

> **Workflow:** drop a bookmaker screenshot → the odds + fixtures are read off it → gaps (form, lineups, injuries, context, weather, referee) are enriched from the open web → the layered analysis runs (math for calibration, judgment for tactics/context/market) → out comes a ranked set of **value bets with stakes**, or a disciplined **pass**.

### Recommend-only by design

Kairos **never places bets, stores credentials, or moves money.** It outputs picks and Kelly-sized stakes; a human places them. Automating a bookmaker account violates their terms of service (account bans, voided winnings) and creates a credential/security liability — so that path is deliberately excluded.

---

## ⚡ New in v2.0 — the sharp-line edge

v1 estimated goals by judgment, then priced markets from scratch. The honest weakness: **the inputs were guesses.** v2.0 fixes the input layer with a proven retail approach — **don't out-predict the market, beat the soft book against the sharp one.**

1. **Sharp-line comparison (the core).** Pull odds from many bookmakers via [The Odds API](https://the-odds-api.com), take the **sharp** book (Pinnacle / sharp consensus), de-vig it to the *true* probability, and flag value wherever a soft book (e.g. SportyBet) **pays more than the sharp price says it should**. → [`engine/edge.py`](engine/edge.py)
2. **Data-fed engine (cross-check).** Real **xG** ([Understat](https://understat.com)) and **Elo** ([Club Elo](http://clubelo.com)) feed the existing Poisson engine — grounding the model in data, not vibes. → [`engine/sources/`](engine/sources/)
3. **Backtester (the honesty check).** Replay the soft-vs-sharp strategy on free historical results + closing odds ([Football-Data.co.uk](https://www.football-data.co.uk)) and print **ROI / hit-rate / CLV** — prove the edge *before* risking money or paying for anything. → [`engine/backtest.py`](engine/backtest.py)

**Still keyless-friendly:** Understat, Club Elo, and Football-Data need **no key**. Only the sharp-line module needs one free signup ([The Odds API](https://the-odds-api.com), 500 calls/mo). All HTTP is pure-stdlib `urllib`; the key lives in a gitignored `.env` (see [`.env.example`](.env.example)). Tests run **fully offline** against committed sample fixtures.

```
SportyBet 1.95 (51%)   vs   Pinnacle de-vigged (54%)   →   +6% value, BET
```

> **Honest ceiling:** soft-vs-sharp value is real but fragile (books limit winners, lines move, margins are thin). v2.0 makes the inputs **data-grounded and provable** — a big upgrade over guesses — but profit is never guaranteed. The backtest is the truth check.

---

## Core principles (the four hard rules)

1. **Value is the only reason to bet.** `EV = (my_prob × decimal_odds) − 1`. If your edge doesn't beat the *de-vigged* market price, it's a pass — even on a likely outcome at short odds.
2. **Pass beats forcing.** When the analytical layers conflict, the default is **no bet**. A session of mostly passes is the system working correctly.
3. **Fractional Kelly, hard-capped.** Stake is a function of edge *and* odds, scaled by confidence, capped (≤5% bankroll). Never flat-stake bad odds; never chase losses.
4. **Calibration over vibes.** Probability numbers come from the math engine, not gut feel. Judgment *bounds-adjusts* the math; it never invents percentages.

---

## The anatomy — a 19-layer stack (L0 → L19)

Elite prediction is built from the atomic data level up. Nothing above is trustworthy without the layers below it. The gates that separate profitable from break-even are **market intelligence (L10), value detection (L15), staking (L16), and the contradiction check (L17)**.

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

Full reference: [`knowledge/00-layer-stack.md`](knowledge/00-layer-stack.md).

---

## Repository layout

```
Kairos/
├── KAIROS.md                # operating charter — loaded first every session
├── knowledge/               # the durable anatomy + playbooks + seeded priors
│   ├── 00-layer-stack.md     #   the full L0–L19 reference
│   ├── tactics-playbook.md   #   style-vs-style matchup heuristics
│   ├── market-reading.md     #   de-vig, implied prob, CLV, line movement
│   ├── staking-kelly.md      #   fractional Kelly rules, caps, bankroll discipline
│   ├── context-and-traps.md  #   dead rubbers, congestion, rotation, motivation
│   └── reference-tables.md   #   league base rates, home-advantage priors
├── protocols/               # step-by-step reasoning runbooks
│   ├── predict.md            #   MASTER runbook: screenshot → picks
│   ├── screenshot-intake.md  #   parsing a bookmaker slip
│   ├── enrich.md             #   what to research, in priority order
│   ├── value-scan.md         #   EV scan + ranking
│   └── contradiction-check.md#   the pass/play decision gate
├── engine/                  # zero-dependency local math + data adapters
│   ├── constants.py          #   all tunable parameters, documented in one place
│   ├── config.py             #   .env loader (Odds API key); stdlib, gitignored secret
│   ├── poisson.py            #   Poisson + Dixon-Coles → score matrix → all markets
│   ├── elo.py                #   Elo + strength → expected goals (lambdas)
│   ├── monte_carlo.py        #   match simulation with lambda uncertainty
│   ├── market.py             #   de-vig odds → fair implied probabilities
│   ├── kelly.py              #   EV detection + fractional-Kelly staking + guards
│   ├── edge.py               #   ⚡ sharp-line comparison (the v2.0 core)
│   ├── backtest.py           #   ⚡ soft-vs-sharp backtester → ROI/CLV/hit-rate
│   ├── run.py                #   orchestrator entry point (+ fragility/sensitivity)
│   ├── report.py             #   plain-English card renderer (+ SHARP% column)
│   ├── ledger.py             #   the feedback loop (Brier / ROI / CLV / calibration)
│   ├── sources/             #   ⚡ data adapters (all stdlib urllib)
│   │   ├── odds_api.py        #     The Odds API → many books incl Pinnacle (needs key)
│   │   ├── clubelo.py         #     Club Elo ratings → elo spec (keyless)
│   │   ├── understat.py       #     Understat xG → strengths spec (keyless, big-5)
│   │   └── footballdata.py    #     Football-Data.co.uk history+odds (keyless, backtest)
│   ├── fixtures/            #   committed *_sample.* files so tests run fully offline
│   ├── test_engine.py        #   52 deterministic engine tests
│   ├── test_ledger.py        #   12 persistence/calibration tests
│   ├── test_edge.py          #   27 sharp-line + backtest tests
│   └── test_sources.py       #   13 data-adapter parser tests
├── ledger/                  # predictions → results → rolling calibration
└── output-templates/        # the report format emitted in chat
```

---

## Quickstart

Requires **Python 3.11+** and nothing else — the engine is pure standard library.

```bash
# 1. Run the engine test suite (should print: ALL TESTS PASSED)
python engine/test_engine.py

# 2. Run a prediction on a sample match spec
python engine/run.py engine/example_spec.json

# 3. Pipe your own spec (schema documented in engine/run.py)
python engine/run.py my_match.json
```

A match spec supplies the expected-goals source (direct `lambdas`, relative `strengths`, or `elo`), bounded qualitative `modifiers`, a `confidence` score, the bankroll, and the bookmaker `odds`. The engine returns a calibrated distribution, a Monte Carlo cross-check, and a ranked value table with Kelly stakes.

### Sharp-line edge (v2.0)

```bash
# Compare a soft book to the sharp price (works offline on the sample fixture)
python engine/edge.py

# Prove it on real history — prints ROI / hit-rate / CLV (needs no key)
python engine/backtest.py E0 2425          # download EPL 2024/25 and replay
python engine/backtest.py --fixture fd_sample.csv   # offline demo

# Live sharp odds (after one free signup): copy .env.example → .env, add ODDS_API_KEY
```

### How it computes a prediction

```
screenshot → de-vig → enrich → build spec → run engine →
value scan → contradiction gate → stake → report → log
```

Math owns the numbers (L2, L8–L13, L15, L16); judgment owns the context (L3–L7, L17, L18) and the discipline to pass.

---

## The feedback loop

Every prediction is logged; once a result is known, the loop scores it:

```bash
# record an outcome (+ closing odds for closing-line value)
python engine/ledger.py result <prediction_id> <home|draw|away> <closing_odds>

# recompute the scorecard: Brier score, hit-rate, ROI, CLV, calibration buckets
python engine/ledger.py
```

**Closing-line value (CLV)** — consistently beating the closing price — is the single best long-run indicator of edge, even on losing bets. It is tracked alongside ROI in [`ledger/calibration.md`](ledger/calibration.md).

---

## Testing

**104 deterministic assertions** across four suites, run automatically on every push via [GitHub Actions](.github/workflows/tests.yml) (Python 3.10 / 3.11 / 3.12). Everything runs **fully offline** against committed sample fixtures — no network, no API key.

`engine/test_engine.py` (the math + orchestration) covers:
- probability conservation **and non-negativity** (a bad `rho` can't silently emit negative cells),
- Dixon-Coles low-score correction, and out-of-band `rho` rejection,
- Over/Under **push handling** on whole-number lines (over + under + push = 1.0),
- analytic vs. Monte Carlo agreement within sampling error,
- de-vig sanity for both the proportional and power methods,
- Kelly never exceeding the per-bet cap, the combined-exposure cap, EV signs, confidence floor,
- end-to-end value/pass/**fragile** verdicts, input validation, and surfaced unmodelled markets.

`engine/test_ledger.py` (the persistence/calibration layer) covers:
- schema validation and duplicate-ID auto-versioning (no silent overwrite),
- **multi-pick scoring** (every pick, not just the headline) and score-based settling,
- O/U push voiding, ROI/Brier/CLV arithmetic, and corrupt-line resilience.

`engine/test_edge.py` (the v2.0 sharp-line core) covers:
- sharp-book selection + consensus fallback, de-vig to true probability,
- value detection (soft beats sharp), engine-vs-sharp agreement cross-check,
- The Odds API event parsing, and the soft-vs-sharp **backtester** (ROI/CLV/threshold sweep).

`engine/test_sources.py` (the keyless data adapters) covers:
- Club Elo CSV parsing, Understat xG decode → attack/defence strengths,
- and that the data-fed `strengths`/`elo` specs run end-to-end through the engine.

```bash
python engine/test_engine.py   # → ALL TESTS PASSED
python engine/test_ledger.py   # → ALL LEDGER TESTS PASSED
python engine/test_edge.py     # → ALL EDGE TESTS PASSED
python engine/test_sources.py  # → ALL SOURCE TESTS PASSED
```

> **On calibration honesty:** the rolling Brier / ROI / CLV scorecard lives in [`ledger/calibration.md`](ledger/calibration.md) and is computed from *real* settled results. The sample is currently tiny — **Kairos makes no edge claim until enough results accumulate (≈20+) to show positive closing-line value.** Confident-looking probabilities are also fragility-tested (`sensitivity` in every run): if a "value" bet evaporates under a ±15% shift in the input expected-goals, it is downgraded to *speculative* rather than presented as an edge.

---

## ⚠️ Responsible gambling & disclaimer

This project is for **educational and research purposes**. Betting involves financial risk and **no system — including this one — guarantees profit**. Outcomes in football are inherently uncertain; the goal here is *disciplined, value-based decision-making and bankroll survival*, not a money machine.

- **18+ (or the legal age in your jurisdiction). Bet only what you can afford to lose.**
- Kairos is **recommend-only**; the user is solely responsible for any wager they place.
- If gambling stops being fun, seek help (e.g. BeGambleAware, GamCare, or your local service).

---

## License

Released under the **MIT License**. See [`LICENSE`](LICENSE).

<div align="center">
<sub>Built as a reasoning framework, not a black box — every number is auditable against the market.</sub>
</div>
