# Deepest-site expansion, Part 2: pages and indexes

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the JSON from Part 1 into a page per material, a theme index across the corpus, and the entry points that reach them from the existing front page.

**Architecture:** One generator, `tools/render_site.py`, reads the committed JSON and writes static HTML. It needs no tables and no network, so `make site` runs it and the Pages workflow regenerates on every deploy. The generated files are git-ignored. The existing SPA is untouched apart from two links.

**Tech Stack:** Python 3.9 (`from __future__ import annotations`), `html.escape` and f-strings for templating (no new dependency), pytest, Playwright for the browser smoke test, the vendored cm-chessboard already in `site/vendor`.

**Spec:** `docs/superpowers/specs/2026-09-20-deepest-site-expansion-design.md`

**Depends on:** Part 1 (`docs/superpowers/plans/2026-09-20-deepest-site-expansion-part1-data.md`) must be complete — `site/data/material/*.json`, `site/data/themes.json` and `site/data/index.json` must exist and be committed.

## Global Constraints

- Python floor is **3.9**. `from __future__ import annotations`; `typing.List` / `Dict` / `Optional`, not PEP 604.
- ruff: `line-length = 100`, `select = ["E4","E7","E9","F"]`. `ruff format` is not used.
- **`tools/render_site.py` must import the standard library only.** Not a style preference — a hard constraint. `.github/workflows/pages.yml` runs `make test-site` after `actions/setup-node` and nothing else: there is no `pip install` step, so **python-chess is not available when the site is built in CI**. `make site` now runs this script, so any import that reaches `chess` (directly, or via `tools/published_problems.py`, which does `import chess` at line 72) breaks the Pages deploy. Templating is f-strings plus `html.escape`; Jinja2 is not in `pyproject.toml` and is not being added.
- **Escape every value that reaches HTML.** Material names, theme names and author names all come from JSON; `html.escape` is not optional.
- Tests live in `tests/repo/`, loaded with `importlib.util.spec_from_file_location`.
- Playwright must launch with `args=["--no-sandbox"]` — user namespaces are restricted on this machine.
- Generated output (`site/material/`, `site/themes.html`) is git-ignored and must never be committed.
- Coverage ≥80% on `tools/render_site.py`.

---

### Task 1: The page shell and escaping

