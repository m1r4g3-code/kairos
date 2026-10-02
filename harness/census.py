"""
KAIROS harness — SportyBet gap census (research proposal F1).

The question no backtest can answer: how often does SportyBet pay more than
Pinnacle's fair price, and do those prices beat the close? This module logs
every SportyBet price the owner sends, bet or not, next to Pinnacle's price at
that moment, and later next to Pinnacle's price near kickoff.

File: ledger/census.jsonl, append-only, two kinds of line.
  price  one SportyBet price for one selection, with Pinnacle's odds and fair
         probability at the time it was seen
  close  Pinnacle's odds for an event fetched shortly before kickoff

Only Pinnacle counts as the reference. An event without a Pinnacle price is not
logged: a gap measured against some other soft book says nothing.

Logging the same price twice writes one line. Recommend-only: this records
prices, it places nothing.

CLI:  python harness/census.py summary

Pure stdlib.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import sys

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(_ROOT, "engine"))
import edge                       # noqa: E402
from sources import odds_api      # noqa: E402

import metrics                    # noqa: E402

CENSUS = os.path.join(_ROOT, "ledger", "census.jsonl")
REFERENCE = "pinnacle"
CLOSE_WINDOW_MIN = 180            # a "closing" price is one fetched this close to kickoff
KILL_AFTER = 1000                 # prices needed before the kill rule is read
KILL_SHARE = 0.01                 # share of prices beating fair by 2%+ below which it fails


def _now() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def _parse_time(text: str) -> dt.datetime:
    return dt.datetime.fromisoformat(text.replace("Z", "+00:00"))


def _read(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    out = []
    with open(path, encoding="utf-8") as f:
        for line in f:
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def _append(path: str, rec: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=True, sort_keys=True) + "\n")
        f.flush()
        os.fsync(f.fileno())


def _reference(event: dict) -> tuple[dict, dict] | None:
    """(Pinnacle odds, fair probabilities) for an Odds API event, or None."""
    books = odds_api.parse_event(event)["books"]
    if REFERENCE not in books:
        return None
    sf = edge.sharp_fair({REFERENCE: books[REFERENCE]})
    return books[REFERENCE], sf["fair_prob"]


def log_prices(event: dict, sb_prices: dict, sport_key: str, staked: tuple = (),
               now: dt.datetime | None = None, path: str = CENSUS) -> list[dict]:
    """
    Log SportyBet's price for each selection of one event (h2h market).

    event      a raw Odds API event (as returned by odds_api.fetch_raw / find_event)
    sb_prices  {"home": 2.10, "draw": 3.40, "away": 3.60}; any subset
    staked     selections the owner actually bet, e.g. ("home",)
    Returns the lines written (empty if Pinnacle has no price or all were duplicates).
    """
    ref = _reference(event)
    if ref is None:
        return []
    odds, fair = ref
    now = now or _now()
    seen = {(r["event_id"], r["selection"], r["sb_odds"]) for r in _read(path)
            if r.get("kind") == "price"}
    written = []
    for sel, price in sb_prices.items():
        if sel not in fair or (event["id"], sel, price) in seen:
            continue
        rec = {"kind": "price", "event_id": event["id"], "sport_key": sport_key,
               "event": f"{event.get('home_team')} v {event.get('away_team')}",
               "commence": event.get("commence_time"), "market": "h2h", "selection": sel,
               "sb_odds": price, "seen_utc": now.isoformat(timespec="seconds"),
               "ref_odds": odds, "ref_fair": fair[sel], "ev": price * fair[sel] - 1.0,
               "staked": sel in staked}
        _append(path, rec)
        written.append(rec)
    return written


def log_close(event: dict, now: dt.datetime | None = None, path: str = CENSUS) -> dict | None:
    """
    Record Pinnacle's current price for an event that has census prices. Call it
    with a fetch made shortly before kickoff. Fetches made after kickoff, or for
    events with no logged price, write nothing.
    """
    now = now or _now()
    recs = _read(path)
    if not any(r.get("kind") == "price" and r["event_id"] == event["id"] for r in recs):
        return None
    minutes = (_parse_time(event["commence_time"]) - now).total_seconds() / 60.0
    ref = _reference(event)
    if ref is None or minutes < 0:
        return None
    odds, fair = ref
    rec = {"kind": "close", "event_id": event["id"], "market": "h2h",
           "seen_utc": now.isoformat(timespec="seconds"),
           "minutes_to_kickoff": round(minutes, 1), "ref_odds": odds, "ref_fair": fair}
    _append(path, rec)
    return rec


def summary(path: str = CENSUS, close_window_min: float = CLOSE_WINDOW_MIN) -> dict:
    """Gap share, CLV with a match-clustered interval, and the kill-rule reading."""
    recs = _read(path)
    prices = [r for r in recs if r.get("kind") == "price"]
    closes: dict = {}
    for r in recs:                      # the latest pre-kickoff fetch inside the window wins
        if r.get("kind") == "close" and r["minutes_to_kickoff"] <= close_window_min:
            cur = closes.get(r["event_id"])
            if cur is None or r["minutes_to_kickoff"] < cur["minutes_to_kickoff"]:
                closes[r["event_id"]] = r
    n = len(prices)
    out = {"prices": n, "events": len({p["event_id"] for p in prices}),
           "staked": sum(1 for p in prices if p["staked"]),
           "share_ev_above_0": None, "share_ev_above_2pct": None, "share_ev_above_3pct": None,
           "clv_all": None, "clv_ev_above_2pct": None, "kill_rule": "not enough prices"}
    if not n:
        return out
    for label, thr in (("share_ev_above_0", 0.0), ("share_ev_above_2pct", 0.02),
                       ("share_ev_above_3pct", 0.03)):
        out[label] = sum(1 for p in prices if p["ev"] > thr) / n

    def clv_of(rows):
        bets = []
        for p in rows:
            c = closes.get(p["event_id"])
            if c and p["selection"] in c["ref_fair"]:
                bets.append({"cluster": p["event_id"], "stake": 1.0, "profit": 0.0,
                             "odds": p["sb_odds"],
                             "clv": p["sb_odds"] * c["ref_fair"][p["selection"]] - 1.0})
        s = metrics.bet_summary(bets) if bets else None
        return None if not s else {"n": s["clv_n"], "mean": s["clv"], "ci": s["clv_ci"]}

    out["clv_all"] = clv_of(prices)
    out["clv_ev_above_2pct"] = clv_of([p for p in prices if p["ev"] > 0.02])
    if n >= KILL_AFTER:
        c = out["clv_ev_above_2pct"]
        clv_unproven = c is None or c["ci"][0] <= 0.0
        fails = out["share_ev_above_2pct"] < KILL_SHARE and clv_unproven
        out["kill_rule"] = "FAILS: drop the single-book strategy" if fails else "passes so far"
    return out


if __name__ == "__main__":
    print(json.dumps(summary(), indent=2))
