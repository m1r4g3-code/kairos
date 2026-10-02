"""
KAIROS harness — online team ratings (proposals A5 and A6).

One attack and one defence rating per team per league, plus a league base rate
and home advantage, all on a log scale:

    expected home count = exp(base + home_adv + att_home - def_away)
    expected away count = exp(base + att_away - def_home)

After each match every term moves by k x (count - expected count), which is a
gradient step on the Poisson likelihood. League terms move at k / 10. A team new
to a league starts at the mean rating of the league's three lowest-rated active
teams.

signal = "goals"  rates goals directly (A5).
signal = "sot"    rates shots on target, then converts to expected goals with the
                  league's running goals-per-shot-on-target rate (A6).

The model learns only through observe(), which the walk-forward runner calls
after a whole collection window has been decided.

Pure stdlib.
"""

from __future__ import annotations

import math
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                "engine"))
import poisson  # noqa: E402

from walk import Bet, Decision, Strategy  # noqa: E402

START = {"goals": (math.log(1.30), 0.25), "sot": (math.log(4.2), 0.20)}   # base, home_adv
WARMUP = 10               # league matches seen before the first forecast
LAM_MIN, LAM_MAX = 0.05, 6.0


class _League:
    __slots__ = ("base", "home", "att", "dfn", "last", "n", "goals", "shots")

    def __init__(self, signal: str):
        self.base, self.home = START[signal]
        self.att: dict = {}
        self.dfn: dict = {}
        self.last: dict = {}          # team -> season last seen
        self.n = 0
        self.goals = self.shots = 0.0


class OnlineRatings(Strategy):
    def __init__(self, k: float, signal: str = "goals", bet_ou_book: str | None = None,
                 min_edge: float = 0.03, name: str | None = None):
        if signal not in START:
            raise ValueError("signal must be 'goals' or 'sot'")
        self.k, self.signal, self.bet_ou_book, self.min_edge = k, signal, bet_ou_book, min_edge
        self.leagues: dict = {}
        self.name = name or f"ratings[{signal},k={k}]"

    # ── state ────────────────────────────────────────────────────────────────

    def _league(self, name: str) -> _League:
        if name not in self.leagues:
            self.leagues[name] = _League(self.signal)
        return self.leagues[name]

    @staticmethod
    def _prev(season: str) -> str:
        a = int(season[:2])
        return f"{(a - 1) % 100:02d}{a:02d}"

    def _ensure(self, lg: _League, team: str, season: str) -> None:
        if team in lg.att:
            return
        active = [t for t, s in lg.last.items() if s in (season, self._prev(season))]
        if len(active) >= 3:
            low = sorted(active, key=lambda t: lg.att[t] + lg.dfn[t])[:3]
            lg.att[team] = sum(lg.att[t] for t in low) / 3
            lg.dfn[team] = sum(lg.dfn[t] for t in low) / 3
        else:
            lg.att[team] = lg.dfn[team] = 0.0

    def _expected(self, lg: _League, home: str, away: str) -> tuple[float, float]:
        eh = math.exp(lg.base + lg.home + lg.att[home] - lg.dfn[away])
        ea = math.exp(lg.base + lg.att[away] - lg.dfn[home])
        return eh, ea

    # ── walk interface ───────────────────────────────────────────────────────

    def decide(self, pre) -> Decision:
        d = Decision()
        lg = self._league(pre.league)
        if lg.n < WARMUP:
            return d
        # read-only view of what the ratings would be for teams not yet seen
        tmp_att, tmp_dfn = dict(lg.att), dict(lg.dfn)
        for t in (pre.home, pre.away):
            if t not in lg.att:
                self._ensure(lg, t, pre.season)
        eh, ea = self._expected(lg, pre.home, pre.away)
        lg.att, lg.dfn = tmp_att, tmp_dfn            # deciding must not change state
        if self.signal == "sot":
            if lg.shots <= 0:
                return d
            conv = lg.goals / lg.shots
            eh, ea = eh * conv, ea * conv
        lh, la = min(LAM_MAX, max(LAM_MIN, eh)), min(LAM_MAX, max(LAM_MIN, ea))
        m = poisson.score_matrix(lh, la)
        x = poisson.outcome_1x2(m, ndigits=None)
        over = sum(p for i, row in enumerate(m) for j, p in enumerate(row) if i + j > 2)
        d.forecasts["1x2"] = (x["home"], x["draw"], x["away"])
        d.forecasts["ou25"] = (over, 1.0 - over)
        if self.bet_ou_book:
            price = pre.odds_ou25.get(self.bet_ou_book)
            if price:
                for i, p in enumerate((over, 1.0 - over)):
                    ev = p * price[i] - 1.0
                    if ev > self.min_edge:
                        d.bets.append(Bet("ou25", i, price[i], self.bet_ou_book, ev))
        return d

    def observe(self, pre, post) -> None:
        lg = self._league(pre.league)
        if self.signal == "goals":
            yh, ya = post.fthg, post.ftag
        else:
            if "HST" not in post.stats or "AST" not in post.stats:
                return
            yh, ya = post.stats["HST"], post.stats["AST"]
            lg.goals += post.fthg + post.ftag
            lg.shots += yh + ya
        for t in (pre.home, pre.away):
            self._ensure(lg, t, pre.season)
            lg.last[t] = pre.season
        eh, ea = self._expected(lg, pre.home, pre.away)
        gh, ga = self.k * (yh - eh), self.k * (ya - ea)
        lg.att[pre.home] += gh
        lg.dfn[pre.away] -= gh
        lg.att[pre.away] += ga
        lg.dfn[pre.home] -= ga
        lg.base += (gh + ga) / 10.0
        lg.home += gh / 10.0
        lg.n += 1


