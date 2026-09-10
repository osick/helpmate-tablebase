# `mine` JSON / solutions / infinity / interactive shell — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `helpmate mine` gains `--max infinity`, `--json`, `--themes`, `--solutions` and an `--interactive` shell that narrows, inspects, tallies and saves a held result set without rescanning.

**Architecture:** A new core unit `MineSet` (hits + lazy enrichment + narrowing + JSON/text output) sits beside `Tablebase`; a second core unit `mine_shell` is a pure stream-driven REPL over a `MineSet`; `cmd_mine` in the CLI parses the flags, runs the scan into a `MineSet` and either prints it or hands it to the shell. `Tablebase` gets one small addition, `shows_theme`, so a parametric theme (`promotions:qrr`) can be evaluated on a single FEN without duplicating multiset logic.

**Tech Stack:** C++20, CMake, Catch2 (core unit tests), ctest + cmake `-P` scripts (CLI end-to-end), nlohmann_json (already linked into `helpmate_core`), clang-format via `make format`.

**Spec:** `docs/superpowers/specs/2026-09-10-mine-interactive-design.md`

## Global Constraints

- Target version `0.18.0`; `VERSION` file is the single source of truth (CMake reads it).
- No new build dependencies. No readline. The shell is `std::getline` on a `std::istream`.
- Default `mine` text output (no facet flag) must stay byte-identical: one canonical FEN per line.
- Prompt and progress go to **stderr**; command results and mined output go to **stdout**.
- Flag values are case-sensitive: only `infinity` and `inf` mean "no cap".
- "All themes" = every registry entry whose `param` is null (29 of 30 today). Never filter by "contains a colon".
- Errors inside the shell never exit the shell. Exit code of the shell is 0 on `quit`/`exit`/EOF.
- Coverage of the two new units ≥ 80 % lines (`make coverage`).
- Every commit ends with the attribution trailer from the session (`Co-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>` and the `Claude-Session:` line).
- Run `make format` (clang-format on touched lines, `BASE=main`) before each commit that touches C++.
- Build with `make build`; core tests: `./build/helpmate_tests "<tag or name>"`; CLI tests: `make test-cli`.

