# Context & Traps (L7)

> Football is emotional and scheduled. Context routinely overrides raw strength — and most of these are *traps* that look like value but aren't. When a trap fires, the default is **pass** (feeds L17).

## The trap catalogue

### 1. The dead rubber
Mid-table side late in the season with nothing to play for, or a team already qualified/eliminated. Effort and team selection become unpredictable. **Action:** widen uncertainty, usually pass — especially on the favorite.

### 2. Fixture congestion / rotation
3 games in 7–8 days, or a big fixture (UCL knockout, derby, cup final) within 3 days *after* this one. Expect a rotated XI. **Action:** discount the favorite, wait for confirmed lineups, lower confidence until they're out.

### 3. The "new manager bounce"
First 1–3 games under a new manager often over-perform (morale spike, players auditioning). The market sometimes underprices this. **Action:** small upgrade to the bouncing side early, but it fades fast — don't extrapolate past ~4 games.

### 4. European hangover
A side returning from a draining/emotional midweek European tie (esp. away, long travel) playing a domestic game ~3 days later. **Action:** discount them, especially if the domestic opponent is fresh and motivated.

### 5. The trap favorite (lookahead)
A strong team with a marquee fixture next week may have one eye on it. Classic underdog-value spot. **Action:** consider the underdog / draw / +handicap.

### 6. Derby / high-emotion games
Form often goes out the window; cards and intensity spike, favorites under-deliver, draws more likely. **Action:** lean toward draw/under-favorite outcomes and cards markets; demand more edge on the favorite.

### 7. Relegation desperation
A bottom side fighting to survive vs a mid-table side on the beach can flip expected motivation entirely. **Action:** upgrade the desperate side's intangibles.

### 8. International-break return
Key players back late from international duty (travel, minutes, knocks). Patchy cohesion in the first game back. **Action:** mild discount; check who traveled furthest.

## Motivation scale (quick scoring)

Rate each side's *real* stake in the result, High / Medium / Low:
- **High:** title, top-4, relegation, derby, cup knockout, manager under pressure.
- **Medium:** normal league game, mid-table with pride/bonuses on the line.
- **Low:** dead rubber, season over, already qualified, beach mode.

A **High vs Low** mismatch is a meaningful edge the base model misses. **Low vs Low** = high variance = usually pass.

## Fatigue quick-check

| Days rest | Effect |
|---|---|
| 5+ | Fresh, no penalty |
| 3–4 | Mild fatigue, watch rotation |
| 2 | Notable fatigue, esp. with travel; legs go late |
| Plus long travel / extra-time midweek | Compound the penalty |

## How context enters the math

Translate context into **bounded modifiers** on the score λ and on confidence — not into hand-written final percentages:
- Motivation mismatch: nudge the motivated side's λ up / the flat side's down (≤ ~±0.25).
- Fatigue/rotation: lower the affected side's λ and **lower confidence**.
- Trap fired with no offsetting edge: **set the pick to pass**, don't just shade it.
