# CLAUDE.md — Kairos operating notes

> Practical operating layer for working with this user. Load `KAIROS.md` for the full charter + four hard rules. This file is the day-to-day "how we actually work."

## What this is
Kairos = Claude as a **recommend-only** football (and any-sport) value-betting aide. User sends a SportyBet screenshot → I return value picks or a disciplined pass. **Never** place bets, store credentials, or move money — the user stakes manually.

## The core edge (v2.0)
Compare SportyBet's price to **Pinnacle's de-vigged "true" price** via The Odds API. Bet only where SportyBet pays MORE than the sharp fair price (EV = sb_odds × sharp_prob − 1 > +3%).

### How to run it (the pattern used every session)
```
cd engine   # (use absolute path: c:/Users/HomePC/Documents/Kairos/engine — cwd is not reliably persistent)
# fetch needs network: run Bash with dangerouslyDisableSandbox=true + socket.getaddrinfo pre-resolve + retry loop
python -c "import sys; sys.path.insert(0,'.'); sys.path.insert(0,'sources'); import odds_api, edge; \
 evs=odds_api.fetch_raw(sport_key='soccer_epl', regions='uk,eu', markets='h2h'); \
 ev=odds_api.find_event(evs,'Home hint','Away hint'); p=odds_api.parse_event(ev); \
 f=edge.sharp_fair(p['books'])['fair_prob']; print(edge.value_vs_sharp(sb_odds, f))"
```
- `edge.sharp_fair(books)` → picks Pinnacle (else a consensus of **3+** books), returns `{source, sharp, fair_prob, n_books, others_median, n_others}`. It returns **None** when there is no Pinnacle and fewer than 3 books: that is "no sharp line → skip", not an error to work around.
- `others_median` is what the other books think. If Pinnacle's `fair_prob` is far above it, say so; the backtest found those bets were not worse, so it is a note, not a veto.
- `edge.value_vs_sharp(sb_odds, fair, min_edge=0.03)` → EV per selection.
- `fetch_raw` caches h2h to `odds_<sport>.json` and other markets to `odds_<sport>_<markets>.json` (totals no longer overwrite h2h).
- `find_event` folds accents ("Malaga" matches "Málaga"). If the hints match more than one event it raises an error listing them — give a more specific hint, never take the first.
- `odds_api.parse_lines(ev, 'totals' | 'spreads')` → per book `{line, over, under}` or `{line, home, away}`.
- Print with an ASCII-safe wrapper (`str(x).encode('ascii','replace').decode()`) — Windows cp1252 crashes on accented team names.

**Status (2026-10-02): NO EDGE HAS BEEN SHOWN.** Don't tell the user the edge is real.
- Old `engine/backtest.py` has look-ahead; never quote it.
- Trustworthy backtest, 2012–2024, Bet365 vs Pinnacle at +3%: CLV +2.3% over 2,976 bets, return interval includes zero, nothing in the five big leagues (`docs/backtest-baseline.md`).
- **Held-out seasons 2024/25–2025/26: 169 bets, CLV −0.1% (−1.9 to +1.6).** The historical edge did not carry into recent seasons (`docs/engine-improvements.md`).
- Bet365 is not SportyBet, so SportyBet is still unmeasured. The gap census below is the only thing that can measure it. Until it has ~1,000 prices, say "being measured" and keep stakes small and flat.
- Rating models (goals, shots) add nothing to Pinnacle's price: tested, weight 0.
Engineering work follows `DEV_AGENT_BRIEF.md`, phase by phase.

### Gap census — log EVERY SportyBet price, bet or not
Every time the user sends SportyBet prices for an event that has a Pinnacle line, log them (this is the measurement that decides whether the strategy lives):
```
python -c "import sys; sys.path.insert(0,'c:/Users/HomePC/Documents/Kairos/harness'); import census;  census.log_prices(ev, {'home': 2.10, 'draw': 3.40, 'away': 3.60}, 'soccer_epl', staked=('home',))"
```
- `ev` is the raw Odds API event (from `odds_api.find_event`). No Pinnacle price = nothing logged.
- If a fetch happens within 3 hours of kickoff, call `census.log_close(ev)` for the closing price.
- `python harness/census.py summary` prints the gap share, CLV and the kill-rule reading.

### Paper-trading loop (Phase 4) — running on this PC
- Task Scheduler task **KairosPaper** runs `paper/main.py` at logon. Status: `python paper/main.py --status`; stop: `--stop`. Guide: `docs/paper-trading.md`.
- It shares the Odds API key: the loop caps itself at 440 credits a month and leaves 60 for sessions. Check `paper/state/budget.json` before spending many credits by hand.
- Census prices logged in a session get their closing price from the loop when their match is in a sport it can fetch.

### Backtest harness
`harness/` (stdlib only): `run_baseline.py`, `run_a1.py`…`run_a4.py`, `test_harness.py`. Outcomes of every proposal: `docs/engine-improvements.md`. Sport-agnostic code (staking, de-vig, ledger, metrics) lives in `core/`; `engine/kelly.py`, `market.py`, `ledger.py` are shims, so old imports and `python engine/ledger.py …` still work. Holdout seasons are in `research/holdout.json` — never load them without a written reason. Write each new variant in `research/hypotheses.md` BEFORE running it.

## The user's betting mode — value singles (since 2026-09-26)
- **Value singles only, flat small stake** (~500). No accumulators as a strategy: a 12-of-13 DC acca returned 0, and vig compounds per leg.
- **Only games in this week + next week** — no long-dated picks.
- A scan that returns zero or one pick is normal. Pass plainly; don't manufacture a slip.
- Log every pick with the SportyBet price, the sharp fair price at bet time, and (later) the closing price — CLV is the measure, not win rate.

