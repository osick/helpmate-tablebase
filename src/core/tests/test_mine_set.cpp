#include <algorithm>
#include <catch2/catch_test_macros.hpp>
#include <climits>
#include <filesystem>

#include "generator/generator.h"
#include "probe/mine_set.h"
#include "themes/registry.h"

using namespace hm;

namespace {
std::string gen_kqvk() {
    static std::string dir;
    if (dir.empty()) {
        dir = (std::filesystem::temp_directory_path() / "hm_mine_set_test").string();
        std::filesystem::create_directories(dir);
        GenOptions opt;
        opt.tables_dir = dir;
        generate(*Material::parse("KQvk"), opt);
    }
    return dir;
}
const char* kGolden = "8/7k/5K2/8/8/8/8/6Q1 b - - 0 1";
const char* kFirst = "8/8/8/8/8/8/8/k1KQ4 b - - 0 1";
const char* kSecond = "8/8/8/8/8/2Q5/8/k1K5 b - - 0 1";

MineSet kqvk_set(const Tablebase& tb, int dtm = 2, int cap = INT_MAX) {
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = dtm}, cap);
    uint64_t skipped = 0;
    tb.mine(
        *Material::parse("KQvk"), MineFilter{.dtm = dtm},
        [&](const std::string& f) {
            s.add(f);
            return (int)s.size() < cap;
        },
        &skipped);
    s.set_skipped_saturated(skipped);
    return s;
}
}  // namespace

TEST_CASE("MineSet::add probes dtm and count", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 10);
    REQUIRE(s.size() == 0);
    s.add(kGolden);
    s.add(kFirst);
    REQUIRE(s.size() == 2);
    REQUIRE(s.hits()[0].fen == kGolden);
    REQUIRE(s.hits()[0].dtm == 2);
    REQUIRE(s.hits()[0].count == 4);
    REQUIRE(s.hits()[1].count == 1);
    REQUIRE_FALSE(s.hits()[0].shape.has_value());  // nothing enriched yet
    REQUIRE(s.max() == 10);
    REQUIRE(s.filter().dtm == 2);
    REQUIRE(s.material().name() == "KQvk");
}

TEST_CASE("MineSet loads a whole scan", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb);
    REQUIRE(s.size() == 580);
    REQUIRE(s.hits()[0].fen == kFirst);
    REQUIRE(s.hits()[1].fen == kSecond);
    REQUIRE(s.skipped_saturated() == 0);
    REQUIRE(s.max() == INT_MAX);
}

TEST_CASE("non_parametric drops parametric entries only", "[mine_set]") {
    std::vector<std::string> in{"mirror", "promotions:q", "single-piece:white", "promotions:qrr"};
    auto out = non_parametric(in);
    REQUIRE(out == std::vector<std::string>{"mirror", "single-piece:white"});
    // Sanity: the registry really has exactly one parametric entry today.
    int parametric = 0;
    for (const auto& t : themes::theme_registry()) parametric += t.param != nullptr;
    REQUIRE(parametric == 1);
}

TEST_CASE("enrichment fills shape, themes and solutions once", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 10);
    s.add(kGolden);
    Hit h = s.hits()[0];
    s.ensure_shape(h);
    REQUIRE(h.shape);
    REQUIRE(h.shape->starts == 2);
    REQUIRE(h.shape->ends == 4);
    s.ensure_solutions(h);
    REQUIRE(h.solutions);
    REQUIRE(h.solutions->size() == 4);
    REQUIRE((*h.solutions)[3] == std::vector<std::string>{"Kh8", "Qg7#"});
    s.ensure_themes(h);
    REQUIRE(h.themes);
    auto& t = *h.themes;
    REQUIRE(std::find(t.begin(), t.end(), "mirror") != t.end());
    for (const auto& n : t) REQUIRE(themes::resolve_theme(n)->def->param == nullptr);
    REQUIRE(h.unavailable.empty());
}

