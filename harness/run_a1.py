"""
KAIROS harness — proposal A1, the checked sharp reference (research/hypotheses.md).

Development run (default): tags every baseline 1X2 bet with the gap between
Pinnacle and the other bookmakers, then compares kept and flagged bets at each
registered gap limit, and scores the three reference forecasts.

Holdout run: only after a gap limit has been chosen on development data.
    python harness/run_a1.py --holdout 0.10 "reason for reading the holdout"

Writes research/results/a1_<scope>.json and .md and appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

import fd_data
import fd_fetch
import metrics
import runlog
import score
import strategies
import walk
from run_baseline import BET_HEAD, RESULTS_DIR, bet_row, pct

GRID = (0.05, 0.10, 0.15)
MIN_FLAGGED = 30


def load_holdout(reason: str) -> list:
    out = []
    for season in fd_fetch.SEASONS:
        for league in fd_fetch.LEAGUES:
            if fd_data.is_holdout(league, season):
                out.extend(fd_data.load(league, season, include_holdout=True, reason=reason))
    return out


def analyse(matches: list, grid=GRID) -> dict:
    tagger = strategies.KairosV2Checked("B365", 0.03)
    pin = strategies.KairosV2("B365", 0.03, markets=("1x2",), name="pinnacle_alone")
    med = strategies.OthersMedian("B365")
    blends = [strategies.CheckedBlend(r) for r in grid]
    sc = score.Scorer()
    walk.run(matches, [tagger, pin, med, *blends], sc)
    bets = sc.bets.get(tagger.name, [])
    checked = [b for b in bets if b["gap"] is not None]
    res: dict = {"matches": len(matches), "bets": len(bets), "checked_bets": len(checked),
                 "unchecked_bets": len(bets) - len(checked),
                 "all": metrics.bet_summary(bets), "gates": {}, "forecasts": {}}
    for r in grid:
        kept = [b for b in bets if b["gap"] is None or b["gap"] <= r]
        flagged = [b for b in checked if b["gap"] > r]
        res["gates"][f"{r:.2f}"] = {
            "kept": metrics.bet_summary(kept), "flagged": metrics.bet_summary(flagged),
            "clv_kept_minus_flagged": metrics.group_diff(kept, flagged)}
    # Forecasts, on the matches all of them cover (those with enough other books).
    names = [pin.name, med.name, *(b.name for b in blends)]
    keys = sc.common_keys(names, "1x2")
    res["forecasts"]["common_matches"] = len(keys)
    for n in names:
        s = sc.forecast_table(n, "1x2", keys=keys).get("all")
        row = {k: s[k] for k in ("n", "log_loss", "brier", "rps", "ece")} if s else None
        if row and n != pin.name:
            row["log_loss_minus_pinnacle"] = sc.paired_log_loss(n, pin.name, "1x2", keys)
        res["forecasts"][n] = row
    return res


def choose(res: dict) -> float | None:
    """The registered choice rule: largest r with >= 30 flagged bets and diff interval > 0."""
    ok = [float(r) for r, g in res["gates"].items()
          if g["flagged"] and g["flagged"]["bets"] >= MIN_FLAGGED
          and g["clv_kept_minus_flagged"] and g["clv_kept_minus_flagged"]["lo"] > 0]
    return max(ok) if ok else None


def render(res: dict, title: str) -> str:
    L = [f"# {title}", "", f"Commit `{res['commit']}`. {res['matches']} matches, "
         f"{res['bets']} baseline 1X2 bets, {res['unchecked_bets']} of them with fewer than "
         f"3 other bookmakers (kept, not checkable).", "", BET_HEAD,
         bet_row("All baseline bets", res["all"])]
    for r, g in res["gates"].items():
        d = g["clv_kept_minus_flagged"]
        L += [bet_row(f"gap limit {float(r):.0%}: kept", g["kept"]),
              bet_row(f"gap limit {float(r):.0%}: flagged", g["flagged"]),
              f"| gap limit {float(r):.0%}: CLV kept minus flagged | | | | "
              + (f"{pct(d['diff'])} | {d['lo'] * 100:+.1f} to {d['hi'] * 100:+.1f} | |" if d
                 else "- | - | |")]
    L += ["", f"## Reference forecasts ({res['forecasts']['common_matches']} matches)", "",
          "| Forecaster | Log loss | Brier | Calibration error | Log loss minus Pinnacle alone | 95% interval |",
          "|---|---|---|---|---|---|"]
    for n, s in res["forecasts"].items():
        if n == "common_matches" or not s:
            continue
        d = s.get("log_loss_minus_pinnacle")
        L.append(f"| {n} | {s['log_loss']:.4f} | {s['brier']:.4f} | {s['ece'] * 100:.2f}% | "
                 + (f"{d['mean']:+.5f} | {d['lo']:+.5f} to {d['hi']:+.5f} |" if d else "- | - |"))
    if "chosen_r" in res:
        L += ["", f"Registered choice rule picks: "
              f"{'none' if res['chosen_r'] is None else format(res['chosen_r'], '.0%')}"]
    return "\n".join(L) + "\n"


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--holdout":
        r, reason = float(args[1]), " ".join(args[2:])
        res = analyse(load_holdout(reason), grid=(r,))
        scope, title = "holdout", f"A1 on the holdout, gap limit {r:.0%}"
    else:
        res = analyse(fd_data.load_development())
        res["chosen_r"] = choose(res)
        scope, title = "development", "A1 on development data"
    res["commit"] = runlog.git_commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"a1_{scope}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    text = render(res, title)
    with open(os.path.join(RESULTS_DIR, f"a1_{scope}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    keep = ("bets", "roi", "roi_ci", "clv", "clv_ci")
    runlog.append("B0" if scope == "holdout" else "A1", "baseline 1x2 bets", scope,
                  {k: res["all"][k] for k in keep} if res["all"] else None)
    for r, g in res["gates"].items():
        runlog.append("A1", f"gap limit {r}", scope, {
            "kept": {k: g["kept"][k] for k in keep} if g["kept"] else None,
            "flagged": {k: g["flagged"][k] for k in keep} if g["flagged"] else None,
            "clv_kept_minus_flagged": g["clv_kept_minus_flagged"]})
    for n, s in res["forecasts"].items():
        if n != "common_matches" and s:
            runlog.append("A1", f"forecast {n}", scope, s)


if __name__ == "__main__":
    main()
