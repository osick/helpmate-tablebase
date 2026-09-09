#include "themes/identity.h"

#include <array>

namespace hm::themes {

std::vector<PlyIdentity> identities(const Solution& s) {
    // origin[sq]: the diagram square of the unit now on sq, or -1; type[sq]:
    // that unit's current type. Both are indexed by square, not colour: a
    // square holds at most one unit, and a capture replaces the occupant.
    std::array<int, 64> origin;
    std::array<PieceType, 64> type;
    origin.fill(-1);
    for (const auto& pp : s.start.pieces()) {
        origin[pp.square] = pp.square;
        type[pp.square] = pp.piece.type;
    }

    std::vector<PlyIdentity> out;
    out.reserve(s.plies.size());
    for (const auto& p : s.plies) {
        PlyIdentity id;
        id.mover_origin = origin[p.from];
        id.mover_type = type[p.from];
        if (p.captured) {
            // An en-passant capture takes the pawn standing beside `to`, on
            // the capturing pawn's own rank -- the same formula as
            // trajectory.cpp's `gone`.
            const int gone = p.is_ep ? (sq_rank(p.from) * 8 + sq_file(p.to)) : (int)p.to;
            id.captured_origin = origin[gone];
            origin[gone] = -1;
        }
        origin[p.to] = id.mover_origin;
        type[p.to] = p.promotion.value_or(type[p.from]);
        origin[p.from] = -1;
        out.push_back(id);
    }
    return out;
}

}  // namespace hm::themes
