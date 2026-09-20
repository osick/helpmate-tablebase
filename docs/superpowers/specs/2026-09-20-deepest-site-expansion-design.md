# Deepest-problem site expansion

**Date:** 2026-09-20
**Status:** approved, not yet implemented

The static showcase shows one problem per material: the deepest position whose
solution is unique. This expands it to as many as six problems per material,
gives every material a page of its own, and adds a theme index across the
whole corpus.

Five requirements, as stated:

- **R1** — up to three positions per material, differing significantly in
  solution and position.
- **R2** — also the deepest problems with exactly two solutions
  (`starts = ends = count = 2`), up to three, same criteria.
- **R3** — every problem carries the themes it shows.
- **R4** — a list of all themes referencing the problems that match them; each
  material page carries its own statistics.
- **R5** — a page per material, plus a main starting page.

## What exists today

`tools/deepest_showcase.py` writes `docs/DEEPEST.json`: one entry per material,
234 of them. It mines nothing. The deepest unique depth comes from the
`uniqueness` map in each `*.stats.json` sidecar (`dtm -> count -> how many`),
which makes the depth exact, and the sidecar's `deepest_unique` list supplies a
sample FEN that is verified by probing before use.

`tools/build_site_data.py` turns that, the puzzle EPD and the sidecars into the
four committed files the site reads: `deepest.json`, `puzzles.json`,
`materials.json`, `corpus.json` (1.27 MB total). The Pages workflow has no
tables, which is why that output is committed.

`site/` is a 55-line hash-routed SPA: `#/` (front), `#/deepest[/MATERIAL]`,
`#/puzzles`, `#/materials`.

## Measurements this design rests on

Taken against the local corpus at `~/tb` on 2026-09-20:

| Question | Answer |
| --- | --- |
| Worst-case full plane scan, 4 GB six-piece table | 30 s |
| Full scan, 74 MB five-piece table | 0.55 s |
| Materials with ≥3 unique positions at the deepest depth | 188 of 234 |
| Materials with exactly 1 / exactly 2 | 21 / 25 |
| `count=2, starts=2, ends=2` at the **deepest** dual depth | empty in 9 of 10 sampled |
| Depth cost of insisting on it | usually 1 ply; 3–7 for KQvk, KPvk |

Total regeneration is therefore tens of minutes, not an overnight run.

`mine --dtm D --count C --themes --solutions --jsonl` returns fen, dtm, count,
starts, ends, themes and the full SAN solutions in one call, so a material costs
about two subprocess invocations rather than a dozen probes. **Its default
`--max` is 10**; the tool must pass `--max` explicitly or it will silently
consider only the first ten candidates.

## The problem R1 actually poses

KQvk has exactly three unique positions at its deepest depth, and they are one
problem wearing three hats:

```
8/8/7k/6Q1/8/8/8/K7 b   Kh7 Kb2 Kh8 Kc3 Kh7 Kd4 Kh8 Ke5 Kh7 Kf6 Kh8 Qg7#
8/7k/8/6Q1/8/8/8/K7 b   Kh8 Kb2 Kh7 Kc3 Kh8 Kd4 Kh7 Ke5 Kh8 Kf6 Kh7 Qg7#
7k/8/8/6Q1/8/8/8/K7 b   Kh7 Kb2 Kh8 Kc3 Kh7 Kd4 Kh8 Ke5 Kh7 Kf6 Kh8 Qg7#
```

The black king shuffles between h6, h7 and h8 while the white king walks up to
the same `Qg7#`. Presenting these as three problems would be a lie of
presentation. Note also that their *theme* sets differ (`set-play` and
`pendulum` appear on some and not others), so themes cannot be the similarity
test.

**Decision: distinct-or-fewer, staying at the deepest depth.** A material that
holds only one real idea shows one problem and says so. The depth claim is
never diluted by topping up from shallower depths.

## Selection

### Unique problems (R1)

1. Read the deepest depth `D` with a `count:1` entry from the sidecar. Exact,
   no scan.
2. `mine <MAT> --dtm D --count 1 --themes --solutions --jsonl --max 500`.
3. Run the picker (below) over the candidates.

### Dual problems (R2)

1. Collect every depth with a `count:2` entry from the sidecar, descending.
2. For each, `mine --dtm D --count 2 --starts 2 --ends 2 --themes --solutions
   --jsonl --max 500`. The first depth that yields a hit is `D2`.
3. Run the same picker.

