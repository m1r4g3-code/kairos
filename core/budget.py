"""
KAIROS core — a monthly budget for a metered API, kept in a file.

The free Odds API tier gives 500 credits a month and the owner's own sessions
use the same key. The budget therefore trusts the provider's own count when it
has one (the remaining-credits header of the last response) and its own
running total otherwise, and keeps a reserve the loop may never spend.

    b = Budget(path, monthly_cap=440, reserve=60)
    if b.allow(cost): ... call ...; b.record(cost, remaining_header)

Pure stdlib. Nothing here knows about football.
"""

from __future__ import annotations

import datetime as dt

from core import store


def month_key(now: dt.datetime) -> str:
    return now.strftime("%Y-%m")


class Budget:
    def __init__(self, path: str, monthly_cap: int, reserve: int = 0):
        self.path, self.cap, self.reserve = path, monthly_cap, reserve

    def _state(self, now: dt.datetime) -> dict:
        s = store.load_json(self.path, {}) or {}
        if s.get("month") != month_key(now):
            s = {"month": month_key(now), "spent": 0, "calls": 0, "remaining": None,
                 "refused": 0}
        return s

    def status(self, now: dt.datetime) -> dict:
        s = self._state(now)
        return {**s, "cap": self.cap, "reserve": self.reserve,
                "left_under_cap": self.cap - s["spent"]}

    def allow(self, cost: int, now: dt.datetime, spare: int = 0) -> bool:
        """
        True if `cost` credits may be spent now while still leaving `spare`
        credits (e.g. for closing prices already owed) and the reserve.
        A refusal is counted so the health log can show it.
        """
        s = self._state(now)
        ok = s["spent"] + cost + spare <= self.cap
        if s["remaining"] is not None:
            ok = ok and s["remaining"] - cost - spare >= self.reserve
        if not ok:
            s["refused"] += 1
            store.save_json(self.path, s)
        return ok

    def record(self, cost: int, now: dt.datetime, remaining: int | None = None) -> None:
        s = self._state(now)
        s["spent"] += cost
        s["calls"] += 1
        if remaining is not None:
            s["remaining"] = remaining
        store.save_json(self.path, s)
