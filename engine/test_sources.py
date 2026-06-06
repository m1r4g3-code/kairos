"""
KAIROS — data-source parser tests (offline, fixture-based; no network, no key).

Confirms the keyless feeds (Club Elo, Understat) parse correctly and produce
specs that run.build_prediction accepts end-to-end.

Run:  python test_sources.py
"""

from __future__ import annotations

import os

import config
from run import build_prediction
from sources import clubelo, understat

_failures: list[str] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    status = "PASS" if cond else "FAIL"
    print(f"[{status}] {name}" + (f" -- {detail}" if detail and not cond else ""))
    if not cond:
        _failures.append(name)


def test_clubelo_parse() -> None:
    csv_text = ("Rank,Club,Country,Level,Elo,From,To\n"
                "5,Arsenal,ENG,1,1955.0,2026-05-26,2026-06-01\n"
                "5,Arsenal,ENG,1,1962.3,2026-06-02,2026-06-08\n")
    elo = clubelo.parse_elo_csv(csv_text)
    check("clubelo takes latest Elo", elo == 1962.3, f"got {elo}")
    check("empty csv -> None", clubelo.parse_elo_csv("") is None)


def test_understat_parse_and_strengths() -> None:
    path = os.path.join(config.CACHE_DIR, "understat_sample.html")
    with open(path, encoding="utf-8") as f:
        html = f.read()
    teams = understat.parse_teams_data(html)
    check("parsed 3 teams", len(teams) == 3, f"got {len(teams)}")

    s = understat.team_strengths(teams)
    check("strengths for all teams", set(s) == {"Arsenal", "Chelsea", "Everton"})
    # Arsenal: high xG, low xGA -> strong attack (att>1), tight defence (def<1).
    check("Arsenal strong attack", s["Arsenal"]["att"] > 1.0, f"{s['Arsenal']}")
    check("Arsenal tight defence", s["Arsenal"]["def"] < 1.0, f"{s['Arsenal']}")
    # Everton: low xG, high xGA -> weak attack, leaky defence.
    check("Everton leaky defence", s["Everton"]["def"] > 1.0, f"{s['Everton']}")
    check("Arsenal stronger attack than Everton",
          s["Arsenal"]["att"] > s["Everton"]["att"])


def test_strengths_spec_feeds_engine() -> None:
    path = os.path.join(config.CACHE_DIR, "understat_sample.html")
    with open(path, encoding="utf-8") as f:
        s = understat.team_strengths(understat.parse_teams_data(f.read()))
    spec = understat.build_strengths_spec("Arsenal", "Everton", s,
                                          match="Arsenal vs Everton")
    check("spec built", spec is not None and "strengths" in spec)
    spec["confidence"] = 60
    spec["odds"] = {"1x2": {"home": 1.5, "draw": 4.0, "away": 6.5}}
    res = build_prediction(spec)
    check("engine runs on understat spec", "distribution" in res)
    x = res["distribution"]["1x2"]
    check("strong home favoured by data-fed engine", x["home"] > x["away"],
          f"{x}")
    # missing team -> None (caller falls back to judgment)
    check("missing team -> no spec",
          understat.build_strengths_spec("Arsenal", "Nope FC", s) is None)


def test_elo_spec_shape() -> None:
    # build_elo_spec needs network; just verify the spec shape the engine expects
    # by constructing it the same way and running the engine.
    spec = {"match": "A vs B", "elo": {"home": 1850.0, "away": 1600.0,
            "total_goals": 2.7}, "confidence": 60,
            "odds": {"1x2": {"home": 1.7, "draw": 3.8, "away": 5.0}}}
    res = build_prediction(spec)
    check("elo spec runs through engine", res["distribution"]["1x2"]["home"]
          > res["distribution"]["1x2"]["away"])


def run_all() -> None:
    for fn in (test_clubelo_parse, test_understat_parse_and_strengths,
               test_strengths_spec_feeds_engine, test_elo_spec_shape):
        fn()
    print("\n" + ("ALL SOURCE TESTS PASSED" if not _failures
                  else f"{len(_failures)} FAILURE(S): {_failures}"))
    raise SystemExit(1 if _failures else 0)


if __name__ == "__main__":
    run_all()
