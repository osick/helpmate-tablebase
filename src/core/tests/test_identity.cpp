#include <catch2/catch_test_macros.hpp>

#include "probe/solution.h"
#include "themes/identity.h"

using namespace hm;
using namespace hm::themes;

namespace {
int sq(const char* n) { return (n[1] - '1') * 8 + (n[0] - 'a'); }

struct MoveSpec {
    const char* from;
    const char* to;
    std::optional<PieceType> promo;
};

// Same fixture builder as test_line_themes.cpp: legal moves only, boards by
// Board::make, ply fields filled the way collect_solutions fills them.
Solution play(const std::string& fen, const std::vector<MoveSpec>& specs) {
    auto b = Board::from_fen(fen);
    REQUIRE(b);
    Solution s{*b, {}};
    Board cur = *b;
    for (const auto& ms : specs) {
        const Move* found = nullptr;
        auto legal = cur.legal_moves();
        for (const auto& m : legal)
            if ((int)m.from == sq(ms.from) && (int)m.to == sq(ms.to) && m.promotion() == ms.promo) found = &m;
        REQUIRE(found != nullptr);
        Ply p;
        p.from = found->from;
        p.to = found->to;
        p.promotion = found->promotion();
        p.is_ep = found->is_ep();
        for (const auto& pp : cur.pieces()) {
            if ((int)pp.square == (int)found->from) p.piece = pp.piece;
            else if ((int)pp.square == (int)found->to) p.captured = pp.piece.type;
        }
        if (p.is_ep) p.captured = PieceType::Pawn;
        cur.make(*found);
        p.is_check = cur.in_check();
        p.after = cur;
        s.plies.push_back(std::move(p));
    }
    return s;
}
}  // namespace

TEST_CASE("identities follow a unit through moves and name its origin", "[themes][identity]") {
    // White king walks e1-e2-e3; black king a8-b8.
    auto s = play("k7/8/8/8/8/8/8/4K3 w - - 0 1", {{"e1", "e2", {}}, {"a8", "b8", {}}, {"e2", "e3", {}}});
    auto ids = identities(s);
    REQUIRE(ids.size() == 3);
    CHECK(ids[0].mover_origin == sq("e1"));
    CHECK(ids[2].mover_origin == sq("e1"));  // still the e1 king, now moving from e2
    CHECK(ids[1].mover_origin == sq("a8"));
    CHECK(ids[0].mover_type == PieceType::King);
    CHECK(ids[0].captured_origin == -1);
}

TEST_CASE("identities report the captured unit's origin, including through a recapture",
          "[themes][identity]") {
    // Black pawn d6-d5, Rd1xd5, Rd8xd5: the white rook that started on d1 dies
    // on d5, captured by the rook that started on d8.
    auto s =
        play("3r3k/8/3p4/8/8/8/8/K2R4 b - - 0 1", {{"d6", "d5", {}}, {"d1", "d5", {}}, {"d8", "d5", {}}});
    auto ids = identities(s);
    CHECK(ids[1].captured_origin == sq("d6"));  // the pawn, by its diagram square
    CHECK(ids[2].mover_origin == sq("d8"));
    CHECK(ids[2].captured_origin == sq("d1"));
}

TEST_CASE("identities locate an en-passant victim beside the capture square", "[themes][identity]") {
    auto s = play("k7/6p1/8/5P2/8/8/8/K7 b - - 0 1", {{"g7", "g5", {}}, {"f5", "g6", {}}});
    auto ids = identities(s);
    REQUIRE(s.plies[1].is_ep);
    CHECK(ids[1].captured_origin == sq("g7"));  // the pawn that started on g7, taken on g5
    CHECK(ids[1].mover_origin == sq("f5"));
}

TEST_CASE("identities give a promoted pawn its new type on later plies but keep its origin",
          "[themes][identity]") {
    auto s = play("k7/6P1/8/8/8/8/8/K7 w - - 0 1",
                  {{"g7", "g8", PieceType::Queen}, {"a8", "a7", {}}, {"g8", "g3", {}}});
    auto ids = identities(s);
    CHECK(ids[0].mover_type == PieceType::Pawn);   // the promoting ply is still a pawn move
    CHECK(ids[2].mover_type == PieceType::Queen);  // afterwards it is a queen
    CHECK(ids[2].mover_origin == sq("g7"));        // and still the g7 pawn by identity
}
