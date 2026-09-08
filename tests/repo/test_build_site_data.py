"""tools/build_site_data.py: the data behind the static showcase.

The browser has no chess logic, so everything it relies on is decided here:
that a SAN line expands to the right squares and ends in mate, that the EPD
parser agrees with the dashboard's, that a marker sidecar yields an empty
row rather than a crash, and that the corpus totals add up.
"""

import importlib.util
import sys
from pathlib import Path

import pytest

pytest.importorskip("chess")
ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_site_data", ROOT / "tools/build_site_data.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_site_data"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_expand_solution_gives_uci_and_fen_per_ply_and_ends_in_mate():
    m = _load()
    plies = m.expand_solution("8/7k/5K2/8/8/8/8/6Q1 b - - 0 1", "Kh6 Qg6#")
    assert [p["san"] for p in plies] == ["Kh6", "Qg6#"]
    assert [p["uci"] for p in plies] == ["h7h6", "g1g6"]
    assert plies[0]["fen"].startswith("8/8/5K1k/8/8/8/8/6Q1 w")
    assert plies[1]["fen"].startswith("8/8/5KQk/8/8/8/8/8 b")


def test_expand_solution_carries_promotion_in_uci():
    m = _load()
    plies = m.expand_solution(
        "6k1/8/8/8/8/8/4P3/2K5 w - - 0 1", "e3 Kf7 e4 Ke6 e5 Kd5 e6 Kc4 e7 Kb3 e8=Q Ka2 Qa4#"
    )
    assert plies[10]["san"] == "e8=Q" and plies[10]["uci"] == "e7e8q"
    assert len(plies) == 13


def test_expand_solution_rejects_a_line_that_does_not_mate():
    m = _load()
    with pytest.raises(ValueError, match="does not end in checkmate"):
        m.expand_solution("8/7k/5K2/8/8/8/8/6Q1 b - - 0 1", "Kh6 Qg2")
    with pytest.raises(ValueError, match="cannot play"):
        m.expand_solution("8/7k/5K2/8/8/8/8/6Q1 b - - 0 1", "Kh5 Qg6#")


def test_parse_epd_matches_the_dashboard_rules():
    m = _load()
    got = m.parse_epd(
        '# c\n8/7k/5K2/8/8/8/8/6Q1 b - - ; hm 4 ; id "a"\nbad line\n7k/8/5K2/8/8/8/8/6Q1 w - - ; hm x\n'
    )
    assert got == [{"fen": "8/7k/5K2/8/8/8/8/6Q1 b - - 0 1", "dtm": 4, "id": "a"}]


def test_material_of_orders_men_canonically():
    m = _load()
    assert m.material_of("8/7k/5K2/8/6B1/8/8/6Q1 b - - 0 1") == "KQBvk"
    assert m.material_of("8/8/1n6/3b4/q7/8/8/K1kB4 w - - 0 1") == "KBvkqbn"
    assert m.piece_count("KBvkqbn") == 6


def test_material_row_and_corpus_summary():
    m = _load()
    real = {
        "material": "KQvk",
        "plane_size": 100,
        "max_dtm": 14,
        "cells": {"invalid": {"wtm": 10, "btm": 10}, "unsolvable": {"wtm": 5, "btm": 5}},
        "uniqueness": {"wtm": {"2": {"1": 3, "2": 9}}, "btm": {"1": {"1": 4}}},
    }
    marker = {
        "material": "Kvk",
        "plane_size": 462,
        "max_dtm": 255,
        "all_unsolvable": True,
        "cells": {},
        "uniqueness": {},
    }
    r1 = m.material_row(real, 1000)
    r2 = m.material_row(marker, 480)
    assert r1 == {
        "material": "KQvk",
        "pieces": 3,
        "max_dtm": 14,
        "solvable": 170,
        "unique": 7,
        "size_bytes": 1000,
    }
    assert r2["max_dtm"] is None and r2["solvable"] == 0 and r2["unique"] == 0
    c = m.corpus_summary([r1, r2])
    assert c["tables"] == 2 and c["markers"] == 1 and c["size_bytes"] == 1480
    assert c["deepest"] == {"material": "KQvk", "dtm": 14} and c["by_pieces"] == {"3": 1, "2": 1}
