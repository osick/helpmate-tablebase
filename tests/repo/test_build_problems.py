"""tools/build_problems.py: mining the problems the site shows.

The sidecar arithmetic is exact and testable without a corpus, so it is
tested here; the mining itself is driven through a fake binary in Task 5.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The shape of a real sidecar, cut down to what this tool reads. `uniqueness`
# maps side -> dtm -> solution count -> how many positions.
STATS = {
    "material": "KQvk",
    "max_dtm": 14,
    "plane_size": 29568,
    "uniqueness": {
        "wtm": {"7": {"2": 3}, "13": {"255": 2}},
        "btm": {"10": {"2": 4}, "12": {"1": 3}, "14": {"255": 4}},
    },
}


def _load():
    spec = importlib.util.spec_from_file_location(
        "build_problems", ROOT / "tools/build_problems.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["build_problems"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_deepest_depth_with_a_unique_solution():
    m = _load()
    assert m.deepest_depth(STATS, 1) == 12


def test_deepest_depth_spans_both_sides_to_move():
    m = _load()
    # count=2 appears at btm 10 and wtm 7; the deeper one wins.
    assert m.deepest_depth(STATS, 2) == 10


def test_depths_with_are_listed_deepest_first():
    m = _load()
    assert m.depths_with(STATS, 2) == [10, 7]


def test_deepest_depth_is_none_when_the_count_never_occurs():
    m = _load()
    assert m.deepest_depth(STATS, 3) is None
    assert m.depths_with(STATS, 3) == []