**Pinned numbers** (measured 2026-09-10 on the repo's generated KQvk table; if one differs, re-measure with the CLI before touching a test):

| Query on KQvk, dtm 2 | hits |
|---|---|
| unfiltered | 580 |
| `mirror` | 477 |
| not `mirror` | 103 |
| `count 1` | 356 |
| `mirror` and `count 1` | 257 |
| first FEN of the unfiltered scan | `8/8/8/8/8/8/8/k1KQ4 b - - 0 1` (dtm 2, count 1, shows `mirror`, single solution `Ka2 Qa4#`) |
| second FEN | `8/8/8/8/8/2Q5/8/k1K5 b - - 0 1` (dtm 2, count 1, no `mirror`, solution `Ka2 Qb2#`) |
| golden `8/7k/5K2/8/8/8/8/6Q1 b - - 0 1` | dtm 2, count 4, starts 2, ends 4, lines `Kh6 Qh2#`, `Kh6 Qh1#`, `Kh6 Qg6#`, `Kh8 Qg7#` |

---

## File structure

| File | Status | Responsibility |
|---|---|---|
| `src/core/probe/mine_set.h` / `.cpp` | create | `Hit`, `non_parametric()`, `MineSet`: hold, enrich, narrow, tally, serialise |
| `src/core/probe/mine_shell.h` / `.cpp` | create | `run_mine_shell()`: parse commands from an istream, drive a `MineSet`, print |
| `src/core/probe/tablebase.h` / `.cpp` | modify | add `shows_theme(fen, ResolvedTheme, max)`; factor the `ThemeInput` build out of `themes_of` |
| `src/core/CMakeLists.txt` | modify | append the two sources and two test files |
| `src/core/tests/test_mine_set.cpp` | create | Catch2 tests for `MineSet` |
| `src/core/tests/test_mine_shell.cpp` | create | Catch2 tests for the shell via string streams |
| `src/packages/cli/main.cpp` | modify | `--max infinity`, `--json`, `--themes`, `--solutions`, `--interactive`/`--tui`; `cmd_mine` glue; usage text |
| `src/packages/cli/CMakeLists.txt` | modify | new ctests; drop `cli_mine_themes_rejected` |
| `src/packages/cli/tests/verify_mine_outputs.cmake` | create | pins `--max infinity` count, `--json` shape, `--solutions` text |
| `src/packages/cli/tests/verify_mine_shell.cmake` + `mine_shell_session.txt` | create | end-to-end stdin-driven shell session |
| `docs/USAGE.md`, `CHANGELOG.md`, `VERSION`, `docs/ROADMAP.md` | modify | docs and release |
| `docs/superpowers/specs/2026-09-10-mine-interactive-design.md` | modify | three amendments (Task 1) |

---

### Task 1: Spec amendments and `Tablebase::shows_theme`

**Files:**
- Modify: `docs/superpowers/specs/2026-09-10-mine-interactive-design.md`
- Modify: `src/core/probe/tablebase.h` (class `Tablebase`, public section after `themes_of`; private section)
- Modify: `src/core/probe/tablebase.cpp` (`Tablebase::themes_of`, around line 368)
- Test: `src/core/tests/test_solutions.cpp` (append one case; it already has `gen_kqvk()`)

**Interfaces:**
- Produces: `bool Tablebase::shows_theme(const std::string& fen, const themes::ResolvedTheme& t, int max) const` — true when the position shows the resolved (possibly parametric) theme; `max` caps solution enumeration exactly like `themes_of`.

- [ ] **Step 1: Amend the spec** (three edits, plain text):

  1. In the Architecture table, change the `mine_shell` row's "Lives in" to `src/core/probe/mine_shell.{h,cpp}` and add a sentence below the table: "The shell lives in the core library, not the CLI package, so Catch2 can drive it through string streams; the CLI only wires `std::cin`/`std::cout`/`std::cerr` to it."
  2. Replace the sentence "`Tablebase` is not changed." with: "`Tablebase` gains one method, `shows_theme(fen, ResolvedTheme, max)`, so the shell can evaluate a parametric theme such as `promotions:qrr` on one hit; it shares the `ThemeInput` construction with `themes_of`. Nothing else in `Tablebase` changes."
  3. In "JSON shape", replace "no external library (the repo writes its stats JSON by hand already; a small escaper in `mine_set.cpp` does the same)" with "built with `nlohmann::ordered_json`, which `helpmate_core` already links, so key order is stable and escaping is the library's".

- [ ] **Step 2: Write the failing test** — append to `src/core/tests/test_solutions.cpp`:

```cpp
TEST_CASE("shows_theme evaluates one resolved theme on a FEN", "[themes][solutions]") {
    Tablebase tb(gen_kqvk());
    std::string err;
    auto mirror = themes::resolve_theme("mirror", &err);
    REQUIRE(mirror);
    auto promo = themes::resolve_theme("promotions:q", &err);
    REQUIRE(promo);
    // golden: dtm 2 count 4; every mate is a mirror mate, and KQvk has no pawn.
    REQUIRE(tb.shows_theme(kGolden, *mirror, 4));
    REQUIRE_FALSE(tb.shows_theme(kGolden, *promo, 4));
    // Same answer as themes_of, which is the reference implementation.
    auto names = tb.themes_of(kGolden, 4);
    REQUIRE(std::find(names.begin(), names.end(), "mirror") != names.end());
}
```

Add `#include <algorithm>` at the top of the file if absent.

- [ ] **Step 3: Run it to verify it fails**

Run: `make build 2>&1 | tail -5`
Expected: compile error, `shows_theme` is not a member of `Tablebase`.

- [ ] **Step 4: Implement** — in `tablebase.h`, add before `namespace hm {`:

```cpp
namespace hm::themes { struct ResolvedTheme; struct ThemeInput; }
```

In the public section, after `themes_of`:

```cpp
    // Does `fen` show the (possibly parametric) theme `t`? Same ThemeInput
    // as themes_of, so a parametric value such as promotions:qrr is judged by
    // the registry's own eval, never by string-matching themes_of's output.
    bool shows_theme(const std::string& fen, const themes::ResolvedTheme& t, int max) const;
```

In the private section:

```cpp
    // THE one place a ThemeInput is built (themes_of and shows_theme both
    // route here). `use` runs while the input's referents are alive.
    void with_theme_input(const std::string& fen, int max,
                          const std::function<void(const themes::ThemeInput&)>& use) const;
```

In `tablebase.cpp`, replace the body of `themes_of` and add the two functions:

```cpp
void Tablebase::with_theme_input(const std::string& fen, int max,
                                 const std::function<void(const themes::ThemeInput&)>& use) const {
    auto b = Board::from_fen(fen);
    if (!b) throw std::invalid_argument("bad FEN (or castling rights): " + fen);
    std::vector<Solution> sols = solutions(fen, max);
    ValuePair value{DTM_UNSOLVABLE, 0};
    try {
        value = value_of(*b);
    } catch (const MissingTableError&) {
        // no table for this position's own plane: leave the DTM_UNSOLVABLE
        // sentinel rather than inventing a value -- has_set_play answers "no".
    }
    std::optional<ValuePair> other;
    Board flipped = *b;
    flipped.reset(b->pieces(), b->stm() == Color::White ? Color::Black : Color::White);
    try {
        other = value_of(flipped);
    } catch (const MissingTableError&) {
        other = std::nullopt;  // no table for the sibling plane: answer "no"
    }
    themes::ThemeInput in{*b, value, other, sols};
    use(in);
}

std::vector<std::string> Tablebase::themes_of(const std::string& fen, int max) const {
    std::vector<std::string> out;
    with_theme_input(fen, max, [&](const themes::ThemeInput& in) { out = themes::detect(in); });
    return out;
}

bool Tablebase::shows_theme(const std::string& fen, const themes::ResolvedTheme& t, int max) const {
    bool r = false;
    with_theme_input(fen, max, [&](const themes::ThemeInput& in) { r = t.eval(in); });
    return r;
}
```

- [ ] **Step 5: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[solutions]"`
Expected: all pass, including the new case and the existing `mine filters by theme`.

- [ ] **Step 6: Format and commit**

```bash
make format BASE=main
git add docs/superpowers/specs/2026-09-10-mine-interactive-design.md src/core/probe/tablebase.h src/core/probe/tablebase.cpp src/core/tests/test_solutions.cpp
git commit -m "probe: Tablebase::shows_theme; spec amendments for the mine-interactive plan"
```

---

### Task 2: `MineSet` skeleton — hits, `add`, `non_parametric`

**Files:**
- Create: `src/core/probe/mine_set.h`, `src/core/probe/mine_set.cpp`
- Modify: `src/core/CMakeLists.txt` (append `probe/mine_set.cpp` to `HELPMATE_SOURCES`; append `tests/test_mine_set.cpp` to `helpmate_tests`)
- Test: `src/core/tests/test_mine_set.cpp`

**Interfaces:**
- Produces:
  - `struct Hit { std::string fen; int dtm, count; std::optional<SolutionShape> shape; std::optional<std::vector<std::string>> themes; std::optional<std::vector<std::vector<std::string>>> solutions; std::string unavailable; }`
  - `std::vector<std::string> non_parametric(const std::vector<std::string>& names)`
  - `class MineSet` with `MineSet(const Tablebase&, Material, MineFilter, int max)`, `void add(const std::string& fen)`, `void add(Hit)`, `hits()`, `size()`, `material()`, `filter()`, `max()`, `skipped_saturated()`, `set_skipped_saturated(uint64_t)`. `max == INT_MAX` means infinity.

- [ ] **Step 1: Write the failing tests** — `src/core/tests/test_mine_set.cpp`:

```cpp
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
```

- [ ] **Step 2: Register the files and run to verify failure**

In `src/core/CMakeLists.txt`: add `probe/mine_set.cpp` at the end of the `set(HELPMATE_SOURCES ...)` list (before the closing paren) and `tests/test_mine_set.cpp` as the last entry of `add_executable(helpmate_tests ...)`.

Run: `make build 2>&1 | tail -3`
Expected: error, `probe/mine_set.h` not found.

- [ ] **Step 3: Implement** — `src/core/probe/mine_set.h`:

```cpp
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
    std::optional<std::vector<std::string>> themes;               // non-parametric names only
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
    struct Facets { bool themes = false; bool solutions = false; };
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

private:
    const Tablebase* tb_;
    Material m_;
    MineFilter f_;
    int max_;
    uint64_t skipped_ = 0;
    std::vector<Hit> hits_;
};

}  // namespace hm
```

`src/core/probe/mine_set.cpp`:

```cpp
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
```

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[mine_set]"`
Expected: 3 test cases pass.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/core/probe/mine_set.h src/core/probe/mine_set.cpp src/core/CMakeLists.txt src/core/tests/test_mine_set.cpp
git commit -m "probe: MineSet skeleton -- held hits with probed dtm/count, non_parametric()"
```

---

### Task 3: Enrichment — shape, themes, solutions, unavailable marking

**Files:**
- Modify: `src/core/probe/mine_set.h`, `src/core/probe/mine_set.cpp`
- Test: `src/core/tests/test_mine_set.cpp`

**Interfaces:**
- Produces on `MineSet`: `void ensure_shape(Hit&) const`, `void ensure_themes(Hit&) const`, `void ensure_solutions(Hit&) const`, `void ensure_themes_all(const Progress& = nullptr)`, `void ensure_solutions_all(const Progress& = nullptr)`, `bool all_have_themes() const`, `size_t unavailable_count() const`.
- Rule: each `ensure_*` is idempotent; on `MissingTableError` it sets `hit.unavailable = e.what()` and leaves the optional empty; a hit with `unavailable` set is skipped by every later `ensure_*`.
- Enumeration cap: `hit.count >= (int)COUNT_SAT ? 100 : hit.count` (same rule as `probe --themes`).

- [ ] **Step 1: Write the failing tests** — append to `test_mine_set.cpp`:

```cpp
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
```

Add `#include <algorithm>` to the test's includes.

- [ ] **Step 2: Run to verify failure**

Run: `make build 2>&1 | tail -3`
Expected: compile error, `ensure_shape` not a member.

- [ ] **Step 3: Implement** — add to the public section of `MineSet` in `mine_set.h`:

```cpp
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
```

and a private helper:

```cpp
    int enum_cap(const Hit& h) const;  // COUNT_SAT -> 100, else the hit's own count
    template <class F> void guarded(Hit& h, F&& f) const;  // runs f, marks unavailable on MissingTableError
```

In `mine_set.cpp` (add `#include "chess/types.h"` for `COUNT_SAT`):

```cpp
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
```

Note the progress contract: the last call carries `done == total` only if the last hit needed work. The test's set is freshly loaded, so it does. Keep that contract; the shell prints the final tally itself (Task 6).

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[mine_set]"`
Expected: 6 cases pass.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/core/probe/mine_set.h src/core/probe/mine_set.cpp src/core/tests/test_mine_set.cpp
git commit -m "probe: MineSet lazy enrichment -- shape, themes, solutions, unavailable marking"
```

---

### Task 4: Narrowing and the theme histogram

**Files:**
- Modify: `src/core/probe/mine_set.h`, `src/core/probe/mine_set.cpp`
- Test: `src/core/tests/test_mine_set.cpp`

**Interfaces:**
- Produces on `MineSet`:
  - `MineSet with_theme(const std::string& name, bool negate, const Progress& = nullptr)` — throws `std::invalid_argument` with the `resolve_theme` error text on an unknown name. Non-parametric name: uses cached `themes` (forcing `ensure_themes_all`). Parametric name: `Tablebase::shows_theme` per hit. A hit with `unavailable` set never matches (dropped when `negate` is false, kept when `negate` is true? No: **dropped in both cases**, spec: "never matches a theme or shape narrowing").
  - `MineSet with_count(int)`, `MineSet with_starts(int)`, `MineSet with_ends(int)` — starts/ends force `ensure_shape`; unavailable hits are dropped.
  - `std::vector<std::pair<std::string, size_t>> theme_histogram(const Progress& = nullptr)` — every non-parametric registry name in registry order, zeros included.
- The returned set shares `tb`, material, filter, max and `skipped_saturated`; the source set keeps its (now enriched) hits.

- [ ] **Step 1: Write the failing tests** — append:

```cpp
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
```

- [ ] **Step 2: Run to verify failure**

Run: `make build 2>&1 | tail -3`
Expected: compile error, `with_theme` not a member.

- [ ] **Step 3: Implement** — public section additions in `mine_set.h`:

```cpp
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
```

private:

```cpp
    MineSet empty_like() const;  // same tb/material/filter/max/skipped, no hits
    template <class Pred> MineSet filtered(Pred&& keep) const;
```

`mine_set.cpp`:

```cpp
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
```

Add `#include <algorithm>` and `#include <stdexcept>` to `mine_set.cpp`.

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[mine_set]"`
Expected: 10 cases pass. If 477/103/356/257 differ, re-measure with `./build/helpmate mine KQvk --dtm 2 --max 100000 [--theme mirror] [--count 1] --tables build/cli_tables | wc -l` and report the discrepancy rather than editing the numbers blindly.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/core/probe/mine_set.h src/core/probe/mine_set.cpp src/core/tests/test_mine_set.cpp
git commit -m "probe: MineSet narrowing (theme/not theme/count/starts/ends) and theme histogram"
```

---

### Task 5: JSON and text output

**Files:**
- Modify: `src/core/probe/mine_set.h`, `src/core/probe/mine_set.cpp`
- Test: `src/core/tests/test_mine_set.cpp`

**Interfaces:**
- Produces on `MineSet`: `std::string to_json(Facets, const Progress& = nullptr)` and `void to_text(std::ostream&, Facets, const Progress& = nullptr)`. Both force the enrichment the facets need (`ensure_themes_all` for `themes`, `ensure_solutions_all` for `solutions`), so they are non-const.
- JSON keys exactly as the spec: top level `material`, `filter{dtm,count,starts,ends,themes}`, `max` (int or `"infinity"`), `skipped_saturated`, `positions[]`; per position `fen`, `dtm`, `count`, optional `unavailable`, with facets `themes` and `starts`/`ends`/`solutions`. Pretty-printed with indent 2, trailing newline.

- [ ] **Step 1: Write the failing tests** — append (add `#include <nlohmann/json.hpp>` and `#include <sstream>`):

```cpp
TEST_CASE("to_json has the documented shape", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2, .themes = {"mirror"}}, INT_MAX);
    s.add(kGolden);
    s.add(kFirst);
    auto j = nlohmann::json::parse(s.to_json({.themes = true, .solutions = true}));
    REQUIRE(j["material"] == "KQvk");
    REQUIRE(j["filter"]["dtm"] == 2);
    REQUIRE(j["filter"]["count"] == -1);
    REQUIRE(j["filter"]["themes"] == nlohmann::json::array({"mirror"}));
    REQUIRE(j["max"] == "infinity");
    REQUIRE(j["skipped_saturated"] == 0);
    REQUIRE(j["positions"].size() == 2);
    auto& p = j["positions"][0];
    REQUIRE(p["fen"] == kGolden);
    REQUIRE(p["dtm"] == 2);
    REQUIRE(p["count"] == 4);
    REQUIRE(p["starts"] == 2);
    REQUIRE(p["ends"] == 4);
    REQUIRE(p["solutions"].size() == 4);
    REQUIRE(p["solutions"][3] == nlohmann::json::array({"Kh8", "Qg7#"}));
    REQUIRE(p["themes"].is_array());
    REQUIRE_FALSE(p.contains("unavailable"));
    // Key order is stable: material first, positions last.
    auto text = s.to_json({});
    REQUIRE(text.find("\"material\"") < text.find("\"positions\""));
    REQUIRE(text.back() == '\n');
}

TEST_CASE("to_json without facets is minimal; max as integer", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 7);
    s.add(kFirst);
    auto j = nlohmann::json::parse(s.to_json({}));
    REQUIRE(j["max"] == 7);
    auto& p = j["positions"][0];
    REQUIRE(p.size() == 3);  // fen, dtm, count
    REQUIRE_FALSE(p.contains("themes"));
    REQUIRE_FALSE(p.contains("solutions"));
}

TEST_CASE("unavailable hits serialise with the message and nothing else", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 7);
    Hit h;
    h.fen = kFirst;
    h.dtm = 2;
    h.count = 1;
    h.unavailable = "no table for \"Kvk\"";  // a quote, to prove escaping
    s.add(h);
    auto j = nlohmann::json::parse(s.to_json({.themes = true, .solutions = true}));
    auto& p = j["positions"][0];
    REQUIRE(p["unavailable"] == "no table for \"Kvk\"");
    REQUIRE_FALSE(p.contains("themes"));
    REQUIRE_FALSE(p.contains("solutions"));
    std::ostringstream out;
    s.to_text(out, {.themes = true, .solutions = true});
    REQUIRE(out.str() == std::string(kFirst) + "\n  unavailable: no table for \"Kvk\"\n\n");
}

TEST_CASE("to_text: bare FENs by default, indented facets otherwise", "[mine_set]") {
    Tablebase tb(gen_kqvk());
    MineSet s(tb, *Material::parse("KQvk"), MineFilter{.dtm = 2}, 7);
    s.add(kFirst);
    s.add(kSecond);
    std::ostringstream bare;
    s.to_text(bare, {});
    REQUIRE(bare.str() == std::string(kFirst) + "\n" + kSecond + "\n");
    std::ostringstream sol;
    s.to_text(sol, {.solutions = true});
    REQUIRE(sol.str() == std::string(kFirst) + "\n  Ka2 Qa4#\n\n" + kSecond + "\n  Ka2 Qb2#\n\n");
    std::ostringstream both;
    s.to_text(both, {.themes = true, .solutions = true});
    std::string text = both.str();
    REQUIRE(text.rfind(std::string(kFirst) + "\n  themes:", 0) == 0);
    REQUIRE(text.find(" mirror") != std::string::npos);
    REQUIRE(text.find("\n  Ka2 Qa4#\n\n") != std::string::npos);
}
```

- [ ] **Step 2: Run to verify failure**

Run: `make build 2>&1 | tail -3`
Expected: compile error, `to_json` not a member.

- [ ] **Step 3: Implement** — public additions in `mine_set.h`:

```cpp
    // Output. Both force whatever enrichment the facets need, hence non-const.
    std::string to_json(Facets f, const Progress& progress = nullptr);
    void to_text(std::ostream& os, Facets f, const Progress& progress = nullptr);
```

private:

```cpp
    void enrich_for(Facets f, const Progress& progress);
```

`mine_set.cpp` (add `#include <climits>` and `#include <nlohmann/json.hpp>`):

```cpp
void MineSet::enrich_for(Facets f, const Progress& progress) {
    if (f.themes) ensure_themes_all(progress);
    if (f.solutions) ensure_solutions_all(progress);
}

std::string MineSet::to_json(Facets f, const Progress& progress) {
    enrich_for(f, progress);
    nlohmann::ordered_json j;
    j["material"] = m_.name();
    j["filter"] = {{"dtm", f_.dtm}, {"count", f_.count}, {"starts", f_.starts},
                   {"ends", f_.ends}, {"themes", f_.themes}};
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
                p["starts"] = h.shape->starts;
                p["ends"] = h.shape->ends;
                p["solutions"] = *h.solutions;
            }
        }
        positions.push_back(std::move(p));
    }
    j["positions"] = std::move(positions);
    return j.dump(2) + "\n";
}

void MineSet::to_text(std::ostream& os, Facets f, const Progress& progress) {
    enrich_for(f, progress);
    const bool facets = f.themes || f.solutions;
    for (const auto& h : hits_) {
        os << h.fen << "\n";
        if (!facets) continue;
        if (!h.unavailable.empty()) {
            os << "  unavailable: " << h.unavailable << "\n\n";
            continue;
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
        }
        os << "\n";
    }
}
```

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[mine_set]"`
Expected: 14 cases pass.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/core/probe/mine_set.h src/core/probe/mine_set.cpp src/core/tests/test_mine_set.cpp
git commit -m "probe: MineSet JSON (ordered_json) and indented text output with facets"
```

---

### Task 6: The shell — `run_mine_shell`

**Files:**
- Create: `src/core/probe/mine_shell.h`, `src/core/probe/mine_shell.cpp`
- Modify: `src/core/CMakeLists.txt` (append `probe/mine_shell.cpp` and `tests/test_mine_shell.cpp`)
- Test: `src/core/tests/test_mine_shell.cpp`

**Interfaces:**
- Produces: `int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err, MineSet::Facets cli_facets)`. Returns 0. `cli_facets` records which of `--themes`/`--solutions` were on the command line (they decide what `save x.json` includes).
- Prompt `[N] mine> ` on `err` before each read. Commands and replies exactly as below; every reply line goes to `out` except the prompt, progress and error lines, which go to `err`.

Reply formats (pin these in tests):

| Input | stdout | stderr |
|---|---|---|
| `theme NAME` / `not theme NAME` | `N positions` | progress lines `evaluating themes: D/T` every 100 done (and never for D==T unless D%100==0; the tally line on stdout is enough) |
| `count N` / `starts N` / `ends N` | `N positions` | — |
| `back` | `N positions` | at root: `already at the root set` |
| `reset` | `N positions` | — |
| `list [FROM [N]]` | one line per hit: `<index>  <fen>` (index 1-based, right-aligned width 6) | FROM out of range: `no hit FROM (set has N)` |
| `show I` | `<fen>` / `  themes: ...` / one `  <san...>` per solution (same layout as `to_text` with both facets, no trailing blank line) | bad index: `no hit I (set has N)` |
| `themes` | one line per non-parametric theme: name padded to the longest name + 2 spaces, then count | progress as above |
| `save FILE` | `saved N positions to FILE (json[, themes][, solutions])` or `saved N positions to FILE (fens)` | cannot open: `cannot write FILE: <strerror>` |
| `help` | the command table as plain lines (see implementation) | — |
| `quit` / `exit` / EOF | — | — ; returns 0 |
| empty line | nothing | — |
| anything else | — | `unknown command "X"; type help` |
| bad/missing number | — | `<cmd> needs a positive integer` |
| unknown theme | — | `error: <resolve_theme message>` then `valid themes: ...` (registry display names, space-separated) |

`save FILE.json` facets: `themes` = `cli_facets.themes || current.all_have_themes()`; `solutions` = `cli_facets.solutions`. Otherwise (any other name) bare FENs, one per line.

- [ ] **Step 1: Write the failing tests** — `src/core/tests/test_mine_shell.cpp`:

```cpp
#include <catch2/catch_test_macros.hpp>
#include <climits>
#include <filesystem>
#include <fstream>
#include <nlohmann/json.hpp>
#include <sstream>

