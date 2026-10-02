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

import os
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


class MarketForecast(Strategy):
    """A bookmaker's pre-match price, de-vigged, as a forecast. Never bets."""

    def __init__(self, book: str, method: str = "proportional", markets=("1x2", "ou25")):
        self.book, self.method, self.markets = book, method, markets
        self.name = f"market[{book},{method}]"

    def decide(self, pre) -> Decision:
        d = Decision()
        for mkt in self.markets:
            v = (pre.odds_1x2 if mkt == "1x2" else pre.odds_ou25).get(self.book)
            if v:
                fn = market.devig_power if self.method == "power" else market.devig_proportional
                d.forecasts[mkt] = tuple(fn(list(v)))
        return d
