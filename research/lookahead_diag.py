"""Phase 0 audit diagnostic (research script, not part of the engine).

Run: python research/lookahead_diag.py   (needs fd_<league>_<season>.csv files in engine/fixtures)

Reads the cached football-data CSVs and compares:
  A) the repo backtest rule: select with Pinnacle CLOSING fair price, bet at Bet365 pre-match
  B) the same rule without look-ahead: select with Pinnacle PRE-MATCH fair price
Reports ROI and de-vigged CLV with match-clustered bootstrap 95% intervals.
"""
import csv, glob, os, random, sys

ENG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "engine")
sys.path.insert(0, ENG)
import market

RES = ("H", "D", "A")


def odds(row, cols):
    try:
        v = [float(row[c]) for c in cols]
    except (KeyError, ValueError, TypeError):
        return None
    return v if all(o > 1.0 for o in v) else None


def load():
    rows = []
    for p in sorted(glob.glob(os.path.join(ENG, "fixtures", "fd_*_*.csv"))):
        tag = os.path.basename(p)[3:-4]
        with open(p, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("FTR"):
                    r["_tag"] = tag
                    rows.append(r)
    return rows


def bets_for(rows, select_cols, thr):
    """Return per-match list of (profit, clv_devig, raw_ratio) tuples."""
    per_match = []
    counts = {"usable": 0, "b365_missing": 0, "multi": 0}
    for r in rows:
        soft = odds(r, ("B365H", "B365D", "B365A"))
        sel = odds(r, select_cols)
        close = odds(r, ("PSCH", "PSCD", "PSCA"))
        if not soft:
            counts["b365_missing"] += 1
        if not soft or not sel or not close:
            continue
        counts["usable"] += 1
        fair_sel = market.devig_power(sel)
        fair_close = market.devig_power(close)
        mb = []
        for k, res in enumerate(RES):
            if soft[k] * fair_sel[k] - 1.0 > thr:
                profit = soft[k] - 1.0 if r["FTR"] == res else -1.0
                mb.append((profit, soft[k] * fair_close[k] - 1.0, soft[k] / close[k] - 1.0))
        if len(mb) > 1:
            counts["multi"] += 1
        if mb:
            per_match.append(mb)
    return per_match, counts


def summarise(per_match, n_boot=4000, seed=11):
    flat = [b for m in per_match for b in m]
    n = len(flat)
    if not n:
        return None
    roi = sum(b[0] for b in flat) / n
    clv = sum(b[1] for b in flat) / n
    raw = sum(b[2] for b in flat) / n
    rng = random.Random(seed)
    rois, clvs = [], []
    M = len(per_match)
    for _ in range(n_boot):
        s = c = cnt = 0.0
        for _ in range(M):
            m = per_match[rng.randrange(M)]
            for b in m:
                s += b[0]; c += b[1]; cnt += 1
        rois.append(s / cnt); clvs.append(c / cnt)
    rois.sort(); clvs.sort()
    lo, hi = int(0.025 * n_boot), int(0.975 * n_boot) - 1
    return dict(bets=n, matches=M, roi=roi, roi_ci=(rois[lo], rois[hi]),
                clv=clv, clv_ci=(clvs[lo], clvs[hi]), raw_ratio=raw,
                profit=sum(b[0] for b in flat))


def line(name, s):
    if not s:
        print(f"  {name:<34} no bets"); return
    print(f"  {name:<34} bets {s['bets']:>4}  profit {s['profit']:>+8.2f}u  "
          f"ROI {s['roi']*100:>+6.1f}% [{s['roi_ci'][0]*100:+.1f}, {s['roi_ci'][1]*100:+.1f}]  "
          f"CLV(devig) {s['clv']*100:>+5.1f}% [{s['clv_ci'][0]*100:+.1f}, {s['clv_ci'][1]*100:+.1f}]  "
          f"repo-'CLV' {s['raw_ratio']*100:>+5.1f}%")


rows = load()
tags = sorted({r["_tag"] for r in rows})
print(f"matches loaded: {len(rows)} from {len(tags)} league-seasons: {', '.join(tags)}")
for thr in (0.0, 0.02, 0.05):
    print(f"\n== threshold EV > {thr*100:.0f}% (pooled) ==")
    a, ca = bets_for(rows, ("PSCH", "PSCD", "PSCA"), thr)
    b, cb = bets_for(rows, ("PSH", "PSD", "PSA"), thr)
    line("A select on Pinnacle CLOSING", summarise(a))
    line("B select on Pinnacle PRE-MATCH", summarise(b))
    if thr == 0.02:
        print(f"  usable A {ca['usable']}  usable B {cb['usable']}  B365 missing {ca['b365_missing']}  "
              f"matches with >1 outcome bet: A {ca['multi']}  B {cb['multi']}")

print("\n== per league-season at EV > 2% ==")
for t in tags:
    sub = [r for r in rows if r["_tag"] == t]
    a, _ = bets_for(sub, ("PSCH", "PSCD", "PSCA"), 0.02)
    b, _ = bets_for(sub, ("PSH", "PSD", "PSA"), 0.02)
    sa, sb = summarise(a, 500), summarise(b, 500)
    fa = f"{sa['bets']:>4} bets {sa['roi']*100:>+6.1f}%" if sa else "   0 bets"
    fb = f"{sb['bets']:>4} bets {sb['roi']*100:>+6.1f}% CLV {sb['clv']*100:>+5.1f}%" if sb else "   0 bets"
    print(f"  {t:<9} A: {fa}   B: {fb}")

# How far is Bet365 from Pinnacle at the same snapshot vs at close?
import statistics
m_b365, m_ps, m_psc = [], [], []
for r in rows:
    for cols, acc in ((("B365H", "B365D", "B365A"), m_b365), (("PSH", "PSD", "PSA"), m_ps),
                      (("PSCH", "PSCD", "PSCA"), m_psc)):
        o = odds(r, cols)
        if o:
            acc.append(sum(1 / x for x in o) - 1)
print(f"\nmean overround: Bet365 {statistics.mean(m_b365)*100:.2f}%  Pinnacle pre {statistics.mean(m_ps)*100:.2f}%  "
      f"Pinnacle close {statistics.mean(m_psc)*100:.2f}%")
