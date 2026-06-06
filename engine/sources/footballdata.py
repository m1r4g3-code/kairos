"""
KAIROS source — Football-Data.co.uk adapter (free, KEYLESS).

Historical match results PLUS multiple bookmakers' odds (including Pinnacle and
Pinnacle Closing) as downloadable CSVs. This is the backtest fuel: it lets us
replay the soft-vs-sharp strategy on real seasons and measure ROI/CLV before
risking a single naira.

CSV columns we use:
  FTR                 full-time result: H / D / A
  B365H/B365D/B365A   Bet365 (soft-ish proxy)
  PSH/PSD/PSA         Pinnacle (sharp)
  PSCH/PSCD/PSCA      Pinnacle closing (sharpest truth proxy)
  MaxH/MaxD/MaxA      best price across all books (line-shopping proxy)

Pure stdlib (urllib + csv).
"""

from __future__ import annotations

import csv
import io
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import config  # noqa: E402

BASE = "https://www.football-data.co.uk/mmz4281"
# season code is like "2425" for 2024/25; league code "E0"=EPL, "SP1"=La Liga, etc.


def parse_csv(text: str) -> list[dict]:
    """Parse a Football-Data.co.uk CSV into a list of row dicts."""
    return [row for row in csv.DictReader(io.StringIO(text)) if row.get("FTR")]


def download(league: str = "E0", season: str = "2425", cache: bool = True) -> list[dict]:
    """Download one league-season CSV and return parsed rows."""
    url = f"{BASE}/{season}/{league}.csv"
    with urllib.request.urlopen(url, timeout=30) as resp:
        text = resp.read().decode("utf-8", errors="replace")
    if cache:
        os.makedirs(config.CACHE_DIR, exist_ok=True)
        with open(os.path.join(config.CACHE_DIR, f"fd_{league}_{season}.csv"),
                  "w", encoding="utf-8") as f:
            f.write(text)
    return parse_csv(text)


if __name__ == "__main__":
    print("Football-Data.co.uk adapter. Example: download('E0','2425').")
