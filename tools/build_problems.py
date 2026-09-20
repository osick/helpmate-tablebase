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

from pathlib import Path
from typing import List, Optional

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
