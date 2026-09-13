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


def test_detex_turns_tex_umlauts_back_into_letters():
    assert pp.detex('Ban, Jen"o') == "Ban, Jenö"
    assert pp.detex('Suomen Teht"av"aniekat') == "Suomen Tehtäväniekat"
    assert pp.detex('Gla"s, G"unter') == "Glaß, Günter"
    assert pp.detex("The Problemist, No. H2794") == "The Problemist, No. H2794"
    ps = pp.parse('No. 1 (id: P1)\nBan, Jen"o\nsource 1: Tidskrift f"or Schack\n8/8/8/8/8/8/8/K6k\nstipulation: h#2\nsolution:\n1.x\n')
    assert ps[0].author == "Ban, Jenö" and ps[0].sources == ["Tidskrift för Schack"]


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

    matched, replaced, changed = pp.annotate([r], index, mine=lambda m, d, n: mined, describe_fn=described)
    assert (matched, replaced, changed) == (1, 0, 1)
    assert r["published"][0]["id"] == "P1" and r["published"][0]["author"] == "A, B"
    assert r["alternative"]["fen"] == "8/8/8/8/8/8/8/K1Qk4 b - - 0 1"
    assert calls == ["8/8/8/8/8/8/8/K1Qk4 b - - 0 1"]   # only the survivor is described
    # a second run with nothing published clears both keys and reports the change
    matched, replaced, changed = pp.annotate([r], pp.PublishedIndex([]), mine=lambda m, d, n: [], describe_fn=described)
    assert (matched, replaced, changed) == (0, 0, 1)
    assert "published" not in r and "alternative" not in r


def test_annotate_twice_is_a_no_op_the_second_time():
    rows = json.loads(DATA.read_text())[:20]
    pp.annotate(rows, pp.PublishedIndex([]), mine=lambda m, d, n: [], describe_fn=None, replace=False)
    assert all("quality" in r and "published" not in r for r in rows)
    snapshot = json.dumps(rows)
    matched, replaced, changed = pp.annotate(rows, pp.PublishedIndex([]), mine=lambda m, d, n: [],
                                             describe_fn=None, replace=False)
    assert (matched, replaced, changed) == (0, 0, 0)
    assert json.dumps(rows) == snapshot


@pytest.mark.skipif(not (ROOT / "sampledata" / "hmatt_lower7.fen").exists(),
                    reason="the published database is not part of the repo")
def test_real_database_parses_and_the_annotation_agrees_with_it():
    text = (ROOT / "sampledata" / "hmatt_lower7.fen").read_text(encoding="latin-1")
    ps = pp.parse(text)
    assert len(ps) > 8000
    index = pp.PublishedIndex(ps)
    rows = json.loads(DATA.read_text())
    # whatever the database holds today, the annotation in DEEPEST.json agrees with it
    assert [r["material"] for r in rows if index.lookup(r["fen"])] == \
        [r["material"] for r in rows if r.get("published")]


# --------------------------------------------------------------------------
# quality: capture on move one, check in the diagram, no legal last move


def test_assess_flags_a_first_move_capture_and_a_check():
    q = pp.assess("8/1q6/1n6/8/8/8/q7/KBk5 w - - 0 1", "Kxa2 Kd2 Be4")
    assert q["capture_first"] is True and q["check"] is True and q["legal"] is True
    q = pp.assess("8/7k/8/6Q1/8/8/8/K7 b - - 0 1", "Kh8 Kb2")
    assert q == {"capture_first": False, "check": False, "legal": True}


def test_legal_last_move_is_decided_exactly():
    import chess
    # White's men are all immobile and never moved: no retraction, illegal.
    assert pp.legal_last_move(chess.Board("7k/8/8/8/8/8/PPP5/KB6 b - - 0 1")) is False
    # Free c2 and the bishop can have come from there: legal.
    assert pp.legal_last_move(chess.Board("7k/8/8/8/8/8/PP6/KB6 b - - 0 1")) is True
    # Side not to move in check is illegal outright.
    assert pp.legal_last_move(chess.Board("7k/8/8/8/8/8/8/K6q b - - 0 1")) is False
    # A rook on the back rank next to its king with nothing else around
    # could only have arrived by capturing or moving in: legal.
    assert pp.legal_last_move(chess.Board("k7/8/8/8/8/8/8/KR6 b - - 0 1")) is True
    # Unpromotion: a white knight on b8 with the pawn's origin a7/c7 free.
    assert pp.legal_last_move(chess.Board("1N5k/8/8/8/8/8/8/K7 b - - 0 1")) is True


