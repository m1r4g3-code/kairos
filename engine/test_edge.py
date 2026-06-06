"""
KAIROS — sharp-line edge tests (offline, fixture-based; no network, no key).

Run:  python test_edge.py   (exits non-zero on any failure)
"""

from __future__ import annotations

import os

import backtest
import config
import edge
from sources import footballdata, odds_api

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def test_sharp_fair_prefers_pinnacle() -> None:
    books = {
        "pinnacle":  {"home": 1.80, "draw": 3.90, "away": 4.50},
        "williamhill": {"home": 1.95, "draw": 3.80, "away": 4.30},
    }
    sf = edge.sharp_fair(books)
    check("sharp source is pinnacle", sf["source"] == "pinnacle")
    s = sum(sf["fair_prob"].values())
    check("sharp fair sums to 1.0", abs(s - 1.0) < 1e-6, f"sum={s}")
    check("favourite has highest fair prob",
          sf["fair_prob"]["home"] > sf["fair_prob"]["away"])
    # de-vig shrinks raw implied (margin removed)
    check("fair home < raw implied", sf["fair_prob"]["home"] < 1 / 1.80)


def test_consensus_fallback() -> None:
    books = {  # no sharp-priority book present -> consensus
        "williamhill": {"home": 1.95, "draw": 3.80, "away": 4.30},
        "betway": {"home": 1.83, "draw": 3.85, "away": 4.40},
    }
    sf = edge.sharp_fair(books)
    check("falls back to consensus", sf["source"] == "consensus")
    check("consensus sums to 1.0", abs(sum(sf["fair_prob"].values()) - 1.0) < 1e-6)
    check("consensus used both books", sf["n_books"] == 2)


def test_value_detection() -> None:
    # Soft book (williamhill) overprices Arsenal vs the Pinnacle truth.
    books = {
        "pinnacle":  {"home": 1.80, "draw": 3.90, "away": 4.50},
        "williamhill": {"home": 1.95, "draw": 3.80, "away": 4.30},
    }
    fair = edge.sharp_fair(books)["fair_prob"]
    rows = edge.value_vs_sharp(books["williamhill"], fair)
    home = next(r for r in rows if r["selection"] == "home")
    check("home flagged value (soft > sharp)", home["value"], f"ev={home['ev']}")
    check("home EV positive", home["ev"] > 0)
    # A selection priced at exactly the sharp fair odds has ~0 EV (no value).
    fair_home_odds = 1.0 / fair["home"]
    rows2 = edge.value_vs_sharp({"home": round(fair_home_odds, 4)}, fair)
    check("fair-priced selection is NOT value", not rows2[0]["value"],
          f"ev={rows2[0]['ev']}")


def test_agreement_crosscheck() -> None:
    fair = {"home": 0.54, "draw": 0.27, "away": 0.19}
    close = {"home": 0.52, "draw": 0.28, "away": 0.20}
    far = {"home": 0.30, "draw": 0.30, "away": 0.40}
    check("close engine aligns with sharp", edge.agree(close, fair)["aligned"])
    check("divergent engine flagged not-aligned", not edge.agree(far, fair)["aligned"])


def test_odds_api_parser() -> None:
    events = odds_api.load_fixture("odds_sample.json")
    check("fixture has events", len(events) >= 2)
    p = odds_api.parse_event(events[0])
    check("parsed home/away", p["home_team"] == "Arsenal" and p["away_team"] == "Chelsea")
    check("parsed pinnacle h2h", set(p["books"]["pinnacle"]) == {"home", "draw", "away"})
    check("draw mapped correctly", p["books"]["pinnacle"]["draw"] == 3.90)
    # find_event loose matching
    ev = odds_api.find_event(events, "Arsenal FC", "Chelsea")
    check("find_event matches by name", ev is not None and ev["id"] == "sample_ars_che")

    # End-to-end on the fixture: Arsenal value at the soft books vs Pinnacle.
    fair = edge.sharp_fair(p["books"])["fair_prob"]
    rows = edge.value_vs_sharp(p["books"]["williamhill"], fair)
    check("e2e: a value bet surfaces on the sample",
          any(r["value"] for r in rows))


def test_backtester() -> None:
    path = os.path.join(config.CACHE_DIR, "fd_sample.csv")
    with open(path, encoding="utf-8") as f:
        rows = footballdata.parse_csv(f.read())
    check("backtest parses sample rows", len(rows) == 10, f"got {len(rows)}")
    res = backtest.run_backtest(rows, thresholds=(0.0, 0.05))
    check("backtest returns a row per threshold", len(res) == 2)
    base = res[0]
    check("backtest finds bets at 0% threshold", base["bets"] > 0,
          f"bets={base['bets']}")
    check("ROI computed", base["roi"] is not None)
    check("CLV computed (soft vs sharp)", base["avg_clv"] is not None)
    # Higher threshold => fewer-or-equal bets (stricter filter).
    check("stricter threshold -> fewer/equal bets", res[1]["bets"] <= base["bets"])


def test_sharp_card_render() -> None:
    import report
    events = odds_api.load_fixture("odds_sample.json")
    p = odds_api.parse_event(events[0])           # Arsenal vs Chelsea
    sharp = edge.sharp_fair(p["books"])["fair_prob"]
    rows = [{
        "match": "Arsenal v Chelsea",
        "sb_odds": p["books"]["williamhill"],     # treat William Hill as the "soft" book
        "sharp": sharp,
        "engine": {"home": 0.55, "draw": 0.25, "away": 0.20},
    }]
    card = report.render_sharp_card(rows)
    check("card has SHARP% column", "SHARP%" in card)
    check("card names team + venue", "Arsenal (HOME)" in card)
    check("card surfaces a value bet", "BET THESE (SportyBet pays" in card)


def run_all() -> None:
    for fn in (test_sharp_fair_prefers_pinnacle, test_consensus_fallback,
               test_value_detection, test_agreement_crosscheck, test_odds_api_parser,
               test_backtester, test_sharp_card_render):
        fn()
    print("\n" + ("ALL EDGE TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
