"""
KAIROS harness — scorer.

Collects every strategy's forecasts and bets as the walk goes, settles them
against Post, and summarises them overall, per league and per season.

Closing-line value is measured against Pinnacle's closing price with the margin
removed: CLV = price taken x fair closing probability - 1. The power method is
the primary de-vig (it is what Kairos uses); the proportional method is recorded
next to it so a result that depends on the de-vig choice is visible.

The closing price is also scored as a forecast. It is a reference bar, not a
strategy: nobody can bet at Friday's price knowing Sunday's closing price.

Pure stdlib.
"""

from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "engine"))
import market   # noqa: E402

import metrics  # noqa: E402

SHARP = "PS"
CLOSE_REF = "reference: Pinnacle closing"


def outcome_index(mkt: str, post) -> int:
    if mkt == "1x2":
        return "HDA".index(post.ftr)
    return 0 if post.fthg + post.ftag > 2 else 1        # over 2.5, under 2.5


def fair_close(mkt: str, post, method: str = "power") -> list[float] | None:
    v = (post.close_1x2 if mkt == "1x2" else post.close_ou25).get(SHARP)
    if not v:
        return None
    return market.devig_power(list(v)) if method == "power" else market.devig_proportional(list(v))


class Scorer:
    def __init__(self):
        self.forecasts: dict = {}     # name -> market -> {key: (probs, outcome, league, season)}
        self.bets: dict = {}          # name -> list of settled bet dicts
        self._closed: set = set()

    def __call__(self, strategy, pre, post, decision) -> None:
        name = strategy.name
        for mkt, probs in decision.forecasts.items():
            self.forecasts.setdefault(name, {}).setdefault(mkt, {})[pre.key] = (
                tuple(probs), outcome_index(mkt, post), pre.league, pre.season)
        for bet in decision.bets:
            won = outcome_index(bet.market, post) == bet.selection
            fc, fcp = fair_close(bet.market, post), fair_close(bet.market, post, "proportional")
            self.bets.setdefault(name, []).append({
                "cluster": pre.key, "league": pre.league, "season": pre.season,
                "market": bet.market, "selection": bet.selection, "odds": bet.odds,
                "book": bet.book, "stake": bet.stake, "claimed_ev": bet.claimed_ev,
                "profit": bet.stake * (bet.odds - 1.0) if won else -bet.stake,
                "clv": bet.odds * fc[bet.selection] - 1.0 if fc else None,
                "clv_prop": bet.odds * fcp[bet.selection] - 1.0 if fcp else None,
                **dict(bet.tags),
            })
        if pre.key not in self._closed:
            self._closed.add(pre.key)
            for mkt in ("1x2", "ou25"):
                fc = fair_close(mkt, post)
                if fc:
                    self.forecasts.setdefault(CLOSE_REF, {}).setdefault(mkt, {})[pre.key] = (
                        tuple(fc), outcome_index(mkt, post), pre.league, pre.season)

    # ── summaries ────────────────────────────────────────────────────────────

    def forecast_table(self, name: str, mkt: str, by: str | None = None,
                       keys: set | None = None) -> dict:
        """Forecast scores, optionally split by 'league' or 'season', optionally on a key set."""
        recs = self.forecasts.get(name, {}).get(mkt, {})
        groups: dict = {}
        for k, (probs, out, league, season) in recs.items():
            if keys is not None and k not in keys:
                continue
            g = "all" if by is None else (league if by == "league" else season)
            groups.setdefault(g, []).append((probs, out))
        return {g: metrics.forecast_summary(r) for g, r in sorted(groups.items())}

    def common_keys(self, names: list[str], mkt: str) -> set:
        sets = [set(self.forecasts.get(n, {}).get(mkt, {})) for n in names]
        return set.intersection(*sets) if sets else set()

    def paired_log_loss(self, a: str, b: str, mkt: str, keys: set) -> dict:
        """Mean log loss of a minus b on the same matches (negative = a is better)."""
        fa, fb = self.forecasts[a][mkt], self.forecasts[b][mkt]
        ks = sorted(keys)
        return metrics.paired_diff([metrics.log_loss(*fa[k][:2]) for k in ks],
                                   [metrics.log_loss(*fb[k][:2]) for k in ks])

    def bet_table(self, name: str, mkt: str | None = None, by: str | None = None,
                  clv_key: str = "clv", **kw) -> dict:
        groups: dict = {}
        for b in self.bets.get(name, []):
            if mkt and b["market"] != mkt:
                continue
            g = "all" if by is None else b[by]
            groups.setdefault(g, []).append(dict(b, clv=b[clv_key]))
        return {g: metrics.bet_summary(bs, **kw) for g, bs in sorted(groups.items())}
