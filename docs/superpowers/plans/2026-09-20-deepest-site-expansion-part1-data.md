# Deepest-site expansion, Part 1: the data pipeline

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Produce `site/data/material/<MAT>.json`, `site/data/themes.json` and `site/data/index.json` holding up to three deepest unique problems and up to three deepest strict-dual problems per material, each with its themes and ply-by-ply solutions.

**Architecture:** A pure selection module (`tools/problem_picker.py`) with no I/O, and a CLI (`tools/build_problems.py`) that mines the corpus, validates, and writes JSON. The picker is unit-tested without a corpus; the CLI is tested against a fake binary.

**Tech Stack:** Python 3.9 (floor — no `match`, no PEP 604 unions at runtime; use `from __future__ import annotations`), pytest, python-chess (`chess>=1.10`), the `helpmate` CLI, ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-20-deepest-site-expansion-design.md`

## Global Constraints

- Python floor is **3.9**. Every new module starts with `from __future__ import annotations`. Use `typing.List` / `Optional` / `Tuple` in annotations, not `list[...]` / `X | None`, matching `tools/build_site_data.py`.
- ruff: `line-length = 100`, `select = ["E4","E7","E9","F"]`, `ignore = ["E701","E702","E401"]`. `ruff format` is **not** used — do not reformat existing code.
- Tests for repo tooling live in `tests/repo/` and run via `make test-repo` (`python -m pytest tests/repo -v`).
- Existing tool tests load the module under test with `importlib.util.spec_from_file_location`, because `tools/` is not a package. Follow that pattern exactly (see `tests/repo/test_build_site_data.py:19`).
- `mine`'s default `--max` is **10**. Always pass `--max` explicitly.
- Corpus for manual runs: `~/tb`. Binary: `./build/helpmate`.
- Coverage ≥80% on both new modules.
- Never ship a problem whose claimed dtm/count/starts/ends disagree with a re-probe, or whose solution does not end in mate.

---

### Task 1: The distance primitives

**Files:**
- Create: `tools/problem_picker.py`
- Test: `tests/repo/test_problem_picker.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `white_line(solution: List[str], white_moves_first: bool) -> List[str]`, `san_distance(a: List[str], b: List[str]) -> float`, `position_distance(fen_a: str, fen_b: str) -> int`.

- [ ] **Step 1: Write the failing test**

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_problem_picker.py -v`
Expected: collection error — `tools/problem_picker.py` does not exist.

- [ ] **Step 3: Write the implementation**

```python
"""Choosing which problems a material shows.

Pure functions over candidate dicts as `helpmate mine --jsonl` emits them --
no I/O, no subprocesses, no corpus. `build_problems.py` does the talking to
the binary; this module only decides.

The hard part is R1's "differ significantly". At the deepest depth a material
often holds one idea wearing several hats: KQvk's three h#6 positions are the
same king walk to the same Qg7#, differing only in which square the black king
shuffles to. Comparing the full solution does not catch that -- those pairs
score 0.50, above any threshold that would not also collapse real problems.
Comparing WHITE's moves does: all three play Kb2 Kc3 Kd4 Ke5 Kf6 Qg7#.

In a helpmate Black's moves are the cooperative ones, so the composition's
content is White's manoeuvre plus the mating picture. That is the signal.
"""
from __future__ import annotations

from typing import Dict, List, Sequence


def white_line(solution: Sequence[str], white_moves_first: bool) -> List[str]:
    """Just White's moves. Black moves first in an even-dtm helpmate."""
    return list(solution[0::2] if white_moves_first else solution[1::2])


def san_distance(a: Sequence[str], b: Sequence[str]) -> float:
    """Levenshtein over SAN tokens, normalized by the longer line. 0.0 .. 1.0."""
    if not a and not b:
        return 0.0
    prev = list(range(len(b) + 1))
    for i, tok in enumerate(a, 1):
        cur = [i]
        for j, other in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (tok != other)))
        prev = cur
    return prev[-1] / max(len(a), len(b))


def _men(fen: str) -> List[str]:
    """`(piece, square)` for every man, as `Qg5`-style strings."""
    out = []
    for r, rank in enumerate(fen.split()[0].split("/")):
        f = 0
        for ch in rank:
            if ch.isdigit():
                f += int(ch)
            else:
                out.append(f"{ch}{'abcdefgh'[f]}{8 - r}")
                f += 1
    return out


