# src/packages/api/tests/test_contrib_verify_pr.py
import json

from fakes import FakeGitHub, FakeHub
from helpmate_server import tables_cli
from helpmate_server.contrib.hf import PullRequest
from helpmate_server.contrib.links import format_links, parse_links
from helpmate_server.contrib.verify import check_pr_hygiene


def test_links_roundtrip_and_legacy_forms():
    assert parse_links(format_links(39, "popeye37")) == (39, "popeye37")
    assert parse_links("see https://github.com/osick/helpmate-tablebase/issues/41") == (41, None)
    assert parse_links("Claim: #45\nGitHub: @T31M") == (45, "T31M")
    assert parse_links("nothing here") == (None, None)


def _pr(files, description="Claim: #39"):
    return PullRequest(2, "Add", "popeye37", "open", description, files, "h", "u")


def test_v1_hygiene():
    ok = check_pr_hygiene(_pr(["KRRvkqq.hm", "KRRvkqq.stats.json"]), {})
    assert ok.status == "pass"
    assert check_pr_hygiene(_pr(["KRRvkqq.hm"]), {}).status == "fail"            # no sidecar
    assert check_pr_hygiene(_pr(["KRRvkqq.hm", "KRRvkqq.stats.json", "manifest.json"]),
                            {}).status == "fail"
    assert check_pr_hygiene(_pr(["KRRvkqq.hm", "KRRvkqq.stats.json"]),
                            {"KRRvkqq.hm": {"sha256": "ab", "size": 1}}).status == "fail"
    assert check_pr_hygiene(_pr(["KRRvkqq.hm", "KRRvkqq.stats.json"], ""), {}).status == "warn"


def _hub_with_kqvk_pr(corpus, description="Claim: osick/helpmate-tablebase#39"):
    """Main has the corpus minus KQvk; PR 2 adds KQvk."""
    main = {p.name: p.read_bytes() for p in corpus.iterdir() if not p.name.startswith("KQvk.")}
    hub = FakeHub(main)
    hub.add_pr(2, {n: (corpus / n).read_bytes() for n in ("KQvk.hm", "KQvk.stats.json")},
               description=description, head="abc123")
    return hub


def _tables_without_kqvk(tmp_path, corpus):
    d = tmp_path / "tb"
    d.mkdir()
    for p in corpus.iterdir():
        if not p.name.startswith("KQvk."):
            (d / p.name).write_bytes(p.read_bytes())
    return d


ARGS = ["--samples", "50", "--oracle-samples", "2", "--seed", "1"]


def test_plan_only_downloads_nothing(tmp_path, compressed_tables, capsys):
    hub = _hub_with_kqvk_pr(compressed_tables)
    rc = tables_cli.main(["verify", "--tables", str(_tables_without_kqvk(tmp_path, compressed_tables)),
                          "--pr", "2", "--staging", str(tmp_path / "st"), "--plan-only"],
                         hub_factory=lambda r: hub, gh_factory=lambda r: FakeGitHub())
    assert rc == 0 and hub.downloads == []
    assert "KQvk.hm" in capsys.readouterr().out


def test_verify_pr_passes_and_posts(tmp_path, compressed_tables):
    hub, gh = _hub_with_kqvk_pr(compressed_tables), FakeGitHub()
    staging = tmp_path / "st"
    rc = tables_cli.main(["verify", "--tables", str(_tables_without_kqvk(tmp_path, compressed_tables)),
                          "--pr", "2", "--staging", str(staging), "--yes", *ARGS],
                         hub_factory=lambda r: hub, gh_factory=lambda r: gh)
    assert rc == 0
    rep = json.loads((staging / "pr-2" / "report.json").read_text())
    assert rep["result"] == "pass" and rep["head"] == "abc123" and rep["pr"] == 2
    assert hub.comments[0][0] == 2 and "passed" in hub.comments[0][1]
    assert gh.posted[0][0] == 39 and "HF PR #2" in gh.posted[0][1]


def test_verify_pr_rerun_skips_downloaded_files(tmp_path, compressed_tables):
    hub = _hub_with_kqvk_pr(compressed_tables)
    tables = _tables_without_kqvk(tmp_path, compressed_tables)
    base = ["verify", "--tables", str(tables), "--pr", "2", "--staging", str(tmp_path / "st"),
            "--yes", "--no-post", *ARGS]
    tables_cli.main(base, hub_factory=lambda r: hub, gh_factory=lambda r: FakeGitHub())
    n = len(hub.downloads)
    tables_cli.main(base, hub_factory=lambda r: hub, gh_factory=lambda r: FakeGitHub())
    assert len(hub.downloads) == n


