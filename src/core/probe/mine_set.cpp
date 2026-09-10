#include "probe/mine_set.h"

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

}  // namespace hm
