"""
KAIROS harness — baseline run (hypotheses B0, R1, S1, S2 in research/hypotheses.md).

Walks every development league-season on disk, scores the shipped Kairos v2
strategy and the registered reference and sensitivity variants, runs the
leakage audit on the real data, and writes:

    research/results/baseline.json        every number, machine-readable
    research/results/baseline_tables.md   the same numbers as tables
    research/runs.jsonl                   one appended line per variant

Holdout league-seasons are never loaded.

CLI:  python harness/run_baseline.py [--no-log]

Pure stdlib.
"""

from __future__ import annotations

import json
import os
import random
import sys
import time

import fd_data
import fd_fetch
import runlog
import score
import strategies
import walk

RESULTS_DIR = os.path.join(fd_fetch.ROOT, "research", "results")
MARKETS = ("1x2", "ou25")
MARKET_NAMES = {"1x2": "1X2", "ou25": "Over/under 2.5"}
PHASE0 = {f"{lg}_{s}" for lg in ("E0", "SP1", "D1", "I1", "F1") for s in ("2324", "2425")}

B0 = strategies.KairosV2("B365", 0.03)
S1 = [strategies.KairosV2("B365", t) for t in (0.0, 0.02, 0.05)]
S2 = [strategies.KairosV2("BEST", t) for t in (0.0, 0.02, 0.03, 0.05)]
R1 = [strategies.MarketForecast("B365"), strategies.MarketForecast(("Avg", "BbAv"))]
HYPOTHESIS = {B0.name: "B0", **{s.name: "S1" for s in S1}, **{s.name: "S2" for s in S2},
              **{s.name: "R1" for s in R1}, score.CLOSE_REF: "R1"}


def pct(x, digits=1):
    return "-" if x is None else f"{x * 100:+.{digits}f}%"


def ci(pair, digits=1):
    return "-" if not pair else f"{pair[0] * 100:+.{digits}f} to {pair[1] * 100:+.{digits}f}"


def coverage(matches) -> dict:
    out: dict = {}
    for pre, post in matches:
        c = out.setdefault(pre.league, {"matches": 0, "seasons": set(), "ps_pre": 0,
                                        "ps_close": 0, "b365": 0, "ps_ou": 0, "ps_ou_close": 0,
                                        "ps_seasons": set()})
        c["matches"] += 1
        c["seasons"].add(pre.season)
        if "PS" in pre.odds_1x2:
            c["ps_pre"] += 1
            c["ps_seasons"].add(pre.season)
        c["ps_close"] += "PS" in pre.odds_1x2 and "PS" in post.close_1x2
        c["b365"] += "B365" in pre.odds_1x2
        c["ps_ou"] += "PS" in pre.odds_ou25
        c["ps_ou_close"] += "PS" in pre.odds_ou25 and "PS" in post.close_ou25
    for c in out.values():
        for k in ("seasons", "ps_seasons"):
            ss = sorted(c[k], key=fd_fetch.season_start_year)
            c[k] = {"n": len(ss), "first": ss[0] if ss else None, "last": ss[-1] if ss else None}
    return out


def leak_audit(matches, strategy_factories) -> dict:
    """Three checks on the real development data."""
    # 1. Scramble everything a strategy must not see; decisions must not move.
    rng = random.Random(5)
    posts = [post for _pre, post in matches]
    rng.shuffle(posts)
    scrambled = [(pre, fd_data.Post(pre.key, p.fthg, p.ftag, p.ftr, p.close_1x2,
                                    p.close_ou25, p.stats))
                 for (pre, _), p in zip(matches, posts)]
    changed = 0
    for make in strategy_factories:
        a, b = walk.decisions_of(matches, make(matches)), walk.decisions_of(scrambled, make(scrambled))
        changed += sum(1 for k in a if a[k] != b[k])
    # 2. Truncation test.
    truncated = sum(len(walk.leak_check(matches, make, n_cuts=4)) for make in strategy_factories)
    # 3. Order: no result dated on or after a collection day is observed before it.
    violations, seen_max = 0, None
    for cutoff, group in walk.windows(matches):
        if seen_max is not None and seen_max >= cutoff:
            violations += 1
        seen_max = max(pre.date for pre, _ in group)
    return {"matches": len(matches), "strategies": len(strategy_factories),
            "decisions_changed_by_scrambling_results_and_closing_prices": changed,
            "decisions_changed_by_truncating_history": truncated,
            "windows_with_an_earlier_result_dated_on_or_after_cutoff": violations}


