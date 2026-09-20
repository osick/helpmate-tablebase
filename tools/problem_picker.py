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
            cur.append(
                min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (tok != other))
            )
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
