"""
KAIROS engine — soft-vs-sharp backtester (the honesty check).

Replays the v2.0 strategy on real history: where a SOFT book's price beats the
de-vigged SHARP (Pinnacle) price by a threshold, place a notional 1u bet and
settle on the actual result. Reports ROI / hit-rate / closing-line value so the
user can judge whether the edge is real BEFORE paying for anything.

Reuses market.devig_power for the sharp fair probs. Pure stdlib.

CLI:
    python backtest.py <league> <season>     # e.g. python backtest.py E0 2425
    python backtest.py --fixture fd_sample.csv
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config          # noqa: E402
import market          # noqa: E402
from sources import footballdata  # noqa: E402

# Column groups, tried in order (newer files have closing 'C' columns).
SOFT_COLS = [("B365H", "B365D", "B365A"), ("MaxH", "MaxD", "MaxA")]
SHARP_COLS = [("PSCH", "PSCD", "PSCA"), ("PSH", "PSD", "PSA"),
              ("AvgCH", "AvgCD", "AvgCA")]
RESULTS = ("H", "D", "A")


def _odds(row: dict, cols: tuple[str, str, str]) -> list[float] | None:
    try:
        vals = [float(row[c]) for c in cols]
    except (KeyError, ValueError, TypeError):
        return None
    return vals if all(o > 1.0 for o in vals) else None


def _first(row: dict, groups: list[tuple[str, str, str]]):
    for g in groups:
        o = _odds(row, g)
        if o:
            return o
    return None


def run_backtest(rows: list[dict], thresholds=(0.0, 0.02, 0.05, 0.08, 0.10)) -> list[dict]:
    """For each EV threshold, replay soft-vs-sharp and tally ROI/hit/CLV."""
    out = []
    for thr in thresholds:
        bets = wins = 0
        staked = profit = 0.0
        clv_terms: list[float] = []
        usable = 0
        for row in rows:
            soft = _first(row, SOFT_COLS)
            sharp = _first(row, SHARP_COLS)
            if not soft or not sharp:
                continue
            usable += 1
            fair = market.devig_power(sharp)           # sharp "true" probs
            for k, res in enumerate(RESULTS):
                ev = soft[k] * fair[k] - 1.0
                if ev > thr:
                    bets += 1
                    staked += 1.0
                    clv_terms.append(soft[k] / sharp[k] - 1.0)  # beat the sharp price?
                    if row.get("FTR") == res:
                        wins += 1
                        profit += soft[k] - 1.0
                    else:
                        profit -= 1.0
        out.append({
            "threshold": thr,
            "bets": bets,
            "hit_rate": round(wins / bets, 4) if bets else None,
            "roi": round(profit / staked, 4) if staked else None,
            "profit_u": round(profit, 2),
            "avg_clv": round(sum(clv_terms) / len(clv_terms), 4) if clv_terms else None,
            "matches_usable": usable,
        })
    return out


def print_report(rows: list[dict], title: str) -> None:
    res = run_backtest(rows)
    print("=" * 72)
    print(f"  KAIROS BACKTEST -- {title}   ({len(rows)} matches)")
    print("  Strategy: bet when a soft price beats Pinnacle's de-vigged fair price.")
    print("=" * 72)
    print(f"  {'min EV':>7}{'#bets':>8}{'hit%':>8}{'ROI':>9}{'profit(u)':>11}{'avg CLV':>10}")
    print("  " + "-" * 68)
    for r in res:
        hit = f"{r['hit_rate']*100:.1f}" if r["hit_rate"] is not None else "-"
        roi = f"{r['roi']*100:+.1f}%" if r["roi"] is not None else "-"
        clv = f"{r['avg_clv']*100:+.1f}%" if r["avg_clv"] is not None else "-"
        print(f"  {r['threshold']*100:>6.0f}%{r['bets']:>8}{hit:>8}{roi:>9}"
              f"{r['profit_u']:>11.2f}{clv:>10}")
    print("  " + "-" * 68)
    print("  ROI>0 AND CLV>0 across a big sample = real edge. You judge it.")
    print("=" * 72)


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--fixture":
        path = os.path.join(config.CACHE_DIR, args[1])
        with open(path, encoding="utf-8") as f:
            rows = footballdata.parse_csv(f.read())
        print_report(rows, f"fixture {args[1]}")
        return
    league = args[0] if args else "E0"
    season = args[1] if len(args) > 1 else "2425"
    rows = footballdata.download(league, season)
    print_report(rows, f"{league} {season}")


if __name__ == "__main__":
    main()
