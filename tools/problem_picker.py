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

from typing import Dict, List, Optional, Sequence, Tuple


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


def pick(
    candidates: List[Dict],
    limit: int = 3,
    seed_fen: Optional[str] = None,
) -> Tuple[List[Dict], List[str]]:
    """Up to `limit` candidates that are not each other's twins, plus notes.

    Greedy max-min: seed, then repeatedly take whatever is farthest from
    everything already chosen, stopping when no non-twin remains."""
    if not candidates:
        return [], ["No position at this depth satisfies the filter."]

    pool = list(candidates)
    seed = next((c for c in pool if c["fen"] == seed_fen), pool[0])
    chosen = [seed]
    pool.remove(seed)

    while pool and len(chosen) < limit:
        fresh = [c for c in pool if not any(same_idea(c, k) for k in chosen)]
        if not fresh:
            break
        best = max(fresh, key=lambda c: min(distance(c, k) for k in chosen))
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
