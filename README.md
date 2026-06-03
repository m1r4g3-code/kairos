<div align="center">

# ⚡ KAIROS

**A predictor "mech suit" for an LLM — turn a bookmaker screenshot into calibrated, value-first football picks.**

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)
[![Dependencies](https://img.shields.io/badge/dependencies-zero-brightgreen.svg)](#)
[![Tests](https://img.shields.io/badge/tests-58%2F58%20passing-success.svg)](#testing)
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
├── engine/                  # zero-dependency local math (the calibration core)
│   ├── constants.py          #   all tunable parameters, documented in one place
│   ├── poisson.py            #   Poisson + Dixon-Coles → score matrix → all markets
│   ├── elo.py                #   Elo + strength → expected goals (lambdas)
│   ├── monte_carlo.py        #   match simulation with lambda uncertainty
│   ├── market.py             #   de-vig odds → fair implied probabilities
│   ├── kelly.py              #   EV detection + fractional-Kelly staking + guards
│   ├── run.py                #   orchestrator entry point (+ fragility/sensitivity)
│   ├── ledger.py             #   the feedback loop (Brier / ROI / CLV / calibration)
│   ├── test_engine.py        #   46 deterministic engine tests
│   └── test_ledger.py        #   12 persistence/calibration tests
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

**58 deterministic assertions** across two suites, run automatically on every push via [GitHub Actions](.github/workflows/tests.yml) (Python 3.10 / 3.11 / 3.12).

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

```bash
python engine/test_engine.py   # → ALL TESTS PASSED
python engine/test_ledger.py   # → ALL LEDGER TESTS PASSED
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
