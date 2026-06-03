# Staking & Kelly (L16)

> Selection without stake sizing goes broke. This is where most "good predictors" lose. A 60%-accurate predictor flat-staking bad odds loses money; a 52%-accurate predictor with value + disciplined Kelly makes money.

## The Kelly criterion

For a single bet at decimal odds `d`, with my estimated win probability `p`:

```
b = d − 1                 # net fractional odds (profit per 1 staked)
q = 1 − p
f* = (b·p − q) / b        # full Kelly fraction of bankroll
```

- `f*` is the fraction of bankroll that maximizes long-run log growth.
- If `f* ≤ 0`, **there is no edge → do not bet** (this coincides with EV ≤ 0).

## Why we use *fractional* Kelly

Full Kelly is theoretically optimal but brutally volatile and assumes my `p` is exact — which it never is. My probability estimates have error, and Kelly is very sensitive to overestimated edges (it overbets). So:

- **Use ¼ to ½ Kelly.** Default **¼ Kelly** for normal confidence; up to ½ only when confidence is high and the edge is robust.
- **Hard cap:** never stake more than **5% of bankroll** on a single bet, regardless of what Kelly says.
- **Confidence scaling:** final stake = `fractional_kelly × (confidence/100)`. A 60-confidence pick gets 60% of the already-fractional stake.

## Worked example

Bankroll 100 units. My prob `p = 0.55`, odds `d = 2.10` (`b = 1.10`).

```
f* = (1.10·0.55 − 0.45) / 1.10 = (0.605 − 0.45)/1.10 = 0.141  → 14.1% full Kelly
¼ Kelly = 3.5%
× confidence 0.70 = 2.46%  → cap (5%) not hit
Stake ≈ 2.5 units
```

If instead odds were 1.70 (`b=0.70`, implied 58.8% > my 55%): `f* = (0.70·0.55 − 0.45)/0.70 = −0.093` → **negative → no bet.** Right outcome: the price is worse than my edge.

## Bankroll discipline (non-negotiable)

1. **Never chase losses.** Stakes are a function of edge, never of recent results. No "double up to recover."
2. **One bankroll, fixed unit.** Re-base the unit only on a schedule (e.g. weekly), never mid-tilt.
3. **Correlated bets count once.** Two bets on the same match (or same outcome via different markets) aren't independent — size them as one exposure, don't stack full stakes.
4. **Max simultaneous exposure** cap across all open bets (e.g. ≤ 15% bankroll live at once).
5. **Confidence floor:** below a confidence threshold (e.g. < 45), stake = 0 (pass), even if EV looks positive — the edge is inside the error bars.

## Default parameters (tunable in `engine/kelly.py`)

| Parameter | Default |
|---|---|
| Kelly fraction | 0.25 (¼) |
| Per-bet cap | 5% of bankroll |
| Max live exposure | 15% of bankroll |
| Confidence floor for any stake | 45 |
| Min edge (EV) to bet | +3% |

> These defaults are deliberately conservative. The goal is survival + compounding, not a fast bankroll. Surviving variance is the whole game.
