"""tools/build_problems.py: mining the problems the site shows.

The sidecar arithmetic is exact and testable without a corpus, so it is
tested here; the mining itself is driven through a fake binary in Task 5.
"""

import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

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


def _fake_run_with_codes(responses):
    """Stand in for subprocess.run, returning canned (returncode, stdout, stderr).

    `responses` is a list of (returncode, stdout, stderr) tuples, consumed in
    order. The argv of each call is recorded so the test can assert what was
    asked of the binary."""
    calls = []

    def run(argv, capture_output=True, text=True, **kw):
        calls.append(argv)
        if responses:
            code, out, err = responses.pop(0)
        else:
            code, out, err = 0, "", ""
        return types.SimpleNamespace(returncode=code, stdout=out, stderr=err)

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


def test_run_jsonl_raises_on_nonzero_return_without_checksum_error(monkeypatch):
    """Non-zero return code with non-checksum error fails immediately."""
    m = _load()
    import pytest
    fake = _fake_run_with_codes([(1, "", "some other error")])
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="some other error"):
        m.run_jsonl("./build/helpmate", ["mine", "KQvk"], "/tb")
    assert len(fake.calls) == 1


def test_run_jsonl_raises_when_output_has_no_footer(monkeypatch):
    """Header without footer (single line) indicates truncated scan."""
    m = _load()
    import pytest
    fake = _fake_run_with_codes([(0, HEADER, "")])
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="cut short"):
        m.run_jsonl("./build/helpmate", ["mine", "KQvk"], "/tb")


def test_run_jsonl_retries_on_checksum_and_raises_after_limit(monkeypatch):
    """Checksum errors are retried; gives up after exhausting retries."""
    m = _load()
    import pytest
    responses = [
        (1, "", "checksum error: ..."),
        (1, "", "checksum error: ..."),
        (1, "", "checksum error: ..."),
    ]
    fake = _fake_run_with_codes(responses)
    monkeypatch.setattr(subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="failed after 3 retries"):
        m.run_jsonl("./build/helpmate", ["mine", "KQvk"], "/tb")
    assert len(fake.calls) == 3


pytest.importorskip("chess")

DEEPEST_ROW = {
    "material": "KPvk",
    "fen": "6k1/8/8/8/8/8/4P3/2K5 w - - 0 1",
    "published": [{"id": "P0530828", "author": "Niemann, John",
                   "sources": ["Schachmatt, No. 427, 13/07/1947"]}],
    "published_by": "Niemann (1947)",
    "quality": {"capture_first": False, "check": False, "legal": True},
    "alternative": None,
}


def test_attribution_is_keyed_by_fen():
    m = _load()
    a = m.attribution([DEEPEST_ROW])
    assert a["6k1/8/8/8/8/8/4P3/2K5 w - - 0 1"]["published_by"] == "Niemann (1947)"


def test_problem_record_carries_attribution_over_by_fen():
    m = _load()
    cand = {"fen": DEEPEST_ROW["fen"], "dtm": 13, "count": 1, "starts": 1, "ends": 1,
            "themes": ["model"],
            "solutions": [["e3", "Kf7", "e4", "Ke6", "e5", "Kd5", "e6", "Kc4",
                           "e7", "Kb3", "e8=Q", "Ka2", "Qa4#"]]}
    rec = m.problem_record(cand, m.attribution([DEEPEST_ROW]))
    assert rec["published_by"] == "Niemann (1947)"
    assert rec["stipulation"] == "h#6.5"
    assert rec["solutions"][0][0] == {"san": "e3", "uci": "e2e3",
                                      "fen": "6k1/8/8/8/8/4P3/8/2K5 b - - 0 1"}


def test_problem_record_recomputes_quality_for_a_new_position():
    """Most problems have no DEEPEST.json row to carry quality from."""
    m = _load()
    cand = {"fen": DEEPEST_ROW["fen"], "dtm": 13, "count": 1, "starts": 1, "ends": 1,
            "themes": [],
            "solutions": [["e3", "Kf7", "e4", "Ke6", "e5", "Kd5", "e6", "Kc4",
                           "e7", "Kb3", "e8=Q", "Ka2", "Qa4#"]]}
    rec = m.problem_record(cand, {})          # no attribution at all
    assert rec["published"] is None and rec["published_by"] is None
    assert rec["quality"] == {"capture_first": False, "check": False, "legal": True}