def test_verify_pr_without_confirmation_stops(tmp_path, compressed_tables, monkeypatch):
    hub = _hub_with_kqvk_pr(compressed_tables)
    monkeypatch.setattr("builtins.input", lambda prompt: "n")
    rc = tables_cli.main(["verify", "--tables", str(_tables_without_kqvk(tmp_path, compressed_tables)),
                          "--pr", "2", "--staging", str(tmp_path / "st")],
                         hub_factory=lambda r: hub, gh_factory=lambda r: FakeGitHub())
    assert rc == 2 and hub.downloads == []


def test_missing_subtable_stops_and_posts_nothing(tmp_path, compressed_tables, capsys):
    """An incomplete maintainer corpus is not the contributor's fault."""
    hub, gh = _hub_with_kqvk_pr(compressed_tables), FakeGitHub()
    empty = tmp_path / "empty"
    empty.mkdir()
    rc = tables_cli.main(["verify", "--tables", str(empty), "--pr", "2",
                          "--staging", str(tmp_path / "st"), "--yes", *ARGS],
                         hub_factory=lambda r: hub, gh_factory=lambda r: gh)
    assert rc == 2
    assert hub.comments == [] and gh.posted == []
    assert capsys.readouterr().err.strip()


class _Lfs:
    def __init__(self, sha):
        self.sha256 = sha


def _rf(path, size, sha=None, blob="b"):
    from huggingface_hub.hf_api import RepoFile
    return RepoFile(path=path, size=size, oid=blob, lfs={"oid": sha, "size": size,
                                                         "pointerSize": 1} if sha else None)


class _Details:
    is_pull_request = True
    title, author, status, diff = "Add", "popeye37", "open", None
    events = [type("E", (), {"type": "comment", "content": "Claim: #39"})()]


class _Api:
    def get_discussion_details(self, *a, **k):
        return _Details()

    def list_repo_refs(self, *a, **k):
        ref = type("R", (), {"ref": "refs/pr/2", "target_commit": "abc"})()
        return type("Refs", (), {"pull_requests": [ref]})()

    def list_repo_tree(self, repo, repo_type=None, revision="main", expand=False):
        base = [_rf("KQvk.hm", 5, "aa"), _rf("manifest.json", 9, blob="m1"),
                _rf(".gitattributes", 1, blob="g" + revision)]
        if revision == "main":
            return base
        return base[:1] + [_rf("manifest.json", 9, blob="m1"), base[2], _rf("KRRvkqq.hm", 7, "bb"),
                           _rf("KRRvkqq.stats.json", 3, blob="s1")]


def test_pull_request_files_fall_back_to_tree_diff_when_diff_is_empty():
    from helpmate_server.contrib.hf import Hub
    pr = Hub("o/d", api=_Api()).pull_request(2)
    assert pr.files == ["KRRvkqq.hm", "KRRvkqq.stats.json"]
    assert pr.materials == ["KRRvkqq"] and pr.head == "abc"
    assert Hub("o/d", api=_Api()).file_sizes([], "refs/pr/2") == {}


def _run_pr(hub, tables, staging, *extra):
    return tables_cli.main(["verify", "--tables", str(tables), "--pr", "2", "--staging",
                            str(staging), "--yes", "--no-post", *ARGS, *extra],
                           hub_factory=lambda r: hub, gh_factory=lambda r: FakeGitHub())


def test_truncated_staged_file_is_redownloaded(tmp_path, compressed_tables):
    hub = _hub_with_kqvk_pr(compressed_tables)
    tables, staging = _tables_without_kqvk(tmp_path, compressed_tables), tmp_path / "st"
    _run_pr(hub, tables, staging)
    n = len(hub.downloads)
    f = staging / "pr-2" / "files" / "KQvk.hm"
    f.write_bytes(f.read_bytes()[:10])
    assert _run_pr(hub, tables, staging) == 0
    assert len(hub.downloads) > n
    assert json.loads((staging / "pr-2" / "report.json").read_text())["result"] == "pass"


def test_new_head_with_same_sizes_is_redownloaded(tmp_path, compressed_tables):
    hub = _hub_with_kqvk_pr(compressed_tables)
    tables, staging = _tables_without_kqvk(tmp_path, compressed_tables), tmp_path / "st"
    _run_pr(hub, tables, staging)
    n = len(hub.downloads)
    pr, files = hub.prs[2]
    pr.head = "h2"
    hub.prs[2] = (pr, files)
    _run_pr(hub, tables, staging)
    assert len(hub.downloads) > n
    assert json.loads((staging / "pr-2" / "report.json").read_text())["head"] == "h2"
    assert (staging / "pr-2" / "files" / ".head").read_text() == "h2"


def test_unsafe_file_name_downloads_nothing_and_fails(tmp_path, compressed_tables):
    hub = FakeHub()
    hub.add_pr(2, {"../evil.hm": b"x", "../evil.stats.json": b"y"}, description="Claim: #39")
    assert _run_pr(hub, tmp_path / "tb", tmp_path / "st") == 1
    assert hub.downloads == []
    rep = json.loads((tmp_path / "st" / "pr-2" / "report.json").read_text())
    assert rep["result"] == "fail"
