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
    def dirty_paths(self): return []
    def reset_to_origin_main(self, branch, paths): self._do("reset_to_origin_main", branch)
    def commit_all(self, message): self._do("commit_all", message)
    def push(self, branch): self._do("push", branch)
    def open_pr(self, title, body, branch=None): self._do("open_pr", title); return "https://gh/pr/1"
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


def _forget_merged_prs(hub):
    """After a merge the resume must not depend on the Hub's view of the PR."""
    def gone(num):
        raise AssertionError(f"PR #{num} fetched again after the merge")
    hub.pull_request = gone


def test_accept_resumes_after_ci_failure_without_merging_twice(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at="wait_and_merge"))
    assert hub.merged == [2]
    hub.commit({"manifest.json": hub.main["manifest.json"], "README.md": b"moved"}, "main moves on")
    _forget_merged_prs(hub)
    git = FakeGit()
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert hub.merged == [2]                                     # not merged again
    assert [c[0] for c in git.calls] == ["wait_and_merge", "back"]   # resumes at the docs PR


class ManifestFails(FakeHub):
    def commit(self, files, message):
        if "manifest.json" in files and not getattr(self, "healed", False):
            raise RuntimeError("network")
        super().commit(files, message)


def test_resume_after_merge_records_the_prs_tables(tmp_path):
    checkout, staging, hub0, gh, tables = _setup(tmp_path)
    hub = ManifestFails(dict(hub0.main))
    hub.prs, hub.bases, hub.deletes = hub0.prs, hub0.bases, hub0.deletes
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit())
    assert hub.merged == [2]
    hub.healed = True
    hub.commit({"README.md": b"moved"}, "main moves on after the merge")
    _forget_merged_prs(hub)
    git = FakeGit()
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    reg = json.loads((checkout / "data" / "contributions.json").read_text())
    assert list(reg["tables"]) == ["KRRvkqq"]
    assert (tables / "KRRvkqq.hm").exists()
    msg = next(c[1] for c in git.calls if c[0] == "commit_all")
    assert msg.startswith("Data: 1 table(s)")


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


class FlakyHub(FakeHub):
    def merge(self, num):
        if num == 3 and not getattr(self, "healed", False):
            raise RuntimeError("network")
        super().merge(num)


def _two_prs(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    flaky = FlakyHub(dict(hub.main))
    files = {"KRRvkqr.hm": b"t2", "KRRvkqr.stats.json": b'{"generator_version": "0.20.0", "plane_size": 1, "max_dtm": 9}'}
    flaky.prs, flaky.bases, flaky.deletes = hub.prs, hub.bases, hub.deletes
    flaky.add_pr(3, files, head="h3")
    d = staging / "pr-3"
    (d / "files").mkdir(parents=True)
    for k, v in files.items():
        (d / "files" / k).write_bytes(v)
    (d / "report.json").write_text(json.dumps({"result": "pass", "head": "h3", "pr": 3}))
    return checkout, staging, flaky, gh, tables


def _run2(checkout, staging, hub, gh, tables, git):
    return accept([2, 3], hub=hub, gh=gh, git=git, checkout=checkout, tables=tables,
                  staging=staging, contributor=None, today="2026-10-01")


def test_partial_batch_merge_resumes(tmp_path):
    checkout, staging, hub, gh, tables = _two_prs(tmp_path)
    with pytest.raises(RuntimeError):
        _run2(checkout, staging, hub, gh, tables, FakeGit())
    assert hub.merged == [2]
    hub.healed = True
    assert _run2(checkout, staging, hub, gh, tables, FakeGit()) == 0
    assert hub.merged == [2, 3]
    assert (tables / "KRRvkqr.hm").exists()


@pytest.mark.parametrize("fail_at", ["push", "open_pr"])
def test_docs_failure_before_pr_resumes_without_duplicate_changelog(tmp_path, fail_at):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at=fail_at))
    git = FakeGit()
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert (checkout / "CHANGELOG.md").read_text().count("KRRvkqq contributed by") == 1
    assert ("back", "main") in git.calls and hub.merged == [2]
    names = [c[0] for c in git.calls]
    assert "commit_all" not in names if fail_at == "open_pr" else "push" in names


