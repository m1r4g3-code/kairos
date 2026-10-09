"""
KAIROS paper trading — Cloudbet price reader. READ-ONLY.

This module can do exactly one thing: GET pre-match 1X2 prices from Cloudbet's
Feed API. It contains no bet placement, no account call and no write of any
kind, and `_get` refuses any URL outside the odds feed. The owner's key is a
Trading key (it could place bets); on 2026-10-09 the owner approved storing it
for reading prices only. It is read from Windows Credential Manager
(core.secret, name "KairosCloudbet") and is never written to a file, a log or
a prompt.

    client = Client.from_secret()           # None if no key is stored
    client.match_odds("soccer-england-championship")
        -> [{"home", "away", "kickoff", "prices": {home, draw, away},
             "max_stake": {home, draw, away}}]

Research C1 in research/hypotheses.md. Pure stdlib.
"""

from __future__ import annotations

import json
import urllib.request

FEED = "https://sports-api.cloudbet.com/pub/v2/odds/"
MARKET = "soccer.match_odds"
SECRET_NAME = "KairosCloudbet"
USER_AGENT = "Kairos-paper (personal, read-only)"


def default_get(url: str, headers: dict, timeout: float = 30.0) -> bytes:
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def parse(body: bytes | str) -> list[dict]:
    """Pre-match matches with all three full-time 1X2 prices open."""
    out = []
    for ev in json.loads(body).get("events", []):
        if ev.get("type") != "EVENT_TYPE_EVENT" or ev.get("status") != "TRADING":
            continue
        home, away = (ev.get("home") or {}).get("name"), (ev.get("away") or {}).get("name")
        sub = ((ev.get("markets") or {}).get(MARKET) or {}).get("submarkets", {}).get("period=ft") or {}
        prices, stakes = {}, {}
        for s in sub.get("selections", []):
            if (s.get("status") == "SELECTION_ENABLED" and s.get("side", "BACK") == "BACK"
                    and isinstance(s.get("price"), (int, float)) and s["price"] > 1.0):
                prices[s.get("outcome")] = float(s["price"])
                stakes[s.get("outcome")] = s.get("maxStake")
        if home and away and ev.get("cutoffTime") and set(prices) == {"home", "draw", "away"}:
            out.append({"home": home, "away": away, "kickoff": ev["cutoffTime"],
                        "prices": prices, "max_stake": stakes})
    return out


class Client:
    def __init__(self, key: str, get=default_get):
        self._key, self._getter = key, get

    @classmethod
    def from_secret(cls, get=default_get):
        from core import secret
        key = secret.get(SECRET_NAME)
        return cls(key, get) if key else None

    def _get(self, path: str) -> bytes:
        url = FEED + path.lstrip("/")
        if not url.startswith(FEED) or ".." in url:
            raise ValueError("Cloudbet reader: only the odds feed may be read")
        return self._getter(url, {"X-API-Key": self._key, "accept": "application/json",
                                  "User-Agent": USER_AGENT})

    def match_odds(self, competition: str) -> list[dict]:
        return parse(self._get(f"competitions/{competition}?markets={MARKET}"))
