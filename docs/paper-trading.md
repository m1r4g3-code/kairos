# Paper trading: how to run it and read it

Written 2026-10-03 (Phase 4). The loop is installed on the owner's PC and running.
Nothing in it places a bet, logs into a bookmaker, or stores a bookmaker login.

## What it does, in one paragraph

Every few minutes the loop checks the clock and its files and runs whatever is due.
When a match in a watched league is within 60 hours of kickoff, it takes every
bookmaker's 1X2 price from The Odds API, removes Pinnacle's margin, and records a
one-unit paper bet wherever another bookmaker's price beats Pinnacle's fair price by
3% or more ("strategy P1"). Twice a day Claude Code reviews new picks, with a web
search for team news, and logs a veto or no-veto beside each pick without changing
it. About 30 minutes before kickoff the loop takes Pinnacle's price again (the
closing price). After the match it settles the pick from Football-Data's results
file. Once a day it writes a scorecard.

## Start, stop, check

| What | Command (from the Kairos folder) |
|---|---|
| Start the loop by hand | `python paper/main.py` |
| One pass of every due job, then exit | `python paper/main.py --once` |
| Print the scorecard and recent health lines | `python paper/main.py --status` |
| Stop a running loop (exits within seconds) | `python paper/main.py --stop` |
| Start it automatically at Windows logon (installed 2026-10-03) | `powershell -ExecutionPolicy Bypass -File paper\autostart.ps1` |
| Remove the automatic start | `powershell -ExecutionPolicy Bypass -File paper\autostart.ps1 -Remove` |
| Start the installed task now | `Start-ScheduledTask -TaskName KairosPaper` (PowerShell) |

The task is called **KairosPaper** in Task Scheduler. It runs with `pythonw`, so no
window opens. It keeps running on battery and has no time limit. Only one copy can
run: a second start is refused while the first is alive.

## Reading it in one minute

Open `paper/state/scorecard.md` (or run `--status`).

1. **Health.** "Loop running now: yes" and a heartbeat from the last few minutes
   mean it is alive. Any warning or error from the last 24 hours is listed.
2. **Credits.** How many Odds API credits the loop has spent this month and how many
   the provider says are left.
3. **Picks.** How many were made, how many have kicked off, and for how many the
   closing price was captured. A low capture rate means the PC was off at kickoff.
4. **The table.** The column to watch is **CLV** and its interval. A return per bet
   means little until there are hundreds of settled bets. The two "Claude vetoed /
   did not veto" rows show whether the judgment pass picks out worse bets.
5. **Census.** SportyBet prices logged from screenshots, how often they beat
   Pinnacle's fair price, and their CLV once closing prices exist.

## What survives the PC being off

| Situation | What happens |
|---|---|
| Killed or PC shut down mid-job | Every file is written whole or not at all; on restart nothing is lost or doubled. |
| Off when a match entered the 60-hour window | Picked up at the next run, as long as kickoff is still more than 3 hours away. Otherwise skipped: no late picks. |
| Off at kickoff | No closing price for that match. It is counted as missed, never faked. The pick still settles; its CLV is blank. |
| Off when results came in | Settled at the next run (results are checked every 6 hours). |
| Started twice | The second copy exits at once ("another copy is running"). |
| Claude unavailable (offline, usage limit, logged out) | The judgment pass logs a warning and tries again at the next scheduled hour. Picks, closes and settlement are unaffected. |
| Odds API budget used up | Snapshots stop first; credits are held back for closing prices already owed. Each refusal is logged. |

The loop does not wake a sleeping PC. Sleep counts as "off".

## Files

All in `paper/state/` (gitignored: the data stays on this PC).

| File | Contents |
|---|---|
| `picks.jsonl` | One line per paper pick: match, selection, price, bookmaker, Pinnacle fair probability, claimed edge |
| `snapshots.jsonl` | Every bookmaker's 1X2 price at pick time, for every watched match, picked or not |
| `closes.jsonl` | Pinnacle's price shortly before kickoff, per match with a pick |
| `results.jsonl` | Final score per match, or "unmatched" after 10 days |
| `judgments.jsonl` | Claude's verdict per pick: veto or not, one-line reason, model |
| `scorecard.md` | The summary above, rewritten daily and after each settlement |
| `health.log` | One line per job that did something, and every warning or error |
| `heartbeat.txt` | Time of the last loop tick |
| `budget.json`, `state.json` | Credits this month; when each job last ran |
| `results_cache/` | This season's Football-Data results files, refreshed at most every 12 hours |

The SportyBet census stays in `ledger/census.jsonl`. The loop adds closing prices
to it for any census match it can see.

## Moving it to another machine

1. Copy the whole Kairos folder, including `paper/state/` and `.env`. If git is used
   instead, copy `paper/state/` and `.env` across by hand: neither is in git.
