"""
KAIROS harness — E1: is there a gap against Pinnacle on venues that allow
automation, after commission? (research/hypotheses.md, E1.)

  E1a  development seasons: bet the Betfair Exchange pre-match price (Football-Data
       column BFE) where it beats Pinnacle's fair price by 3% after commission.
  E1b  the paper loop's stored snapshots: how often each exchange's price in
       The Odds API feed beats Pinnacle's fair price, before and after commission.

    python harness/run_e1.py [--no-log]

Writes research/results/e1_automatable.json and .md. Pure stdlib.
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
import walk

RESULTS_DIR = os.path.join(fd_fetch.ROOT, "research", "results")
SNAPS = os.path.join(fd_fetch.ROOT, "paper", "state", "snapshots.jsonl")
COMMISSIONS = (0.0, 0.02, 0.05)
MIN_EDGE = 0.03
EXCHANGES = {"matchbook": 0.04, "smarkets": 0.02, "betfair_ex_uk": 0.05, "betfair_ex_eu": 0.05}
SOFT_SAMPLE = ("williamhill", "onexbet", "betway")      # for scale, no commission


def net(odds: float, c: float) -> float:
    """Price after commission on winnings."""
    return 1.0 + (odds - 1.0) * (1.0 - c)


class ExchangeBets(walk.Strategy):
    def __init__(self, c: float):
        self.c, self.name = c, f"bfe[{c:.0%} commission]"

    def decide(self, pre) -> walk.Decision:
        d = walk.Decision()
        sharp, ex = pre.odds_1x2.get("PS"), pre.odds_1x2.get("BFE")
        if not sharp or not ex:
            return d
        try:
            fair = score.market.devig_power(list(sharp))
        except ValueError:
            return d
        for i in range(3):
            o = net(ex[i], self.c)
            if o * fair[i] - 1.0 > MIN_EDGE:
                d.bets.append(walk.Bet("1x2", i, o, "BFE", o * fair[i] - 1.0))
        return d


def e1a() -> dict:
    matches = fd_data.load_development()
    both = sum(1 for pre, _ in matches if "PS" in pre.odds_1x2 and "BFE" in pre.odds_1x2)
    sc = score.Scorer()
    strats = [ExchangeBets(c) for c in COMMISSIONS]
    walk.run(matches, strats, sc)
    out = {"matches_with_both_prices": both, "variants": {}}
    for s in strats:
        t = sc.bet_table(s.name, "1x2").get("all") if s.name in sc.bets else None
        out["variants"][s.name] = t and {k: t[k] for k in ("bets", "roi", "roi_ci", "clv", "clv_ci")}
    return out


def e1b() -> dict:
    try:
        with open(SNAPS, encoding="utf-8") as f:
            snaps = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return {"snapshots": 0}
    out = {"snapshots": len(snaps), "books": {}}
    for book, c in {**EXCHANGES, **{b: 0.0 for b in SOFT_SAMPLE}}.items():
        n = gross0 = gross3 = net0 = net3 = 0
        for s in snaps:
            pin, px = s["books"].get("pinnacle"), s["books"].get(book)
            if not pin or not px or len(pin) != 3 or len(px) != 3:
                continue
            try:
                fair = score.market.devig_power(list(pin))
            except ValueError:
                continue
            # snapshot prices are stored in the feed's outcome order, the same for every book
            for o, p in zip(px, fair):
                n += 1
                g, m = o * p - 1.0, net(o, c) * p - 1.0
                gross0 += g > 0
                gross3 += g > MIN_EDGE
                net0 += m > 0
                net3 += m > MIN_EDGE
        out["books"][book] = {"commission": c, "prices": n, "gross_above_0": gross0,
                              "gross_above_3pct": gross3, "net_above_0": net0, "net_above_3pct": net3}
    return out


def main() -> None:
    res = {"commit": runlog.git_commit(), "E1a": e1a(), "E1b": e1b()}
    os.makedirs(RESULTS_DIR, exist_ok=True)
    with open(os.path.join(RESULTS_DIR, "e1_automatable.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, indent=1, sort_keys=True)
    p = lambda x: "-" if x is None else f"{x * 100:+.1f}%"
    L = ["# E1: gap against Pinnacle on venues that allow automation", "",
         f"Commit {res['commit']}.", "",
         "## E1a: Betfair Exchange pre-match price, development seasons", "",
         f"{res['E1a']['matches_with_both_prices']} matches carry both a Pinnacle and an exchange "
         "pre-match price. Bet where the price after commission beats Pinnacle's fair price by 3%.", "",
         "| Commission | Bets | CLV | 95% interval | Return per bet | 95% interval |", "|---|---|---|---|---|---|"]
    for name, t in res["E1a"]["variants"].items():
        if not t:
            L.append(f"| {name} | 0 | - | - | - | - |")
            continue
        L.append(f"| {name} | {t['bets']} | {p(t['clv'])} | "
                 + ("-" if not t["clv_ci"] else f"{p(t['clv_ci'][0])} to {p(t['clv_ci'][1])}")
                 + f" | {p(t['roi'])} | {p(t['roi_ci'][0])} to {p(t['roi_ci'][1])} |")
    b = res["E1b"]
    L += ["", "## E1b: prices in the paper loop's snapshots", "",
          f"{b['snapshots']} matches snapshotted between 3 and 8 October 2026 (six second-tier leagues). "
          "Counts of single prices beating Pinnacle's fair price. No liquidity information: an exchange "
          "price in the feed may have very little money behind it.", "",
          "| Book | Commission assumed | Prices | Above fair | Above fair by 3% | Above fair after commission | By 3% after commission |",
          "|---|---|---|---|---|---|---|"]
    for book, r in b.get("books", {}).items():
        L.append(f"| {book} | {r['commission'] * 100:.0f}% | {r['prices']} | {r['gross_above_0']} | "
                 f"{r['gross_above_3pct']} | {r['net_above_0']} | {r['net_above_3pct']} |")
    text = "\n".join(L) + "\n"
    with open(os.path.join(RESULTS_DIR, "e1_automatable.md"), "w", encoding="utf-8") as f:
        f.write(text)
    print(text)
    if "--no-log" not in sys.argv:
        runlog.append("E1", "E1a", "development league-seasons only", res["E1a"])
        runlog.append("E1", "E1b", "paper snapshots 2026-10-03 to 2026-10-08", res["E1b"])


if __name__ == "__main__":
    main()
