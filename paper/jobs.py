"""
KAIROS paper trading — the jobs. Football-specific; the loop, state files,
budget and Claude call come from core/.

Strategy under forward test ("P1"): for each watched match, take Pinnacle's
price from The Odds API, remove the margin (power method, edge.sharp_fair), and
paper-bet one unit on any selection where the best price among the other
bookmakers in the feed beats that fair price by min_edge. This is the forward
version of the backtest's "best of named books" variant. SportyBet is not in
the feed; its prices reach the census through the owner's screenshots, and the
closing job captures their closing prices too.

Files (all under paper/state/, append-only unless noted):
  picks.jsonl       one line per paper pick, written once
  snapshots.jsonl   every bookmaker's 1X2 price at pick time, per event
  closes.jsonl      Pinnacle's price shortly before kickoff, per event
  results.jsonl     final score per event (or "unmatched")
  fd_closes.jsonl   closing prices from the Football-Data results file, per event
  cloudbet.jsonl    Cloudbet's 1X2 prices beside Pinnacle's fair price, per event (research C1)
  judgments.jsonl   Claude's verdict per pick (veto or not, and why)
  state.json        timestamps of the last run of each job (rewritten)
  budget.json       Odds API credits this month (rewritten)
  health.log        one JSON line per job run or error
  scorecard.md      the daily summary (rewritten)

Pure stdlib.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
for p in (ROOT, os.path.join(ROOT, "engine"), os.path.join(ROOT, "harness")):
    if p not in sys.path:
        sys.path.insert(0, p)

from core import budget as budget_mod      # noqa: E402
from core import devig, judgment, metrics, store  # noqa: E402
from core.scheduler import Health          # noqa: E402
import config as engine_config             # noqa: E402
import edge                                # noqa: E402
import census                              # noqa: E402

import feeds                               # noqa: E402
import names                               # noqa: E402

LABELS = ("home", "draw", "away")
PROXY_BOOK = "BFE"       # Betfair Exchange close from Football-Data; see research M1


def parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat(timespec="seconds")


class Paper:
    """Shared context: config, files, feeds."""

    def __init__(self, cfg: dict, state_dir: str, odds_client=None, http=None,
                 judge=None, census_path: str | None = None, cloudbet="auto"):
        self.cfg, self.dir = cfg, state_dir
        os.makedirs(state_dir, exist_ok=True)
        self.picks = store.KeyedLog(os.path.join(state_dir, "picks.jsonl"))
        self.snaps = store.KeyedLog(os.path.join(state_dir, "snapshots.jsonl"))
        self.closes = store.KeyedLog(os.path.join(state_dir, "closes.jsonl"))
        self.results = store.KeyedLog(os.path.join(state_dir, "results.jsonl"))
        self.fd_closes = store.KeyedLog(os.path.join(state_dir, "fd_closes.jsonl"))
        self.cb_prices = store.KeyedLog(os.path.join(state_dir, "cloudbet.jsonl"))
        cb_cfg = cfg.get("cloudbet") or {}
        if cloudbet == "auto":                    # read-only price reader; None when off or no key stored
            import cloudbet as cloudbet_mod
            cloudbet = cloudbet_mod.Client.from_secret() if cb_cfg.get("enabled") else None
        self.cloudbet = cloudbet
        self.judgments = store.KeyedLog(os.path.join(state_dir, "judgments.jsonl"))
        self.state_path = os.path.join(state_dir, "state.json")
        self.health = Health(os.path.join(state_dir, "health.log"))
        self.budget = budget_mod.Budget(os.path.join(state_dir, "budget.json"),
                                        cfg["budget_monthly_cap"], cfg["budget_reserve"])
        self.http = http or feeds.default_http
        self.odds = odds_client or feeds.OddsClient(engine_config.ODDS_API_KEY,
                                                    engine_config.ODDS_API_BASE, self.budget,
                                                    self.http)
        self.judge = judge or judgment.ask
        self.census_path = census_path or census.CENSUS
        self.cost = len(cfg["regions"].split(",")) * len(cfg["markets"].split(","))

    # ── small state helpers ──────────────────────────────────────────────────
    def state(self) -> dict:
        return store.load_json(self.state_path, {}) or {}

    def set_state(self, key: str, value) -> None:
        s = self.state()
        s[key] = value
        store.save_json(self.state_path, s)

    def league_of(self, sport: str) -> str | None:
        return next((k for k, v in self.cfg["leagues"].items() if v["odds_key"] == sport), None)

    # ── derived views ────────────────────────────────────────────────────────
    def open_picks(self, now: dt.datetime) -> list[dict]:
        """Picks whose event has no closing price yet and has not kicked off."""
        closed = self.closes.keys()
        return [p for p in self.picks.records()
                if f"close|{p['event_id']}" not in closed and parse_time(p["commence"]) > now]

    def unsettled(self) -> list[dict]:
        done = self.results.keys()
        return [p for p in self.picks.records() if f"result|{p['event_id']}" not in done]

    def owed_close_credits(self, now: dt.datetime) -> int:
        """Credits needed to fetch closing prices for picks already made."""
        slots = {(p["sport"], parse_time(p["commence"]).replace(minute=0, second=0))
                 for p in self.open_picks(now)}
        return self.cost * len(slots)


# ── the strategy ─────────────────────────────────────────────────────────────

def sharp_and_best(event: dict, cfg: dict) -> tuple[dict, dict] | None:
    """(Pinnacle fair probabilities, best other price per selection) or None."""
    from sources import odds_api
    books = odds_api.parse_event(event)["books"]
    sharp = books.get(cfg["sharp_book"])
    if not sharp or set(sharp) != set(LABELS):
        return None
    fair = edge.sharp_fair({cfg["sharp_book"]: sharp})["fair_prob"]
    best = {}
    for bk, prices in books.items():
        if bk == cfg["sharp_book"] or bk in cfg["excluded_books"]:
            continue
        for sel in LABELS:
            if sel in prices and (sel not in best or prices[sel] > best[sel][0]):
                best[sel] = (prices[sel], bk)
    return fair, best


# ── jobs ─────────────────────────────────────────────────────────────────────

class Snapshot:
    """Fetch odds for a league when a match without a snapshot is coming up; make picks."""
    name = "snapshot"

    def __init__(self, paper: Paper):
        self.p = paper

    def _targets(self, now: dt.datetime) -> dict:
        cfg, out = self.p.cfg, {}
        horizon = now + dt.timedelta(hours=cfg["snapshot_horizon_hours"])
        lead = now + dt.timedelta(minutes=cfg["snapshot_min_lead_minutes"])
        last = self.p.state().get("events_checked", {})
        for lg, info in cfg["leagues"].items():
            checked = last.get(lg)
            if checked and now - parse_time(checked) < dt.timedelta(hours=6):
                continue                          # the free events list at most every 6 hours
            evs = self.p.odds.events(info["odds_key"])
            last[lg] = iso(now)
            due = [e for e in evs if lead < parse_time(e["commence_time"]) <= horizon
                   and not self.p.snaps.has(f"snap|{e['id']}")]
            if due:
                out[lg] = due
        self.p.set_state("events_checked", last)
        return out

    def due(self, now: dt.datetime) -> bool:
        self._pending = self._targets(now)
        return bool(self._pending)

    def run(self, now: dt.datetime) -> str:
        cfg, made, skipped = self.p.cfg, 0, []
        for lg, due in self._pending.items():
            sport = cfg["leagues"][lg]["odds_key"]
            evs = self.p.odds.odds(sport, cfg["regions"], cfg["markets"], now,
                                   spare=self.p.owed_close_credits(now))
            if evs is None:
                skipped.append(lg)
                continue
            wanted = {e["id"] for e in due}
            lead = now + dt.timedelta(minutes=cfg["snapshot_min_lead_minutes"])
            for ev in evs:
                if ev["id"] not in wanted or parse_time(ev["commence_time"]) <= lead:
                    continue                      # never pick a match about to start
                got = sharp_and_best(ev, cfg)
                order = [ev["home_team"], "Draw", ev["away_team"]]
                books = {}
                for b in ev.get("bookmakers", []):
                    for m in b.get("markets", []):
                        by_name = {o["name"]: o["price"] for o in m["outcomes"]}
                        if m.get("key") == "h2h" and set(by_name) == set(order):
                            books[b["key"]] = [by_name[n] for n in order]   # always home, draw, away
                self.p.snaps.add({"key": f"snap|{ev['id']}", "event_id": ev["id"],
                                  "sport": sport, "league": lg, "seen_utc": iso(now),
                                  "commence": ev["commence_time"], "home": ev["home_team"],
                                  "away": ev["away_team"], "has_sharp": got is not None,
                                  "order": "home,draw,away",   # older lines: the feed's order (alphabetical, draw last)
                                  "books": books})
                if not got:
                    continue
                fair, best = got
                for sel in LABELS:
                    if sel not in best:
                        continue
                    price, book = best[sel]
                    ev_claim = price * fair[sel] - 1.0
                    if ev_claim > cfg["min_edge"]:
                        made += self.p.picks.add({
                            "key": f"pick|{ev['id']}|{sel}|P1", "event_id": ev["id"],
                            "strategy": "P1", "sport": sport, "league": lg,
                            "home": ev["home_team"], "away": ev["away_team"],
                            "commence": ev["commence_time"], "selection": sel,
                            "odds": price, "book": book, "fair_prob": fair[sel],
                            "claimed_ev": ev_claim, "stake": 1.0, "made_utc": iso(now)})
            made += self._cloudbet(lg, sport, [e for e in evs if e["id"] in wanted], now)
        msg = f"{made} new picks from {sum(len(v) for v in self._pending.values())} matches"
        if skipped:
            msg += f"; budget refused snapshots for {', '.join(skipped)}"
            self.p.health.write("warn", "budget", f"snapshot skipped for {skipped}", now)
        return msg


    def _cloudbet(self, lg: str, sport: str, events: list[dict], now: dt.datetime) -> int:
        """
        Research C1: read Cloudbet's prices for this league right after the Odds API
        fetch, store each beside Pinnacle's fair price, and paper-pick the ones 3%
        above it. Read-only. Any failure is a warning and never stops the snapshot.
        """
        cfg = self.p.cfg.get("cloudbet") or {}
        comp = (cfg.get("competitions") or {}).get(lg)
        if not self.p.cloudbet or not comp or not events:
            return 0
        try:
            rows = [dict(r, date=parse_time(r["kickoff"]).date()) for r in self.p.cloudbet.match_odds(comp)]
        except Exception as e:                                    # never let Cloudbet break the loop
            self.p.health.write("warn", "cloudbet", f"{lg}: {type(e).__name__}: {e}"[:200], now)
            return 0
        if not rows:
            self.p.health.write("warn", "cloudbet", f"{lg}: Cloudbet shows no open 1X2 price", now)
            return 0
        made = 0
        lead = now + dt.timedelta(minutes=self.p.cfg["snapshot_min_lead_minutes"])
        for ev in events:
            start = parse_time(ev["commence_time"])
            got = sharp_and_best(ev, self.p.cfg)
            row = names.match(ev["home_team"], ev["away_team"], start.date(), rows)
            if not got or not row or start <= lead:
                continue
            if abs((parse_time(row["kickoff"]) - start).total_seconds()) > 3 * 3600:
                continue                                          # same teams, different fixture
            fair = got[0]
            self.p.cb_prices.add({"key": f"cb|{ev['id']}", "event_id": ev["id"], "league": lg,
                                  "seen_utc": iso(now), "commence": ev["commence_time"],
                                  "home": ev["home_team"], "away": ev["away_team"],
                                  "prices": row["prices"], "max_stake": row["max_stake"], "fair_prob": fair})
            for sel in LABELS:
                claim = row["prices"][sel] * fair[sel] - 1.0
                if claim > cfg.get("min_edge", self.p.cfg["min_edge"]):
                    made += self.p.picks.add({
                        "key": f"pick|{ev['id']}|{sel}|C1", "event_id": ev["id"], "strategy": "C1",
                        "sport": sport, "league": lg, "home": ev["home_team"], "away": ev["away_team"],
                        "commence": ev["commence_time"], "selection": sel, "odds": row["prices"][sel],
                        "book": "cloudbet", "fair_prob": fair[sel], "claimed_ev": claim, "stake": 1.0,
                        "max_stake": row["max_stake"].get(sel), "made_utc": iso(now)})
        return made


class Closing:
    """Fetch Pinnacle's price shortly before kickoff for every match with a pick or census price."""
    name = "closing"

    def __init__(self, paper: Paper):
        self.p = paper

    def _census_open(self, now: dt.datetime) -> list[dict]:
        recs = census._read(self.p.census_path)
        closed = {r["event_id"] for r in recs if r.get("kind") == "close"
                  and r["minutes_to_kickoff"] <= self.p.cfg["close_window_minutes"]}
        return [r for r in recs if r.get("kind") == "price" and r["event_id"] not in closed
                and r.get("commence") and parse_time(r["commence"]) > now]

    def _sports_due(self, now: dt.datetime) -> set:
        cfg = self.p.cfg
        lo = now + dt.timedelta(minutes=cfg["close_min_lead_minutes"])
        hi = now + dt.timedelta(minutes=cfg["close_window_minutes"])
        last = self.p.state().get("close_fetched", {})
        sports = set()
        items = [(x["sport"], x["commence"]) for x in self.p.open_picks(now)]
        items += [(x["sport_key"], x["commence"]) for x in self._census_open(now)]
        for sport, commence in items:
            if lo <= parse_time(commence) <= hi:
                prev = last.get(sport)
                if not prev or now - parse_time(prev) >= dt.timedelta(minutes=cfg["close_refetch_minutes"]):
                    sports.add(sport)
        return sports

    def due(self, now: dt.datetime) -> bool:
        self._sports = self._sports_due(now)
        return bool(self._sports)

    def run(self, now: dt.datetime) -> str:
        cfg, n, refused = self.p.cfg, 0, []
        hi = now + dt.timedelta(minutes=cfg["close_window_minutes"])
        last = self.p.state().get("close_fetched", {})
        open_ids = {p["event_id"] for p in self.p.open_picks(now)}
        census_ids = {r["event_id"] for r in self._census_open(now)}
        for sport in sorted(self._sports):
            evs = self.p.odds.odds(sport, cfg["regions"], cfg["markets"], now)
            if evs is None:
                refused.append(sport)
                continue
            last[sport] = iso(now)
            for ev in evs:
                start = parse_time(ev["commence_time"])
                if not now < start <= hi:
                    continue
                if ev["id"] in census_ids:
                    census.log_close(ev, now=now, path=self.p.census_path)
                if ev["id"] not in open_ids:
                    continue
                got = sharp_and_best(ev, cfg)
                if not got:
                    continue
                from sources import odds_api
                n += self.p.closes.add({
                    "key": f"close|{ev['id']}", "event_id": ev["id"], "seen_utc": iso(now),
                    "minutes_to_kickoff": round((start - now).total_seconds() / 60, 1),
                    "sharp_odds": odds_api.parse_event(ev)["books"][cfg["sharp_book"]],
                    "fair_prob": got[0]})
        self.p.set_state("close_fetched", last)
        if refused:
            self.p.health.write("warn", "budget", f"closing fetch refused for {refused}", now)
        return f"{n} closing prices recorded" + (f"; refused {refused}" if refused else "")


