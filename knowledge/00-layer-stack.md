# The Kairos Layer Stack — Complete Predictor Anatomy (L0 → L19)

> The full anatomy of an elite football predictor, from the atomic data level up to god-mode. Bottom-up: **nothing above is trustworthy without the layers below it.** Most losing bettors live at L0–L6 only. The gates that separate elite from break-even are **L10 (market), L15 (value), L16 (staking), and L17 (pass-discipline)**.

**Owner legend:** 🧮 local math (`engine/`) · 🧠 my judgment · 📷 from screenshot · 🌐 web search

---

## L0 — Raw Reality (the atoms) 📷🌐

The irreducible inputs. Everything else is *derived* from these. Garbage here propagates everywhere — most of the edge in elite prediction is built here, in the quality of the representation, not in the model at the end.

**Match atoms:** competition, round/matchday, date & kickoff time, home/away designation, venue, stakes (cup/league/playoff).
**Result atoms (per past match, both teams):** goals for/against, shots, shots on target, possession %, corners, fouls, yellow/red cards, xG/xGA.
**Player atoms:** fitness status, injuries, suspensions, minutes-load (last 7/14 days), position, recent starts vs benchings.
**Team atoms:** current formation, manager, squad depth, recent transfers.
**Environment atoms:** weather, temperature, wind, precipitation, pitch type/condition, altitude, travel distance for the away side.
**Market atoms:** SportyBet odds for every market on the slip (📷 — handed to me free), plus opening & current line elsewhere if findable (🌐).

> **Sourcing rule:** odds + fixtures come from the screenshot; the rest is web-enriched, priority-ordered and time-boxed (see `protocols/enrich.md`). What can't be sourced is declared, not invented.

---

## L1 — Feature Engineering 🧮🧠

