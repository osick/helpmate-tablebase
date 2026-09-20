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
from pathlib import Path

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
