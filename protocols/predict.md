# MASTER RUNBOOK — predict.md

> The end-to-end flow Kairos runs for every prediction: **screenshot → calibrated picks (or pass)**. Follow it in order. Each step links to its detailed sub-protocol. Do not skip the gates (L10, L15, L16, L17).

---

## Preconditions
- I have loaded `KAIROS.md` (the charter + four hard rules).
- The user has dropped a **SportyBet screenshot** (or invoked `/predict`).
- Today's date is known (for staleness/lineup-timing judgments).

---

## Step 1 — Intake the screenshot  (L0, L10)
Follow `protocols/screenshot-intake.md`.
- Read every fixture, market, selection, and **decimal odds** off the image.
- Capture kickoff date/time and booking code if visible.
- Echo back a clean parse so the user can correct OCR errors before I commit.

**Output of step:** a structured list of `{match, market, selection: odds}`.

---

## Step 2 — De-vig the market  (L10)
For each market, run `engine/market.py` (`market_view`).
- Get fair (de-vigged) probabilities + overround.
- These fair probs are **the number I must beat**. Note any market with a fat overround (demand more edge there).

---

## Step 3 — Enrich  (L0, L3, L4, L7, L8, L9, L11, L18)
Follow `protocols/enrich.md` — priority-ordered, **time-boxed**.
- Confirmed/predicted lineups, injuries, suspensions (L4) — highest priority.
- Recent opponent-adjusted form + xG (L6, L11).
- Motivation/context/traps + congestion (L7).
- Venue/home edge, weather (L8, L9).
- God-mode if time allows: referee, manager tendencies, micro-matchups, news (L18).
- **Declare what couldn't be sourced** and let it lower confidence. Never fabricate.

---

## Step 4 — Build the engine spec  (L2, L5, L6, L13)
Turn enrichment into a `run.py` spec (schema in `engine/run.py` header):
1. **Base lambdas:** prefer `strengths` (from xG/goal data) or `elo` if that's all I have; fall back to the league row in `knowledge/reference-tables.md`.
2. **Home advantage:** set `home_mult` from the venue prior (default ×1.15).
3. **Qualitative modifiers:** translate tactics (L5), lineup (L4), context (L7), weather (L9), god-mode (L18) into **bounded** `lam_home_mult` / `lam_away_mult` — judgment *nudges*, it does not invent percentages. Keep each nudge small (≈ ≤ ±0.3 goals total) and write a one-line `note` explaining them.
4. **Confidence (L14):** score 0–100 from data freshness, lineup certainty, and how much the layers agree. Low confidence widens the Monte Carlo tails and shrinks stakes automatically.
5. Attach the screenshot **odds** and the **bankroll**.

---

## Step 5 — Run the engine  (L11, L12, L13, L15, L16)
```
python engine/run.py spec.json
```
Returns: the calibrated distribution, a Monte Carlo cross-check, and a **value table** (EV + Kelly stake per selection), plus a verdict.

**Sanity checks before trusting it:**
- Probabilities sum to 1; draw prob in the ~18–34% band unless there's a reason.
- Analytic and Monte Carlo agree within sampling error.
- If my probs diverge wildly from the de-vigged market, **suspect myself first** (missed team news?) before calling it value (see `protocols/value-scan.md`).

---

## Step 6 — Value scan  (L15)
Follow `protocols/value-scan.md`. Rank selections by edge. A bet exists only where my edge beats the price by the min threshold (+3% EV default).

---

## Step 7 — Contradiction / decision gate  (L17)  ← mandatory
Follow `protocols/contradiction-check.md`.
- If the layers conflict (model loves a side the lineup/context/market argue against), **PASS**.
- A clean pass is a successful outcome, not a failure. Most slips should yield few or zero bets.

---

## Step 8 — Stake  (L16)
The engine already sized each bet with fractional Kelly, capped, confidence-scaled, and exposure-limited across the slip. Confirm stakes respect the caps in `knowledge/staking-kelly.md`. Never chase; never override the cap upward.

---

## Step 9 — Report  (output)
Emit `output-templates/prediction-report.md`:
- **Verdict first** (BET … / PASS), then the my-prob-vs-market table, then the "why," the contradiction check, and the staking line.
- Always show the de-vigged market prob beside mine so the edge is auditable.
- State confidence and what's dragging it.
- Remind: **you place the bet manually; Kairos never bets for you.**

---

## Step 10 — Log  (L19)
Append the prediction to `ledger/predictions.jsonl` (see `protocols/` logging note below) with inputs, probs, stake, confidence, and rationale. After the match, the result + closing line go to `ledger/results.jsonl` and `ledger/calibration.md` updates — that's the loop that sharpens the suit.

### Ledger record shape (one JSON object per line)
```json
{"id":"2026-06-03-ARS-CHE","ts":"2026-06-03T12:00:00Z","match":"Arsenal vs Chelsea",
 "league":"Premier League","lambdas":{"home":1.6,"away":1.1},"confidence":68,
 "picks":[{"market":"1x2","selection":"home","odds":2.10,"my_prob":0.55,
           "fair_prob":0.476,"ev":0.155,"stake_units":2.5}],
 "verdict":"BET","note":"home press edge; Chelsea CB out","result":null,"closing_line":null}
```

---

## The whole flow in one breath
intake → de-vig → enrich → build spec → run engine → value scan → contradiction gate → stake → report → log. **Math owns the numbers; I own the judgment and the discipline to pass.**
