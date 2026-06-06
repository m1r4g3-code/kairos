"""
KAIROS source — The Odds API adapter (https://the-odds-api.com).

Fetches head-to-head (1X2) odds across many bookmakers — crucially including the
sharp book Pinnacle — so edge.py can compare SportyBet to the sharp price.

Free tier = 500 requests/month, so every response is CACHED to fixtures/ and the
parser works offline on that cache (tests + dev never burn the quota or need a key).

Pure stdlib (urllib + json).
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

CACHE = config.CACHE_DIR


def fetch_raw(sport_key: str = "soccer_epl", regions: str = "uk,eu",
              markets: str = "h2h", api_key: str | None = None,
              cache: bool = True) -> list[dict]:
    """
    GET odds for a sport from The Odds API. Returns the raw events list.
    Caches to fixtures/odds_<sport>.json. Raises if no key is configured.
    """
    key = api_key or config.ODDS_API_KEY
    if not key:
        raise RuntimeError(
            "No ODDS_API_KEY set. Add it to .env (see .env.example), or load a "
            "cached fixture with load_fixture()."
        )
    qs = urllib.parse.urlencode({
        "apiKey": key, "regions": regions, "markets": markets,
        "oddsFormat": "decimal", "dateFormat": "iso",
    })
    url = f"{config.ODDS_API_BASE}/sports/{sport_key}/odds/?{qs}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if cache:
        os.makedirs(CACHE, exist_ok=True)
        path = os.path.join(CACHE, f"odds_{sport_key}.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump({"_fetched": time.time(), "events": data}, f)
    return data


def load_fixture(name: str) -> list[dict]:
    """Load a cached/sample events list from fixtures/<name>."""
    path = os.path.join(CACHE, name)
    with open(path, "r", encoding="utf-8") as f:
        blob = json.load(f)
    return blob["events"] if isinstance(blob, dict) and "events" in blob else blob


def parse_event(event: dict) -> dict:
    """
    Flatten one Odds API event into:
      {"home_team","away_team","commence","books": {bk: {home/draw/away: odds}}}
    Maps each h2h outcome name to home/away via the event's team names; everything
    else (e.g. "Draw") becomes the draw price.
    """
    home, away = event.get("home_team"), event.get("away_team")
    books: dict[str, dict[str, float]] = {}
    for bk in event.get("bookmakers", []):
        for mkt in bk.get("markets", []):
            if mkt.get("key") != "h2h":
                continue
            sel: dict[str, float] = {}
            for out in mkt.get("outcomes", []):
                name, price = out.get("name"), out.get("price")
                if name == home:
                    sel["home"] = price
                elif name == away:
                    sel["away"] = price
                else:
                    sel["draw"] = price
            if sel:
                books[bk["key"]] = sel
    return {"home_team": home, "away_team": away,
            "commence": event.get("commence_time"), "books": books}


def find_event(events: list[dict], home_hint: str, away_hint: str) -> dict | None:
    """Loosely match a screenshot fixture to an Odds API event by team-name substring."""
    def norm(s: str) -> str:
        return "".join(c for c in s.lower() if c.isalnum())
    h, a = norm(home_hint), norm(away_hint)
    for ev in events:
        eh, ea = norm(ev.get("home_team", "")), norm(ev.get("away_team", ""))
        if (h in eh or eh in h) and (a in ea or ea in a):
            return ev
    return None


if __name__ == "__main__":
    # Offline demo against the bundled sample.
    evs = load_fixture("odds_sample.json")
    for ev in evs:
        p = parse_event(ev)
        print(p["home_team"], "vs", p["away_team"], "->", list(p["books"].keys()))
