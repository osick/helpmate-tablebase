# `helpmate mine`: JSON output, full solutions, no cap, and an interactive shell

Date: 2026-09-10. Branch: `feature/mine-interactive`. Target release: 0.18.0.

## Why

`mine` answers "which positions of MATERIAL have dtm D (and count C, shape,
themes)?" and prints bare FENs. With 30 themes in the registry a query often
returns thousands of hits, and the next question is always a narrowing one:
"of these, which also show a switchback? how many are mirror mates? show me
number 17 with all its solutions." Today each of those is a fresh table scan
with a longer flag list, and the answer is still bare FENs that need a
`probe --themes` per line to read. This round makes a `mine` result a thing
you can hold, annotate, narrow and export.

Four user-facing additions, one shared model:

1. `--max infinity`: no cap on hits.
2. `--json`: the result as one JSON document.
3. `--themes`: evaluate every non-parametric theme for every hit.
4. `--solutions`: every optimal solution for every hit.
5. `--interactive` (alias `--tui`): after the scan, a shell over the held
   result set that narrows, inspects, tallies and saves without rescanning.

Out of scope this round: the Python bindings, the HTTP API and the web
dashboard. They keep their current `mine` surface; the new core unit is
written so they can adopt it later without a redesign.

## Architecture

Three units, each with one job:

| Unit | Lives in | Does |
|---|---|---|
| `MineSet` | `src/core/probe/mine_set.{h,cpp}` | Holds hits; enriches them lazily; narrows; tallies; serialises to JSON and text |
| `mine_shell` | `src/core/probe/mine_shell.{h,cpp}` | Reads commands from a stream, applies them to a `MineSet`, prints replies |
| `cmd_mine` | `src/packages/cli/main.cpp` (existing) | Parses flags, runs the scan into a `MineSet`, then either prints it or hands it to the shell |

The shell lives in the core library, not the CLI package, so Catch2 can drive it through string streams; the CLI only wires `std::cin`/`std::cout`/`std::cerr` to it.

`Tablebase` gains one method, `shows_theme(fen, ResolvedTheme, max)`, so the shell can evaluate a parametric theme such as `promotions:qrr` on one hit; it shares the `ThemeInput` construction with `themes_of`. Nothing else in `Tablebase` changes. It is a read cache and stays one; the result set
is a query artifact and lives beside it. `MineSet` depends on `Tablebase`
only through its existing public methods (`probe`, `lines`,
`solution_shape`, `themes_of`) and on `themes::theme_registry()` for the
list of non-parametric names.

### `MineSet`

```cpp
struct Hit {
    std::string fen;
    int dtm = -1, count = -1;                 // from probe(); filled at load
    std::optional<SolutionShape> shape;       // starts/ends; filled on demand
    std::optional<std::vector<std::string>> themes;               // on demand
    std::optional<std::vector<std::vector<std::string>>> solutions;  // SAN; on demand
    std::string unavailable;  // non-empty: enrichment failed (MissingTableError text)
};

class MineSet {
public:
    MineSet(const Tablebase& tb, Material m, MineFilter f, uint64_t skipped_saturated);
    void add(const std::string& fen);            // probe() once, store dtm/count
    const std::vector<Hit>& hits() const;
    size_t size() const;

    // Enrichment (idempotent, cached per hit). `progress` may be null.
    void ensure_shape(Hit&);      void ensure_themes(Hit&);   void ensure_solutions(Hit&);
    void ensure_themes_all(std::function<void(size_t done, size_t total)> progress = nullptr);

    // Narrowing: each returns a NEW MineSet sharing tb/material/filter; the
    // caller keeps the old one (the shell's undo stack).
    MineSet with_theme(const std::string& name, bool negate) const;
    MineSet with_count(int) const;  MineSet with_starts(int) const;  MineSet with_ends(int) const;

    // Histogram: name -> number of hits showing it, for every non-parametric
    // registry theme, in registry order. Forces ensure_themes_all().
    std::vector<std::pair<std::string, size_t>> theme_histogram();

    // Output. `facets` says which optional fields to include.
    struct Facets { bool themes = false, solutions = false; };
    std::string to_json(Facets) const;   // forces the needed enrichment first
    void to_text(std::ostream&, Facets) const;
};
```

