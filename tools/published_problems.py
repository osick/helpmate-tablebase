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

Entries without a match are left exactly as they were, and the JSON is only
rewritten when something changed, so running this with a file that contains
none of the showcase (the case on 2026-09-13: a database of h#2 against a
showcase of h#6..h#17) is a no-op that says so.
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


def find_alternative(entry: dict, index: PublishedIndex,
                     mine: Callable[[str, int, int], list[str]],
                     describe_fn: Callable[[str], dict],
                     max_hits: int = 5000) -> dict | None:
    """The first unique-solution position of the entry's material at its
    depth that is neither the entry itself nor published, described."""
    own = canon(entry["fen"])
    for fen in mine(entry["material"], entry["dtm"], max_hits):
        k = canon(fen)
        if k == own or index.lookup(fen):
            continue
        return describe_fn(fen)
    return None


def published_record(p: Published) -> dict:
    return {"id": p.id, "author": p.author, "sources": p.sources,
            "stipulation": p.stipulation, "fen": p.fen}


def annotate(rows: list[dict], index: PublishedIndex,
             mine: Callable[[str, int, int], list[str]],
             describe_fn: Callable[[str], dict]) -> tuple[int, int]:
    """Set `published` / `alternative` on matching entries, drop them from
    the rest. Returns (entries matched, entries changed)."""
    matched = changed = 0
    for r in rows:
        before = (r.get("published"), r.get("alternative"))
        hits = index.lookup(r["fen"])
        if hits:
            matched += 1
            r["published"] = [published_record(p) for p in hits]
            alt = find_alternative(r, index, mine, describe_fn)
            if alt:
                r["alternative"] = alt
            else:
                r.pop("alternative", None)
        else:
            r.pop("published", None)
            r.pop("alternative", None)
        if (r.get("published"), r.get("alternative")) != before:
            changed += 1
    return matched, changed


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--published", required=True, help="the published-problems file")
    ap.add_argument("--data", default="docs/DEEPEST.json")
    ap.add_argument("--out", default=None, help="default: rewrite --data in place")
    ap.add_argument("--tables", default=str(Path.home() / "tb"))
    ap.add_argument("--binary", default="./build/helpmate")
    ap.add_argument("--max-hits", type=int, default=5000,
                    help="how many unique positions to scan for an alternative")
    a = ap.parse_args()

    problems = parse(Path(a.published).read_text(encoding="latin-1"))
    index = PublishedIndex(problems)
    rows = json.loads(Path(a.data).read_text())
    print(f"{len(problems)} published problems indexed; {len(rows)} showcase entries",
          file=sys.stderr)

    matched, changed = annotate(
        rows, index,
        mine=lambda mat, dtm, n: mine_unique(a.binary, a.tables, mat, dtm, n),
        describe_fn=lambda fen: describe(a.binary, a.tables, fen),
    )
    for r in rows:
        if r.get("published"):
            p = r["published"][0]
            alt = r.get("alternative")
            print(f"  {r['material']} {hn(r['dtm'])}: published -- {p['author']}, "
                  f"{p['sources'][0] if p['sources'] else '?'} ({p['id']})"
                  + (f"; alternative {alt['fen']}" if alt else "; no unpublished alternative found"),
                  file=sys.stderr)
    out = Path(a.out) if a.out else Path(a.data)
    if changed or (a.out and out != Path(a.data)):
        out.write_text(json.dumps(rows, indent=1))
        print(f"wrote {out}: {matched} published, {changed} entries changed", file=sys.stderr)
    else:
        print(f"{matched} showcase entries are published; nothing to change in {a.data}",
              file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
