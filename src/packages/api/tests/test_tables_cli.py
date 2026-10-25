import json
from pathlib import Path
from helpmate_server import tables_cli

class RecorderHub:
    def __init__(self):
        self.uploaded: list[str] = []
        self.store: dict[str, bytes] = {}
        self.commits: list[list[str]] = []      # one entry per commit
    def commit_files(self, paths, message: str) -> None:
        self.commits.append([Path(p).name for p in paths])
        for path in paths:
            self.uploaded.append(Path(path).name)
            self.store[Path(path).name] = Path(path).read_bytes()
    def upload(self, path: Path, repo_id: str) -> None:
        self.commit_files([path], "upload")
    def fetch_manifest(self) -> dict | None:
        if "manifest.json" not in self.store:
            return None
        return json.loads(self.store["manifest.json"])
    def download(self, filename: str, dest_dir: Path) -> Path:
        p = Path(dest_dir) / filename
        p.write_bytes(self.store[filename])
        return p

def seed(d: Path):
    (d / "KQvk.hm").write_bytes(b"\x03" * 24)
    (d / "KQvk.stats.json").write_text('{"material":"KQvk"}')
    (d / "Kvk.hm").write_bytes(b"\x04" * 8)

def test_push_selected_material(tmp_path):
    seed(tmp_path)
    hub = RecorderHub()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--material", "KQvk"], hub_factory=lambda repo: hub)
    assert rc == 0
    assert set(hub.uploaded) == {"KQvk.hm", "KQvk.stats.json", "manifest.json"}
    uploaded_manifest = json.loads(hub.store["manifest.json"])
    assert set(uploaded_manifest["files"]) == {"KQvk.hm", "KQvk.stats.json"}
    assert "Kvk.hm" not in uploaded_manifest["files"]   # never uploaded, not advertised
    local_manifest = json.loads((tmp_path / "manifest.json").read_text())
    assert "Kvk.hm" in local_manifest["files"]          # local manifest covers the whole dir
    assert local_manifest["generator_version"] == "unknown"

def test_push_scoped_merges_with_existing_remote_manifest(tmp_path):
    seed(tmp_path)
    hub = RecorderHub()
    hub.store["manifest.json"] = json.dumps({
        "schema": 1, "generator_version": "old",
        "files": {"KRvk.hm": {"sha256": "deadbeef", "size": 42}},
    }).encode()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--material", "KQvk"], hub_factory=lambda repo: hub)
    assert rc == 0
    uploaded_manifest = json.loads(hub.store["manifest.json"])
    assert uploaded_manifest["files"]["KRvk.hm"] == {"sha256": "deadbeef", "size": 42}
    assert set(uploaded_manifest["files"]) == {"KRvk.hm", "KQvk.hm", "KQvk.stats.json"}

def test_push_all_then_pull_roundtrip(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir(); seed(src)
    hub = RecorderHub()
    assert tables_cli.main(["push", "--tables", str(src), "--repo", "u/ds"],
                           hub_factory=lambda repo: hub) == 0
    assert tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds",
                            "--material", "KQvk"], hub_factory=lambda repo: hub) == 0
    assert (dst / "KQvk.hm").read_bytes() == b"\x03" * 24

def test_pull_rejects_corruption(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir(); seed(src)
    hub = RecorderHub()
    tables_cli.main(["push", "--tables", str(src), "--repo", "u/ds"],
                    hub_factory=lambda repo: hub)
    hub.store["KQvk.hm"] = b"\x05" * 24                     # corrupt in transit
    rc = tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds",
                          "--material", "KQvk"], hub_factory=lambda repo: hub)
    assert rc == 1 and not (dst / "KQvk.hm").exists()

def test_usage_errors():
    assert tables_cli.main([]) == 2
    assert tables_cli.main(["push", "--tables", "/nonexistent", "--repo", "u/ds"]) == 2

class BrokenDownloadHub(RecorderHub):
    def download(self, filename: str, dest_dir: Path) -> Path:
        raise IOError(f"boom: {filename}")

def test_pull_handles_download_error(tmp_path, capsys):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir(); seed(src)
    hub = RecorderHub()
    tables_cli.main(["push", "--tables", str(src), "--repo", "u/ds"],
                    hub_factory=lambda repo: hub)
    broken = BrokenDownloadHub()
    broken.store = hub.store
    rc = tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds",
                          "--material", "KQvk"], hub_factory=lambda repo: broken)
    assert rc == 1
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err

class BrokenManifestHub(RecorderHub):
    def fetch_manifest(self):
        raise IOError("boom")

def test_push_fails_loudly_on_manifest_fetch_error(tmp_path, capsys):
    seed(tmp_path)
    hub = BrokenManifestHub()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--material", "KQvk"], hub_factory=lambda repo: hub)
    assert rc == 1
    assert hub.uploaded == []                # nothing uploaded before the failure
    captured = capsys.readouterr()
    assert "error:" in captured.err
    assert "Traceback" not in captured.err

