# Sub-protocol — enrich.md (L0, L3–L11, L18)

> Hybrid sourcing: the screenshot gave me odds + fixtures; now I fill the gaps with WebSearch/WebFetch. **Priority-ordered and time-boxed** — get the highest-leverage facts first, declare what's missing, and let gaps lower confidence.

## Priority ladder (stop when time/budget is spent; never skip 1–2)

### Priority 1 — Availability (L4) · highest leverage
The biggest single edge most bettors miss.
- **Confirmed lineups** (drop ~1h pre-kickoff) > **predicted lineups** > full-strength assumption.
- Injuries and **suspensions** (deterministic — never miss an accumulated-card ban).
- Searches: `"<home> vs <away> predicted lineup"`, `"<team> injury news"`, `"<team> suspended <matchday>"`.
- Translate to impact via L3 (key CB out ≈ −2–4%; talisman out ≈ −8–14%; #1 keeper out often underpriced).

### Priority 2 — Form & strength (L2, L6, L11)
- Last 5–6 results **and** the underlying xG/xGA (results can lie).
- Home/away splits. Opponent-adjusted, not raw.
- Searches: `"<team> recent form xG"`, `"<team> home record this season"`, site:fbref/understat-style sources.

### Priority 3 — Context & traps (L7)
- Stakes for each side (title/relegation/dead rubber), derby, fixture congestion, a big game looming, European hangover, manager change.
- Cross-check `knowledge/context-and-traps.md`. A fired trap with no offsetting edge → likely pass.
- Searches: `"<team> next fixture"`, `"<league> table"`, `"<team> manager news"`.

### Priority 4 — Venue & environment (L8, L9)
- Team-specific home edge (use `reference-tables.md` prior if no data).
- **Weather at kickoff** for the venue (wind/rain/heat → goal & variance modifiers).
- Searches: `"<venue> weather <date>"`, altitude if relevant.

### Priority 5 — God-mode (L18) · if time allows
- **Referee** appointment + card/penalty tendencies (big for cards/totals/derby risk).
- Manager tendencies (sub timing, vs this opponent), micro-matchups (pace vs slow FB), late team-news leaks, line movement.
- Searches: `"<match> referee appointed"`, `"<referee> cards per game"`.

## Time-boxing & honesty
- Aim for the **Priority 1–3** facts on every prediction; 4–5 are bonus.
- For each layer, record: **found / not found / stale**. Missing Priority-1 info (lineups not out yet) is itself a finding → **lower confidence**, consider waiting until lineups drop.
- **Never invent** a stat, lineup, or referee. "Couldn't confirm" beats a confident fabrication. The ledger punishes fabrication via bad calibration.

## Turning enrichment into the engine spec
Each finding becomes either:
- a **lambda input** (strength/form/home edge → base λ), or
- a **bounded modifier** (`lam_home_mult` / `lam_away_mult`, each a small nudge, with a one-line `note`), or
- a **confidence adjustment** (missing/stale data → down; confirmed lineups + clear context → up).

Then hand the spec to `engine/run.py`. The math re-derives every probability — I never hand-write the final percentages.
