"""
KAIROS harness — the frozen baseline on the holdout seasons (entry B0-H in
research/hypotheses.md). Run once, at the end of Phase 3.

    python harness/run_b0_holdout.py "reason for reading the holdout"

Writes research/results/b0_holdout.json and .md and appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

import fd_fetch
import metrics
import runlog
import score
import strategies
import walk
from run_a1 import load_holdout
from run_baseline import (BET_HEAD, FC_HEAD, MARKET_NAMES, MARKETS, RESULTS_DIR, bet_row,
                          fc_row, slim)

BIG5 = {"E0", "SP1", "D1", "I1", "F1"}


def main() -> None:
    reason = " ".join(sys.argv[1:])
    matches = load_holdout(reason)
    b0 = strategies.KairosV2("B365", 0.03)
    sc = score.Scorer()
    walk.run(matches, [b0], sc)
    res: dict = {"matches": len(matches), "commit": runlog.git_commit(), "bets": {}, "forecast": {}}
    for mkt in MARKETS:
        res["bets"][mkt] = {"all": sc.bet_table(b0.name, mkt).get("all"),
                            "all_clv_proportional": sc.bet_table(b0.name, mkt, clv_key="clv_prop").get("all"),
                            "by_league": sc.bet_table(b0.name, mkt, by="league"),
                            "by_season": sc.bet_table(b0.name, mkt, by="season")}
        res["forecast"][mkt] = {"all": slim(sc.forecast_table(b0.name, mkt).get("all")),
                                "closing": slim(sc.forecast_table(score.CLOSE_REF, mkt).get("all"))}
    bets = [b for b in sc.bets.get(b0.name, []) if b["market"] == "1x2"]
    res["groups_1x2"] = {
        "E0 SP1 D1 I1 F1": metrics.bet_summary([b for b in bets if b["league"] in BIG5]),
        "other 17 leagues": metrics.bet_summary([b for b in bets if b["league"] not in BIG5])}
    res["priced_1x2"] = sum(1 for p, _ in matches if "PS" in p.odds_1x2 and "B365" in p.odds_1x2)
    res["mean_claimed_ev_1x2"] = sum(b["claimed_ev"] for b in bets) / len(bets) if bets else None

    L = ["# Baseline B0 on the holdout seasons", "",
         f"Commit `{res['commit']}`. {res['matches']} holdout matches "
         f"(2025/26 all leagues; 2024/25 for 17 leagues). {res['priced_1x2']} priced by both "
         "Pinnacle and Bet365 for 1X2."]
    for mkt in MARKETS:
        b = res["bets"][mkt]
        L += ["", f"## Bets, {MARKET_NAMES[mkt]}", "", BET_HEAD, bet_row("**All**", b["all"])]
        if b["all_clv_proportional"]:
            p = b["all_clv_proportional"]
            L.append(f"| All, CLV by proportional de-vig | {p['bets']} | | | "
                     f"{p['clv'] * 100:+.1f}% | {p['clv_ci'][0] * 100:+.1f} to {p['clv_ci'][1] * 100:+.1f} | |")
        L += [bet_row(k, v) for k, v in b["by_season"].items()]
        if mkt == "1x2":
            L += [bet_row(k, v) for k, v in res["groups_1x2"].items()]
        L += [bet_row(k, v) for k, v in b["by_league"].items()]
    L += ["", "## Forecast (Pinnacle pre-match, power de-vig) and the closing price", "", FC_HEAD]
    for mkt in MARKETS:
        L += [fc_row(f"{MARKET_NAMES[mkt]}: pre-match", res["forecast"][mkt]["all"]),
              fc_row(f"{MARKET_NAMES[mkt]}: closing", res["forecast"][mkt]["closing"])]
    if res["mean_claimed_ev_1x2"] is not None:
        L += ["", f"Mean claimed edge of the 1X2 bets: {res['mean_claimed_ev_1x2'] * 100:+.2f}%."]
    text = "\n".join(L) + "\n"

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "b0_holdout.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    with open(os.path.join(RESULTS_DIR, "b0_holdout.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    for mkt in MARKETS:
        s = res["bets"][mkt]["all"]
        runlog.append("B0-H", f"{b0.name} {mkt}", "holdout",
                      None if s is None else {k: s[k] for k in
                                              ("bets", "roi", "roi_ci", "clv", "clv_ci", "clv_n")})


if __name__ == "__main__":
    if len(sys.argv) < 2:
        raise SystemExit("give a reason for reading the holdout")
    main()
