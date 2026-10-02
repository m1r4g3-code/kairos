"""
KAIROS harness — proposal A4 part 2, staking rules on the baseline's bets
(research/hypotheses.md).

Bootstraps bankroll paths over the B0 1X2 bets under three staking rules: flat,
quarter Kelly on the claimed edge, and quarter Kelly on the shrunk edge with
same-match grouping. The shrink factor is mean CLV / mean claimed edge on the
development bets.

    python harness/run_a4.py                              development data
    python harness/run_a4.py --holdout <shrink> "reason"   only if the rule passes

Writes research/results/a4_<scope>.json and .md and appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import random
import sys

import fd_data
import runlog
import score
import strategies
import walk
from run_a1 import load_holdout
from run_baseline import RESULTS_DIR

sys.path.insert(0, os.path.join(fd_data.ROOT, "engine"))
import kelly  # noqa: E402

START = 100.0
RULES = ("flat 1 unit", "quarter Kelly, claimed edge", "quarter Kelly, shrunk edge, grouped")


def stakes_for(match_bets: list[dict], rule: str, bankroll: float, shrink: float) -> list[float]:
    if rule == RULES[0]:
        return [1.0] * len(match_bets)
    k = 1.0 if rule == RULES[1] else shrink
    fr = [kelly.shrunk_stake_fraction(b["odds"], b["claimed_ev"], shrink=k) for b in match_bets]
    if rule == RULES[2] and sum(fr) > kelly.DEFAULT_CAP:      # one match, one position
        fr = [f * kelly.DEFAULT_CAP / sum(fr) for f in fr]
    return [f * bankroll for f in fr]


def path(clusters: list[list[dict]], rule: str, shrink: float) -> tuple[float, float]:
    """Final bankroll and worst peak-to-trough drawdown (as a share of the peak)."""
    bank = peak = START
    worst = 0.0
    for match_bets in clusters:
        if bank <= 0:
            break
        for b, st in zip(match_bets, stakes_for(match_bets, rule, bank, shrink)):
            bank += st * (b["odds"] - 1.0) if b["profit"] > 0 else -st
        peak = max(peak, bank)
        worst = max(worst, (peak - bank) / peak)
    return bank, worst


def pctl(xs: list[float], q: float) -> float:
    s = sorted(xs)
    return s[min(len(s) - 1, int(q * len(s)))]


def analyse(matches: list, shrink: float | None, n_paths: int = 2000, seed: int = 11) -> dict:
    b0 = strategies.KairosV2("B365", 0.03, markets=("1x2",))
    sc = score.Scorer()
    walk.run(matches, [b0], sc)
    bets = sc.bets.get(b0.name, [])
    by_match: dict = {}
    for b in bets:
        by_match.setdefault(b["cluster"], []).append(b)
    clusters = list(by_match.values())            # in walk (date) order
    with_clv = [b for b in bets if b["clv"] is not None]
    mean_claimed = sum(b["claimed_ev"] for b in bets) / len(bets)
    mean_clv = sum(b["clv"] for b in with_clv) / len(with_clv)
    fitted = max(0.0, min(1.0, mean_clv / mean_claimed))
    use = fitted if shrink is None else shrink
    res: dict = {"bets": len(bets), "matches_with_bets": len(clusters),
                 "mean_claimed_ev": mean_claimed, "mean_clv": mean_clv,
                 "shrink_fitted_here": fitted, "shrink_used": use, "n_paths": n_paths,
                 "actual_order": {}, "rules": {}}
    rng = random.Random(seed)
    draws = [rng.choices(clusters, k=len(clusters)) for _ in range(n_paths)]
    for rule in RULES:
        final, dd = zip(*(path(d, rule, use) for d in draws))
        res["rules"][rule] = {"median_final": pctl(final, 0.5), "p05_final": pctl(final, 0.05),
                              "median_drawdown": pctl(dd, 0.5), "p95_drawdown": pctl(dd, 0.95),
                              "share_of_paths_below_start": sum(f < START for f in final) / n_paths}
        f, d = path(clusters, rule, use)
        res["actual_order"][rule] = {"final": f, "worst_drawdown": d}
    return res


def passes(res: dict) -> bool:
    a, b = res["rules"][RULES[2]], res["rules"][RULES[1]]
    return a["p95_drawdown"] < b["p95_drawdown"] and a["median_final"] >= b["median_final"]


def render(res: dict, title: str) -> str:
    L = [f"# {title}", "",
         f"Commit `{res['commit']}`. {res['bets']} baseline 1X2 bets on {res['matches_with_bets']} "
         f"matches. Mean claimed edge {res['mean_claimed_ev'] * 100:+.2f}%, mean CLV "
         f"{res['mean_clv'] * 100:+.2f}%, shrink factor used {res['shrink_used']:.3f}. "
         f"Bankroll starts at {START:.0f}. {res['n_paths']} bootstrap paths.", "",
         "| Staking rule | Median final bankroll | 5th percentile final | Median worst drawdown | "
         "95th percentile worst drawdown | Paths ending below the start | Actual order: final | "
         "Actual order: worst drawdown |", "|---|---|---|---|---|---|---|---|"]
    for rule, r in res["rules"].items():
        a = res["actual_order"][rule]
        L.append(f"| {rule} | {r['median_final']:.1f} | {r['p05_final']:.1f} | "
                 f"{r['median_drawdown'] * 100:.1f}% | {r['p95_drawdown'] * 100:.1f}% | "
                 f"{r['share_of_paths_below_start'] * 100:.0f}% | {a['final']:.1f} | "
                 f"{a['worst_drawdown'] * 100:.1f}% |")
    L += ["", f"Registered rule (smaller 95th-percentile drawdown and no lower median final "
          f"bankroll than quarter Kelly on the claimed edge): "
          f"{'passes' if res['passes_rule'] else 'fails'}"]
    return "\n".join(L) + "\n"


def main() -> None:
    args = sys.argv[1:]
    if args and args[0] == "--holdout":
        res = analyse(load_holdout(" ".join(args[2:])), shrink=float(args[1]))
        scope = "holdout"
    else:
        res, scope = analyse(fd_data.load_development(), shrink=None), "development"
    res["passes_rule"] = passes(res)
    res["commit"] = runlog.git_commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"a4_{scope}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    text = render(res, f"A4 staking rules on the baseline's bets, {scope} data")
    with open(os.path.join(RESULTS_DIR, f"a4_{scope}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    for rule, r in res["rules"].items():
        runlog.append("A4", rule, scope, {**r, "shrink_used": res["shrink_used"],
                                          "passes_rule": res["passes_rule"]})


if __name__ == "__main__":
    main()
