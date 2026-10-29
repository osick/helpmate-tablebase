# Theme occurrence counts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `--theme NAME:N` matches a position when theme NAME occurs at least N times summed over all its optimal solutions (`promotion:4`, `ideal:2`), on every surface that accepts a theme name.

**Architecture:** Every per-solution detector gets a counting twin `count_X(const Solution&) -> int`, and the boolean `has_X` becomes `count_X(s) > 0`, so there is one implementation per theme. The registry entry carries the counter; `resolve_theme` parses a trailing `:<digits>` into `ResolvedTheme::min_count`, and `ResolvedTheme::eval` sums the counter over the solutions. All surfaces already resolve names through `resolve_theme`, so the filter needs no surface code; the surfaces only gain a `countable` flag, JSON `theme_counts` and a dashboard text field.

**Tech Stack:** C++20 core (Catch2 tests, `build/helpmate_tests`), pybind11 bindings (pytest), FastAPI server (pytest), dashboard ES modules (`node --test`, Playwright UI tests).

**Spec:** `docs/superpowers/specs/2026-10-29-theme-occurrence-counts-design.md`

## Global Constraints

- A trailing `:<digits>` is a count; `1 <= N <= 9999`; the canonical name prints N without leading zeros (`ideal:02` -> `ideal:2`).
- Count = occurrences summed over ALL optimal solutions, matched as `>= N`.
- Not countable: `set-play`, `zilahi`, `allumwandlung`, `promotions:<types>`.
- Error messages exactly as in the spec's error table.
- No existing output changes: `probe` text, `mine` text, the `"themes"` list in JSON, `detect()`; `has_X(s) == (count_X(s) > 0)` for every theme.
- Commits end with the two attribution lines from the session (Co-Authored-By, Claude-Session).
- Run builds and tests with `taskset -c 1-7,9-15`.

## Review Focus

1. **A theme name that already contains a colon** (`excelsior:white:2`, `single-piece:black:3`, `maslar:black-white:2`) must resolve to that theme with a count, not to "unknown theme" — Task 2, `resolve_theme: counts on colon names`.
2. **`promotion:qrr`** must keep its "did you mean promotions:qrr?" error and **`promotion:4`** must now be valid — Task 2, `resolve_theme: the promotion/promotions pair`.
3. **`nocapture:2`** means "at least 2 capture-free solutions", not "every solution" — Task 2, `eval: nocapture counts capture-free solutions`.
4. **A count no position can reach** (`--count 1 --theme ideal:2`) returns no hits and no error — Task 3, `mine: an unreachable count is no hits, not an error`.
5. **Existing answers unchanged on real tables**: the `themes` lists of `mine --themes --jsonl` are byte-identical before and after — Task 1 baseline, Task 4 comparison.

---

### Task 1: Counting detectors for line and mate themes

**Files:**
- Modify: `src/core/themes/line_themes.h`, `src/core/themes/line_themes.cpp`
- Modify: `src/core/themes/mate_themes.h`, `src/core/themes/mate_themes.cpp`
- Test: `src/core/tests/test_line_themes.cpp`, `src/core/tests/test_mate_themes.cpp`
- Create (not committed): `$CLAUDE_JOB_DIR/tmp/themes-baseline/` — the regression baseline

**Interfaces:**
- Produces, in `namespace hm::themes`, one `int count_X(const Solution& s)` per row of the spec's occurrence table: `count_pure`, `count_model`, `count_ideal`, `count_mirror`, `count_umnov_mate`, `count_promotion`, `count_underpromotion`, `count_excelsior`, `count_excelsior_white`, `count_excelsior_black`, `count_switchback`, `count_closed_walk`, `count_pendulum`, `count_self_block`, `count_single_piece`, `count_single_piece_white`, `count_single_piece_black`, `count_en_passant`, `count_kniest`, `count_zajic`, `count_phoenix`, `count_schnoebelen`, `count_capture_free`, `count_check_free`, `count_umnov`, `count_klasinc`, `count_indian`, `count_maslar`, `count_maslar_black_white`.
- Every existing `bool has_X` / `is_X` keeps its signature and becomes `return count_X(s) > 0;` (for the 0/1 themes the counter is `is_X(s) ? 1 : 0` and `is_X` keeps its body — whichever direction leaves one implementation).