def test_rank_orders_the_weaknesses():
    ok = {"capture_first": False, "check": False, "legal": True}
    assert pp.rank(ok) == 0
    assert pp.rank({**ok, "check": True}) == 1
    assert pp.rank({**ok, "capture_first": True}) == 2
    assert pp.rank({**ok, "capture_first": True, "check": True}) == 3
    assert pp.rank({**ok, "legal": False}) == 4
    assert pp.quality_note(ok) == ""
    assert "capture" in pp.quality_note({**ok, "capture_first": True})
    assert "legal last move" in pp.quality_note({**ok, "legal": False})


def test_published_by_is_surname_and_year():
    P = pp.Published
    assert pp.published_by(P("1", "P1", "Sheglow, Wiktor S.", ["Suomen Tehtäväniekat, No. (257), 05-06/1998"], "8", "h#6", "")) == "Sheglow (1998)"
    assert pp.published_by(P("1", "P1", "Abdurahmanovic, Fadil; Becker, Richard", ["The Problemist, No. (R), 01/2006"], "8", "h#7", "")) == "Abdurahmanovic & Becker (2006)"
    assert pp.published_by(P("1", "P1", "?, ?", ["Sachova skladba, No. 1065, 06/1987"], "8", "h#8", "")) == "unknown (1987)"
    assert pp.published_by(P("1", "P1", "Maslar, Zdravko", ["?"], "8", "h#8", "")) == "Maslar"
    assert pp.published_by({"author": "Ban, Jenö", "sources": ["Stella Polaris, No. 1072, 06/1967"]}) == "Ban (1967)"


def test_annotate_replaces_a_weak_unpublished_position_with_a_cleaner_one():
    # entry: unpublished, solution starts with a capture (rank 2)
    r = {"material": "KQvk", "pieces": 3, "dtm": 12, "max_dtm": 14, "unique_at_depth": 3,
         "saturated_at_max": True, "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
         "solution": "Kxg5 Kb2 Kh7 Kc3 Kh8 Kd4 Kh7 Ke5 Kh8 Kf6 Kh7 Qg7#", "themes": []}
    candidates = ["8/8/7k/6Q1/8/8/8/K7 b - - 0 1",           # itself
                  "8/7k/8/6Q1/8/8/8/K7 b - - 0 1"]           # clean
    def describe(fen):
        return {"fen": fen, "solution": "Kh8 Kb2 Kh7 Kc3 Kh8 Kd4 Kh7 Ke5 Kh8 Kf6 Kh7 Qg7#", "themes": ["pure"]}
    matched, replaced, changed = pp.annotate([r], pp.PublishedIndex([]), mine=lambda m, d, n: candidates,
                                             describe_fn=describe)
    assert (matched, replaced, changed) == (0, 1, 1)
    assert r["fen"] == "8/7k/8/6Q1/8/8/8/K7 b - - 0 1" and r["replaced_from"] == "8/8/7k/6Q1/8/8/8/K7 b - - 0 1"
    assert r["quality"] == {"capture_first": False, "check": False, "legal": True}
    # keep-positions: the weak entry stays and only gets graded
    r2 = {**r, "fen": r["replaced_from"], "solution": "Kxg5 x"}; r2.pop("replaced_from")
    pp.annotate([r2], pp.PublishedIndex([]), mine=lambda m, d, n: candidates, describe_fn=describe, replace=False)
    assert r2["fen"] == "8/8/7k/6Q1/8/8/8/K7 b - - 0 1" and r2["quality"]["capture_first"] is True


def test_best_candidate_prefers_the_best_rank_and_skips_illegal_diagrams():
    entry = {"material": "KQvk", "dtm": 12, "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1"}
    cands = ["7k/8/8/8/8/8/PPP5/KB6 b - - 0 1",      # illegal
             "8/8/8/8/8/8/8/K1Q4k b - - 0 1",         # black king in check
             "8/7k/8/6Q1/8/8/8/K7 b - - 0 1"]         # clean
    seen = []
    def describe(fen):
        seen.append(fen)
        return {"fen": fen, "solution": "Kh8 Qg7#", "themes": []}
    best = pp.best_candidate(entry, pp.PublishedIndex([]), mine=lambda m, d, n: cands, describe_fn=describe)
    assert best["fen"] == "8/7k/8/6Q1/8/8/8/K7 b - - 0 1" and pp.rank(best["quality"]) == 0
    assert cands[0] not in seen  # never described: illegal diagrams are skipped on the FEN alone