def test_pull_reports_missing_remote_manifest(tmp_path, capsys):
    hub = RecorderHub()                       # empty store: no manifest.json yet
    rc = tables_cli.main(["pull", "--tables", str(tmp_path), "--repo", "u/ds"],
                         hub_factory=lambda repo: hub)
    assert rc == 1
    captured = capsys.readouterr()
    assert "error: remote has no manifest" in captured.err

def test_pull_defaults_to_all_materials(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir(); seed(src)
    hub = RecorderHub()
    assert tables_cli.main(["push", "--tables", str(src), "--repo", "u/ds"],
                           hub_factory=lambda repo: hub) == 0
    rc = tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds"],
                         hub_factory=lambda repo: hub)
    assert rc == 0
    assert (dst / "KQvk.hm").read_bytes() == b"\x03" * 24
    assert (dst / "KQvk.stats.json").exists()
    assert (dst / "Kvk.hm").read_bytes() == b"\x04" * 8


class PrHub(RecorderHub):
    """A hub that can also open pull requests, for the contributor path."""
    def __init__(self, url="https://huggingface.co/datasets/u/ds/discussions/7"):
        super().__init__()
        self.prs: list[tuple[list[str], str]] = []
        self.url = url
        self.description = None
    def open_pr(self, paths, message, description=""):
        self.prs.append(([Path(p).name for p in paths], message))
        self.description = description
        return self.url

def test_create_pr_opens_one_request_for_the_whole_set(tmp_path, capsys):
    # A table and its sidecar must arrive as ONE pull request. Opening one per
    # file would leave a maintainer merging halves in lockstep.
    seed(tmp_path)
    hub = PrHub()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--material", "KQvk", "--create-pr"],
                         hub_factory=lambda repo: hub)
    assert rc == 0
    assert len(hub.prs) == 1
    files, message = hub.prs[0]
    assert files == ["KQvk.hm", "KQvk.stats.json"]
    assert "KQvk" in message
    assert hub.url in capsys.readouterr().out

def test_create_pr_touches_no_manifest_anywhere(tmp_path):
    # Not the remote one -- the maintainer regenerates it, and a PR editing it
    # would conflict with every other open PR. Not the local one either: a
    # contributor's tables directory is not ours to write into.
    seed(tmp_path)
    hub = PrHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                            "--create-pr"], hub_factory=lambda repo: hub) == 0
    assert hub.uploaded == []                       # nothing written directly
    assert "manifest.json" not in hub.store
    assert not (tmp_path / "manifest.json").exists()
    proposed, _ = hub.prs[0]
    assert "manifest.json" not in proposed

def test_create_pr_without_material_proposes_every_table(tmp_path):
    seed(tmp_path)
    hub = PrHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                            "--create-pr"], hub_factory=lambda repo: hub) == 0
    proposed, _ = hub.prs[0]
    assert set(proposed) == {"KQvk.hm", "KQvk.stats.json", "Kvk.hm"}

def test_create_pr_on_an_empty_directory_is_an_error(tmp_path):
    hub = PrHub()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--create-pr"], hub_factory=lambda repo: hub)
    assert rc == 2
    assert hub.prs == []

def test_create_pr_reports_failure_without_claiming_success(tmp_path, capsys):
    seed(tmp_path)
    class Failing(PrHub):
        def open_pr(self, paths, message, description=""):
            raise OSError("413 payload too large")
    hub = Failing()
    rc = tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                          "--create-pr"], hub_factory=lambda repo: hub)
    assert rc == 1
    assert "413 payload too large" in capsys.readouterr().err

def test_push_without_create_pr_is_unchanged(tmp_path):
    # The default path still writes directly and still maintains the manifest.
    seed(tmp_path)
    hub = PrHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                            "--material", "KQvk"],
                           hub_factory=lambda repo: hub) == 0
    assert hub.prs == []
    assert "manifest.json" in hub.store


def test_push_batches_files_into_few_commits(tmp_path):
    # The Hub caps repository commits at 128/hour. One commit per file made a
    # full-corpus push (295 tables + sidecars) die partway with a 429 that no
    # retry could clear, so the file count and the commit count must decouple.
    for i in range(80):
        (tmp_path / f"K{i}vk.hm").write_bytes(b"\x03" * 8)
        (tmp_path / f"K{i}vk.stats.json").write_text('{"material":"x"}')
    hub = RecorderHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds"],
                           hub_factory=lambda repo: hub) == 0
    assert len(hub.uploaded) == 161            # 80 tables + 80 sidecars + manifest
    assert len(hub.commits) <= 4               # not 161
    assert all(len(c) <= 65 for c in hub.commits)

def test_push_advertises_the_manifest_only_in_the_final_commit(tmp_path):
    # A manifest that landed first would name files not yet uploaded, and a
    # client reading it would 404 on every one of them.
    for i in range(70):
        (tmp_path / f"K{i}vk.hm").write_bytes(b"\x03" * 8)
    hub = RecorderHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds"],
                           hub_factory=lambda repo: hub) == 0
    assert len(hub.commits) > 1                                  # actually chunked
    assert "manifest.json" not in sum(hub.commits[:-1], [])
    assert "manifest.json" in hub.commits[-1]


