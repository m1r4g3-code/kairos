# Calibration Ledger

> Rolling scorecard. The feedback loop (L19) that makes the suit sharper over time. Updated after results come in.

## How to update this

The loop is tooled in `engine/ledger.py` (pure stdlib):
- Each prediction is appended to `predictions.jsonl` automatically at report time.
- After a match: `python engine/ledger.py result <id> <home|draw|away|win|lose> <closing_odds>`
- Recompute the scorecard: `python engine/ledger.py` → prints Brier / hit-rate / ROI / CLV / buckets. Paste the headline numbers into the tables below.

## How to read this

- **Brier score** — lower is better (0 = perfect, 0.25 = coin-flip on a 2-way). Measures probability accuracy.
- **CLV (closing-line value)** — did we beat the closing price? Positive CLV is the single best long-run predictor of profit, even on losing bets.
- **ROI** — return on stake. The bottom line.
- **Hit rate** — % of picks that won. Useful but secondary to ROI (a 45% hit rate at good odds beats 60% at bad odds).

## Lifetime

| Metric | Value | Sample (n) |
|--------|-------|-----------|
| Predictions logged | 0 | — |
| Results recorded | 0 | — |
| Brier score | — | — |
| Hit rate | — | — |
| ROI | — | — |
| Avg CLV | — | — |

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
