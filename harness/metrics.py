"""
KAIROS harness — metrics. Nothing in this file knows about football.

Forecast quality (lower is better for all three):
  log loss   -ln(probability given to what happened)
  Brier      sum over outcomes of (probability - happened)^2, range 0..2
  RPS        ranked probability score for ordered outcomes, range 0..1

Betting:
  return per bet   profit / amount staked
  CLV              price taken x fair closing probability - 1

Intervals for betting figures are bootstrap percentile intervals that resample
whole clusters (matches), because bets on the same match are not independent.
Intervals for forecast scores use the normal approximation on per-match scores,
which is accurate at the sample sizes here and keeps the run fast.

Pure stdlib.
"""

from __future__ import annotations

import math
import random

EPS = 1e-12


# ── per-forecast scores ──────────────────────────────────────────────────────

def log_loss(probs, outcome: int) -> float:
    return -math.log(max(probs[outcome], EPS))


def brier(probs, outcome: int) -> float:
    return sum((p - (1.0 if i == outcome else 0.0)) ** 2 for i, p in enumerate(probs))


def rps(probs, outcome: int) -> float:
    n = len(probs)
    if n < 2:
        return 0.0
    cum_p = cum_o = total = 0.0
    for i in range(n - 1):
        cum_p += probs[i]
        cum_o += 1.0 if i == outcome else 0.0
        total += (cum_p - cum_o) ** 2
    return total / (n - 1)


def mean_se(values: list[float]) -> tuple[float, float]:
    n = len(values)
    if n == 0:
        return float("nan"), float("nan")
    m = sum(values) / n
    if n == 1:
        return m, float("nan")
    var = sum((v - m) ** 2 for v in values) / (n - 1)
    return m, math.sqrt(var / n)


def calibration_buckets(pairs: list[tuple[float, int]], width: float = 0.1) -> list[dict]:
    """pairs = (probability, 1 if it happened else 0) for every outcome of every match."""
    k = int(round(1.0 / width))
    acc = [[0, 0.0, 0] for _ in range(k)]
    for p, hit in pairs:
        b = min(k - 1, int(p * k + 1e-9))
        acc[b][0] += 1
        acc[b][1] += p
        acc[b][2] += hit
    out = []
    for b, (n, sp, sh) in enumerate(acc):
        if n:
            out.append({"bucket": f"{b * width:.1f}-{(b + 1) * width:.1f}", "n": n,
                        "mean_prob": sp / n, "observed": sh / n,
                        "gap": sh / n - sp / n})
    return out


def expected_calibration_error(buckets: list[dict]) -> float:
    n = sum(b["n"] for b in buckets)
    return sum(b["n"] * abs(b["gap"]) for b in buckets) / n if n else float("nan")


def forecast_summary(records: list[tuple[tuple, int]]) -> dict | None:
    """records = (probabilities, index of what happened)."""
    if not records:
        return None
    ll = [log_loss(p, o) for p, o in records]
    br = [brier(p, o) for p, o in records]
    rp = [rps(p, o) for p, o in records]
    pairs = [(p, 1 if i == o else 0) for probs, o in records for i, p in enumerate(probs)]
    buckets = calibration_buckets(pairs)
    ll_m, ll_se = mean_se(ll)
    br_m, br_se = mean_se(br)
    return {"n": len(records), "log_loss": ll_m, "log_loss_se": ll_se,
            "brier": br_m, "brier_se": br_se, "rps": mean_se(rp)[0],
            "ece": expected_calibration_error(buckets), "buckets": buckets}


def paired_diff(a: list[float], b: list[float]) -> dict:
    """Mean of a-b on the same matches, with standard error and a 95% interval."""
    d = [x - y for x, y in zip(a, b)]
    m, se = mean_se(d)
    return {"n": len(d), "mean": m, "se": se, "lo": m - 1.96 * se, "hi": m + 1.96 * se}


# ── betting ──────────────────────────────────────────────────────────────────

def _percentile_interval(samples: list[float], level: float = 0.95) -> tuple[float, float]:
    s = sorted(samples)
    lo = int((1 - level) / 2 * len(s))
    hi = min(len(s) - 1, int((1 + level) / 2 * len(s)) - 1)
    return s[lo], s[hi]


def bet_summary(bets: list[dict], n_boot: int = 2000, seed: int = 11,
                max_draws: int = 40_000_000) -> dict | None:
    """
    bets: dicts with cluster, stake, profit, clv (None when no closing price).

    Returns counts, return per bet and mean CLV, each with a 95% interval from
    resampling clusters with replacement.
    """
    if not bets:
        return None
    clusters: dict = {}
    for b in bets:
        c = clusters.setdefault(b["cluster"], [0.0, 0.0, 0.0, 0])
        c[0] += b["profit"]
        c[1] += b["stake"]
        if b["clv"] is not None:
            c[2] += b["clv"]
            c[3] += 1
    prof = [c[0] for c in clusters.values()]
    stak = [c[1] for c in clusters.values()]
    clvs = [c[2] for c in clusters.values()]
    clvn = [c[3] for c in clusters.values()]
    m = len(prof)
    n_clv = sum(clvn)
    out = {"bets": len(bets), "clusters": m, "staked": sum(stak), "profit": sum(prof),
           "wins": sum(1 for b in bets if b["profit"] > 0),
           "roi": sum(prof) / sum(stak),
           "clv": sum(clvs) / n_clv if n_clv else None, "clv_n": n_clv,
           "mean_odds": sum(b["odds"] for b in bets) / len(bets)}
    n_boot = max(200, min(n_boot, max_draws // m))
    rng = random.Random(seed)
    idx_range = range(m)
    rois, cl = [], []
    for _ in range(n_boot):
        idx = rng.choices(idx_range, k=m)
        s = sum(map(stak.__getitem__, idx))
        rois.append(sum(map(prof.__getitem__, idx)) / s)
        if n_clv:
            n = sum(map(clvn.__getitem__, idx))
            if n:
                cl.append(sum(map(clvs.__getitem__, idx)) / n)
    out["roi_ci"] = _percentile_interval(rois)
    out["clv_ci"] = _percentile_interval(cl) if cl else None
    out["n_boot"] = n_boot
    return out