- [ ] **Step 1: Record the regression baseline with the current build**

Before touching code, on the unchanged branch:

```bash
taskset -c 1-7,9-15 make build
for spec in "KQvk 8" "KPvk 13" "KBPvk 14" "KRBPvk 14" "KBvkrp 26" "KNPvkn 15" "KPPvk 14" "KBBvk 13"; do
  set -- $spec
  ./build/helpmate mine $1 --dtm $2 --themes --jsonl --max 2000 --tables ~/tb > "$CLAUDE_JOB_DIR/tmp/themes-baseline/$1-$2.jsonl"
done
```

Expected: eight non-empty files (promotion, excelsior, switchback, pendulum, self-block and mate themes all occur in them).

- [ ] **Step 2: Write the failing count tests**

In `test_line_themes.cpp`, a `TEST_CASE("occurrence counts per solution", "[themes][line][count]")` using the file's `play(fen, specs)` helper, one `SECTION` per counter with hand-built lines, asserting exact values from the spec table:
- two promotions in one line (`count_promotion == 2`), one of them to a knight (`count_underpromotion == 1`);
- a unit going a1-b1-a1-b1 (`count_switchback == 2`, `count_pendulum == 1`);
- a unit going a1-b1-c1-a1 then a1-b1-c1-a1 again (`count_closed_walk == 2`), and a1-b1-c1-a1-b1-c1 (`== 1`);
- a quiet line (`count_capture_free == 1`), a line with one capture (`== 0`);
- two Umnov plies in one line (`count_umnov == 2`);
- an empty solution (already mate): every counter `== 0`.

In `test_mate_themes.cpp`: `count_ideal`, `count_model`, `count_pure`, `count_mirror` are 1 on the file's existing positive fixtures and 0 on its negatives.

Plus `TEST_CASE("has_X agrees with count_X on every fixture", "[themes][count]")`: for every Solution built in both test files' existing fixtures (collect them in a vector), for each pair, `REQUIRE(has_X(s) == (count_X(s) > 0))`.

- [ ] **Step 3: Run the tests and see them fail**

Run: `taskset -c 1-7,9-15 make build` — Expected: compile errors, `count_promotion` etc. not declared.

- [ ] **Step 4: Implement the counters**

