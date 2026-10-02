"""
KAIROS — backtest harness tests (offline, synthetic data; no network, no key).

Run:  python test_harness.py   (exits non-zero on any failure)

The leakage tests are the ones that matter most:
  - PreMatch carries no result, statistic or closing price;
  - the runner never shows a strategy a result dated on or after the day the
    odds for the match being decided were collected;
  - leak_check passes an honest learning strategy and catches one that fits on
    the whole history up front.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import json
import math
import os
import tempfile

import census
import fd_data
import fd_fetch
import metrics
import score
import strategies
import walk

import edge      # engine, put on the path by strategies
import market

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


HEADER = ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,HS,AS,HST,AST,HC,AC,"
          "B365H,B365D,B365A,BWH,BWD,BWA,PSH,PSD,PSA,VCH,VCD,VCA,BFEH,BFED,BFEA,"
          "MaxH,MaxD,MaxA,AvgH,AvgD,AvgA,B365>2.5,B365<2.5,P>2.5,P<2.5,"
          "B365CH,B365CD,B365CA,PSCH,PSCD,PSCA,VCCH,VCCD,VCCA,PC>2.5,PC<2.5")


def row(date, home, away, hg, ag, b365=(2.0, 3.5, 3.8), bw=(1.95, 3.4, 3.7),
        ps=(2.02, 3.6, 3.9), psc=(1.9, 3.7, 4.3), ou=(1.9, 1.9), p_ou=(1.95, 1.95),
        pc_ou=(1.8, 2.1)) -> str:
    ftr = "H" if hg > ag else "A" if ag > hg else "D"
    vals = ["E0", date, home, away, hg, ag, ftr, 12, 9, 5, 3, 6, 4,
            *b365, *bw, *ps, 1.9, 3.3, 3.6, 2.1, 3.7, 4.1,
            2.1, 3.7, 4.1, 1.98, 3.45, 3.75, *ou, *p_ou,
            1.5, 4.0, 7.0, *psc, 1.5, 4.0, 7.0, *pc_ou]
    return ",".join(str(v) for v in vals)


def sample(rows: list[str]):
    return fd_data.parse(HEADER + "\n" + "\n".join(rows) + "\n", "E0", "1920")


def many_matches(n_weeks: int = 30):
    """A small league: four teams, two games every Saturday and Sunday."""
    teams = ["A", "B", "C", "D"]
    rows, day = [], dt.date(2019, 8, 3)                     # a Saturday
    for w in range(n_weeks):
        sat, sun = day + dt.timedelta(weeks=w), day + dt.timedelta(weeks=w, days=1)
        h, a = teams[w % 4], teams[(w + 1) % 4]
        h2, a2 = teams[(w + 2) % 4], teams[(w + 3) % 4]
        rows.append(row(sat.strftime("%d/%m/%Y"), h, a, (w * 7) % 4, (w * 3) % 3))
        rows.append(row(sun.strftime("%d/%m/%Y"), h2, a2, (w * 5) % 3, (w * 2) % 4))
    return sample(rows)


# ── loader ───────────────────────────────────────────────────────────────────

def test_columns_split_pre_and_closing() -> None:
    g = fd_data.book_columns(HEADER.split(","))
    check("pre-match 1X2 books found",
          g["pre_1x2"] == ["Avg", "B365", "BFE", "BW", "Max", "PS", "VC"], str(g["pre_1x2"]))
    check("closing 1X2 books found", g["close_1x2"] == ["B365", "PS", "VC"], str(g["close_1x2"]))
    check("VC is a bookmaker, not a closing column", "VC" in g["pre_1x2"])
    check("pre-match O/U books found", g["pre_ou25"] == ["B365", "P"], str(g["pre_ou25"]))
    check("closing O/U books found", g["close_ou25"] == ["P"], str(g["close_ou25"]))


def test_prematch_holds_nothing_from_the_future() -> None:
    names = {f.name for f in dataclasses.fields(fd_data.PreMatch)}
    check("PreMatch fields are the allowed ones",
          names == {"key", "league", "season", "date", "home", "away", "odds_1x2", "odds_ou25"},
          str(names))
    pre, post = sample([row("03/08/2019", "A", "B", 2, 1)])[0]
    check("pre-match Pinnacle price is PSH, not the closing PSCH",
          pre.odds_1x2["PS"] == (2.02, 3.6, 3.9))
    check("closing Pinnacle price lives in Post", post.close_1x2["PS"] == (1.9, 3.7, 4.3))
    check("pre-match O/U Pinnacle renamed to PS", pre.odds_ou25["PS"] == (1.95, 1.95))
    check("closing O/U lives in Post", post.close_ou25["PS"] == (1.8, 2.1))
    flat = [v for d in (pre.odds_1x2, pre.odds_ou25) for t in d.values() for v in t]
    check("no closing number appears in PreMatch",
          not ({1.5, 7.0, 4.3, 1.8} & set(flat)))
    check("result and stats are in Post",
          (post.fthg, post.ftag, post.ftr, post.stats["HST"]) == (2, 1, "H", 5))


def test_parse_is_robust() -> None:
    text = (HEADER + "\n" + row("03/08/19", "A", "B", 1, 1) + "\n"
            + "E0,04/08/2019\n"                                   # ragged row
            + row("bad-date", "C", "D", 1, 0) + "\n"
            + row("05/08/2019", "C", "D", 0, 2, b365=(1.0, 3.0, 4.0)) + "\n")
    ms = fd_data.parse(text, "E0", "1920")
    check("two-digit year parsed", ms[0][0].date == dt.date(2019, 8, 3))
    check("ragged and undated rows dropped", len(ms) == 2, f"{len(ms)} rows")
    check("a price of 1.0 or less drops that book only",
          "B365" not in ms[1][0].odds_1x2 and "PS" in ms[1][0].odds_1x2)
    check("empty file gives no matches", fd_data.parse("", "E0", "1920") == [])


def test_holdout_guard() -> None:
    check("2526 is holdout for every league",
          all(fd_data.is_holdout(lg, "2526") for lg in fd_fetch.LEAGUES))
    check("2425 is holdout outside the five leagues seen in Phase 0",
          fd_data.is_holdout("E1", "2425") and fd_data.is_holdout("N1", "2425"))
    check("2425 top five are development (already seen)",
          not any(fd_data.is_holdout(lg, "2425") for lg in ("E0", "SP1", "D1", "I1", "F1")))
    check("2324 and earlier are development",
          not fd_data.is_holdout("E1", "2324") and not fd_data.is_holdout("E0", "0001"))
    for kwargs, label in (({}, "no flag"), ({"include_holdout": True}, "flag without reason")):
        try:
            fd_data.load("E0", "2526", **kwargs)
            check(f"holdout load refused ({label})", False)
        except fd_data.HoldoutError:
            check(f"holdout load refused ({label})", True)
    with open(fd_data.HOLDOUT_FILE, encoding="utf-8") as f:
        spec = json.load(f)
    seen = {s.split()[0] for s in spec["already_seen"]["league_seasons"] if s.endswith("2425")}
    check("machine rule matches the recorded prose",
          seen == set(spec["machine"]["2425"]["except"]))
    check("development loader never returns a holdout season",
          all(not fd_data.is_holdout(p.league, p.season)
              for p, _ in fd_data.load_development(leagues=("E0", "E1"),
                                                   seasons=("2324", "2425", "2526"))))


# ── walk-forward ─────────────────────────────────────────────────────────────

def test_collection_cutoff() -> None:
    fri = dt.date(2024, 8, 16)
    expect = {0: fri, 1: fri, 2: fri, 3: fri,                      # Fri Sat Sun Mon
              4: fri + dt.timedelta(4), 5: fri + dt.timedelta(4), 6: fri + dt.timedelta(4)}
    ok = all(walk.collection_cutoff(fri + dt.timedelta(d)) == c for d, c in expect.items())
    check("Fri-Mon map to Friday, Tue-Thu map to Tuesday", ok)
    d0 = dt.date(2020, 1, 1)
    spans = [(d0 + dt.timedelta(i) - walk.collection_cutoff(d0 + dt.timedelta(i))).days
             for i in range(60)]
    check("cutoff is 0 to 3 days before the match", min(spans) == 0 and max(spans) == 3)


class Spy(walk.Strategy):
    name = "spy"

    def __init__(self):
        self.seen_dates, self.violations, self.decided, self.observed = [], 0, [], []

    def decide(self, pre):
        cutoff = walk.collection_cutoff(pre.date)
        self.violations += sum(1 for d in self.seen_dates if d >= cutoff)
        self.decided.append(pre.key)
        return walk.Decision()

    def observe(self, pre, post):
        self.seen_dates.append(pre.date)
        self.observed.append(pre.key)


def test_runner_never_shows_the_future() -> None:
    ms = many_matches()
    spy, calls = Spy(), []
    walk.run(ms, [spy], lambda s, pre, post, d: calls.append(pre.key))
    check("every match decided exactly once", sorted(spy.decided) == sorted(p.key for p, _ in ms))
    check("every match observed exactly once", sorted(spy.observed) == sorted(spy.decided))
    check("scorer called once per match", len(calls) == len(ms))
    check("no result dated on or after the collection day was visible", spy.violations == 0)
    # Sunday's game must be decided before Saturday's result is observed.
    sat, sun = spy.decided[0], spy.decided[1]
    check("whole weekend decided before any of it is observed",
          spy.observed[0] == sat and spy.decided.index(sun) == 1)
    shuffled = list(reversed(ms))
    spy2 = Spy()
    walk.run(shuffled, [spy2], lambda *a: None)
    check("input order does not matter", spy2.decided == spy.decided and spy2.violations == 0)


class HomeRate(walk.Strategy):
    """Honest learner: forecasts with the home-win rate seen so far."""
    name = "home_rate"

    def __init__(self, _matches=None):
        self.n = self.h = 0

    def decide(self, pre):
        p = (self.h + 1) / (self.n + 3)
        return walk.Decision(forecasts={"1x2": (p, (1 - p) / 2, (1 - p) / 2)})

    def observe(self, pre, post):
        self.n += 1
        self.h += post.ftr == "H"


class Cheat(walk.Strategy):
    """Leaks: fits the home-win rate on the whole history it is handed."""
    name = "cheat"

    def __init__(self, matches):
        self.p = sum(post.ftr == "H" for _, post in matches) / len(matches)

    def decide(self, pre):
        return walk.Decision(forecasts={"1x2": (self.p, (1 - self.p) / 2, (1 - self.p) / 2)})


def test_leak_check() -> None:
    ms = many_matches()
    check("honest learning strategy passes", walk.leak_check(ms, HomeRate) == [])
    check("strategy fitted on the full history is caught", len(walk.leak_check(ms, Cheat)) > 0)
    check("baseline strategy passes",
          walk.leak_check(ms, lambda _m: strategies.KairosV2(min_edge=0.0)) == [])


# ── metrics ──────────────────────────────────────────────────────────────────

def test_forecast_scores() -> None:
    p = (0.5, 0.3, 0.2)
    check("log loss", abs(metrics.log_loss(p, 0) - math.log(2)) < 1e-12)
    check("Brier", abs(metrics.brier(p, 0) - (0.25 + 0.09 + 0.04)) < 1e-12)
    check("RPS", abs(metrics.rps(p, 0) - (0.25 + 0.04) / 2) < 1e-12)
    check("perfect forecast scores zero",
          metrics.brier((1, 0, 0), 0) == 0 and metrics.rps((1, 0, 0), 0) == 0)
    recs = [((0.7, 0.3), 0)] * 7 + [((0.7, 0.3), 1)] * 3
    s = metrics.forecast_summary(recs)
    b = {x["bucket"]: x for x in s["buckets"]}
    check("calibrated forecast has zero gap in both buckets",
          abs(b["0.7-0.8"]["gap"]) < 1e-9 and abs(b["0.3-0.4"]["gap"]) < 1e-9, str(s["buckets"]))
    check("ECE zero when calibrated", s["ece"] < 1e-9)
    check("bucket edge 0.3 lands in 0.3-0.4", "0.3-0.4" in b and b["0.3-0.4"]["n"] == 10)
    d = metrics.paired_diff([1.0, 2.0, 3.0], [0.5, 1.5, 2.5])
    check("paired difference mean and zero spread", abs(d["mean"] - 0.5) < 1e-12 and d["se"] < 1e-12)


def test_bet_summary() -> None:
    bets = ([{"cluster": i, "stake": 1.0, "profit": 1.0, "clv": 0.02, "odds": 2.0} for i in range(50)]
            + [{"cluster": 100 + i, "stake": 1.0, "profit": -1.0, "clv": -0.01, "odds": 2.0}
               for i in range(50)])
    s = metrics.bet_summary(bets, n_boot=500)
    check("return per bet", abs(s["roi"]) < 1e-12 and s["bets"] == 100 and s["wins"] == 50)
    check("mean CLV", abs(s["clv"] - 0.005) < 1e-12)
    check("interval brackets the point estimate",
          s["roi_ci"][0] < s["roi"] < s["roi_ci"][1] and s["clv_ci"][0] < s["clv"] < s["clv_ci"][1])
    check("interval width is plausible for 100 even-money bets",
          0.25 < s["roi_ci"][1] - s["roi_ci"][0] < 0.55, str(s["roi_ci"]))
    check("same seed, same interval", metrics.bet_summary(bets, n_boot=500)["roi_ci"] == s["roi_ci"])
    same = [{"cluster": i, "stake": 1.0, "profit": 0.1, "clv": None, "odds": 1.1} for i in range(20)]
    s2 = metrics.bet_summary(same, n_boot=200)
    check("identical bets give a zero-width interval",
          abs(s2["roi_ci"][0] - 0.1) < 1e-9 and abs(s2["roi_ci"][1] - 0.1) < 1e-9)
    check("missing closing prices are counted, not guessed", s2["clv"] is None and s2["clv_n"] == 0)
    two = [{"cluster": "m", "stake": 1.0, "profit": 2.0, "clv": 0.0, "odds": 3.0},
           {"cluster": "m", "stake": 1.0, "profit": -1.0, "clv": 0.0, "odds": 3.0}]
    check("bets on one match form one cluster", metrics.bet_summary(two, n_boot=200)["clusters"] == 1)
    check("no bets gives None", metrics.bet_summary([]) is None)


# ── baseline strategy and scorer ─────────────────────────────────────────────

def test_baseline_matches_engine() -> None:
    # Bet365 pays 2.30 on a home side Pinnacle prices at 2.02: clear value on home only.
    pre, post = sample([row("03/08/2019", "A", "B", 2, 1, b365=(2.30, 3.4, 3.5),
                            ou=(2.2, 1.7), p_ou=(1.95, 1.95))])[0]
    d = strategies.KairosV2().decide(pre)
    fair = edge.sharp_fair({"pinnacle": {"home": 2.02, "draw": 3.6, "away": 3.9}})["fair_prob"]
    want = [r["selection"] for r in edge.value_vs_sharp(
        {"home": 2.30, "draw": 3.4, "away": 3.5}, fair) if r["value"]]
    got = [b for b in d.bets if b.market == "1x2"]
    check("1X2 bets equal edge.value_vs_sharp", want == ["home"] and len(got) == 1
          and got[0].selection == 0 and got[0].odds == 2.30 and got[0].book == "B365")
    check("forecast is the engine's sharp fair probability",
          d.forecasts["1x2"] == (fair["home"], fair["draw"], fair["away"]))
    ou = [b for b in d.bets if b.market == "ou25"]
    check("O/U value found on the over only", len(ou) == 1 and ou[0].selection == 0
          and ou[0].odds == 2.2)
    check("claimed EV is price x fair - 1",
          abs(got[0].claimed_ev - (2.30 * fair["home"] - 1)) < 1e-12)

    # Closing price screams value, pre-match price does not: no bet (no look-ahead).
    pre2, _ = sample([row("03/08/2019", "A", "B", 2, 1, b365=(2.0, 3.5, 3.8),
                          ps=(2.02, 3.6, 3.9), psc=(1.5, 4.5, 7.0))])[0]
    check("closing price cannot trigger a bet",
          [b for b in strategies.KairosV2().decide(pre2).bets if b.market == "1x2"] == [])

    # No Pinnacle price: no forecast and no bet.
    text = "Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A\nE0,03/08/2019,A,B,1,0,H,2.5,3.2,2.9\n"
    pre3, _ = fd_data.parse(text, "E0", "0506")[0]
    d3 = strategies.KairosV2().decide(pre3)
    check("no Pinnacle price means no forecast and no bet", d3.forecasts == {} and d3.bets == [])


def test_best_price_uses_named_books_only() -> None:
    # Max and the exchange both show 2.10 home; the best named book (B365) shows 2.00.
    pre, _ = sample([row("03/08/2019", "A", "B", 2, 1)])[0]
    s = strategies.KairosV2(soft="BEST", min_edge=-1.0, markets=("1x2",))
    bets = s.decide(pre).bets
    check("best price excludes Pinnacle, exchange, Max and Avg",
          {b.book for b in bets} <= {"B365", "BW", "VC"} and bets
          and max(b.odds for b in bets if b.selection == 0) == 2.0,
          str([(b.book, b.odds) for b in bets]))
    check("soft_books filter", set(strategies.soft_books(pre.odds_1x2)) == {"B365", "BW", "VC"})


def test_scorer() -> None:
    ms = sample([row("03/08/2019", "A", "B", 2, 1, b365=(2.30, 3.4, 3.5)),
                 row("04/08/2019", "C", "D", 0, 0, b365=(2.30, 3.4, 3.5))])
    sc = score.Scorer()
    strat = strategies.KairosV2(markets=("1x2",))
    walk.run(ms, [strat], sc)
    bets = sc.bets[strat.name]
    fc = market.devig_power([1.9, 3.7, 4.3])
    check("winning bet pays odds - 1, losing bet loses the stake",
          [round(b["profit"], 6) for b in bets] == [1.3, -1.0])
    check("CLV is price x fair closing probability - 1",
          all(abs(b["clv"] - (2.30 * fc[0] - 1)) < 1e-12 for b in bets))
    prop = market.devig_proportional([1.9, 3.7, 4.3])
    check("proportional CLV recorded beside it",
          all(abs(b["clv_prop"] - (2.30 * prop[0] - 1)) < 1e-12 for b in bets))
    t = sc.bet_table(strat.name, n_boot=200)["all"]
    check("bet table totals", t["bets"] == 2 and abs(t["profit"] - 0.3) < 1e-9
          and abs(t["roi"] - 0.15) < 1e-9)
    ref = sc.forecasts[score.CLOSE_REF]["1x2"]
    check("closing reference scored once per match", len(ref) == 2)
    check("over/under outcome index", score.outcome_index("ou25", ms[0][1]) == 0
          and score.outcome_index("ou25", ms[1][1]) == 1)
    f = sc.forecast_table(strat.name, "1x2")["all"]
    check("forecast table counts matches", f["n"] == 2 and f["log_loss"] > 0)
    keys = sc.common_keys([strat.name, score.CLOSE_REF], "1x2")
    pd = sc.paired_log_loss(strat.name, score.CLOSE_REF, "1x2", keys)
    check("paired comparison runs on the common matches", pd["n"] == 2)

    # A match with no Pinnacle closing price: bet settles, CLV is None.
    text = ("Div,Date,HomeTeam,AwayTeam,FTHG,FTAG,FTR,B365H,B365D,B365A,PSH,PSD,PSA\n"
            "E0,03/08/2019,A,B,1,0,H,2.30,3.4,3.5,2.02,3.6,3.9\n")
    sc2 = score.Scorer()
    walk.run(fd_data.parse(text, "E0", "1920"), [strat], sc2)
    check("no closing price gives CLV None", sc2.bets[strat.name][0]["clv"] is None)


def test_season_codes() -> None:
    check("season code", fd_fetch.season_code(2024) == "2425" and fd_fetch.season_code(1999) == "9900")
    check("season start year", fd_fetch.season_start_year("2425") == 2024
          and fd_fetch.season_start_year("9900") == 1999)
    check("26 seasons listed", len(fd_fetch.SEASONS) == 26 and fd_fetch.SEASONS[0] == "0001"
          and fd_fetch.SEASONS[-1] == "2526")


# ── gap census ───────────────────────────────────────────────────────────────

def _event(eid="ev1", pin=(2.02, 3.6, 3.9), kickoff="2026-10-10T15:00:00Z", with_pin=True):
    def bk(key, o):
        return {"key": key, "markets": [{"key": "h2h", "outcomes": [
            {"name": "Home FC", "price": o[0]}, {"name": "Away FC", "price": o[2]},
            {"name": "Draw", "price": o[1]}]}]}
    books = [bk("williamhill", (1.95, 3.4, 3.7))] + ([bk("pinnacle", pin)] if with_pin else [])
    return {"id": eid, "home_team": "Home FC", "away_team": "Away FC",
            "commence_time": kickoff, "bookmakers": books}


def test_census() -> None:
    path = os.path.join(tempfile.mkdtemp(), "census.jsonl")
    t_seen = dt.datetime(2026, 10, 8, 12, 0, tzinfo=dt.timezone.utc)
    fair = edge.sharp_fair({"pinnacle": {"home": 2.02, "draw": 3.6, "away": 3.9}})["fair_prob"]
    w = census.log_prices(_event(), {"home": 2.30, "draw": 3.3}, "soccer_epl",
                          staked=("home",), now=t_seen, path=path)
    check("one line per SportyBet price", len(w) == 2)
    check("EV is price x Pinnacle fair - 1", abs(w[0]["ev"] - (2.30 * fair["home"] - 1)) < 1e-12)
    check("staked flag recorded", w[0]["staked"] and not w[1]["staked"])
    check("logging the same price twice writes nothing",
          census.log_prices(_event(), {"home": 2.30}, "soccer_epl", now=t_seen, path=path) == [])
    check("no Pinnacle price, nothing logged",
          census.log_prices(_event("ev2", with_pin=False), {"home": 2.3}, "soccer_epl",
                            now=t_seen, path=path) == [])
    check("close for an event with no logged price is ignored",
          census.log_close(_event("ev9"), now=t_seen, path=path) is None)
    late = dt.datetime(2026, 10, 10, 15, 5, tzinfo=dt.timezone.utc)
    check("a fetch after kickoff is not a closing price",
          census.log_close(_event(pin=(1.8, 3.8, 4.6)), now=late, path=path) is None)
    early = dt.datetime(2026, 10, 9, 15, 0, tzinfo=dt.timezone.utc)       # 24h out
    census.log_close(_event(pin=(1.95, 3.7, 4.1)), now=early, path=path)
    s0 = census.summary(path)
    check("a fetch a day before kickoff does not count as the close", s0["clv_all"] is None)
    near = dt.datetime(2026, 10, 10, 14, 30, tzinfo=dt.timezone.utc)      # 30 min out
    census.log_close(_event(pin=(1.80, 3.8, 4.6)), now=near, path=path)
    s = census.summary(path)
    fc = edge.sharp_fair({"pinnacle": {"home": 1.80, "draw": 3.8, "away": 4.6}})["fair_prob"]
    want = ((2.30 * fc["home"] - 1) + (3.3 * fc["draw"] - 1)) / 2
    check("CLV uses the fetch nearest kickoff", s["clv_all"]["n"] == 2
          and abs(s["clv_all"]["mean"] - want) < 1e-12)
    check("gap shares", s["prices"] == 2 and s["events"] == 1 and s["staked"] == 1
          and s["share_ev_above_2pct"] == 0.5)
    check("kill rule waits for enough prices", s["kill_rule"] == "not enough prices")
    check("empty census summarises cleanly",
          census.summary(os.path.join(tempfile.mkdtemp(), "none.jsonl"))["prices"] == 0)


def run_all() -> None:
    for fn in (test_columns_split_pre_and_closing, test_prematch_holds_nothing_from_the_future,
               test_parse_is_robust, test_holdout_guard, test_collection_cutoff,
               test_runner_never_shows_the_future, test_leak_check, test_forecast_scores,
               test_bet_summary, test_baseline_matches_engine,
               test_best_price_uses_named_books_only, test_scorer, test_season_codes,
               test_census):
        fn()
    print("\n" + ("ALL HARNESS TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
