# Reference Tables (priors for L8, L13, L9)

> Seeded with well-established base rates so the **first** prediction is already grounded, not starting from zero. These are *priors* — the L19 ledger refines them as real results accumulate. Treat as approximate; recency and the specific clubs always override the league average.

## League base rates (full-time 1X2 & goals)

Long-run approximate distributions. Home/Draw/Away are share of results; goals are total goals per game.

| League | Home win | Draw | Away win | Goals/game | Avg home goals | Avg away goals |
|---|---|---|---|---|---|---|
| Premier League (ENG) | ~45% | ~24% | ~31% | ~2.8 | ~1.55 | ~1.25 |
| La Liga (ESP) | ~47% | ~25% | ~28% | ~2.6 | ~1.45 | ~1.15 |
| Serie A (ITA) | ~44% | ~26% | ~30% | ~2.8 | ~1.50 | ~1.30 |
| Bundesliga (GER) | ~44% | ~23% | ~33% | ~3.1 | ~1.70 | ~1.40 |
| Ligue 1 (FRA) | ~45% | ~27% | ~28% | ~2.6 | ~1.45 | ~1.15 |
| Champions League | ~47% | ~25% | ~28% | ~2.9 | ~1.60 | ~1.30 |
| Generic / unknown league | ~45% | ~26% | ~29% | ~2.7 | ~1.50 | ~1.20 |

> **Draws cluster at 24–27% almost everywhere** — a key calibration anchor. Any model spitting out a <18% or >32% draw probability needs a reason. Use the league row as the Poisson λ starting point before team-specific and contextual adjustment.

## Home advantage priors

Expressed as the home side's expected-goals uplift / win-prob boost vs a neutral venue.

| Context | Home λ multiplier | Win-prob boost | Notes |
|---|---|---|---|
| Strong home fortress (hostile crowd) | ×1.25–1.35 | +12–15% | e.g. historically intimidating grounds |
| Typical top-league home | ×1.15–1.20 | +8–10% | default if unknown |
| Weak home edge / neutral-ish crowd | ×1.05–1.10 | +3–5% | small/quiet stadiums |
| Empty / behind closed doors | ×1.00–1.05 | ~0–3% | crowd effect largely removed |
| True neutral venue (cup final, tournament) | ×1.00 | 0% | no home side |
| High altitude (home side acclimatized) | +additional ×1.05–1.15 | extra edge | Andean / highland venues vs lowland visitors |

**Default when unknown:** home λ ×1.15, ≈ +9% win prob.

## Goals / variance environment (for O/U & BTTS)

| Total goals (model λ_home+λ_away) | Over 2.5 prob (approx, Poisson) | Lean |
|---|---|---|
| ~2.2 | ~38% | Under |
| ~2.7 | ~50% | Coin-flip |
| ~3.2 | ~62% | Over |
| ~3.6 | ~70% | Strong over |

> BTTS-yes baseline across top leagues ≈ **48–52%**. Push up with two competent attacks + open game; down with an elite defense or a likely comfortable favorite.

## Weather modifiers (L9) — applied to total λ

| Condition | Effect on goals | Variance |
|---|---|---|
| Calm, dry, mild | neutral | neutral |
| Strong wind (>30 km/h) | −5 to −10% goals | ↑ |
| Heavy rain / wet pitch | slight −, favors direct sides | ↑↑ |
| Extreme heat (>30°C) | −5 to −15% goals, slower tempo | neutral |
| Snow / freezing | −, unpredictable | ↑↑ |

## Referee priors (L18) — fill per-referee as discovered

| Referee profile | Cards/game | Pen frequency | Use for |
|---|---|---|---|
| Card-happy / strict | 5+ | higher | over-cards markets, derby risk |
| Lenient / lets it flow | <3.5 | lower | under-cards |
| League average (default) | ~3.5–4.5 | ~0.25/game | baseline |

_(Add named referees here as the ledger learns them.)_

---

## Maintenance

- These are **starting priors**, not truth. After ~20–30 logged results, reconcile the calibration buckets in `ledger/calibration.md` against these rows and adjust.
- When a specific club deviates strongly from its league row (elite attack, fortress home, low-scoring grinder), the **club-specific read wins** — these tables are only the fallback prior.