def test_create_pr_writes_claim_and_github_lines(tmp_path):
    seed(tmp_path)
    hub = PrHub()
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                            "--material", "KQvk", "--create-pr", "--claim", "39",
                            "--github", "popeye37"], hub_factory=lambda repo: hub) == 0
    assert hub.description == "Claim: osick/helpmate-tablebase#39\nGitHub: @popeye37"


def test_claim_without_create_pr_is_a_usage_error(tmp_path, capsys):
    seed(tmp_path)
    assert tables_cli.main(["push", "--tables", str(tmp_path), "--repo", "u/ds",
                            "--claim", "39"], hub_factory=lambda repo: RecorderHub()) == 2


# --- diff and pull --missing ---------------------------------------------------

class CountingHub(RecorderHub):
    def __init__(self):
        super().__init__()
        self.downloads: list[str] = []
    def download(self, filename: str, dest_dir: Path) -> Path:
        self.downloads.append(filename)
        return super().download(filename, dest_dir)

def _published(tmp_path):
    src, dst = tmp_path / "src", tmp_path / "dst"
    src.mkdir(); dst.mkdir(); seed(src)
    hub = CountingHub()
    assert tables_cli.main(["push", "--tables", str(src), "--repo", "u/ds"],
                           hub_factory=lambda repo: hub) == 0
    return src, dst, hub

def _diff(dst, hub, capsys, *extra):
    assert tables_cli.main(["diff", "--tables", str(dst), "--repo", "u/ds", *extra],
                           hub_factory=lambda repo: hub) == 0
    return capsys.readouterr().out

def test_diff_of_an_empty_directory_lists_everything_as_new(tmp_path, capsys):
    _, dst, hub = _published(tmp_path)
    out = _diff(dst, hub, capsys)
    assert "new      KQvk" in out and "new      Kvk" in out
    assert out.splitlines()[-1].startswith("2 new")
    assert hub.downloads == []                      # diff downloads nothing

def test_pull_missing_fetches_only_what_is_new(tmp_path, capsys):
    _, dst, hub = _published(tmp_path)
    assert tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds", "--material", "KQvk"],
                           hub_factory=lambda repo: hub) == 0
    hub.downloads.clear()
    assert tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds", "--missing"],
                           hub_factory=lambda repo: hub) == 0
    assert hub.downloads == ["Kvk.hm"]              # KQvk is already here
    hub.downloads.clear()
    assert tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds", "--missing"],
                           hub_factory=lambda repo: hub) == 0
    assert hub.downloads == []                      # nothing left to fetch

def test_pulled_files_are_current_without_hashing_again(tmp_path, capsys, monkeypatch):
    _, dst, hub = _published(tmp_path)
    tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds"], hub_factory=lambda repo: hub)
    capsys.readouterr()
    import helpmate_server.corpus_diff as cd
    monkeypatch.setattr(cd, "sha256_file", lambda p: (_ for _ in ()).throw(AssertionError("hashed")))
    out = _diff(dst, hub, capsys, "--verify")       # the cache from pull covers every file
    assert out.splitlines()[-1].startswith("0 new") and "2 up to date," in out

def test_a_copied_file_is_current_by_size_until_verified(tmp_path, capsys):
    src, dst, hub = _published(tmp_path)
    for f in src.iterdir():
        if f.suffix in (".hm", ".json") and f.name != "manifest.json":
            (dst / f.name).write_bytes(f.read_bytes())
    assert "(2 by size only" in _diff(dst, hub, capsys)
    out = _diff(dst, hub, capsys, "--verify")
    assert "by size only" not in out and "2 up to date," in out

def test_changed_files_are_found_by_size_and_by_hash(tmp_path, capsys):
    _, dst, hub = _published(tmp_path)
    tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds"], hub_factory=lambda repo: hub)
    capsys.readouterr()
    (dst / "Kvk.hm").write_bytes(b"\x04" * 9)        # size differs
    (dst / "KQvk.hm").write_bytes(b"\x07" * 24)      # same size, other content
    import os
    st = (dst / "KQvk.hm").stat()                    # a later edit: the mtime moves
    os.utime(dst / "KQvk.hm", ns=(st.st_atime_ns, st.st_mtime_ns + 10**9))
    out = _diff(dst, hub, capsys, "--verify")
    assert "changed  Kvk" in out and "changed  KQvk" in out
    hub.downloads.clear()
    tables_cli.main(["pull", "--tables", str(dst), "--repo", "u/ds", "--missing"],
                    hub_factory=lambda repo: hub)
    assert sorted(hub.downloads) == ["KQvk.hm", "KQvk.stats.json", "Kvk.hm"]
    assert (dst / "KQvk.hm").read_bytes() == b"\x03" * 24

def test_diff_lists_local_tables_the_dataset_lacks(tmp_path, capsys):
    _, dst, hub = _published(tmp_path)
    (dst / "KRvk.hm").write_bytes(b"\x01")
    assert "local    KRvk" in _diff(dst, hub, capsys)