2. Install Python 3.10 or later. Nothing else is needed.
3. Log in to Claude Code on that machine (`claude` in a terminal, once) if the
   judgment pass should work there. Without it the loop runs and logs a warning.
4. Run `python paper/main.py --once` to check, then the autostart command above.
5. Remove the task on the old machine (`-Remove`) so two PCs do not spend the same
   credits.

## Choices made and why

**Leagues watched** (`paper/config.json`): Championship, League One, League Two,
2. Bundesliga, Serie B, La Liga 2. In the backtest the five big leagues showed no
gap at all, and second tiers showed the most. On the holdout seasons no league
group showed a reliable gap either, so this list is the best guess the data
allows, not a finding. All six are in The Odds API, in Football-Data's free results
files, and on SportyBet.

**Strategy P1** is the forward version of the backtest's "best of named
bookmakers" variant. SportyBet is not in The Odds API's feed, so P1 measures the
bookmakers that are. SportyBet itself is measured by the census.

**Credit budget.** The free tier is 500 credits a month. One price fetch for one
league costs 2 (UK and EU regions, 1X2 only); the events list is free. A league
needs about 2 to 3 snapshot fetches a week plus one closing fetch per kickoff slot
that has a pick, so roughly 40 to 70 credits a month. The loop is capped at 440 and
always leaves 60 for the owner's own sessions. It reads the provider's own count
from every response, so credits the owner spends by hand are counted too.

**Claude judgment pass.** At most at 10:00 and 19:00 local time, at least 4 hours
apart, only when there are unjudged picks. Model `sonnet` through Claude Code on
the Pro subscription, with web search allowed and nothing else. One review of three
picks took about a minute. Claude's verdict is logged next to the pick and never
changes it, so after enough settled picks the scorecard shows whether its vetoes
pick out worse bets (the research's proposal F2).

## Odds sources the brief named

| Source | Verdict | Why |
|---|---|---|
| The Odds API, free tier | **Used** | Terms allow this use (checked in Phase 1). Pinnacle plus about 20 other bookmakers. Budgeted as above. |
| Cloudbet feed API | **Not used yet. Needs a decision.** | Cloudbet issues two kinds of key. A *Trading* key, from the player account, can place bets: storing it would break the rule against storing bookmaker credentials. An *Affiliate* key is read-only (cached odds, cannot place bets) but comes from a separate affiliate account. Rate limits for the feed are not published; the bet endpoint is limited to 1 request a second. |
| SX Bet API | **Not used** | Most market data is public with no key, but the best-odds endpoint needs an account key, and I found no terms page covering jurisdictions or data use. Soccer liquidity on an exchange of this size is thin, so it adds little as a reference beside Pinnacle. Published limits are generous (500 requests a minute for market data). |
| NaijaBet-Api | **Not used** | It covers Bet9ja, BetKing and Nairabet, not SportyBet ("Add Sportybet" is still a to-do). It calls the bookmakers' own website endpoints, not a published API, and needs a Nigerian connection (this PC is in Nigeria, so no country block applies). I could not find terms from those bookmakers that allow automated collection, so under the brief's rule it is not used. |
| SportyBet directly | **Not used** | Its robots.txt blocks only search pages, but its terms page would not load for me, so I could not confirm that automated reading is allowed. SportyBet prices keep coming in through screenshots and the census. |

Sources: [The Odds API v4 guide](https://the-odds-api.com/liveapi/guides/v4/),
[Cloudbet API wiki](https://cloudbet.github.io/wiki/en/docs/sports/api/),
[Cloudbet key types (Jentic)](https://jentic.com/apis/cloudbet.com),
[SX Bet rate limits](https://docs.sx.bet/developers/rate-limits.md),
[SX Bet best-odds endpoint](https://docs.sx.bet/api-reference/get-best-odds-v3.md),
[NaijaBet_Api README](https://github.com/jayteealao/NaijaBet_Api).

## What has been checked live, and what has not

Checked on 2026-10-03:
- One pass against the live feeds: 20 matches seen in 60 hours, 3 leagues fetched,
  6 credits spent, 3 picks made (all League Two; two at onexbet, one at livescorebet).
- The judgment pass through Claude Code: 3 of 3 picks reviewed with team-news
  searches, none vetoed.
- The task installed, started, stopped and restarted; a second copy refused.

Not yet checked live:
- A closing-price fetch and a settlement on real data (the first ones fall due on
  3 October at about 14:30 and on the next Football-Data update). The offline tests
  cover both.
- Behaviour after a full reboot and a fresh logon.
- What happens when the Claude Code login expires or the Pro usage limit is hit
  (the code treats both as "no judgment", but I have not seen the real messages).
- Team-name matching on leagues other than the Championship file I looked at.
