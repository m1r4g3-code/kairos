"""
KAIROS harness — M1: do Football-Data's closing prices give the same CLV as
Pinnacle's close? (research/hypotheses.md, M1). Development seasons only.

    python harness/run_m1.py [--no-log]

Writes research/results/m1_close_proxy.json and .md. Pure stdlib.
"""

from __future__ import annotations

import json
import math
import os
import sys

import fd_data
import fd_fetch
import metrics
import runlog
import score
import strategies
import walk

RESULTS_DIR = os.path.join(fd_fetch.ROOT, "research", "results")
PROXIES = {"Avg": ("Avg", "BbAv"), "B365": ("B365",), "BFE": ("BFE",)}
SETS = {"B0 (Bet365 +3%)": strategies.KairosV2("B365", 0.03),
        "best of books +3%": strategies.KairosV2("BEST", 0.03)}


def corr(a: list[float], b: list[float]) -> float | None:
    n = len(a)
    if n < 3:
        return None
    ma, mb = sum(a) / n, sum(b) / n
    va, vb = sum((x - ma) ** 2 for x in a), sum((y - mb) ** 2 for y in b)
    if not va or not vb:
        return None
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / math.sqrt(va * vb)


def main() -> None:
    matches = fd_data.load_development()
    rows: dict = {name: [] for name in SETS}
    by_name = {s.name: label for label, s in SETS.items()}

    def on_decision(strategy, pre, post, decision):
        for bet in decision.bets:
            if bet.market != "1x2":
                continue
            ref = score.fair_close("1x2", post)
            rec = {"cluster": pre.key, "odds": bet.odds, "sel": bet.selection,
                   "pin": bet.odds * ref[bet.selection] - 1.0 if ref else None}
            for proxy, cols in PROXIES.items():
                v = next((post.close_1x2[c] for c in cols if c in post.close_1x2), None)
                try:
                    fair = score.market.devig_power(list(v)) if v else None
                except ValueError:
                    fair = None
                rec[proxy] = bet.odds * fair[bet.selection] - 1.0 if fair else None
            rows[by_name[strategy.name]].append(rec)

    walk.run(matches, list(SETS.values()), on_decision)

    res: dict = {"scope": "development league-seasons only", "matches": len(matches),
                 "commit": runlog.git_commit(), "sets": {}}
    for label, recs in rows.items():
        out = {"bets": len(recs), "with_pinnacle_close": sum(r["pin"] is not None for r in recs),
               "proxies": {}}
        for proxy in PROXIES:
            both = [r for r in recs if r["pin"] is not None and r[proxy] is not None]
            if not both:
                out["proxies"][proxy] = {"n": 0}
                continue
            a, b = [r[proxy] for r in both], [r["pin"] for r in both]
            d = metrics.paired_diff(a, b)
            out["proxies"][proxy] = {
                "n": len(both), "clv_proxy": sum(a) / len(a), "clv_pinnacle": sum(b) / len(b),
                "diff": d["mean"], "diff_lo": d["lo"], "diff_hi": d["hi"],
                "corr": corr(a, b),
                "rmse": math.sqrt(sum((x - y) ** 2 for x, y in zip(a, b)) / len(a)),
                "sign_agree": sum((x > 0) == (y > 0) for x, y in zip(a, b)) / len(a),
                "passes": abs(d["mean"]) <= 0.005 and (corr(a, b) or 0) >= 0.9}
        res["sets"][label] = out

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "m1_close_proxy.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    p = lambda x: "-" if x is None else f"{x * 100:+.2f}%"
    L = ["# M1: closing-price proxies against Pinnacle's close", "",
         f"Development seasons, {res['matches']} matches, commit {res['commit']}. 1X2 bets, power de-vig.", ""]
    for label, out in res["sets"].items():
        L += [f"## {label}", "", f"{out['bets']} bets, {out['with_pinnacle_close']} with a Pinnacle close.", "",
              "| Proxy close | Bets with both | CLV by proxy | CLV by Pinnacle | Proxy minus Pinnacle | 95% interval | Correlation | Per-bet error (RMSE) | Same sign | Passes |",
              "|---|---|---|---|---|---|---|---|---|---|"]
        for proxy, r in out["proxies"].items():
            if not r["n"]:
                L.append(f"| {proxy} | 0 | - | - | - | - | - | - | - | - |")
                continue
            L.append(f"| {proxy} | {r['n']} | {p(r['clv_proxy'])} | {p(r['clv_pinnacle'])} | {p(r['diff'])} | "
                     f"{p(r['diff_lo'])} to {p(r['diff_hi'])} | {r['corr']:.3f} | {r['rmse'] * 100:.2f} pts | "
                     f"{r['sign_agree'] * 100:.1f}% | {'yes' if r['passes'] else 'no'} |")
        L.append("")
    text = "\n".join(L)
    with open(os.path.join(RESULTS_DIR, "m1_close_proxy.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    if "--no-log" not in sys.argv:
        for label, out in res["sets"].items():
            runlog.append("M1", label, res["scope"], out)


if __name__ == "__main__":
    main()