class Settle:
    """Settle picks from this season's Football-Data files."""
    name = "settle"

    def __init__(self, paper: Paper):
        self.p = paper

    def _ready(self, now: dt.datetime) -> list[dict]:
        after = dt.timedelta(minutes=self.p.cfg["settle_after_minutes"])
        return [p for p in self.p.unsettled() if parse_time(p["commence"]) + after < now]

    def _owed_fd_close(self, now: dt.datetime) -> list[dict]:
        """Settled picks still without the results file's closing prices (not older than the give-up age)."""
        res, have = self.p.results.latest(), self.p.fd_closes.keys()
        limit = dt.timedelta(days=self.p.cfg["settle_give_up_days"])
        return [p for p in self.p.picks.records()
                if (res.get(f"result|{p['event_id']}") or {}).get("status") == "settled"
                and f"fdclose|{p['event_id']}" not in have
                and now - parse_time(p["commence"]) <= limit]

    def due(self, now: dt.datetime) -> bool:
        last = self.p.state().get("settled_utc")
        if last and now - parse_time(last) < dt.timedelta(hours=self.p.cfg["settle_every_hours"]):
            return False
        return bool(self._ready(now) or self._owed_fd_close(now))

    def run(self, now: dt.datetime) -> str:
        cfg, done, gave_up, stand_ins = self.p.cfg, 0, 0, 0
        by_league: dict = {}
        for p in self._ready(now) + self._owed_fd_close(now):
            by_league.setdefault(p["league"], []).append(p)
        cache = os.path.join(self.p.dir, "results_cache")
        for lg, picks in by_league.items():
            rows = feeds.results(lg, now.date(), cache, cfg["results_cache_hours"], self.p.http)
            for pk in picks:
                key = f"result|{pk['event_id']}"
                start = parse_time(pk["commence"])
                row = names.match(pk["home"], pk["away"], start.date(), rows)
                if row and row.get("close"):
                    stand_ins += self.p.fd_closes.add({
                        "key": f"fdclose|{pk['event_id']}", "event_id": pk["event_id"],
                        "close": row["close"], "seen_utc": iso(now)})
                if self.p.results.has(key):
                    continue
                if row:
                    done += self.p.results.add({
                        "key": key, "event_id": pk["event_id"], "status": "settled",
                        "fthg": row["fthg"], "ftag": row["ftag"],
                        "fd_home": row["home"], "fd_away": row["away"], "seen_utc": iso(now)})
                elif now - start > dt.timedelta(days=cfg["settle_give_up_days"]):
                    gave_up += self.p.results.add({"key": key, "event_id": pk["event_id"],
                                                   "status": "unmatched", "seen_utc": iso(now)})
        self.p.set_state("settled_utc", iso(now))
        if gave_up:
            self.p.health.write("warn", "settle", f"{gave_up} events could not be matched", now)
        return (f"{done} events settled, {gave_up} given up"
                + (f", {stand_ins} stand-in closing prices stored" if stand_ins else ""))


