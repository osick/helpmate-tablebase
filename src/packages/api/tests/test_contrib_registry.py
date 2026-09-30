import json
from pathlib import Path

from helpmate_server.contrib.hf import PullRequest
from helpmate_server.contrib.registry import Contributor, Registry, resolve_contributor

REPO_ROOT = Path(__file__).resolve().parents[4]


def _reg(tmp_path):
    p = tmp_path / "c.json"
    p.write_text(json.dumps({"schema": 1, "contributors": {
        "T31M": {"github": "T31M", "hf": "T31M", "display": "T31M"}}, "tables": {}}))
    return Registry.load(p)


def _pr(author="popeye37", description=""):
    return PullRequest(2, "Add", author, "open", description, ["KRRvkqq.hm"], "h", "u")


def test_resolution_order(tmp_path):
    reg = _reg(tmp_path)
    # 1. explicit override wins
    assert resolve_contributor(reg, _pr(), "x", "someone").github == "someone"
    # 2. GitHub: line in the description
    assert resolve_contributor(reg, _pr(description="GitHub: @pop"), "x", None).github == "pop"
    # 3. claim issue author
    c = resolve_contributor(reg, _pr(), "popeye37", None)
    assert (c.github, c.hf) == ("popeye37", "popeye37")
    # 4. registry by HF user
    assert resolve_contributor(reg, _pr(author="T31M"), None, None).key == "T31M"
    # 5. nothing
    assert resolve_contributor(reg, _pr(author="stranger"), None, None) is None


def test_record_and_save_roundtrip(tmp_path):
    reg = _reg(tmp_path)
    reg.add_contributor(Contributor("popeye37", "popeye37", "popeye37", "popeye37"))
    reg.record_table("KRRvkqq", contributor="popeye37", hf_pr=2, claim=39, merged="2026-10-01",
                     generator_version="0.20.0", verification={"result": "pass"})
    reg.save()
    again = Registry.load(reg.path)
    assert again.tables_of("popeye37") == ["KRRvkqq"]
    assert again.by_hf("popeye37").key == "popeye37"


def test_seeded_registry_credits_t31m_with_fifteen_tables():
    reg = Registry.load(REPO_ROOT / "data" / "contributions.json")
    assert len(reg.tables_of("T31M")) == 15
    assert all(reg.tables[m]["hf_pr"] == 1 and reg.tables[m]["claim"] == 41
               for m in reg.tables_of("T31M"))
