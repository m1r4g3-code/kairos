# Prediction Report Template

> The exact format Kairos emits in chat. Keep it scannable: verdict first, evidence second, the math audit last. Omit sections that don't apply, but never hide low confidence or missing data.

---

## 🎯 VERDICT — {Home} vs {Away}

**{BET: <selection> @ <odds> · stake X.X units}**  _or_  **{PASS — no value}**

> One-line reason. e.g. "Home priced at 2.10 but my model + confirmed XI put them at 2.6% edge — thin, single unit." / "Model likes the draw but it's a dead rubber with both sides rotating — pass."

| | |
|---|---|
| Competition | {league, round} |
| Kickoff | {date/time} |
| Confidence | {0–100} ({what's driving it / dragging it}) |
| Data freshness | {lineups confirmed? injuries current? referee known?} |

---

## 📊 Probabilities — mine vs the market

| Outcome | My prob | Market (de-vigged) | Odds (SportyBet) | Edge (EV) | Verdict |
|---------|---------|--------------------|--------------------|-----------|---------|
| Home win | — | — | — | — | — |
| Draw | — | — | — | — | — |
| Away win | — | — | — | — | — |

_Overround on this market: {x%}. Predicted scoreline: {H}–{A} (λ_home={..}, λ_away={..})._

Other markets scanned (O/U, BTTS, etc.): _{ranked by edge, or "none with value"}._

---

## 🧠 Why — the layers that moved the number

- **Strength / form (L2,L6):** {opponent-adjusted read}
- **Lineups / availability (L4):** {key ins/outs and their impact}
- **Tactical matchup (L5):** {style vs style}
- **Context / traps (L7):** {motivation, congestion, dead-rubber check}
- **Venue / environment (L8,L9):** {home edge, weather/pitch}
- **God-mode (L18):** {referee, manager, micro-matchup, news — if found}
- **Market read (L10):** {line movement, where the market sits vs me}

---

## ⚖️ Contradiction check (L17)

{Which layers agree, which conflict, and the resolution. If conflict was decisive → PASS and say so plainly.}

---

## 💰 Staking (L16)

- Bankroll assumed: {units}
- Kelly fraction: {¼/½} Kelly = {f}
- Recommended stake: **{X.X units}** (capped at {cap}, scaled by confidence)
- _You place this manually on SportyBet. Kairos does not bet for you._

---

## 📝 Logged

Prediction appended to `ledger/predictions.jsonl` as `{id}` for calibration once the result is known.