Each counter follows the detector's existing scan with `return true` replaced by `++n` and a final `return n`, except where the spec table fixes a different unit:
- `count_closed_walk`: per trajectory, scan i left to right; when (i, j) is a circuit by the existing test, `++n` and continue at i = j; else ++i.
- `count_pendulum`: units, so one per qualifying trajectory.
- `count_self_block`: one per qualifying field square (the existing loop's `return true` becomes `++n; break;` out of the ply loop).
- `count_zajic`: one per king recapture j that has an earlier capture i on the mating square.
- `count_phoenix`, `count_schnoebelen`: one per qualifying promoting ply.
- `count_klasinc`: one per (trajectory, leave index k) window with a line piece passing over.
- `count_indian`, `count_maslar`, `count_maslar_black_white`: one per distinct completing ply. `critical_then_interference` gains a variant that collects completing ply indices into a `std::set<int>` instead of stopping at the first; `finish` returns the completing ply index (or -1) instead of bool.

- [ ] **Step 5: Run the tests and see them pass**

Run: `taskset -c 1-7,9-15 make test-core`
Expected: all test cases pass, including every existing `[themes]` test unchanged.

- [ ] **Step 6: Commit**

```bash
git add src/core/themes src/core/tests/test_line_themes.cpp src/core/tests/test_mate_themes.cpp
git commit -m "themes: an occurrence counter for every per-solution theme"
```

### Task 2: Counted themes in the registry and the resolver

**Files:**
- Modify: `src/core/themes/registry.h`, `src/core/themes/registry.cpp`
- Test: `src/core/tests/test_themes_registry.cpp`

**Interfaces:**
- Consumes: the `count_X` functions of Task 1.
- Produces:
  - `using Counter = int (*)(const Solution&);` and a new last member `Counter count = nullptr;` in `ThemeDef` (null = not countable).
  - `bool countable(const ThemeDef& t);` (`t.count != nullptr`).
  - `ResolvedTheme::min_count` (`int`, 0 = plain theme); `eval` sums `def->count` over `in.solutions` and returns `sum >= min_count` (false on an empty set; stop summing once reached); `name()` appends `":" + std::to_string(min_count)` when `min_count > 0`.
  - `std::vector<std::pair<std::string, int>> count_all(const ThemeInput& in);` — every countable theme with total > 0, in registry order, keyed by the registry name.
  - `inline constexpr int kMaxThemeCount = 9999;`

- [ ] **Step 1: Write the failing tests**

In `test_themes_registry.cpp`:
- `TEST_CASE("resolve_theme: counts", ...)`: `resolve_theme("promotion:4")` has `def->name == "promotion"`, `min_count == 4`, `name() == "promotion:4"`; `resolve_theme("ideal:02")->name() == "ideal:2"`; `ideal:0`, `ideal:10000` fail with the spec's exact messages.
- `TEST_CASE("resolve_theme: counts on colon names", ...)`: `excelsior:white:2`, `single-piece:black:3`, `maslar:black-white:2` resolve to those registry names with `min_count` 2, 3, 2.
- `TEST_CASE("resolve_theme: the promotion/promotions pair", ...)`: `promotion:qrr` still fails mentioning `promotions:qrr`; `promotion:4` succeeds; `promotions:qrr` is still parametric with `min_count == 0`; `promotions:qrr:2` fails with the not-countable message.
- `TEST_CASE("resolve_theme: not countable", ...)`: `set-play:2` -> "a property of the position"; `zilahi:2`, `allumwandlung:2` -> "a property of the whole solution set"; `pure:yes` -> the spec's message.
- `TEST_CASE("countable themes are exactly the per-solution ones", ...)`: `countable()` is false for exactly `set-play`, `zilahi`, `allumwandlung`, `promotions`; true for every other registry entry.
- `TEST_CASE("eval sums occurrences over solutions", ...)`: with a ThemeInput of two hand-built solutions, one with 2 promotions and one with 1: `promotion:3` true, `promotion:4` false, `promotion:1` == plain `promotion`.
- `TEST_CASE("eval: nocapture counts capture-free solutions", ...)`: two solutions, one quiet, one capturing: plain `nocapture` false, `nocapture:1` true, `nocapture:2` false.
- `TEST_CASE("count_all lists every countable theme that occurs", ...)`: on the two-solution input, contains `{"promotion", 3}`, contains no entry with value 0 and no entry for a non-countable theme.

- [ ] **Step 2: Run them and see them fail**

Run: `taskset -c 1-7,9-15 make build` — Expected: compile errors (`min_count`, `countable`, `count_all` unknown).

- [ ] **Step 3: Implement**

Registry: every countable entry gets its `count_X` as the new last field (the four non-countable entries leave it null). `resolve_theme`: before the existing logic, if `name` ends in `:` followed by one or more digits, split there, parse the number (reject 0 and > 9999 with the spec's messages, which quote the full typed name), resolve the prefix with the existing logic, then reject a parametric or non-countable result with the spec's message; otherwise return it with `min_count` set. A `base:value` whose value is not all digits keeps today's path, and the `pure:yes` message is changed to the spec's wording.

- [ ] **Step 4: Run and see them pass**

Run: `taskset -c 1-7,9-15 make test-core` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/core/themes/registry.h src/core/themes/registry.cpp src/core/tests/test_themes_registry.cpp
git commit -m "themes: NAME:N counts occurrences over all solutions"
```

### Task 3: The count in `mine`, the CLI listing, JSON and the bindings

**Files:**
- Modify: `src/core/probe/tablebase.h`, `src/core/probe/tablebase.cpp` (new `theme_counts`)
- Modify: `src/core/probe/mine_set.h`, `src/core/probe/mine_set.cpp` (`theme_counts` in JSON hits)
- Modify: `src/packages/cli/main.cpp` (`cmd_themes`, usage text for `--theme`)
- Modify: `src/packages/bindings/pymodule.cpp` (`countable` in `themes()`)
- Modify: `src/packages/cli/CMakeLists.txt` (CLI tests)
- Test: `src/core/tests/test_mine_set.cpp`, `src/core/tests/test_mine_shell.cpp`, `src/packages/bindings/tests/test_smoke.py`

**Interfaces:**
- Consumes: `themes::countable`, `themes::count_all`, `ResolvedTheme::min_count` (Task 2).
- Produces: `std::vector<std::pair<std::string,int>> Tablebase::theme_counts(const std::string& fen, int max) const` (built on the existing `with_theme_input`); `Hit::theme_counts` of that type, filled where `h.themes` is filled; JSON key `"theme_counts"` (object, registry order) on a hit whenever `"themes"` is emitted; Python `themes()` dicts gain `"countable": bool`.

- [ ] **Step 1: Write the failing tests**

- `test_mine_set.cpp`: on the file's existing KQvk fixture tables, `mine` with `themes = {"nocapture:1"}` returns the same FENs as `{"nocapture"}` restricted to single-solution hits; a JSON hit with themes on contains `"theme_counts"` and its `"themes"` list is unchanged from before (compare with the existing expected string).
- `TEST_CASE("mine: an unreachable count is no hits, not an error")`: `count = 1`, `themes = {"ideal:2"}` returns zero hits and throws nothing.
- `test_mine_shell.cpp`: the shell's theme filter command, in the file's existing style, accepts `ideal:1` (same hits as `ideal`) and rejects `ideal:0` with the resolver's message.
- `test_smoke.py`: `by_name["promotion"]["countable"] is True`, `by_name["set-play"]["countable"] is False`; `helpmate.check_theme("ideal:2") is None`; `"at least 1" in helpmate.check_theme("ideal:0")`; `tb.mine("KQvk", 2, themes=["ideal:2"], max=3)` runs without error.
- `CMakeLists.txt`: `cli_themes_countable` runs `helpmate themes` with `PASS_REGULAR_EXPRESSION "countable: yes"`; `cli_mine_count` runs `helpmate mine KQvk --dtm 2 --theme ideal:1 --max 3` on `${CLI_TT}`; `cli_mine_count_bad` runs it with `ideal:0` and `WILL_FAIL TRUE`.

- [ ] **Step 2: Run and see them fail**

Run: `taskset -c 1-7,9-15 make test-core test-cli test-bindings` — Expected: failures on `theme_counts`, `countable`, `cli_themes_countable`.

- [ ] **Step 3: Implement**

`cmd_themes`: after `needs:`, print `    countable: yes` or `no`; after the list, one wrapped paragraph: "NAME:N (countable themes only) matches when the theme occurs at least N times over all optimal solutions, e.g. promotion:4 or ideal:2." The `--theme` usage line gains `NAME:N`. Text output of `mine` and `probe` stays byte-identical.

- [ ] **Step 4: Run and see them pass; regression against the baseline**

Run: `taskset -c 1-7,9-15 make test-core test-cli test-bindings` — Expected: all pass.
Then rerun the eight Task 1 baseline commands into `themes-after/` and compare only the `themes` lists:

```bash
for f in "$CLAUDE_JOB_DIR"/tmp/themes-baseline/*.jsonl; do
  diff <(jq -c '{fen,themes}' "$f") <(jq -c '{fen,themes}' "$CLAUDE_JOB_DIR/tmp/themes-after/$(basename "$f")") || echo "DIFF in $f"
done
```

Expected: no output.

- [ ] **Step 5: Commit**

```bash
git add src/core/probe src/packages/cli src/packages/bindings src/core/tests/test_mine_set.cpp src/core/tests/test_mine_shell.cpp
git commit -m "mine: counted themes, theme_counts in JSON, countable in the theme list"
```

### Task 4: API and dashboard

**Files:**
- Modify: `src/packages/web/helpmate_web/static/js/lib/themes.js` (`themeQueryNames`)
- Modify: `src/packages/web/helpmate_web/static/js/mine.js` (read the new field)
- Modify: `src/packages/web/helpmate_web/static/index.html` (the field, next to `#mine-theme-params`)
- Test: `src/packages/web/tests/js/themes.test.js`, `src/packages/api/tests/test_api_mine.py`, `src/packages/web/tests/ui/` (existing mine-screen test file)

**Interfaces:**
- Consumes: `/v1/themes` now carries `countable` (Task 3, via the bindings); `/v1/mine` already passes `theme` values to `resolve_theme`.
- Produces: `themeQueryNames(selected, paramValues, countText = "")` — `countText` split on whitespace and commas, empty words dropped, appended after the existing names; an input `<input id="mine-theme-counts" placeholder="e.g. promotion:4 ideal:2">` labelled "Count filters".

- [ ] **Step 1: Write the failing tests**

- `themes.test.js`: `themeQueryNames(["pure"], {}, " promotion:4, ideal:2 ")` deep-equals `["pure", "promotion:4", "ideal:2"]`; with `countText` omitted the result is unchanged from today's tests.
- `test_api_mine.py`: `/v1/mine` with `theme=ideal:2` is 200 (fake or fixture tables, as the file's existing theme tests do); with `theme=ideal:0` it is 400 and the body contains "at least 1"; `/v1/themes` lists `countable` for every theme.
- UI test: typing `ideal:1` into `#mine-theme-counts` and searching sends a request whose `theme` parameters include `ideal:1` (check with the existing request-capture pattern of that test file).

- [ ] **Step 2: Run and see them fail**

Run: `node --test src/packages/web/tests/js/themes.test.js` and `taskset -c 1-7,9-15 make test-api` — Expected: the new cases fail.

- [ ] **Step 3: Implement** the parameter, the input and its reading in `mine.js` (`q.theme = themeQueryNames(selectedThemes(themeSel), paramValues, countInput.value)`).

- [ ] **Step 4: Run and see them pass**

Run: `taskset -c 1-7,9-15 make test-api test-web` and `node --test src/packages/web/tests/js/*.test.js` — Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add src/packages/web src/packages/api/tests/test_api_mine.py
git commit -m "dashboard: count filters for themes"
```

### Task 5: Documentation, full verification, PR

**Files:**
- Modify: `docs/USAGE.md` (the `--theme` option and the Themes section), `docs/THEME-CATALOG.md` (a "counting" column or note with the spec's occurrence table), `CHANGELOG.md` (Unreleased, Added)

- [ ] **Step 1: Write the docs.** USAGE: `--theme NAME:N`, the four rules of the spec's Semantics section, two examples (`--count 2 --theme ideal:2`, `--theme promotion:4`), and `theme_counts` in JSON. THEME-CATALOG: the occurrence definition per theme, copied from the spec table. CHANGELOG: one entry crediting the request as user feedback.

- [ ] **Step 2: Full verification**

Run: `taskset -c 1-7,9-15 make test-all`, `make lint`, `make typecheck`, and `make coverage` — Expected: all green; line coverage of `src/core/themes/` at least 80 % (report the figure).

- [ ] **Step 3: Real search sanity check**

Run: `./build/helpmate mine KPPvk --dtm 14 --theme promotion:2 --themes --jsonl --max 5 --tables ~/tb` and `./build/helpmate mine KBBvk --dtm 9 --count 2 --theme model:2 --themes --jsonl --max 5 --tables ~/tb` — Expected: each hit's `theme_counts` shows `promotion >= 2` resp. `model == 2`; report the hits (or that none exist) to the user.

- [ ] **Step 4: Commit, push, open the PR** (after the user's go)

```bash
git add docs CHANGELOG.md
git commit -m "docs: theme occurrence counts"
```
