"""
KAIROS harness — Football-Data.co.uk loader.

Turns one league-season CSV into two records per match:

  PreMatch  what was knowable when the odds were collected: teams, date and the
            pre-match prices (collected Friday afternoon for weekend games and
            Tuesday afternoon for midweek games, per the site's notes.txt).
  Post      what was only knowable later: the result, the match statistics and
            the closing prices.

A strategy is handed PreMatch only. Post goes to the scorer, and to the strategy
only after the whole collection window has been decided (see walk.py). Keeping
the two in separate types is the first of the leakage defences.

Holdout league-seasons (research/holdout.json) are refused unless the caller
passes include_holdout=True with a reason; every such read is logged.

Pure stdlib.
"""

from __future__ import annotations

import csv
import datetime as dt
import io
import json
import os
from dataclasses import dataclass, field

import fd_fetch

ROOT = fd_fetch.ROOT
HOLDOUT_FILE = os.path.join(ROOT, "research", "holdout.json")
HOLDOUT_LOG = os.path.join(ROOT, "research", "holdout_access.jsonl")

# Column prefixes that are not a single bookmaker's pre-match price.
AGGREGATES = ("Max", "Avg", "BbMx", "BbAv")
SHARP = "PS"                       # Pinnacle
EXCHANGES = ("BFE",)               # Betfair Exchange: commission applies, not a book price
OU_RENAME = {"P": "PS", "PC": "PSC"}   # the O/U columns call Pinnacle "P"
STAT_COLS = ("HS", "AS", "HST", "AST", "HC", "AC")


class HoldoutError(RuntimeError):
    pass


@dataclass(frozen=True)
class PreMatch:
    key: str
    league: str
    season: str
    date: dt.date
    home: str
    away: str
    odds_1x2: dict = field(default_factory=dict)    # book -> (home, draw, away)
    odds_ou25: dict = field(default_factory=dict)   # book -> (over, under)


@dataclass(frozen=True)
class Post:
    key: str
    fthg: int
    ftag: int
    ftr: str                                        # "H" / "D" / "A"
    close_1x2: dict = field(default_factory=dict)   # book -> (home, draw, away)
    close_ou25: dict = field(default_factory=dict)  # book -> (over, under)
    stats: dict = field(default_factory=dict)       # shots, shots on target, corners


# ── holdout guard ────────────────────────────────────────────────────────────

def _holdout_spec() -> dict:
    with open(HOLDOUT_FILE, encoding="utf-8") as f:
        return json.load(f)["machine"]


def is_holdout(league: str, season: str) -> bool:
    rule = _holdout_spec().get(season)
    if rule is None:
        return False
    return rule == "*" or league not in rule["except"]


def _log_holdout_read(league: str, season: str, reason: str) -> None:
    rec = {"utc": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "league": league, "season": season, "reason": reason}
    with open(HOLDOUT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec) + "\n")


# ── parsing ──────────────────────────────────────────────────────────────────

def _price(row: dict, cols: tuple) -> tuple | None:
    try:
        vals = tuple(float(row[c]) for c in cols)
    except (KeyError, ValueError, TypeError):
        return None
    return vals if all(v > 1.0 for v in vals) else None


def _date(text: str) -> dt.date | None:
    for fmt in ("%d/%m/%Y", "%d/%m/%y"):
        try:
            return dt.datetime.strptime(text.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def book_columns(header: list[str]) -> dict:
    """
    Sort a file's odds columns into pre-match and closing groups.

    1X2 prices are any <prefix>H, <prefix>D, <prefix>A triple. A prefix that is
    another prefix plus "C" is that book's closing price (B365 -> B365C).
    O/U 2.5 prices are <prefix>>2.5 and <prefix><2.5, closing likewise.
    """
    cols = set(header)
    triples = {c[:-1] for c in cols
               if c.endswith("H") and len(c) > 1
               and c[:-1] + "D" in cols and c[:-1] + "A" in cols}
    pre = {p for p in triples if not (p.endswith("C") and p[:-1] in triples)}
    close = {p[:-1] for p in triples - pre}
    ou = {c[:-4] for c in cols if c.endswith(">2.5") and c[:-4] + "<2.5" in cols}
    ou_pre = {p for p in ou if not (p.endswith("C") and p[:-1] in ou)}
    ou_close = {p[:-1] for p in ou - ou_pre}
    return {"pre_1x2": sorted(pre), "close_1x2": sorted(close),
            "pre_ou25": sorted(ou_pre), "close_ou25": sorted(ou_close)}


def parse(text: str, league: str, season: str) -> list[tuple[PreMatch, Post]]:
    """Parse one CSV. Rows without a date, teams or a full-time score are dropped."""
    reader = csv.reader(io.StringIO(text))
    try:
        header = [h.strip() for h in next(reader)]
    except StopIteration:
        return []
    groups = book_columns(header)
    out = []
    for i, raw in enumerate(reader):
        row = dict(zip(header, raw))
        date = _date(row.get("Date", ""))
        home, away = row.get("HomeTeam", "").strip(), row.get("AwayTeam", "").strip()
        ftr = row.get("FTR", "").strip()
        try:
            hg, ag = int(float(row["FTHG"])), int(float(row["FTAG"]))
        except (KeyError, ValueError, TypeError):
            continue
        if not date or not home or not away or ftr not in ("H", "D", "A"):
            continue
        key = f"{league}_{season}_{i:04d}"

        pre_1x2, close_1x2, pre_ou, close_ou = {}, {}, {}, {}
        for p in groups["pre_1x2"]:
            v = _price(row, (p + "H", p + "D", p + "A"))
            if v:
                pre_1x2[p] = v
        for p in groups["close_1x2"]:
            v = _price(row, (p + "CH", p + "CD", p + "CA"))
            if v:
                close_1x2[p] = v
        for p in groups["pre_ou25"]:
            v = _price(row, (p + ">2.5", p + "<2.5"))
            if v:
                pre_ou[OU_RENAME.get(p, p)] = v
        for p in groups["close_ou25"]:
            v = _price(row, (p + "C>2.5", p + "C<2.5"))
            if v:
                close_ou[OU_RENAME.get(p, p)] = v

        stats = {}
        for c in STAT_COLS:
            try:
                stats[c] = int(float(row[c]))
            except (KeyError, ValueError, TypeError):
                pass

        out.append((
            PreMatch(key, league, season, date, home, away, pre_1x2, pre_ou),
            Post(key, hg, ag, ftr, close_1x2, close_ou, stats),
        ))
    return out


def _read_text(path: str) -> str:
    with open(path, "rb") as f:
        raw = f.read()
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        return raw.decode("cp1252", errors="replace")


def load(league: str, season: str, include_holdout: bool = False,
         reason: str = "") -> list[tuple[PreMatch, Post]]:
    """Load one league-season from disk. Holdout seasons need a written reason."""
    if is_holdout(league, season):
        if not include_holdout or not reason.strip():
            raise HoldoutError(f"{league} {season} is holdout (research/holdout.json)")
        _log_holdout_read(league, season, reason)
    path = fd_fetch.path_for(league, season)
    if not os.path.exists(path):
        return []
    return parse(_read_text(path), league, season)


def load_development(leagues=fd_fetch.LEAGUES, seasons=fd_fetch.SEASONS):
    """Every non-holdout league-season on disk, in file order."""
    out = []
    for season in seasons:
        for league in leagues:
            if not is_holdout(league, season):
                out.extend(load(league, season))
    return out
