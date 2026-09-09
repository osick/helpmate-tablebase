#pragma once
#include <optional>
#include <string>
#include <string_view>
#include <vector>

#include "chess/types.h"
#include "probe/solution.h"

namespace hm::themes {

// What a detector must be given. Ordered by cost: a query needs only the
// most expensive input any of its themes asks for.
enum class Needs : uint8_t { Position = 0, Plane = 1, Solutions = 2 };

// The wire/display name of a Needs value. Defined once: every surface that
// reports `needs` uses this, so adding a fourth value cannot silently fall
// through to "solutions" in one surface and not another.
constexpr std::string_view needs_name(Needs n) {
    switch (n) {
        case Needs::Position:
            return "position";
        case Needs::Plane:
            return "plane";
        case Needs::Solutions:
            return "solutions";
    }
    return "solutions";
}

// Everything a detector may read. The CALLER fetches; the detector stays a
// pure function, so it is still testable against a hand-built position with
// no .hm file on disk. `solutions` is empty unless some theme needs it, and
// `other_plane` is nullopt unless some theme needs it. `value` is this
// position's own stored dtm/count -- needed by detectors (set-play) that
// compare the sibling plane against the position's OWN distance, not merely
// its solvability.
struct ThemeInput {
    const Board& start;
    ValuePair value;
    std::optional<ValuePair> other_plane;
    const std::vector<Solution>& solutions;
};

using Detector = bool (*)(const ThemeInput&);

// A PARAMETRIC theme: one registry entry, a family of questions. The user
// writes `name:value` (`promotions:qrr`); `canon` normalises and validates
// the value (nullopt = not a valid value), `eval` answers the yes/no for one
// canonical value, and `values` lists every canonical value the position
// shows, which is what `probe --themes` prints (`promotions:qrr`). The
// registry entry's `fn` is null for such a theme; it is never called as a
// boolean, because "promotions, unqualified" is not a question.
struct ThemeParam {
    std::string_view name;     // what the value is called, e.g. "types"
    std::string_view doc;      // what a value means and what is accepted
    std::string_view example;  // one valid value, for placeholders and errors
    std::optional<std::string> (*canon)(std::string_view raw);
    bool (*eval)(const ThemeInput&, std::string_view canon_value);
    std::vector<std::string> (*values)(const ThemeInput&);
};

struct ThemeDef {
    std::string_view name;
    Detector fn;
    std::string_view doc;  // the definition, shown by `helpmate themes`
    Needs needs;
    const ThemeParam* param = nullptr;  // non-null: parametric, fn is null
};

// "promotions:<types>" for a parametric entry, the bare name otherwise. The
// name every listing surface shows, so a user can see that a value is needed.
std::string display_name(const ThemeDef& t);

// A theme name as the user wrote it, resolved: the registry entry plus, for
// a parametric theme, its canonical value. This -- not a bare Detector -- is
// what `mine` evaluates, so the parametric case never leaks into the scan.
struct ResolvedTheme {
    const ThemeDef* def;
    std::string value;  // canonical; empty for a boolean theme
    bool eval(const ThemeInput& in) const;
    std::string name() const;  // "promotions:qrr", or the bare name
};

// Resolves `name`. Exact registry names first (so `excelsior:white` stays a
// full name, not `excelsior` with a value), then `base:value` against a
// parametric base. On failure returns nullopt and, if `error` is given,
// writes a message that names the problem: an unknown name, a parametric
// theme given without a value, a value the theme does not accept, or the
// singular typo `promotion:qrr` for `promotions:qrr` -- which must never
// silently match the boolean `promotion` with its value discarded.
std::optional<ResolvedTheme> resolve_theme(std::string_view name, std::string* error = nullptr);

// Adapts a per-solution detector to the registry signature, supplying the
// `any` the query surface uses for a positive theme ("some solution shows a
// switchback"). This is the ONLY place `any` is expressed.
template <bool (*F)(const Solution&)>
bool any_of(const ThemeInput& in) {
    for (const auto& s : in.solutions)
        if (F(s)) return true;
    return false;
}

// The `every` counterpart, for a theme that is a property of the whole
// solution set: "no solution captures" is false as soon as ONE solution
// does, so `any` would be the wrong adapter for it. An EMPTY set shows
// nothing -- a position whose solutions could not be enumerated must not
// vacuously match `nocapture`, the same way it does not match anything
// else. This is the ONLY place `every` is expressed.
template <bool (*F)(const Solution&)>
bool all_of(const ThemeInput& in) {
    if (in.solutions.empty()) return false;
    for (const auto& s : in.solutions)
        if (!F(s)) return false;
    return true;
}

// Every detector this build knows, in display order. CLI, API and dashboard
// all enumerate this rather than hard-coding names, so none of them needs
// touching when a theme is added.
const std::vector<ThemeDef>& theme_registry();

// nullptr when `name` is not registered. Matching is exact -- no case folding,
// no aliases: a near-miss should be an error naming the valid options, not a
// silent guess.
const ThemeDef* find_theme(std::string_view name);

// Names of every theme shown by `in` -- the `any` semantics the query surface
// uses (via any_of<>, for solution-based detectors). Returned in registry order.
// A parametric theme contributes one `name:value` entry per canonical value
// the position shows (`promotions:q promotions:rn`), and nothing when it
// shows none.
std::vector<std::string> detect(const ThemeInput& in);

}  // namespace hm::themes