#include "generator/generator.h"
#include "probe/mine_set.h"
#include "probe/mine_shell.h"

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
    tb.mine(m, MineFilter{.dtm = 2}, [&](const std::string& f) { s.add(f); return (int)s.size() < cap; });
    return s;
}

struct Run { int rc; std::string out, err; };
Run run(const Tablebase& tb, const std::string& script, MineSet::Facets cli = {}, int cap = INT_MAX) {
    std::istringstream in(script);
    std::ostringstream out, err;
    int rc = run_mine_shell(root(tb, cap), in, out, err, cli);
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
    REQUIRE(r.out == "477 positions\n257 positions\n477 positions\n103 positions\n580 positions\n580 positions\n");
    REQUIRE(has(r.err, "[477] mine> "));
    REQUIRE(has(r.err, "[257] mine> "));
    REQUIRE(has(r.err, "already at the root set"));
    REQUIRE(has(r.err, "evaluating themes: 100/580"));
}

TEST_CASE("shell: list and show", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "list 1 2\nshow 1\nshow 0\nlist 999\n", {}, 5);
    std::string expect_list = "     1  8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n     2  8/8/8/8/8/2Q5/8/k1K5 b - - 0 1\n";
    REQUIRE(r.out.rfind(expect_list, 0) == 0);
    REQUIRE(has(r.out, std::string(kFirst) + "\n  themes:"));
    REQUIRE(has(r.out, " mirror"));
    REQUIRE(has(r.out, "\n  Ka2 Qa4#\n"));
    REQUIRE(has(r.err, "no hit 0 (set has 5)"));
    REQUIRE(has(r.err, "no hit 999 (set has 5)"));
}

