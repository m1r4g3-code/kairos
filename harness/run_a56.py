"""
KAIROS harness — proposals A5 (goal ratings, 1X2) and A6 (shots-on-target
ratings, over/under 2.5). Specifications are in research/hypotheses.md.

    python harness/run_a56.py a5
    python harness/run_a56.py a6
    python harness/run_a56.py a5 --holdout <k> <w> "reason"   only if the rule passes

Development run: picks k by the model's own log loss, fits the log-pool weight
against Pinnacle's pre-match price (overall, and walk-forward by season), and
for A6 also scores the model's bets at Bet365's over/under price.

Writes research/results/<a5|a6>_<scope>.json and .md, appends to research/runs.jsonl.

Pure stdlib.
"""

from __future__ import annotations

import json
import math
import os
import sys

import fd_data
import fd_fetch
import metrics
import ratings
import runlog
import score
import strategies
import walk
from run_a1 import load_holdout
from run_baseline import BET_HEAD, RESULTS_DIR, bet_row

K_GRID = (0.02, 0.04, 0.08)
SPEC = {"a5": ("goals", "1x2"), "a6": ("sot", "ou25")}


def rows_for(sc, model: str, market: str, mkt: str, keys=None) -> list[tuple]:
    """(log market, log model, outcome, season, key) on matches both forecasters cover."""
    fm, fq = sc.forecasts.get(market, {}).get(mkt, {}), sc.forecasts.get(model, {}).get(mkt, {})
    out = []
    for k in sorted(set(fm) & set(fq)):
        if keys is not None and k not in keys:
            continue
        m, o, _lg, season = fm[k]
        q = fq[k][0]
        out.append((tuple(math.log(max(x, 1e-12)) for x in m),
                    tuple(math.log(max(x, 1e-12)) for x in q), o, season, k))
    return out


def losses(rows: list[tuple], w: float) -> list[float]:
    return [-ratings.pool_loglik([r[:3]], w) for r in rows]


def analyse(matches: list, which: str, eval_keys=None, k_fixed=None, w_fixed=None) -> dict:
    signal, mkt = SPEC[which]
    ks = (k_fixed,) if k_fixed else K_GRID
    models = [ratings.OnlineRatings(k, signal, bet_ou_book="B365" if which == "a6" else None)
              for k in ks]
    market = strategies.KairosV2("B365", 0.03, markets=(mkt,), name="pinnacle_pre")
    sc = score.Scorer()
    walk.run(matches, [market, *models], sc)

    res: dict = {"matches": len(matches), "market": mkt, "k_grid": {}}
    best = None
    for m in models:
        rows = rows_for(sc, m.name, market.name, mkt, eval_keys)
        ll_model = sum(losses(rows, 1.0)) / len(rows)
        ll_mkt = sum(losses(rows, 0.0)) / len(rows)
        res["k_grid"][str(m.k)] = {"n": len(rows), "model_log_loss": ll_model,
                                   "market_log_loss": ll_mkt}
        if best is None or ll_model < best[1]:
            best = (m, ll_model, rows)
    model, _, rows = best
    res["k"] = model.k
    res["model_minus_market"] = metrics.paired_diff(losses(rows, 1.0), losses(rows, 0.0))

    if w_fixed is None:
        fit = ratings.fit_weight([r[:3] for r in rows])
        res["weight"] = fit
        # walk-forward: each season uses the weight fitted on earlier seasons only
        seasons = sorted({r[3] for r in rows}, key=fd_fetch.season_start_year)
        wf_blend, wf_mkt, wf_w = [], [], {}
        for s in seasons[1:]:
            y = fd_fetch.season_start_year(s)
            past = [r[:3] for r in rows if fd_fetch.season_start_year(r[3]) < y]
            w = ratings.fit_weight(past, interval=False)["w"]
            cur = [r for r in rows if r[3] == s]
            wf_w[s] = w
            wf_blend += losses(cur, w)
            wf_mkt += losses(cur, 0.0)
        res["walk_forward"] = {"weights_by_season": wf_w,
                               "blend_minus_market": metrics.paired_diff(wf_blend, wf_mkt)}
        res["goes_to_holdout"] = bool(fit["lo"] > 0
                                      and res["walk_forward"]["blend_minus_market"]["hi"] < 0)
    else:
        res["weight_frozen"] = w_fixed
        res["blend_minus_market"] = metrics.paired_diff(losses(rows, w_fixed), losses(rows, 0.0))

    if which == "a6":
        bets = [b for b in sc.bets.get(model.name, [])
                if eval_keys is None or b["cluster"] in eval_keys]
        res["bets"] = metrics.bet_summary(bets)
        if w_fixed is None:
            res["goes_to_holdout"] = bool(res["goes_to_holdout"] and res["bets"]
                                          and res["bets"]["clv_ci"]
                                          and res["bets"]["clv_ci"][0] > 0)
    return res


