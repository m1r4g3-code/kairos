"""
KAIROS paper trading — match an Odds API fixture to a Football-Data result.

The two sources spell teams differently ("Queens Park Rangers" / "QPR",
"West Bromwich Albion" / "West Brom", "Wrexham AFC" / "Wrexham"). Within one
league and one date (plus or minus a day) there are only a handful of games, so
the pair of names is scored against each candidate and the best clear winner
is taken. Anything ambiguous is left unmatched rather than guessed.

Pure stdlib.
"""

from __future__ import annotations

import datetime as dt
import difflib
import unicodedata

STOP = {"fc", "afc", "cf", "sc", "ac", "ssc", "us", "as", "calcio", "club", "de", "cd", "ud",
        "sd", "rc", "real", "the", "1", "fk", "sv", "vfl", "vfb", "tsg", "fsv", "spvgg", "ssv",
        "city", "united", "town", "athletic", "rovers", "county", "wanderers", "albion",
        "hotspur", "and", "hove"}
ALIASES = {"wolverhampton wanderers": "wolves", "queens park rangers": "qpr",
           "sheffield wednesday": "sheffield weds", "milton keynes dons": "milton keynes dons",
           "nottingham forest": "nott'm forest"}


def norm(name: str) -> str:
    s = unicodedata.normalize("NFKD", name)
    s = "".join(c for c in s if not unicodedata.combining(c)).lower()
    s = ALIASES.get(s.strip(), s)
    return "".join(c if c.isalnum() or c == " " else " " for c in s).strip()


def core_tokens(name: str) -> str:
    toks = [t for t in norm(name).split() if t not in STOP]
    return " ".join(toks) or norm(name)


def similarity(a: str, b: str) -> float:
    na, nb = norm(a), norm(b)
    if na == nb:
        return 1.0
    ca, cb = core_tokens(a), core_tokens(b)
    if ca == cb:
        return 0.95
    initials = "".join(t[0] for t in na.split() if t not in {"fc", "afc"})
    if initials and initials == nb.replace(" ", ""):
        return 0.9
    if ca and cb and (ca.startswith(cb) or cb.startswith(ca)):
        return 0.85
    return difflib.SequenceMatcher(None, ca, cb).ratio()


def match(home: str, away: str, kickoff: dt.date, rows: list[dict],
          min_score: float = 0.6, min_margin: float = 0.15) -> dict | None:
    """The result row for this fixture, or None if no clear match."""
    cands = [r for r in rows if abs((r["date"] - kickoff).days) <= 1]
    scored = sorted(((min(similarity(home, r["home"]), similarity(away, r["away"])), i)
                     for i, r in enumerate(cands)), reverse=True)
    if not scored or scored[0][0] < min_score:
        return None
    if len(scored) > 1 and scored[0][0] - scored[1][0] < min_margin:
        return None
    return cands[scored[0][1]]