TEST_CASE("shell: themes histogram", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "themes\n", {}, 50);
    REQUIRE(has(r.out, "mirror"));
    // every non-parametric registry name appears, and 'promotions' (parametric) does not as a bare line
    REQUIRE_FALSE(has(r.out, "\npromotions  "));
    REQUIRE(has(r.out, "pure"));
    std::istringstream lines(r.out);
    std::string l;
    int n = 0;
    while (std::getline(lines, l)) ++n;
    REQUIRE(n == 29);
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
}

TEST_CASE("shell: help lists every command", "[mine_shell]") {
    Tablebase tb(gen_kqvk());
    auto r = run(tb, "help\n", {}, 1);
    for (const char* c : {"theme", "not theme", "count", "starts", "ends", "back", "reset", "list", "show",
                          "themes", "save", "help", "quit"})
        REQUIRE(has(r.out, c));
}
```

- [ ] **Step 2: Register and run to verify failure**

Append `probe/mine_shell.cpp` to `HELPMATE_SOURCES` and `tests/test_mine_shell.cpp` to `helpmate_tests` in `src/core/CMakeLists.txt`.

Run: `make build 2>&1 | tail -3`
Expected: error, `probe/mine_shell.h` not found.

- [ ] **Step 3: Implement** — `src/core/probe/mine_shell.h`:

```cpp
#pragma once
#include <istream>
#include <ostream>

#include "probe/mine_set.h"

namespace hm {

// The `mine --interactive` loop: reads one command per line from `in`,
// narrows/inspects/saves `root` and its descendants, replies on `out`. The
// prompt, progress and every error go to `err`, so stdout stays a clean
// record of results. Returns 0 on quit/exit/EOF. Never throws for user
// input; a MissingTableError from enrichment is absorbed by MineSet.
// `cli_facets`: which of --themes/--solutions were given on the command
// line; they decide what `save FILE.json` includes.
int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                   MineSet::Facets cli_facets);

}  // namespace hm
```

`src/core/probe/mine_shell.cpp`:

```cpp
#include "probe/mine_shell.h"

#include <cerrno>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <sstream>
#include <stdexcept>
#include <vector>

#include "themes/registry.h"