Record both `D2` and the deepest `count:2` depth overall. The page states the
distinction plainly — "deepest dual with distinct first and last moves: h#4.5
(the deepest dual overall is h#5)" — because those differ for most materials
and a reader comparing against the sidecar deserves to know why.

A material with no `count:2` depth at all, or none satisfying the strict
filter at any depth, ships an empty `duals[]` and a note.

### The picker

Between two candidates:

- `white_line` — the SAN tokens played by **White** alone. Which indices those
  are depends on the side to move in the FEN: with Black to move (even dtm)
  White plays the odd indices, with White to move (odd dtm) the even ones.
- `sol_dist` — Levenshtein distance over the full SAN token lists, normalized
  by the longer list's length.
- `pos_dist` — the number of men not standing on the same square: the symmetric
  difference over `(piece, square)` pairs, halved.

Two candidates are **the same idea** when their `white_line` is identical
**and** `pos_dist <= 1`.

The obvious rule — "`sol_dist` below some threshold" — was tried first and is
wrong. Measured on KQvk's three positions, the pairs 1-2 and 2-3 score
`sol_dist = 0.50`, above any threshold that does not also collapse genuinely
different problems, because the black king shuffles h7/h8 in one order and
h8/h7 in the other. White plays the identical `Kb2 Kc3 Kd4 Ke5 Kf6 Qg7#` in
all three. In a helpmate Black's moves are the cooperative ones; the
composition's content is White's manoeuvre and the mating picture, so White's
line is the signal and the full line is noise.

`pos_dist <= 1` is the necessary guard on the other side: the same white
manoeuvre set up with two or more men elsewhere is a different problem, not a
twin.

Selection is greedy max-min:

1. Seed with the candidate carrying a published attribution in
   `docs/DEEPEST.json`, if any; otherwise the first candidate in scan order.
2. Repeatedly add the candidate whose minimum distance to the already-chosen
   set is largest, where distance between two candidates is
   `max(white_line_dist, pos_dist / men)` — the normalized Levenshtein over
   White's moves, against the fraction of men standing elsewhere.
3. Stop at three, or when the best remaining candidate is the same idea as
   something already chosen.
4. If fewer than three were chosen, append a note naming the reason and the
   number of positions that were collapsed.

**Known limitation.** `--max 500` truncates in scan order for the 40 materials
holding 100+ unique positions at their deepest depth, so the candidate pool is
drawn from one region of the plane rather than sampled across it. 500
candidates is ample for picking three dissimilar ones, but the result is "three
distinct problems", not "the three most distinct problems in the class". The
JSON records `candidates_considered` and `candidates_total` so the claim on the
page stays honest.

## Stage 1 — data (`tools/build_problems.py`)

Needs the corpus. Run by hand, like `deepest_showcase.py` and
`build_site_data.py` today. Output is committed.

`site/data/material/<MAT>.json`:

```json
{
  "material": "KQvk",
  "pieces": 3,
  "stats": {
    "max_dtm": 14,
    "deepest_unique_dtm": 12,
    "unique_at_depth": 3,
    "deepest_dual_dtm": 10,
    "strict_dual_dtm": 7,
    "plane_size": 29568,
    "solvable": 45723,
    "unique": 3064,
    "size_bytes": 71647,
    "saturated_at_max": true,
    "dtm_histogram": {"…dtm": "…how many positions…"}
  },
  "unique": [ { "…problem…" } ],
  "duals":  [ { "…problem…" } ],
  "notes": [
    "Only one distinct idea exists at h#6: 3 positions share a solution."
  ],
  "candidates_considered": 3,
  "candidates_total": 3
}
```

Two fields in that block read alike and are not: `unique` is how many positions
in the whole material have a single optimal solution (3,064 for KQvk, straight
from `materials.json`), while `unique_at_depth` is how many of those sit at
`deepest_unique_dtm` (3 for KQvk). The picker draws only from the latter.

A problem:

```json
{
  "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
  "dtm": 12,
  "stipulation": "h#6",
  "count": 1,
  "starts": 1,
  "ends": 1,
  "themes": ["pure", "model", "ideal", "switchback", "nocapture", "nocheck"],
  "solutions": [
    [ {"san": "Kh7", "uci": "h6h7", "fen": "…"}, … ]
  ],
  "published": [
    {"id": "P0530828", "author": "Niemann, John",
     "sources": ["Schachmatt, No. 427, 13/07/1947", "…"]}
  ],
  "published_by": "Niemann (1947)",
  "quality": {"capture_first": false, "check": false, "legal": true},
  "alternative": {"fen": "…", "solution": "…", "themes": ["…"]}
}
```

Two different mechanisms, which the shapes above make easy to confuse:

- **Attribution is carried over.** `published` (a *list* of
  `{id, author, sources[]}` records), `published_by` and `alternative` are
  copied from `docs/DEEPEST.json` by exact FEN match. That attribution is the
  output of PRs #30–32 and regenerating the showcase must not drop it. A
  problem with no matching row gets nulls — which will be most of them, since
  only 26 of the 234 existing entries are published and problems 2, 3 and every
  dual are new positions.
- **Quality is recomputed.** `quality` is `{capture_first, check, legal}`,
  derived from the FEN and the solution, and `docs/DEEPEST.json` carries it for
  every entry, published or not. Carrying it over would leave it null on the
  ~1,500 new problems, so `build_problems.py` reuses the grader in
  `tools/published_problems.py` (`capture_first` / `check` / `legal`, around
  line 305) and computes it for every problem it emits. `quality_note()` from
  the same module supplies the human-readable caveat the page prints.

Also written:

- `site/data/themes.json` — `{theme: {count, problems: [{material, fen, dtm,
  stipulation, kind}]}}`, where `kind` is `"unique"` or `"dual"`.
- `site/data/index.json` — one slim row per material for the front page and the
  material list: material, pieces, deepest stipulation, problem counts, whether
  a table exists.

### Validation before writing

Every selected problem is re-probed and must report the dtm, count, starts and
ends the entry claims. Every solution is replayed with python-chess and must
end in checkmate — `build_site_data.expand_solution` already raises on an
illegal, ambiguous or non-mating line, and that behaviour is reused unchanged.
A material failing either check is reported and **excluded**, never shipped
with a silently wrong claim. The existing checksum-retry wrapper in
`deepest_showcase.run` is reused for the intermittent zstd read error.

### Marker materials

68 of the 302 tables are markers: material in which no helpmate exists at all.
They get a page stating that, with statistics and no problems. They are not
errors and must not be logged as such.

## Stage 2 — pages (`tools/render_site.py`)

Needs no tables. Reads the committed JSON, writes HTML. Wired into `make site`,
so the Pages workflow regenerates it on every deploy and the generated files
stay out of git (`site/material/` and `site/themes.html` are git-ignored).

- `site/material/<MAT>.html` — 302 pages: statistics block, the unique
  problems, the dual problems, the themes this material shows, notes printed
  verbatim, links to the theme index and back to the front page.
- `site/themes.html` — every theme, its problem count, and each matching
  problem linked to its material page. States plainly that the engine
  implements about 30 of the 295 themes the Helpmate Analyzer glossary names,
  so the list does not read as a gap.
- The front page — corpus totals and entry points: materials by piece count,
  the theme index, the puzzle trainer, the booklet PDF.

**`index.html` remains the SPA shell and the main starting page.** The existing
`#/puzzles`, `#/deepest` and `#/materials` routes are live URLs and keep
working unchanged.

The front view is **not** statically generated. An earlier draft of this spec
said it would be; that was wrong, and planning caught it. `front.js` animates
the deepest six-piece problem on a board on load, stepping it ply by ply on a
timer, and pre-rendering the markup would either kill the animation or leave
two renderers to keep in sync for no gain.

What changes instead is smaller and already half-built:

- The existing `#/materials` screen becomes the directory of the new pages —
  `materials.js` links each row's material to `material/<MAT>.html`. That
  screen already lists all 302 tables with sorting and a piece-count filter,
  so the directory requires a link, not a new view.
- `index.html` gains one nav entry, `Themes`, pointing at `themes.html`. It is
  a plain `href`, not a hash route, because the theme index is a generated
  document rather than a screen.

The generated pages are plain documents; they do not load `app.js`.

Boards render with the vendored cm-chessboard already in `site/vendor`, and
solutions step through `{san, uci, fen}` triples, so the new pages need no
chess logic of their own — the same contract the SPA already relies on.

## Testing

- **Picker unit tests** (`tests/site/test_picker.py`) against synthetic
  candidates, no corpus: the distance metric, the KQvk three-twin collapse, the
  seed preference for a published position, the stop-at-three rule, the note
  text when fewer than three exist, and the descending dual-depth search
  including the no-strict-position case.
- **Renderer golden test** — one fixture material JSON in, expected HTML out,
  covering a normal material, a marker material and a material with notes.
- **Playwright smoke test** (`--no-sandbox`, per the environment's standing
  note): a generated material page and the theme index load, a board appears,
  a solution steps, and the links between the pages resolve.
- `make test-site` and the existing `site/tests/*.test.js` stay green.
- Coverage ≥80% on both new modules.

## Delivery

Two parts, as agreed:

1. **Data pipeline** — R1, R2, R3: `build_problems.py`, the picker, the JSON.
   Verifiable on its own, before any HTML exists.
2. **Pages and indexes** — R4, R5: `render_site.py`, the material pages, the
   theme index, the front page, the Makefile and gitignore wiring.

## Open risks

- **Scan-order bias** in the candidate cap, recorded in the JSON rather than
  hidden (above).
- **Regeneration is manual** and needs the 576 GB corpus. Nothing in CI can
  reproduce stage 1, which is already true of the existing showcase.
- **Page count.** 302 generated pages is a large output for a site that has
  had one. If the theme index or front page proves the more useful entry
  point, some material pages may never be visited; they cost build time, not
  maintenance, since nothing is hand-edited.
