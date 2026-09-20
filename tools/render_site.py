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

import html
import json
from typing import Dict, List, Optional


def esc(value) -> str:
    """Every value that reaches HTML goes through here. `None` is empty."""
    return "" if value is None else html.escape(str(value), quote=True)


def page(title: str, body: str, depth: int = 0,
         description: str = "") -> str:
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
        return ("the diagram has no legal last move, so it cannot arise in "
                "a game")
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
        rows.append(
            f"<li><strong>{esc(rec.get('author'))}</strong> — {sources}</li>")
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
             f'moves ({esc(p.get("starts"))} starts, {esc(p.get("ends"))} '
             f'ends).</p>')
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
    cells = "".join(f"<div><dd>{esc(v)}</dd><dt>{esc(k)}</dt></div>" for k, v in
                    rows)
    return f'<dl class="numbers">{cells}</dl>'


def _section(title: str, problems: List[Dict], empty: str,
             offset: int = 0) -> str:
    if not problems:
        return (f"<section><h2>{esc(title)}</h2><p class=\"empty\">"
                f"{esc(empty)}</p></section>")
    body = "".join(problem_html(p, i + offset) for i, p in enumerate(problems,
                                                                      1))
    return f"<section><h2>{esc(title)}</h2>{body}</section>"


def material_page(doc: Dict) -> str:
    s = doc["stats"]
    notes = "".join(f'<p class="note">{esc(n)}</p>' for n in doc.get("notes",
                                                                     []))

    dual_title = "Deepest dual problems"
    if (s["strict_dual_dtm"] is not None and
            s["deepest_dual_dtm"] != s["strict_dual_dtm"]):
        dual_note = (f'<p class="note">Deepest dual with different first and '
                     f'last moves: {stipulation(s["strict_dual_dtm"])}. The '
                     f'deepest dual overall is '
                     f'{stipulation(s["deepest_dual_dtm"])}, where the two '
                     f'solutions share a first or a last move.</p>')
    else:
        dual_note = ""

    considered = ""
    if doc.get("candidates_total", 0) > doc.get("candidates_considered", 0):
        considered = (f'<p class="note">Chosen from the first '
                      f'{_num(doc["candidates_considered"])} of '
                      f'{_num(doc["candidates_total"])} positions at this '
                      f'depth.</p>')

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
                description=(f'The deepest helpmate problems in '
                             f'{doc["material"]}, with their solutions and '
                             f'themes.'))


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
    lede = (f'<p class="lede">{len(themes)} themes across {len(index)} '
            f'materials, {with_table} of which hold a helpmate. The Helpmate '
            f'Analyzer glossary names {GLOSSARY_THEMES} themes; these are the '
            f'ones this engine detects directly from the tables, so the list '
            f'is short by design rather than incomplete.</p>')

    toc = " ".join(f'<a href="#{esc(t)}">{esc(t)}</a>' for t in sorted(themes))
    body = (f'<div class="themes"><h1>Themes</h1>{lede}'
            f'<nav class="toc">{toc}</nav>{"".join(blocks)}</div>')
    return page("Themes", body, depth=0,
                description=("Every theme the helpmate tablebases detect, and "
                             "the deepest problems showing each one."))
