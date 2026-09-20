"""tools/problem_picker.py: choosing which problems a material shows.

The whole point of this module is deciding when two positions are the same
idea wearing different hats, so the tests are mostly about KQvk's three
deepest unique positions, which are exactly that.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# KQvk's three unique positions at h#6. The black king shuffles h6/h7/h8 while
# the white king walks up to the same Qg7#. Real data, from the corpus.
KQVK = [
    {
        "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
        "solutions": [["Kh7", "Kb2", "Kh8", "Kc3", "Kh7", "Kd4",
                       "Kh8", "Ke5", "Kh7", "Kf6", "Kh8", "Qg7#"]],
    },
    {
        "fen": "8/7k/8/6Q1/8/8/8/K7 b - - 0 1",
        "solutions": [["Kh8", "Kb2", "Kh7", "Kc3", "Kh8", "Kd4",
                       "Kh7", "Ke5", "Kh8", "Kf6", "Kh7", "Qg7#"]],
    },
    {
        "fen": "7k/8/8/6Q1/8/8/8/K7 b - - 0 1",
        "solutions": [["Kh7", "Kb2", "Kh8", "Kc3", "Kh7", "Kd4",
                       "Kh8", "Ke5", "Kh7", "Kf6", "Kh8", "Qg7#"]],
    },
]


def _load():
    spec = importlib.util.spec_from_file_location(
        "problem_picker", ROOT / "tools/problem_picker.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["problem_picker"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_white_line_takes_odd_indices_when_black_moves_first():
    m = _load()
    assert m.white_line(KQVK[0]["solutions"][0], white_moves_first=False) == [
        "Kb2", "Kc3", "Kd4", "Ke5", "Kf6", "Qg7#"
    ]


def test_white_line_takes_even_indices_when_white_moves_first():
    m = _load()
    assert m.white_line(["d4", "Kg3", "d5", "Kf4"], white_moves_first=True) == ["d4", "d5"]


def test_san_distance_is_zero_for_identical_and_one_for_disjoint():
    m = _load()
    assert m.san_distance(["a", "b"], ["a", "b"]) == 0.0
    assert m.san_distance(["a", "b"], ["c", "d"]) == 1.0


def test_san_distance_normalizes_by_the_longer_line():
    m = _load()
    # One substitution in four tokens.
    assert m.san_distance(["a", "b", "c", "d"], ["a", "b", "c", "X"]) == 0.25


def test_position_distance_counts_men_on_different_squares():
    m = _load()
    # Black king h6 vs h7; everything else identical. One man moved.
    assert m.position_distance(KQVK[0]["fen"], KQVK[1]["fen"]) == 1
    assert m.position_distance(KQVK[0]["fen"], KQVK[0]["fen"]) == 0


def test_full_san_distance_does_not_separate_the_kqvk_twins():
    """The rule this module deliberately does NOT use, pinned so it stays rejected.

    Positions 1 and 2 differ only in which square the king shuffles to, yet
    score 0.50 on the full line -- above any threshold that would not also
    collapse genuinely different problems."""
    m = _load()
    assert m.san_distance(KQVK[0]["solutions"][0], KQVK[1]["solutions"][0]) == 0.5
