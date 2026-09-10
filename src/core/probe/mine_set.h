#pragma once
#include <cstdint>
#include <functional>
#include <optional>
#include <ostream>
#include <string>
#include <utility>
#include <vector>

#include "indexing/material.h"
#include "probe/tablebase.h"

namespace hm {

// One mined position. dtm/count come from a single probe at load; the
// optionals are filled on demand and cached. `unavailable` non-empty means
// enrichment threw MissingTableError (its text) -- the hit stays in the set,
// never matches a theme or shape narrowing, and says so in every output.
struct Hit {
    std::string fen;
    int dtm = -1, count = -1;
    std::optional<SolutionShape> shape;
    std::optional<std::vector<std::string>> themes;                  // non-parametric names only
    std::optional<std::vector<std::vector<std::string>>> solutions;  // SAN, one vector per solution
    std::string unavailable;
};

// Keeps the entries of a themes_of() result whose registry entry is not
// parametric. Judged by the registry (`param == nullptr`), never by the
// presence of a colon: single-piece:white is a full non-parametric name.
std::vector<std::string> non_parametric(const std::vector<std::string>& names);

// A mine result held in memory: the hits of one scan plus everything that
// can be computed from them without rescanning. Narrowing returns a new set
// so the shell can keep the old one for `back`.
class MineSet {
public:
    struct Facets {
        bool themes = false;
        bool solutions = false;
    };
    using Progress = std::function<void(size_t done, size_t total)>;

    MineSet(const Tablebase& tb, Material m, MineFilter f, int max);

    void add(const std::string& fen);  // one probe: dtm, count
    void add(Hit h);
    const std::vector<Hit>& hits() const { return hits_; }
    size_t size() const { return hits_.size(); }
    const Material& material() const { return m_; }
    const MineFilter& filter() const { return f_; }
    int max() const { return max_; }  // INT_MAX = infinity
    uint64_t skipped_saturated() const { return skipped_; }
    void set_skipped_saturated(uint64_t n) { skipped_ = n; }

    // Enrichment: idempotent, cached in the hit. A MissingTableError marks
    // the hit unavailable (its text) instead of propagating; a hit already
    // marked is skipped. Progress, when given, is called after every hit
    // that actually needed work, with (done, total) over the whole set, and
    // never when there was nothing to do.
    void ensure_shape(Hit& h) const;
    void ensure_themes(Hit& h) const;
    void ensure_solutions(Hit& h) const;
    void ensure_themes_all(const Progress& progress = nullptr);
    void ensure_solutions_all(const Progress& progress = nullptr);
    bool all_have_themes() const;
    size_t unavailable_count() const;

    // Narrowing. Each returns a NEW set (same tb/material/filter/max/skipped)
    // holding the hits that match; `this` keeps its hits, now enriched, so
    // the shell's `back` costs nothing. A hit marked unavailable never
    // matches, with or without `negate`. Unknown theme: std::invalid_argument
    // carrying resolve_theme's message.
    MineSet with_theme(const std::string& name, bool negate, const Progress& progress = nullptr);
    MineSet with_count(int n);
    MineSet with_starts(int n);
    MineSet with_ends(int n);

    // (name, hits showing it) for every non-parametric registry theme, in
    // registry order, zeros included. Forces ensure_themes_all.
    std::vector<std::pair<std::string, size_t>> theme_histogram(const Progress& progress = nullptr);

    // Output. Both force whatever enrichment the facets need, hence non-const.
    std::string to_json(Facets f, const Progress& progress = nullptr);
    void to_text(std::ostream& os, Facets f, const Progress& progress = nullptr);

private:
    int enum_cap(const Hit& h) const;  // COUNT_SAT -> 100, else the hit's own count
    template <class F>
    void guarded(Hit& h, F&& f) const;  // runs f, marks unavailable on MissingTableError
    MineSet empty_like() const;         // same tb/material/filter/max/skipped, no hits
    template <class Pred>
    MineSet filtered(Pred&& keep) const;
    void enrich_for(Facets f, const Progress& progress);

    const Tablebase* tb_;
    Material m_;
    MineFilter f_;
    int max_;
    uint64_t skipped_ = 0;
    std::vector<Hit> hits_;
};

}  // namespace hm
