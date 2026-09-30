"""GitHub REST over urllib: the Action has GITHUB_TOKEN, the maintainer has
`gh auth token`. No third-party client, so the Action installs nothing."""
from __future__ import annotations

import json
import os
import subprocess
import urllib.request
from typing import Any, Callable


def _token() -> str | None:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True,
                              check=True).stdout.strip() or None
    except (OSError, subprocess.CalledProcessError):
        return None


class GitHub:
    def __init__(self, repo: str, token: str | None = None,
                 opener: Callable[..., Any] | None = None):
        self.repo = repo
        self.token = token if token is not None else _token()
        self._open = opener or urllib.request.urlopen

    def _req(self, method: str, path: str, body: Any = None) -> Any:
        url = path if path.startswith("https://") else f"https://api.github.com{path}"
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method)
        req.add_header("Accept", "application/vnd.github+json")
        if self.token:
            req.add_header("Authorization", f"Bearer {self.token}")
        with self._open(req) as resp:
            raw = resp.read()
        return json.loads(raw) if raw else None

    def comment(self, issue: int, body: str) -> None:
        self._req("POST", f"/repos/{self.repo}/issues/{issue}/comments", {"body": body})

    def issue(self, num: int) -> dict:
        return self._req("GET", f"/repos/{self.repo}/issues/{num}")
