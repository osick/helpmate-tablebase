#include <catch2/catch_test_macros.hpp>
#include <climits>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sstream>

#include "generator/generator.h"
#include "probe/mine_set.h"
#include "probe/mine_shell.h"
#include "themes/registry.h"

using namespace hm;

namespace {
std::string gen_kqvk() {
    static std::string dir;
    if (dir.empty()) {
        dir = (std::filesystem::temp_directory_path() / "hm_mine_shell_test").string();
        std::filesystem::create_directories(dir);
        GenOptions opt;
        opt.tables_dir = dir;
        generate(*Material::parse("KQvk"), opt);
    }
    return dir;
}
const char* kFirst = "8/8/8/8/8/8/8/k1KQ4 b - - 0 1";

MineSet root(const Tablebase& tb, int cap = INT_MAX) {
    auto m = *Material::parse("KQvk");
    MineSet s(tb, m, MineFilter{.dtm = 2}, cap);
    tb.mine(m, MineFilter{.dtm = 2}, [&](const std::string& f) {
        s.add(f);
        return (int)s.size() < cap;
    });
    return s;
}

struct Run {
    int rc;
    std::string out, err;
};
Run run(const Tablebase& tb, const std::string& script, MineSet::Facets cli = {}, int cap = INT_MAX) {
    std::istringstream in(script);
    std::ostringstream out, err;
    int rc = run_mine_shell(root(tb, cap), in, out, err, cli, "tt");
    return {rc, out.str(), err.str()};
}
bool has(const std::string& s, const std::string& needle) { return s.find(needle) != std::string::npos; }
}  // namespace

TEST_CASE("shell: EOF and quit both end with 0; prompt shows the size on stderr", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "");
    REQUIRE(r.rc == 0);
    REQUIRE(r.out.empty());
    REQUIRE(has(r.err, "[580] mine> "));
    auto q = run(tb, "quit\nlist\n");
    REQUIRE(q.rc == 0);
    REQUIRE(q.out.empty());  // nothing after quit ran
}

TEST_CASE("shell: narrowing, back and reset", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "theme mirror\ncount 1\nback\nnot theme mirror\nreset\nback\n");
    // back restores the all-mirror set, so "not theme mirror" on it is empty.
    REQUIRE(r.out ==
            "477 positions\n257 positions\n477 positions\n0 positions\n580 positions\n580 positions\n");
    REQUIRE(has(r.err, "[477] mine> "));
    REQUIRE(has(r.err, "[257] mine> "));
    REQUIRE(has(r.err, "already at the root set"));
    REQUIRE(has(r.err, "evaluating: 100/580"));
}

TEST_CASE("shell: list and show", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "list 1 2\nshow 1\nshow 0\nlist 999\n", {}, 5);
    std::string expect_list =
        "     1  8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n     2  8/8/8/8/8/2Q5/8/k1K5 b - - 0 1\n";
    REQUIRE(r.out.rfind(expect_list, 0) == 0);
    REQUIRE(has(r.out, std::string(kFirst) + "\n  themes:"));
    REQUIRE(has(r.out, " mirror"));
    REQUIRE(has(r.out, "\n  Ka2 Qa4#\n"));
    REQUIRE(has(r.err, "no hit 0 (set has 5)"));
    REQUIRE(has(r.err, "no hit 999 (set has 5)"));
}

TEST_CASE("shell: themes histogram", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "themes\nlist 1 2\n", {}, 50);
    REQUIRE(has(r.out, "mirror"));
    // every non-parametric registry name appears, and 'promotions' (parametric) does not as a bare line
    REQUIRE_FALSE(has(r.out, "\npromotions  "));
    REQUIRE(has(r.out, "pure"));
    int non_parametric = 0;
    for (const auto& t : themes::theme_registry())
        if (t.param == nullptr) ++non_parametric;
    std::istringstream lines(r.out);
    std::string l;
    int n = 0;
    while (std::getline(lines, l)) ++n;
    REQUIRE(n == non_parametric + 2);  // + the two `list 1 2` lines that follow
    // `std::left` from the histogram must not leak into `list`'s right-aligned width-6 index.
    REQUIRE(has(r.out, "     1  8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n     2  8/8/8/8/8/2Q5/8/k1K5 b - - 0 1\n"));
}

