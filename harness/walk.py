"""
KAIROS harness — walk-forward runner.

The rule: a decision for a match may use nothing dated on or after the day its
odds were collected. Football-Data collects prices on Friday afternoon for
Friday-to-Monday games and on Tuesday afternoon for Tuesday-to-Thursday games,
so matches are grouped into collection windows. For each window, in date order:

  1. every strategy decides every match in the window, seeing PreMatch only;
  2. the decisions are scored against Post;
  3. only then is each (PreMatch, Post) pair shown to the strategies.

So when a strategy decides a Sunday match it has not seen Saturday's results,
because the price it is betting at was collected on Friday. This is stricter
than "nothing after kickoff".

Pure stdlib. Nothing here is football-specific except collection_cutoff().
"""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Bet:
    market: str          # "1x2" or "ou25"
    selection: int       # index into the market's outcomes
    odds: float          # price taken
    book: str            # where the price came from
    claimed_ev: float    # what the strategy believed the edge was
    stake: float = 1.0
    tags: tuple = ()     # (name, value) pairs copied onto the settled bet record


@dataclass
class Decision:
    forecasts: dict = field(default_factory=dict)   # market -> tuple of probabilities
    bets: list = field(default_factory=list)


class Strategy:
    """Subclass and override decide(); override observe() to learn from results."""

    name = "strategy"

    def decide(self, pre) -> Decision:              # pragma: no cover - interface
        raise NotImplementedError

    def observe(self, pre, post) -> None:
        pass


def collection_cutoff(date: dt.date) -> dt.date:
    """The Friday (Fri-Mon games) or Tuesday (Tue-Thu games) the odds were collected."""
    wd = date.weekday()                 # Monday = 0
    back = {4: 0, 5: 1, 6: 2, 0: 3, 1: 0, 2: 1, 3: 2}[wd]
    return date - dt.timedelta(days=back)


def windows(matches: list) -> list[tuple[dt.date, list]]:
    """Group (PreMatch, Post) pairs into collection windows, oldest first."""
    groups: dict[dt.date, list] = {}
    for pre, post in matches:
        groups.setdefault(collection_cutoff(pre.date), []).append((pre, post))
    out = []
    for cutoff in sorted(groups):
        out.append((cutoff, sorted(groups[cutoff], key=lambda m: (m[0].date, m[0].key))))
    return out


def run(matches: list, strategies: list, on_decision) -> None:
    """
    Walk forward. on_decision(strategy, pre, post, decision) is called once per
    strategy per match, after the whole window has been decided.
    """
    for _cutoff, group in windows(matches):
        decided = [[s.decide(pre) for pre, _post in group] for s in strategies]
        for s, decisions in zip(strategies, decided):
            for (pre, post), d in zip(group, decisions):
                on_decision(s, pre, post, d)
        for s in strategies:
            for pre, post in group:
                s.observe(pre, post)


def decisions_of(matches: list, strategy) -> dict:
    """Run one strategy and return {match key: (forecasts, bets)} for comparison."""
    out = {}

    def keep(_s, pre, _post, d):
        out[pre.key] = (dict(d.forecasts), list(d.bets))

    run(matches, [strategy], keep)
    return out


def leak_check(matches: list, make_strategy, n_cuts: int = 5) -> list[str]:
    """
    Truncation test for any strategy, including ones that learn from results.

    make_strategy(matches) builds a fresh strategy and is handed the same
    history the run is given, so a strategy that fits anything up front (ratings,
    league averages, tuned parameters) fits it on that history.

    The strategy is run on the full history, then again on histories cut off
    after chosen windows. A decision that changes when later matches are removed
    has used the future. Returns the keys of matches whose decisions differ
    (empty list = no leak found at these cut points).
    """
    wins = windows(matches)
    if not wins:
        return []
    full = decisions_of(matches, make_strategy(matches))
    step = max(1, len(wins) // (n_cuts + 1))
    bad = []
    for i in range(step, len(wins), step):
        upto = [m for _c, g in wins[: i + 1] for m in g]
        part = decisions_of(upto, make_strategy(upto))
        bad.extend(k for k, d in part.items() if d != full[k])
    return sorted(set(bad))