def render(res: dict, title: str) -> str:
    def d(x):
        return f"{x['mean']:+.5f} ({x['lo']:+.5f} to {x['hi']:+.5f})"

    L = [f"# {title}", "", f"Commit `{res['commit']}`. Market: Pinnacle pre-match, power de-vig, "
         f"{res['market']}. Differences are log loss minus the market's on the same matches; "
         "positive means worse than the market.", "",
         "| k | Matches | Model log loss | Market log loss |", "|---|---|---|---|"]
    for k, g in res["k_grid"].items():
        L.append(f"| {k} | {g['n']} | {g['model_log_loss']:.5f} | {g['market_log_loss']:.5f} |")
    L += ["", f"Chosen k: {res['k']}. Model minus market: {d(res['model_minus_market'])}."]
    if "weight" in res:
        w = res["weight"]
        L += ["", f"Log-pool weight on the model: **{w['w']:.4f}** (95% interval {w['lo']:.4f} to "
              f"{w['hi']:.4f}), {w['n']} matches.",
              f"Walk-forward blend minus market: {d(res['walk_forward']['blend_minus_market'])}.",
              "Weights by season (fitted on earlier seasons): "
              + ", ".join(f"{s} {v:.3f}" for s, v in res["walk_forward"]["weights_by_season"].items())]
    else:
        L += ["", f"Frozen weight {res['weight_frozen']}: blend minus market {d(res['blend_minus_market'])}."]
    if "bets" in res:
        L += ["", "Bets at Bet365's over/under price where model probability x price - 1 > 3%:",
              "", BET_HEAD, bet_row("Model bets", res["bets"])]
    if "goes_to_holdout" in res:
        L += ["", f"Registered choice rule: {'goes to the holdout' if res['goes_to_holdout'] else 'killed on development data; holdout not read'}"]
    return "\n".join(L) + "\n"


def main() -> None:
    which, args = sys.argv[1], sys.argv[2:]
    if args and args[0] == "--holdout":
        k, w, reason = float(args[1]), float(args[2]), " ".join(args[3:])
        hold = load_holdout(reason)
        res = analyse(fd_data.load_development() + hold, which,
                      eval_keys={p.key for p, _ in hold}, k_fixed=k, w_fixed=w)
        scope = "holdout"
    else:
        res, scope = analyse(fd_data.load_development(), which), "development"
    res["commit"] = runlog.git_commit()
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, f"{which}_{scope}.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    text = render(res, f"{which.upper()} ratings model, {scope} data")
    with open(os.path.join(RESULTS_DIR, f"{which}_{scope}.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    for k, g in res["k_grid"].items():
        runlog.append(which.upper(), f"ratings k={k}", scope, g)
    runlog.append(which.upper(), f"log pool, k={res['k']}", scope,
                  {x: res[x] for x in ("weight", "walk_forward", "model_minus_market",
                                       "blend_minus_market", "bets", "goes_to_holdout")
                   if x in res})


if __name__ == "__main__":
    main()