**Files:**
- Create: `tools/render_site.py`
- Test: `tests/repo/test_render_site.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `page(title: str, body: str, depth: int = 0, description: str = "") -> str`, `esc(value) -> str`.

- [ ] **Step 1: Write the failing test**

```python
"""tools/render_site.py: the static pages built from the committed JSON.

These pages are generated from data the site owns, but material and author
names still reach HTML as text, so escaping is tested rather than assumed.
"""

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load():
    spec = importlib.util.spec_from_file_location(
        "render_site", ROOT / "tools/render_site.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules["render_site"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_page_is_a_complete_document_with_the_title():
    m = _load()
    html = m.page("KQvk", "<p>hi</p>")
    assert html.startswith("<!doctype html>")
    assert "<title>KQvk" in html
    assert "<p>hi</p>" in html
    assert html.rstrip().endswith("</html>")


def test_page_at_depth_one_reaches_assets_with_dotdot():
    m = _load()
    top = m.page("Themes", "", depth=0)
    nested = m.page("KQvk", "", depth=1)
    assert 'href="css/site.css"' in top
    assert 'href="../css/site.css"' in nested
    assert 'href="index.html"' in top
    assert 'href="../index.html"' in nested


def test_esc_neutralizes_markup_and_quotes():
    m = _load()
    assert m.esc('<b>"x"</b>') == "&lt;b&gt;&quot;x&quot;&lt;/b&gt;"
    assert m.esc(None) == ""
    assert m.esc(12) == "12"


def test_page_carries_the_description_when_given_one():
    m = _load()
    assert 'name="description" content="Deepest helpmates in KQvk"' in m.page(
        "KQvk", "", description="Deepest helpmates in KQvk")
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: collection error — `tools/render_site.py` does not exist.

- [ ] **Step 3: Write the implementation**

```python
"""Render the static pages the showcase serves from committed JSON.

    python3 tools/render_site.py [--data site/data] [--out site]

No tables, no network: everything this reads was produced by
tools/build_problems.py and committed. That is why `make site` runs it on
every build and the output is git-ignored -- it is derived, deterministic and
cheap, so checking it in would swamp diffs with generated markup.

Three kinds of page:

  site/material/<MAT>.html   one per material, 302 of them, including the 68
                             markers -- material in which no helpmate exists
  site/themes.html           every theme, linked to each problem showing it
  (index.html)               untouched; it keeps the SPA and its animated
                             front board, and only gains links into the above

Boards are drawn by the vendored cm-chessboard, and solutions step through the
{san, uci, fen} triples the JSON already carries, so these pages need no chess
logic of their own -- the same contract the SPA relies on.
"""
from __future__ import annotations

import argparse
import html
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

ROOT = Path(__file__).resolve().parents[1]


def esc(value) -> str:
    """Every value that reaches HTML goes through here. `None` is empty."""
    return "" if value is None else html.escape(str(value), quote=True)


def page(title: str, body: str, depth: int = 0, description: str = "") -> str:
    """A complete document. `depth` is how many directories down it sits, so
    a material page can reach the shared css and the front page."""
    up = "../" * depth
    meta = (f'\n<meta name="description" content="{esc(description)}">'
            if description else "")
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · Helpmate tablebases</title>{meta}
<link rel="stylesheet" href="{up}vendor/cm-chessboard/assets/chessboard.css">
<link rel="stylesheet" href="{up}css/site.css">
</head>
<body>
<header>
  <div class="brand">
    <a href="{up}index.html" class="title">Helpmate tablebases</a>
    <span class="tagline">Every solution to every position, precomputed.</span>
  </div>
  <nav aria-label="Screens">
    <a href="{up}index.html#/">About</a>
    <a href="{up}index.html#/deepest">Deepest</a>
    <a href="{up}index.html#/puzzles">Puzzles</a>
    <a href="{up}index.html#/materials">Materials</a>
    <a href="{up}themes.html">Themes</a>
  </nav>
</header>
<main>
{body}
</main>
</body>
</html>
"""
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: 4 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/render_site.py tests/repo/test_render_site.py
git add tools/render_site.py tests/repo/test_render_site.py
git commit -m "render_site: the page shell, with escaping tested not assumed"
```

---

### Task 2: Rendering one problem

**Files:**
- Modify: `tools/render_site.py`
- Test: `tests/repo/test_render_site.py`

**Interfaces:**
- Consumes: `esc` from Task 1.
- Produces: `problem_html(p: dict, n: int) -> str`, `attribution_html(p: dict) -> str`.

A problem dict is what Part 1 wrote: `{fen, dtm, stipulation, count, starts, ends, themes, solutions, published, published_by, quality, alternative}`, where each entry of `solutions` is a list of `{san, uci, fen}`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_render_site.py`:

```python
PROBLEM = {
    "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
    "dtm": 12, "stipulation": "h#6", "count": 1, "starts": 1, "ends": 1,
    "themes": ["pure", "model", "single-piece:black"],
    "solutions": [[
        {"san": "Kh7", "uci": "h6h7", "fen": "8/7k/8/6Q1/8/8/8/K7 w - - 1 2"},
        {"san": "Qg7#", "uci": "g5g7", "fen": "8/6Qk/8/8/8/8/8/K7 b - - 2 2"},
    ]],
    "published": None, "published_by": None,
    "quality": {"capture_first": False, "check": False, "legal": True},
    "alternative": None,
}

DUAL = dict(PROBLEM, count=2, starts=2, ends=2, solutions=[
    PROBLEM["solutions"][0],
    [{"san": "Kh5", "uci": "h6h5", "fen": "8/8/8/6Qk/8/8/8/K7 w - - 1 2"},
     {"san": "Qg6#", "uci": "g5g6", "fen": "8/8/6Q1/7k/8/8/8/K7 b - - 2 2"}],
])

PUBLISHED = dict(PROBLEM,
                 published=[{"id": "P0530828", "author": "Niemann, John",
                             "sources": ["Schachmatt, No. 427, 13/07/1947"]}],
                 published_by="Niemann (1947)")

FLAWED = dict(PROBLEM, quality={"capture_first": True, "check": False, "legal": True})


def test_problem_html_carries_the_fen_and_the_stipulation():
    m = _load()
    out = m.problem_html(PROBLEM, 1)
    assert 'data-fen="8/8/7k/6Q1/8/8/8/K7 b - - 0 1"' in out
    assert "h#6" in out


def test_problem_html_lists_every_theme_linked_to_the_theme_index():
    m = _load()
    out = m.problem_html(PROBLEM, 1)
    assert '../themes.html#single-piece:black' in out
    assert ">pure<" in out and ">model<" in out


def test_problem_html_renders_both_solutions_of_a_dual():
    m = _load()
    out = m.problem_html(DUAL, 1)
    assert out.count('class="solution"') == 2
    assert "Qg7#" in out and "Qg6#" in out


def test_problem_html_embeds_the_plies_as_escaped_json_for_the_board():
    """The JSON rides in an HTML attribute, so its quotes are entity-escaped.

    Asserting the raw `"uci": "g5g7"` here would fail, and the tempting way to
    make that pass is to drop the escaping — which is exactly the bug. The
    browser unescapes `&quot;` when it reads `dataset.plies`, so what must hold
    is that the values survive and the attribute is escaped."""
    m = _load()
    out = m.problem_html(PROBLEM, 1)
    assert "data-plies='" in out
    assert "g5g7" in out and "Qg7#" in out
    assert "&quot;uci&quot;" in out
    # And it must round-trip the way the browser will read it.
    import html as html_mod
    import json as json_mod
    attr = out.split("data-plies='")[1].split("'")[0]
    assert json_mod.loads(html_mod.unescape(attr))[0][1]["uci"] == "g5g7"


def test_attribution_names_the_author_and_source_when_published():
    m = _load()
    out = m.attribution_html(PUBLISHED)
    assert "Niemann (1947)" in out
    assert "Schachmatt, No. 427, 13/07/1947" in out


def test_attribution_is_empty_for_an_unpublished_problem():
    m = _load()
    assert m.attribution_html(PROBLEM).strip() == ""


def test_a_flawed_problem_says_what_is_wrong():
    m = _load()
    out = m.problem_html(FLAWED, 1)
    assert "the solution begins with a capture" in out


def test_author_names_are_escaped():
    m = _load()
    nasty = dict(PROBLEM, published_by='<script>alert(1)</script>',
                 published=[{"id": "x", "author": "a", "sources": ["s"]}])
    assert "<script>" not in m.attribution_html(nasty)
    assert "&lt;script&gt;" in m.attribution_html(nasty)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_render_site.py -v -k "problem or attribution or author"`
Expected: FAIL — `module 'render_site' has no attribute 'problem_html'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/render_site.py`:

```python
def _quality_note(q: Optional[Dict]) -> str:
    """What is wrong with a problem, in words.

    Deliberately mirrors tools/published_problems.quality_note rather than
    importing it. That module does `import chess` at module scope, and the
    Pages workflow builds this site with node only -- no pip step, so
    python-chess is absent in CI. Importing it here would break the deploy.
    Keep the two wordings in step."""
    if not q:
        return ""
    if not q.get("legal", True):
        return "the diagram has no legal last move, so it cannot arise in a game"
    parts = []
    if q.get("check"):
        parts.append("the side to move is in check in the diagram")
    if q.get("capture_first"):
        parts.append("the solution begins with a capture")
    return "; ".join(parts)


def attribution_html(p: Dict) -> str:
    """Who published this problem, if anyone. Most problems are new positions
    with nothing to show here."""
    if not p.get("published"):
        return ""
    rows = []
    for rec in p["published"]:
        sources = "; ".join(esc(s) for s in rec.get("sources", []))
        rows.append(f"<li><strong>{esc(rec.get('author'))}</strong> — {sources}</li>")
    return (f'<div class="attribution"><p>Published as '
            f'{esc(p.get("published_by"))}</p><ul>{"".join(rows)}</ul></div>')


def problem_html(p: Dict, n: int) -> str:
    """One problem: a board, its solutions, its themes, its caveats.

    The plies ride along as JSON so the page's script can step the board
    without any chess logic -- it sets FENs it was handed."""
    themes = " ".join(
        f'<a class="theme" href="../themes.html#{esc(t)}">{esc(t)}</a>'
        for t in p.get("themes", []))
    solutions = "".join(
        f'<li class="solution">{" ".join(esc(ply["san"]) for ply in line)}</li>'
        for line in p.get("solutions", []))
    note = _quality_note(p.get("quality"))
    caveat = f'<p class="caveat">Note: {esc(note)}.</p>' if note else ""
    plies = json.dumps(p.get("solutions", []))
    duals = ("" if p.get("count", 1) == 1 else
             f'<p class="duals">Two solutions, with different first and last '
             f'moves ({esc(p.get("starts"))} starts, {esc(p.get("ends"))} ends).</p>')
    return f"""<article class="problem" id="problem-{n}">
  <div class="board" data-fen="{esc(p["fen"])}" data-plies='{esc(plies)}'></div>
  <div class="detail">
    <h3>{esc(p["stipulation"])}</h3>
    <p class="fen mono">{esc(p["fen"])}</p>
    {duals}
    <ol class="solutions">{solutions}</ol>
    <p class="themes">{themes}</p>
    {caveat}
    {attribution_html(p)}
  </div>
</article>"""
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: 12 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/render_site.py tests/repo/test_render_site.py
git add tools/render_site.py tests/repo/test_render_site.py
git commit -m "render_site: a problem as a board, its solutions and its caveats"
```

---

### Task 3: The material page

**Files:**
- Modify: `tools/render_site.py`
- Test: `tests/repo/test_render_site.py`

**Interfaces:**
- Consumes: `page`, `problem_html`, `esc`.
- Produces: `stats_html(doc: dict) -> str`, `material_page(doc: dict) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_render_site.py`:

```python
DOC = {
    "material": "KQvk", "pieces": 3,
    "stats": {"max_dtm": 14, "deepest_unique_dtm": 12, "unique_at_depth": 3,
              "deepest_dual_dtm": 10, "strict_dual_dtm": 7, "plane_size": 29568,
              "solvable": 45723, "unique": 3064, "size_bytes": 71647,
              "saturated_at_max": True, "dtm_histogram": {}},
    "unique": [PROBLEM], "duals": [DUAL],
    "notes": ["Only one distinct idea exists at this depth: 3 positions share a solution."],
    "candidates_considered": 3, "candidates_total": 3,
}

MARKER = {
    "material": "Kvk", "pieces": 2,
    "stats": {"max_dtm": None, "deepest_unique_dtm": None, "unique_at_depth": 0,
              "deepest_dual_dtm": None, "strict_dual_dtm": None, "plane_size": 462,
              "solvable": 0, "unique": 0, "size_bytes": 466,
              "saturated_at_max": False, "dtm_histogram": {}},
    "unique": [], "duals": [],
    "notes": ["No helpmate exists in this material."],
    "candidates_considered": 0, "candidates_total": 0,
}


def test_material_page_shows_both_problem_classes():
    m = _load()
    out = m.material_page(DOC)
    assert "KQvk" in out
    assert "Deepest unique" in out and "Deepest dual" in out
    assert out.count('class="problem"') == 2


def test_material_page_prints_the_notes_verbatim():
    m = _load()
    out = m.material_page(DOC)
    assert "Only one distinct idea exists at this depth" in out


def test_material_page_states_both_dual_depths_because_they_differ():
    """The strict dual is usually shallower than the deepest dual; say so."""
    m = _load()
    out = m.material_page(DOC)
    assert "h#3.5" in out          # strict_dual_dtm 7
    assert "h#5" in out            # deepest_dual_dtm 10


def test_marker_material_gets_a_page_saying_no_helpmate_exists():
    m = _load()
    out = m.material_page(MARKER)
    assert "No helpmate exists in this material." in out
    assert 'class="problem"' not in out
    assert out.startswith("<!doctype html>")


def test_stats_html_formats_numbers_with_separators():
    m = _load()
    out = m.stats_html(DOC)
    assert "45,723" in out
    assert "3,064" in out


def test_material_page_links_back_to_the_materials_directory():
    m = _load()
    assert "../index.html#/materials" in m.material_page(DOC)
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_render_site.py -v -k "material or stats_html"`
Expected: FAIL — `module 'render_site' has no attribute 'material_page'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/render_site.py`:

```python
def stipulation(dtm: Optional[int]) -> str:
    """`h#n` from a ply distance. Odd dtm means White to move: the .5 case."""
    if dtm is None:
        return "—"
    return f"h#{dtm // 2}" if dtm % 2 == 0 else f"h#{dtm // 2}.5"


def _num(n) -> str:
    return "—" if n is None else f"{n:,}"


def stats_html(doc: Dict) -> str:
    s = doc["stats"]
    rows = [
        ("longest mate", stipulation(s["max_dtm"])),
        ("deepest unique", stipulation(s["deepest_unique_dtm"])),
        ("positions at that depth", _num(s["unique_at_depth"])),
        ("deepest dual", stipulation(s["deepest_dual_dtm"])),
        ("deepest strict dual", stipulation(s["strict_dual_dtm"])),
        ("positions with a helpmate", _num(s["solvable"])),
        ("with a unique solution", _num(s["unique"])),
        ("cells in the plane", _num(s["plane_size"])),
        ("on disk", _num(s["size_bytes"]) + " bytes"),
    ]
    cells = "".join(f"<div><dd>{esc(v)}</dd><dt>{esc(k)}</dt></div>" for k, v in rows)
    return f'<dl class="numbers">{cells}</dl>'


def _section(title: str, problems: List[Dict], empty: str, offset: int = 0) -> str:
    if not problems:
        return f"<section><h2>{esc(title)}</h2><p class=\"empty\">{esc(empty)}</p></section>"
    body = "".join(problem_html(p, i + offset) for i, p in enumerate(problems, 1))
    return f"<section><h2>{esc(title)}</h2>{body}</section>"


def material_page(doc: Dict) -> str:
    s = doc["stats"]
    notes = "".join(f'<p class="note">{esc(n)}</p>' for n in doc.get("notes", []))

    dual_title = "Deepest dual problems"
    if s["strict_dual_dtm"] is not None and s["deepest_dual_dtm"] != s["strict_dual_dtm"]:
        dual_note = (f'<p class="note">Deepest dual with different first and last '
                     f'moves: {stipulation(s["strict_dual_dtm"])}. The deepest dual '
                     f'overall is {stipulation(s["deepest_dual_dtm"])}, where the two '
                     f'solutions share a first or a last move.</p>')
    else:
        dual_note = ""

    considered = ""
    if doc.get("candidates_total", 0) > doc.get("candidates_considered", 0):
        considered = (f'<p class="note">Chosen from the first '
                      f'{_num(doc["candidates_considered"])} of '
                      f'{_num(doc["candidates_total"])} positions at this depth.</p>')

    body = f"""<div class="material">
  <p class="crumb"><a href="../index.html#/materials">← all materials</a></p>
  <h1>{esc(doc["material"])}</h1>
  <p class="lede">{esc(doc["pieces"])} pieces.</p>
  {stats_html(doc)}
  {notes}
  {_section("Deepest unique problems", doc["unique"],
            "No unique solution exists at any depth in this material.")}
  {considered}
  {dual_note}
  {_section(dual_title, doc["duals"],
            "No position in this material has exactly two solutions "
            "differing in both their first and last move.", offset=10)}
</div>
<script type="module" src="../js/static-board.js"></script>"""
    return page(doc["material"], body, depth=1,
                description=f'The deepest helpmate problems in {doc["material"]}, '
                            f'with their solutions and themes.')
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: 18 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/render_site.py tests/repo/test_render_site.py
git add tools/render_site.py tests/repo/test_render_site.py
git commit -m "render_site: the material page, markers included"
```

---

### Task 4: The theme index

**Files:**
- Modify: `tools/render_site.py`
- Test: `tests/repo/test_render_site.py`

**Interfaces:**
- Consumes: `page`, `esc`, `stipulation`.
- Produces: `themes_page(themes: dict, index: List[dict]) -> str`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_render_site.py`:

```python
THEMES = {
    "model": {"count": 2, "problems": [
        {"material": "KQvk", "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
         "dtm": 12, "stipulation": "h#6", "kind": "unique"},
        {"material": "KRvk", "fen": "8/8/8/8/8/8/8/K1R2k2 b - - 0 1",
         "dtm": 10, "stipulation": "h#5", "kind": "dual"},
    ]},
    "single-piece:black": {"count": 1, "problems": [
        {"material": "KQvk", "fen": "8/8/7k/6Q1/8/8/8/K7 b - - 0 1",
         "dtm": 12, "stipulation": "h#6", "kind": "unique"},
    ]},
}
INDEX = [
    {"material": "KQvk", "pieces": 3, "stipulation": "h#6",
     "unique": 1, "duals": 1, "has_table": True},
    {"material": "Kvk", "pieces": 2, "stipulation": None,
     "unique": 0, "duals": 0, "has_table": False},
]


def test_themes_page_lists_every_theme_with_its_count():
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert ">model<" in out and "2 problems" in out
    assert "single-piece:black" in out and "1 problem<" in out


def test_each_theme_is_an_anchor_a_problem_can_link_to():
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert 'id="model"' in out
    assert 'id="single-piece:black"' in out


def test_theme_entries_link_to_the_material_page():
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert 'href="material/KQvk.html"' in out
    assert 'href="material/KRvk.html"' in out


def test_themes_page_distinguishes_unique_from_dual_problems():
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert "unique" in out and "dual" in out


def test_themes_page_says_how_many_themes_the_engine_implements():
    """295 are named in the glossary; the engine implements far fewer. Saying
    so keeps the short list from reading as a gap."""
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert "295" in out
    assert "2 themes" in out


def test_themes_page_counts_the_materials_it_covers():
    m = _load()
    out = m.themes_page(THEMES, INDEX)
    assert "2 materials" in out
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_render_site.py -v -k theme`
Expected: FAIL — `module 'render_site' has no attribute 'themes_page'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/render_site.py`:

```python
GLOSSARY_THEMES = 295          # named in the Helpmate Analyzer glossary


def themes_page(themes: Dict[str, Dict], index: List[Dict]) -> str:
    """Every theme, and every problem showing it, across the whole corpus."""
    blocks = []
    for name in sorted(themes):
        entry = themes[name]
        n = entry["count"]
        items = "".join(
            f'<li><a href="material/{esc(p["material"])}.html">'
            f'{esc(p["material"])}</a> · {esc(p["stipulation"])} '
            f'<span class="kind">{esc(p["kind"])}</span></li>'
            for p in entry["problems"])
        blocks.append(
            f'<section class="theme-block" id="{esc(name)}">'
            f'<h2>{esc(name)} <span class="count">{n} '
            f'{"problem" if n == 1 else "problems"}</span></h2>'
            f'<ul class="theme-problems">{items}</ul></section>')

    with_table = sum(1 for r in index if r["has_table"])
    lede = (f'<p class="lede">{len(themes)} themes across {len(index)} materials, '
            f'{with_table} of which hold a helpmate. The Helpmate Analyzer glossary '
            f'names {GLOSSARY_THEMES} themes; these are the ones this engine detects '
            f'directly from the tables, so the list is short by design rather than '
            f'incomplete.</p>')

    toc = " ".join(f'<a href="#{esc(t)}">{esc(t)}</a>' for t in sorted(themes))
    body = (f'<div class="themes"><h1>Themes</h1>{lede}'
            f'<nav class="toc">{toc}</nav>{"".join(blocks)}</div>')
    return page("Themes", body, depth=0,
                description="Every theme the helpmate tablebases detect, and the "
                            "deepest problems showing each one.")
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: 24 passed.

- [ ] **Step 5: Lint and commit**

```bash
ruff check tools/render_site.py tests/repo/test_render_site.py
git add tools/render_site.py tests/repo/test_render_site.py
git commit -m "render_site: the corpus-wide theme index"
```

---

### Task 5: The board script for static pages

**Files:**
- Modify: `site/js/board.js` (add an `assetsUrl` option with the current value as its default)
- Create: `site/js/static-board.js`
- Test: `site/tests/static-board.test.js`

**Interfaces:**
- Consumes: `makeBoard` from `site/js/board.js`; the `data-fen` / `data-plies` attributes Task 2 emits.
- Produces: a module that, on load, turns every `.board` into a cm-chessboard and wires a step-through control. Exports `parsePlies(el)` so the parsing is testable without a DOM.

- [ ] **Step 1: Teach `makeBoard` where its assets live**

`site/js/board.js:10` hardcodes `assetsUrl: "vendor/cm-chessboard/assets/"`. That is a **relative** URL with no `<base>` tag in play, so it resolves against the document's own path. It is correct for `index.html` at the site root and wrong for `material/KQvk.html`, where it would resolve to `material/vendor/...` — every piece sprite 404s and every board on all 302 material pages renders empty.

Give the option a seam, keeping the current value as the default so the SPA is untouched:

```javascript
export function makeBoard(el, { input = false, assetsUrl = "vendor/cm-chessboard/assets/" } = {}) {
  const board = new Chessboard(el, {
    position: "8/8/8/8/8/8/8/8",
    assetsUrl,
    style: { borderType: BORDER_TYPE.none },
    extensions: input ? [{ class: PromotionDialog }] : [],
  });
```

Everything else in `makeBoard` stays exactly as it is. `front.js`, `deepest.js` and `puzzles.js` call it without the new option and keep working unchanged.

Then note `makeBoard`'s remaining API — `show(fen, jump)`, `enableInput`, `disableInput` — the material pages use it the same way the SPA screens do, never a second board implementation.

- [ ] **Step 1b: Verify the SPA still works before moving on**

Run: `node --check site/js/board.js && make test-site`
Expected: passes. The default argument means this change is a no-op for every existing caller.

- [ ] **Step 2: Write the failing test**

```javascript
// site/tests/static-board.test.js
import test from "node:test";
import assert from "node:assert/strict";
import { parsePlies } from "../js/static-board.js";

test("parsePlies reads the JSON the renderer embedded", () => {
  const el = { dataset: { plies: JSON.stringify([[{ san: "Qg7#", uci: "g5g7", fen: "8/8" }]]) } };
  const lines = parsePlies(el);
  assert.equal(lines.length, 1);
  assert.equal(lines[0][0].san, "Qg7#");
});

test("parsePlies returns an empty list rather than throwing on bad data", () => {
  assert.deepEqual(parsePlies({ dataset: { plies: "not json" } }), []);
  assert.deepEqual(parsePlies({ dataset: {} }), []);
});
```

- [ ] **Step 3: Run it and verify it fails**

Run: `node --test site/tests/static-board.test.js`
Expected: FAIL — cannot resolve `../js/static-board.js`.

- [ ] **Step 4: Write the implementation**

```javascript
// site/js/static-board.js
// Boards on the generated material pages. The SPA's screens build their own
// boards; these pages have no router and no app.js, so this module does the
// one thing they need: turn every .board the renderer emitted into a board
// that steps through the solutions embedded beside it.
import { makeBoard } from "./board.js";

export function parsePlies(el) {
  try {
    const raw = el.dataset.plies;
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];                       // a malformed attribute shows a static board
  }
}

function wire(el) {
  const fen = el.dataset.fen;
  const lines = parsePlies(el);
  // These pages live one directory down, so the sprites are up a level. The
  // SPA at the site root keeps makeBoard's default.
  const board = makeBoard(el, { assetsUrl: "../vendor/cm-chessboard/assets/" });
  board.show(fen, true);
  if (!lines.length) return;

  const plies = lines[0];
  let ply = 0;
  const controls = document.createElement("div");
  controls.className = "board-controls";
  controls.innerHTML =
    `<button type="button" data-step="-1">‹</button>` +
    `<span class="ply">start</span>` +
    `<button type="button" data-step="1">›</button>`;
  el.after(controls);

  const render = () => {
    board.show(ply === 0 ? fen : plies[ply - 1].fen);
    controls.querySelector(".ply").textContent =
      ply === 0 ? "start" : plies[ply - 1].san;
  };
  controls.addEventListener("click", (ev) => {
    const step = Number(ev.target.dataset.step || 0);
    if (!step) return;
    ply = Math.min(plies.length, Math.max(0, ply + step));
    render();
  });
}

if (typeof document !== "undefined") {
  document.querySelectorAll(".board").forEach(wire);
}
```

- [ ] **Step 5: Run the tests and verify they pass**

Run: `node --test site/tests/static-board.test.js`
Expected: 2 passed.

- [ ] **Step 6: Commit**

```bash
node --check site/js/static-board.js
git add site/js/static-board.js site/tests/static-board.test.js
git commit -m "site: board stepping for the generated material pages"
```

---

### Task 6: The CLI, and wiring it into the build

**Files:**
- Modify: `tools/render_site.py`, `Makefile`, `.gitignore`, `site/js/materials.js`, `site/index.html`
- Test: `tests/repo/test_render_site.py`

**Interfaces:**
- Consumes: `material_page`, `themes_page`.
- Produces: `main(argv=None) -> int`.

- [ ] **Step 1: Write the failing test**

Append to `tests/repo/test_render_site.py`:

```python
import json


def test_main_writes_a_page_per_material_and_the_theme_index(tmp_path):
    m = _load()
    data = tmp_path / "data"
    (data / "material").mkdir(parents=True)
    (data / "material" / "KQvk.json").write_text(json.dumps(DOC))
    (data / "material" / "Kvk.json").write_text(json.dumps(MARKER))
    (data / "themes.json").write_text(json.dumps(THEMES))
    (data / "index.json").write_text(json.dumps(INDEX))
    out = tmp_path / "site"
    out.mkdir()

    assert m.main(["--data", str(data), "--out", str(out)]) == 0
    assert (out / "material" / "KQvk.html").exists()
    assert (out / "material" / "Kvk.html").exists()
    assert (out / "themes.html").exists()
    assert "KQvk" in (out / "material" / "KQvk.html").read_text()
    assert "No helpmate exists" in (out / "material" / "Kvk.html").read_text()


def test_main_is_idempotent(tmp_path):
    """make site runs this on every build; a rerun must not append or differ."""
    m = _load()
    data = tmp_path / "data"
    (data / "material").mkdir(parents=True)
    (data / "material" / "KQvk.json").write_text(json.dumps(DOC))
    (data / "themes.json").write_text(json.dumps(THEMES))
    (data / "index.json").write_text(json.dumps(INDEX))
    out = tmp_path / "site"
    out.mkdir()
    m.main(["--data", str(data), "--out", str(out)])
    first = (out / "material" / "KQvk.html").read_text()
    m.main(["--data", str(data), "--out", str(out)])
    assert (out / "material" / "KQvk.html").read_text() == first


def test_main_reports_missing_data_instead_of_writing_half_a_site(tmp_path):
    m = _load()
    data = tmp_path / "data"
    data.mkdir()
    out = tmp_path / "site"
    out.mkdir()
    assert m.main(["--data", str(data), "--out", str(out)]) == 1
```

- [ ] **Step 2: Run the tests and verify they fail**

Run: `python -m pytest tests/repo/test_render_site.py -v -k main`
Expected: FAIL — `module 'render_site' has no attribute 'main'`.

- [ ] **Step 3: Write the implementation**

Append to `tools/render_site.py`:

```python
def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser("render_site")
    ap.add_argument("--data", default="site/data")
    ap.add_argument("--out", default="site")
    a = ap.parse_args(argv)

    data, out = Path(a.data), Path(a.out)
    themes_file, index_file = data / "themes.json", data / "index.json"
    if not themes_file.exists() or not index_file.exists():
        print(f"error: {data} has no themes.json/index.json -- run "
              f"tools/build_problems.py first", file=sys.stderr)
        return 1

    (out / "material").mkdir(parents=True, exist_ok=True)
    written = 0
    for doc_path in sorted((data / "material").glob("*.json")):
        doc = json.loads(doc_path.read_text())
        (out / "material" / f'{doc["material"]}.html').write_text(material_page(doc))
        written += 1

    (out / "themes.html").write_text(
        themes_page(json.loads(themes_file.read_text()),
                    json.loads(index_file.read_text())))
    print(f"rendered {written} material pages and the theme index", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run the tests and verify they pass**

Run: `python -m pytest tests/repo/test_render_site.py -v`
Expected: 27 passed.

- [ ] **Step 5: Ignore the generated output**

Append to `.gitignore`:

```gitignore
# Generated by tools/render_site.py on every `make site` from the committed
# JSON in site/data. Derived, deterministic and cheap to rebuild, so it is not
# committed -- 302 files of generated markup would swamp every diff.
site/material/
site/themes.html
```

- [ ] **Step 6: Wire it into `make site`**

In `Makefile`, extend the `site` target (line 250) so it renders after vendoring:

```make
site:
	rm -rf site/vendor && mkdir -p site/vendor
	cp -r src/packages/web/helpmate_web/static/vendor/cm-chessboard site/vendor/cm-chessboard
	cp src/packages/web/helpmate_web/static/vendor/README.md site/vendor/README.md
	python3 tools/render_site.py --data site/data --out site
```

- [ ] **Step 7: Link the new pages from the SPA**

In `site/js/materials.js`, in `render()`, make the material cell a link:

```javascript
    <td class="mono"><a href="material/${r.material}.html">${r.material}</a></td>
```

In `site/index.html`, add the Themes entry to the nav, after the Materials link:

```html
    <a href="themes.html">Themes</a>
```

- [ ] **Step 8: Verify the whole site assembles and its tests pass**

Run: `make test-site`
Expected: the render line on stderr, then node's tests passing, then every `site/js/*.js` passing `node --check`. Confirm the output exists and is ignored:

```bash
ls site/material | wc -l          # expect 302
git status --porcelain site/      # expect no untracked site/material or themes.html
```

- [ ] **Step 9: Commit**

```bash
ruff check tools/render_site.py tests/repo/test_render_site.py
git add tools/render_site.py tests/repo/test_render_site.py .gitignore Makefile \
        site/js/materials.js site/index.html
git commit -m "render_site: CLI, make site wiring, and links from the SPA"
```

---

### Task 7: Browser smoke test

**Files:**
- Create: `tests/repo/test_site_browser.py`

**Interfaces:**
- Consumes: the generated site from Task 6.
- Produces: nothing other tasks use.

- [ ] **Step 1: Write the test**

```python
"""The generated pages in a real browser.

Everything else about these pages is tested as strings; this is the check that
the strings are a page a browser can actually render -- the board draws, the
step control moves it, and the links between the pages resolve.

Playwright must launch with --no-sandbox here: user namespaces are restricted
on this machine, and chromium will not start without it.
"""

import http.server
import json
import socketserver
import threading
from pathlib import Path

import pytest

playwright_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[2]
SITE = ROOT / "site"


@pytest.fixture(scope="module")
def server():
    if not (SITE / "themes.html").exists():
        pytest.skip("site not built -- run `make site` first")

    handler = lambda *a, **k: http.server.SimpleHTTPRequestHandler(
        *a, directory=str(SITE), **k)
    with socketserver.TCPServer(("127.0.0.1", 0), handler) as httpd:
        thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        thread.start()
        yield f"http://127.0.0.1:{httpd.server_address[1]}"
        httpd.shutdown()


@pytest.fixture(scope="module")
def browser():
    with playwright_api.sync_playwright() as p:
        b = p.chromium.launch(args=["--no-sandbox"])
        yield b
        b.close()


def _first_material_with_problems():
    index = json.loads((SITE / "data/index.json").read_text())
    return next(r["material"] for r in index if r["unique"])


def test_material_page_draws_a_board_and_steps_it(server, browser):
    material = _first_material_with_problems()
    page = browser.new_page()
    page.goto(f"{server}/material/{material}.html")
    page.wait_for_selector(".board")
    assert page.locator(".problem").count() >= 1
    # cm-chessboard draws squares into the container.
    page.wait_for_selector(".board svg, .board canvas", timeout=5000)
    before = page.locator(".board-controls .ply").first.inner_text()
    page.locator('.board-controls button[data-step="1"]').first.click()
    assert page.locator(".board-controls .ply").first.inner_text() != before
    page.close()


def test_theme_index_links_reach_a_material_page(server, browser):
    page = browser.new_page()
    page.goto(f"{server}/themes.html")
    page.wait_for_selector(".theme-block")
    link = page.locator(".theme-problems a").first
    href = link.get_attribute("href")
    link.click()
    page.wait_for_load_state()
    assert href.replace("material/", "") in page.url
    page.close()


def test_a_marker_material_says_no_helpmate_exists(server, browser):
    index = json.loads((SITE / "data/index.json").read_text())
    marker = next((r["material"] for r in index if not r["has_table"]), None)
    if marker is None:
        pytest.skip("no marker material in the index")
    page = browser.new_page()
    page.goto(f"{server}/material/{marker}.html")
    assert "No helpmate exists" in page.content()
    page.close()


def test_the_spa_still_routes_after_the_nav_change(server, browser):
    page = browser.new_page()
    page.goto(f"{server}/index.html#/materials")
    page.wait_for_selector("#materials-table tbody tr")
    assert page.locator("#screen-materials").is_visible()
    page.close()
```

- [ ] **Step 2: Install the driver if it is missing**

Run: `python3 -c "import playwright" || pip install playwright`
Then: `python3 -m playwright install chromium` (only if chromium is not already cached in `~/.cache/ms-playwright`).

- [ ] **Step 3: Build the site and run the browser tests**

Run: `make site && python -m pytest tests/repo/test_site_browser.py -v`
Expected: 4 passed. A skip means the site was not built — run `make site` first, do not mark the task done on a skip.

- [ ] **Step 4: Run the whole repo suite and commit**

```bash
make test-repo
make test-site
git add tests/repo/test_site_browser.py
git commit -m "test: the generated pages in a real browser"
```

---

### Task 8: Documentation and the pull request

**Files:**
- Modify: `docs/BUILD.md`, `README.md`, `CHANGELOG.md`

- [ ] **Step 1: Document the two-stage pipeline in `docs/BUILD.md`**

Add a section covering: `make site-data` (Part 1, needs a corpus, 20–40 minutes, output committed) then `make site` (Part 2, no corpus, runs on every build, output git-ignored). State plainly that a contributor editing page markup never needs the corpus.

- [ ] **Step 2: Point `README.md` at the new pages**

In the paragraph describing the static showcase (around line 82, "**Or on a board:**"), add that every material now has a page of its own and that there is a theme index, with the live URLs
`osick.github.io/helpmate-tablebase/material/KQvk.html` and
`osick.github.io/helpmate-tablebase/themes.html`.

- [ ] **Step 3: Add a CHANGELOG entry**

Under the unreleased heading, describe: up to three deepest unique problems and up to three deepest strict-dual problems per material, themes on every problem, a page per material including the 68 markers, and a corpus-wide theme index.

- [ ] **Step 4: Verify everything one last time**

```bash
make test-repo && make test-site && ruff check tools/ tests/repo/
```
Expected: all green.

- [ ] **Step 5: Commit and open the pull request**

```bash
git add docs/BUILD.md README.md CHANGELOG.md
git commit -m "docs: the two-stage site pipeline, material pages and theme index"
git push -u origin feature/deepest-site-expansion
gh pr create --title "Per-material pages, deepest duals, and a theme index" --body "..."
```

The PR body must state what a reviewer cannot see from the diff: that
`site/material/` and `site/themes.html` are generated and ignored by design,
that `site/data/` is committed because the Pages workflow has no tables, and
what the strict dual filter costs in depth.

---

## Self-review

**Spec coverage.** R4 → Task 4 (theme index with references) and Task 3 (`stats_html` per material). R5 → Task 3 (material page), Task 6 (CLI writes all 302, SPA links). Markers get pages → Task 3 and Task 7. `index.html` stays the SPA shell, front view untouched → Task 6 Step 7 changes only the nav and one table cell. Generated output git-ignored → Task 6 Step 5. Boards need no chess logic → Task 5 steps `{san, uci, fen}` triples. Playwright with `--no-sandbox` → Task 7.

**Deliberate deviation from the spec, already folded back into it:** the spec's first draft said the front view would be statically generated. `front.js` animates the deepest six-piece problem on a timer, so pre-rendering it would kill the animation or duplicate the renderer. The spec now says the front view stays dynamic and the Materials screen becomes the directory.

**Known gap, deliberate and forced:** `_quality_note` in Task 2 duplicates the wording of `quality_note` in `tools/published_problems.py` rather than importing it. That module does `import chess` at module scope (line 72), and `.github/workflows/pages.yml` builds the site with `actions/setup-node` and no pip step — python-chess is simply not there in CI. Since `make site` now runs the renderer, importing it would break the Pages deploy. The duplication is the cheaper of two bad options; keep the two wordings in step, and if a third caller appears, extract the wording into a dependency-free module rather than copying it again.

**Defect found in pre-flight and corrected:** Task 2's original test asserted the raw `'"uci": "g5g7"'` appeared in the output. It does not — the JSON rides in an HTML attribute and `html.escape` turns its quotes into `&quot;`. Left as written, the obvious way to make that test pass is to drop the escaping, which is the actual bug. The test now asserts the attribute is escaped *and* round-trips through `html.unescape` + `json.loads` the way the browser reads it.

**Placeholder scan:** none. Every code step carries real code. Task 8's PR body is described by what it must contain rather than quoted, which is a writing instruction, not a deferred decision.

**Type consistency:** `page(title, body, depth, description)` defined Task 1, used Tasks 3 and 4. `problem_html(p, n)` defined Task 2, used Task 3 via `_section`. `esc` defined Task 1, used throughout. `stipulation(dtm)` defined Task 3, used Tasks 3 and 4 — note it duplicates the identically-named helper in `tools/build_problems.py`; both are four lines and the renderer must not import the miner, which needs a corpus path to be useful. `material_page(doc)` and `themes_page(themes, index)` defined Tasks 3 and 4, used Task 6. `parsePlies(el)` defined Task 5, consumed by the `data-plies` attribute Task 2 emits.