Atoms mean nothing raw; convert them into *signals*.
- Raw "Arsenal scored 3" → feature "attack output +22% vs the defenses faced."
- Rolling rates (last 5/10), **opponent-adjusted** rates, per-90 normalization, home/away splits, recency-weighted decay (recent games weigh more), variance/consistency measures.
- Divergence features: result vs underlying performance (a team winning while being out-xG'd is due to regress).

This stage produces dozens–hundreds of features. The math engine consumes the quantitative ones; I reason over the contextual ones.

---

## L2 — Team Strength Model 🧮

True strength, **not league position** (position lags and is noisy early/late season). Sub-models:
- **Offensive:** goals/90, xG/90, big chances created, shot quality (xG per shot).
- **Defensive:** xGA/90, defensive errors, press resistance, clean-sheet rate.
- **Transition:** counter-attacks for/against, counter-defense.
- **Set-piece:** corner & free-kick conversion and concession.
- **Possession/build-up:** build-up quality, press-breaking ability.

Output feeds Elo ratings and the Poisson λ (expected-goals) inputs in `engine/`.

---

## L3 — Player Impact Model 🧠🌐

Most predictors stop at the team. Elite ones don't — they price individuals.
- **Visible influence:** goals/xG contribution, progressive passes/carries, key passes, defensive actions.
- **Hidden influence:** space creation, pressing triggers, ball retention, leadership/composure.
- **Rule of thumb:** losing a rotation player ≈ negligible; losing a key center-back ≈ −2 to −4% win prob and +goals-against variance; losing a talisman striker/playmaker ≈ −8 to −14%. A first-choice keeper out is frequently underpriced by the market.

---

## L4 — Lineup / Availability Model 🧠🌐

**The single biggest amateur blind spot.** Evaluate the *actual XI*, not the badge.
- "Man City" ≠ "City without Rodri and Dias." The model must condition on who actually starts.
- Hierarchy of certainty: **confirmed lineup (≈1h pre-kickoff) > predicted lineup > full-strength assumption.** Confidence rises sharply once lineups are confirmed.
- Track **rotation risk**: a big midweek fixture (UCL) ahead, a cup tie, or a settled league position all raise the chance of a weakened XI.
- Suspensions and accumulated-card risk are deterministic and must never be missed.

---

## L5 — Tactical Matchup Engine 🧠

Football is **style vs style**, not strength vs strength. A strong team can be a bad matchup for a weaker one.
- High press vs patient build-up; low block vs a crossing/wide team; counter-attack vs a high defensive line; aerial side vs a small back line.
- Key questions: *Can A exploit B's specific structural weakness? Has B historically struggled against this exact shape/manager?*
- See `knowledge/tactics-playbook.md` for the matchup heuristics.

---

## L6 — Form Model (opponent-adjusted) 🧮🧠

Not "won last 5." Sophisticated form:
- **Opponent-adjusted** form (5 wins vs bottom sides ≠ 5 wins vs the top half).
- **xG-form** (underlying performance trend), **chance-quality** trend.
- **Performance-vs-result divergence** → mean-reversion signal: lucky teams cool, unlucky teams heat up. The market often over-reacts to raw results, creating value.

---

## L7 — Context Model 🧠🌐

Football is emotional and scheduled. Context routinely overrides raw strength.
- **Motivation:** title race, relegation fight, derby, European push — vs the **dead-rubber trap** (nothing to play for → unpredictable, often a pass).
- **Fatigue:** days since last match, fixture congestion (3 games in 7 days), international-break returnees.
- **Travel:** distance, time-zone changes (esp. continental/intercontinental).
- **Rotation risk:** a bigger game looming.
- **Off-pitch:** managerial change (new-manager bounce), contract/turmoil, fan protests.
- See `knowledge/context-and-traps.md` for the trap catalogue.

---

## L8 — Venue / Home Advantage 🧮🌐

Home edge is real but **not uniform** — it ranges from ~+3% to ~+15% by club, and it has shrunk post-2020 in empty/quiet stadiums.
- Use **team-specific** home/away xG splits, not a flat league constant.
- Drivers: crowd size/hostility, altitude (e.g. Andean sides), familiarity, reduced travel.
- See seeded priors in `knowledge/reference-tables.md`.

---

## L9 — Environment Modifiers 🧮🌐

- **Wind** suppresses passing accuracy and long-ball/crossing teams, and raises goal variance.
- **Heavy rain / wet pitch** favors physical/direct sides, hampers technical possession sides, raises error/goal variance.
- **Extreme heat** lowers tempo and total goals; aids the fitter/deeper squad.
- **Pitch type/size** and **altitude** shift expected goals and stamina.
These adjust the λ inputs and the variance in the simulation.

---

## L10 — Market Intelligence 📷🌐  ← **THE GATE MOST PEOPLE SKIP**

You can be 100% right about the winner and still lose money if the price already embeds your information. **The market is a competitor to beat, not just a price tag.**
- The screenshot hands me SportyBet's prices → I **de-vig** (remove the overround) to get the market's honest implied probabilities. That's the number my model must beat.
- Where findable: opening vs current line, **steam moves** (sharp sudden shifts), **closing-line value** (CLV — beating the closing price is the best long-run profit signal).
- See `knowledge/market-reading.md`.

---

## L11 — Advanced Statistical Layer 🧮🌐

The quantitative substrate beneath strength and simulation — where syndicates live.
- **xG / xGA** (expected goals for/against), **xPoints**, **PPDA** (passes allowed per defensive action = press intensity), **deep completions**, **field tilt**, **possession value / threat (xT)**, packing metrics.
- These feed and sanity-check L2 strength and the L12 λ values.

---

## L12 — Simulation Engine 🧮

Prediction proper begins here. Run the match **thousands of times** (Monte Carlo, 10k–100k), varying finishing luck, cards, and shock events.
- Built on Poisson/Dixon-Coles λ for each side → a **full scoreline distribution**.
- From that distribution derive every market: 1X2, Over/Under (any line), BTTS, correct score, Asian handicaps, clean sheets.

---

## L13 — Probability + Calibration 🧮🧠

Output is a **distribution**, never "X wins." e.g. Home 53.2% / Draw 24.7% / Away 22.1%.
- **Calibration is mandatory:** my probabilities are checked against the de-vigged market (L10) and historical base rates (`reference-tables.md`). Big unexplained divergence from the market is a red flag to re-examine, not automatically "value."
- This is why **math leads here** — LLM gut-feel percentages are poorly calibrated.

---

## L14 — Uncertainty / Confidence 🧠🧮

Elite predictors know what they *don't* know. Confidence (0–100) is driven by:
- **Data quality / freshness** (lineups confirmed? injuries current?),
- **Lineup certainty**, **model agreement** (do math sub-models converge?), **missing information**.
- Low confidence → smaller or zero stake. Confidence directly scales the Kelly stake.

---

## L15 — Value Detection 🧮  ← **GATE**

**EV = (my_prob × decimal_odds) − 1.** A bet is worth making only when my edge **beats the de-vigged market price**.
- Scan *every* market on the slip; rank by edge.
- **Value is the only reason to bet.** A 70%-likely outcome at 1.30 (implied 77%) is a *negative-EV pass*. A 40% outcome at 3.20 (implied 31%) is a *bet*.
- See `protocols/value-scan.md`.

---

## L16 — Staking (Kelly) 🧮  ← **GATE**

Selection without stake sizing goes broke. Stake = a function of edge **and** odds.
- **Fractional Kelly** (¼–½ Kelly) on the measured edge, **hard-capped** (e.g. ≤ 5% bankroll), scaled by confidence.
- The math: a 60%-correct predictor flat-staking bad odds *loses*; a 52%-correct predictor with value + Kelly *wins*.
- Never chase losses; never exceed the cap. See `knowledge/staking-kelly.md`.

---

## L17 — Contradiction Check / Decision 🧠  ← **GATE**

The discipline layer where most "good predictors" fall apart.
- When layers **conflict** (math loves the home side, but the key CB is out, it's a dead rubber, and the line is drifting against them), the correct move is almost always **PASS**, not force a pick.
- Explicit pass criteria live in `protocols/contradiction-check.md`. A pass is a *successful* outcome of the pipeline, not a failure.

---

## L18 — God-Mode Signals 🧠🌐

What top syndicates layer on top once everything below is solid:
- **Referee tendencies:** cards/penalties per game, home bias, advantage-play style (affects cards/totals markets heavily).
- **Manager tendencies:** substitution timing, in-game tactical shifts, performance vs specific opponents.
- **Individual micro-matchups:** this fullback vs that winger; a slow CB vs a pacey striker.
- **Hidden injury signals:** reduced training minutes, evasive press conferences, late fitness tests.
- **News / insider intelligence:** local reporters, club beat-writers, lineup leaks.
- **Market microstructure:** how sharp money is behaving inside the price.

---

## L19 — Feedback & Calibration Loop 🧮🧠

What makes the suit *get sharper*:
- After each match: store prediction + actual result + **closing line** → compute Brier score, ROI, **CLV** → update calibration buckets and per-league/per-market trust weights in `ledger/calibration.md`.
- Persistent biases (e.g. systematically over-rating home favorites in league X) get corrected. This is the compounding engine.

---

## Ownership map

| Owner | Layers |
|-------|--------|
| 🧮 Local math (`engine/`) | L1(quant), L2, L6(quant), L8, L9, L11, L12, L13, L15, L16, L19(scoring) |
| 🧠 My judgment | L1(context), L3, L4, L5, L7, L10(read), L13(sanity), L14, L17, L18, orchestration |
| 📷 Screenshot | L0 odds/fixtures, L10 prices |
| 🌐 Web search | L0 enrichment, L3, L4, L7, L8, L9, L10, L11, L18 |

## The hierarchy of who wins

- **Losing bettors** operate at L0–L6: last 5 results + an injury check, then pick. ~90% of losers.
- **Break-even** adds L5 + L7: reads tactics, spots dead-rubber traps.
- **Elite/profitable** fires **all** layers, and crucially L10 + L15 + L16 + L17 together: better than the market, value-gated, Kelly-staked, and disciplined enough to pass.

> The biggest difference between an average and a world-class predictor is **not the final algorithm** — it's the depth and quality of the representation built in L0–L11 before any probability is produced.
