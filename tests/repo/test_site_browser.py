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


def _new_page_failing_on_error_responses(browser):
    """A page that fails the test on any 4xx/5xx response.

    This is what catches a wrong assetsUrl: board.js resolves piece sprites
    relative to the document, and a material page one directory down with a
    wrong relative path 404s every sprite while the page still renders a
    perfectly normal-looking, piece-less board. Nothing else notices that.
    """
    page = browser.new_page()
    bad_responses = []

    def on_response(response):
        if response.status >= 400:
            bad_responses.append(f"{response.status} {response.url}")

    page.on("response", on_response)
    return page, bad_responses


def _first_material_with_problems():
    index = json.loads((SITE / "data/index.json").read_text())
    return next(r["material"] for r in index if r["unique"])


def test_material_page_draws_a_board_and_steps_it(server, browser):
    material = _first_material_with_problems()
    page, bad_responses = _new_page_failing_on_error_responses(browser)
    page.goto(f"{server}/material/{material}.html")
    page.wait_for_selector(".board")
    assert page.locator(".problem").count() >= 1
    # cm-chessboard draws squares into the container.
    page.wait_for_selector(".board svg, .board canvas", timeout=5000)
    # The most valuable assertion here: the board actually drew pieces, not
    # just an empty board. A wrong assetsUrl (resolved relative to the
    # document, and a material page lives one directory down from the site
    # root) makes every piece sprite 404 while the page still renders a
    # flawless, piece-less chessboard -- no error visible anywhere else.
    piece_count = page.locator(".board svg use, .board svg image").count()
    assert piece_count > 0, "board drew no pieces -- check assetsUrl in board.js"
    before = page.locator(".board-controls .ply").first.inner_text()
    page.locator('.board-controls button[data-step="1"]').first.click()
    assert page.locator(".board-controls .ply").first.inner_text() != before
    assert not bad_responses, f"4xx/5xx responses: {bad_responses}"
    page.close()


def test_theme_index_links_reach_a_material_page(server, browser):
    page, bad_responses = _new_page_failing_on_error_responses(browser)
    page.goto(f"{server}/themes.html")
    page.wait_for_selector(".theme-block")
    link = page.locator(".theme-problems a").first
    href = link.get_attribute("href")
    link.click()
    page.wait_for_load_state()
    assert href.replace("material/", "") in page.url
    assert not bad_responses, f"4xx/5xx responses: {bad_responses}"
    page.close()


def test_a_marker_material_says_no_helpmate_exists(server, browser):
    index = json.loads((SITE / "data/index.json").read_text())
    marker = next((r["material"] for r in index if not r["has_table"]), None)
    if marker is None:
        pytest.skip("no marker material in the index")
    page, bad_responses = _new_page_failing_on_error_responses(browser)
    page.goto(f"{server}/material/{marker}.html")
    assert "No helpmate exists" in page.content()
    assert not bad_responses, f"4xx/5xx responses: {bad_responses}"
    page.close()


def test_the_spa_still_routes_after_the_nav_change(server, browser):
    page, bad_responses = _new_page_failing_on_error_responses(browser)
    page.goto(f"{server}/index.html#/materials")
    page.wait_for_selector("#materials-table tbody tr")
    assert page.locator("#screen-materials").is_visible()
    assert not bad_responses, f"4xx/5xx responses: {bad_responses}"
    page.close()
