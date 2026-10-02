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
import unicodedata
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
    Raises if no key is configured.

    Cache file: fixtures/odds_<sport>.json for h2h, and
    fixtures/odds_<sport>_<markets>.json for anything else, so fetching totals
    no longer overwrites the h2h cache.
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
        suffix = "" if markets == "h2h" else "_" + markets.replace(",", "+")
        path = os.path.join(CACHE, f"odds_{sport_key}{suffix}.json")
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


def parse_lines(event: dict, market: str = "totals") -> dict[str, dict]:
    """
    Flatten the totals or spreads market of one event:

      totals   {book: {"line": 2.5,  "over": 1.95, "under": 1.87}}
      spreads  {book: {"line": -0.5, "home": 1.93, "away": 1.89}}   line = home handicap

    A book that quotes several lines keeps the first one listed. Books with an
    incomplete pair are left out.
    """
    if market not in ("totals", "spreads"):
        raise ValueError("market must be 'totals' or 'spreads'")
    home, away = event.get("home_team"), event.get("away_team")
    out: dict[str, dict] = {}
    for bk in event.get("bookmakers", []):
        for mkt in bk.get("markets", []):
            if mkt.get("key") != market:
                continue
            row: dict = {}
            for o in mkt.get("outcomes", []):
                name, price, point = o.get("name"), o.get("price"), o.get("point")
                if market == "totals" and name in ("Over", "Under"):
                    row.setdefault(name.lower(), price)
                    row.setdefault("line", point)
                elif market == "spreads" and name in (home, away):
                    row.setdefault("home" if name == home else "away", price)
                    if name == home:
                        row.setdefault("line", point)
            need = ("over", "under") if market == "totals" else ("home", "away")
            if all(k in row for k in need) and row.get("line") is not None:
                out.setdefault(bk["key"], row)
    return out


def find_event(events: list[dict], home_hint: str, away_hint: str) -> dict | None:
    """
    Match a screenshot fixture to an Odds API event by team-name substring.

    Accents are folded, so "Malaga" matches "Málaga". If several events match, an
    exact name match wins; if that does not settle it, a ValueError lists the
    candidates rather than returning the first one (which may be the wrong game).
    """
    def norm(s: str) -> str:
        s = unicodedata.normalize("NFKD", s)
        return "".join(c for c in s.lower() if c.isalnum() and not unicodedata.combining(c))
    h, a = norm(home_hint), norm(away_hint)
    hits = []
    for ev in events:
        eh, ea = norm(ev.get("home_team", "")), norm(ev.get("away_team", ""))
        if (h in eh or eh in h) and (a in ea or ea in a):
            hits.append((ev, eh == h and ea == a))
    if not hits:
        return None
    exact = [ev for ev, is_exact in hits if is_exact]
    if len(exact) == 1:
        return exact[0]
    if len(hits) == 1:
        return hits[0][0]
    names = [f"{ev.get('home_team')} v {ev.get('away_team')}" for ev, _ in hits]
    raise ValueError(f"hints match {len(hits)} events, be more specific: {names}")


if __name__ == "__main__":
    # Offline demo against the bundled sample.
    evs = load_fixture("odds_sample.json")
    for ev in evs:
        p = parse_event(ev)
        print(p["home_team"], "vs", p["away_team"], "->", list(p["books"].keys()))
