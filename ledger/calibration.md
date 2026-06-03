# Calibration Ledger

> Rolling scorecard. The feedback loop (L19) that makes the suit sharper over time. Updated after results come in.

## How to update this

The loop is tooled in `engine/ledger.py` (pure stdlib):
- Each prediction is appended to `predictions.jsonl` automatically at report time.
- See what's awaiting a result: `python engine/ledger.py pending`
- After a match: `python engine/ledger.py result <id> <home|draw|away|win|lose> [closing_odds] [score]`
  - Pass the final `score` (e.g. `2-1`) to settle **every** pick exactly — including O/U pushes on whole-number lines — not just the headline.
- Recompute the scorecard: `python engine/ledger.py` → prints Brier / hit-rate / ROI / CLV / buckets across **all** picks. Paste the headline numbers into the tables below.

## How to read this

- **Brier score** — lower is better (0 = perfect, 0.25 = coin-flip on a 2-way). Measures probability accuracy.
- **CLV (closing-line value)** — did we beat the closing price? Positive CLV is the single best long-run predictor of profit, even on losing bets.
- **ROI** — return on stake. The bottom line.
- **Hit rate** — % of picks that won. Useful but secondary to ROI (a 45% hit rate at good odds beats 60% at bad odds).

## Lifetime

_(As of 2026-06-03. Sample is tiny — directional only; no edge claim until n ≥ ~20 settled.)_

| Metric | Value | Sample (n) |
|--------|-------|-----------|
| Predictions logged | 10 | — |
| Results recorded | 3 | 3 |
| Brier score | 0.1265 | 3 scored picks |
| Hit rate | 0.0 | 1 staked |
| ROI | −1.00 | 0.59u staked |
| Profit | −0.59u | — |
| Avg CLV | — | 0 (no closing lines logged yet) |

**Settled so far:** Fortaleza 1–2 Vitória (home pick **lost**, only staked bet), Junior 3–0 Nacional (away lean wrong, no stake), Denmark 0–0 DR Congo (away lean wrong, no stake). Brier 0.13 ≈ a fair two-way score on a 3-pick sample; the one real bet lost. **Too small to conclude anything** — logged here only to prove the loop runs on real data.

## Per-league trust notes

_(Grows as samples accumulate. Note where the model over/under-rates: home edge, draw frequency, goal totals, etc.)_

## Per-market trust notes

_(1X2 vs O/U vs BTTS — which markets we have edge in and which to avoid.)_

## Calibration buckets (filled after ~20–30 results)

| Predicted prob band | Actual hit rate | n | Verdict |
|---------------------|-----------------|---|---------|
| 70–100% | — | — | — |
| 55–70% | — | — | — |
| 40–55% | — | — | — |
| 25–40% | — | — | — |
| 0–25% | — | — | — |

> Well-calibrated = actual hit rate inside each band ≈ the band's midpoint. Systematic gaps reveal bias to correct.
