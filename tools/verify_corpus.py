"""Decompress every block of every block-compressed table and report the ones
that do not come back clean.

    python3 tools/verify_corpus.py ~/tb              # a directory
    python3 tools/verify_corpus.py ~/tb/KBvkqbn.hm   # one table
    python3 tools/verify_corpus.py ~/tb -j 4         # four tables at a time

Read-only. Nothing about the tables is interpreted -- no positions, no DTM
semantics -- only that each zstd frame decodes, that its content checksum
matches (every block is written with one; see compress_block in
src/core/format/block_codec.cpp), and that it decodes to the length the block
index promises. Markers (format version 2) and raw tables (version 1) have no
blocks and are reported as skipped.

Why this exists: on 2026-08-21 tools/deepest_showcase.py hit "zstd decompress
failed: Restored data doesn't match checksum" on roughly one probe in ten
against large compressed tables, and grew a retry. On 2026-09-07 the error did
not reproduce in ~550 CLI runs and every block of the 233-table corpus
(8,099,259 blocks) decoded cleanly with this script. The reader had not
changed between the two dates. A checksum failure that comes and goes on
identical bytes is not something the reader can cause on its own, so the
question to ask when it appears is whether the bytes on disk are sound, and
this is how to ask it. A table that fails here is corrupt on disk; one that
passes here and still fails in helpmate points at the machine.

Exit status: 0 when every table checked is clean, 1 when any is not, 2 on
usage errors. Layout follows TableHeader in src/core/format/table_file.h.
"""

from __future__ import annotations

import argparse
import os
import struct
import sys
import time
from multiprocessing import Pool
from pathlib import Path

try:
    import zstandard as zstd
except ImportError:  # pragma: no cover - environment, not logic
    sys.exit("verify_corpus: needs the 'zstandard' package (pip install zstandard)")

MAGIC = b"HM8P"
HEADER_LEN = 64
MAX_REPORTED = 20  # bad blocks listed per table before giving up on it


def check_table(path: str) -> tuple[str, str, int, float]:
    """Return (path, verdict, blocks_checked, seconds). verdict is 'OK', a
    'skip ...' reason, or 'BAD ...' with the first bad blocks listed."""
    t0 = time.time()
    with open(path, "rb") as fh:
        hdr = fh.read(HEADER_LEN)
        if len(hdr) < HEADER_LEN or hdr[:4] != MAGIC:
            return path, "BAD not a helpmate table (magic)", 0, time.time() - t0
        version, encoding = struct.unpack_from("<IB", hdr, 4)
        (plane_size,) = struct.unpack_from("<Q", hdr, 36)
        _max_dtm, flags, block_size = struct.unpack_from("<BBI", hdr, 44)
        (json_len,) = struct.unpack_from("<I", hdr, 60)
        if flags & 1:
            return path, f"skip marker (v{version})", 0, time.time() - t0
        if encoding != 2 or block_size == 0:
            return path, f"skip raw (v{version}, encoding {encoding})", 0, time.time() - t0

        fh.seek(HEADER_LEN + json_len)
        raw = fh.read(8)
        if len(raw) < 8:
            return path, "BAD truncated before block index", 0, time.time() - t0
        (nb,) = struct.unpack("<Q", raw)
        index = fh.read(8 * (nb + 1))
        if len(index) < 8 * (nb + 1):
            return path, "BAD truncated block index", 0, time.time() - t0
        offsets = struct.unpack(f"<{nb + 1}Q", index)
        blocks_start = fh.tell()
        file_size = os.fstat(fh.fileno()).st_size
        if blocks_start + offsets[-1] > file_size:
            return path, "BAD block index points past end of file", 0, time.time() - t0

        total = 4 * plane_size
        dctx = zstd.ZstdDecompressor()
        bad: list[str] = []
        for b in range(nb):
            expect = min(block_size, total - b * block_size)
            fh.seek(blocks_start + offsets[b])
            src = fh.read(offsets[b + 1] - offsets[b])
            try:
                out = dctx.decompress(src, max_output_size=expect)
            except zstd.ZstdError as exc:
                bad.append(f"block {b}: {exc}")
            else:
                if len(out) != expect:
                    bad.append(f"block {b}: decoded {len(out)} bytes, index says {expect}")
            if len(bad) >= MAX_REPORTED:
                bad.append("...")
                break
        verdict = "OK" if not bad else "BAD " + "; ".join(bad)
        return path, verdict, nb, time.time() - t0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("target", help="a .hm file or a directory of them")
    ap.add_argument(
        "-j", "--jobs", type=int, default=2, help="tables checked in parallel (default 2)"
    )
    a = ap.parse_args(argv)

    target = Path(a.target).expanduser()
    if target.is_dir():
        paths = sorted((str(p) for p in target.glob("*.hm")), key=os.path.getsize)
    elif target.is_file():
        paths = [str(target)]
    else:
        print(f"verify_corpus: no such file or directory: {target}", file=sys.stderr)
        return 2
    if not paths:
        print(f"verify_corpus: no .hm files in {target}", file=sys.stderr)
        return 2

    failed = 0
    checked = blocks = 0
    with Pool(max(1, a.jobs)) as pool:
        for path, verdict, nb, dt in pool.imap_unordered(check_table, paths):
            print(f"{Path(path).name:20} {verdict}  blocks={nb} {dt:.0f}s", flush=True)
            if verdict.startswith("BAD"):
                failed += 1
            if not verdict.startswith("skip"):
                checked += 1
                blocks += nb
    print(
        f"\n{checked} table(s) checked, {blocks:,} blocks, {failed} bad, "
        f"{len(paths) - checked} skipped (markers / raw)"
    )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
