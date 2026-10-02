"""
KAIROS harness — proposal A3, pricing cousin markets from the sharp line
(research/hypotheses.md).

T1  Fit expected goals to Pinnacle's fair 1X2 only; score the fitted over-2.5
    probability against Pinnacle's own and Bet365's own over/under price.
T2  Fit expected goals to Pinnacle's fair 1X2 margin and fair over 2.5; score
    the fitted probability that the home side covers the Asian handicap line
    (half lines only) against Pinnacle's own and Bet365's own handicap price.

Each forecast uses only its own match's pre-match prices, so no walk is needed.

    python harness/run_a3.py                         development data
    python harness/run_a3.py --holdout "reason"      only for fits that survived

Writes research/results/a3_<scope>.json and .md and appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import sys

import fd_data
import metrics
import runlog
from run_a1 import load_holdout
from run_baseline import RESULTS_DIR

sys.path.insert(0, os.path.join(fd_data.ROOT, "engine"))
import derive   # noqa: E402
import market   # noqa: E402
import poisson  # noqa: E402

LABELS = ("home", "draw", "away")


def _fair_1x2(pre) -> dict | None:
    v = pre.odds_1x2.get("PS")
    return dict(zip(LABELS, market.devig_power(list(v)))) if v else None


def _compare(rows: list[tuple]) -> dict:
    """rows: (derived p, pinnacle p, bet365 p, happened) for the 'yes' side of a 2-way market."""
    def ll(i):
        return [metrics.log_loss((r[i], 1.0 - r[i]), 0 if r[3] else 1) for r in rows]
    d, p, b = ll(0), ll(1), ll(2)
    recs = [((r[0], 1.0 - r[0]), 0 if r[3] else 1) for r in rows]
    return {"n": len(rows),
            "log_loss": {"derived": metrics.mean_se(d)[0], "pinnacle_own": metrics.mean_se(p)[0],
                         "bet365_own": metrics.mean_se(b)[0]},
            "derived_minus_pinnacle": metrics.paired_diff(d, p),
            "derived_minus_bet365": metrics.paired_diff(d, b),
            "derived_ece": metrics.forecast_summary(recs)["ece"],
            "mean_abs_gap_to_pinnacle": sum(abs(r[0] - r[1]) for r in rows) / len(rows)}


def analyse(matches: list, tests=("T1", "T2")) -> dict:
    t1, t2 = [], []
    for pre, post in matches:
        fair = _fair_1x2(pre)
        ou_p, ou_b = pre.odds_ou25.get("PS"), pre.odds_ou25.get("B365")
        if not fair or not ou_p:
            continue
        p_over = market.devig_power(list(ou_p))[0]
        if "T1" in tests and ou_b:
            lh, la = derive.fit_from_1x2(fair)
            s = derive.total_settlement(poisson.score_matrix(lh, la), 2.5)
            t1.append((s["win"], p_over, market.devig_power(list(ou_b))[0],
                       post.fthg + post.ftag > 2))
        ah_p, ah_b = pre.odds_ah.get("PS"), pre.odds_ah.get("B365")
        line = pre.ah_line
        if "T2" in tests and ah_p and ah_b and line is not None and (line * 2) % 2 == 1:
            lh, la = derive.fit_from_1x2_and_total(fair, p_over)
            s = derive.handicap_settlement(poisson.score_matrix(lh, la), line)
            t2.append((s["win"], market.devig_power(list(ah_p))[0],
                       market.devig_power(list(ah_b))[0], post.fthg - post.ftag + line > 0))
    res: dict = {"matches": len(matches)}
    if "T1" in tests:
        res["T1 over 2.5 from 1X2 only"] = _compare(t1) if t1 else None
    if "T2" in tests:
        res["T2 handicap (half lines) from 1X2 and total"] = _compare(t2) if t2 else None
    return res


def survives(entry: dict | None) -> bool:
    """Registered kill rule: dead if worse than Bet365's own (interval wholly above zero)."""
    return bool(entry) and entry["derived_minus_bet365"]["lo"] <= 0


def render(res: dict, title: str) -> str:
    L = [f"# {title}", "", f"Commit `{res['commit']}`. {res['matches']} matches loaded. "
         "Differences are log loss of the derived price minus the bookmaker's own, on the "
         "same matches; positive means the derived price is worse.", "",
         "| Test | Matches | Derived | Pinnacle's own | Bet365's own | Derived minus Pinnacle | "
         "Derived minus Bet365 | Mean gap to Pinnacle | Verdict |", "|---|---|---|---|---|---|---|---|---|"]

    def d(x):
        return f"{x['mean']:+.5f} ({x['lo']:+.5f} to {x['hi']:+.5f})"

    for name, e in res.items():
        if not isinstance(e, dict) or "log_loss" not in e:
            continue
        ll = e["log_loss"]
        L.append(f"| {name} | {e['n']} | {ll['derived']:.5f} | {ll['pinnacle_own']:.5f} | "
                 f"{ll['bet365_own']:.5f} | {d(e['derived_minus_pinnacle'])} | "
                 f"{d(e['derived_minus_bet365'])} | {e['mean_abs_gap_to_pinnacle'] * 100:.2f} points | "
                 f"{'survives' if survives(e) else 'killed'} |")
    return "\n".join(L) + "\n"


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--holdout":
        tests = tuple(args[1].split(","))
        res, scope = analyse(load_holdout(" ".join(args[2:])), tests), "holdout"
    else:
        res, scope = analyse(fd_data.load_development()), "development"
    res["commit"] = runlog.git_commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"a3_{scope}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    text = render(res, f"A3 cousin-market pricing, {scope} data")
    with open(os.path.join(RESULTS_DIR, f"a3_{scope}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    for name, e in res.items():
        if isinstance(e, dict) and "log_loss" in e:
            runlog.append("A3", name, scope, {**e, "survives": survives(e)})


if __name__ == "__main__":
    main()