def position_distance(fen_a: str, fen_b: str) -> int:
    """How many men stand on different squares.

    Symmetric difference over (piece, square), halved -- one man moving
    contributes two entries, the square it left and the one it took."""
    a, b = sorted(_men(fen_a)), sorted(_men(fen_b))
    counts: Dict[str, int] = {}
    for m in a:
        counts[m] = counts.get(m, 0) + 1
    for m in b:
        counts[m] = counts.get(m, 0) - 1
    return sum(abs(v) for v in counts.values()) // 2
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_problem_picker.py -v`
Expected: 6 passed.

- [ ] **Step 5: Lint**

Run: `ruff check tools/problem_picker.py tests/repo/test_problem_picker.py`
Expected: `All checks passed!`

- [ ] **Step 6: Commit**

```bash
git add tools/problem_picker.py tests/repo/test_problem_picker.py
git commit -m "picker: distance primitives over White's line and piece placement"
```

---

### Task 2: Same-idea and the greedy picker

**Files:**
- Modify: `tools/problem_picker.py`
- Test: `tests/repo/test_problem_picker.py`

**Interfaces:**
- Consumes: `white_line`, `san_distance`, `position_distance` from Task 1.
- Produces: `same_idea(a: dict, b: dict) -> bool`, `distance(a: dict, b: dict) -> float`, `pick(candidates: List[dict], limit: int = 3, seed_fen: Optional[str] = None) -> Tuple[List[dict], List[str]]`. A candidate is a `mine --jsonl` record: `{"fen", "dtm", "count", "starts", "ends", "themes", "solutions"}`. `pick` returns the chosen candidates and a list of note strings.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_problem_picker.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_problem_picker.py -v -k "idea or pick or elsewhere"`
Expected: FAIL — `module 'problem_picker' has no attribute 'same_idea'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/problem_picker.py`:

```python
def _white_line_of(cand: Dict) -> List[str]:
    """White's moves in a candidate's first solution.

    `mine` emits the FEN it scanned, so the side to move is in the FEN --
    not inferred from the dtm's parity, which would invert on a flipped probe."""
    white_first = cand["fen"].split()[1] == "w"
    return white_line(cand["solutions"][0], white_first)


def same_idea(a: Dict, b: Dict) -> bool:
    """One problem wearing two hats: White plays the same moves and at most
    one man stands elsewhere."""
    return (_white_line_of(a) == _white_line_of(b)
            and position_distance(a["fen"], b["fen"]) <= 1)


def distance(a: Dict, b: Dict) -> float:
    """How far apart two candidates are, for the greedy max-min pick."""
    men = max(len(_men(a["fen"])), 1)
    return max(san_distance(_white_line_of(a), _white_line_of(b)),
               position_distance(a["fen"], b["fen"]) / men)


def pick(candidates: List[Dict], limit: int = 3, seed_fen: str = None):
    """Up to `limit` candidates that are not each other's twins, plus notes.

    Greedy max-min: seed, then repeatedly take whatever is farthest from
    everything already chosen, stopping when the best remaining is the same
    idea as something held."""
    if not candidates:
        return [], ["No position at this depth satisfies the filter."]

    pool = list(candidates)
    seed = next((c for c in pool if c["fen"] == seed_fen), pool[0])
    chosen = [seed]
    pool.remove(seed)

    while pool and len(chosen) < limit:
        best = max(pool, key=lambda c: min(distance(c, k) for k in chosen))
        if any(same_idea(best, k) for k in chosen):
            break
        chosen.append(best)
        pool.remove(best)

    notes = []
    if len(chosen) < limit:
        if len(chosen) == 1:
            notes.append(
                "Only one distinct idea exists at this depth: "
                f"{len(candidates)} positions share a solution."
            )
        else:
            notes.append(f"Only {len(chosen)} distinct ideas exist at this depth.")
    return chosen, notes
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_problem_picker.py -v`
Expected: 13 passed.

- [ ] **Step 5: Check coverage of the module**

Run: `python -m pytest tests/repo/test_problem_picker.py --cov=tools.problem_picker --cov-report=term-missing`
Expected: ≥80%. If `pytest-cov` is unavailable, run `python -m coverage run -m pytest tests/repo/test_problem_picker.py && python -m coverage report --include='*problem_picker*'`.

