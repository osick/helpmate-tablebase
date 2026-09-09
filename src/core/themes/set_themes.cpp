#include "themes/set_themes.h"

#include <algorithm>

#include "themes/identity.h"
#include "themes/line_themes.h"

namespace hm::themes {

namespace {
struct MateAndCaptures {
    int mate = -1;                     // diagram square of the mating mover
    std::vector<int> captured_white;   // diagram squares of white units captured
};

MateAndCaptures mate_and_captures(const Solution& s) {
    MateAndCaptures mc;
    if (s.plies.empty()) return mc;
    const auto ids = identities(s);
    mc.mate = ids.back().mover_origin;
    for (size_t i = 0; i < s.plies.size(); ++i)
        // A white unit is captured by a BLACK ply; the ply's own colour says
        // whose unit died.
        if (ids[i].captured_origin >= 0 && s.plies[i].piece.color == Color::Black)
            mc.captured_white.push_back(ids[i].captured_origin);
    return mc;
}

bool contains(const std::vector<int>& v, int x) { return std::find(v.begin(), v.end(), x) != v.end(); }
}  // namespace

bool has_zilahi(const ThemeInput& in) {
    if (in.solutions.size() < 2) return false;
    std::vector<MateAndCaptures> mcs;
    mcs.reserve(in.solutions.size());
    for (const auto& s : in.solutions) mcs.push_back(mate_and_captures(s));
    for (size_t a = 0; a < mcs.size(); ++a) {
        if (mcs[a].mate < 0) continue;
        for (size_t b = a + 1; b < mcs.size(); ++b) {
            if (mcs[b].mate < 0 || mcs[a].mate == mcs[b].mate) continue;
            if (contains(mcs[b].captured_white, mcs[a].mate) && contains(mcs[a].captured_white, mcs[b].mate))
                return true;
        }
    }
    return false;
}

bool has_allumwandlung(const ThemeInput& in) {
    if (in.solutions.empty()) return false;
    bool q = false, r = false, b = false, n = false;
    for (const auto& s : in.solutions)
        for (const auto& p : s.plies) {
            if (!p.promotion) continue;
            switch (*p.promotion) {
                case PieceType::Queen:
                    q = true;
                    break;
                case PieceType::Rook:
                    r = true;
                    break;
                case PieceType::Bishop:
                    b = true;
                    break;
                case PieceType::Knight:
                    n = true;
                    break;
                default:
                    break;
            }
        }
    return q && r && b && n;
}

bool promotions_eval(const ThemeInput& in, std::string_view canon_value) {
    for (const auto& s : in.solutions)
        if (promotion_multiset(s) == canon_value) return true;
    return false;
}

std::vector<std::string> promotions_values(const ThemeInput& in) {
    std::vector<std::string> out;
    for (const auto& s : in.solutions) {
        std::string m = promotion_multiset(s);
        if (m.empty()) continue;
        if (std::find(out.begin(), out.end(), m) == out.end()) out.push_back(std::move(m));
    }
    return out;
}

const ThemeParam kPromotionsParam{
    "types",
    "one letter per promotion, q r b n in any order and case, up to eight; matched as a "
    "multiset, so qrr is one queen and two rooks and rq is the same as qr",
    "qrr",
    &canon_promotions,
    &promotions_eval,
    &promotions_values,
};

}  // namespace hm::themes