JUDGE_PROMPT = """You are reviewing paper bets for a recommend-only football research project.
No money is staked and nothing will be placed. Each bet below was chosen by a rule:
a bookmaker's price is higher than Pinnacle's margin-free price by the stated edge.

Your job is narrow. Veto a bet only for a concrete reason the price comparison could
not see, for example: confirmed key injuries or suspensions announced after the
prices were set, a likely data error (wrong teams, a stale or obviously wrong price),
or the match not being played as listed. If you have no concrete reason, do not veto.
Before deciding, search the web once per match for that match's latest team news.
Do not give betting advice beyond this.

Bets:
{bets}

Answer with one JSON object and nothing else:
{{"verdicts": [{{"key": "<the text inside the square brackets>", "veto": true or false, "reason": "<one short sentence>"}}]}}"""


class Judge:
    """At most a few times a day, ask Claude to flag or veto new picks. Fails safe."""
    name = "judgment"

    def __init__(self, paper: Paper, local_now=None):
        self.p = paper
        self.local_now = local_now or (lambda now: now.astimezone())

    def _todo(self, now: dt.datetime) -> list[dict]:
        soon = now + dt.timedelta(minutes=30)
        return [p for p in self.p.picks.records()
                if not self.p.judgments.has(f"judgment|{p['key']}")
                and parse_time(p["commence"]) > soon]

    def due(self, now: dt.datetime) -> bool:
        j = self.p.cfg["judgment"]
        if not j["enabled"] or self.local_now(now).hour not in j["local_hours"]:
            return False
        last = self.p.state().get("judged_utc")
        if last and now - parse_time(last) < dt.timedelta(hours=j["min_gap_hours"]):
            return False
        return bool(self._todo(now))

    def run(self, now: dt.datetime) -> str:
        j, todo = self.p.cfg["judgment"], self._todo(now)
        self.p.set_state("judged_utc", iso(now))      # one attempt per slot, even if it fails
        lines = [f"- [{p['key']}] {p['home']} v {p['away']} ({self.p.cfg['leagues'][p['league']]['name']}), "
                 f"kick-off {p['commence']}, {p['selection']} at {p['odds']} ({p['book']}), "
                 f"Pinnacle fair {p['fair_prob']:.3f}, edge {p['claimed_ev'] * 100:+.1f}%" for p in todo]
        answer, status = self.p.judge(JUDGE_PROMPT.format(bets="\n".join(lines)),
                                      model=j["model"], timeout_s=j["timeout_seconds"],
                                      allowed_tools=j["allowed_tools"])
        if answer is None:
            self.p.health.write("warn", "judgment", f"no judgment: {status}", now)
            return f"no judgment ({status}); picks unaffected"
        wanted = sorted((p["key"] for p in todo), key=len, reverse=True)
        n = 0
        for v in answer.get("verdicts", []) if isinstance(answer.get("verdicts"), list) else []:
            if not isinstance(v, dict):
                continue
            key = next((k for k in wanted if k in str(v.get("key", ""))), None)  # tolerates "key pick|..."
            if key:
                n += self.p.judgments.add({"key": f"judgment|{key}", "pick_key": key,
                                           "veto": bool(v.get("veto")),
                                           "reason": str(v.get("reason", ""))[:300],
                                           "model": j["model"], "seen_utc": iso(now)})
        return f"{n} of {len(todo)} picks judged"


