# Tactics Playbook (L5)

> Style vs style. A stronger team can be a *bad matchup*. These heuristics turn "who's better" into "who beats whom, given how they play." Adjust the base distribution; never override calibration wholesale.

## Core matchup pairs

| Team A style | vs Team B style | Edge tends toward | Why |
|---|---|---|---|
| High press | Patient build-up from the back | **A**, if A's press is well-drilled | Forces errors in B's defensive third; B's keeper/CBs under pressure |
| High press | Direct / long-ball team | **B** | The press is bypassed; B targets the space behind A's high line |
| Counter-attack | High defensive line + possession | **A (counter)** | Space in behind; one transition = a clear chance |
| Low block + counter | Dominant possession, no pace | **A (low block)** | B passes sideways, can't break the block, gets caught on the break |
| Crossing / wide overloads | Small or aerially weak back line | **A** | Set-pieces + crosses feast |
| Technical possession | Aggressive midfield press on a wet/heavy pitch | **B** | Pitch + press disrupt A's passing rhythm |
| Pace out wide | Slow fullbacks | **A** | Repeatable 1v1 isolation |

## Reading a matchup in 5 questions

1. **Who controls tempo?** The side that imposes its preferred speed usually controls xG share.
2. **Where is the space?** A high line concedes depth; a low block concedes the ball but not space — pick the team built to exploit what's offered.
3. **Press vs build-up:** Does the pressing side have the legs (fresh, deep squad) to sustain it 90'? A tiring press leaks late goals.
4. **Set-piece mismatch:** Height/strength deltas + a good delivery = a real, repeatable edge, especially in tight games and low-confidence picks.
5. **Game-state effect:** If A scores first, does B's style become *more* dangerous (must-chase, opens up) or less (can't break a low block)? This shifts in-play and BTTS/totals reads.

## Goals environment (for O/U & BTTS)

- **Over-leaning matchups:** two open, high-line, attacking sides; a press-vs-direct clash; a desperate must-win chase.
- **Under-leaning matchups:** two low blocks; a strong defense vs a blunt attack; high stakes + cagey managers (cup finals, relegation six-pointers); awful weather.
- **BTTS-yes:** both attacks decent + at least one shaky defense + open game-state incentives.
- **BTTS-no:** one elite defense / clean-sheet machine, or a heavy favorite likely to win comfortably while the underdog parks the bus.

## Manager overlay (links to L18)

- Note pragmatic vs ideological managers: ideologues keep their shape regardless of opponent (more predictable); pragmatists set up specifically to nullify (read the presser).
- Sub patterns: who goes for it when chasing vs who shuts up shop when ahead → late-goals signal.

## Discipline

- A tactical edge is a **modifier**, not a verdict. Translate it into a bounded nudge of the score λ (typically ≤ ±0.3 goals) and let `engine/` re-derive probabilities. Don't hand-write the percentage.
