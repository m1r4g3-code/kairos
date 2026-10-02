"""
KAIROS harness — proposal A2, the de-vig bake-off (research/hypotheses.md).

Scores proportional, power and Shin de-vig of Pinnacle's price by log loss, on
1X2 and over/under 2.5, pre-match and closing. Each forecast uses only its own
match's price, so no walk is needed.

    python harness/run_a2.py                         development data
    python harness/run_a2.py --holdout "reason"      only after the choice rule passes

Writes research/results/a2_<scope>.json and .md and appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

import fd_data
import metrics
import runlog
import score
from run_a1 import load_holdout
from run_baseline import RESULTS_DIR

sys.path.insert(0, os.path.join(fd_data.ROOT, "engine"))
import market  # noqa: E402

METHODS = ("power", "proportional", "shin")
SETS = {"1x2 pre-match": ("1x2", "pre"), "1x2 closing": ("1x2", "close"),
        "ou25 pre-match": ("ou25", "pre"), "ou25 closing": ("ou25", "close")}
PRIMARY = "1x2 pre-match"


def band(longest: float) -> str:
    return "longest price under 5" if longest < 5 else (
        "longest price 5 to 10" if longest < 10 else "longest price 10 and over")


def price(pre, post, mkt: str, when: str):
    if when == "pre":
        return (pre.odds_1x2 if mkt == "1x2" else pre.odds_ou25).get("PS")
    return (post.close_1x2 if mkt == "1x2" else post.close_ou25).get("PS")


def analyse(matches: list) -> dict:
    res: dict = {"matches": len(matches), "sets": {}}
    for name, (mkt, when) in SETS.items():
        losses = {m: [] for m in METHODS}
        groups: list[tuple[str, str]] = []
        for pre, post in matches:
            v = price(pre, post, mkt, when)
            if not v:
                continue
            out = score.outcome_index(mkt, post)
            for m in METHODS:
                losses[m].append(metrics.log_loss(market.DEVIG[m](list(v)), out))
            groups.append((band(max(v)), pre.league))
        n = len(groups)
        entry = {"n": n, "log_loss": {m: metrics.mean_se(losses[m])[0] for m in METHODS},
                 "minus_power": {m: metrics.paired_diff(losses[m], losses["power"])
                                 for m in METHODS if m != "power"},
                 "by_band": {}, "by_league": {}}
        for gi, key in ((0, "by_band"), (1, "by_league")):
            for g in sorted({x[gi] for x in groups}):
                idx = [i for i, x in enumerate(groups) if x[gi] == g]
                entry[key][g] = {"n": len(idx), **{
                    m: metrics.paired_diff([losses[m][i] for i in idx],
                                           [losses["power"][i] for i in idx])
                    for m in METHODS if m != "power"}}
        res["sets"][name] = entry
    return res


def choose(res: dict) -> str | None:
    """Registered rule: lowest log loss on 1X2 pre-match, if its interval vs power is below zero."""
    s = res["sets"][PRIMARY]
    best = min(METHODS, key=lambda m: s["log_loss"][m])
    if best == "power" or s["minus_power"][best]["hi"] >= 0:
        return None
    return best


def render(res: dict, title: str) -> str:
    L = [f"# {title}", "", f"Commit `{res['commit']}`. {res['matches']} matches. "
         "Differences are log loss minus the power method's on the same matches; "
         "negative means better than power.", "",
         "| Price set | Matches | Power | Proportional | Shin | Proportional minus power | "
         "Shin minus power |", "|---|---|---|---|---|---|---|"]

    def d(x):
        return f"{x['mean']:+.5f} ({x['lo']:+.5f} to {x['hi']:+.5f})"

    for name, s in res["sets"].items():
        ll = s["log_loss"]
        L.append(f"| {name} | {s['n']} | {ll['power']:.5f} | {ll['proportional']:.5f} | "
                 f"{ll['shin']:.5f} | {d(s['minus_power']['proportional'])} | "
                 f"{d(s['minus_power']['shin'])} |")
    for key, label in (("by_band", "By longest price in the market"), ("by_league", "By league")):
        L += ["", f"## {label}, {PRIMARY}", "",
              "| Group | Matches | Proportional minus power | Shin minus power |", "|---|---|---|---|"]
        for g, s in res["sets"][PRIMARY][key].items():
            L.append(f"| {g} | {s['n']} | {d(s['proportional'])} | {d(s['shin'])} |")
    if "chosen" in res:
        L += ["", f"Registered choice rule picks: {res['chosen'] or 'none (power stays)'}"]
    return "\n".join(L) + "\n"


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--holdout":
        res, scope = analyse(load_holdout(" ".join(args[1:]))), "holdout"
    else:
        res, scope = analyse(fd_data.load_development()), "development"
        res["chosen"] = choose(res)
    res["commit"] = runlog.git_commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"a2_{scope}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    text = render(res, f"A2 de-vig bake-off, {scope} data")
    with open(os.path.join(RESULTS_DIR, f"a2_{scope}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    for name, s in res["sets"].items():
        for m in METHODS:
            runlog.append("A2", f"{m} de-vig, {name}", scope,
                          {"n": s["n"], "log_loss": s["log_loss"][m],
                           "minus_power": s["minus_power"].get(m)})


if __name__ == "__main__":
    main()
