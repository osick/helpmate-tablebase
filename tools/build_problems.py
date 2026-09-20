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

import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]

# `mine` defaults to --max 10. Ask for enough candidates that the picker has
# room to find three dissimilar ones, without scanning a plane into memory.
CANDIDATE_CAP = 500


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
