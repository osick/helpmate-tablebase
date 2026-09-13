"""tools/published_problems.py: parsing the published-helpmates file, matching
under every mirroring, and annotating DEEPEST entries with an unpublished
alternative. The real database on hand (h#2 only) matches no showcase entry,
so the matching path is exercised with a synthetic block built from a real
showcase position, mirrored."""
import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
TOOLS = ROOT / "tools"
DATA = ROOT / "docs" / "DEEPEST.json"


def _load(name):
    spec = importlib.util.spec_from_file_location(name, TOOLS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # dataclasses look their module up here
    spec.loader.exec_module(mod)
    return mod


pp = _load("published_problems")

SAMPLE = """\


No. 3 (id: P0003471)
Steudel, Theodor
source 1: Die Schwalbe, No. 2746, 07-08/1968
8/8/8/8/1tt5/4k3/2B5/T3K3
stipulation: h#2
solution:
1.Tf4 Td1 2.Tbe4 Td3#


No. 4 (id: P0003480)
Kubecka, Jan
source 1: feenschach, No. (A), 09/1971
source 2: Somewhere else, 1999
8/8/7s/8/6t1/7k/7B/4K2T
stipulation: h#2 Duplex
solution:
1.Sf5 Kf2 2.Sg3 hxg3#

garbage block without a header
"""


def test_parse_reads_blocks_and_converts_german_letters():
    ps = pp.parse(SAMPLE)
    assert [p.id for p in ps] == ["P0003471", "P0003480"]
    a = ps[0]
    assert a.author == "Steudel, Theodor"
    assert a.sources == ["Die Schwalbe, No. 2746, 07-08/1968"]
    assert a.fen == "8/8/8/8/1rr5/4k3/2P5/R3K3"   # t->r, B->P, T->R
    assert a.stipulation == "h#2"
    assert a.solution.startswith("1.Tf4")
    b = ps[1]
    assert b.fen == "8/8/7n/8/6r1/7k/7P/4K2R"
    assert len(b.sources) == 2 and b.stipulation == "h#2 Duplex"


def test_canon_is_invariant_under_the_symmetries_that_apply():
    pawnless = "8/1q6/1n6/8/8/8/q7/KBk5"
    # transpose + flips of a pawnless board all share one key
    rows = pp.board_rows(pawnless)
    keys = {pp.canon(pp.rows_key(v)) for v in pp.mirrorings(rows)}
    assert len(keys) == 1
    assert len(pp.mirrorings(rows)) == 8
    with_pawn = "6k1/8/8/8/8/8/4P3/2K5"
    rows = pp.board_rows(with_pawn)
    assert len(pp.mirrorings(rows)) == 2
    mirrored = "1k6/8/8/8/8/8/3P4/5K2"          # files a<->h
    assert pp.canon(with_pawn) == pp.canon(mirrored)
    upside_down = "2K5/4P3/8/8/8/8/8/6k1"       # ranks flipped: a different problem with pawns
    assert pp.canon(with_pawn) != pp.canon(upside_down)


def test_index_finds_a_showcase_position_given_mirrored_in_german():
    rows = json.loads(DATA.read_text())
    r = next(x for x in rows if x["material"] == "KQvk")
    # mirror the board left-right and write it with German letters
    mirrored = "/".join("".join(reversed(rank)) for rank in r["fen"].split()[0].split("/"))
    german = mirrored.translate(str.maketrans("QRBNPqrbnp", "DTLSBdtlsb"))
    block = (f"No. 9 (id: P0000009)\nAnon, Ymous\nsource 1: Test, 2026\n{german}\n"
             f"stipulation: {pp.hn(r['dtm'])}\nsolution:\n1.x y#\n")
    index = pp.PublishedIndex(pp.parse(block))
    assert len(index) == 1
    hits = index.lookup(r["fen"])
    assert [h.id for h in hits] == ["P0000009"]
    assert index.lookup("8/8/8/8/8/8/8/K6k") == []


def test_annotate_adds_publication_and_an_unpublished_alternative():
    rows = json.loads(DATA.read_text())
    r = dict(next(x for x in rows if x["material"] == "KQvk"))
    block = (f"No. 1 (id: P1)\nA, B\nsource 1: S1\n"
             f"{r['fen'].split()[0].translate(str.maketrans('QRBNPqrbnp', 'DTLSBdtlsb'))}\n"
             f"stipulation: h#6\nsolution:\n1.x\n\n"
             f"No. 2 (id: P2)\nC, D\nsource 1: S2\n8/8/8/8/8/8/D7/K6k\nstipulation: h#6\nsolution:\n1.y\n")
    index = pp.PublishedIndex(pp.parse(block))
    # the tablebase "returns" the entry itself, then a published one, then a fresh one
    mined = [r["fen"], "8/8/8/8/8/8/Q7/K6k b - - 0 1", "8/8/8/8/8/8/8/K1Qk4 b - - 0 1"]
    calls = []

    def described(fen):
        calls.append(fen)
        return {"fen": fen, "solution": "1.Kc1 Qb1#", "themes": ["pure"]}

    matched, changed = pp.annotate([r], index, mine=lambda m, d, n: mined, describe_fn=described)
    assert (matched, changed) == (1, 1)
    assert r["published"][0]["id"] == "P1" and r["published"][0]["author"] == "A, B"
    assert r["alternative"]["fen"] == "8/8/8/8/8/8/8/K1Qk4 b - - 0 1"
    assert calls == ["8/8/8/8/8/8/8/K1Qk4 b - - 0 1"]   # only the survivor is described
    # a second run with nothing published clears both keys and reports the change
    matched, changed = pp.annotate([r], pp.PublishedIndex([]), mine=lambda m, d, n: [], describe_fn=described)
    assert (matched, changed) == (0, 1)
    assert "published" not in r and "alternative" not in r


def test_annotate_is_a_no_op_without_matches():
    rows = json.loads(DATA.read_text())
    snapshot = json.dumps(rows)
    matched, changed = pp.annotate(rows, pp.PublishedIndex([]), mine=lambda m, d, n: [], describe_fn=None)
    assert (matched, changed) == (0, 0)
    assert json.dumps(rows) == snapshot


@pytest.mark.skipif(not (ROOT / "sampledata" / "hmatt_lower7.fen").exists(),
                    reason="the published database is not part of the repo")
def test_real_database_parses_and_matches_no_showcase_entry_today():
    text = (ROOT / "sampledata" / "hmatt_lower7.fen").read_text(encoding="utf-8", errors="replace")
    ps = pp.parse(text)
    assert len(ps) > 8000
    index = pp.PublishedIndex(ps)
    rows = json.loads(DATA.read_text())
    assert sum(1 for r in rows if index.lookup(r["fen"])) == 0