## Basketball (added — sport-agnostic edge)
`edge.py` works on any sport. Basketball differences: **no draw** (2-way h2h), no Double Chance. Main sharp markets = **moneyline (h2h), spread (spreads/handicap), total (totals)** — spreads & totals are where basketball value lives; lines are very sharp. Covered game-level: **NBA** (Oct–Jun), **WNBA** (May–Sep) via `basketball_nba` / `basketball_wnba` (regions `us,uk,eu`). No EuroLeague/NCAAB games in this account's feed. De-vig a 2-way market the same way; no DC-acca style here — treat as single-value / spread bets.

### Cousin markets — `engine/derive.py`
For goal lines, Asian handicaps, double chance and draw-no-bet, fit to Pinnacle and read the market off the fit:
```
fair = edge.sharp_fair(p['books'])['fair_prob']                      # Pinnacle 1X2
t = odds_api.parse_lines(ev_totals, 'totals')['pinnacle']            # Pinnacle total, any line
lh, la = derive.fit_from_1x2_and_total_prices(fair, t['line'], t['over'], t['under'])
m = poisson.score_matrix(lh, la)
s = derive.handicap_settlement(m, -0.25, 'home')    # or derive.total_settlement(m, 2.75, 'over')
derive.fair_price(s); derive.settlement_ev(s, sportybet_price)
derive.double_chance(fair)                           # straight from the fair 1X2
```
- **Never price a total from 1X2 alone** — tested and killed (4 points off Pinnacle on average).
- A derived handicap price is about 0.6 points of probability off Pinnacle's own. Ask for **+5% or more** before calling a derived-price bet value, and say it is a derived price.
- Quarter lines are settled as two half stakes (the September Real Madrid Under phantom was this).

## Market-switching workflow
When 1X2 has no value/confidence, proactively check the **cousins**: O/U (totals), Handicap (spreads), Double Chance (derive from 1X2), To-Qualify (knockouts, derive from 1X2 + ET model). Give the user the sharp **fair bar** and ask for SportyBet's number in that market.

## Coverage — only bet what has a sharp line
**Covered by The Odds API** (verifiable): EPL, EFL Champ/L1/L2/Cup, La Liga + La Liga 2, Serie A + B + Coppa, Bundesliga 1/2/3 + Pokal, Ligue 1/2, Eredivisie, Portugal, Turkey, Greece, Scotland, Belgium, Austria, Switzerland, Russia, Poland, Denmark, Sweden (Allsvenskan/Superettan), Norway, Finland, Ireland, Saudi, J-League, K-League, China, MLS, Liga MX, Brazil Série A + B, Argentina Primera, Chile, Copa Libertadores/Sudamericana, UCL qualifiers, Nations League — plus non-soccer: NFL/NCAAF/CFL, NBA/WNBA, MLB/KBO/NPB, NHL, AFL, NRL, tennis (ATP/WTA), cricket, MMA/boxing.
**NOT covered = always skip** (no sharp reference): Uruguay, Peru, Venezuela, Ecuador, Bolivia, Costa Rica, Panama, Colombia lower, Argentina 2nd tier (Primera Nacional), Brazil Série C/D + state leagues (Baiano/Catarinense/Mineiro/etc.) + women's, USL (all), MLS Next Pro, Canadian Premier, youth/U20/U23 internationals, Mexico Liga Premier, small regional leagues.

## Engine rules changed on 2026-10-02
- Modifiers outside 0.80–1.20 are rejected by `run.py`.
- A fragile ("speculative") candidate has `bet: false` and no stake.
- `ledger.record_result` refuses an unknown id and a second result (use `correction=True` to fix one). Pass `closing_fair_prob` (Pinnacle's de-vigged closing probability) for fair CLV.
- Log `raw_prob` next to `my_prob` on every model-path pick so the judgment layer can be scored.
- All bets on one match together are capped at 5% of bankroll.

## Hard discipline (learned the hard way)
- **A huge "edge" is a BUG, not a bet.** Real value is a quiet 2–5%. Any 30–70% "edge" = missing/thin Pinnacle line (single non-Pinnacle book, two-legged-tie mismatch) or my own model error. Suspect myself first. (Craiova +73% mirage; my own quarter-line +7.5% phantom.)
- **Quarter/half goal lines**: Pinnacle often prices one total line at .0/.25/.75. Handle the push/quarter correctly when fitting μ — don't treat 2.75 as 2.5.
- **Knockout 1X2 = 90 minutes only** — ET/pens don't count. Flag on every cup tie; prefer To-Qualify or DC for a grinding favourite. (Argentina 1-1 CPV loss.)
- Live/in-play = out of scope (sharp line moves too fast; pre-match only).
- GG/NG, corners, cards, 1st-half, exact score, player props = **no sharp line** → estimate at most, never claim verified value.

## Money management to reinforce with the user
- Lock in wins: most of a payout comes OUT of betting (bank/save/enjoy). Only a small **fixed** slice is the betting bankroll.
- When the betting slice runs out, STOP — never refill from savings. Never chase. Keep stakes steady (they use ~500).

## Secrets
`.env` (gitignored, NEVER commit): `THE_ODDS_API_KEY`, `OPENWEATHER_API_KEY`. Config accepts `THE_ODDS_API_KEY` or `ODDS_API_KEY`. Free tier 500 calls/mo — cache to `engine/fixtures/`. Stay zero-dependency (stdlib urllib). Git identity: Adekoya Emmanuel; GitHub m1r4g3-code/kairos (private).
