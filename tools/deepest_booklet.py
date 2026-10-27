"""Render docs/DEEPEST.json as a LaTeX booklet: docs/DEEPEST.tex.

A print companion to docs/DEEPEST.md: one A5 page per material class with the
deepest problem that has a unique solution. Each page carries the class at a
glance (key figures and a chart of its positions by distance to mate), the
diagram, the solution, the themes, any published problem it matches, and a
link plus QR code that opens the position in the Helpmate Analyzer. A summary
of the whole tablebase and a statistics chapter come first, an index last.

    python3 tools/deepest_booklet.py --data docs/DEEPEST.json [--lang de]
    lualatex -output-directory=... docs/DEEPEST.tex   (twice: index page refs)

`--lang de` or `--lang fr` writes the German or French booklet
(docs/DEEPEST_de.tex, docs/DEEPEST_fr.tex); the words live in
tools/deepest_booklet_text.py.

Needs LuaLaTeX with the Source Serif Pro and Linux Biolinum O fonts, and the
`chessboard`, `tcolorbox`, `pgfplots` and `qrcode` packages (TeX Live).
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from itertools import combinations_with_replacement
from pathlib import Path
from statistics import mean, median

sys.path.insert(0, str(Path(__file__).resolve().parent))

from deepest_booklet_text import LANGS, MAINTAINER, TEXT, fill  # noqa: E402
from deepest_lib import (  # noqa: E402
    helpman_url, hn, numbers, ordered, piece_counts, tex_escape,
)

ROOT = Path(__file__).resolve().parent.parent

CHAPTERS = {
    3: "Three men",
    4: "Four men",
    5: "Five men",
    6: "Six men",
}

OFFICERS = "QRBNP"

FIGURINE = {"K": r"\symking{}", "Q": r"\symqueen{}", "R": r"\symrook{}",
            "B": r"\symbishop{}", "N": r"\symknight{}"}


def out_path(lang: str) -> str:
    """docs/DEEPEST.tex for English, docs/DEEPEST_de.tex and so on for the others."""
    return "docs/DEEPEST.tex" if lang == "en" else f"docs/DEEPEST_{lang}.tex"


def multisets(n: int) -> int:
    """How many unordered selections of n officers there are, repeats allowed."""
    return len(list(combinations_with_replacement(OFFICERS, n)))


def possible_classes(pieces: int) -> int:
    """How many material classes exist with this many men on the board.

    Two kings are compulsory; the remaining men are split between the sides,
    each side's share an unordered multiset drawn from Q, R, B, N, P. White
    versus Black is *not* a symmetry here -- White mates, so KRPvkb and
    KBvkrp are different problems -- which is why both orders are counted.
    """
    spare = pieces - 2
    if spare < 0:
        return 0
    total = 0
    for w in range(spare + 1):
        b = spare - w
        total += multisets(w) * multisets(b)
    return total


def mateable_classes(pieces: int) -> int:
    """Of those, the ones that can hold a mate at all.

    A bare white king cannot deliver mate, so every class where White has
    nothing but the king is empty by construction -- there is no problem in
    it to show. Subtracting them turns the raw 715 six-man classes into the
    645 that can hold a problem. (README.md counts progress over all 715: the
    bare-king classes are published as marker tables and count as done there.)
    """
    if pieces < 3:
        return 0
    return possible_classes(pieces) - multisets(pieces - 2)


def statistics(rows: list[dict]) -> dict:
    gaps = [r["max_dtm"] - r["dtm"] for r in rows]
    by_pieces = Counter(r["pieces"] for r in rows)
    covered = {n: by_pieces.get(n, 0) for n in sorted(CHAPTERS)}
    top = max(r["dtm"] for r in rows)
    longest = max(r["max_dtm"] for r in rows)
    return {
        "classes": len(rows),
        "covered": covered,
        "possible": sum(mateable_classes(n) for n in CHAPTERS),
        "combinatorial": sum(possible_classes(n) for n in CHAPTERS),
        "indexed": sum(r["plane_size"] or 0 for r in rows),
        "positions": sum(r.get("positions", 0) for r in rows),
        "helpmates": sum(r.get("helpmates", 0) for r in rows),
        "unique": sum(sum(r.get("unique_hist", {}).values()) for r in rows),
        "deepest": max(rows, key=lambda r: (r["dtm"], r["material"])),
        "record": sorted(r["material"] for r in rows if r["dtm"] == top),
        "longest": sorted(r["material"] for r in rows if r["max_dtm"] == longest),
        "longest_dtm": longest,
        "widest": max(rows, key=lambda r: r["max_dtm"] - r["dtm"]),
        "gap_mean": mean(gaps),
        "gap_median": median(gaps),
        "gap_max": max(gaps),
        "saturated": sum(1 for r in rows if r["saturated_at_max"]),
        "singletons": sorted((r for r in rows if r["unique_at_depth"] == 1),
                             key=lambda r: (-r["dtm"], r["material"])),
        "few": sum(1 for r in rows if r["unique_at_depth"] <= 10),
        "published": sum(1 for r in rows if r.get("published")),
        "depth_hist": Counter(r["dtm"] for r in rows),
        "gap_hist": Counter(gaps),
    }


def num(n: int) -> str:
    """A thousands-separated number LaTeX will not break across a line."""
    return f"{n:,}".replace(",", "\\,")


def dec(x: float, spec: str, lang: str = "en") -> str:
    """`x` formatted by `spec`, with the language's decimal mark (`12,3` in German)."""
    return format(x, spec).replace(".", TEXT[lang]["decimal"])


