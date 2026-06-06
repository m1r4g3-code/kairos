"""
KAIROS source — Club Elo adapter (http://clubelo.com, free, KEYLESS).

Club Elo publishes daily Elo ratings for thousands of clubs as plain CSV at
http://api.clubelo.com/<ClubName>. We take the latest rating per club and hand it
to the existing engine via an `elo` spec -> run.build_prediction -> elo_to_lambdas.

This replaces my hand-guessed strength with a real, continuously-updated number.
Pure stdlib (urllib + csv).
"""

from __future__ import annotations

import csv
import io
import os
import sys
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

BASE = "http://api.clubelo.com"


def parse_elo_csv(text: str) -> float | None:
    """Return the most recent Elo from a Club Elo CSV (last data row's Elo)."""
    rows = list(csv.DictReader(io.StringIO(text)))
    if not rows:
        return None
    for row in reversed(rows):                 # latest period is last
        val = row.get("Elo")
        if val:
            try:
                return round(float(val), 2)
            except ValueError:
                continue
    return None


def get_elo(club: str, cache: bool = True) -> float | None:
    """Fetch a club's current Elo. Club names use Club Elo's spelling (e.g. 'Man City')."""
    url = f"{BASE}/{urllib.parse.quote(club)}"
    with urllib.request.urlopen(url, timeout=20) as resp:
        text = resp.read().decode("utf-8")
    if cache:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(os.path.join(config.CACHE_DIR, f"elo_{club}.csv"), "w",
                  encoding="utf-8") as f:
            f.write(text)
    return parse_elo_csv(text)


def build_elo_spec(home_club: str, away_club: str, match: str = "",
                   total_goals: float = 2.7) -> dict | None:
    """
    Build a run.build_prediction `elo` spec from two clubs' live Elo ratings.
    Returns None if either rating can't be fetched (caller falls back to judgment).
    """
    eh, ea = get_elo(home_club), get_elo(away_club)
    if eh is None or ea is None:
        return None
    return {
        "match": match or f"{home_club} vs {away_club}",
        "elo": {"home": eh, "away": ea, "total_goals": total_goals},
        "source": "clubelo",
    }


if __name__ == "__main__":
    sample = ("Rank,Club,Country,Level,Elo,From,To\n"
              "5,Arsenal,ENG,1,1955.0,2026-05-26,2026-06-01\n"
              "5,Arsenal,ENG,1,1962.3,2026-06-02,2026-06-08\n")
    print("Latest Elo from sample CSV:", parse_elo_csv(sample))