def slim(summary: dict | None) -> dict | None:
    """Drop bucket detail from a forecast summary for per-league rows."""
    if summary is None:
        return None
    return {k: v for k, v in summary.items() if k != "buckets"}


def main() -> None:
    t0 = time.time()
    matches = fd_data.load_development()
    strats = [B0, *S1, *S2, *R1]
    sc = score.Scorer()
    walk.run(matches, strats, sc)
    print(f"walked {len(matches)} matches in {time.time() - t0:.0f}s", flush=True)

    res: dict = {"scope": "development league-seasons only (research/holdout.json)",
                 "matches": len(matches), "coverage": coverage(matches), "commit": runlog.git_commit()}

    # ── B0 betting ──
    res["B0"] = {"name": B0.name, "bets": {}, "forecast": {}}
    for mkt in MARKETS:
        res["B0"]["bets"][mkt] = {
            "all": sc.bet_table(B0.name, mkt).get("all"),
            "all_clv_proportional": sc.bet_table(B0.name, mkt, clv_key="clv_prop").get("all"),
            "by_league": sc.bet_table(B0.name, mkt, by="league"),
            "by_season": sc.bet_table(B0.name, mkt, by="season"),
        }
        res["B0"]["forecast"][mkt] = {
            "all": sc.forecast_table(B0.name, mkt).get("all"),
            "by_league": {k: slim(v) for k, v in sc.forecast_table(B0.name, mkt, by="league").items()},
            "by_season": {k: slim(v) for k, v in sc.forecast_table(B0.name, mkt, by="season").items()},
        }
    res["B0"]["bets"]["both"] = {"all": sc.bet_table(B0.name).get("all")}

    # ── reference forecasts on the matches every forecaster covers ──
    res["R1"] = {}
    names = [B0.name, *(s.name for s in R1), score.CLOSE_REF]
    for mkt in MARKETS:
        keys = sc.common_keys(names, mkt)
        rows = {}
        for n in names:
            rows[n] = slim(sc.forecast_table(n, mkt, keys=keys).get("all"))
            if n != B0.name and keys:
                rows[n]["log_loss_minus_baseline"] = sc.paired_log_loss(n, B0.name, mkt, keys)
        res["R1"][mkt] = {"common_matches": len(keys), "forecasters": rows,
                          "closing_buckets": (sc.forecast_table(score.CLOSE_REF, mkt, keys=keys)
                                              .get("all") or {}).get("buckets")}

    # ── sensitivity variants ──
    res["variants"] = {}
    for s in [*S1, B0, *S2]:
        res["variants"][s.name] = {mkt: sc.bet_table(s.name, mkt).get("all") for mkt in MARKETS}
    best3 = S2[2].name
    res["S2_by_season"] = {mkt: sc.bet_table(best3, mkt, by="season") for mkt in MARKETS}
    res["S2_books"] = {}
    for b in sc.bets.get(best3, []):
        res["S2_books"][b["book"]] = res["S2_books"].get(b["book"], 0) + 1

    # ── Phase 0 cross-check: same rule, same ten league-seasons, 1X2, +2% ──
    name2 = S1[1].name
    sub = [dict(b) for b in sc.bets.get(name2, [])
           if b["market"] == "1x2" and f"{b['league']}_{b['season']}" in PHASE0]
    from metrics import bet_summary
    res["phase0_crosscheck"] = bet_summary(sub, n_boot=4000)

    # ── leakage audit on real data ──
    res["leak_audit"] = leak_audit(matches, [lambda _m: strategies.KairosV2("B365", 0.03),
                                             lambda _m: strategies.KairosV2("BEST", 0.0)])
    res["seconds"] = round(time.time() - t0)

    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "baseline.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    with open(os.path.join(RESULTS_DIR, "baseline_tables.md"), "w", encoding="utf-8") as f:
        f.write(tables(res))

    if "--no-log" not in sys.argv:
        for name, by_mkt in res["variants"].items():
            for mkt, s in by_mkt.items():
                runlog.append(HYPOTHESIS[name], f"{name} {mkt}", res["scope"],
                              None if s is None else {k: s[k] for k in
                                                      ("bets", "roi", "roi_ci", "clv", "clv_ci", "clv_n")})
        for mkt in MARKETS:
            for n, r in res["R1"][mkt]["forecasters"].items():
                if r:
                    runlog.append(HYPOTHESIS[n], f"{n} {mkt} forecast", res["scope"],
                                  {"n": r["n"], "log_loss": r["log_loss"], "brier": r["brier"]})
    print(f"done in {res['seconds']}s; wrote research/results/baseline.json and baseline_tables.md")


