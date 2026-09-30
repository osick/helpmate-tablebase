"""The dataset side: pull requests, their files, comments, merges, commits."""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

_DIFF_FILE = re.compile(r"^diff --git a/(\S+) b/\S+$", re.M)


@dataclass
class PullRequest:
    num: int
    title: str
    author: str
    status: str            # "open" | "merged" | "closed" | "draft"
    description: str
    files: list[str] = field(default_factory=list)
    head: str | None = None
    url: str = ""

    @property
    def materials(self) -> list[str]:
        return sorted({f[: -len(".hm")] for f in self.files if f.endswith(".hm")})


@dataclass(frozen=True)
class FileMeta:
    path: str
    size: int
    sha256: str | None     # None for non-LFS files: hash their bytes


class Hub:
    def __init__(self, repo_id: str, api=None):
        from huggingface_hub import HfApi

        self.repo = repo_id
        self.api = api or HfApi()

    def _url(self, num: int) -> str:
        return f"https://huggingface.co/datasets/{self.repo}/discussions/{num}"

    def pull_request(self, num: int) -> PullRequest:
        d = self.api.get_discussion_details(self.repo, num, repo_type="dataset")
        if not d.is_pull_request:
            raise ValueError(f"#{num} on {self.repo} is a discussion, not a pull request")
        desc = next((getattr(e, "content", "") for e in d.events
                     if getattr(e, "type", "") == "comment"), "")
        head = None
        refs = self.api.list_repo_refs(self.repo, repo_type="dataset", include_pull_requests=True)
        for r in refs.pull_requests or []:
            if r.ref == f"refs/pr/{num}":
                head = r.target_commit
        files = sorted(set(_DIFF_FILE.findall(d.diff or "")))
        if not files:  # the API leaves `diff` empty for LFS-only changes
            files = self._changed_files(f"refs/pr/{num}")
        return PullRequest(num, d.title, d.author, d.status, desc, files, head, self._url(num))

    def _tree(self, revision: str) -> dict[str, tuple]:
        from huggingface_hub.hf_api import RepoFile

        return {f.path: (f.size, f.lfs.sha256 if f.lfs else f.blob_id)
                for f in self.api.list_repo_tree(self.repo, repo_type="dataset",
                                                 revision=revision, expand=True)
                if isinstance(f, RepoFile)}

    def _changed_files(self, revision: str) -> list[str]:
        """Files added or changed on the PR branch relative to main.
        `.gitattributes` is maintained by the Hub itself, not contributed."""
        main, pr = self._tree("main"), self._tree(revision)
        return sorted(p for p, ident in pr.items() if p != ".gitattributes" and main.get(p) != ident)

    def open_pull_requests(self) -> list[PullRequest]:
        ds = self.api.get_repo_discussions(self.repo, repo_type="dataset",
                                           discussion_type="pull_request",
                                           discussion_status="open")
        return [self.pull_request(d.num) for d in ds]

    def file_sizes(self, files: list[str], revision: str) -> dict[str, int]:
        if not files:
            return {}
        infos = self.api.get_paths_info(self.repo, files, revision=revision, repo_type="dataset")
        return {i.path: i.size for i in infos}

    def download(self, filename: str, revision: str, dest: Path) -> Path:
        from huggingface_hub import hf_hub_download

        return Path(hf_hub_download(self.repo, filename, repo_type="dataset",
                                    revision=revision, local_dir=dest))

    def comment(self, num: int, text: str) -> None:
        self.api.comment_discussion(self.repo, num, text, repo_type="dataset")

    def merge(self, num: int) -> None:
        self.api.merge_pull_request(self.repo, num, repo_type="dataset")

    def main_files(self) -> dict[str, FileMeta]:
        from huggingface_hub.hf_api import RepoFile

        out = {}
        for f in self.api.list_repo_tree(self.repo, repo_type="dataset", expand=True):
            if isinstance(f, RepoFile):
                out[f.path] = FileMeta(f.path, f.size, f.lfs.sha256 if f.lfs else None)
        return out

    def read_bytes(self, filename: str, revision: str = "main") -> bytes:
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            return self.download(filename, revision, Path(tmp)).read_bytes()

    def fetch_manifest(self) -> dict:
        import json

        return json.loads(self.read_bytes("manifest.json"))

    def commit(self, files: dict[str, bytes], message: str) -> None:
        from huggingface_hub import CommitOperationAdd

        ops = [CommitOperationAdd(path_in_repo=k, path_or_fileobj=v) for k, v in files.items()]
        self.api.create_commit(repo_id=self.repo, repo_type="dataset", operations=ops,
                               commit_message=message)
