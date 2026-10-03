"""Corpus statistics from the tables' .stats.json sidecars: one row per table, the
lossless DTM x solution-count histogram, Parquet for Hugging Face and a compact JSON
for the site's Statistics screen. Nothing here reads a table's payload."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from .materials import Material

if TYPE_CHECKING:
    from .registry import Registry

STMS = ("wtm", "btm")


@dataclass
class TableStats:
    material: str
    stats: dict
    size_bytes: int


def collect(tables: Path) -> list[TableStats]:
    """Every sidecar whose table is present (the rule of site_data.material_rows)."""
    out = []
    for sc in Path(tables).glob("*.stats.json"):
        hm = sc.with_name(sc.name[: -len(".stats.json")] + ".hm")
        if hm.exists():
            stats = json.loads(sc.read_text())
            out.append(TableStats(stats["material"], stats, hm.stat().st_size))
    return sorted(out, key=lambda t: (Material(t.material).pieces, t.material))


def is_marker(stats: dict) -> bool:
    return bool(stats.get("all_unsolvable")) or int(stats.get("max_dtm", 255)) >= 255


def contributor_of(material: str, registry: Registry | None) -> tuple[str, int | None, str | None]:
    entry = registry.tables.get(material) if registry else None
    if not entry:
        return "maintainer", None, None
    c = registry.contributors.get(entry["contributor"]) if registry else None
    name = "anonymous" if c and c.anonymous else (c.display if c else entry["contributor"])
    return name, entry.get("hf_pr"), entry.get("merged")


def _unique(stats: dict) -> int:
    return sum(int(by_count.get("1", 0))
               for side in stats.get("uniqueness", {}).values() for by_count in side.values())


def materials_rows(ts: list[TableStats], registry: Registry | None) -> list[dict]:
    rows = []
    for t in ts:
        s, m = t.stats, Material(t.material)
        cells = s.get("cells", {})  # tolerant like site_data.stats_row: minimal sidecars exist in tests
        inv = {k: int(cells.get("invalid", {}).get(k, 0)) for k in STMS}
        uns = {k: int(cells.get("unsolvable", {}).get(k, 0)) for k in STMS}
        marker = is_marker(s)
        who, pr, merged = contributor_of(t.material, registry)
        rows.append({"material": t.material, "pieces": m.pieces, "pawns": m.pawns,
                     "white": m.white, "black": m.black, "marker": marker,
                     "max_dtm": None if marker else int(s["max_dtm"]),
                     "plane_size": int(s["plane_size"]),
                     "invalid_wtm": inv["wtm"], "invalid_btm": inv["btm"],
                     "unsolvable_wtm": uns["wtm"], "unsolvable_btm": uns["btm"],
                     "solvable": 0 if marker else 2 * int(s["plane_size"]) - sum(inv.values()) - sum(uns.values()),
                     "unique": 0 if marker else _unique(s), "size_bytes": t.size_bytes,
                     "generator_version": str(s.get("generator_version", "")),
                     "contributor": who, "hf_pr": pr, "merged": merged})
    return rows


def histogram_rows(ts: list[TableStats]) -> list[dict]:
    rows = []
    for t in ts:
        if is_marker(t.stats):
            continue
        pieces = Material(t.material).pieces
        for stm in STMS:
            by_dtm = t.stats.get("uniqueness", {}).get(stm, {})
            for d in sorted(by_dtm, key=int):
                for c in sorted(by_dtm[d], key=int):
                    rows.append({"material": t.material, "pieces": pieces, "stm": stm,
                                 "dtm": int(d), "count": int(c), "cells": int(by_dtm[d][c])})
    return rows


def _depths(stats: dict, stm: str) -> list[list[int]]:
    hist = stats.get("dtm_histogram", {}).get(stm, {})
    uniq = stats.get("uniqueness", {}).get(stm, {})
    return [[int(d), int(hist[d]), int(uniq.get(d, {}).get("1", 0))] for d in sorted(hist, key=int)]


def site_stats(ts: list[TableStats]) -> dict:
    materials: dict[str, dict] = {}
    total: dict[str, dict[int, list[int]]] = {k: {} for k in STMS}
    by_pieces: dict[str, dict[str, int]] = {}
    for row, t in zip(materials_rows(ts, None), ts):
        marker = row["marker"]
        entry = {"pieces": row["pieces"], "max_dtm": row["max_dtm"]}
        for stm in STMS:
            entry[stm] = [] if marker else _depths(t.stats, stm)
            for d, cells, uniq in entry[stm]:
                acc = total[stm].setdefault(d, [d, 0, 0])
                acc[1] += cells
                acc[2] += uniq
        materials[t.material] = entry
        bp = by_pieces.setdefault(str(row["pieces"]), {"tables": 0, "solvable": 0, "unique": 0})
        bp["tables"] += 1
        bp["solvable"] += row["solvable"]
        bp["unique"] += row["unique"]
    return {"materials": materials,
            "total": {stm: [total[stm][d] for d in sorted(total[stm])] for stm in STMS},
            "by_pieces": by_pieces}