namespace hm {
namespace {

std::vector<std::string> split(const std::string& line) {
    std::istringstream ss(line);
    std::vector<std::string> w;
    for (std::string t; ss >> t;) w.push_back(t);
    return w;
}

bool positive_int(const std::string& s, int& out) {
    if (s.empty()) return false;
    for (char c : s)
        if (c < '0' || c > '9') return false;
    try {
        long v = std::stol(s);
        if (v < 1 || v > INT_MAX) return false;
        out = (int)v;
        return true;
    } catch (const std::exception&) { return false; }
}

void help(std::ostream& out) {
    out << "commands:\n"
           "  theme NAME       keep positions showing NAME (promotions:qrr allowed)\n"
           "  not theme NAME   drop positions showing NAME\n"
           "  count N          keep positions with exactly N optimal solutions\n"
           "  starts N         keep positions with N distinct first moves\n"
           "  ends N           keep positions with N distinct mating moves\n"
           "  back             undo the last narrowing\n"
           "  reset            return to the loaded set\n"
           "  list [FROM [N]]  print FENs FROM..FROM+N-1 (default 1, 20)\n"
           "  show I           print hit I with its themes and every solution\n"
           "  themes           how many positions show each theme\n"
           "  save FILE        write the set: FILE.json as JSON, otherwise bare FENs\n"
           "  help             this list\n"
           "  quit             leave (exit and EOF do too)\n";
}

void print_hit(std::ostream& out, MineSet& set, Hit& h) {
    set.ensure_themes(h);
    set.ensure_solutions(h);
    out << h.fen << "\n";
    if (!h.unavailable.empty()) {
        out << "  unavailable: " << h.unavailable << "\n";
        return;
    }
    out << "  themes:";
    if (h.themes->empty()) out << " (none)";
    for (const auto& n : *h.themes) out << " " << n;
    out << "\n";
    for (const auto& line : *h.solutions) {
        if (line.empty()) continue;
        out << " ";
        for (const auto& mv : line) out << " " << mv;
        out << "\n";
    }
}

}  // namespace

int run_mine_shell(MineSet root, std::istream& in, std::ostream& out, std::ostream& err,
                   MineSet::Facets cli_facets) {
    std::vector<MineSet> stack;  // previous sets, most recent last
    MineSet cur = std::move(root);
    auto progress = [&](size_t done, size_t total) {
        if (done % 100 == 0 && done != total) err << "evaluating themes: " << done << "/" << total << "\n";
    };
    auto narrowed = [&](MineSet next) {
        stack.push_back(std::move(cur));
        cur = std::move(next);
        out << cur.size() << " positions\n";
    };
    auto need_int = [&](const std::vector<std::string>& w, int& n) {
        if (w.size() < 2 || !positive_int(w[1], n)) {
            err << w[0] << " needs a positive integer\n";
            return false;
        }
        return true;
    };

    std::string line;
    while (true) {
        err << "[" << cur.size() << "] mine> ";
        if (!std::getline(in, line)) break;
        auto w = split(line);
        if (w.empty()) continue;
        const std::string& c = w[0];
        if (c == "quit" || c == "exit") break;
        if (c == "help") {
            help(out);
        } else if (c == "theme" || (c == "not" && w.size() >= 2 && w[1] == "theme")) {
            const bool negate = c == "not";
            const size_t at = negate ? 2 : 1;
            if (w.size() <= at) {
                err << "theme needs a NAME\n";
                continue;
            }
            try {
                narrowed(cur.with_theme(w[at], negate, progress));
            } catch (const std::invalid_argument& e) {
                err << "error: " << e.what() << "\nvalid themes:";
                for (const auto& t : themes::theme_registry()) err << " " << themes::display_name(t);
                err << "\n";
            }
        } else if (c == "count" || c == "starts" || c == "ends") {
            int n = 0;
            if (!need_int(w, n)) continue;
            narrowed(c == "count" ? cur.with_count(n) : c == "starts" ? cur.with_starts(n) : cur.with_ends(n));
        } else if (c == "back") {
            if (stack.empty()) {
                err << "already at the root set\n";
            } else {
                cur = std::move(stack.back());
                stack.pop_back();
            }
            out << cur.size() << " positions\n";
        } else if (c == "reset") {
            if (!stack.empty()) {
                cur = std::move(stack.front());
                stack.clear();
            }
            out << cur.size() << " positions\n";
        } else if (c == "list") {
            int from = 1, n = 20;
            if (w.size() >= 2 && !positive_int(w[1], from)) { err << "list needs a positive integer\n"; continue; }
            if (w.size() >= 3 && !positive_int(w[2], n)) { err << "list needs a positive integer\n"; continue; }
            if ((size_t)from > cur.size()) {
                err << "no hit " << from << " (set has " << cur.size() << ")\n";
                continue;
            }
            for (size_t i = (size_t)from - 1; i < cur.size() && i < (size_t)from - 1 + (size_t)n; ++i)
                out << std::setw(6) << (i + 1) << "  " << cur.hits()[i].fen << "\n";
        } else if (c == "show") {
            int i = 0;
            if (w.size() < 2 || !positive_int(w[1], i) || (size_t)i > cur.size()) {
                err << "no hit " << (w.size() >= 2 ? w[1] : "?") << " (set has " << cur.size() << ")\n";
                continue;
            }
            Hit h = cur.hits()[(size_t)i - 1];
            print_hit(out, cur, h);
        } else if (c == "themes") {
            auto hist = cur.theme_histogram(progress);
            size_t width = 0;
            for (const auto& [name, _] : hist) width = std::max(width, name.size());
            for (const auto& [name, n] : hist) out << std::left << std::setw((int)width + 2) << name << n << "\n";
        } else if (c == "save") {
            if (w.size() < 2) {
                err << "save needs a FILE\n";
                continue;
            }
            const std::string& path = w[1];
            const bool json = path.size() >= 5 && path.compare(path.size() - 5, 5, ".json") == 0;
            std::ofstream f(path);
            if (!f) {
                err << "cannot write " << path << ": " << std::strerror(errno) << "\n";
                continue;
            }
            if (json) {
                MineSet::Facets fac{cli_facets.themes || cur.all_have_themes(), cli_facets.solutions};
                f << cur.to_json(fac, progress);
                out << "saved " << cur.size() << " positions to " << path << " (json" << (fac.themes ? ", themes" : "")
                    << (fac.solutions ? ", solutions" : "") << ")\n";
            } else {
                for (const auto& h : cur.hits()) f << h.fen << "\n";
                out << "saved " << cur.size() << " positions to " << path << " (fens)\n";
            }
        } else {
            err << "unknown command \"" << c << "\"; type help\n";
        }
    }
    return 0;
}

}  // namespace hm
```

Add `#include <algorithm>` and `#include <climits>` at the top of `mine_shell.cpp`.

Note on `show`: `print_hit` enriches a **copy** of the hit, so `show` never mutates the set (keeps `all_have_themes()` honest for `save`). Cost: one enumeration per `show`, acceptable.

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && ./build/helpmate_tests "[mine_shell]"`
Expected: 7 cases pass. The `themes` case expects 29 lines: if the registry has changed, replace 29 by `count of non-parametric registry entries` computed in the test the same way Task 4's histogram test does.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/core/probe/mine_shell.h src/core/probe/mine_shell.cpp src/core/CMakeLists.txt src/core/tests/test_mine_shell.cpp
git commit -m "probe: mine shell -- stream-driven REPL over a MineSet (narrow, back, list, show, themes, save)"
```

---

### Task 7: CLI flags — `--max infinity`, `--json`, `--themes`, `--solutions`

**Files:**
- Modify: `src/packages/cli/main.cpp` (usage text lines ~33–34, 92–101, 115–118; `cmd_mine` ~503–575; parser `--max` ~919 and the `--themes` branch ~958–972; dispatch ~1018)
- Modify: `src/packages/cli/CMakeLists.txt` (remove `cli_mine_themes_rejected`; add tests)
- Create: `src/packages/cli/tests/verify_mine_outputs.cmake`

