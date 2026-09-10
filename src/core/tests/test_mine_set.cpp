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
    tb.mine(*Material::parse("KQvk"), MineFilter{.dtm = dtm},
            [&](const std::string& f) { s.add(f); return (int)s.size() < cap; }, &skipped);
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
