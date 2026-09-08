"""Build the JSON the static showcase (site/) reads.

    python3 tools/build_site_data.py --tables ~/tb [--binary helpmate] [--out site/data]

Run by hand against a corpus, like tools/deepest_showcase.py; the output is
committed, because the GitHub Pages workflow has no tables. Four files:

  deepest.json    docs/DEEPEST.json with every solution expanded ply by ply
  puzzles.json    the dashboard's puzzles.epd, each with its one solution
  materials.json  one row per table from the stats sidecars and file sizes
  corpus.json     the totals the front page states

Every solution ply carries its SAN, its from/to squares (UCI, promotion piece
appended) and the FEN after the move. The browser therefore needs no chess
logic at all: stepping through a line is setting positions, and grading a
puzzle move is comparing two UCI strings. python-chess does the SAN parsing
here, once.

`helpmate line` is called once per puzzle. A puzzle was mined with count = 1,
so the one line it prints is the solution; a puzzle for which the binary
prints anything else is dropped with a note rather than shipped wrong.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PUZZLES_EPD = ROOT / "src/packages/web/helpmate_web/static/puzzles.epd"
DEEPEST_JSON = ROOT / "docs/DEEPEST.json"


def piece_count(material: str) -> int:
    """Same rule as helpmate_server.storage._piece_count: every letter but the separator."""
    return sum(1 for c in material if c != "v")


def expand_solution(fen: str, san_line: str) -> list[dict]:
    """[{san, uci, fen}] for each ply of `san_line` played from `fen`.

    Raises ValueError on an illegal or ambiguous SAN, which would mean the
    line and the position disagree -- never something to ship silently."""
    import chess

    board = chess.Board(fen)
    plies = []
    for san in san_line.split():
        try:
            move = board.parse_san(san)
        except ValueError as exc:
            raise ValueError(f"{fen}: cannot play {san!r} at ply {len(plies) + 1}: {exc}") from exc
        board.push(move)
        plies.append({"san": san, "uci": move.uci(), "fen": board.fen()})
    if not board.is_checkmate():
        raise ValueError(f"{fen}: line {san_line!r} does not end in checkmate")
    return plies


def parse_epd(text: str) -> list[dict]:
    """Mirror of site/js/lib and the dashboard's parseEpd: fen, dtm (plies), id."""
    out = []
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        head, *ops = line.split(";")
        fields = head.split()
        if len(fields) < 4:
            continue
        p = {"fen": " ".join(fields[:4]) + " 0 1", "dtm": None, "id": None}
        for op in ops:
            t = op.strip()
            if not t:
                continue
            key, _, val = t.partition(" ")
            val = val.strip().strip('"')
            if key == "hm":
                try:
                    p["dtm"] = int(val)
                except ValueError:
                    p["dtm"] = None
            elif key == "id":
                p["id"] = val
        if p["dtm"] and p["dtm"] > 0:
            out.append(p)
    return out


def material_of(fen: str) -> str:
    """Canonical material name of a FEN: White's men then 'v' then Black's, K first, then Q R B N P."""
    order = "KQRBNP"
    placement = fen.split()[0]
    white = sorted((c for c in placement if c.isupper()), key=order.index)
    black = sorted((c.upper() for c in placement if c.islower()), key=order.index)
    return "".join(white) + "v" + "".join(black).lower()


def material_row(stats: dict, size_bytes: int) -> dict:
    """One materials.json row from a stats sidecar and the table's on-disk size."""
    cells = stats.get("cells", {})
    total = 2 * int(stats["plane_size"])
    invalid = sum(int(v) for v in cells.get("invalid", {}).values())
    unsolvable = sum(int(v) for v in cells.get("unsolvable", {}).values())
    unique = 0
    for side in stats.get("uniqueness", {}).values():
        for by_count in side.values():
            unique += int(by_count.get("1", 0))
    marker = bool(stats.get("all_unsolvable")) or int(stats.get("max_dtm", 255)) >= 255
    return {
        "material": stats["material"],
        "pieces": piece_count(stats["material"]),
        "max_dtm": None if marker else int(stats["max_dtm"]),
        "solvable": 0 if marker else total - invalid - unsolvable,
        "unique": 0 if marker else unique,
        "size_bytes": size_bytes,
    }


