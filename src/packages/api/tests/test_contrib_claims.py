# src/packages/api/tests/test_contrib_claims.py
from datetime import date

from fakes import FakeGitHub, FakeHub
from helpmate_server.contrib.claims import (
    Claim, ClaimIndex, material_status, parse_claim, run_claims,
)
from helpmate_server.contrib.registry import Registry

ISSUE_39 = """Hi Oliver,\n\nI like to contribute to your fantastic project !
I will generate all types of six-piece tablebases\nof the type KRRvk?? in the next weeks/months.\n"""
ISSUE_40 = "I will generate all types of six-piece tablebases\nof the type KQvk??? in the next weeks."
ISSUE_45 = "- KRNvkqq ✔️\n- KRNvkqr ✔️\n- KRNvkpp ✔️\nNeeds a verification pass"


def test_parse_the_live_claims():
    assert len(parse_claim(ISSUE_39)[0]) == 15
    assert len(parse_claim(ISSUE_40)[0]) == 35
    assert parse_claim(ISSUE_45)[0] == ["KRNvkqq", "KRNvkqr", "KRNvkpp"]


def test_strikethrough_releases_a_material():
    claimed, released = parse_claim("KRRvk??\n~~KRRvkpp 🚧~~ handed to T31M")
    assert "KRRvkpp" not in claimed and released == ["KRRvkpp"]


def test_non_materials_are_ignored():
    assert parse_claim("Kvk KQQQQQvk KRBvkqq, and kqvK") == (["KRBvkqq"], [])


def _claim(n, author, text, created="2026-09-20T00:00:00Z"):
    mats, rel = parse_claim(text)
    return Claim(n, author, created, mats, rel, text)


def test_status_precedence(tmp_path):
    from fakes import FakeHub
    hub = FakeHub()
    hub.add_pr(3, {"KRRvkqr.hm": b"x", "KRRvkqr.stats.json": b"{}"})
    reg = Registry(tmp_path / "c.json", {"contributors": {}, "tables": {}})
    idx = ClaimIndex([_claim(39, "popeye37", "KRRvk??")])
    st = material_status({"KRRvkqq"}, {"KRRvkqr": hub.pull_request(3)}, idx, reg)
    assert st["KRRvkqq"].state == "done"
    assert st["KRRvkqr"].state == "in review" and st["KRRvkqr"].hf_pr == 3
    assert st["KRRvkrr"].state == "claimed" and st["KRRvkrr"].claim == 39
    assert st["KQRvkqq"].state == "open"
    assert st["Kvkqqqq"].state == "not needed"
    assert len(st) == 1000


def _gh_issue(n, author, body, created="2026-09-20T00:00:00Z"):
    return {"number": n, "title": f"claim: {n}", "body": body, "user": {"login": author},
            "created_at": created, "labels": [], "state": "open"}


def test_run_claims_posts_one_status_comment_and_edits_it_later(tmp_path):
    hub = FakeHub({"manifest.json": b'{"schema":1,"files":{"KRRvkqq.hm":{"sha256":"a","size":1}}}'})
    gh = FakeGitHub([_gh_issue(39, "popeye37", ISSUE_39)])
    reg = Registry(tmp_path / "c.json", {"contributors": {}, "tables": {}})
    assert run_claims(hub, gh, reg, date(2026, 9, 30)) == 0
    assert len(gh.posted) == 1 and "<!-- contrib-status" in gh.posted[0][1]
    assert "KRRvkqq" in gh.posted[0][1] and "done" in gh.posted[0][1]
    run_claims(hub, gh, reg, date(2026, 10, 1))
    assert gh.edited == []                                    # nothing changed: no edit
    hub.add_pr(3, {"KRRvkqr.hm": b"x", "KRRvkqr.stats.json": b"{}"})
    run_claims(hub, gh, reg, date(2026, 10, 2))
    assert len(gh.posted) == 1 and len(gh.edited) == 1        # edited in place
    assert "in review" in gh.edited[0][1]


def test_overlap_is_a_conflict_first_claim_wins(tmp_path):
    hub = FakeHub()
    gh = FakeGitHub([_gh_issue(39, "popeye37", ISSUE_39),
                     _gh_issue(50, "late", "claim KRRvkpp please")])
    reg = Registry(tmp_path / "c.json", {"contributors": {}, "tables": {}})
    run_claims(hub, gh, reg, date(2026, 9, 30))
    assert "claim-conflict" in gh.labels[50] and "claim-conflict" not in gh.labels[39]


def test_stale_after_21_days_without_author_activity(tmp_path):
    hub = FakeHub()
    gh = FakeGitHub([_gh_issue(40, "popeye37", ISSUE_40, created="2026-09-01T00:00:00Z")])
    reg = Registry(tmp_path / "c.json", {"contributors": {}, "tables": {}})
    # first run records the body; nothing new afterwards
    run_claims(hub, gh, reg, date(2026, 9, 5))
    run_claims(hub, gh, reg, date(2026, 9, 27))
    assert "claim-stale" in gh.labels[40]
    assert 40 not in gh.closed                                  # never closes
