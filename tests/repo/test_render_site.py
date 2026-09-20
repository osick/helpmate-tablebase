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