TEST_CASE("shell: errors never end the loop", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "frobnicate\ntheme nosuch\ncount x\ncount\ncount 1\n", {}, 20);
    REQUIRE(r.rc == 0);
    REQUIRE(has(r.err, "unknown command \"frobnicate\"; type help"));
    REQUIRE(has(r.err, "unknown theme"));
    REQUIRE(has(r.err, "valid themes:"));
    REQUIRE(has(r.err, "count needs a positive integer"));
    REQUIRE(has(r.out, " positions\n"));  // the last command still ran
}

TEST_CASE("shell: save json and fens", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto dir = std::filesystem::temp_directory_path() / "hm_mine_shell_save";
    std::filesystem::create_directories(dir);
    auto jpath = (dir / "out.json").string();
    auto tpath = (dir / "out.txt").string();
    auto r = run(tb, "theme mirror\nsave " + jpath + "\nsave " + tpath + "\nsave /nonexistent/dir/x.json\n",
                 {.solutions = true}, 10);
    std::ifstream jf(jpath);
    auto j = nlohmann::json::parse(jf);
    REQUIRE(j["positions"].size() > 0);
    REQUIRE(j["positions"][0].contains("themes"));     // set was theme-narrowed: themes known
    REQUIRE(j["positions"][0].contains("solutions"));  // --solutions was on the command line
    REQUIRE(has(r.out, "to " + jpath + " (json, themes, solutions)"));
    std::ifstream tf(tpath);
    std::string first;
    std::getline(tf, first);
    REQUIRE(first == kFirst);
    REQUIRE(has(r.out, "to " + tpath + " (fens)"));
    REQUIRE(has(r.err, "cannot write /nonexistent/dir/x.json"));

    // A path with a space in it is one path, not a path plus junk: `save my
    // file.json` used to write a file called "my" and report that name.
    auto spath = (dir / "two words.json").string();
    auto r2 = run(tb, "save " + spath + "\n", {}, 3);
    REQUIRE(has(r2.out, "saved 3 positions to " + spath + " (json"));
    REQUIRE(std::filesystem::exists(spath));
    REQUIRE_FALSE(std::filesystem::exists(dir / "two"));
}

TEST_CASE("shell: show enriches in the set, so it is cached", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto twice = run(tb, "show 1\nshow 1\n", {}, 1);
    auto nl = twice.out.find('\n', twice.out.find("Ka2 Qa4#"));
    REQUIRE(nl != std::string::npos);
    std::string first_block = twice.out.substr(0, nl + 1);
    REQUIRE(twice.out == first_block + first_block);  // identical, second time from the cache

    // `show` filled the only hit's themes, so the set now has themes for
    // every hit and `save` says so without a bulk pass of its own.
    auto dir = std::filesystem::temp_directory_path() / "hm_mine_shell_save";
    std::filesystem::create_directories(dir);
    auto jpath = (dir / "after_show.json").string();
    auto r = run(tb, "show 1\nsave " + jpath + "\n", {}, 1);
    REQUIRE(has(r.out, "to " + jpath + " (json, themes)"));
}

TEST_CASE("shell: a narrowing that cannot annotate says so once, with the gen hint", "[mine_shell]") {
    // A Tablebase over an EMPTY directory: every enrichment throws
    // MissingTableError, so both hits end up marked unavailable.
    auto empty = (std::filesystem::temp_directory_path() / "hm_mine_shell_empty").string();
    std::filesystem::create_directories(empty);
    Tablebase tb(empty);
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 10);
    for (const char* fen : {kFirst, "8/8/8/8/8/2Q5/8/k1K5 b - - 0 1"}) {
        Hit h;
        h.fen = fen;
        h.dtm = 2;
        h.count = 1;
        s.add(h);
    }
    std::istringstream in("theme mirror\n");
    std::ostringstream out, err;
    REQUIRE(run_mine_shell(std::move(s), in, out, err, {}, "tt") == 0);
    REQUIRE(out.str() == "0 positions\n");  // marked hits never match
    REQUIRE(has(err.str(), "note: 2 position(s) could not be annotated"));
    REQUIRE(has(err.str(), "helpmate gen KQvk --tables tt"));
}

TEST_CASE("shell: help lists every command", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "help\n", {}, 1);
    for (const char* c : {"theme", "not theme", "count", "starts", "ends", "back", "reset", "list", "show",
                          "themes", "save", "help", "quit"})
        REQUIRE(has(r.out, c));
}