def test_dirty_unrelated_path_stops_docs_step(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    git = FakeGit()
    git.dirty_paths = lambda: ["src/other.py"]
    assert _run(checkout, staging, hub, gh, tables, git) == 2
    assert "src/other.py" in capsys.readouterr().err


def test_original_branch_survives_a_resume_from_the_data_branch(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at="push"))
    git = FakeGit()
    git.current = lambda: "data/accept-2"
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert ("back", "main") in git.calls


def test_card_uploaded_only_after_docs_pr_merged(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at="wait_and_merge"))
    assert not any("Dataset card" in m for m, _ in hub.commits)
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 0
    assert sum("Dataset card" in m for m, _ in hub.commits) == 1


def test_claim_comment_not_posted_twice_after_rerun(tmp_path):
    checkout, staging, hub, gh, tables = _two_prs(tmp_path)
    (staging / "pr-3" / "files" / "KRRvkqr.hm").write_bytes(b"t2")
    calls = {"n": 0}
    orig = gh.comment

    def flaky(issue, body):
        calls["n"] += 1
        if calls["n"] == 2:
            raise RuntimeError("api")
        orig(issue, body)
    gh.comment = flaky
    hub.healed = True
    with pytest.raises(RuntimeError):
        _run2(checkout, staging, hub, gh, tables, FakeGit())
    gh.comment = orig
    assert _run2(checkout, staging, hub, gh, tables, FakeGit()) == 0
    assert sum("KRRvkqq" in b and b.startswith("Accepted") for _, b in gh.posted) == 1
    assert sum("KRRvkqr" in b and b.startswith("Accepted") for _, b in gh.posted) == 1