**Interfaces:**
- Consumes: `MineSet`, `MineSet::Facets` (Task 5).
- Produces: `cmd_mine(pos, tables, dtm, count, maxn, starts, ends, starts_given, ends_given, theme_names, MineOutput out)` where `struct MineOutput { bool json = false; bool themes = false; bool solutions = false; bool interactive = false; };` (defined in `main.cpp`'s anonymous namespace). `interactive` is wired in Task 8; this task parses it but treats it as "build a set and print text" until Task 8.

- [ ] **Step 1: Write the failing ctest script** — `src/packages/cli/tests/verify_mine_outputs.cmake`:

```cmake
# Test-support script (not installed): pins the v0.18.0 mine output modes
# against the KQvk table. Required: -DHELPMATE=<binary> -DTABLES=<dir>
foreach(v HELPMATE TABLES)
  if(NOT DEFINED ${v})
    message(FATAL_ERROR "verify_mine_outputs.cmake: -D${v}=... is required")
  endif()
endforeach()

function(run_helpmate outvar rcvar)
  execute_process(COMMAND "${HELPMATE}" ${ARGN} OUTPUT_VARIABLE out ERROR_VARIABLE err RESULT_VARIABLE rc)
  set(${outvar} "${out}" PARENT_SCOPE)
  set(${rcvar} "${rc}" PARENT_SCOPE)
  set(last_err "${err}" PARENT_SCOPE)
endfunction()

# 1. --max infinity and --max inf lift the cap: 580 dtm=2 positions.
foreach(word infinity inf)
  run_helpmate(out rc mine KQvk --dtm 2 --max ${word} --tables "${TABLES}")
  if(NOT rc EQUAL 0)
    message(FATAL_ERROR "--max ${word} failed (${rc}): ${last_err}")
  endif()
  string(REGEX MATCHALL "\n" nl "${out}")
  list(LENGTH nl n)
  if(NOT n EQUAL 580)
    message(FATAL_ERROR "--max ${word}: expected 580 lines, got ${n}")
  endif()
endforeach()

# 2. A bad --max word is rejected, naming the accepted words.
run_helpmate(out rc mine KQvk --dtm 2 --max all --tables "${TABLES}")
if(NOT rc EQUAL 3 OR NOT "${last_err}" MATCHES "infinity")
  message(FATAL_ERROR "--max all: expected exit 3 naming infinity, got ${rc}: ${last_err}")
endif()

# 3. --json with both facets: the documented keys, in order.
run_helpmate(out rc mine KQvk --dtm 2 --max 2 --json --themes --solutions --tables "${TABLES}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "--json failed (${rc}): ${last_err}")
endif()
foreach(key "\"material\": \"KQvk\"" "\"filter\"" "\"max\": 2" "\"skipped_saturated\": 0" "\"positions\""
            "\"fen\": \"8/8/8/8/8/8/8/k1KQ4 b - - 0 1\"" "\"count\": 1" "\"starts\": 1" "\"ends\": 1"
            "\"themes\"" "\"solutions\"" "\"Qa4#\"")
  if(NOT "${out}" MATCHES "${key}")
    message(FATAL_ERROR "--json output lacks ${key}:\n${out}")
  endif()
endforeach()
string(FIND "${out}" "\"material\"" pos_m)
string(FIND "${out}" "\"positions\"" pos_p)
if(NOT pos_m LESS pos_p)
  message(FATAL_ERROR "--json: material must precede positions")
endif()
find_program(PYTHON3 python3)
if(PYTHON3)
  file(WRITE "${TABLES}/mine_out.json" "${out}")
  execute_process(COMMAND "${PYTHON3}" -c "import json,sys; d=json.load(open(sys.argv[1])); assert len(d['positions'])==2; assert d['max']==2" "${TABLES}/mine_out.json" RESULT_VARIABLE prc)
  if(NOT prc EQUAL 0)
    message(FATAL_ERROR "--json output does not parse as JSON")
  endif()
else()
  message(STATUS "python3 not found: JSON parse check skipped")
endif()

# 4. --json alone: minimal record, no facets.
run_helpmate(out rc mine KQvk --dtm 2 --max 1 --json --tables "${TABLES}")
if(NOT rc EQUAL 0 OR "${out}" MATCHES "\"themes\"" OR "${out}" MATCHES "\"solutions\"")
  message(FATAL_ERROR "--json alone must not carry facets:\n${out}")
endif()

# 5. Text --solutions: FEN, indented line, blank line. And --themes is accepted by mine now.
run_helpmate(out rc mine KQvk --dtm 2 --max 2 --solutions --themes --tables "${TABLES}")
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "--solutions --themes failed (${rc}): ${last_err}")
endif()
if(NOT "${out}" MATCHES "^8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n  themes:[^\n]*mirror[^\n]*\n  Ka2 Qa4#\n\n8/8/8/8/8/2Q5/8/k1K5 b - - 0 1\n")
  message(FATAL_ERROR "--solutions --themes text layout is wrong:\n${out}")
endif()

# 6. Default output is unchanged: bare FENs.
run_helpmate(out rc mine KQvk --dtm 2 --max 2 --tables "${TABLES}")
if(NOT "${out}" STREQUAL "8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n8/8/8/8/8/2Q5/8/k1K5 b - - 0 1\n")
  message(FATAL_ERROR "default mine output changed:\n${out}")
endif()

message(STATUS "mine output modes verified (--max infinity/inf, --json, --themes, --solutions)")
```

In `src/packages/cli/CMakeLists.txt`: delete the whole `cli_mine_themes_rejected` block (the comment and `add_test` + `set_tests_properties`), and add after `cli_mine_theme`:

```cmake
# v0.18.0: output modes. One script pins them all against the same table so
# the numbers (580 dtm=2 positions) are shared with verify_mine_theme_filters.
add_test(NAME cli_mine_outputs COMMAND ${CMAKE_COMMAND}
         -DHELPMATE=$<TARGET_FILE:helpmate>
         -DTABLES=${CLI_TT}
         -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_mine_outputs.cmake)
set_tests_properties(cli_mine_outputs PROPERTIES DEPENDS cli_gen)
```

- [ ] **Step 2: Run to verify failure**

Run: `make build 2>&1 | tail -3 && ctest --test-dir build --output-on-failure -R cli_mine_outputs`
Expected: FAIL at check 1 (`--max infinity` currently prints "expects an integer").

- [ ] **Step 3: Implement in `main.cpp`**

Includes: add `#include "probe/mine_set.h"` and `#include "probe/mine_shell.h"`.

Usage text: replace the two `mine` lines in "Usage:" with

```
                 "  helpmate mine <MATERIAL> --dtm D [--count C] [--starts N] [--ends N]\n"
                 "                           [--theme NAME]... [--themes] [--solutions] [--json]\n"
                 "                           [--interactive] [--max N|infinity] [--tables DIR]\n"
```

Replace the `mine` command description with:

```
                 "  mine   Print positions in MATERIAL matching --dtm exactly (and, if given,\n"
                 "         --count/--starts/--ends/--theme), up to --max, one FEN per line.\n"
                 "         --themes adds every theme each position shows, --solutions every\n"
                 "         optimal solution, --json emits one JSON document instead of text,\n"
                 "         --interactive opens a shell over the result (see docs/USAGE.md).\n"
```

In "Options:", change `--max` to

```
                 "  --max N        cap on lines/FENs printed (default: 10); \"infinity\" or\n"
                 "                 \"inf\" for no cap\n"
```

and change the `--themes` line to

```
                 "  --themes       probe: also print the themes the position's solutions show\n"
                 "                 mine: annotate every hit with all (non-parametric) themes\n"
                 "  --solutions    mine: print every optimal solution of each hit (SAN)\n"
                 "  --json         mine: one JSON document (material, filter, positions[])\n"
                 "  --interactive  mine: after the scan, a shell to narrow/inspect/save the\n"
                 "                 result without rescanning (--tui is an alias)\n"
```

Examples: add

```
                 "  helpmate mine KQvk --dtm 2 --max infinity --json --themes --tables tt\n"
                 "  helpmate mine KQvk --dtm 4 --max 5000 --interactive --tables tt\n"
```

Define, in the anonymous namespace before `cmd_mine`:

```cpp
struct MineOutput {
    bool json = false, themes = false, solutions = false, interactive = false;
    bool wants_set() const { return json || themes || solutions || interactive; }
};
```

Change `cmd_mine`'s signature to append `const MineOutput& out` and replace everything from `Tablebase tb(tables);` to the end of the function with:

```cpp
    Tablebase tb(tables);
    MineFilter filter{.dtm = dtm, .count = count, .starts = starts, .ends = ends, .themes = theme_names};
    uint64_t skipped = 0;
    if (!out.wants_set()) {
        // Streaming path, byte-identical to every release before 0.18.0.
        int printed = 0;
        tb.mine(
            *m, filter,
            [&](const std::string& fen) {
                if (printed >= maxn) return false;  // handles --max 0
                std::cout << fen << "\n";
                ++printed;
                return printed < maxn;
            },
            &skipped);
        if (skipped) note_skipped(skipped);
        return 0;
    }
    MineSet set(tb, *m, filter, maxn);
    if (maxn > 0)
        tb.mine(
            *m, filter,
            [&](const std::string& fen) {
                set.add(fen);
                return (int)set.size() < maxn;
            },
            &skipped);
    set.set_skipped_saturated(skipped);
    if (skipped) note_skipped(skipped);
    MineSet::Facets facets{out.themes, out.solutions};
    auto progress = [](size_t done, size_t total) {
        if (done % 100 == 0 && done != total) std::cerr << "evaluating: " << done << "/" << total << "\n";
    };
    if (out.interactive) {
        std::cerr << "loaded " << set.size() << " positions (" << m->name() << " dtm=" << dtm << ")\n";
        return run_mine_shell(std::move(set), std::cin, std::cout, std::cerr, facets);
    }
    if (out.json) std::cout << set.to_json(facets, progress);
    else set.to_text(std::cout, facets, progress);
    if (set.unavailable_count())
        std::cerr << "note: " << set.unavailable_count()
                  << " position(s) could not be annotated: a table their solutions reach is missing from "
                  << tables << " (each says which); run: helpmate gen " << pos[0] << " --tables " << tables << "\n";
    return 0;
```

Add above `cmd_mine`:

```cpp
void note_skipped(uint64_t skipped) {
    std::cerr << "note: skipped " << skipped
              << " position(s) whose solution count is saturated (255+): their"
                 " solutions cannot be enumerated exhaustively\n";
}
```

Parser: declare `MineOutput mine_out;` next to `show_themes`. Replace the `--max` branch with:

```cpp
        else if (a == "--max") {
            const std::string& v = args[++i];
            if (v == "infinity" || v == "inf") maxn = INT_MAX;
            else if (!parse_int(v, maxn)) {
                std::cerr << "error: --max expects an integer, \"infinity\" or \"inf\", got \"" << v << "\"\n\n";
                usage();
                return 3;
            }
        }
```

Replace the `--themes` branch's `if (cmd == "mine") {...}` block with `if (cmd == "mine") { mine_out.themes = true; continue; }` placed **before** the `cmd != "probe"` check, and add three new branches after it:

```cpp
        else if (a == "--json" || a == "--solutions" || a == "--interactive" || a == "--tui") {
            if (cmd != "mine") {
                std::cerr << "error: " << cmd << " has no \"" << a << "\" flag; only \"mine\" has it\n\n";
                usage();
                return 3;
            }
            if (a == "--json") mine_out.json = true;
            else if (a == "--solutions") mine_out.solutions = true;
            else mine_out.interactive = true;
        }
```

Dispatch: pass `mine_out` as the last argument of `cmd_mine`.

- [ ] **Step 4: Run the tests**

Run: `make build 2>&1 | tail -3 && make test-cli 2>&1 | tail -5 && ./build/helpmate_tests "[mine_set]"`
Expected: all `cli_*` tests pass (including the new one; `cli_mine_themes_rejected` is gone), core tests still pass.

- [ ] **Step 5: Format and commit**

```bash
make format BASE=main
git add src/packages/cli/main.cpp src/packages/cli/CMakeLists.txt src/packages/cli/tests/verify_mine_outputs.cmake
git commit -m "cli: mine --max infinity, --json, --themes, --solutions (MineSet-backed output)"
```

---

### Task 8: `--interactive` end-to-end

**Files:**
- Modify: `src/packages/cli/CMakeLists.txt`
- Create: `src/packages/cli/tests/verify_mine_shell.cmake`, `src/packages/cli/tests/mine_shell_session.txt`

**Interfaces:**
- Consumes: `run_mine_shell` (Task 6) already wired in `cmd_mine` (Task 7).

- [ ] **Step 1: Write the session and the failing ctest** — `src/packages/cli/tests/mine_shell_session.txt`:

```
theme mirror
count 1
themes
back
list 1 2
show 1
save @OUT@
quit
list
```

`src/packages/cli/tests/verify_mine_shell.cmake`:

```cmake
# Test-support script (not installed): drives `mine --interactive` through a
# piped stdin and pins what a user sees. Required: -DHELPMATE -DTABLES -DSESSION
foreach(v HELPMATE TABLES SESSION)
  if(NOT DEFINED ${v})
    message(FATAL_ERROR "verify_mine_shell.cmake: -D${v}=... is required")
  endif()
endforeach()
set(out_json "${TABLES}/shell_out.json")
file(REMOVE "${out_json}")
file(READ "${SESSION}" script)
string(REPLACE "@OUT@" "${out_json}" script "${script}")
file(WRITE "${TABLES}/shell_session.txt" "${script}")

execute_process(COMMAND "${HELPMATE}" mine KQvk --dtm 2 --max infinity --interactive --tables "${TABLES}"
                INPUT_FILE "${TABLES}/shell_session.txt"
                OUTPUT_VARIABLE out ERROR_VARIABLE err RESULT_VARIABLE rc)
if(NOT rc EQUAL 0)
  message(FATAL_ERROR "shell exited ${rc}:\n${out}\n${err}")
endif()
foreach(p "loaded 580 positions \\(KQvk dtm=2\\)" "\\[580\\] mine> " "\\[477\\] mine> " "\\[257\\] mine> ")
  if(NOT "${err}" MATCHES "${p}")
    message(FATAL_ERROR "stderr lacks ${p}:\n${err}")
  endif()
endforeach()
# stdout, in order: narrowing tallies, histogram, back, list, show, save.
if(NOT "${out}" MATCHES "^477 positions\n257 positions\n")
  message(FATAL_ERROR "tallies wrong:\n${out}")
endif()
if(NOT "${out}" MATCHES "\nmirror +257\n")
  message(FATAL_ERROR "histogram lacks mirror 257:\n${out}")
endif()
if(NOT "${out}" MATCHES "\n477 positions\n     1  8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n     2  ")
  message(FATAL_ERROR "back/list wrong:\n${out}")
endif()
if(NOT "${out}" MATCHES "\n8/8/8/8/8/8/8/k1KQ4 b - - 0 1\n  themes:[^\n]*mirror[^\n]*\n  Ka2 Qa4#\n")
  message(FATAL_ERROR "show wrong:\n${out}")
endif()
if(NOT "${out}" MATCHES "saved 477 positions to [^\n]*shell_out.json \\(json, themes\\)\n$")
  message(FATAL_ERROR "save line wrong or something ran after quit:\n${out}")
endif()
if(NOT EXISTS "${out_json}")
  message(FATAL_ERROR "save did not write ${out_json}")
endif()
file(READ "${out_json}" saved)
if(NOT "${saved}" MATCHES "\"positions\"" OR NOT "${saved}" MATCHES "\"themes\"")
  message(FATAL_ERROR "saved JSON lacks positions/themes:\n${saved}")
endif()

# A second session: errors do not end the loop; EOF ends it with 0.
file(WRITE "${TABLES}/shell_errors.txt" "theme nosuch\nshow 0\nfrobnicate\ncount 1\n")
execute_process(COMMAND "${HELPMATE}" mine KQvk --dtm 2 --max 20 --interactive --tables "${TABLES}"
                INPUT_FILE "${TABLES}/shell_errors.txt"
                OUTPUT_VARIABLE out2 ERROR_VARIABLE err2 RESULT_VARIABLE rc2)
if(NOT rc2 EQUAL 0)
  message(FATAL_ERROR "error session exited ${rc2}")
endif()
foreach(p "unknown theme" "valid themes:" "no hit 0 \\(set has 20\\)" "unknown command \"frobnicate\"")
  if(NOT "${err2}" MATCHES "${p}")
    message(FATAL_ERROR "stderr lacks ${p}:\n${err2}")
  endif()
endforeach()
if(NOT "${out2}" MATCHES " positions\n$")
  message(FATAL_ERROR "count 1 did not run after the errors:\n${out2}")
endif()
message(STATUS "mine --interactive session verified")
```

In `CMakeLists.txt`, after `cli_mine_outputs`:

```cmake
add_test(NAME cli_mine_shell COMMAND ${CMAKE_COMMAND}
         -DHELPMATE=$<TARGET_FILE:helpmate>
         -DTABLES=${CLI_TT}
         -DSESSION=${CMAKE_CURRENT_SOURCE_DIR}/tests/mine_shell_session.txt
         -P ${CMAKE_CURRENT_SOURCE_DIR}/tests/verify_mine_shell.cmake)
set_tests_properties(cli_mine_shell PROPERTIES DEPENDS cli_gen)
```

- [ ] **Step 2: Run it**

Run: `make build 2>&1 | tail -3 && ctest --test-dir build --output-on-failure -R cli_mine_shell`
Expected: PASS on first run if Tasks 6 and 7 are correct. If a pattern fails, print the captured `out`/`err` from the failure message and compare against the reply-format table in Task 6; fix the implementation, not the pinned text, unless the table itself is what changed.

- [ ] **Step 3: Try it by hand once** (not a test, a sanity check that the terminal experience matches the spec):

```bash
printf 'themes\nquit\n' | ./build/helpmate mine KQvk --dtm 2 --max 100 --interactive --tables build/cli_tables
```

Expected: prompt `[100] mine> ` on the terminal, a 29-line histogram, exit 0.

- [ ] **Step 4: Commit**

```bash
git add src/packages/cli/CMakeLists.txt src/packages/cli/tests/verify_mine_shell.cmake src/packages/cli/tests/mine_shell_session.txt
git commit -m "cli: end-to-end ctest for mine --interactive (piped session, errors, save)"
```

---

### Task 9: Docs, changelog, version, coverage

**Files:**
- Modify: `docs/USAGE.md` (the `mine` section starting at "## `mine` — scan for composition candidates", ~line 522)
- Modify: `CHANGELOG.md` (new `## [0.18.0] - <date>` above `## [0.17.0]`)
- Modify: `VERSION` (`0.17.0` → `0.18.0`)
- Modify: `docs/ROADMAP.md` (add a short shipped entry)

- [ ] **Step 1: Version** — `printf '0.18.0\n' > VERSION`, then `grep -rn "0\.17\.0" --include=pyproject.toml --include=*.py --include=*.toml . | grep -v CHANGELOG` and update any other hard-coded copy the grep finds (there should be none; CMake reads `VERSION`).

- [ ] **Step 2: USAGE.md** — in the `mine` synopsis line add `[--themes] [--solutions] [--json] [--interactive]` and change `[--max N]` to `[--max N|infinity]`. In the option list, change the `--max N` bullet to:

```
- `--max N`: cap on positions (default 10); `--max infinity` (or `inf`) lifts
  the cap;
- `--themes`: annotate every hit with all the themes it shows (every
  non-parametric theme; `promotions:<types>` is asked for with `--theme`);
- `--solutions`: print every optimal solution of each hit as SAN;
- `--json`: emit one JSON document instead of text (below);
- `--interactive` (alias `--tui`): after the scan, open a shell over the
  result (below).
```

After the saturated-count note paragraph, append three subsections:

````
### Annotated text output

With `--themes` and/or `--solutions` each hit becomes a block: the FEN, an
indented `themes:` line, one indented line per solution, then a blank line.
The bare FEN list is `grep -v '^ ' | grep .` away.

```
$ helpmate mine KQvk --dtm 2 --max 2 --themes --solutions --tables tt
8/8/8/8/8/8/8/k1KQ4 b - - 0 1
  themes: set-play pure model ideal mirror single-piece single-piece:white single-piece:black
  Ka2 Qa4#

8/8/8/8/8/2Q5/8/k1K5 b - - 0 1
  themes: single-piece single-piece:white single-piece:black
  Ka2 Qb2#

```

A hit whose solutions reach a material this `--tables` directory lacks
prints `  unavailable: <reason>` instead, and `mine` prints one note with the
`gen` command that fixes it.

### JSON output

`--json` prints one object. `fen`, `dtm`, `count` are always present per
position; `themes` needs `--themes`; `starts`, `ends`, `solutions` need
`--solutions`. `max` is the integer given or `"infinity"`. The filter block
repeats what was asked, `-1` meaning "not filtered".

```
$ helpmate mine KQvk --dtm 2 --max 1 --json --themes --solutions --tables tt
{
  "material": "KQvk",
  "filter": {"dtm": 2, "count": -1, "starts": -1, "ends": -1, "themes": []},
  "max": 1,
  "skipped_saturated": 0,
  "positions": [
    {
      "fen": "8/8/8/8/8/8/8/k1KQ4 b - - 0 1",
      "dtm": 2,
      "count": 1,
      "themes": ["set-play", "pure", "model", "ideal", "mirror", "single-piece", "single-piece:white", "single-piece:black"],
      "starts": 1,
      "ends": 1,
      "solutions": [["Ka2", "Qa4#"]]
    }
  ]
}
```

### Interactive mining

`--interactive` runs the scan once, keeps the hits in memory, and opens a
prompt. Nothing rescans the table: narrowing, tallies and `show` work on the
held set, computing each position's themes and solutions the first time they
are needed and caching them. The prompt (on stderr) shows the current size.

| Command | Effect |
|---|---|
| `theme NAME` | keep positions showing NAME (`promotions:qrr` works too) |
| `not theme NAME` | drop positions showing NAME |
| `count N`, `starts N`, `ends N` | keep positions with exactly that value |
| `back` | undo the last narrowing; `reset` returns to the loaded set |
| `list [FROM [N]]` | print FENs FROM..FROM+N-1 with their index (default 1, 20) |
| `show I` | FEN, themes and every solution of hit I |
| `themes` | how many positions in the current set show each theme |
| `save FILE` | `.json`: the JSON above (themes if known for the whole set or `--themes` given, solutions if `--solutions` given); anything else: bare FENs |
| `help`, `quit` | (EOF quits too) |

```
$ helpmate mine KQvk --dtm 2 --max infinity --interactive --tables tt
loaded 580 positions (KQvk dtm=2)
[580] mine> theme mirror
477 positions
[477] mine> count 1
257 positions
[257] mine> show 1
8/8/8/8/8/8/8/k1KQ4 b - - 0 1
  themes: set-play pure model ideal mirror single-piece single-piece:white single-piece:black
  Ka2 Qa4#
[257] mine> save mirror-unique.json
saved 257 positions to mirror-unique.json (json, themes)
[257] mine> quit
```

Stdout carries only results, so `helpmate mine ... --interactive < script > out`
gives a clean file. There is no line editing; use `rlwrap helpmate ...` for
history. `back` keeps whole copies of each previous set, which for a
100k-position root and a deep stack is tens of MB.
````

Refresh the two `themes:` lists in the examples from the real binary (`./build/helpmate probe "<fen>" --themes --tables build/cli_tables`) so they match the 0.18.0 registry.

- [ ] **Step 3: CHANGELOG.md** — insert above `## [0.17.0]`:

```
## [0.18.0] - <today's date, YYYY-MM-DD>

### Added
- **`mine` holds its result: `--json`, `--themes`, `--solutions`, `--max
  infinity`, and an `--interactive` shell.** `--max infinity` (or `inf`)
  lifts the cap. `--themes` annotates every hit with all non-parametric
  themes it shows, `--solutions` with every optimal solution; in text mode
  these print as indented lines under the FEN, and `--json` emits one
  document (`material`, `filter`, `max`, `skipped_saturated`,
  `positions[]`). `--interactive` (alias `--tui`) opens a prompt over the
  held set: `theme`/`not theme`/`count`/`starts`/`ends` narrow it without
  rescanning, `back`/`reset` undo, `list`/`show` inspect, `themes` tallies
  every theme over the current set, `save FILE` writes JSON or FENs. Backed
  by a new core unit, `MineSet` (`probe/mine_set.h`), plus a stream-driven
  `run_mine_shell`, both unit-tested with Catch2; `Tablebase` gained
  `shows_theme` so a parametric theme can be checked on one position. The
  Python bindings and the HTTP API are unchanged.

### Changed
- `mine --themes` is now a real flag (it used to be rejected as a typo for
  `--theme`). `probe --theme` is still rejected.
```

- [ ] **Step 4: ROADMAP.md** — under the most recent shipped section, add:

```
## v0.18.0 — `mine` result sets: JSON, solutions, `--max infinity`, interactive shell

- **Shipped.** Design: `docs/superpowers/specs/2026-09-10-mine-interactive-design.md`.
- Follow-up: expose `MineSet` through the Python bindings and `/v1/mine`.
```

- [ ] **Step 5: Full verification**

Run, in order, and paste the tails into the commit message body if anything is notable:

```bash
make build 2>&1 | tail -3
make test 2>&1 | tail -5            # all ctest, incl. core via catch_discover_tests
make test-cli 2>&1 | tail -3
./build/helpmate --version          # helpmate 0.18.0
make format-check BASE=main
make coverage 2>&1 | tail -15       # read the summary; mine_set.cpp and mine_shell.cpp lines >= 80 %
```

If coverage of either new file is below 80 %, add Catch2 cases for the uncovered branches (the coverage HTML at `build-cov/coverage/index.html` names the lines) before committing.

- [ ] **Step 6: Commit**

```bash
git add docs/USAGE.md CHANGELOG.md VERSION docs/ROADMAP.md
git commit -m "docs+release: 0.18.0 -- mine --json/--themes/--solutions/--max infinity/--interactive"
```

Then hand over to `superpowers:finishing-a-development-branch` (PR against `main`; the release itself is the `v0.18.0` tag after merge, per the roadmap memory).