- [ ] **Step 6: Lint and commit**

```bash
ruff check tools/problem_picker.py tests/repo/test_problem_picker.py
git add tools/problem_picker.py tests/repo/test_problem_picker.py
git commit -m "picker: same-idea collapse and greedy max-min selection"
```

---

### Task 3: Reading depths out of a stats sidecar

**Files:**
- Create: `tools/build_problems.py`
- Test: `tests/repo/test_build_problems.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces: `deepest_depth(stats: dict, count: int) -> Optional[int]`, `depths_with(stats: dict, count: int) -> List[int]` (descending), `white_moves_first(fen: str) -> bool`.

- [ ] **Step 1: Write the failing test**

```python
"""tools/build_problems.py: mining the problems the site shows.

The sidecar arithmetic is exact and testable without a corpus, so it is
tested here; the mining itself is driven through a fake binary in Task 5.
"""

import importlib.util
import json
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


def test_white_moves_first_reads_the_fen_not_the_parity():
    m = _load()
    assert m.white_moves_first("8/8/8/8/8/8/8/K6k w - - 0 1") is True
    assert m.white_moves_first("8/8/8/8/8/8/8/K6k b - - 0 1") is False
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_build_problems.py -v`
Expected: collection error — `tools/build_problems.py` does not exist.

- [ ] **Step 3: Write the implementation**

```python
"""Build the per-material problem data the static site reads.

    python3 tools/build_problems.py --tables ~/tb [--binary ./build/helpmate]
                                    [--out site/data] [--material KQvk ...]

Run by hand against a corpus, like tools/build_site_data.py -- the output is
committed, because the Pages workflow has no tables.

Two classes of problem per material:

  unique  the deepest positions with exactly one optimal solution
  duals   the deepest positions with exactly two, which differ in both their
          first and their last move (starts = ends = count = 2)

The depths come from the sidecar's `uniqueness` map and are exact, so no
scanning is needed to find them. Only the positions themselves are mined.
`mine --jsonl --themes --solutions` returns fen, dtm, count, starts, ends,
themes and the SAN solutions in one call, so a material costs about two
subprocess invocations.

Note that the strict dual filter is usually empty at the deepest dual depth --
the two solutions there almost always share a first or a last move -- so the
search walks depths downward and typically lands one ply shallower. Both
depths are recorded; the page states the difference.
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# `mine` defaults to --max 10. Ask for enough candidates that the picker has
# room to find three dissimilar ones, without scanning a plane into memory.
CANDIDATE_CAP = 500


def white_moves_first(fen: str) -> bool:
    return fen.split()[1] == "w"


def depths_with(stats: dict, count: int) -> List[int]:
    """Every dtm holding a position with exactly `count` optimal solutions,
    deepest first, across both sides to move."""
    key = str(count)
    found = set()
    for side in ("wtm", "btm"):
        for dtm, counts in stats.get("uniqueness", {}).get(side, {}).items():
            if counts.get(key):
                found.add(int(dtm))
    return sorted(found, reverse=True)


def deepest_depth(stats: dict, count: int) -> Optional[int]:
    depths = depths_with(stats, count)
    return depths[0] if depths else None
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_build_problems.py -v`
Expected: 5 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/build_problems.py tests/repo/test_build_problems.py
git add tools/build_problems.py tests/repo/test_build_problems.py
git commit -m "build_problems: exact depth arithmetic from the stats sidecars"
```

---

### Task 4: Mining candidates through the binary

**Files:**
- Modify: `tools/build_problems.py`
- Test: `tests/repo/test_build_problems.py`

**Interfaces:**
- Consumes: `depths_with` from Task 3.
- Produces: `run_jsonl(binary: str, args: List[str], tables: str) -> List[dict]`, `mine(binary, tables, material, dtm, count, strict=False, cap=CANDIDATE_CAP) -> List[dict]`, `strict_dual_depth(binary, tables, material, stats) -> Tuple[Optional[int], List[dict]]`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_build_problems.py`:

```python
import subprocess
import types


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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_build_problems.py -v -k "jsonl or mine or strict"`
Expected: FAIL — `module 'build_problems' has no attribute 'run_jsonl'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/build_problems.py`:

```python
def run_jsonl(binary: str, args: List[str], tables: str, retries: int = 3) -> List[Dict]:
    """The position records from a `mine --jsonl` run.

    The first line is the filter header and the last is the counts footer;
    neither is a position. A run cut short before its footer is a truncated
    scan, not an empty result, and raises rather than silently shipping fewer
    problems.

    Retried on the intermittent zstd checksum error the compressed read path
    threw on 2026-08-21 -- the same guard tools/deepest_showcase.py carries,
    and a recurrence is a reason to run tools/verify_corpus.py, not to suspect
    this script."""
    for attempt in range(retries):
        p = subprocess.run([binary, *args, "--tables", tables],
                           capture_output=True, text=True)
        if p.returncode == 0:
            lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
            if len(lines) < 2:
                raise RuntimeError(f"{' '.join(args)}: no footer -- scan was cut short")
            return [json.loads(ln) for ln in lines[1:-1]]
        if "checksum" not in p.stderr:
            raise RuntimeError(f"{' '.join(args)}: {p.stderr.strip()[:200]}")
        print(f"    retry {attempt + 1} after checksum error", file=sys.stderr)
    raise RuntimeError(f"{' '.join(args)}: failed after {retries} retries")


def mine(binary: str, tables: str, material: str, dtm: int, count: int,
         strict: bool = False, cap: int = CANDIDATE_CAP) -> List[Dict]:
    """Candidates at one depth. `--max` is passed explicitly: it defaults to 10."""
    args = ["mine", material, "--dtm", str(dtm), "--count", str(count),
            "--max", str(cap), "--themes", "--solutions", "--jsonl"]
    if strict:
        args += ["--starts", "2", "--ends", "2"]
    return run_jsonl(binary, args, tables)


def strict_dual_depth(binary: str, tables: str, material: str, stats: dict):
    """The deepest dtm holding a dual whose solutions differ in both their
    first and their last move, and its candidates.

    Walks downward because the deepest dual depth is almost always empty under
    that filter -- the two solutions there share a first or a last move."""
    for dtm in depths_with(stats, 2):
        rows = mine(binary, tables, material, dtm, 2, strict=True)
        if rows:
            return dtm, rows
    return None, []
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_build_problems.py -v`
Expected: 10 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/build_problems.py tests/repo/test_build_problems.py
git add tools/build_problems.py tests/repo/test_build_problems.py
git commit -m "build_problems: mine candidates, walking down to a strict dual depth"
```

---

### Task 5: Assembling one material, with validation

**Files:**
- Modify: `tools/build_problems.py`
- Test: `tests/repo/test_build_problems.py`

**Interfaces:**
- Consumes: `mine`, `strict_dual_depth`, `deepest_depth` (Tasks 3–4); `pick` from `tools/problem_picker.py`; `expand_solution` from `tools/build_site_data.py`; `assess(fen, solution)` from `tools/published_problems.py:305`.
- Produces: `load_module(path: Path, name: str)`, `attribution(deepest_rows: List[dict]) -> Dict[str, dict]`, `problem_record(cand: dict, attrib: Dict[str, dict]) -> dict`, `build_material(binary, tables, material, stats, row, attrib) -> dict`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_build_problems.py`:

```python
import pytest

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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_build_problems.py -v -k "attribution or record"`
Expected: FAIL — `module 'build_problems' has no attribute 'attribution'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/build_problems.py`:

```python
def load_module(path: Path, name: str):
    """Import a sibling tool. `tools/` is not a package, so this is the only way
    to reuse code across these scripts -- the same trick tests/repo uses."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


