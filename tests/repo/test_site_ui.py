"""The site's Materials and front pages in a real browser, with and without
status.json, at desktop and phone width."""
import functools
import http.server
import json
import shutil
import threading
from pathlib import Path

import pytest

sync_api = pytest.importorskip("playwright.sync_api")
ROOT = Path(__file__).resolve().parents[2]
STATUS = {"generated_at": "2026-10-01T05:17Z",
          "materials": {"KQvkqbb": {"state": "claimed", "contributor": "<i>pop</i>", "hf_pr": None, "claim": 40}},
          "contributors": [{"display": "T31M", "hf": "T31M", "github": "T31M", "anonymous": False,
                            "tables": 30, "six": 30, "materials": []},
                           {"display": "<b>bold</b>", "hf": None, "github": None, "anonymous": False,
                            "tables": 1, "six": 1, "materials": []}],
          "counts": {"six": {"done": 31, "in review": 0, "claimed": 1, "open": 613, "not needed": 70},
                     "all": {}}}


@pytest.fixture(params=[True, False], ids=["with-status", "without-status"])
def site(request, tmp_path):
    if not (ROOT / "site" / "vendor").exists():
        pytest.skip("run `make site` first")
    d = tmp_path / "site"
    shutil.copytree(ROOT / "site", d)
    (d / "data" / "status.json").unlink(missing_ok=True)
    if request.param:
        (d / "data" / "status.json").write_text(json.dumps(STATUS))
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(d))
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_port}/", request.param
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    with sync_api.sync_playwright() as p:
        try:
            b = p.chromium.launch(args=["--no-sandbox"])
        except Exception as exc:  # no browser installed on this machine
            pytest.skip(f"chromium unavailable: {exc}")
        yield b
        b.close()


NO_HSCROLL = "document.documentElement.scrollWidth <= window.innerWidth + 1"


@pytest.mark.parametrize("width", [1280, 390])
def test_materials_page(site, browser, width):
    url, has_status = site
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(url + "#/materials?state=open&prio=1")
    page.wait_for_selector("#materials-table tbody tr")
    assert page.is_visible("#screen-materials")
    assert page.input_value('[data-f="state"]') == "open"
    assert page.input_value('[data-f="prio"]') == "1"
    rows = page.locator("#materials-table tbody tr")
    assert rows.count() > 0
    assert all("P1" in t for t in rows.locator("td:nth-child(3)").all_inner_texts())
    assert ("as of" in page.inner_text("#materials-asof")) == has_status
    options = page.locator('#materials-controls [data-f="contributor"] option').count()
    page.select_option('[data-f="state"]', "all")
    page.fill('[data-f="q"]', "KQvk???")
    assert "q=KQvk" in page.url
    assert page.is_visible("#screen-materials")
    # changing a filter must not re-initialise the screen (that would append
    # the contributor options again)
    assert page.locator('#materials-controls [data-f="contributor"] option').count() == options
    page.select_option('[data-f="prio"]', "all")
    assert page.locator('#materials-controls [data-f="contributor"] option').count() == options
    assert page.locator("#materials-table tbody tr").count() == 35
    if has_status:
        # an HTML-looking name is shown literally and creates no element
        assert page.locator("#materials-table td", has_text="<i>pop</i>").count() == 1
        assert page.locator("#materials-table i").count() == 0
    assert page.evaluate(NO_HSCROLL)
    page.close()


@pytest.mark.parametrize("width", [1280, 390])
def test_front_contributors(site, browser, width):
    url, has_status = site
    page = browser.new_page(viewport={"width": width, "height": 900})
    page.goto(url + "#/")
    page.wait_for_selector("#contrib-progress:not(:empty)")
    assert ("T31M" in page.inner_text("#contrib-cards")) == has_status
    if has_status:
        assert "<b>bold</b>" in page.inner_text("#contrib-cards")
        assert page.locator("#contrib-cards b").count() == 0
    assert "of 645" in page.inner_text("#contrib-progress")
    assert page.evaluate(NO_HSCROLL)
    page.close()