def test_missing_or_short_staged_file_stops_before_merging(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    (staging / "pr-2" / "files" / "KRRvkqq.hm").write_bytes(b"tab")
    assert _run(checkout, staging, hub, gh, tables, FakeGit()) == 2
    assert hub.merged == [] and "KRRvkqq.hm" in capsys.readouterr().err


class Runner:
    def __init__(self, checks):
        self.checks, self.calls, self.slept = list(checks), [], 0

    def __call__(self, args, **kw):
        import subprocess
        self.calls.append(args)
        out = ""
        if args[:3] == ["gh", "pr", "view"]:
            out = '{"state": "OPEN"}'
        elif args[:3] == ["gh", "pr", "checks"] and "--watch" not in args:
            out = self.checks.pop(0)
        return subprocess.CompletedProcess(args, 0, out, "")


def test_wait_and_merge_polls_until_checks_are_reported(tmp_path):
    from helpmate_server.contrib.accept import Git
    r = Runner(["no checks reported on the 'x' branch", "no checks reported", "ci pending"])
    g = Git(tmp_path, runner=r, sleep=lambda s: setattr(r, "slept", r.slept + 1))
    g.wait_and_merge("u")
    assert r.slept == 2
    assert r.calls[-2][:4] == ["gh", "pr", "checks", "u"] and "--watch" in r.calls[-2]
    assert r.calls[-1][:3] == ["gh", "pr", "merge"]


def test_wait_and_merge_skips_an_already_merged_pr(tmp_path):
    import subprocess
    from helpmate_server.contrib.accept import Git
    calls = []

    def run(args, **kw):
        calls.append(args)
        return subprocess.CompletedProcess(args, 0, '{"state": "MERGED"}', "")
    Git(tmp_path, runner=run).wait_and_merge("u")
    assert len(calls) == 1


def test_wait_and_merge_gives_up_without_checks(tmp_path):
    from helpmate_server.contrib.accept import Git
    r = Runner(["no checks reported"] * 12)
    with pytest.raises(RuntimeError, match="no checks"):
        Git(tmp_path, runner=r, sleep=lambda s: None).wait_and_merge("u")


def test_open_pr_reuses_an_existing_one(tmp_path):
    import subprocess
    from helpmate_server.contrib.accept import Git

    def run(args, **kw):
        assert "create" not in args
        return subprocess.CompletedProcess(args, 0, '[{"url": "https://gh/pr/9"}]', "")
    assert Git(tmp_path, runner=run).open_pr("t", "b", "br") == "https://gh/pr/9"


def test_first_docs_attempt_with_dirty_listed_path_stops_and_discards_nothing(tmp_path, capsys):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    git = FakeGit()
    answers = iter([True])                          # clean for the merge step, dirty from then on
    git.clean = lambda: next(answers, False)
    git.dirty_paths = lambda: ["CHANGELOG.md"]
    assert _run(checkout, staging, hub, gh, tables, git) == 2
    assert hub.merged == [2]                        # got past the merge step, into docs
    assert "commit or stash" in capsys.readouterr().err
    assert not any(c[0] in ("reset_to_origin_main", "commit_all") for c in git.calls)
    assert "docs_started" not in json.loads(next(staging.glob("accept-*.json")).read_text())


def test_redo_after_docs_started_resets_even_when_listed_paths_are_dirty(tmp_path):
    checkout, staging, hub, gh, tables = _setup(tmp_path)
    with pytest.raises(RuntimeError):
        _run(checkout, staging, hub, gh, tables, FakeGit(fail_at="commit_all"))
    git = FakeGit()
    git.clean = lambda: False                       # leftovers of the failed attempt
    git.dirty_paths = lambda: ["CHANGELOG.md", "docs/MATERIALS.md"]
    assert _run(checkout, staging, hub, gh, tables, git) == 0
    assert any(c[0] == "reset_to_origin_main" for c in git.calls)


def _git_env():
    import os
    return {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_SYSTEM": "/dev/null"}


def _sh(cwd, *args):
    import subprocess
    return subprocess.run(args, cwd=cwd, check=True, capture_output=True, text=True,
                          env=_git_env()).stdout


@pytest.fixture
def clone(tmp_path):
    origin = tmp_path / "origin.git"
    _sh(tmp_path, "git", "init", "-q", "--bare", "-b", "main", str(origin))
    work = tmp_path / "clone"
    _sh(tmp_path, "git", "clone", "-q", str(origin), str(work))
    _sh(work, "git", "config", "user.name", "t")
    _sh(work, "git", "config", "user.email", "t@example.com")
    _sh(work, "git", "config", "commit.gpgsign", "false")
    (work / "docs").mkdir()
    (work / "CHANGELOG.md").write_text("# C\n\n## [Unreleased]\n")
    (work / "docs" / "other.md").write_text("keep\n")
    _sh(work, "git", "add", "-A")
    _sh(work, "git", "commit", "-q", "-m", "init")
    _sh(work, "git", "push", "-q", "-u", "origin", "main")
    return work


def test_real_git_reset_discards_staged_and_untracked_generated_files(clone, monkeypatch):
    from helpmate_server.contrib.accept import Git
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", "/dev/null")
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", "/dev/null")
    (clone / "CHANGELOG.md").write_text("# C\n\n## [Unreleased]\n### Data\n- dup\n")
    _sh(clone, "git", "add", "CHANGELOG.md")                 # staged, as after a failed commit
    (clone / "docs" / "MATERIALS.md").write_text("generated\n")
    (clone / ".all-contributorsrc").write_text("{}")
    _sh(clone, "git", "add", ".all-contributorsrc")           # staged new file
    (clone / "docs" / "other.md").write_text("mine\n")         # unlisted, unstaged edit
    Git(clone).reset_to_origin_main("data/accept-2")
    assert _sh(clone, "git", "rev-parse", "--abbrev-ref", "HEAD").strip() == "data/accept-2"
    assert (clone / "CHANGELOG.md").read_text() == _sh(clone, "git", "show", "origin/main:CHANGELOG.md")
    assert _sh(clone, "git", "diff", "--cached", "--name-only") == ""
    assert not (clone / "docs" / "MATERIALS.md").exists() and not (clone / ".all-contributorsrc").exists()
    assert (clone / "docs" / "other.md").read_text() == "mine\n"   # unrelated edit untouched


def test_real_git_dirty_paths_lets_accept_refuse_unlisted_edits(clone, tmp_path, capsys):
    from helpmate_server.contrib.accept import DOCS_PATHS, Git
    (clone / "docs" / "other.md").write_text("mine\n")
    (clone / "CHANGELOG.md").write_text("changed\n")
    dirty = Git(clone).dirty_paths()
    assert sorted(dirty) == ["CHANGELOG.md", "docs/other.md"]
    assert [d for d in dirty if d not in DOCS_PATHS] == ["docs/other.md"]
