"""
KAIROS — paper-trading tests (offline: fake feeds, fake clock, fake Claude).

Run:  python paper/test_paper.py   (exits non-zero on any failure)

Covers the brief's Phase 4 requirements: state in files, safe to kill and
restart, no double logging, a call budget that cannot be overspent, closing
prices, automatic settlement, a judgment pass that fails safe, and the scorecard.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import jobs   # noqa: E402
import feeds  # noqa: E402
import names  # noqa: E402
import main as run  # noqa: E402

from core import budget as budget_mod      # noqa: E402
from core import judgment, scheduler, store  # noqa: E402
import census                              # noqa: E402

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


UTC = dt.timezone.utc
T0 = dt.datetime(2026, 10, 8, 9, 0, tzinfo=UTC)            # a Thursday morning


def at(hours: float) -> dt.datetime:
    return T0 + dt.timedelta(hours=hours)


def book(key, h, d, a, home="Queens Park Rangers", away="West Bromwich Albion"):
    return {"key": key, "markets": [{"key": "h2h", "outcomes": [
        {"name": home, "price": h}, {"name": away, "price": a}, {"name": "Draw", "price": d}]}]}


class World:
    """Fake Odds API and Football-Data. Prices can be changed between calls."""

    def __init__(self):
        self.calls = []
        self.remaining = 500
        self.kickoff = at(50)                              # Saturday 11:00 UTC
        self.pin = (2.10, 3.40, 3.60)
        self.soft = (2.40, 3.30, 3.40)                     # home clearly above Pinnacle fair
        self.csv = ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
                    "E1,10/10/2026,QPR,West Brom,2,0,H\n")

    def event(self, pin=None, soft=None, eid="ev1", kickoff=None, with_pin=True):
        pin, soft = pin or self.pin, soft or self.soft
        books = [book("williamhill", *soft), book("betfair_ex_uk", 9.0, 9.0, 9.0)]
        if with_pin:
            books.append(book("pinnacle", *pin))
        return {"id": eid, "sport_key": "soccer_efl_champ", "home_team": "Queens Park Rangers",
                "away_team": "West Bromwich Albion",
                "commence_time": (kickoff or self.kickoff).isoformat().replace("+00:00", "Z"),
                "bookmakers": books}

    def http(self, url, timeout=30.0):
        self.calls.append(url)
        if "/events?" in url:
            if "soccer_efl_champ" in url:
                return json.dumps([{k: v for k, v in self.event().items() if k != "bookmakers"}]).encode(), {}
            return b"[]", {}
        if "/odds/" in url:
            self.remaining -= 2
            evs = [self.event()] if "soccer_efl_champ" in url else []
            return json.dumps(evs).encode(), {"x-requests-remaining": str(self.remaining),
                                              "x-requests-last": "2"}
        if "football-data" in url:
            return self.csv.encode(), {}
        raise AssertionError(f"unexpected url {url}")

    def odds_calls(self):
        return [u for u in self.calls if "/odds/" in u]


def make(world, state_dir, judge=None, cfg_over=None):
    cfg = run.load_config()
    cfg.update(cfg_over or {})
    budget = budget_mod.Budget(os.path.join(state_dir, "budget.json"),
                               cfg["budget_monthly_cap"], cfg["budget_reserve"])
    client = feeds.OddsClient("KEY", "https://api.example/v4", budget, world.http)
    census_path = os.path.join(state_dir, "census.jsonl")
    paper, loop = run.build(cfg, state_dir, odds_client=client, http=world.http,
                            judge=judge or (lambda *a, **k: (None, "disabled in test")),
                            census_path=census_path)
    paper.budget = budget
    return paper, loop


def tick(loop, when):
    loop.clock = lambda: when
    return dict(loop.tick())


# ── core pieces ──────────────────────────────────────────────────────────────

def test_store() -> None:
    d = tempfile.mkdtemp()
    log = store.KeyedLog(os.path.join(d, "x.jsonl"))
    check("first write goes in", log.add({"key": "a", "v": 1}))
    check("same key is not written twice", not log.add({"key": "a", "v": 2}))
    check("a fresh reader sees one record", len(store.KeyedLog(log.path).records()) == 1)
    with open(log.path, "a") as f:
        f.write('{"key": "torn"')                           # a write cut off by a crash
    check("a torn last line is skipped", len(store.KeyedLog(log.path).records()) == 1)
    p = os.path.join(d, "s.json")
    store.save_json(p, {"n": 1})
    check("json state round trip", store.load_json(p) == {"n": 1}
          and not [x for x in os.listdir(d) if x.endswith(".part")])
    lock = os.path.join(d, "loop.lock")
    with store.SingleInstance(lock):
        try:
            with store.SingleInstance(lock):
                check("a second copy is refused", False)
        except RuntimeError:
            check("a second copy is refused", True)
    check("the lock is released on exit", not os.path.exists(lock))
    with open(lock, "w") as f:
        f.write("999999 0")                                 # left by a process that died
    with store.SingleInstance(lock):
        check("a stale lock is taken over", True)


def test_budget() -> None:
    d = tempfile.mkdtemp()
    b = budget_mod.Budget(os.path.join(d, "b.json"), monthly_cap=10, reserve=5)
    now = T0
    check("spend allowed under the cap", b.allow(2, now))
    b.record(2, now, remaining=100)
    check("spare credits are protected", not b.allow(2, now, spare=7))
    for _ in range(4):
        b.record(2, now, remaining=100)
    check("cap reached: refused", not b.allow(2, now))
    check("refusals are counted", b.status(now)["refused"] == 2)
    check("a new month starts at zero", b.allow(2, dt.datetime(2026, 11, 1, tzinfo=UTC)))
    b2 = budget_mod.Budget(os.path.join(d, "b2.json"), monthly_cap=400, reserve=60)
    b2.record(2, now, remaining=61)
    check("the provider's own count and the reserve win over the cap", not b2.allow(2, now))


def test_scheduler() -> None:
    d = tempfile.mkdtemp()

    class Boom:
        name = "boom"
        def due(self, now): return True
        def run(self, now): raise ValueError("bad data")

    class Fine:
        name = "fine"
        def due(self, now): return True
        def run(self, now): return "did it"

    loop = scheduler.Loop([Boom(), Fine()], os.path.join(d, "h.log"), os.path.join(d, "STOP"),
                          clock=lambda: T0)
    out = dict(loop.tick())
    check("one failing job does not stop the others", out["fine"] == "did it"
          and out["boom"].startswith("error"))
    h = scheduler.Health(os.path.join(d, "h.log")).tail()
    check("the failure is in the health log", any(x["level"] == "error" and x["what"] == "boom" for x in h))
    open(os.path.join(d, "STOP"), "w").close()
    loop.run_forever(sleep_s=5)
    check("a stop file ends the loop and is cleared", not os.path.exists(os.path.join(d, "STOP")))


def test_judgment_fails_safe() -> None:
    check("JSON found inside prose",
          judgment.first_json_object('Sure. {"verdicts": [{"key": "a", "veto": false}]} done')
          == {"verdicts": [{"key": "a", "veto": False}]})
    check("braces inside strings handled",
          judgment.first_json_object('{"r": "a } b", "n": 1}') == {"r": "a } b", "n": 1})

    class P:
        def __init__(self, rc, out, err=""):
            self.returncode, self.stdout, self.stderr = rc, out, err

    ok = lambda *a, **k: P(0, json.dumps({"result": '{"verdicts": []}', "is_error": False}))  # noqa: E731
    check("a good answer is parsed", judgment.ask("x", runner=ok, cli="claude")[0] == {"verdicts": []})
    for label, runner in (
        ("non-zero exit", lambda *a, **k: P(1, "", "usage limit reached")),
        ("no JSON in answer", lambda *a, **k: P(0, json.dumps({"result": "I cannot help"}))),
        ("CLI error flag", lambda *a, **k: P(0, json.dumps({"result": "oops", "is_error": True}))),
    ):
        check(f"fails safe on {label}", judgment.ask("x", runner=runner, cli="claude")[0] is None)

    def slow(*a, **k):
        raise subprocess.TimeoutExpired("claude", 1)
    check("fails safe on timeout", judgment.ask("x", runner=slow, cli="claude")[0] is None)
    check("fails safe with no CLI", judgment.ask("x", runner=ok, cli=None)[0] is None
          or judgment.find_cli() is not None)


# ── feeds and names ──────────────────────────────────────────────────────────

def test_names_and_feeds() -> None:
    rows = feeds.parse_results("﻿Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR\n"
                               "E1,10/10/2026,QPR,West Brom,2,0,H\n"
                               "E1,10/10/2026,Wrexham,Derby,1,1,D\n"
                               "E1,10/10/2026,Bristol City,Charlton,0,1,A\n"
                               "E1,bad,X,Y,1,0,H\n")
    check("results parsed, bad rows dropped", len(rows) == 3 and rows[0]["fthg"] == 2)
    d = dt.date(2026, 10, 10)
    check("QPR matched from Queens Park Rangers",
          names.match("Queens Park Rangers", "West Bromwich Albion", d, rows)["home"] == "QPR")
    check("Wrexham AFC and Derby County matched",
          names.match("Wrexham AFC", "Derby County", d, rows)["away"] == "Derby")
    check("a date a day out still matches",
          names.match("Bristol City", "Charlton Athletic", dt.date(2026, 10, 11), rows) is not None)
    check("an unrelated fixture is not guessed",
          names.match("Sunderland", "Leeds United", d, rows) is None)
    check("a different date is not matched",
          names.match("Queens Park Rangers", "West Bromwich Albion", dt.date(2026, 10, 20), rows) is None)
    check("season code", feeds.season_code(dt.date(2026, 10, 3)) == "2627"
          and feeds.season_code(dt.date(2027, 5, 1)) == "2627")
    w, c = World(), tempfile.mkdtemp()
    feeds.results("E1", d, c, 12, w.http)
    feeds.results("E1", d, c, 12, w.http)
    check("results file downloaded once within the cache window",
          sum("football-data" in u for u in w.calls) == 1)


# ── the jobs, end to end ─────────────────────────────────────────────────────

def test_end_to_end() -> None:
    w, d = World(), tempfile.mkdtemp()
    verdicts = []

    def judge(prompt, **kw):
        verdicts.append(prompt)
        key = "pick|ev1|home|P1"
        return {"verdicts": [{"key": key, "veto": True, "reason": "keeper injured"}]}, "ok"

    paper, loop = make(w, d, judge=judge)

    # Thursday 09:00 UTC: the Saturday match is inside the 60-hour horizon.
    out = tick(loop, T0)
    picks = paper.picks.records()
    check("snapshot makes a pick where the best price beats Pinnacle's fair price",
          len(picks) == 1 and picks[0]["selection"] == "home" and picks[0]["book"] == "williamhill"
          and picks[0]["odds"] == 2.40, f"{out} {picks}")
    check("the exchange price is not used", all(p["book"] != "betfair_ex_uk" for p in picks))
    check("one odds call spent 2 credits", len(w.odds_calls()) == 1
          and paper.budget.status(T0)["spent"] == 2)
    check("every bookmaker's price is stored with the snapshot",
          set(paper.snaps.records()[0]["books"]) == {"williamhill", "betfair_ex_uk", "pinnacle"})

    # Run again an hour later, and again after a 'restart' with fresh objects.
    tick(loop, at(1))
    paper2, loop2 = make(w, d, judge=judge)
    tick(loop2, at(2))
    check("no double logging across runs and restarts",
          len(paper2.picks.records()) == 1 and len(w.odds_calls()) == 1)

    # The judgment pass runs only in the configured local hours.
    paper2.cfg["judgment"]["local_hours"] = [at(3).astimezone().hour]
    tick(loop2, at(3))
    j = paper2.judgments.records()
    check("Claude's verdict is logged next to the pick, not applied to it",
          len(j) == 1 and j[0]["veto"] is True and len(paper2.picks.records()) == 1)
    check("the prompt carries the pick", "Queens Park Rangers" in verdicts[0])

    # 30 minutes before kickoff: the closing job fetches Pinnacle again.
    w.pin = (1.95, 3.50, 4.00)
    tick(loop2, w.kickoff - dt.timedelta(minutes=30))
    closes = paper2.closes.records()
    check("closing price captured shortly before kickoff",
          len(closes) == 1 and closes[0]["minutes_to_kickoff"] == 30.0 and len(w.odds_calls()) == 2)
    tick(loop2, w.kickoff - dt.timedelta(minutes=20))
    check("no second closing fetch within the refetch gap", len(w.odds_calls()) == 2)

    # After the match: settle from the Football-Data file.
    tick(loop2, w.kickoff + dt.timedelta(hours=3))
    res = paper2.results.records()
    check("settled automatically from the results file",
          len(res) == 1 and res[0]["status"] == "settled" and res[0]["fthg"] == 2)
    bets = jobs.settled_bets(paper2)
    fc = jobs.edge.sharp_fair({"pinnacle": dict(zip(jobs.LABELS, w.pin))})["fair_prob"]["home"]
    check("profit and CLV of the settled pick",
          abs(bets[0]["profit"] - 1.40) < 1e-9 and abs(bets[0]["clv"] - (2.40 * fc - 1)) < 1e-9)
    card = open(os.path.join(d, "scorecard.md"), encoding="utf-8").read()
    check("scorecard written with the settled bet and the veto split",
          "Settled: 1" in card and "Claude vetoed" in card and "Closing price captured for 1 of 1" in card,
          card[:400])


def test_missed_windows_and_budget() -> None:
    # The PC was off from Thursday until after kickoff: nothing is picked late,
    # the close is missed (not faked), and the match still settles.
    w, d = World(), tempfile.mkdtemp()
    paper, loop = make(w, d)
    tick(loop, w.kickoff - dt.timedelta(hours=2))
    check("no pick inside three hours of kickoff", paper.picks.records() == [])

    w2, d2 = World(), tempfile.mkdtemp()
    paper2, loop2 = make(w2, d2)
    tick(loop2, T0)
    tick(loop2, w2.kickoff + dt.timedelta(hours=4))       # woke up after the match
    check("a missed close is not faked", paper2.closes.records() == []
          and len(w2.odds_calls()) == 1)
    check("the match still settles", len(paper2.results.records()) == 1)
    bets = jobs.settled_bets(paper2)
    check("a settled pick without a close has CLV None", bets and bets[0]["clv"] is None)

    # Budget: with the cap nearly used, the snapshot is refused and logged.
    w3, d3 = World(), tempfile.mkdtemp()
    paper3, loop3 = make(w3, d3, cfg_over={"budget_monthly_cap": 1})
    tick(loop3, T0)
    check("budget refusal: no odds call, no pick", w3.odds_calls() == [] and paper3.picks.records() == [])
    check("the refusal is in the health log",
          any(h["what"] == "budget" for h in paper3.health.tail()))

    # No Pinnacle price: no pick (no sharp line, skip).
    w4, d4 = World(), tempfile.mkdtemp()
    w4.event_orig = w4.event
    w4.event = lambda **k: w4.event_orig(with_pin=False)
    paper4, loop4 = make(w4, d4)
    tick(loop4, T0)
    check("no Pinnacle price: snapshot kept, no pick",
          paper4.picks.records() == [] and paper4.snaps.records()[0]["has_sharp"] is False)


def test_judgment_failure_is_safe() -> None:
    w, d = World(), tempfile.mkdtemp()
    paper, loop = make(w, d, judge=lambda *a, **k: (None, "usage limit reached"))
    paper.cfg["judgment"]["local_hours"] = list(range(24))
    out = tick(loop, T0)
    check("a failed judgment leaves the pick in place",
          len(paper.picks.records()) == 1 and paper.judgments.records() == [])
    check("the failure is reported", "no judgment" in out.get("judgment", ""), str(out))
    out2 = tick(loop, at(1))
    check("no retry storm: one attempt per slot", "judgment" not in out2)


def test_census_closing() -> None:
    w, d = World(), tempfile.mkdtemp()
    paper, loop = make(w, d)
    paper.cfg["leagues"] = {}                                  # nothing watched: census only
    census.log_prices(w.event(), {"home": 2.30}, "soccer_efl_champ", now=T0,
                      path=paper.census_path)
    tick(loop, w.kickoff - dt.timedelta(minutes=40))
    s = census.summary(paper.census_path)
    check("a SportyBet census price gets its closing price from the loop",
          s["clv_all"] is not None and s["clv_all"]["n"] == 1, str(s))


def test_status_command() -> None:
    out = subprocess.run([sys.executable, os.path.join(HERE, "main.py"), "--status"],
                         capture_output=True, text=True, timeout=120)
    check("--status prints a scorecard", out.returncode == 0 and "Paper trading scorecard" in out.stdout,
          out.stderr[-300:])


def run_all() -> None:
    for fn in (test_store, test_budget, test_scheduler, test_judgment_fails_safe,
               test_names_and_feeds, test_end_to_end, test_missed_windows_and_budget,
               test_judgment_failure_is_safe, test_census_closing, test_status_command):
        fn()
    print("\n" + ("ALL PAPER TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
