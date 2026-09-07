"""tools/verify_corpus.py: the block-level integrity check for compressed tables.

The tool reads the on-disk layout directly (TableHeader, then the block index,
then zstd frames), so the test builds a table the same way, byte by byte, and
then damages it in the ways that matter: a flipped payload byte (the zstd
content checksum must catch it), an index that lies about a block's length,
and a file cut short. A clean table must come back OK, a marker and a raw
table must be skipped rather than failed, and the exit status must follow.
"""

import importlib.util
import struct
import sys
from pathlib import Path

import pytest

zstd = pytest.importorskip("zstandard")

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "verify_corpus", ROOT / "tools" / "verify_corpus.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["verify_corpus"] = mod
    spec.loader.exec_module(mod)
    return mod


def _header(*, version, encoding, plane_size, flags, block_size, json_len):
    h = struct.pack(
        "<4sIBB26sQBBIB9sI",
        b"HM8P",
        version,
        encoding,
        1,
        b"KQvk".ljust(26, b"\0"),
        plane_size,
        14,
        flags,
        block_size,
        1 if block_size else 0,
        b"\0" * 9,
        json_len,
    )
    assert len(h) == 64
    return h


def _compressed_table(path: Path, planes: bytes, block_size: int) -> None:
    """Write a version-3 / encoding-2 table holding `planes` (4 * plane_size bytes)."""
    assert len(planes) % 4 == 0
    cctx = zstd.ZstdCompressor(level=3, write_checksum=True)
    frames = [cctx.compress(planes[i : i + block_size]) for i in range(0, len(planes), block_size)]
    offsets = [0]
    for f in frames:
        offsets.append(offsets[-1] + len(f))
    meta = b"{}"
    body = (
        struct.pack("<Q", len(frames))
        + struct.pack(f"<{len(frames) + 1}Q", *offsets)
        + b"".join(frames)
    )
    path.write_bytes(
        _header(
            version=3,
            encoding=2,
            plane_size=len(planes) // 4,
            flags=0,
            block_size=block_size,
            json_len=len(meta),
        )
        + meta
        + body
    )


@pytest.fixture
def corpus(tmp_path):
    planes = bytes((i * 7 + 3) % 251 for i in range(4 * 1000))  # 4000 bytes, not a multiple of 1024
    _compressed_table(tmp_path / "KQvk.hm", planes, block_size=1024)
    (tmp_path / "Kvk.hm").write_bytes(
        _header(version=2, encoding=1, plane_size=462, flags=1, block_size=0, json_len=0)
    )
    (tmp_path / "KRvk.hm").write_bytes(
        _header(version=1, encoding=1, plane_size=2, flags=0, block_size=0, json_len=0) + b"\0" * 8
    )
    return tmp_path


def test_clean_table_is_ok_and_markers_and_raw_are_skipped(corpus):
    vc = _load()
    verdicts = {
        Path(p).name: v for p, v, _, _ in map(vc.check_table, map(str, corpus.glob("*.hm")))
    }
    assert verdicts["KQvk.hm"] == "OK"
    assert verdicts["Kvk.hm"].startswith("skip marker")
    assert verdicts["KRvk.hm"].startswith("skip raw")
    _, _, nb, _ = vc.check_table(str(corpus / "KQvk.hm"))
    assert nb == 4  # 4000 bytes in 1024-byte blocks: three full, one of 928


def test_flipped_payload_byte_fails_the_checksum(corpus):
    vc = _load()
    p = corpus / "KQvk.hm"
    data = bytearray(p.read_bytes())
    # Last 20 bytes of the file sit inside the final frame's payload, well past its header.
    data[-20] ^= 0xFF
    p.write_bytes(data)
    _, verdict, _, _ = vc.check_table(str(p))
    assert verdict.startswith("BAD block 3:"), verdict


def test_index_length_lie_is_reported(corpus):
    vc = _load()
    p = corpus / "KQvk.hm"
    data = bytearray(p.read_bytes())
    # Shrink plane_size so the tool expects the last block to be shorter than it decodes to.
    struct.pack_into("<Q", data, 36, 990)
    p.write_bytes(data)
    _, verdict, _, _ = vc.check_table(str(p))
    assert "BAD" in verdict and "index says" in verdict, verdict


def test_truncated_file_is_reported_not_crashed(corpus):
    vc = _load()
    p = corpus / "KQvk.hm"
    data = p.read_bytes()
    p.write_bytes(data[: 64 + 2 + 8 + 8 * 2])  # header, json, block count, two of five offsets
    _, verdict, _, _ = vc.check_table(str(p))
    assert verdict.startswith("BAD truncated block index")


def test_exit_status_follows_the_verdicts(corpus, capsys):
    vc = _load()
    assert vc.main([str(corpus), "-j", "1"]) == 0
    out = capsys.readouterr().out
    assert "1 table(s) checked, 4 blocks, 0 bad, 2 skipped" in out
    data = bytearray((corpus / "KQvk.hm").read_bytes())
    data[-20] ^= 0xFF
    (corpus / "KQvk.hm").write_bytes(data)
    assert vc.main([str(corpus / "KQvk.hm")]) == 1
    assert vc.main([str(corpus / "nope")]) == 2
