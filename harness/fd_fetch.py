"""
KAIROS harness — Football-Data.co.uk bulk fetch (polite, resumable).

Downloads one league-season CSV at a time into data/football-data/ (gitignored),
with a pause between requests. Safe to kill at any moment: a file is written to
a .part name and renamed only when complete, and files already on disk are
skipped on the next run. Seasons a league does not have are remembered in
_missing.json so they are not asked for twice.

It never parses match rows. `manifest()` records only checksum, size, line count
and column names, which is allowed for holdout files (research/holdout.json).

CLI:
    python harness/fd_fetch.py            # fetch everything missing
    python harness/fd_fetch.py --manifest # rewrite research/data_manifest.json

Pure stdlib.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
import urllib.error
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(ROOT, "data", "football-data")
MANIFEST = os.path.join(ROOT, "research", "data_manifest.json")
MISSING = os.path.join(DATA_DIR, "_missing.json")
BASE = "https://www.football-data.co.uk/mmz4281"
USER_AGENT = "Kairos-research (personal, non-commercial; one request every few seconds)"

LEAGUES = ("E0", "E1", "E2", "E3", "EC", "SC0", "SC1", "SC2", "SC3", "D1", "D2",
           "I1", "I2", "SP1", "SP2", "F1", "F2", "N1", "B1", "P1", "T1", "G1")
FIRST_SEASON, LAST_SEASON = 2000, 2025      # start years: 2000/01 .. 2025/26


def season_code(start_year: int) -> str:
    """2024 -> '2425'."""
    return f"{start_year % 100:02d}{(start_year + 1) % 100:02d}"


def season_start_year(code: str) -> int:
    """'2425' -> 2024, '9900' -> 1999."""
    yy = int(code[:2])
    return 2000 + yy if yy < 80 else 1900 + yy


SEASONS = tuple(season_code(y) for y in range(FIRST_SEASON, LAST_SEASON + 1))


def path_for(league: str, season: str) -> str:
    return os.path.join(DATA_DIR, f"{league}_{season}.csv")


def _load_missing() -> list[str]:
    if os.path.exists(MISSING):
        with open(MISSING, encoding="utf-8") as f:
            return json.load(f)
    return []


def _save_json(path: str, obj) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def fetch_one(league: str, season: str, timeout: float = 30.0) -> str:
    """Fetch one file. Returns 'ok', 'missing' (HTTP 404) or 'limited' (HTTP 429)."""
    req = urllib.request.Request(f"{BASE}/{season}/{league}.csv",
                                 headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return "missing"
        if e.code == 429:
            return "limited"
        raise
    if not body.lstrip(b"\xef\xbb\xbf").startswith(b"Div"):
        return "missing"            # the site answers some absent files with an HTML page
    dest = path_for(league, season)
    with open(dest + ".part", "wb") as f:
        f.write(body)
    os.replace(dest + ".part", dest)
    return "ok"


def fetch_all(leagues=LEAGUES, seasons=SEASONS, delay: float = 3.0,
              max_backoffs: int = 6) -> dict:
    """Fetch every league-season not already on disk. Returns counts."""
    os.makedirs(DATA_DIR, exist_ok=True)
    missing = set(_load_missing())
    counts = {"ok": 0, "skipped": 0, "missing": 0, "errors": 0}
    for season in seasons:
        for league in leagues:
            key = f"{league}_{season}"
            if os.path.exists(path_for(league, season)) or key in missing:
                counts["skipped"] += 1
                continue
            backoff, status = 60.0, "limited"
            for _ in range(max_backoffs):
                try:
                    status = fetch_one(league, season)
                except (urllib.error.URLError, TimeoutError, OSError) as e:
                    status = f"error: {e}"
                if status != "limited":
                    break
                print(f"{key}: rate limited, waiting {backoff:.0f}s", flush=True)
                time.sleep(backoff)
                backoff *= 2
            if status == "limited":
                print("still rate limited; stopping. Re-run later to resume.", flush=True)
                return counts
            if status == "ok":
                counts["ok"] += 1
            elif status == "missing":
                counts["missing"] += 1
                missing.add(key)
                _save_json(MISSING, sorted(missing))
            else:
                counts["errors"] += 1
            print(f"{key}: {status}", flush=True)
            time.sleep(delay)
    return counts


def manifest() -> dict:
    """Checksum, size, line count and header of every file on disk. Reads no rows."""
    out = {}
    for name in sorted(os.listdir(DATA_DIR)):
        if not name.endswith(".csv"):
            continue
        with open(os.path.join(DATA_DIR, name), "rb") as f:
            raw = f.read()
        first = raw.split(b"\n", 1)[0].decode("utf-8-sig", errors="replace").strip()
        cols = [c for c in first.split(",") if c]
        out[name[:-4]] = {
            "sha256": hashlib.sha256(raw).hexdigest(),
            "bytes": len(raw),
            "lines": raw.count(b"\n"),
            "columns": cols,
        }
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    _save_json(MANIFEST, out)
    return out


if __name__ == "__main__":
    if "--manifest" in sys.argv:
        print(f"{len(manifest())} files in manifest")
    else:
        print(fetch_all())
        print(f"{len(manifest())} files in manifest")
