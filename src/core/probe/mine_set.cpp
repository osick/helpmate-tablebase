#include "probe/mine_set.h"

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

int MineSet::enum_cap(const Hit& h) const { return h.count >= (int)COUNT_SAT ? 100 : h.count; }

template <class F>
void MineSet::guarded(Hit& h, F&& f) const {
    if (!h.unavailable.empty()) return;
    try {
        f();
    } catch (const MissingTableError& e) { h.unavailable = e.what(); }
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

}  // namespace hm