class Scorecard:
    """Rewrite scorecard.md once a day (and after any settlement)."""
    name = "scorecard"

    def __init__(self, paper: Paper):
        self.p = paper

    def due(self, now: dt.datetime) -> bool:
        s = self.p.state()
        last, settled = s.get("scorecard_utc"), s.get("settled_utc")
        if not last:
            return True
        return (now - parse_time(last) >= dt.timedelta(hours=24)
                or (settled is not None and settled > last))

    def run(self, now: dt.datetime) -> str:
        text = scorecard(self.p, now)
        tmp = os.path.join(self.p.dir, "scorecard.md.part")
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp, os.path.join(self.p.dir, "scorecard.md"))
        self.p.set_state("scorecard_utc", iso(now))
        return "scorecard written"


# ── the scorecard ────────────────────────────────────────────────────────────

def settled_bets(paper: Paper) -> list[dict]:
    """Every settled pick with profit and CLV (None when no closing price)."""
    res = paper.results.latest()
    closes = paper.closes.latest()
    vetoes = {r["pick_key"]: r["veto"] for r in paper.judgments.records()}
    fd = paper.fd_closes.latest()
    out = []
    for p in paper.picks.records():
        r = res.get(f"result|{p['event_id']}")
        if not r or r.get("status") != "settled":
            continue
        h, a = r["fthg"], r["ftag"]
        won = {"home": h > a, "draw": h == a, "away": h < a}[p["selection"]]
        c = closes.get(f"close|{p['event_id']}")
        proxy = ((fd.get(f"fdclose|{p['event_id']}") or {}).get("close") or {}).get(PROXY_BOOK)
        try:
            proxy_fair = devig.devig_power(list(proxy)) if proxy else None
        except ValueError:
            proxy_fair = None
        out.append({"cluster": p["event_id"], "league": p["league"], "stake": p["stake"],
                    "strategy": p.get("strategy", "P1"),
                    "odds": p["odds"], "profit": p["stake"] * (p["odds"] - 1) if won else -p["stake"],
                    "clv": p["odds"] * c["fair_prob"][p["selection"]] - 1.0 if c else None,
                    "clv_proxy": (p["odds"] * proxy_fair[LABELS.index(p["selection"])] - 1.0
                                  if proxy_fair else None),
                    "claimed_ev": p["claimed_ev"], "veto": vetoes.get(p["key"])})
    return out


