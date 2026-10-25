"""Compare a local tables directory with the dataset's manifest.

`helpmate-tables diff` reports it, `pull --missing` downloads only what differs.
Hashing a whole corpus takes hours, so a file's status is decided as cheaply as
possible: a missing file is new; a size that differs from the manifest is a
change; a matching size is checked against a local checksum cache
(`.sha256-cache.json` in the tables directory, filled whenever a file is hashed,
e.g. by `pull`), keyed by size and modification time so an edited file is never
taken on trust (a same-size rewrite within one filesystem clock tick of the
last hash would be; no tool rewrites tables that way). Only `--verify` hashes
the files the cache does not cover.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from .manifest import sha256_file

CACHE = ".sha256-cache.json"


class ShaCache:
    def __init__(self, tables: Path):
        self.path = Path(tables) / CACHE
        self.dirty = False
        try:
            self.entries: dict[str, dict] = json.loads(self.path.read_text())
        except (OSError, ValueError):
            self.entries = {}

    def get(self, p: Path) -> str | None:
        e, st = self.entries.get(p.name), p.stat()
        if e and e.get("size") == st.st_size and e.get("mtime_ns") == st.st_mtime_ns:
            return e.get("sha256")
        return None

    def hash(self, p: Path) -> str:
        sha = sha256_file(p)
        st = p.stat()
        self.entries[p.name] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "sha256": sha}
        self.dirty = True
        return sha

    def save(self) -> None:
        if not self.dirty:
            return
        try:
            self.path.write_text(json.dumps(self.entries, indent=1, sort_keys=True))
            self.dirty = False
        except OSError:
            pass  # a read-only tables directory still gets a correct diff


@dataclass
class Diff:
    new: dict[str, int] = field(default_factory=dict)       # material -> bytes to download
    changed: dict[str, int] = field(default_factory=dict)
    current: list[str] = field(default_factory=list)
    size_only: list[str] = field(default_factory=list)      # current by size, not hashed
    local_only: list[str] = field(default_factory=list)

    @property
    def to_pull(self) -> list[str]:
        return sorted({*self.new, *self.changed})


def file_status(p: Path, entry: dict, cache: ShaCache, verify: bool) -> str:
    """'new', 'changed', 'current' or 'size' (same size, never hashed)."""
    if not p.is_file():
        return "new"
    if p.stat().st_size != entry.get("size"):
        return "changed"
    sha = cache.get(p)
    if sha is None:
        if not verify:
            return "size"
        sha = cache.hash(p)
    return "current" if sha == entry.get("sha256") else "changed"


def diff(tables: Path, manifest: dict, verify: bool = False) -> Diff:
    files = manifest.get("files", {})
    materials = sorted({n[: -len(".hm")] for n in files if n.endswith(".hm")})
    cache, out = ShaCache(tables), Diff()
    for m in materials:
        names = [n for n in (f"{m}.hm", f"{m}.stats.json") if n in files]
        states = [file_status(Path(tables) / n, files[n], cache, verify) for n in names]
        size = sum(files[n].get("size", 0) for n, s in zip(names, states) if s in ("new", "changed"))
        if all(s == "new" for s in states):
            out.new[m] = size
        elif any(s in ("new", "changed") for s in states):
            out.changed[m] = size
        else:
            out.current.append(m)
            if "size" in states:
                out.size_only.append(m)
    known = set(materials)
    out.local_only = sorted(p.name[: -len(".hm")] for p in Path(tables).glob("*.hm")
                            if p.name[: -len(".hm")] not in known)
    cache.save()
    return out


def report(d: Diff) -> str:
    gib = lambda b: f"{b / 2**30:,.2f} GiB"  # noqa: E731
    lines = [f"new      {m:10} {gib(s):>12}" for m, s in sorted(d.new.items())]
    lines += [f"changed  {m:10} {gib(s):>12}" for m, s in sorted(d.changed.items())]
    lines += [f"local    {m:10} (not in the dataset)" for m in d.local_only]
    note = f" ({len(d.size_only)} by size only; --verify hashes them)" if d.size_only else ""
    lines.append(f"{len(d.new)} new ({gib(sum(d.new.values()))}), {len(d.changed)} changed "
                 f"({gib(sum(d.changed.values()))}), {len(d.current)} up to date{note}, "
                 f"{len(d.local_only)} only local")
    return "\n".join(lines)