def test_problem_record_rejects_a_line_that_does_not_mate():
    m = _load()
    cand = {"fen": "8/7k/5K2/8/8/8/8/6Q1 b - - 0 1", "dtm": 2, "count": 1,
            "starts": 1, "ends": 1, "themes": [], "solutions": [["Kh6", "Qg5"]]}
    with pytest.raises(ValueError, match="does not end in checkmate"):
        m.problem_record(cand, {})


def test_saturated_at_max_is_false_for_a_marker():
    m = _load()
    assert m.saturated_at_max(MARKER_STATS) is False


def test_saturated_at_max_is_true_when_the_max_bucket_is_only_255():
    m = _load()
    stats = {"max_dtm": 14, "uniqueness": {
        "wtm": {"14": {"255": 2}}, "btm": {"14": {"255": 4}},
    }}
    assert m.saturated_at_max(stats) is True


MARKER_STATS = {"material": "Kvk", "max_dtm": 255, "plane_size": 462, "uniqueness": {}}
MATERIAL_ROW = {"material": "KQvk", "pieces": 3, "max_dtm": 14,
                "solvable": 45723, "unique": 3064, "size_bytes": 71647}


def test_build_material_on_a_marker_reports_no_helpmate_without_mining(monkeypatch):
    m = _load()
    def explode(*a, **k):
        raise AssertionError("a marker material must not be mined")
    monkeypatch.setattr(m, "mine", explode)
    doc = m.build_material("./build/helpmate", "/tb", "Kvk", MARKER_STATS,
                           {"material": "Kvk", "pieces": 2, "max_dtm": None,
                            "solvable": 0, "unique": 0, "size_bytes": 466}, {})
    assert doc["unique"] == [] and doc["duals"] == []
    assert doc["notes"] == ["No helpmate exists in this material."]
    assert doc["stats"]["deepest_unique_dtm"] is None


def test_build_material_records_both_dual_depths(monkeypatch):
    m = _load()
    cand = {"fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1", "dtm": 12, "count": 1,
            "starts": 1, "ends": 1, "themes": [],
            "solutions": [["Kh7", "Kb2", "Kh8", "Qg7#"]]}
    dual = {"fen": "8/5Q2/8/8/8/6k1/8/K7 w - - 0 1", "dtm": 7, "count": 2,
            "starts": 2, "ends": 2, "themes": [],
            "solutions": [["Qf3", "Kh4", "Qh3#"], ["Qg7", "Kh4", "Qh6#"]]}
    monkeypatch.setattr(m, "mine", lambda *a, **k: [cand])
    monkeypatch.setattr(m, "strict_dual_depth", lambda *a, **k: (7, [dual]))
    monkeypatch.setattr(m, "problem_record", lambda c, a: dict(c, stipulation="x"))
    doc = m.build_material("./build/helpmate", "/tb", "KQvk", STATS, MATERIAL_ROW, {})
    assert doc["stats"]["deepest_unique_dtm"] == 12
    assert doc["stats"]["deepest_dual_dtm"] == 10      # from the sidecar
    assert doc["stats"]["strict_dual_dtm"] == 7        # what the filter found
    assert doc["stats"]["solvable"] == 45723
    assert len(doc["unique"]) == 1 and len(doc["duals"]) == 1


def test_build_material_carries_the_pickers_notes(monkeypatch):
    m = _load()
    monkeypatch.setattr(m, "mine", lambda *a, **k: [])
    monkeypatch.setattr(m, "strict_dual_depth", lambda *a, **k: (None, []))
    doc = m.build_material("./build/helpmate", "/tb", "KQvk", STATS, MATERIAL_ROW, {})
    assert "No position at this depth satisfies the filter." in doc["notes"]