def _line(label: str, s: dict | None) -> str:
    if not s:
        return f"| {label} | 0 | - | - | - | - |"
    clv = "-" if s["clv"] is None else f"{s['clv'] * 100:+.1f}%"
    clv_ci = "-" if not s["clv_ci"] else f"{s['clv_ci'][0] * 100:+.1f} to {s['clv_ci'][1] * 100:+.1f}"
    return (f"| {label} | {s['bets']} | {s['roi'] * 100:+.1f}% | "
            f"{s['roi_ci'][0] * 100:+.1f} to {s['roi_ci'][1] * 100:+.1f} | {clv} | {clv_ci} |")


def scorecard(paper: Paper, now: dt.datetime) -> str:
    all_picks = paper.picks.records()
    all_bets = settled_bets(paper)
    picks = [p for p in all_picks if p.get("strategy", "P1") == "P1"]
    bets = [x for x in all_bets if x["strategy"] == "P1"]
    started = [p for p in picks if parse_time(p["commence"]) <= now]
    closed = paper.closes.keys()
    with_close = sum(1 for p in started if f"close|{p['event_id']}" in closed)
    b = paper.budget.status(now)
    recent = [h for h in paper.health.tail(400)
              if now - parse_time(h["utc"]) <= dt.timedelta(hours=24)]
    errors = [h for h in recent if h["level"] in ("error", "warn")]
    last_beat = paper.health.tail(1)
    try:
        with open(os.path.join(paper.dir, "heartbeat.txt"), encoding="utf-8") as f:
            heartbeat = f.read().strip()
    except FileNotFoundError:
        heartbeat = None
    try:
        with open(os.path.join(paper.dir, "loop.lock"), encoding="utf-8") as f:
            running = store._pid_alive(int(f.read().split()[0]))
    except (OSError, ValueError, IndexError):
        running = False
    L = [f"# Paper trading scorecard", "",
         f"Written {now.astimezone().strftime('%Y-%m-%d %H:%M')} (local). Strategy P1: best "
         f"price in the feed against Pinnacle's fair price, +{paper.cfg['min_edge'] * 100:.0f}%, "
         "1 unit flat. No money involved.", "",
         "## Health", "",
         f"- Loop running now: {'yes' if running else 'NO'}. Last heartbeat: {heartbeat or 'none'} "
         f"(it beats every few minutes while running)",
         f"- Last job that did something: {last_beat[0]['utc'] if last_beat else 'none'}",
         f"- Warnings and errors in the last 24 hours: {len(errors)}"]
    L += [f"  - {h['utc']} {h['level']} {h['what']}: {h['detail'][:160]}" for h in errors[-5:]]
    L += [f"- Odds API credits this month: {b['spent']} spent by this loop, cap {b['cap']}, "
          f"provider says {b['remaining'] if b['remaining'] is not None else 'unknown'} left; "
          f"{b['refused']} calls refused by the budget", "",
          "## Picks", "",
          f"- Made: {len(picks)}. Kicked off: {len(started)}. Closing price captured for "
          f"{with_close} of {len(started)}"
          + (f" ({with_close / len(started) * 100:.0f}%)." if started else "."),
          f"- Settled: {len(bets)}. Waiting for a result: "
          f"{sum(1 for p in paper.unsettled() if p.get('strategy', 'P1') == 'P1')}.", "",
          "| Group | Settled bets | Return per bet | 95% interval | CLV | 95% interval |",
          "|---|---|---|---|---|---|"]
    if bets:
        L.append(_line("**All**", metrics.bet_summary(bets)))
        for lg in sorted({x["league"] for x in bets}):
            L.append(_line(lg, metrics.bet_summary([x for x in bets if x["league"] == lg])))
        kept = [x for x in bets if x["veto"] is False]
        vetoed = [x for x in bets if x["veto"] is True]
        L.append(_line("Claude did not veto", metrics.bet_summary(kept) if kept else None))
        L.append(_line("Claude vetoed", metrics.bet_summary(vetoed) if vetoed else None))
    else:
        L.append("| **All** | 0 | - | - | - | - |")
    px = [dict(x, clv=x["clv_proxy"]) for x in bets if x["clv_proxy"] is not None]
    both = [x for x in bets if x["clv"] is not None and x["clv_proxy"] is not None]
    L += ["", "## Stand-in closing price (Betfair Exchange close from the results file)", "",
          "Used only to score picks whose Pinnacle close was missed. It is a stand-in: on past "
          "seasons it read 0.1 points below Pinnacle's CLV on average (156 bets, interval -0.6 to "
          "+0.4), and one bet can differ by 3 points. It never counts toward the 300-pick test.", ""]
    if px:
        s = metrics.bet_summary(px)
        L.append(f"- Settled picks with a stand-in close: {len(px)}. CLV by the stand-in: "
                 f"{s['clv'] * 100:+.1f}% ({s['clv_ci'][0] * 100:+.1f} to {s['clv_ci'][1] * 100:+.1f}).")
    else:
        L.append("- No settled pick has a stand-in close yet.")
    if both:
        d = metrics.paired_diff([x["clv_proxy"] for x in both], [x["clv"] for x in both])
        L.append(f"- Live check on {d['n']} picks with both closes: stand-in minus Pinnacle "
                 f"{d['mean'] * 100:+.2f} points"
                 + (f" ({d['lo'] * 100:+.2f} to {d['hi'] * 100:+.2f})." if d["n"] > 1 else "."))
    else:
        L.append("- Live check against Pinnacle's close: no pick has both yet.")
    cb = paper.cb_prices.records()
    c1_picks = [p for p in all_picks if p.get("strategy") == "C1"]
    c1 = [x for x in all_bets if x["strategy"] == "C1"]
    L += ["", "## Cloudbet (strategy C1: Cloudbet's price against Pinnacle's fair price, +3%)", "",
          "Prices are read only. Nothing is placed. The two prices are read seconds apart."]
    if not paper.cloudbet and not cb:
        L.append("- Not running: no Cloudbet key stored, or switched off in the config.")
    else:
        n = sum(len(r["prices"]) for r in cb)
        over0 = sum(1 for r in cb for s in LABELS if r["prices"][s] * r["fair_prob"][s] > 1.0)
        over3 = sum(1 for r in cb for s in LABELS if r["prices"][s] * r["fair_prob"][s] > 1.03)
        L.append(f"- Cloudbet prices logged: {n} on {len(cb)} matches. Above Pinnacle's fair price: "
                 + (f"{over0} ({over0 / n * 100:.1f}%). Above it by 3%: {over3} ({over3 / n * 100:.1f}%)."
                    if n else "none yet."))
        with_c = sum(1 for p in c1_picks if parse_time(p["commence"]) <= now
                     and f"close|{p['event_id']}" in closed)
        c1_started = sum(1 for p in c1_picks if parse_time(p["commence"]) <= now)
        L.append(f"- C1 picks made: {len(c1_picks)}. Kicked off: {c1_started}. "
                 f"Pinnacle closing price captured for {with_c}.")
        L += ["", "| Group | Settled bets | Return per bet | 95% interval | CLV | 95% interval |",
              "|---|---|---|---|---|---|",
              _line("**C1 (Cloudbet)**", metrics.bet_summary(c1) if c1 else None)]
    cs = census.summary(paper.census_path)
    L += ["", "## SportyBet census (prices from screenshots)", "",
          f"- Prices logged: {cs['prices']} on {cs['events']} matches; "
          f"beating Pinnacle's fair price by 2%+: "
          + ("-" if cs["share_ev_above_2pct"] is None else f"{cs['share_ev_above_2pct'] * 100:.1f}%"),
          f"- CLV of all census prices: "
          + ("no closing prices yet" if not cs["clv_all"] else
             f"{cs['clv_all']['mean'] * 100:+.1f}% over {cs['clv_all']['n']}"),
          f"- Kill rule: {cs['kill_rule']}", "",
          "How to read this: CLV is the measure. A return per bet means little until there are "
          "hundreds of settled bets; look at whether the CLV interval sits above zero."]
    return "\n".join(L) + "\n"
