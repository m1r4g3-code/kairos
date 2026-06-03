# Sub-protocol — contradiction-check.md (L17)

> The discipline gate where most "good predictors" fall apart. When the layers disagree, the correct move is usually **PASS**. A pass is a *successful* output of the pipeline — forcing a pick when signals conflict is how bankrolls die.

## Run this on every candidate value bet before it becomes a recommendation.

## The conflict matrix — does any layer argue *against* the pick?

| Layer | Supports the pick if… | Argues to PASS if… |
|---|---|---|
| Strength/form (L2,L6) | underlying numbers favor the side | results flatter a team the xG says is worse |
| Lineup (L4) | key players confirmed fit | a key CB/striker/keeper is out or doubtful |
| Tactics (L5) | matchup exploits opponent weakness | opponent's shape neutralizes the pick's strength |
| Context (L7) | motivation/rest favor the side | dead rubber, congestion, lookahead, hangover |
| Venue/env (L8,L9) | home edge / weather helps | bad weather kills the pick's style; weak home edge |
| Market (L10) | line moving *toward* my pick | line drifting *against* it (smart money fading me) |
| Confidence (L14) | high, data fresh | low, lineups not out, key data missing |

## Decision rules

1. **Unanimous or near-unanimous support** + EV clears threshold → **BET** at full sized stake.
2. **One soft dissent** (e.g. mild rotation risk) but everything else aligned → **BET, reduced stake + lower confidence**.
3. **A hard dissent** — line drifting against me, a key player out, or a fired trap (dead rubber / congestion / lookahead) — with no strong offset → **PASS**, even if the raw EV looked good.
4. **Layers genuinely split / I'm guessing** → **PASS**. If I can't articulate *why* I'm beating the market, there's no edge.
5. **Market already moved to my number** (line shortened to match my prob) → the edge is gone → **PASS**.

## Hard PASS triggers (any one → no bet)
- Lineups not yet released **and** the pick hinges on a specific player. → wait or pass.
- A Priority-1 fact couldn't be sourced and it's material. → confidence below floor → pass.
- Confidence below the floor (default 45). → engine already zeroes the stake; confirm pass.
- The "value" came from a single huge divergence I can't explain (see value-scan "suspect myself first").
- Dead-rubber / both-sides-low-motivation game → high variance → pass unless a *specific* edge survives.

## Framing the pass to the user
Be plain and unapologetic:
> "**Pass.** The model likes the home side, but the line is drifting toward the away team and their first-choice CB is out — when the market and the team news both lean against the model, the edge isn't real. No bet here."

A session that returns mostly passes is doing its job. The four hard rules exist precisely so the engine doesn't manufacture action.