Enrichment cost is paid once per hit and never up front: `add` does one
`probe` (cheap, one table read); shape, themes and solutions walk the
solution tree and are computed only when a flag or shell command asks.
"All themes" means every registry entry whose `param` is null. That is the
check, not "name contains a colon": `single-piece:white` and
`excelsior:white` are full non-parametric names and must be included.

A hit whose enrichment throws `MissingTableError` (solutions walk into a
capture/promotion material this `--tables` directory lacks) gets the error
text in `unavailable`, its optional fields stay empty, and it is kept in the
set. It never matches a theme or shape narrowing and shows up as
`"unavailable": "..."` in JSON and an indented `unavailable: ...` line in
text. `MineSet` counts these; callers print one note, not one per hit.

### JSON shape

One object, streamed to stdout, built with `nlohmann::ordered_json`, which
`helpmate_core` already links, so key order is stable and escaping is the
library's. Keys are stable and documented in USAGE.md.

```json
{
  "material": "KQvk",
  "filter": {"dtm": 2, "count": -1, "starts": -1, "ends": -1, "themes": ["mirror"]},
  "max": "infinity",
  "skipped_saturated": 0,
  "positions": [
    {
      "fen": "8/7k/5K2/8/8/8/8/6Q1 b - - 0 1",
      "dtm": 2, "count": 1,
      "starts": 1, "ends": 1,
      "themes": ["mirror", "pure"],
      "solutions": [["Kh8", "Qg7#"]]
    }
  ]
}
```

`fen`, `dtm`, `count` are always present. `themes` appears with `--themes`;
`starts`, `ends`, `solutions` appear with `--solutions`. `max` is the
integer given or the string `"infinity"`. Filter values are the raw
`MineFilter` (`-1` = not filtered) so a consumer can see exactly what was
asked. A position with `unavailable` set carries that string and omits the
fields it could not compute.

### Text shape

Default (no facet flag) is unchanged: one FEN per line, nothing else, so
every existing script and ctest keeps working. With `--themes` and/or
`--solutions`:

```
8/7k/5K2/8/8/8/8/6Q1 b - - 0 1
  themes: mirror pure
  Kh8 Qg7#
  Kh6 Qg6#

<next FEN>
```

Solution lines use the same SAN rendering as `line --all`. Blank line
between hits. `grep -v '^ ' | grep .` recovers the bare FEN list.

### `--max infinity`

`--max` accepts `infinity` and `inf` (case-sensitive, like every other flag
value), meaning no cap; internally `INT_MAX`. `--max 0` still prints nothing;
negative and non-numeric values other than those two words stay rejected
with the existing message, now naming the two words. Applies to `line --all`
too, since the flag is shared; that costs nothing and avoids an asymmetry.

### Flag interactions in `cmd_mine`

- `--themes` is accepted by `mine` (it already is by `probe`). The special
  error "mine has no --themes flag; did you mean --theme" is removed. The
  companion error for `probe --theme` stays.
- `--json` with neither `--themes` nor `--solutions` is valid and gives the
  minimal per-position record.
- `--interactive` and `--tui` are synonyms; `--tui` is not mentioned in
  usage examples, only in the option list, so there is one spelling in docs.
- `--interactive` with `--json`, `--themes` or `--solutions`: the scan still
  fills the set; those flags then only set the default facets for `save`
  and are otherwise ignored. Not an error, so a user can add `--interactive`
  to a command line they already have.
- Streaming: without `--interactive` and without `--json`, hits are printed
  as they are found (as today). With `--json`, output is emitted after the
  scan because the object needs `skipped_saturated` and an array; the set is
  still built incrementally. With `--interactive`, nothing is printed until
  the prompt appears except a one-line scan summary on stderr.

## The shell

Started by `--interactive`. The scan runs first, honouring `--max`, and its
hits become the root set. stderr gets `loaded N positions (KQvk dtm=2 ...)`.
Then a plain `std::getline` loop on stdin. No readline, no terminal control
sequences: it must work under `rlwrap`, through a pipe, and in ctest.

Prompt, on **stderr**: `[N] mine> ` where N is the current set size. stdout
carries only command results, so `helpmate mine ... --interactive < script
> out` yields a clean file.