def attribution(deepest_rows: List[Dict]) -> Dict[str, Dict]:
    """The published-problem fields from docs/DEEPEST.json, keyed by FEN.

    Output of PRs #30-32. Only 26 of 234 entries are published and problems 2,
    3 and every dual are positions that file has never seen, so most lookups
    miss -- that is expected, not a failure."""
    return {r["fen"]: r for r in deepest_rows}


def stipulation(dtm: int) -> str:
    """`h#n` from a ply distance. Odd dtm means White to move: the .5 case."""
    return f"h#{dtm // 2}" if dtm % 2 == 0 else f"h#{dtm // 2}.5"


def problem_record(cand: Dict, attrib: Dict[str, Dict]) -> Dict:
    """One problem as the site reads it: solutions expanded ply by ply,
    themes as mined, attribution carried over, quality recomputed.

    Raises ValueError if a solution is illegal, ambiguous or does not mate --
    never something to ship silently."""
    site_data = load_module(ROOT / "tools/build_site_data.py", "build_site_data")
    published = load_module(ROOT / "tools/published_problems.py", "published_problems")

    solutions = [site_data.expand_solution(cand["fen"], " ".join(line))
                 for line in cand["solutions"]]
    row = attrib.get(cand["fen"], {})
    return {
        "fen": cand["fen"],
        "dtm": cand["dtm"],
        "stipulation": stipulation(cand["dtm"]),
        "count": cand["count"],
        "starts": cand["starts"],
        "ends": cand["ends"],
        "themes": cand["themes"],
        "solutions": solutions,
        "published": row.get("published"),
        "published_by": row.get("published_by"),
        "quality": published.assess(cand["fen"], " ".join(cand["solutions"][0])),
        "alternative": row.get("alternative"),
    }
