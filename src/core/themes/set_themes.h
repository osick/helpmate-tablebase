#pragma once
#include <string>
#include <string_view>
#include <vector>

#include "themes/registry.h"

namespace hm::themes {

// Detectors over the whole solution SET -- the questions a single-problem
// analyser has to find every solution to answer, and this project gets for
// free from `solutions()`. Plain functions on ThemeInput, like has_set_play;
// each refuses an empty set and, where the theme compares solutions, a set
// of one. On a saturated position `probe` hands these the first 100
// solutions only, so their doc strings carry that caveat.

// Zilahi: two solutions and two white units X != Y such that X gives mate in
// one solution and is captured in the other, and Y gives mate in the second
// and is captured in the first. Units are identified by diagram square
// (themes/identity.h); the mating unit is the one that MOVED on the last ply,
// which for a battery mate is the front piece, stated rather than guessed.
bool has_zilahi(const ThemeInput& in);

// Allumwandlung: across all solutions, pawns of either colour promote to all
// four types -- queen, rook, bishop and knight -- in any number of solutions.
// Set COVERAGE, as the 2026-08-08 design fixed it; the exact-multiset
// question is `promotions:<types>`, a different theme.
bool has_allumwandlung(const ThemeInput& in);

// The `promotions:<types>` parametric theme, over the promotions of ALL
// solutions taken together with multiplicity: `promotions_eval` answers
// whether that combined multiset CONTAINS the canonical value (q and r in
// one solution plus r in another satisfies qrr, and so does q, r, r, n);
// `promotions_values` returns the combined multiset itself, one value, for
// `probe`, or nothing when no solution promotes.
bool promotions_eval(const ThemeInput& in, std::string_view canon_value);
std::vector<std::string> promotions_values(const ThemeInput& in);

// The registry's descriptor for `promotions:<types>`.
extern const ThemeParam kPromotionsParam;

}  // namespace hm::themes
