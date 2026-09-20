"""tools/build_problems.py: mining the problems the site shows.

The sidecar arithmetic is exact and testable without a corpus, so it is
tested here; the mining itself is driven through a fake binary in Task 5.
"""

import importlib.util
import subprocess
import sys
import types
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


def _fake_run(outputs):
    """Stand in for subprocess.run, returning canned stdout per invocation.

    `outputs` is a list of stdout strings, consumed in order. The argv of each
    call is recorded so the test can assert what was asked of the binary."""
    calls = []

    def run(argv, capture_output=True, text=True, **kw):
        calls.append(argv)
        out = outputs.pop(0) if outputs else ""
        return types.SimpleNamespace(returncode=0, stdout=out, stderr="")

    run.calls = calls
    return run


HEADER = '{"material":"KQvk","filter":{},"max":500}'
FOOTER = '{"positions":1,"skipped_saturated":0}'
ROW = ('{"fen":"8/8/7k/6Q1/8/8/8/K7 b - - 0 1","dtm":12,"count":1,'
       '"themes":["pure","model"],"starts":1,"ends":1,'
       '"solutions":[["Kh7","Kb2","Kh8","Qg7#"]]}')


def test_run_jsonl_drops_the_header_and_footer(monkeypatch):
    m = _load()
    monkeypatch.setattr(subprocess, "run", _fake_run(["\n".join([HEADER, ROW, FOOTER])]))
    rows = m.run_jsonl("./build/helpmate", ["mine", "KQvk"], "/tb")
    assert len(rows) == 1
    assert rows[0]["fen"].startswith("8/8/7k/6Q1")
    assert rows[0]["themes"] == ["pure", "model"]


def test_mine_passes_max_explicitly_because_the_default_is_ten(monkeypatch):
    m = _load()
    fake = _fake_run(["\n".join([HEADER, ROW, FOOTER])])
    monkeypatch.setattr(subprocess, "run", fake)
    m.mine("./build/helpmate", "/tb", "KQvk", 12, 1)
    argv = fake.calls[0]
    assert "--max" in argv and argv[argv.index("--max") + 1] == "500"
    assert "--themes" in argv and "--solutions" in argv and "--jsonl" in argv
    assert "--starts" not in argv


def test_mine_adds_the_strict_filter_when_asked(monkeypatch):
    m = _load()
    fake = _fake_run(["\n".join([HEADER, FOOTER])])
    monkeypatch.setattr(subprocess, "run", fake)
    m.mine("./build/helpmate", "/tb", "KQvk", 10, 2, strict=True)
    argv = fake.calls[0]
    assert argv[argv.index("--starts") + 1] == "2"
    assert argv[argv.index("--ends") + 1] == "2"


def test_strict_dual_depth_walks_downward_until_a_depth_yields(monkeypatch):
    """The deepest dual depth is almost always empty under starts=ends=2."""
    m = _load()
    empty = "\n".join([HEADER, FOOTER])
    hit = "\n".join([HEADER, ROW, FOOTER])
    fake = _fake_run([empty, hit])          # depth 10 empty, depth 7 yields
    monkeypatch.setattr(subprocess, "run", fake)
    depth, rows = m.strict_dual_depth("./build/helpmate", "/tb", "KQvk", STATS)
    assert depth == 7
    assert len(rows) == 1
    assert [c[c.index("--dtm") + 1] for c in fake.calls] == ["10", "7"]


def test_strict_dual_depth_returns_none_when_no_depth_yields(monkeypatch):
    m = _load()
    empty = "\n".join([HEADER, FOOTER])
    monkeypatch.setattr(subprocess, "run", _fake_run([empty, empty]))
    depth, rows = m.strict_dual_depth("./build/helpmate", "/tb", "KQvk", STATS)
    assert depth is None and rows == []
