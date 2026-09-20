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