```

`assess(fen: str, solution: str) -> dict` is already a module-level function in
`tools/published_problems.py` (line 305) returning exactly
`{"capture_first", "check", "legal"}` — no extraction is needed. That module
carries `from __future__ import annotations`, so importing it under the 3.9
floor is safe despite the `dict | None` annotations further down. Its siblings
`rank(q)` and `quality_note(q)` are what Part 2 will use to phrase the caveat
on a page; do not duplicate that logic here.

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_build_problems.py -v`
Expected: 14 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/build_problems.py tests/repo/test_build_problems.py
git add tools/build_problems.py tools/published_problems.py tests/repo/test_build_problems.py
git commit -m "build_problems: assemble a problem record, validating every line"
```

---

### Task 6: `build_material`, markers, and the CLI

**Files:**
- Modify: `tools/build_problems.py`
- Test: `tests/repo/test_build_problems.py`

**Interfaces:**
- Consumes: everything from Tasks 3–5.
- Produces: `build_material(...) -> dict` (the per-material document from the spec), `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_build_problems.py`:

```python
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
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_build_problems.py -v -k build_material`
Expected: FAIL — `module 'build_problems' has no attribute 'build_material'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/build_problems.py`:

```python
def build_material(binary: str, tables: str, material: str, stats: dict,
                   row: dict, attrib: Dict[str, Dict]) -> Dict:
    """The document for one material: statistics, both problem classes, notes.

    A marker material -- one provably holding no helpmate at all -- is not an
    error and is not mined. 68 of the 302 tables are markers."""
    picker = load_module(ROOT / "tools/problem_picker.py", "problem_picker")

    unique_dtm = deepest_depth(stats, 1)
    doc = {
        "material": material,
        "pieces": row["pieces"],
        "stats": {
            "max_dtm": row["max_dtm"],
            "deepest_unique_dtm": unique_dtm,
            "unique_at_depth": 0,
            "deepest_dual_dtm": deepest_depth(stats, 2),
            "strict_dual_dtm": None,
            "plane_size": stats.get("plane_size"),
            "solvable": row["solvable"],
            "unique": row["unique"],
            "size_bytes": row["size_bytes"],
            "saturated_at_max": False,
            "dtm_histogram": stats.get("dtm_histogram", {}),
        },
        "unique": [], "duals": [], "notes": [],
        "candidates_considered": 0, "candidates_total": 0,
    }

    if unique_dtm is None:
        doc["notes"].append("No helpmate exists in this material.")
        return doc

    cands = mine(binary, tables, material, unique_dtm, 1)
    doc["candidates_considered"] = len(cands)
    doc["candidates_total"] = sum(
        int(stats["uniqueness"][s].get(str(unique_dtm), {}).get("1", 0))
        for s in ("wtm", "btm"))
    doc["stats"]["unique_at_depth"] = doc["candidates_total"]

    seed = next((f for f in attrib if any(c["fen"] == f for c in cands)), None)
    chosen, notes = picker.pick(cands, limit=3, seed_fen=seed)
    doc["unique"] = [problem_record(c, attrib) for c in chosen]
    doc["notes"] += notes

    dual_dtm, dual_cands = strict_dual_depth(binary, tables, material, stats)
    doc["stats"]["strict_dual_dtm"] = dual_dtm
    chosen, notes = picker.pick(dual_cands, limit=3)
    doc["duals"] = [problem_record(c, attrib) for c in chosen]
    doc["notes"] += notes
    return doc
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_build_problems.py -v`
Expected: 17 passed.

- [ ] **Step 5: Write the CLI**

Append to `tools/build_problems.py`:

```python
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser("build_problems")
    ap.add_argument("--tables", required=True)
    ap.add_argument("--binary", default="./build/helpmate")
    ap.add_argument("--out", default="site/data")
    ap.add_argument("--material", action="append", default=[],
                    help="restrict to these materials (repeatable)")
    a = ap.parse_args(argv)

    out = Path(a.out)
    (out / "material").mkdir(parents=True, exist_ok=True)

    deepest_rows = json.loads((ROOT / "docs/DEEPEST.json").read_text())
    attrib = attribution(deepest_rows)
    rows = {r["material"]: r
            for r in json.loads((out / "materials.json").read_text())}

    index: List[Dict] = []
    themes: Dict[str, List[Dict]] = {}
    failures = 0
    for sc in sorted(Path(a.tables).glob("*.stats.json")):
        material = sc.name[: -len(".stats.json")]
        if a.material and material not in a.material:
            continue
        if material not in rows:
            print(f"  {material}: not in materials.json, skipped", file=sys.stderr)
            continue
        try:
            doc = build_material(a.binary, a.tables, material,
                                 json.loads(sc.read_text()), rows[material], attrib)
        except Exception as exc:                        # reported per material, not hidden
            print(f"  {material}: FAILED -- {exc}", file=sys.stderr)
            failures += 1
            continue

        (out / "material" / f"{material}.json").write_text(json.dumps(doc, indent=1))
        for kind in ("unique", "duals"):
            for p in doc[kind]:
                for t in p["themes"]:
                    themes.setdefault(t, []).append({
                        "material": material, "fen": p["fen"], "dtm": p["dtm"],
                        "stipulation": p["stipulation"],
                        "kind": "unique" if kind == "unique" else "dual"})
        index.append({
            "material": material, "pieces": doc["pieces"],
            "stipulation": (stipulation(doc["stats"]["deepest_unique_dtm"])
                            if doc["stats"]["deepest_unique_dtm"] else None),
            "unique": len(doc["unique"]), "duals": len(doc["duals"]),
            "has_table": doc["stats"]["deepest_unique_dtm"] is not None,
        })
        print(f"  {material}: {len(doc['unique'])} unique, {len(doc['duals'])} dual",
              file=sys.stderr)

    (out / "themes.json").write_text(json.dumps(
        {t: {"count": len(ps), "problems": ps} for t, ps in sorted(themes.items())},
        indent=1))
    (out / "index.json").write_text(json.dumps(index, indent=1))
    print(f"wrote {len(index)} materials, {len(themes)} themes, "
          f"{failures} failure(s)", file=sys.stderr)
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 6: Smoke-test the CLI against the real corpus on three materials**