def corpus_summary(rows: list[dict]) -> dict:
    by_pieces: dict[str, int] = {}
    for r in rows:
        by_pieces[str(r["pieces"])] = by_pieces.get(str(r["pieces"]), 0) + 1
    real = [r for r in rows if r["max_dtm"] is not None]
    deepest = max(real, key=lambda r: r["max_dtm"]) if real else None
    return {
        "tables": len(rows),
        "markers": len(rows) - len(real),
        "size_bytes": sum(r["size_bytes"] for r in rows),
        "solvable": sum(r["solvable"] for r in rows),
        "unique": sum(r["unique"] for r in rows),
        "by_pieces": by_pieces,
        "deepest": {"material": deepest["material"], "dtm": deepest["max_dtm"]}
        if deepest
        else None,
    }


def helpmate_line(binary: str, fen: str, tables: str) -> str:
    p = subprocess.run([binary, "line", fen, "--tables", tables], capture_output=True, text=True)
    if p.returncode != 0:
        raise RuntimeError(p.stderr.strip()[:200])
    lines = [ln for ln in p.stdout.splitlines() if ln.strip()]
    if len(lines) != 1:
        raise RuntimeError(f"expected one line, got {len(lines)}")
    return lines[0]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--tables", required=True)
    ap.add_argument("--binary", default="helpmate")
    ap.add_argument("--out", default=str(ROOT / "site/data"))
    ap.add_argument("--deepest", default=str(DEEPEST_JSON))
    ap.add_argument("--puzzles", default=str(PUZZLES_EPD))
    a = ap.parse_args(argv)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tables = Path(a.tables).expanduser()

    # deepest
    deepest = []
    for e in json.load(open(a.deepest)):
        deepest.append(
            {
                "material": e["material"],
                "pieces": e["pieces"],
                "fen": e["fen"],
                "dtm": e["dtm"],
                "max_dtm": e["max_dtm"],
                "unique_at_depth": e["unique_at_depth"],
                "plies": expand_solution(e["fen"], e["solution"]),
            }
        )
    (out / "deepest.json").write_text(json.dumps(deepest, separators=(",", ":")))
    print(f"deepest.json: {len(deepest)} positions", file=sys.stderr)

    # puzzles
    puzzles, dropped = [], 0
    for p in parse_epd(Path(a.puzzles).read_text()):
        try:
            plies = expand_solution(p["fen"], helpmate_line(a.binary, p["fen"], str(tables)))
        except (RuntimeError, ValueError) as exc:
            dropped += 1
            print(f"  drop {p['id']}: {exc}", file=sys.stderr)
            continue
        if len(plies) != p["dtm"]:
            dropped += 1
            print(
                f"  drop {p['id']}: epd says {p['dtm']} plies, line has {len(plies)}",
                file=sys.stderr,
            )
            continue
        mat = material_of(p["fen"])
        puzzles.append(
            {
                "id": p["id"],
                "fen": p["fen"],
                "dtm": p["dtm"],
                "material": mat,
                "pieces": piece_count(mat),
                "plies": plies,
            }
        )
    (out / "puzzles.json").write_text(json.dumps(puzzles, separators=(",", ":")))
    print(f"puzzles.json: {len(puzzles)} puzzles, {dropped} dropped", file=sys.stderr)

    # materials + corpus
    rows = []
    for sc in sorted(tables.glob("*.stats.json")):
        hm = sc.with_name(sc.name[: -len(".stats.json")] + ".hm")
        if not hm.exists():
            continue
        rows.append(material_row(json.loads(sc.read_text()), os.path.getsize(hm)))
    rows.sort(key=lambda r: (r["pieces"], r["material"]))
    (out / "materials.json").write_text(json.dumps(rows, separators=(",", ":")))
    (out / "corpus.json").write_text(json.dumps(corpus_summary(rows), indent=1))
    print(f"materials.json: {len(rows)} rows", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
