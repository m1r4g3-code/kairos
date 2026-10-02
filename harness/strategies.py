"""
KAIROS harness — strategies under test.

KairosV2 is the baseline. It calls the shipped engine code (edge.sharp_fair and
edge.value_vs_sharp) so the backtest measures what Kairos actually does today:
de-vig Pinnacle with the power method, bet where a soft price pays more than
that fair price by the threshold, one unit flat.

MarketForecast emits a de-vigged bookmaker price as a forecast and never bets.
It exists so the baseline's probabilities can be compared with a plain soft-book
or market-average reading on the same matches.

Pure stdlib.
"""

from __future__ import annotations

import math
import os
import statistics
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "engine"))
import config   # noqa: E402
import edge     # noqa: E402
import market   # noqa: E402

import fd_data  # noqa: E402
from walk import Bet, Decision, Strategy  # noqa: E402

LABELS = {"1x2": ("home", "draw", "away"), "ou25": ("over", "under")}
SHARP = fd_data.SHARP
NOT_SOFT = set(fd_data.AGGREGATES) | set(fd_data.EXCHANGES) | {SHARP}


def soft_books(odds: dict) -> dict:
    """Named bookmakers only: no Pinnacle, no exchange, no max/average columns."""
    return {b: v for b, v in odds.items() if b not in NOT_SOFT}


class KairosV2(Strategy):
    """
    soft = a column prefix such as "B365" (one bookmaker, like the owner's one
    SportyBet account) or "BEST" (the best price among all named soft books).
    """

    def __init__(self, soft: str = "B365", min_edge: float = config.MIN_EDGE,
                 markets: tuple = ("1x2", "ou25"), name: str | None = None):
        self.soft, self.min_edge, self.markets = soft, min_edge, markets
        self.name = name or f"kairos_v2[{soft},{min_edge:.0%}]"

    def _soft_prices(self, odds: dict, n: int):
        """Per selection: (price, book) or None."""
        if self.soft != "BEST":
            v = odds.get(self.soft)
            return [(p, self.soft) for p in v] if v else None
        books = soft_books(odds)
        if not books:
            return None
        return [max((v[i], b) for b, v in books.items()) for i in range(n)]

    def decide(self, pre) -> Decision:
        d = Decision()
        for mkt in self.markets:
            odds = pre.odds_1x2 if mkt == "1x2" else pre.odds_ou25
            sharp = odds.get(SHARP)
            if not sharp:
                continue
            labels = LABELS[mkt]
            sf = edge.sharp_fair({"pinnacle": dict(zip(labels, sharp))})
            fair = sf["fair_prob"]
            d.forecasts[mkt] = tuple(fair[k] for k in labels)
            soft = self._soft_prices(odds, len(labels))
            if not soft:
                continue
            sb = {k: soft[i][0] for i, k in enumerate(labels)}
            for row in edge.value_vs_sharp(sb, fair, min_edge=self.min_edge):
                if row["value"]:
                    i = labels.index(row["selection"])
                    d.bets.append(Bet(mkt, i, soft[i][0], soft[i][1],
                                      soft[i][0] * fair[row["selection"]] - 1.0))
        return d


MIN_OTHERS = 3


def others_median(odds: dict, exclude: str) -> tuple | None:
    """
    Median fair probability per selection across the named soft books other than
    `exclude`, each de-vigged by the power method. None with fewer than MIN_OTHERS.
    """
    books = [v for b, v in soft_books(odds).items() if b != exclude]
    if len(books) < MIN_OTHERS:
        return None
    fair = [market.devig_power(list(v)) for v in books]
    return tuple(statistics.median(f[i] for f in fair) for i in range(len(fair[0])))


class KairosV2Checked(KairosV2):
    """
    Proposal A1. The baseline's 1X2 bets, each tagged with how far Pinnacle stands
    from the other bookmakers on that selection:
        gap = Pinnacle fair probability / others' median fair probability - 1
    With max_gap set, a bet whose gap exceeds it is skipped. With max_gap None
    every bet is kept and only tagged, so the gate can be studied.
    """

    def __init__(self, soft: str = "B365", min_edge: float = config.MIN_EDGE,
                 max_gap: float | None = None, name: str | None = None):
        super().__init__(soft, min_edge, markets=("1x2",), name=name or (
            f"kairos_v2_checked[{soft},{min_edge:.0%},gap<="
            + ("any" if max_gap is None else f"{max_gap:.0%}") + "]"))
        self.max_gap = max_gap

    def decide(self, pre) -> Decision:
        d = super().decide(pre)
        if not d.bets:
            return d
        med = others_median(pre.odds_1x2, exclude=self.soft)
        fair = d.forecasts["1x2"]
        kept = []
        for b in d.bets:
            gap = None if med is None else fair[b.selection] / med[b.selection] - 1.0
            if self.max_gap is not None and gap is not None and gap > self.max_gap:
                continue
            kept.append(Bet(b.market, b.selection, b.odds, b.book, b.claimed_ev,
                            b.stake, (("gap", gap),)))
        d.bets = kept
        return d


class OthersMedian(Strategy):
    """Forecast: the other soft books' median fair probability, renormalised."""

    def __init__(self, exclude: str = "B365"):
        self.exclude, self.name = exclude, f"others_median[excl {exclude}]"

    def decide(self, pre) -> Decision:
        d = Decision()
        med = others_median(pre.odds_1x2, self.exclude)
        if med and SHARP in pre.odds_1x2:
            t = sum(med)
            d.forecasts["1x2"] = tuple(p / t for p in med)
        return d


class CheckedBlend(Strategy):
    """
    Forecast: Pinnacle's fair probabilities, except when any selection's gap to
    the others' median is beyond +/- r; then the normalised geometric mean of the
    two. Only on matches with enough other books.
    """

    def __init__(self, r: float, exclude: str = "B365"):
        self.r, self.exclude, self.name = r, exclude, f"checked_blend[r={r:.0%}]"

    def decide(self, pre) -> Decision:
        d = Decision()
        sharp = pre.odds_1x2.get(SHARP)
        med = others_median(pre.odds_1x2, self.exclude)
        if not sharp or not med:
            return d
        sf = edge.sharp_fair({"pinnacle": dict(zip(LABELS["1x2"], sharp))})["fair_prob"]
        fair = tuple(sf[k] for k in LABELS["1x2"])
        if any(abs(f / m - 1.0) > self.r for f, m in zip(fair, med)):
            geo = [math.sqrt(f * m) for f, m in zip(fair, med)]
            t = sum(geo)
            fair = tuple(g / t for g in geo)
        d.forecasts["1x2"] = fair
        return d


class MarketForecast(Strategy):
    """A bookmaker's pre-match price, de-vigged, as a forecast. Never bets."""

    def __init__(self, books, method: str = "proportional", markets=("1x2", "ou25")):
        # books: one column prefix, or several to try in order (Avg, then the older BbAv)
        self.books = (books,) if isinstance(books, str) else tuple(books)
        self.method, self.markets = method, markets
        self.name = f"market[{self.books[0]},{method}]"

    def decide(self, pre) -> Decision:
        d = Decision()
        for mkt in self.markets:
            odds = pre.odds_1x2 if mkt == "1x2" else pre.odds_ou25
            v = next((odds[b] for b in self.books if b in odds), None)
            if v:
                fn = market.devig_power if self.method == "power" else market.devig_proportional
                d.forecasts[mkt] = tuple(fn(list(v)))
        return d
