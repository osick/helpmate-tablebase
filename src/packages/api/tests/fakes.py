# src/packages/api/tests/fakes.py
"""In-memory stand-ins for the dataset (Hub) and GitHub, recording every
write so tests can assert what would have been posted, merged or pushed."""
from __future__ import annotations

import json
from pathlib import Path

from helpmate_server.contrib.hf import FileMeta, PullRequest


class FakeHub:
    def __init__(self, main: dict[str, bytes] | None = None):
        self.repo = "osick/helpmate-tables"
        self.main: dict[str, bytes] = dict(main or {})
        self.prs: dict[int, tuple[PullRequest, dict[str, bytes]]] = {}
        self.comments: list[tuple[int, str]] = []
        self.merged: list[int] = []
        self.commits: list[tuple[str, dict[str, bytes]]] = []
        self.downloads: list[str] = []

    def add_pr(self, num, files: dict[str, bytes], *, author="popeye37", description="",
               head="h1", status="open"):
        pr = PullRequest(num, f"Add {num}", author, status, description, sorted(files), head,
                         f"https://hf.example/discussions/{num}")
        self.prs[num] = (pr, dict(files))

    def pull_request(self, num):
        return self.prs[num][0]

    def open_pull_requests(self):
        return [p for p, _ in self.prs.values() if p.status == "open"]

    def file_sizes(self, files, revision):
        num = int(revision.rsplit("/", 1)[1])
        return {f: len(self.prs[num][1][f]) for f in files}

    def download(self, filename, revision, dest: Path) -> Path:
        num = int(revision.rsplit("/", 1)[1])
        self.downloads.append(filename)
        dest.mkdir(parents=True, exist_ok=True)
        (dest / filename).write_bytes(self.prs[num][1][filename])
        return dest / filename

    def comment(self, num, text):
        self.comments.append((num, text))

    def merge(self, num):
        pr, files = self.prs[num]
        self.main.update(files)
        pr.status = "merged"
        self.merged.append(num)

    def main_files(self):
        import hashlib
        return {k: FileMeta(k, len(v), hashlib.sha256(v).hexdigest()) for k, v in self.main.items()}

    def read_bytes(self, filename, revision="main"):
        return self.main[filename]

    def fetch_manifest(self):
        return json.loads(self.main.get("manifest.json", b'{"schema":1,"files":{}}'))

    def commit(self, files, message):
        self.commits.append((message, dict(files)))
        self.main.update(files)


class FakeGitHub:
    def __init__(self, issues: list[dict] | None = None):
        self.issues = {i["number"]: i for i in (issues or [])}
        self.posted: list[tuple[int, str]] = []
        self.edited: list[tuple[int, str]] = []
        self.labels: dict[int, set[str]] = {n: set(i.get("labels", [])) for n, i in self.issues.items()}
        self.closed: list[int] = []
        self.issue_comments: dict[int, list[dict]] = {n: [] for n in self.issues}

    def comment(self, issue, body):
        self.posted.append((issue, body))
        self.issue_comments.setdefault(issue, []).append(
            {"id": len(self.posted), "body": body, "user": "github-actions[bot]",
             "created_at": "2026-09-30T00:00:00Z"})

    def issue(self, num):
        return self.issues[num]
