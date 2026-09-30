import json

import pytest

from fakes import FakeGitHub, FakeHub
from helpmate_server.contrib.accept import accept, add_changelog_data, manifest_from_hub


class FakeGit:
    def __init__(self, fail_at=None):
        self.calls, self.fail_at = [], fail_at

    def _do(self, name, *a):
        self.calls.append((name, *a))
        if name == self.fail_at:
            raise RuntimeError(f"{name} failed")

    def clean(self): return True
    def current(self): return "main"
    def start_branch(self, name): self._do("start_branch", name)
    def commit_all(self, message): self._do("commit_all", message)
    def push(self, branch): self._do("push", branch)
    def open_pr(self, title, body): self._do("open_pr", title); return "https://gh/pr/1"
    def wait_and_merge(self, url): self._do("wait_and_merge", url)
    def back(self, ref): self._do("back", ref)


def _setup(tmp_path, head="abc", report_head="abc", result="pass"):
    checkout = tmp_path / "repo"
    (checkout / "data").mkdir(parents=True)
    (checkout / "docs").mkdir()
    (checkout / "data" / "contributions.json").write_text(
        '{"schema":1,"contributors":{},"tables":{}}')
    (checkout / "CHANGELOG.md").write_text("# Changelog\n\n## [Unreleased]\n\n## [0.20.0] - x\n")
    for f in ("README.md", "docs/CONTRIBUTING-TABLES.md", "docs/COOPERATIVE-TABLEBASE.md",
              "docs/hf-dataset-card.md"):
        (checkout / f).write_text("x\n")
    staging = tmp_path / "st"
    d = staging / "pr-2"
    (d / "files").mkdir(parents=True)
    (d / "files" / "KRRvkqq.hm").write_bytes(b"table")
    (d / "files" / "KRRvkqq.stats.json").write_text('{"generator_version": "0.20.0", "plane_size": 1, "max_dtm": 9}')
    (d / "report.json").write_text(json.dumps({"result": result, "head": report_head, "pr": 2}))
    hub = FakeHub({"manifest.json": b'{"schema":1,"generator_version":"0.19.0","files":{}}'})
    hub.add_pr(2, {"KRRvkqq.hm": b"table", "KRRvkqq.stats.json": (d / "files" / "KRRvkqq.stats.json").read_bytes()},
               head=head, description="")
    gh = FakeGitHub([{"number": 39, "title": "claim: KRR", "body": "KRRvk??",
                      "user": {"login": "popeye37"}, "created_at": "2026-09-20T00:00:00Z",
                      "labels": [], "state": "open"}])
    tables = tmp_path / "tb"
    tables.mkdir()
    return checkout, staging, hub, gh, tables


def _run(checkout, staging, hub, gh, tables, git, **kw):
    return accept([2], hub=hub, gh=gh, git=git, checkout=checkout, tables=tables,
                  staging=staging, contributor=kw.get("contributor"), today="2026-10-01")


def test_accept_happy_path(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    git = FakeGit()
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert hub.merged == [2]
    man = json.loads(hub.main["manifest.json"])
    assert "KRRvkqq.hm" in man["files"] and man["generator_version"] == "0.19.0"
    assert (tables / "KRRvkqq.hm").read_bytes() == b"table"
    reg = json.loads((checkout / "data" / "contributions.json").read_text())
    assert reg["tables"]["KRRvkqq"]["contributor"] == "popeye37"
    assert reg["tables"]["KRRvkqq"]["claim"] == 39                 # found via the claims index
    assert "### Data" in (checkout / "CHANGELOG.md").read_text()
    commit_msg = next(c[1] for c in git.calls if c[0] == "commit_all")
    assert "Co-authored-by: popeye37 <1008+popeye37@users.noreply.github.com>" in commit_msg
    assert ("wait_and_merge", "https://gh/pr/1") in git.calls
    assert any(n == 39 and "KRRvkqq" in body for n, body in gh.posted)


def test_accept_refuses_a_pr_changed_after_verification(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path, head="new", report_head="old")
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2
    assert hub.merged == [] and "old" in capsys.readouterr().err


def test_accept_refuses_a_failed_report(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path, result="fail")
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2 and hub.merged == []


def test_accept_resumes_after_ci_failure_without_merging_twice(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at="wait_and_merge"))
    assert hub.merged == [2]
    git = FakeGit()
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert hub.merged == [2]                                     # not merged again
    assert [c[0] for c in git.calls] == ["wait_and_merge", "back"]   # resumes at the docs PR


def test_unknown_contributor_stops_before_merging(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    gh.issues.clear()
    hub.prs[2][0].author = "stranger"
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2
    assert hub.merged == [] and "--contributor" in capsys.readouterr().err


def test_changelog_data_entry_goes_under_unreleased():
    text = "# C\n\n## [Unreleased]\n\n## [0.20.0] - x\n"
    out = add_changelog_data(text, "- KRRvkqq by popeye37")
    assert out.index("### Data") < out.index("## [0.20.0]")
    assert add_changelog_data(out, "- KRRvkqr by popeye37").count("### Data") == 1


def test_manifest_from_hub_hashes_non_lfs_files():
    hub = FakeHub({"a.hm": b"1", "a.stats.json": b"{}", "README.md": b"x"})
    m = manifest_from_hub(hub, "0.19.0")
    assert set(m["files"]) == {"a.hm", "a.stats.json"} and m["schema"] == 1


def test_local_step_moves_only_table_files_not_the_head_marker(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    (staging / "pr-2" / "files" / ".head").write_text("abc")
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 0
    assert not (tables / ".head").exists()
    assert sorted(p.name for p in tables.iterdir()) == ["KRRvkqq.hm", "KRRvkqq.stats.json"]


def test_registry_key_collision_stops_before_merging(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    reg = checkout / "data" / "contributions.json"
    reg.write_text(json.dumps({"schema": 1, "tables": {}, "contributors": {
        "popeye37": {"github": "someone-else", "hf": None, "display": "Other"}}}))
    before = reg.read_text()
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2
    assert hub.merged == [] and "popeye37" in capsys.readouterr().err
    assert reg.read_text() == before


def test_incomplete_tables_dir_stops_before_merging(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    hub.main["manifest.json"] = json.dumps(
        {"schema": 1, "generator_version": "0.19.0", "files": {"Kvk.stats.json": {"size": 1}}}).encode()
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2
    assert hub.merged == [] and "missing" in capsys.readouterr().err


def test_dirty_checkout_stops_before_merging(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    git = FakeGit()
    git.clean = lambda: False
    assert _run(checkout, staging, hub, gh, tables, git) == 2 and hub.merged == []


def test_status_lists_open_prs(tmp_path):
    from helpmate_server.contrib.accept import status
    from helpmate_server.contrib.registry import Registry
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    out = status(hub, gh, Registry.load(checkout / "data" / "contributions.json"), staging, checkout)
    assert "| #2 | popeye37 | KRRvkqq | #39 | pass (stale" not in out
    assert "| #2 | popeye37 | KRRvkqq | #39 | pass |" in out
    hub.prs[2][0].head = "changed"
    out = status(hub, gh, Registry.load(checkout / "data" / "contributions.json"), staging, checkout)
    assert "stale" in out and "since the last DEEPEST refresh" in out
    assert "not verified" in status(hub, gh, Registry.load(checkout / "data" / "contributions.json"),
                                    tmp_path / "empty", checkout)
