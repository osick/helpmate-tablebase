import json
from datetime import datetime, timezone

from fakes import FakeGitHub, FakeHub
from helpmate_server import tables_cli
from helpmate_server.contrib.registry import Registry
from helpmate_server.contrib.site_status import build_status

NOW = datetime(2026, 10, 1, 5, 17, tzinfo=timezone.utc)
FORM = ("### Materials\n\nKRRvk??\n\n### Hugging Face username\n\npopeye37\n\n"
        "### Name to credit\n\n<b>Pop</b>\n\n### Credit\n\n- [ ] Do not name me in the credits.\n")


def _reg(tmp_path):
    return Registry(tmp_path / "c.json", {
        "contributors": {"T31M": {"github": "T31M", "hf": "T31M", "display": "T31M"},
                         "shy": {"github": "shy", "hf": "shy", "display": "Shy", "anonymous": True}},
        "tables": {"KRBvkqq": {"contributor": "T31M", "hf_pr": 1, "claim": 41, "merged": "x",
                               "generator_version": "0.19.0", "verification": None},
                   "KRBvkqr": {"contributor": "shy", "hf_pr": 9, "claim": None, "merged": "x",
                               "generator_version": "0.19.0", "verification": None}}})


def _setup(tmp_path):
    manifest = {"schema": 1, "files": {f"{m}.hm": {"sha256": "a", "size": 1}
                                       for m in ("KRBvkqq", "KRBvkqr", "KQvk")}}
    hub = FakeHub({"manifest.json": json.dumps(manifest).encode()})
    hub.add_pr(3, {"KRRvkqr.hm": b"x", "KRRvkqr.stats.json": b"{}"}, author="popeye37")
    gh = FakeGitHub([{"number": 39, "title": "claim: KRR", "body": FORM,
                      "user": {"login": "popeye37"}, "created_at": "2026-09-20T00:00:00Z",
                      "labels": [], "state": "open"}])
    return hub, gh, _reg(tmp_path)


def test_states_contributors_and_counts(tmp_path):
    hub, gh, reg = _setup(tmp_path)
    s = build_status(hub, gh, reg, NOW)
    assert s["generated_at"] == "2026-10-01T05:17Z"
    m = s["materials"]
    assert m["KRBvkqq"] == {"state": "done", "contributor": "T31M", "hf_pr": 1, "claim": None}
    assert m["KRBvkqr"]["contributor"] == "anonymous"
    assert m["KQvk"]["state"] == "done" and m["KQvk"]["contributor"] is None
    assert m["KRRvkqr"]["state"] == "in review" and m["KRRvkqr"]["hf_pr"] == 3
    assert m["KRRvkqr"]["contributor"] == "<b>Pop</b>"          # escaped by the site, not here
    assert m["KRRvkrr"] == {"state": "claimed", "contributor": "<b>Pop</b>", "hf_pr": None, "claim": 39}
    assert m["Kvkqqqq"]["state"] == "not needed"
    assert "KQRvkqq" not in m                                   # open -> omitted
    assert sum(s["counts"]["all"].values()) == 1000
    assert sum(s["counts"]["six"].values()) == 715 and s["counts"]["six"]["not needed"] == 70
    names = [c["display"] for c in s["contributors"]]
    assert names == ["T31M", "anonymous"]
    anon = s["contributors"][1]
    assert anon["hf"] is None and anon["github"] is None and anon["anonymous"]
    assert s["contributors"][0] == {"display": "T31M", "hf": "T31M", "github": "T31M",
                                    "anonymous": False, "tables": 1, "six": 1,
                                    "materials": ["KRBvkqq"]}


def test_anonymous_claim_form_hides_the_claimant(tmp_path):
    hub, gh, reg = _setup(tmp_path)
    gh.issues[39]["body"] = FORM.replace("- [ ] Do not", "- [X] Do not")
    s = build_status(hub, gh, reg, NOW)
    assert s["materials"]["KRRvkrr"]["contributor"] == "anonymous"


def test_cli_writes_the_file(tmp_path):
    hub, gh, reg = _setup(tmp_path)
    reg.save()
    out = tmp_path / "status.json"
    rc = tables_cli.main(["site-status", "--out", str(out), "--registry", str(reg.path)],
                         hub_factory=lambda r: hub, gh_factory=lambda r: gh)
    assert rc == 0 and json.loads(out.read_text())["materials"]["KRBvkqq"]["state"] == "done"
