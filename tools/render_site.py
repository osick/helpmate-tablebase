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
from pathlib import Path
from typing import Dict, Optional

ROOT = Path(__file__).resolve().parents[1]


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