Run:
```bash
python3 tools/build_problems.py --tables ~/tb --material KQvk --material KPvk \
    --material KRvkbn --out /tmp/bp-smoke
```
Expected: three lines on stderr, `KQvk: 1 unique, ...` among them (its three positions collapse to one idea). Then check the output is real:
```bash
python3 -c "
import json
d = json.load(open('/tmp/bp-smoke/material/KQvk.json'))
assert len(d['unique']) == 1, d['unique']
assert d['notes'][0].startswith('Only one distinct idea'), d['notes']
assert d['stats']['strict_dual_dtm'] == 7, d['stats']
print('ok:', d['notes'])"
```

- [ ] **Step 7: Lint, typecheck, full repo tests, commit**

```bash
ruff check tools/build_problems.py tools/problem_picker.py tests/repo/
make test-repo
git add tools/build_problems.py tests/repo/test_build_problems.py
git commit -m "build_problems: per-material documents, theme index, CLI"
```

---

### Task 7: Generate and commit the real data

**Files:**
- Create: `site/data/material/*.json` (302), `site/data/themes.json`, `site/data/index.json`
- Modify: `Makefile`, `docs/BUILD.md`

**Interfaces:**
- Consumes: the CLI from Task 6.
- Produces: the committed JSON Part 2 renders from.

