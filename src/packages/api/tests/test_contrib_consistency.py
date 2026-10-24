import os
import random
from pathlib import Path

import chess
import helpmate
import pytest

from contrib_helpers import rewrite_payload
from helpmate_server.contrib.consistency import (
    MissingSubtable, check_consistency, check_position, random_position,
)
from helpmate_server.contrib.materials import Material


def test_random_positions_are_legal_and_of_the_material():
    rng = random.Random(1)
    fens = [f for f in (random_position(Material("KPvkp"), rng) for _ in range(300)) if f]
    assert len(fens) > 100
    for f in fens:
        b = chess.Board(f)
        assert b.is_valid()
        assert sorted(p.symbol() for p in b.piece_map().values()) == sorted("KPkp")


@pytest.mark.parametrize("mat", ["KQvk", "KPvk"])
def test_clean_tables_are_consistent(compressed_tables, mat):
    c, fens = check_consistency(mat, compressed_tables, samples=400, seed=7, extra_fens=[])
    assert c.status == "pass", c.detail
    assert len(fens) == 800


def test_mate_and_stalemate(compressed_tables):
    tb = helpmate.Tablebase(str(compressed_tables))
    assert check_position(tb, "k7/1Q6/1K6/8/8/8/8/8 b - - 0 1") is None   # mate: (0, 1)
    assert check_position(tb, "k7/2Q5/1K6/8/8/8/8/8 b - - 0 1") is None   # stalemate: None


def test_one_wrong_cell_is_caught(table_copy):
    p = table_copy / "KQvk.hm"
    tb = helpmate.Tablebase(str(table_copy))
    fen = "8/8/8/8/8/2k5/8/K1Q5 b - - 0 1"
    dtm, count, _ = tb.probe(fen)

    # Find that position's cell by value scan is not possible without the
    # index; instead damage EVERY btm cell with this (dtm, count) pair.
    def damage(payload, ps):
        for i in range(ps, 2 * ps):
            if payload[i] == dtm and payload[2 * ps + i] == count:
                payload[2 * ps + i] = count - 1
    rewrite_payload(p, damage)
    tb2 = helpmate.Tablebase(str(table_copy))
    assert "successors imply" in (check_position(tb2, fen) or "")


def test_missing_subtable_is_an_environment_error(tmp_path, compressed_tables):
    for ext in (".hm", ".stats.json"):
        (tmp_path / f"KPvk{ext}").write_bytes((compressed_tables / f"KPvk{ext}").read_bytes())
    with pytest.raises(MissingSubtable):
        check_consistency("KPvk", tmp_path, samples=50, seed=1, extra_fens=[])


class _FlippedSuccessors:
    """Every successor is found only with colours flipped (probe's third field)."""
    def moves(self, fen):
        return [{"uci": m.uci(), "fen": fen, "solvable": True, "dtm": 3, "count": 1}
                for m in chess.Board(fen).legal_moves]

    def probe(self, fen):
        return (3, 1, True)


def test_a_colour_flipped_successor_is_a_missing_subtable():
    with pytest.raises(MissingSubtable, match="colours flipped"):
        check_position(_FlippedSuccessors(), "8/8/8/8/8/8/8/K6k w - - 0 1")


def test_a_recorded_impossible_position_is_skipped_with_a_warning(compressed_tables):
    impossible = "k7/1Q6/8/8/8/8/8/K7 w - - 0 1"   # Black in check with White to move
    assert not chess.Board(impossible).is_valid()
    c, _ = check_consistency("KQvk", compressed_tables, samples=50, seed=7,
                             extra_fens=[impossible])
    assert c.status == "warn", c.detail
    assert "skipped 1 recorded position(s) no game can reach" in c.detail
    assert impossible in c.detail


def test_a_recorded_legal_position_is_still_checked(compressed_tables):
    fen = "8/8/8/8/8/2k5/8/K1Q5 b - - 0 1"
    c, _ = check_consistency("KQvk", compressed_tables, samples=50, seed=7, extra_fens=[fen])
    assert c.status == "pass", c.detail
    assert c.detail.startswith("101 positions"), c.detail


CORPUS = Path(os.path.expanduser("~/tb"))


@pytest.mark.skipif(not (CORPUS / "KRBvkqp.hm").exists(), reason="needs the real corpus")
@pytest.mark.parametrize("mat", ["KQvkr", "KBNvk", "KRvkp", "KQPvkr", "KRBvkqp"])
def test_real_corpus_tables_are_consistent(mat):
    c, _ = check_consistency(mat, CORPUS, samples=300, seed=11, extra_fens=[])
    assert c.status == "pass", c.detail
