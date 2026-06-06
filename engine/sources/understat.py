"""
KAIROS source — Understat adapter (https://understat.com, free, KEYLESS).

Understat publishes match-level xG for the big-5 European leagues + RPL. Each
league page embeds the data as `var teamsData = JSON.parse('\\x7B...')`. We
decode that, compute each team's xG-for / xG-against per game, normalise to the
league average, and hand the engine a `strengths` spec ->
run.build_prediction -> strengths_to_lambdas.

This grounds the attack/defence numbers in real expected-goals data instead of my
guess. Big-5 leagues only (that's Understat's coverage — and the leagues worth betting).
Pure stdlib (urllib + re + json).
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

BASE = "https://understat.com/league"
LEAGUES = {"EPL", "La_liga", "Bundesliga", "Serie_A", "Ligue_1", "RFPL"}
_RE = re.compile(r"teamsData\s*=\s*JSON\.parse\('([^']+)'\)")


def parse_teams_data(html: str) -> dict:
    """Extract and decode the `teamsData` JSON blob from an Understat league page."""
    m = _RE.search(html)
    if not m:
        return {}
    decoded = m.group(1).encode("utf-8").decode("unicode_escape")
    return json.loads(decoded)


def team_strengths(teams_data: dict) -> dict:
    """
    From Understat teamsData -> {team_title: {"att": x, "def": y, "games": n}}.
      att = (team xG per game) / (league avg xG per game)        >1 = strong attack
      def = (team xGA per game) / (league avg xGA per game)       >1 = leaky defence
    (Defined so they plug straight into elo.strengths_to_lambdas.)
    """
    rows = {}
    tot_xg = tot_games = 0.0
    for t in teams_data.values():
        hist = t.get("history", [])
        if not hist:
            continue
        xg = sum(float(h.get("xG", 0)) for h in hist)
        xga = sum(float(h.get("xGA", 0)) for h in hist)
        n = len(hist)
        rows[t["title"]] = {"xg_pg": xg / n, "xga_pg": xga / n, "games": n}
        tot_xg += xg
        tot_games += n
    if not rows or tot_games == 0:
        return {}
    league_avg = tot_xg / tot_games                # league avg goals/team/game (~xG)
    out = {}
    for name, r in rows.items():
        out[name] = {
            "att": round(r["xg_pg"] / league_avg, 3),
            "def": round(r["xga_pg"] / league_avg, 3),
            "games": r["games"],
        }
    return out


def fetch_strengths(league: str = "EPL", season: str = "2025",
                    cache: bool = True) -> dict:
    """Fetch a league page and return per-team xG strengths. Big-5 only."""
    if league not in LEAGUES:
        raise ValueError(f"Understat covers {sorted(LEAGUES)}, not {league}")
    url = f"{BASE}/{league}/{season}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=20) as resp:
        html = resp.read().decode("utf-8")
    if cache:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(os.path.join(config.CACHE_DIR, f"understat_{league}_{season}.html"),
                  "w", encoding="utf-8") as f:
            f.write(html)
    return team_strengths(parse_teams_data(html))


def build_strengths_spec(home: str, away: str, strengths: dict, match: str = "",
                         home_mult: float = 1.10) -> dict | None:
    """
    Build a run.build_prediction `strengths` spec from two teams' xG strengths.
    home_mult applies a generic home-field boost on top. None if a team is missing.
    """
    h, a = strengths.get(home), strengths.get(away)
    if not h or not a:
        return None
    return {
        "match": match or f"{home} vs {away}",
        "strengths": {
            "att_home": h["att"], "def_home": h["def"],
            "att_away": a["att"], "def_away": a["def"],
            "home_mult": home_mult,
        },
        "source": "understat",
    }


if __name__ == "__main__":
    # Offline demo against the bundled fixture.
    path = os.path.join(config.CACHE_DIR, "understat_sample.html")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            s = team_strengths(parse_teams_data(f.read()))
        for name, r in list(s.items())[:5]:
            print(f"{name:14} att {r['att']}  def {r['def']}  ({r['games']} g)")