# ── markdown ─────────────────────────────────────────────────────────────────

def bet_row(label: str, s: dict | None) -> str:
    if not s:
        return f"| {label} | 0 | - | - | - | - | - |"
    return (f"| {label} | {s['bets']} | {pct(s['roi'])} | {ci(s['roi_ci'])} | "
            f"{pct(s['clv'])} | {ci(s['clv_ci'])} | {s['mean_odds']:.2f} |")


BET_HEAD = ("| | Bets | Return per bet | 95% interval | CLV | 95% interval | Mean odds |\n"
            "|---|---|---|---|---|---|---|")


def fc_row(label: str, s: dict | None) -> str:
    if not s:
        return f"| {label} | 0 | - | - | - | - |"
    return (f"| {label} | {s['n']} | {s['log_loss']:.4f} | {s['brier']:.4f} | "
            f"{s['rps']:.4f} | {s['ece'] * 100:.2f}% |")


FC_HEAD = "| | Matches | Log loss | Brier | RPS | Calibration error |\n|---|---|---|---|---|---|"


def tables(res: dict) -> str:
    L = ["# Baseline tables", "",
         f"Generated by `harness/run_baseline.py` at commit `{res['commit']}`. "
         f"{res['matches']} development matches. Holdout seasons not loaded.", ""]
    L += ["## Coverage", "",
          "| League | Matches | Seasons | Pinnacle pre-match | of which with closing | "
          "Pinnacle seasons | Bet365 | Pinnacle O/U pre-match | of which with closing |",
          "|---|---|---|---|---|---|---|---|---|"]
    tot = [0] * 6
    for lg, c in res["coverage"].items():
        vals = [c["matches"], c["ps_pre"], c["ps_close"], c["b365"], c["ps_ou"], c["ps_ou_close"]]
        tot = [a + b for a, b in zip(tot, vals)]
        L.append(f"| {lg} | {c['matches']} | {c['seasons']['first']}-{c['seasons']['last']} "
                 f"({c['seasons']['n']}) | {c['ps_pre']} | {c['ps_close']} | "
                 f"{c['ps_seasons']['first']}-{c['ps_seasons']['last']} ({c['ps_seasons']['n']}) | "
                 f"{c['b365']} | {c['ps_ou']} | {c['ps_ou_close']} |")
    L.append(f"| **All** | {tot[0]} | | {tot[1]} | {tot[2]} | | {tot[3]} | {tot[4]} | {tot[5]} |")

    for mkt in MARKETS:
        b = res["B0"]["bets"][mkt]
        L += ["", f"## B0 bets, {MARKET_NAMES[mkt]}", "", BET_HEAD, bet_row("**All**", b["all"])]
        if b["all_clv_proportional"]:
            p = b["all_clv_proportional"]
            L.append(f"| All, CLV by proportional de-vig | {p['bets']} | | | {pct(p['clv'])} | "
                     f"{ci(p['clv_ci'])} | |")
        L += [bet_row(k, v) for k, v in b["by_league"].items()]
        L += ["", f"### By season, {MARKET_NAMES[mkt]}", "", BET_HEAD]
        L += [bet_row(k, v) for k, v in sorted(b["by_season"].items(),
                                               key=lambda kv: fd_fetch.season_start_year(kv[0]))]
    L += ["", "## B0 bets, both markets", "", BET_HEAD, bet_row("**All**", res["B0"]["bets"]["both"]["all"])]

    for mkt in MARKETS:
        f = res["B0"]["forecast"][mkt]
        L += ["", f"## B0 forecast (Pinnacle pre-match, power de-vig), {MARKET_NAMES[mkt]}", "",
              FC_HEAD, fc_row("**All**", f["all"])]
        L += [fc_row(k, v) for k, v in f["by_league"].items()]
        L += ["", f"### By season, {MARKET_NAMES[mkt]}", "", FC_HEAD]
        L += [fc_row(k, v) for k, v in sorted(f["by_season"].items(),
                                              key=lambda kv: fd_fetch.season_start_year(kv[0]))]
        if f["all"]:
            L += ["", f"### Calibration buckets, {MARKET_NAMES[mkt]}", "",
                  "| Forecast probability | Outcomes | Mean forecast | Happened | Gap |",
                  "|---|---|---|---|---|"]
            L += [f"| {x['bucket']} | {x['n']} | {x['mean_prob'] * 100:.1f}% | "
                  f"{x['observed'] * 100:.1f}% | {x['gap'] * 100:+.1f} |" for x in f["all"]["buckets"]]

    for mkt in MARKETS:
        r = res["R1"][mkt]
        L += ["", f"## R1 forecast comparison, {MARKET_NAMES[mkt]} "
                  f"({r['common_matches']} matches covered by all)", "",
              "| Forecaster | Log loss | Brier | RPS | Calibration error | "
              "Log loss minus baseline | 95% interval |", "|---|---|---|---|---|---|---|"]
        for n, s in r["forecasters"].items():
            if not s:
                continue
            d = s.get("log_loss_minus_baseline")
            L.append(f"| {n} | {s['log_loss']:.4f} | {s['brier']:.4f} | {s['rps']:.4f} | "
                     f"{s['ece'] * 100:.2f}% | " + (f"{d['mean']:+.4f} | {d['lo']:+.4f} to {d['hi']:+.4f} |"
                                                    if d else "- | - |"))

    for mkt in MARKETS:
        L += ["", f"## S1 and S2 variants, {MARKET_NAMES[mkt]}", "", BET_HEAD]
        L += [bet_row(n, v[mkt]) for n, v in res["variants"].items()]
    for mkt in MARKETS:
        L += ["", f"### S2 best price at +3% by season, {MARKET_NAMES[mkt]}", "", BET_HEAD]
        L += [bet_row(k, v) for k, v in sorted(res["S2_by_season"][mkt].items(),
                                               key=lambda kv: fd_fetch.season_start_year(kv[0]))]
    L += ["", "Books supplying the S2 +3% price: "
          + ", ".join(f"{b} {n}" for b, n in sorted(res["S2_books"].items(), key=lambda kv: -kv[1]))]

    L += ["", "## Phase 0 cross-check (B365 vs Pinnacle pre-match, +2%, 1X2, the ten audited league-seasons)",
          "", BET_HEAD, bet_row("Harness", res["phase0_crosscheck"]),
          "| Phase 0 diagnostic (docs/audit.md 3c) | 31 | -5.9% | -66.0 to +65.3 | -4.4% | -9.8 to +0.3 | |"]
    L += ["", "## Leakage audit on the development data", ""]
    L += [f"- {k.replace('_', ' ')}: {v}" for k, v in res["leak_audit"].items()]
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
