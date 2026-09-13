#!/usr/bin/env python3
"""Cross the DEEPEST showcase with a file of published helpmates.

    python3 tools/published_problems.py --published sampledata/hmatt_lower7.fen \\
        --data docs/DEEPEST.json --tables ~/tb --binary ./build/helpmate

The published file is a plain-text database, one block per problem, blank
line between blocks::

    No. 17 (id: P0003471)
    Steudel, Theodor
    source 1: Die Schwalbe, No. 2746, 07-08/1968
    8/8/8/8/1tt5/4k3/2B5/T3K3
    stipulation: h#2
    solution:
    1.Tf4 Td1 2.Tbe4 Td3#

Piece letters are German (K D T L S B = king queen rook bishop knight pawn;
case is colour) and the board is given without side to move. The file is
Latin-1 with CRLF line ends, and umlauts in names and sources are written as
TeX shorthands (`Jen"o`, `Teht"av"aniekat`, `Gla"s`); those are turned back
into letters here.

Two things happen for every DEEPEST entry:

1. If its position is published -- the same board under ANY mirroring: all
   eight board symmetries for a pawnless position, the two that keep pawns
   moving up the board otherwise -- the entry gets a `published` list with
   the author, sources, stipulation and id of every matching problem.
2. For such an entry the tablebase is asked for another position of the same
   material with a unique solution at the same depth, the first one that is
   NOT published (again under every mirroring) becomes the entry's
   `alternative`: fen, solution and themes, ready to be shown next to the
   published one as an unpublished problem of the same stipulation.

Every position shown -- the showcase's own and every alternative -- is also
graded as a chess problem (`quality`):

* 2a: the solution begins with a capture;
* 2b: the side to move is in check in the diagram;
* 3: the diagram has no legal last move, i.e. no legal position with the
  other side to move leads to it by a legal move. That is decided exactly
  for one retraction: every quiet move, uncapture of any piece, and
  unpromotion (with or without capture) by the side that just moved is
  tried, and the predecessor must be legal and the move legal from it. En
  passant is not retracted. A diagram with the side NOT to move in check is
  illegal outright.

Ranking, best first: no weakness, check only, capture only, both, illegal.
An unpublished showcase position with a weakness is replaced by the
best-ranked unpublished unique position of the same material and depth the
tablebase can offer, if that one ranks better; otherwise it stays and the
documents say what is wrong with it. A published showcase position is never
replaced (it is the published problem); its alternative is chosen by the
same ranking. `published_by` (`Sheglow (1998)`) is stored for the index
tables.

The JSON is only rewritten when something changed.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

import chess

sys.path.insert(0, str(Path(__file__).resolve().parent))
from deepest_lib import hn  # noqa: E402

GERMAN = {"K": "K", "D": "Q", "T": "R", "L": "B", "S": "N", "B": "P"}
UMLAUTS = {'"a': "ä", '"o': "ö", '"u': "ü", '"A': "Ä", '"O': "Ö", '"U': "Ü", '"s': "ß"}


def detex(text: str) -> str:
    """`Ban, Jen"o` -> `Ban, Jenö`; `Gla"s` -> `Glaß`. Only the German
    umlaut shorthands: anything else stays as written."""
    for k, v in UMLAUTS.items():
        text = text.replace(k, v)
    return text
BLOCK_HEAD = re.compile(r"No\.\s*(\d+)\s*\(id:\s*([^)]+)\)")
BOARD_LINE = re.compile(r"[KDTLSBkdtlsb1-8/]+")
PLAIN_STIP = re.compile(r"h#(\d+)(\.5)?\s*$")


@dataclass
class Published:
    no: str
    id: str
    author: str
    sources: list[str]
    fen: str          # board field only, English letters
    stipulation: str  # verbatim, e.g. "h#2*" or "h#2 Duplex"
    solution: str
    text: str = field(repr=False, default="")


def german_to_english(board: str) -> str:
    """`7k/6bb/8/8/8/3b4/8/4K2T` -> `7k/6pp/8/8/8/3p4/8/4K2R`."""
    out = []
    for ch in board:
        up = ch.upper()
        if up in GERMAN:
            out.append(GERMAN[up] if ch.isupper() else GERMAN[up].lower())
        else:
            out.append(ch)
    return "".join(out)


def parse(text: str) -> list[Published]:
    """Every well-formed block of the published-problems file."""
    out = []
    for block in re.split(r"\n\s*\n", text):
        lines = [ln.rstrip() for ln in block.strip().splitlines()]
        if not lines:
            continue
        m = BLOCK_HEAD.match(lines[0])
        if not m:
            continue
        author = detex(lines[1].strip()) if len(lines) > 1 else ""
        sources = [detex(ln.split(":", 1)[1].strip()) for ln in lines[2:]
                   if ln.startswith("source")]
        board = next((ln.strip() for ln in lines[2:]
                      if BOARD_LINE.fullmatch(ln.strip()) and ln.count("/") == 7), None)
        if board is None:
            continue
        stip = detex(next((ln[len("stipulation:"):].strip() for ln in lines
                           if ln.startswith("stipulation:")), ""))
        sol = block[block.find("solution:") + len("solution:"):].strip() if "solution:" in block else ""
        out.append(Published(m.group(1), m.group(2).strip(), author, sources,
                             german_to_english(board), stip, sol, block))
    return out


# --------------------------------------------------------------------------
# symmetry


def board_rows(board: str) -> list[list[str]]:
    rows = []
    for rank in board.split("/"):
        row: list[str] = []
        for ch in rank:
            row += ["."] * int(ch) if ch.isdigit() else [ch]
        rows.append(row)
    return rows


def rows_key(rows: list[list[str]]) -> str:
    return "/".join("".join(r) for r in rows)


def mirrorings(rows: list[list[str]]) -> list[list[list[str]]]:
    """Every board the position can be shown as. Pawns move up the board, so
    with a pawn only the left-right mirror keeps the problem the same; without
    one, all eight symmetries of the square do."""
    def flip_h(b):
        return [list(reversed(r)) for r in b]

    def flip_v(b):
        return list(reversed(b))

    def transpose(b):
        return [list(x) for x in zip(*b)]

    out = [rows, flip_h(rows)]
    if not any(c in "Pp" for r in rows for c in r):
        t = transpose(rows)
        out += [flip_v(rows), flip_v(flip_h(rows)), t, flip_h(t), flip_v(t), flip_v(flip_h(t))]
    return out


def canon(fen_or_board: str) -> str:
    """A key that is the same for every mirroring of the position."""
    return min(rows_key(v) for v in mirrorings(board_rows(fen_or_board.split()[0])))


class PublishedIndex:
    def __init__(self, problems: list[Published]):
        self.by_key: dict[str, list[Published]] = defaultdict(list)
        for p in problems:
            self.by_key[canon(p.fen)].append(p)

    def lookup(self, fen: str) -> list[Published]:
        return self.by_key.get(canon(fen), [])

    def __len__(self) -> int:
        return sum(len(v) for v in self.by_key.values())


# --------------------------------------------------------------------------
# the tablebase side


def run(binary: str, args: list[str], tables: str) -> str:
    return subprocess.run([binary, *args, "--tables", tables],
                          capture_output=True, text=True, check=True).stdout


def mine_unique(binary: str, tables: str, material: str, dtm: int, max_hits: int) -> list[str]:
    out = run(binary, ["mine", material, "--dtm", str(dtm), "--count", "1",
                       "--max", str(max_hits)], tables)
    return [ln.strip() for ln in out.splitlines() if ln.strip()]


def describe(binary: str, tables: str, fen: str) -> dict:
    """solution (one line of SAN) and themes of a unique-solution position."""
    solution = run(binary, ["line", fen], tables).strip().splitlines()[0]
    themes: list[str] = []
    for ln in run(binary, ["probe", fen, "--themes"], tables).splitlines():
        if ln.startswith("themes:"):
            rest = ln[len("themes:"):].strip()
            themes = [] if not rest or rest.startswith("(") else rest.split()
    return {"fen": fen, "solution": solution, "themes": themes}


YEAR = re.compile(r"(?<!\d)(1[89]\d\d|20\d\d)(?!\d)")


def published_by(p: "Published | dict") -> str:
    """`Sheglow (1998)`; `Abdurahmanovic & Becker (2006)`; `unknown (1987)`."""
    author = p.author if isinstance(p, Published) else p.get("author", "")
    sources = p.sources if isinstance(p, Published) else p.get("sources", [])
    names = []
    for part in author.split(";"):
        last = part.split(",")[0].strip()
        names.append(last if last and last != "?" else "unknown")
    who = " & ".join(names) if names else "unknown"
    years = [m.group(1) for src in sources for m in YEAR.finditer(src)]
    return f"{who} ({years[0]})" if years else who


# --------------------------------------------------------------------------
# quality of a position as a chess problem


def legal_last_move(board: chess.Board) -> bool:
    """Does a legal position with the other side to move lead to `board` by
    one legal move? Exact over quiet moves, uncaptures (any piece) and
    unpromotions, with or without capture; en passant is not retracted."""
    if not board.is_valid():
        return False
    mover = not board.turn
    opp = board.turn
    target = board.board_fen()
    uncaptures = [None, chess.QUEEN, chess.ROOK, chess.BISHOP, chess.KNIGHT, chess.PAWN]
    for t in chess.SquareSet(board.occupied_co[mover]):
        piece = board.piece_at(t)
        last_rank = 7 if mover == chess.WHITE else 0
        back = -8 if mover == chess.WHITE else 8  # one step back for this side's pawns
        # (origin square, piece that stood there, promotion, capture required)
        origins: list[tuple[int, int, int | None, bool]] = []
        if piece.piece_type == chess.PAWN:
            f = t + back
            if 0 <= f < 64:
                origins.append((f, chess.PAWN, None, False))
                for df in (-1, 1):
                    g = f + df
                    if 0 <= g < 64 and abs(chess.square_file(g) - chess.square_file(t)) == 1:
                        origins.append((g, chess.PAWN, None, True))
            if chess.square_rank(t) == (3 if mover == chess.WHITE else 4):
                origins.append((t + 2 * back, chess.PAWN, None, False))
        else:
            for f in chess.SQUARES:
                if f != t and board.piece_at(f) is None:
                    origins.append((f, piece.piece_type, None, False))
            if chess.square_rank(t) == last_rank and piece.piece_type != chess.KING:
                f = t + back
                if 0 <= f < 64:
                    origins.append((f, chess.PAWN, piece.piece_type, False))
                    for df in (-1, 1):
                        g = f + df
                        if 0 <= g < 64 and abs(chess.square_file(g) - chess.square_file(t)) == 1:
                            origins.append((g, chess.PAWN, piece.piece_type, True))
        for f, ptype, promo, must_capture in origins:
            for cap in uncaptures:
                if must_capture and cap is None:
                    continue
                if cap == chess.PAWN and chess.square_rank(t) in (0, 7):
                    continue
                prev = chess.Board(None)
                prev.set_piece_map(board.piece_map())
                prev.remove_piece_at(t)
                prev.set_piece_at(f, chess.Piece(ptype, mover))
                if cap is not None:
                    prev.set_piece_at(t, chess.Piece(cap, opp))
                prev.turn = mover
                if not prev.is_valid():
                    continue
                mv = chess.Move(f, t, promotion=promo)
                if mv not in prev.legal_moves:
                    continue
                prev.push(mv)
                if prev.board_fen() == target:
                    return True
    return False


def assess(fen: str, solution: str) -> dict:
    """The weaknesses of a problem: see the module docstring."""
    board = chess.Board(fen)
    first = solution.split()[0] if solution.split() else ""
    return {
        "capture_first": "x" in first,
        "check": board.is_check(),
        "legal": board.is_valid() and legal_last_move(board),
    }


def rank(q: dict) -> int:
    """0 best. Check is the milder weakness, a first-move capture the more
    dramatic one, an illegal diagram the worst."""
    if not q["legal"]:
        return 4
    if q["capture_first"] and q["check"]:
        return 3
    if q["capture_first"]:
        return 2
    if q["check"]:
        return 1
    return 0


def quality_note(q: dict) -> str:
    """Empty for a well-formed problem, else what is wrong, for the documents."""
    if not q["legal"]:
        return "the diagram has no legal last move, so it cannot arise in a game"
    parts = []
    if q["check"]:
        parts.append("the side to move is in check in the diagram")
    if q["capture_first"]:
        parts.append("the solution begins with a capture")
    return "; ".join(parts)


def best_candidate(entry: dict, index: PublishedIndex,
                   mine: Callable[[str, int, int], list[str]],
                   describe_fn: Callable[[str], dict],
                   max_hits: int = 5000, better_than: int = 5) -> dict | None:
    """The best-ranked unique-solution position of the entry's material at
    its depth that is neither the entry itself nor published; None if no
    candidate ranks better than `better_than`. Cheap checks (check, legal
    last move) come from the FEN alone; the solution is fetched only for
    candidates that could still win, and the scan stops at a flawless one."""
    own = canon(entry["fen"])
    best: dict | None = None
    best_rank = min(better_than, 4)  # an illegal diagram is never worth offering
    for fen in mine(entry["material"], entry["dtm"], max_hits):
        if canon(fen) == own or index.lookup(fen):
            continue
        board = chess.Board(fen)
        legal = board.is_valid() and legal_last_move(board)
        floor = 4 if not legal else (1 if board.is_check() else 0)
        if floor >= best_rank:
            continue
        d = describe_fn(fen)
        q = assess(fen, d["solution"])
        r = rank(q)
        if r < best_rank:
            best, best_rank = {**d, "quality": q}, r
            if r == 0:
                break
    return best


def annotate(rows: list[dict], index: PublishedIndex,
             mine: Callable[[str, int, int], list[str]],
             describe_fn: Callable[[str], dict],
             max_hits: int = 5000, replace: bool = True) -> tuple[int, int, int]:
    """Set `published`/`published_by`/`alternative`/`quality` on every entry.
    Returns (entries published, entries whose position was replaced, entries
    changed)."""
    matched = replaced = changed = 0
    for r in rows:
        before = json.dumps({k: r.get(k) for k in
                             ("fen", "published", "published_by", "alternative", "quality")},
                            sort_keys=True)
        hits = index.lookup(r["fen"])
        r["quality"] = assess(r["fen"], r["solution"])
        if hits:
            matched += 1
            r["published"] = [published_record(p) for p in hits]
            r["published_by"] = published_by(hits[0])
            alt = best_candidate(r, index, mine, describe_fn, max_hits)
            if alt:
                r["alternative"] = alt
            else:
                r.pop("alternative", None)
        else:
            for k in ("published", "published_by", "alternative"):
                r.pop(k, None)
            if replace and rank(r["quality"]) > 0:
                better = best_candidate(r, index, mine, describe_fn, max_hits,
                                        better_than=rank(r["quality"]))
                if better:
                    r.setdefault("replaced_from", r["fen"])
                    r["fen"], r["solution"] = better["fen"], better["solution"]
                    r["themes"], r["quality"] = better["themes"], better["quality"]
                    r["probe"] = f"dtm={r['dtm']} ({hn(r['dtm'])}) count=1"
                    replaced += 1
        after = json.dumps({k: r.get(k) for k in
                            ("fen", "published", "published_by", "alternative", "quality")},
                           sort_keys=True)
        if after != before:
            changed += 1
    return matched, replaced, changed


def published_record(p: Published) -> dict:
    return {"id": p.id, "author": p.author, "sources": p.sources,
            "stipulation": p.stipulation, "fen": p.fen}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--published", required=True, help="the published-problems file")
    ap.add_argument("--data", default="docs/DEEPEST.json")
    ap.add_argument("--out", default=None, help="default: rewrite --data in place")
    ap.add_argument("--tables", default=str(Path.home() / "tb"))
    ap.add_argument("--binary", default="./build/helpmate")
    ap.add_argument("--max-hits", type=int, default=5000,
                    help="how many unique positions to scan for an alternative")
    ap.add_argument("--keep-positions", action="store_true",
                    help="never replace a weak unpublished showcase position")
    a = ap.parse_args()

    problems = parse(Path(a.published).read_text(encoding="latin-1"))
    index = PublishedIndex(problems)
    rows = json.loads(Path(a.data).read_text())
    print(f"{len(problems)} published problems indexed; {len(rows)} showcase entries",
          file=sys.stderr)

    ap_replace = not a.keep_positions
    matched, replaced, changed = annotate(
        rows, index,
        mine=lambda mat, dtm, n: mine_unique(a.binary, a.tables, mat, dtm, n),
        describe_fn=lambda fen: describe(a.binary, a.tables, fen),
        max_hits=a.max_hits, replace=ap_replace,
    )
    weak = 0
    for r in rows:
        note = quality_note(r["quality"])
        if r.get("published"):
            alt = r.get("alternative")
            print(f"  {r['material']} {hn(r['dtm'])}: published by {r['published_by']}"
                  + (f"; alternative {alt['fen']} ({quality_note(alt['quality']) or 'well formed'})"
                     if alt else "; no unpublished alternative found"), file=sys.stderr)
        elif r.get("replaced_from"):
            print(f"  {r['material']} {hn(r['dtm'])}: replaced {r['replaced_from']} -> {r['fen']}"
                  f" ({note or 'well formed'})", file=sys.stderr)
        if note:
            weak += 1
            print(f"  {r['material']} {hn(r['dtm'])}: weakness stays -- {note}", file=sys.stderr)
    out = Path(a.out) if a.out else Path(a.data)
    if changed or (a.out and out != Path(a.data)):
        out.write_text(json.dumps(rows, indent=1))
        print(f"wrote {out}: {matched} published, {replaced} positions replaced, "
              f"{weak} still with a weakness, {changed} entries changed", file=sys.stderr)
    else:
        print(f"{matched} showcase entries are published, {weak} with a weakness; "
              f"nothing to change in {a.data}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