def pct(x: float, lang: str = "en") -> str:
    return dec(x, ".1f", lang) + (r"\%" if lang == "en" else r"\,\%")


def big(n: int, lang: str = "en") -> str:
    """`710 million`, `86.7 thousand`: the size of a class in words. German and
    French count by the long scale, so 10**12 is a Billion / un billion there."""
    for unit, div in zip(TEXT[lang]["big"], (1e12, 1e9, 1e6, 1e3)):
        if n >= div:
            return f"{dec(n / div, '.3g', lang)} {unit}"
    return num(n)


def figurines(san: str) -> str:
    """One SAN move with figurines, promotions included (`d1=N`)."""
    out = tex_escape(san)
    for letter, fig in FIGURINE.items():
        out = out.replace("=" + letter, "=" + fig)
    return FIGURINE[out[0]] + out[1:] if out[:1] in FIGURINE else out


def solution_rows(solution: str, dtm: int) -> list[tuple[int, str, str]]:
    """Move pairs in helpmate order, Black first; White to move (odd dtm) opens `1. ...`."""
    moves = [figurines(m) for m in solution.split()]
    if dtm % 2:
        moves = [r"\ldots"] + moves
    if len(moves) % 2:
        moves.append("")
    return [(i // 2 + 1, moves[i], moves[i + 1]) for i in range(0, len(moves), 2)]


def theme_tags(themes: list[str], lang: str = "en") -> str:
    """Registry slugs as a reader expects them; parametric variants (`promotions:n`,
    `excelsior:white`) are left out, their base theme is already listed."""
    names = TEXT[lang]["themes_map"]
    shown = [names.get(t, t) for t in themes if ":" not in t]
    return (" ".join(rf"\themetag{{{tex_escape(t)}}}" for t in shown)
            or rf"\textit{{{TEXT[lang]['no_themes']}}}")


def contributor_counts(registry: dict | None) -> list[tuple[str, int]]:
    """Tables delivered per contributor, as data/contributions.json records them: a
    table one person delivered twice (a re-run after a fix) counts twice."""
    if not registry:
        return []
    per: Counter = Counter()
    for t in registry.get("tables", {}).values():
        for p in t.get("producers", []):
            per[p["contributor"]] += 1
    names = {k: v.get("display", k) for k, v in registry.get("contributors", {}).items()
             if not v.get("anonymous")}
    return [(names[k], n) for k, n in per.most_common() if k in names]


def bar_chart(hist: Counter, xlabel: str, ylabel: str, key) -> list[str]:
    coords = " ".join(f"({key(k)},{v})" for k, v in sorted(hist.items()))
    top = max(hist.values())
    return [
        r"\begin{center}",
        r"\begin{tikzpicture}",
        r"\begin{axis}[",
        r"  width=0.95\linewidth, height=45mm,",
        r"  ybar, bar width=5pt,",
        rf"  xlabel={{{xlabel}}}, ylabel={{{ylabel}}},",
        r"  ylabel near ticks, xlabel near ticks,",
        rf"  ymin=0, ymax={int(top * 1.15) + 1},",
        r"  tick label style={font=\scriptsize},",
        r"  label style={font=\scriptsize},",
        r"  axis lines=left, enlarge x limits=0.06,",
        r"]",
        r"\addplot[fill=ink!55,draw=none] coordinates {" + coords + "};",
        r"\end{axis}",
        r"\end{tikzpicture}",
        r"\end{center}",
    ]


def class_chart(r: dict, lang: str = "en") -> str:
    """Positions by distance to mate (bars), unique solutions per distance (line, log),
    and this problem's depth (dotted)."""
    hist = {int(k): v for k, v in r.get("dtm_hist", {}).items()}
    uniq = {int(k): v for k, v in r.get("unique_hist", {}).items()}
    if not hist:
        return ""
    t = TEXT[lang]
    peak = max(hist.values())
    billions, millions, thousands = t["chart_units"]
    scale, unit = ((1e9, billions) if peak >= 1e9 else (1e6, millions) if peak >= 1e6
                   else (1e3, thousands) if peak >= 1e3 else (1, ""))
    top = peak / scale * 1.1
    bars = " ".join(f"({d},{hist[d] / scale:.4g})" for d in sorted(hist))
    line = " ".join(f"({d},{uniq[d]})" for d in sorted(uniq))
    xmax = max(hist) + 1
    ylab = f"{t['chart_y']} ({unit})" if unit else t["chart_y"]
    return (
        r"\begin{tikzpicture}"
        rf"\begin{{axis}}[width=72mm,height=42mm,ybar,bar width=1.6pt,xmin=-1,xmax={xmax},"
        rf"ymin=0,ymax={top:.4g},axis y line*=left,axis x line*=bottom,"
        rf"xlabel={{\scriptsize {t['chart_x']}}},ylabel={{\scriptsize {ylab}}},"
        r"tick label style={font=\tiny},label style={font=\scriptsize},enlarge x limits=false,"
        r"ylabel shift=-3pt,xlabel shift=-3pt]"
        r"\addplot[fill=ink!55,draw=none] coordinates {" + bars + "};"
        rf"\draw[densely dotted] (axis cs:{r['dtm']},0) -- (axis cs:{r['dtm']},{top:.4g});"
        r"\end{axis}"
        + (rf"\begin{{axis}}[width=72mm,height=42mm,axis y line*=right,axis x line=none,"
           rf"ymode=log,xmin=-1,xmax={xmax},ylabel={{\scriptsize {t['chart_unique']}}},"
           r"tick label style={font=\tiny},label style={font=\scriptsize},ylabel shift=-3pt]"
           r"\addplot[mark=*,mark size=0.7pt,draw=black,thin] coordinates {" + line + "};"
           r"\end{axis}" if line else "")
        + r"\end{tikzpicture}"
    )


PREAMBLE = r"""\documentclass[a5paper,10pt,twoside,openany,headings=small]{scrbook}

\usepackage[<babel>]{babel}
\usepackage[a5paper,inner=15mm,outer=15mm,top=14mm,bottom=18mm]{geometry}
\usepackage{fontspec}
\setmainfont{Source Serif Pro}[Numbers=Lining]
\setsansfont{Linux Biolinum O}
\usepackage{microtype}
\usepackage{booktabs}
\usepackage{longtable}
\usepackage{array}
\usepackage[most]{tcolorbox}
\usepackage{pgfplots}
\pgfplotsset{compat=1.16}
\usepackage{chessfss}
\usepackage{chessboard}
\usepackage{qrcode}
\usepackage[hidelinks]{hyperref}
\usepackage[automark]{scrlayer-scrpage}

\definecolor{ink}{HTML}{24476B}
\setchessboard{boardfontsize=17pt,labelfontsize=5pt,showmover=false,borderwidth=0.3pt,margin=false}
\addtokomafont{disposition}{\color{ink}}

\clearpairofpagestyles
\ofoot{\sffamily\footnotesize\pagemark}
\ifoot{\sffamily\footnotesize\color{ink}<footer>}
\pagestyle{scrheadings}

\raggedbottom
\setlength{\parindent}{0pt}
\setlength{\parskip}{0.5\baselineskip}
\setcounter{tocdepth}{0}
\setcounter{secnumdepth}{0}
<pgfnumbers>
% A theme as a small tinted tag.
\newcommand{\themetag}[1]{\tcbox[on line,colback=ink!8,colframe=ink!8,boxrule=0pt,arc=1.5pt,
  left=2pt,right=2pt,top=0.5pt,bottom=0.5pt,fontupper=\sffamily\scriptsize\color{ink}]{#1}}
% The diagram, measured so the caption under it can end at its right edge.
\newsavebox{\hmboard}
% A labelled key figure in the statistics column.
\newcommand{\hmfigure}[2]{\textcolor{ink}{\textsc{#1}}\\ #2\\[1mm]}
"""


def front_matter(s: dict, contributors: list[tuple[str, int]], lang: str = "en") -> list[str]:
    t = TEXT[lang]
    f = t["facts"]
    record = ", ".join(s["record"])
    longest = ", ".join(s["longest"])
    credits = t["and"].join(fill(t["credit"], name=name, n=n) for name, n in contributors)
    L = [
        r"\begin{document}",
        r"\frontmatter",
        r"\begin{titlepage}",
        r"\centering\sffamily",
        r"\vspace*{2cm}",
        rf"{{\Huge\bfseries\color{{ink}} {t['title']}\par}}",
        r"\vspace{1.2cm}",
        rf"{{\large {t['subtitle']}\par}}",
        r"\vspace{2cm}",
        rf"{{\large {fill(t['all_classes'], n=s['classes'])}\par}}",
        r"\vfill",
        rf"{{\small {t['generated']}\par}}",
        r"\vspace{1cm}",
        r"\end{titlepage}",
        "",
        rf"\chapter*{{{t['brief_title']}}}",
        rf"\markboth{{{t['brief_title']}}}{{}}",
        rf"\addcontentsline{{toc}}{{chapter}}{{{t['brief_title']}}}",
        "",
    ]
    for para in t["brief"]:
        L += [para, ""]
    L += [
        r"\begin{tcolorbox}[enhanced,colback=ink!5,colframe=ink!5,arc=1.5pt,boxrule=0pt]",
        r"\sffamily\small",
        r"\begin{tabular}{@{}l@{\quad}l@{}}",
        rf"{f['classes']} & {fill(f['classes_v'], n=s['classes'])}\\",
        rf"{f['positions']} & {fill(f['positions_v'], n=big(s['positions'], lang))}\\",
        rf"{f['helpmates']} & {big(s['helpmates'], lang)}\\",
        rf"{f['unique']} & {big(s['unique'], lang)}\\",
        rf"{f['deepest']} & {tex_escape(hn(s['deepest']['dtm']))}: {record}\\",
        rf"{f['longest']} & {tex_escape(hn(s['longest_dtm']))}: {longest}\\",
        rf"{f['published']} & {s['published']}\\",
        r"\end{tabular}",
        r"\end{tcolorbox}",
        "",
        t["built"],
        "",
        rf"\section*{{{t['read_title']}}}",
        "",
    ]
    for para in t["read"]:
        L += [para, ""]
    L += [rf"\section*{{{t['about_title']}}}", ""]
    about = t["about"] if credits else t["about"][:1]
    for para in about:
        L += [fill(para, maintainer=MAINTAINER, who=tex_escape(credits)), ""]
    L += [
        r"\begin{tcolorbox}[enhanced,colback=ink!5,colframe=ink!5,arc=1.5pt,boxrule=0pt]",
        r"\sffamily\small",
        r"\begin{tabular}{@{}l@{\quad}l@{}}",
        rf"{t['maintainer']} & {MAINTAINER} (\texttt{{osick}})\\",
    ]
    if credits:
        L.append(rf"{t['contributors']} & {tex_escape(credits)}\\")
    L += [
        rf"{t['code']} & {{\footnotesize\url{{https://github.com/osick/helpmate-tablebase}}}}\\",
        rf"{t['tables']} & {{\footnotesize\url{{https://huggingface.co/datasets/osick/helpmate-tables}}}}\\",
        r"\end{tabular}",
        r"\end{tcolorbox}",
        "",
        rf"\section*{{{t['prior_title']}}}",
        "",
        t["prior"],
        "",
    ]
    L += [
        r"\tableofcontents",
        r"\mainmatter",
        "",
    ]
    return L


def stats_chapter(rows: list[dict], s: dict, lang: str = "en") -> list[str]:
    t = TEXT[lang]
    deep, wide = s["deepest"], s["widest"]
    L = [
        rf"\chapter{{{t['stats_title']}}}",
        rf"\markboth{{{t['stats_title']}}}{{}}",
        "",
        fill(t["stats_intro"], classes=s["classes"], indexed=num(s["indexed"]),
             deep=tex_escape(hn(deep["dtm"])), mat=deep["material"]),
        "",
        rf"\section{{{t['coverage_title']}}}",
        "",
        fill(t["coverage"], comb=num(s["combinatorial"]),
             bare=num(s["combinatorial"] - s["possible"]), poss=num(s["possible"])),
        "",
        r"\begin{center}",
        r"\begin{tabular}{lrrr}",
        r"\toprule",
        t["coverage_head"],
        r"\midrule",
    ]
    for n in sorted(CHAPTERS):
        have, poss = s["covered"].get(n, 0), mateable_classes(n)
        L.append(rf"{n} & {have} & {num(poss)} & {pct(100 * have / poss, lang)} \\")
    L += [
        r"\midrule",
        rf"{t['total']} & {s['classes']} & {num(s['possible'])} & "
        rf"{pct(100 * s['classes'] / s['possible'], lang)} \\",
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{center}",
        "",
        t["no_page"],
        "",
        rf"\section{{{t['depth_title']}}}",
        "",
        fill(t["depth"], classes=s["classes"]),
    ]
    L += bar_chart(s["depth_hist"], t["depth_x"], t["classes"], lambda d: d / 2)
    L += [
        "",
        rf"\section{{{t['gap_title']}}}",
        "",
        t["gap"],
    ]
    L += bar_chart(s["gap_hist"], t["gap_x"], t["classes"], lambda g: g)
    L += [
        "",
        fill(t["gap_summary"], mean=dec(s["gap_mean"], ".1f", lang),
             median=dec(s["gap_median"], ".0f", lang), max=s["gap_max"], mat=wide["material"],
             maxd=tex_escape(hn(wide["max_dtm"])), d=tex_escape(hn(wide["dtm"]))),
        "",
        rf"\section{{{t['ten_title']}}}",
        "",
        r"\begin{center}",
        r"\begin{tabular}{lrrrr}",
        r"\toprule",
        t["ten_head"],
        r"\midrule",
    ]
    for r in sorted(rows, key=lambda r: (-r["dtm"], r["material"]))[:10]:
        L.append(
            rf"{r['material']} & {tex_escape(hn(r['dtm']))} & "
            rf"{tex_escape(hn(r['max_dtm']))} & "
            rf"{r['max_dtm'] - r['dtm']} & {num(r['unique_at_depth'])} \\"
        )
    L += [
        r"\bottomrule",
        r"\end{tabular}",
        r"\end{center}",
        "",
        rf"\section{{{t['rarity_title']}}}",
        "",
        fill(t["rarity"], n=len(s["singletons"]), few=s["few"]),
        "",
    ]
    names = [rf"{r['material']}~{tex_escape(hn(r['dtm']))}" for r in s["singletons"]]
    L += [r"{\footnotesize", r"\begin{longtable}{lll}", r"\toprule",
          rf"\multicolumn{{3}}{{c}}{{{t['singletons']}}} \\",
          r"\midrule", r"\endhead"]
    for i in range(0, len(names), 3):
        row = names[i:i + 3] + [""] * (3 - len(names[i:i + 3]))
        L.append(" & ".join(row) + r" \\")
    L += [r"\bottomrule", r"\end{longtable}", r"}", ""]
    return L


def quality_note(q: dict | None, lang: str = "en") -> str:
    """What is wrong with a position as a problem, or empty.

    Two other stdlib clones of the English wording exist: tools/render_site.py
    (_quality_note) and tools/render_deepest.py (quality_note, around line
    52). Update all three together; the booklet's own words are in
    deepest_booklet_text.py."""
    if not q:
        return ""
    words = TEXT[lang]["quality"]
    if not q.get("legal", True):
        return words["illegal"]
    parts = []
    if q.get("check"):
        parts.append(words["check"])
    if q.get("capture_first"):
        parts.append(words["capture_first"])
    return "; ".join(parts)


def note_tex(q: dict | None, lang: str = "en") -> str:
    n = quality_note(q, lang)
    return (rf"\par\smallskip{{\footnotesize\textit{{{TEXT[lang]['note']}:}} {tex_escape(n)}.}}"
            if n else "")


def published_tex(r: dict, lang: str = "en") -> str:
    """The box under the solution: every published composition this position matches."""
    t = TEXT[lang]
    pubs = r.get("published") or []
    if not pubs:
        return ""
    board = r["fen"].split()[0]
    items = []
    for p in pubs:
        same = p.get("fen", "").split()[0] == board
        sources = p.get("sources") or []
        src = "; ".join(tex_escape(x) for x in sources[:3]) + (r"; \ldots" if len(sources) > 3 else "")
        stip = f", {tex_escape(p['stipulation'])}" if p.get("stipulation") else ""
        tag = t["this_position"] if same else t["related_position"]
        items.append(rf"\textbf{{{tex_escape(p['author'])}}}{stip}\quad"
                     rf"{{\color{{ink}}\scriptsize {tag}}}\\{{\scriptsize {src or t['source_unknown']}}}")
    body = r"\par\smallskip".join(items)
    return ("\n" r"\begin{tcolorbox}[enhanced,colback=white,colframe=ink!35,arc=1.5pt,"
            r"boxrule=0.4pt,left=3mm,right=3mm,top=1.5mm,bottom=1.5mm]"
            "\n" rf"\textcolor{{ink}}{{\sffamily\textsc{{{t['published']}}}}}\par\smallskip\small "
            + body + "\n" r"\end{tcolorbox}")


def entry(r: dict, n: int, lang: str = "en") -> str:
    """One class, one page: header, the class at a glance, the problem, published, link."""
    t = TEXT[lang]
    w, b = piece_counts(r["fen"])
    stip = tex_escape(hn(r["dtm"]))
    mover = t["white_moves"] if r["dtm"] % 2 else t["black_moves"]
    url = helpman_url(r["fen"], r["dtm"])
    sol = "\n".join(rf"\textbf{{{k}.}} & {bl} & {wh}\\" for k, bl, wh in solution_rows(r["solution"], r["dtm"]))
    u = r["unique_at_depth"]
    figures = (
        rf"\hmfigure{{{t['deepest_unique']}}}{{{{\Large {stip}}}}}"
        rf"\hmfigure{{{t['unique_there']}}}{{{{\Large {num(u)}}} {t['position'] if u == 1 else t['positions']}}}"
        rf"\hmfigure{{{t['longest_mate']}}}{{{{\Large {tex_escape(hn(r['max_dtm']))}}}}}"
        + (rf"\hmfigure{{{t['in_class']}}}{{"
           + fill(t["class_size"], p=big(r["positions"], lang), h=big(r["helpmates"], lang)) + "}"
           if r.get("positions") else "")
    )
    return "\n".join([
        rf"\phantomsection\label{{hm:{r['material']}}}",
        r"\begin{tcolorbox}[enhanced,colback=ink,colframe=ink,arc=0pt,boxrule=0pt,"
        r"left=4mm,right=4mm,top=2.5mm,bottom=2.5mm]",
        rf"\color{{white}}\sffamily{{\LARGE\bfseries {tex_escape(r['material'])}}}\hfill{{\Large {stip}}}\\[0.5mm]",
        rf"{{\small {fill(t['men'], n=r['pieces'])}\quad {mover}}}\hfill"
        rf"{{\small {t['no']}~{n}\qquad\href{{{url}}}{{\color{{white}}\bfseries {t['solve']}\,\ensuremath{{\nearrow}}}}}}",
        r"\end{tcolorbox}",
        r"\vspace{2mm}",
        r"\noindent\begin{minipage}[t]{36mm}\vspace{0pt}\sffamily\small\raggedright",
        figures,
        r"\end{minipage}\hfill",
        rf"\begin{{minipage}}[t]{{80mm}}\vspace{{0pt}}{class_chart(r, lang)}\end{{minipage}}",
        r"\vspace{3mm}",
        "",
        rf"\noindent\begin{{minipage}}[t]{{60mm}}\vspace{{0pt}}\sbox\hmboard{{\chessboard[setfen={r['fen']}]}}"
        r"\usebox\hmboard\\[1mm]",
        rf"\makebox[\wd\hmboard]{{\sffamily\hspace{{3mm}}\textbf{{{stip}}}\hfill({w}+{b})}}\end{{minipage}}\hfill",
        r"\begin{minipage}[t]{52mm}\vspace{0pt}",
        rf"\textcolor{{ink}}{{\sffamily\textsc{{{t['solution']}}}}}\par\smallskip\small",
        r"\begin{tabular}{@{}r@{\enspace}l@{\enspace}l@{}}",
        sol,
        r"\end{tabular}\par\vspace{3mm}",
        rf"\qrcode[height=12mm]{{{url}}}\\{{\sffamily\tiny\color{{ink}}{t['scan']}}}",
        r"\end{minipage}",
        r"\vspace{2mm}",
        "",
        rf"{{\raggedright\noindent\textcolor{{ink}}{{\sffamily\textsc{{{t['themes']}}}}}\enspace "
        rf"{theme_tags(r.get('themes') or [], lang)}"
        + note_tex(r.get("quality"), lang) + r"\par}",
        published_tex(r, lang),
        r"\clearpage",
    ])


def index_appendix(rows: list[dict], lang: str = "en") -> list[str]:
    t = TEXT[lang]
    L = [
        r"\appendix",
        rf"\chapter{{{t['index_title']}}}",
        rf"\markboth{{{t['index_title']}}}{{}}",
        "",
        t["index_intro"],
        "",
        r"{\footnotesize",
        r"\begin{longtable}{lrrrr>{\raggedright\arraybackslash}p{22mm}r}",
        r"\toprule",
        t["index_head"],
        r"\midrule",
        r"\endfirsthead",
        r"\toprule",
        t["index_head"],
        r"\midrule",
        r"\endhead",
        r"\bottomrule",
        r"\endfoot",
    ]
    for r in sorted(rows, key=lambda r: (-r["dtm"], r["material"])):
        L.append(
            rf"{r['material']} & {r['pieces']} & "
            rf"\textbf{{{tex_escape(hn(r['dtm']))}}} & "
            rf"{tex_escape(hn(r['max_dtm']))} & {r['max_dtm'] - r['dtm']} & "
            rf"{tex_escape(r.get('published_by', ''))} & "
            rf"\pageref{{hm:{r['material']}}} \\"
        )
    L += [r"\end{longtable}", r"}", ""]
    return L


def preamble(lang: str = "en") -> str:
    t = TEXT[lang]
    pgf = ("" if t["decimal"] == "." else
           "\\pgfplotsset{every axis/.append style={/pgf/number format/.cd,use comma,1000 sep={\\,}}}\n")
    return fill(PREAMBLE, babel=t["babel"], footer=t["footer"], pgfnumbers=pgf)


def build(rows: list[dict], registry: dict | None = None, lang: str = "en") -> str:
    t = TEXT[lang]
    s = statistics(rows)
    name = Path(out_path(lang)).name
    L = [
        f"% docs/{name} -- generated by tools/deepest_booklet.py --lang {lang}.",
        "% Do not edit: regenerate from docs/DEEPEST.json instead.",
        f"% Build: lualatex {name} (twice -- the index carries page refs).",
        "% Needs Source Serif Pro, Linux Biolinum O, chessboard, tcolorbox, pgfplots, qrcode.",
        "",
        preamble(lang),
    ]
    L += front_matter(s, contributor_counts(registry), lang)
    L += stats_chapter(rows, s, lang)
    nums = numbers(rows)

    for n in sorted(CHAPTERS):
        group = [r for r in ordered(rows) if r["pieces"] == n]
        if not group:
            continue
        title = t["chapters"][n]
        L += [
            rf"\chapter{{{title}}}",
            rf"\markboth{{{title}}}{{}}",
            "",
            fill(t["chapter_intro"], n=len(group), poss=num(mateable_classes(n)), men=n),
            r"\clearpage",
            "",
        ]
        for r in group:
            L.append(entry(r, nums[r["material"]], lang))
        L.append("")

    L += index_appendix(rows, lang)
    L.append(r"\end{document}")
    return "\n".join(L) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--data", default="docs/DEEPEST.json")
    ap.add_argument("--registry", default=str(ROOT / "data" / "contributions.json"))
    ap.add_argument("--lang", choices=LANGS, default="en")
    ap.add_argument("--out", default=None, help="default: docs/DEEPEST.tex, or DEEPEST_<lang>.tex")
    a = ap.parse_args()
    out = a.out or out_path(a.lang)
    rows = json.loads(Path(a.data).read_text())
    reg = Path(a.registry)
    registry = json.loads(reg.read_text()) if reg.exists() else None
    Path(out).write_text(build(rows, registry, a.lang))
    print(f"wrote {out}: {len(rows)} entries ({a.lang})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