| Command | Effect |
|---|---|
| `theme NAME` | keep hits that show NAME (parametric values allowed: `theme promotions:qrr`) |
| `not theme NAME` | drop hits that show NAME |
| `count N`, `starts N`, `ends N` | keep hits with that exact value |
| `back` | undo the last narrowing (stack; `back` at the root says so) |
| `reset` | return to the root set |
| `list [FROM [N]]` | print FENs FROM..FROM+N-1 (1-based; default 1, 20) with their index |
| `show I` | print hit I: FEN, `themes:` line, every solution |
| `themes` | histogram: every non-parametric theme with its count over the current set, zeros included, registry order |
| `save FILE` | `.json` suffix: JSON, facets as defined below; otherwise bare FENs, one per line |
| `help` | the table above |
| `quit`, `exit`, EOF | leave, exit code 0 |

`save FILE.json` facets, precisely: themes are included when every hit in
the current set already has them (i.e. after `themes` or a `theme` narrowing
that forced them) or when `--themes` was on the command line; solutions are
included when `--solutions` was on the command line. `save` never triggers a
bulk enumeration on its own; the shell says which facets it wrote.

Rules:

- Every narrowing that needs themes calls `ensure_themes_all` with a
  progress callback; the shell prints `evaluating themes: 400/1234` on stderr
  every 100 hits (or 1 s), so a long pass is visibly alive. Sets already
  enriched pay nothing.
- Errors never leave the shell. Unknown theme: the CLI's exact message plus
  the valid-name list. Unknown command or bad argument: one line naming the
  problem and `type help`. Index out of range: `no hit 999 (set has 42)`.
- `back` and `reset` are O(1): the stack holds full `MineSet` copies (hits
  are small strings plus optionals; a 100k-hit root with a ten-deep stack is
  tens of MB, acceptable for a research tool; documented).
- An interrupted enrichment (Ctrl-C) ends the process, as today for any
  command. No signal handling this round.

## Error handling summary

| Situation | Behaviour |
|---|---|
| bad `--max` word | exit 3, message lists `infinity`/`inf` |
| unknown `--theme` on the command line | unchanged: exit 3, valid names |
| enrichment hits a missing table | hit kept, marked unavailable, one stderr note with the `gen` hint |
| saturated solution count during scan | unchanged: skipped, tallied, note on stderr, also in JSON |
| `save` cannot open FILE | shell prints the OS error, stays in the loop |
| `--interactive` with stdin not readable | prompt loop ends at EOF immediately; exit 0 after printing the load summary |

## Testing

Core (`src/core/tests/test_mine_set.cpp`, Catch2 like the existing core tests):

- `add` fills dtm/count from probe; `with_count`, `with_starts`, `with_ends`
  narrow correctly on the KQvk test table.
- `with_theme("mirror")` on KQvk dtm=2 gives 477 of 580 (the number pinned
  by the existing `verify_mine_theme_filters.cmake`); `not` gives 103.
- `theme_histogram` lists every non-parametric registry name exactly once,
  none of the parametric ones, in registry order.
- `to_json` escapes quotes/backslashes/control characters; a hand-built hit
  with an `unavailable` marker serialises as specified.
- Narrowing returns a new set and leaves the source untouched.

CLI (ctest in `src/packages/cli/CMakeLists.txt` and `tests/`):

- `mine KQvk --dtm 2 --max infinity` prints 580 lines; `--max inf` the same.
- `mine KQvk --dtm 2 --max 3 --json --themes --solutions` is valid JSON with
  the documented keys (checked with `python3 -c 'import json,sys; ...'`,
  guarded on `find_program(python3)`; the test is skipped, not failed, without it).
- `mine KQvk --dtm 2 --max 2 --solutions` matches the pinned text layout.
- `mine KQvk --dtm 2 --themes` no longer exits 3.
- A stdin-driven shell session (`theme mirror`, `count 1`, `themes`, `back`,
  `show 1`, `save out.json`, `quit`) produces pinned stdout and a parseable
  `out.json`; a second session checks that `theme nosuchtheme` and `show 0`
  print errors and the loop continues.

Coverage target for the two new units: at least 80 % lines, per project
policy; `make coverage` includes them.

## Docs and release

- USAGE.md: extend the `mine` section with the flags, the JSON keys, the text
  layout, and a new "Interactive mining" subsection with the command table
  and one worked session.
- CHANGELOG.md `[0.18.0]`; VERSION `0.18.0`; `helpmate --version` follows.
- ROADMAP.md: tick the item, note that bindings/API adoption of `MineSet` is
  the follow-up.