- [ ] **Step 1: Run the full build against the corpus**

Run: `time python3 tools/build_problems.py --tables ~/tb --out site/data 2>&1 | tee /tmp/build-problems.log`
Expected: roughly 20–40 minutes; the last line reports `0 failure(s)`. If any material failed, read the reason in the log and fix the cause before continuing — a failure means a claim did not survive re-probing, which is exactly what the validation is for.

- [ ] **Step 2: Sanity-check the corpus-wide output**

```bash
python3 -c "
import json, glob
docs = [json.load(open(f)) for f in glob.glob('site/data/material/*.json')]
markers = [d for d in docs if d['stats']['deepest_unique_dtm'] is None]
withdual = [d for d in docs if d['duals']]
print(f'{len(docs)} materials, {len(markers)} markers, {len(withdual)} with duals')
print('three unique:', sum(1 for d in docs if len(d['unique']) == 3))
print('one unique  :', sum(1 for d in docs if len(d['unique']) == 1))
themes = json.load(open('site/data/themes.json'))
print(f'{len(themes)} themes, biggest:', max(themes.items(), key=lambda kv: kv[1]['count'])[0])
assert len(docs) == 302, len(docs)
assert len(markers) == 68, len(markers)
"
```
Expected: 302 materials, 68 markers. The spec predicts ~188 materials can show three unique problems; a wildly different number means the picker is miscalibrated — stop and report rather than committing it.

- [ ] **Step 3: Add a Makefile target**

In `Makefile`, next to `docs-deepest` (line 224), add:

```make
# The per-material problem data behind the site's material pages. Needs a
# corpus, like docs-deepest -- the output is committed because the Pages
# workflow has no tables. TABLES defaults to ~/tb.
TABLES ?= $(HOME)/tb
site-data: build
	python3 tools/build_problems.py --tables $(TABLES) --binary $(BUILD)/helpmate \
	  --out site/data
```

- [ ] **Step 4: Document it**

In `docs/BUILD.md`, in the section covering `docs-deepest`, add a paragraph naming `make site-data`, that it takes 20–40 minutes against a full corpus, that its output is committed, and that `--material` restricts it for a quick check.

- [ ] **Step 5: Commit the tooling and the data separately**

The data commit is large and mechanical; keeping it apart keeps the tooling commit reviewable.

```bash
git add Makefile docs/BUILD.md
git commit -m "build: make site-data, and document what it costs"
git add site/data/index.json site/data/themes.json site/data/material
git commit -m "data: deepest unique and dual problems for all 302 materials"
```

---

## Self-review

**Spec coverage.** R1 → Tasks 1, 2, 6 (deepest depth, picker, `build_material`). R2 → Tasks 3, 4, 6 (`depths_with`, `strict_dual_depth`, both depths recorded). R3 → Task 5 (`themes` straight from `mine --themes`). Attribution carried / quality recomputed → Task 5. Validation before writing → Task 5 (`expand_solution` raises) and Task 6 Step 6. Marker materials → Task 6. `candidates_considered` / `candidates_total` → Task 6. `themes.json` and `index.json` → Task 6 CLI. R4 and R5 are Part 2 and deliberately absent here.

**Known gap, deliberate:** the spec's "every selected problem is re-probed and must report the dtm/count/starts/ends the entry claims" is satisfied by mining *with* those filters — a position returned by `mine --dtm D --count 1` provably has that dtm and count — rather than by a second `probe` call per problem. That is the same guarantee for ~1,500 fewer subprocesses. `expand_solution` still independently verifies every line ends in mate.

**Placeholder scan:** none. Every code step carries the actual code. Task 5 Step 3 contains one conditional instruction (extract `grade()` if it is not already module-level), which is a real branch in the existing code that the implementer must look at, not a deferred decision.

**Type consistency:** `pick(candidates, limit, seed_fen) -> (chosen, notes)` is defined in Task 2 and used in Task 6. `mine(binary, tables, material, dtm, count, strict, cap)` defined in Task 4, monkeypatched with the same signature in Task 6. `problem_record(cand, attrib)` defined in Task 5, used in Task 6. `stipulation(dtm)` defined in Task 5, used in Task 6's CLI. `deepest_depth` / `depths_with` defined in Task 3, used in Tasks 4 and 6.