TEST_CASE("ensure_themes_all reports progress and is idempotent", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb, 2, 250);
    REQUIRE(s.size() == 250);
    REQUIRE_FALSE(s.all_have_themes());
    std::vector<std::pair<size_t, size_t>> ticks;
    s.ensure_themes_all([&](size_t d, size_t t) { ticks.emplace_back(d, t); });
    REQUIRE(s.all_have_themes());
    REQUIRE_FALSE(ticks.empty());
    REQUIRE(ticks.back() == std::pair<size_t, size_t>{250, 250});
    ticks.clear();
    s.ensure_themes_all([&](size_t d, size_t t) { ticks.emplace_back(d, t); });
    REQUIRE(ticks.empty());  // nothing left to do: no callback at all
    REQUIRE(s.unavailable_count() == 0);
}

TEST_CASE("a hit whose enrichment needs a missing table is marked, not dropped", "[mine_set]") {
    // A Tablebase over an EMPTY directory: probe/solutions throw MissingTableError.
    auto empty = (std::filesystem::temp_directory_path() / "hm_mine_set_empty").string();
    std::filesystem::create_directories(empty);
    Tablebase tb(empty);
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 10);
    Hit h;
    h.fen = kGolden;
    h.dtm = 2;
    h.count = 4;
    s.add(h);
    Hit copy = s.hits()[0];
    s.ensure_themes(copy);
    REQUIRE_FALSE(copy.themes);
    REQUIRE_FALSE(copy.unavailable.empty());
    s.ensure_solutions(copy);  // skipped: already unavailable, must not throw
    REQUIRE_FALSE(copy.solutions);
    s.ensure_themes_all();
    REQUIRE(s.unavailable_count() == 1);
}

TEST_CASE("with_theme narrows, negates, and leaves the source intact", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb);
    auto mirror = s.with_theme("mirror", false);
    auto rest = s.with_theme("mirror", true);
    REQUIRE(s.size() == 580);
    REQUIRE(mirror.size() == 477);
    REQUIRE(rest.size() == 103);
    REQUIRE(mirror.hits()[0].fen == kFirst);
    REQUIRE(rest.hits()[0].fen == kSecond);
    REQUIRE(mirror.material().name() == "KQvk");
    REQUIRE(mirror.max() == INT_MAX);
    // the source was enriched as a side effect, so a second narrowing is free
    REQUIRE(s.all_have_themes());
    REQUIRE_THROWS_AS(s.with_theme("nosuch", false), std::invalid_argument);
}

TEST_CASE("with_theme accepts a parametric name", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb, 2, 20);
    auto promo = s.with_theme("promotions:q", false);  // no pawn in KQvk
    REQUIRE(promo.size() == 0);
    auto nopromo = s.with_theme("promotions:q", true);
    REQUIRE(nopromo.size() == 20);
}

TEST_CASE("count/starts/ends narrowing", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb);
    REQUIRE(s.with_count(1).size() == 356);
    REQUIRE(s.with_theme("mirror", false).with_count(1).size() == 257);
    MineSet g(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 10);
    g.add(kGolden);
    g.add(kFirst);
    REQUIRE(g.with_starts(2).size() == 1);
    REQUIRE(g.with_ends(4).size() == 1);
    REQUIRE(g.with_ends(1).hits()[0].fen == kFirst);
    REQUIRE(g.with_starts(3).size() == 0);
}

TEST_CASE("theme_histogram lists every non-parametric theme in registry order", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    auto s = kqvk_set(tb, 2, 50);
    auto h = s.theme_histogram();
    std::vector<std::string> expect;
    for (const auto& t : themes::theme_registry())
        if (!t.param) expect.push_back(std::string(t.name));
    REQUIRE(h.size() == expect.size());
    for (size_t i = 0; i < h.size(); ++i) REQUIRE(h[i].first == expect[i]);
    size_t mirror = 0;
    for (const auto& [n, c] : h)
        if (n == "mirror") mirror = c;
    REQUIRE(mirror == s.with_theme("mirror", false).size());
    REQUIRE(mirror > 0);
}
