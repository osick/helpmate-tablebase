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


def _cand(fen, solution, dtm=12):
    return {"fen": fen, "dtm": dtm, "count": 1, "starts": 1, "ends": 1,
            "themes": [], "solutions": [solution]}


KQVK_CANDS = [_cand(c["fen"], c["solutions"][0]) for c in KQVK]


def test_kqvk_twins_are_one_idea():
    m = _load()
    assert m.same_idea(KQVK_CANDS[0], KQVK_CANDS[1])
    assert m.same_idea(KQVK_CANDS[0], KQVK_CANDS[2])
    assert m.same_idea(KQVK_CANDS[1], KQVK_CANDS[2])


def test_pick_collapses_kqvk_to_one_problem_with_a_note():
    m = _load()
    chosen, notes = m.pick(KQVK_CANDS, limit=3)
    assert len(chosen) == 1
    assert chosen[0]["fen"] == KQVK_CANDS[0]["fen"]
    assert notes == [
        "Only one distinct idea exists at this depth: 3 positions share a solution."
    ]


def test_pick_on_a_single_candidate_does_not_claim_it_shares_with_itself():
    m = _load()
    chosen, notes = m.pick([KQVK_CANDS[0]], limit=3)
    assert len(chosen) == 1
    assert notes == ["Only one position exists at this depth."]
    assert "positions share" not in notes[0]


def test_a_different_white_manoeuvre_is_a_different_problem():
    m = _load()
    other = _cand("8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
                  ["Kh7", "Qg1", "Kh8", "Qa7", "Kh7", "Qb8",
                   "Kh8", "Qc7", "Kh7", "Qd8", "Kh8", "Qg7#"])
    assert not m.same_idea(KQVK_CANDS[0], other)
    chosen, notes = m.pick([KQVK_CANDS[0], other], limit=3)
    assert len(chosen) == 2
    assert notes == ["Only 2 distinct ideas exist at this depth."]


def test_same_white_line_but_two_men_elsewhere_is_a_different_problem():
    m = _load()
    # Same white manoeuvre, but the queen starts elsewhere too: 2 men differ.
    moved = _cand("8/7k/8/8/6Q1/8/8/K7 b - - 0 1", KQVK_CANDS[0]["solutions"][0])
    assert m.position_distance(KQVK_CANDS[0]["fen"], moved["fen"]) == 2
    assert not m.same_idea(KQVK_CANDS[0], moved)


def test_pick_seeds_with_the_published_position_when_given_one():
    m = _load()
    a = _cand("8/8/7k/6Q1/8/8/8/K7 b - - 0 1", ["Kh7", "Kb2", "Kh8", "Qg7#"])
    b = _cand("8/8/8/6Q1/8/7k/8/K7 b - - 0 1", ["Kh4", "Qd2", "Kh5", "Qh6#"])
    chosen, _ = m.pick([a, b], limit=1, seed_fen=b["fen"])
    assert chosen[0]["fen"] == b["fen"]


def test_pick_stops_at_the_limit_even_when_more_are_distinct():
    m = _load()
    cands = [
        _cand("8/8/7k/6Q1/8/8/8/K7 b - - 0 1", ["Kh7", "Ka2", "Kh8", "Qg7#"]),
        _cand("8/8/8/6Q1/8/7k/8/K7 b - - 0 1", ["Kh4", "Qd2", "Kh5", "Qh6#"]),
        _cand("8/8/8/8/6Q1/8/7k/K7 b - - 0 1", ["Kh3", "Qb4", "Kh2", "Qh4#"]),
        _cand("8/8/8/8/8/6Q1/7k/K7 b - - 0 1", ["Kh1", "Qc3", "Kh2", "Qh3#"]),
    ]
    chosen, notes = m.pick(cands, limit=3)
    assert len(chosen) == 3
    assert notes == []


def test_pick_on_an_empty_candidate_list_notes_it():
    m = _load()
    chosen, notes = m.pick([], limit=3)
    assert chosen == []
    assert notes == ["No position at this depth satisfies the filter."]


def test_pick_is_order_independent_for_tied_candidates():
    """Regression: pick must not discard distinct problems when distances tie.

    When a twin and a genuinely different problem have equal distance from the
    chosen set, the greedy loop must not break on the first twin it encounters.
    It must filter twins first, then rank, so result is order-independent.

    This construction ensures distance(A, TWIN) == distance(A, NEAR) == 0.3333:
    NEAR's white line differs in exactly 2 of 6 moves, and position_distance is 1.
    The tie forces a consistent ranking independent of pool iteration order."""
    m = _load()
    # A: base problem
    a = _cand("8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
              ["Kh7", "Kb2", "Kh8", "Kc3", "Kh7", "Kd4",
               "Kh8", "Ke5", "Kh7", "Kf6", "Kh8", "Qg7#"])
    # TWIN: same white line, different black king position
    twin = _cand("8/7k/8/6Q1/8/8/8/K7 b - - 0 1",
                 ["Kh8", "Kb2", "Kh7", "Kc3", "Kh8", "Kd4",
                  "Kh7", "Ke5", "Kh8", "Kf6", "Kh7", "Qg7#"])
    # NEAR: genuinely different white line with same distance as TWIN.
    # White line: Kb2 Kc3 Kd4 Ke5 Ka6 Qb7# (differs in 2 of 6 moves -> 0.3333)
    # Position distance: 1 man (queen moved) (1/3 = 0.3333)
    near = _cand("8/7k/8/6Q1/8/8/8/K7 b - - 0 1",
                 ["Kh8", "Kb2", "Kh7", "Kc3", "Kh8", "Kd4",
                  "Kh7", "Ke5", "Kh8", "Ka6", "Kh7", "Qb7#"])
    # Verify setup
    assert m.same_idea(a, twin), "TWIN should be same_idea as A"
    assert not m.same_idea(a, near), "NEAR should NOT be same_idea as A"
    # Distances must be tied (the point of this test)
    dist_a_twin = m.distance(a, twin)
    dist_a_near = m.distance(a, near)
    assert dist_a_twin == dist_a_near == 0.3333333333333333, \
        f"distances must be tied: {dist_a_twin} vs {dist_a_near}"
    # Test both orderings
    chosen_twin_first, notes_twin_first = m.pick([a, twin, near], limit=3)
    chosen_near_first, notes_near_first = m.pick([a, near, twin], limit=3)
    # Both must pick exactly 2 problems (A and NEAR)
    assert len(chosen_twin_first) == 2, \
        f"[A,TWIN,NEAR] should pick 2, got {len(chosen_twin_first)}"
    assert len(chosen_near_first) == 2, \
        f"[A,NEAR,TWIN] should pick 2, got {len(chosen_near_first)}"
    # Both must include NEAR
    assert any(c["fen"] == near["fen"] and
               m.san_distance(m._white_line_of(c), m._white_line_of(near)) < 0.01
               for c in chosen_twin_first), "NEAR must be in [A,TWIN,NEAR] result"
    assert any(c["fen"] == near["fen"] and
               m.san_distance(m._white_line_of(c), m._white_line_of(near)) < 0.01
               for c in chosen_near_first), "NEAR must be in [A,NEAR,TWIN] result"
    # Notes must match (both should say "Only 2 distinct ideas exist")
    assert notes_twin_first == notes_near_first, \
        f"Notes differ by order: {notes_twin_first} vs {notes_near_first}"