# ── log pool ─────────────────────────────────────────────────────────────────

def pool(market: tuple, model: tuple, w: float) -> tuple:
    """Log opinion pool: proportional to market^(1-w) x model^w."""
    raw = [a ** (1.0 - w) * b ** w for a, b in zip(market, model)]
    t = sum(raw)
    return tuple(r / t for r in raw)


def pool_loglik(rows: list[tuple], w: float) -> float:
    """rows = (log market probs, log model probs, outcome index). Total log likelihood."""
    total = 0.0
    for lm, lq, o in rows:
        z = [(1.0 - w) * a + w * b for a, b in zip(lm, lq)]
        mx = max(z)
        total += z[o] - mx - math.log(sum(math.exp(v - mx) for v in z))
    return total


def fit_weight(rows: list[tuple], interval: bool = True) -> dict:
    """Maximum-likelihood w in [0, 1] and its 95% likelihood-ratio interval."""
    lo, hi = 0.0, 1.0
    g = (math.sqrt(5.0) - 1.0) / 2.0
    c, d = hi - g * (hi - lo), lo + g * (hi - lo)
    fc, fd = pool_loglik(rows, c), pool_loglik(rows, d)
    for _ in range(40):
        if fc > fd:
            hi, d, fd = d, c, fc
            c = hi - g * (hi - lo)
            fc = pool_loglik(rows, c)
        else:
            lo, c, fc = c, d, fd
            d = lo + g * (hi - lo)
            fd = pool_loglik(rows, d)
        if hi - lo < 1e-5:
            break
    w = (lo + hi) / 2.0
    f0, f1, fw = pool_loglik(rows, 0.0), pool_loglik(rows, 1.0), pool_loglik(rows, w)
    if f0 >= fw:
        w, fw = 0.0, f0
    if f1 > fw:
        w, fw = 1.0, f1
    out = {"w": w, "loglik": fw, "loglik_at_0": f0, "n": len(rows)}
    if interval:
        cut = fw - 1.92                      # half of chi-square(1) 95% point 3.84

        def edge(a: float, b: float) -> float:   # a is inside the interval, b outside
            for _ in range(30):
                mid = (a + b) / 2.0
                if pool_loglik(rows, mid) >= cut:
                    a = mid
                else:
                    b = mid
            return (a + b) / 2.0

        out["lo"] = 0.0 if f0 >= cut else edge(w, 0.0)
        out["hi"] = 1.0 if f1 >= cut else edge(w, 1.0)
    return out
