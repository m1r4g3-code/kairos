"""
KAIROS paper trading — data feeds.

  OddsClient   The Odds API. The events list is free; odds cost
               regions x markets credits per call and go through the budget.
  results()    This season's Football-Data file for one league (free, cached,
               at most one download per league per `max_age_h` hours).

Network access is injected (`http`) so tests run offline.

Pure stdlib.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
import time
import urllib.parse
import urllib.request

USER_AGENT = "Kairos-paper (personal, non-commercial)"
FD_BASE = "https://www.football-data.co.uk/mmz4281"


def default_http(url: str, timeout: float = 30.0) -> tuple[bytes, dict]:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read(), {k.lower(): v for k, v in resp.headers.items()}


class OddsClient:
    def __init__(self, api_key: str, base: str, budget, http=default_http):
        self.key, self.base, self.budget, self.http = api_key, base, budget, http

    def events(self, sport: str) -> list[dict]:
        """Upcoming events for a competition. Free: does not count against the quota."""
        qs = urllib.parse.urlencode({"apiKey": self.key, "dateFormat": "iso"})
        body, _ = self.http(f"{self.base}/sports/{sport}/events?{qs}")
        return json.loads(body)

    def odds(self, sport: str, regions: str, markets: str, now: dt.datetime,
             spare: int = 0) -> list[dict] | None:
        """Odds for every event in a competition, or None if the budget refuses."""
        cost = len(regions.split(",")) * len(markets.split(","))
        if not self.budget.allow(cost, now, spare=spare):
            return None
        qs = urllib.parse.urlencode({"apiKey": self.key, "regions": regions, "markets": markets,
                                     "oddsFormat": "decimal", "dateFormat": "iso"})
        body, headers = self.http(f"{self.base}/sports/{sport}/odds/?{qs}")
        remaining = headers.get("x-requests-remaining")
        used_now = headers.get("x-requests-last")
        self.budget.record(int(used_now) if used_now and used_now.isdigit() else cost, now,
                           int(float(remaining)) if remaining else None)
        return json.loads(body)


def season_code(day: dt.date) -> str:
    """Football season containing `day` (July starts a new one): 2026-10-03 -> '2627'."""
    y = day.year if day.month >= 7 else day.year - 1
    return f"{y % 100:02d}{(y + 1) % 100:02d}"


def parse_results(text: str) -> list[dict]:
    rows = []
    for r in csv.DictReader(io.StringIO(text.lstrip("﻿"))):
        try:
            date = dt.datetime.strptime(r["Date"].strip(),
                                        "%d/%m/%Y" if len(r["Date"].strip()) == 10 else "%d/%m/%y").date()
            rows.append({"date": date, "home": r["HomeTeam"].strip(), "away": r["AwayTeam"].strip(),
                         "fthg": int(r["FTHG"]), "ftag": int(r["FTAG"])})
        except (KeyError, ValueError, TypeError, AttributeError):
            continue
    return rows


def results(league: str, day: dt.date, cache_dir: str, max_age_h: float = 12.0,
            http=default_http, now_ts: float | None = None) -> list[dict]:
    """This season's results for one league, from cache if fresh enough."""
    season = season_code(day)
    path = os.path.join(cache_dir, f"results_{league}_{season}.csv")
    now_ts = time.time() if now_ts is None else now_ts
    fresh = os.path.exists(path) and now_ts - os.path.getmtime(path) < max_age_h * 3600
    if not fresh:
        body, _ = http(f"{FD_BASE}/{season}/{league}.csv")
        if body.lstrip(b"\xef\xbb\xbf").startswith(b"Div"):
            os.makedirs(cache_dir, exist_ok=True)
            tmp = path + ".part"
            with open(tmp, "wb") as f:
                f.write(body)
            os.replace(tmp, path)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8", errors="replace") as f:
        return parse_results(f.read())
