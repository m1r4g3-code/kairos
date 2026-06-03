# Market Reading (L10)

> The gate most people skip. The bookmaker's price already embeds a huge amount of information. To win, I must be **more right than the price**, not just right. This doc is how I read a SportyBet slip and turn odds into the number I must beat.

## Decimal odds → implied probability

`implied_prob = 1 / decimal_odds`

Example: odds 2.10 → 47.6% implied.

## The overround (vig / margin) and de-vigging

Raw implied probabilities across a market **sum to > 100%** — the excess is the bookmaker's margin (overround / vig). SportyBet's football 1X2 margin is typically **~5–8%**.

```
overround = Σ (1/odds_i) − 1
```

To get the market's *honest* view, **de-vig**. Default method = proportional normalization:

```
fair_prob_i = (1/odds_i) / Σ(1/odds_j)
```

(`engine/market.py` also offers the multiplicative/Shin alternatives. Proportional is fine for casual slips; note that it slightly over-shrinks longshots — favorite-longshot bias — so treat de-vigged longshot probs as a touch high.)

**The de-vigged probability is my benchmark.** My model's job is to find where my probability is meaningfully higher than the fair price implies.

## What a SportyBet screenshot gives me

- **Selections + decimal odds** for each market shown (1X2, Double Chance, O/U 2.5 etc., BTTS, sometimes correct score / handicaps).
- The **fixture + date** (and sometimes kickoff time) — anchors the enrichment search.
- The **booking code / bet ID** if present — useful for the user to re-find the slip.

> A high overround on a market (e.g. 12%+ on correct-score) means the price is stacked against me — demand a bigger edge there, or skip it.

## Line movement (when findable via web)

- **Opening vs current:** which way has the price drifted since it opened?
- **Steam move:** a sharp, sudden shortening across books = sharp money; respect it. Fading steam needs a strong reason.
- **Drift:** a price lengthening into kickoff often signals bad team news (rotation, late injury) — cross-check L4.
- **Closing line:** the most accurate price of all. Beating it (positive **CLV**) is the best long-run profit signal there is — I log it in `ledger/`.

## How the market read changes the decision

1. Compute de-vigged market probs from the screenshot.
2. Compare to my model probs.
3. **Small divergence (< ~2–3% edge):** the market knows what I know → likely a pass.
4. **Large divergence:** *first suspect myself.* Is there team news the price already reflects that I missed? Only after ruling that out is it value.
5. If line movement contradicts my lean (price drifting away from my pick), lower confidence and likely pass (feeds L17).

## Why recommend-only (the SportyBet posture)

I read the screenshot and return picks; the user places them. I do **not** automate SportyBet, because:
- No official betting API exists; placement means scripting the site/app, which **violates SportyBet's ToS** → account ban, **voided winnings**, frozen funds.
- Auto-login requires storing the password + handling OTP/2FA → a security liability on real money.
- An unsupervised stake bot can drain a bankroll on a single logic bug.
Screenshot-in / picks-out carries none of that risk and keeps the human in control of every wager.
