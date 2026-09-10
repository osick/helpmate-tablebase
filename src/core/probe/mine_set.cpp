#include "probe/mine_set.h"

#include <algorithm>
#include <climits>
#include <nlohmann/json.hpp>
#include <stdexcept>

#include "chess/types.h"
#include "themes/registry.h"

namespace hm {

std::vector<std::string> non_parametric(const std::vector<std::string>& names) {
    std::vector<std::string> out;
    for (const auto& n : names) {
        auto r = themes::resolve_theme(n);
        if (r && r->def->param == nullptr) out.push_back(n);
    }
    return out;
}

MineSet::MineSet(const Tablebase& tb, Material m, MineFilter f, int max)
    : tb_(&tb), m_(std::move(m)), f_(std::move(f)), max_(max) {}

void MineSet::add(const std::string& fen) {
    Hit h;
    h.fen = fen;
    if (auto p = tb_->probe(fen)) {
        h.dtm = p->dtm;
        h.count = p->count;
    }
    hits_.push_back(std::move(h));
}

void MineSet::add(Hit h) { hits_.push_back(std::move(h)); }

Hit& MineSet::hit(size_t i) {
    if (i >= hits_.size())
        throw std::out_of_range("MineSet::hit: no hit " + std::to_string(i) + " (set has " +
                                std::to_string(hits_.size()) + ")");
    return hits_[i];
}

int MineSet::enum_cap(const Hit& h) const { return h.count >= (int)COUNT_SAT ? 100 : h.count; }

template <class F>
void MineSet::guarded(Hit& h, F&& f) const {
    if (!h.unavailable.empty()) return;
    try {
        f();
    } catch (const MissingTableError& e) {
        h.unavailable = e.what();
    } catch (const UnsupportedTableVersionError& e) {
        // Same contract as a missing table from the caller's point of view:
        // this hit cannot be annotated, but it is still a hit. Letting this
        // one escape would kill the shell mid-narrowing.
        h.unavailable = e.what();
    }
}

void MineSet::ensure_shape(Hit& h) const {
    if (h.shape) return;
    guarded(h, [&] { h.shape = tb_->solution_shape(h.fen); });
}

void MineSet::ensure_themes(Hit& h) const {
    if (h.themes) return;
    guarded(h, [&] { h.themes = non_parametric(tb_->themes_of(h.fen, enum_cap(h))); });
}

void MineSet::ensure_solutions(Hit& h) const {
    if (h.solutions) return;
    guarded(h, [&] { h.solutions = tb_->lines(h.fen, enum_cap(h)); });
}

void MineSet::ensure_themes_all(const Progress& progress) {
    size_t done = 0;
    for (auto& h : hits_) {
        ++done;
        if (h.themes || !h.unavailable.empty()) continue;
        ensure_themes(h);
        if (progress) progress(done, hits_.size());
    }
}

void MineSet::ensure_solutions_all(const Progress& progress) {
    size_t done = 0;
    for (auto& h : hits_) {
        ++done;
        if ((h.solutions && h.shape) || !h.unavailable.empty()) continue;
        ensure_solutions(h);
        ensure_shape(h);
        if (progress) progress(done, hits_.size());
    }
}

bool MineSet::all_have_themes() const {
    for (const auto& h : hits_)
        if (!h.themes && h.unavailable.empty()) return false;
    return true;
}

size_t MineSet::unavailable_count() const {
    size_t n = 0;
    for (const auto& h : hits_) n += !h.unavailable.empty();
    return n;
}

MineSet MineSet::empty_like() const {
    MineSet s(*tb_, m_, f_, max_);
    s.skipped_ = skipped_;
    return s;
}

template <class Pred>
MineSet MineSet::filtered(Pred&& keep) const {
    MineSet out = empty_like();
    for (const auto& h : hits_)
        if (h.unavailable.empty() && keep(h)) out.hits_.push_back(h);
    return out;
}

MineSet MineSet::with_theme(const std::string& name, bool negate, const Progress& progress) {
    std::string err;
    auto r = themes::resolve_theme(name, &err);
    if (!r) throw std::invalid_argument(err);
    if (r->def->param == nullptr) {
        ensure_themes_all(progress);
        const std::string canon = r->name();
        return filtered([&](const Hit& h) {
            bool shows = std::find(h.themes->begin(), h.themes->end(), canon) != h.themes->end();
            return shows != negate;
        });
    }
    // Parametric: the registry's own eval per hit; no cache, the value differs per query.
    MineSet out = empty_like();
    size_t done = 0;
    for (auto& h : hits_) {
        ++done;
        if (!h.unavailable.empty()) continue;
        bool shows = false;
        guarded(h, [&] { shows = tb_->shows_theme(h.fen, *r, enum_cap(h)); });
        if (h.unavailable.empty() && shows != negate) out.hits_.push_back(h);
        if (progress) progress(done, hits_.size());
    }
    return out;
}

MineSet MineSet::with_count(int n) {
    return filtered([&](const Hit& h) { return h.count == n; });
}

MineSet MineSet::with_starts(int n) {
    for (auto& h : hits_) ensure_shape(h);
    return filtered([&](const Hit& h) { return h.shape->exhaustive && h.shape->starts == n; });
}

MineSet MineSet::with_ends(int n) {
    for (auto& h : hits_) ensure_shape(h);
    return filtered([&](const Hit& h) { return h.shape->exhaustive && h.shape->ends == n; });
}

std::vector<std::pair<std::string, size_t>> MineSet::theme_histogram(const Progress& progress) {
    ensure_themes_all(progress);
    std::vector<std::pair<std::string, size_t>> out;
    for (const auto& t : themes::theme_registry()) {
        if (t.param) continue;
        std::string name(t.name);
        size_t n = 0;
        for (const auto& h : hits_)
            if (h.themes && std::find(h.themes->begin(), h.themes->end(), name) != h.themes->end()) ++n;
        out.emplace_back(std::move(name), n);
    }
    return out;
}

void MineSet::enrich_for(Facets f, const Progress& progress) {
    if (f.themes) ensure_themes_all(progress);
    if (f.solutions) ensure_solutions_all(progress);
}

std::string MineSet::to_json(Facets f, const Progress& progress) {
    enrich_for(f, progress);
    nlohmann::ordered_json j;
    j["material"] = m_.name();
    j["filter"] = {{"dtm", f_.dtm},
                   {"count", f_.count},
                   {"starts", f_.starts},
                   {"ends", f_.ends},
                   {"themes", f_.themes}};
    if (max_ == INT_MAX) j["max"] = "infinity";
    else j["max"] = max_;
    j["skipped_saturated"] = skipped_;
    auto positions = nlohmann::ordered_json::array();
    for (const auto& h : hits_) {
        nlohmann::ordered_json p;
        p["fen"] = h.fen;
        p["dtm"] = h.dtm;
        p["count"] = h.count;
        if (!h.unavailable.empty()) {
            p["unavailable"] = h.unavailable;
        } else {
            if (f.themes && h.themes) p["themes"] = *h.themes;
            if (f.solutions && h.shape && h.solutions) {
                // A saturated position has no countable solution set, so
                // `starts`/`ends` would be a guess presented as a fact: say
                // so with one explicit key instead, and keep `solutions`,
                // which is honestly the first 100 (enum_cap).
                if (h.shape->exhaustive) {
                    p["starts"] = h.shape->starts;
                    p["ends"] = h.shape->ends;
                } else {
                    p["exhaustive"] = false;
                }
                p["solutions"] = *h.solutions;
            }
        }
        positions.push_back(std::move(p));
    }
    j["positions"] = std::move(positions);
    return j.dump(2) + "\n";
}

void MineSet::write_hit(std::ostream& os, const Hit& h, Facets f) const {
    os << h.fen << "\n";
    if (!f.themes && !f.solutions) return;
    if (!h.unavailable.empty()) {
        os << "  unavailable: " << h.unavailable << "\n";
        return;
    }
    if (f.themes && h.themes) {
        os << "  themes:";
        if (h.themes->empty()) os << " (none)";
        for (const auto& n : *h.themes) os << " " << n;
        os << "\n";
    }
    if (f.solutions && h.solutions) {
        for (const auto& line : *h.solutions) {
            if (line.empty()) continue;  // dtm 0: already mate, nothing to print
            os << " ";
            for (const auto& mv : line) os << " " << mv;
            os << "\n";
        }
        // Same honesty as to_json's `exhaustive`: these are the first 100 of
        // an uncountable set, not the whole set.
        if (h.shape && !h.shape->exhaustive) os << "  (solution count saturated: first 100 solutions only)\n";
    }
}

void MineSet::to_text(std::ostream& os, Facets f, const Progress& progress) {
    enrich_for(f, progress);
    const bool facets = f.themes || f.solutions;
    for (const auto& h : hits_) {
        write_hit(os, h, f);
        if (facets) os << "\n";  // one blank line between annotated hits
    }
}

}  // namespace hm
