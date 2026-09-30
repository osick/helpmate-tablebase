"""accept: merge verified dataset PRs and land the bookkeeping.

Each step is recorded in a state file as it completes, so a rerun after a
failure (network, CI) resumes where it stopped and never merges twice.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from .claims import load_index, material_status, ownership_conflict
from .docs_sync import CorpusFacts, SyncError, close_finished_claims, sync
from .hf import PullRequest
from .links import parse_links
from .registry import Contributor, Registry, resolve_contributor

STEPS = ("merge", "manifest", "local", "docs", "card", "claims")
# Every file the docs step writes; anything else dirty in the checkout is not ours to touch.
DOCS_PATHS = ("CHANGELOG.md", "data/contributions.json", "README.md", "docs/CONTRIBUTING-TABLES.md",
              "docs/COOPERATIVE-TABLEBASE.md", "docs/hf-dataset-card.md", "docs/MATERIALS.md",
              ".all-contributorsrc")
_NO_CHECKS = "no checks reported"


def manifest_from_hub(hub, generator_version: str) -> dict:
    files = {}
    for path, meta in sorted(hub.main_files().items()):
        if not path.endswith((".hm", ".stats.json")):
            continue
        sha = meta.sha256 or hashlib.sha256(hub.read_bytes(path)).hexdigest()
        files[path] = {"sha256": sha, "size": meta.size}
    return {"schema": 1, "generator_version": generator_version, "files": files}


def add_changelog_data(text: str, line: str) -> str:
    m = re.search(r"^## \[Unreleased\]\n", text, re.M)
    if not m:
        raise ValueError("CHANGELOG.md has no '## [Unreleased]' section")
    nxt = re.search(r"^## \[", text[m.end():], re.M)
    end = m.end() + (nxt.start() if nxt else len(text) - m.end())
    section = text[m.end():end]
    if "### Data\n" in section:
        i = m.end() + section.index("### Data\n") + len("### Data\n")
        return text[:i] + line + "\n" + text[i:]
    return text[:m.end()] + "\n### Data\n" + line + "\n" + text[m.end():]


class Git:
    """git and gh as the maintainer runs them (see Global Constraints: pushes
    bypass the global config that rewrites HTTPS to SSH)."""

    def __init__(self, checkout: Path, runner=subprocess.run, sleep=time.sleep):
        self.cwd = checkout
        self._runner = runner
        self._sleep = sleep

    def _run(self, *args: str, env: dict | None = None, check: bool = True):
        return self._runner(list(args), cwd=self.cwd, check=check, capture_output=True, text=True,
                            env={**os.environ, **(env or {})})

    def _out(self, *args: str, env: dict | None = None) -> str:
        return self._run(*args, env=env).stdout.strip()

    def clean(self) -> bool:
        return self._out("git", "status", "--porcelain") == ""

    def dirty_paths(self) -> list[str]:
        return [line[3:].strip().strip('"') for line in
                self._run("git", "status", "--porcelain", "--no-renames").stdout.splitlines() if line.strip()]

    def current(self) -> str:
        return self._out("git", "rev-parse", "--abbrev-ref", "HEAD")

    def reset_to_origin_main(self, branch: str, paths: tuple[str, ...] = DOCS_PATHS) -> None:
        """A fresh branch from origin/main. Only `paths` (what accept generates) are restored
        to HEAD, in index and worktree, or removed if untracked: nothing else is touched."""
        in_head = set(self._out("git", "ls-tree", "-r", "--name-only", "HEAD", "--", *paths).splitlines())
        if in_head:
            self._run("git", "restore", "--staged", "--worktree", "--source=HEAD", "--", *sorted(in_head))
        for p in paths:
            if p not in in_head:
                self._run("git", "rm", "-rf", "--ignore-unmatch", "-q", "--", p)
        self._run("git", "clean", "-fd", "--", *paths)
        self._run("git", "fetch", "origin", "main", env={"GIT_CONFIG_GLOBAL": "/dev/null"})
        self._run("git", "switch", "-C", branch, "origin/main")

    def commit_all(self, message: str) -> None:
        self._run("git", "add", "-A")
        self._run("git", "commit", "-m", message)

    def push(self, branch: str) -> None:
        self._run("git", "-c", "credential.helper=",
                  "-c", "credential.helper=!gh auth git-credential",
                  "push", "--force-with-lease", "-u", "origin", branch,
                  env={"GIT_CONFIG_GLOBAL": "/dev/null"})

    def open_pr(self, title: str, body: str, branch: str | None = None) -> str:
        if branch:
            existing = json.loads(self._out("gh", "pr", "list", "--head", branch, "--state", "open",
                                            "--json", "url") or "[]")
            if existing:
                return existing[0]["url"]
        args = ["gh", "pr", "create", "--base", "main", "--title", title, "--body", body]
        if branch:
            args += ["--head", branch]
        return self._out(*args)

    def wait_and_merge(self, url: str) -> None:
        if json.loads(self._out("gh", "pr", "view", url, "--json", "state")).get("state") == "MERGED":
            return
        for _ in range(12):  # right after `pr create`, GitHub has not registered the checks yet
            r = self._run("gh", "pr", "checks", url, check=False)
            if _NO_CHECKS not in (r.stdout + r.stderr).lower():
                break
            self._sleep(10)
        else:
            raise RuntimeError(f"no checks were reported for {url} after 2 minutes")
        # not captured: the maintainer watches CI progress in the terminal
        self._runner(["gh", "pr", "checks", url, "--watch", "--fail-fast"], cwd=self.cwd, check=True)
        self._run("gh", "pr", "merge", url, "--squash", "--delete-branch")

    def back(self, ref: str) -> None:
        self._run("git", "switch", ref)


def _err(msg: str) -> int:
    print(f"error: {msg}", file=sys.stderr)
    return 2


def _missing_staged(hub, pr, files_dir: Path) -> list[str]:
    """Table files of the PR that are not staged locally at the size the PR has."""
    names = [f for f in pr.files if f.endswith((".hm", ".stats.json"))]
    sizes = hub.file_sizes(names, pr.head)
    return [f for f in names
            if not (files_dir / f).exists() or (files_dir / f).stat().st_size != sizes.get(f)]


def accept(prs: list[int], *, hub, gh, git, checkout: Path, tables: Path, staging: Path,
           contributor: str | None, today: str) -> int:
    state_path = staging / f"accept-{'-'.join(map(str, sorted(prs)))}.json"
    state = json.loads(state_path.read_text()) if state_path.exists() else {"done": []}

    def save() -> None:
        state_path.write_text(json.dumps(state, indent=2))

    def mark(step: str, **extra) -> None:
        state["done"].append(step)
        state.update(extra)
        save()

    def sub(name: str) -> bool:
        """True if this sub-step of the docs step is recorded; call sub_done to record it."""
        return name in state.get("sub", [])

    def sub_done(name: str) -> None:
        state.setdefault("sub", []).append(name)
        save()

    reg_path = checkout / "data" / "contributions.json"
    # What each PR contained, as validated: after the merge the Hub is never asked again.
    stored: dict[str, dict] = state.setdefault("pulls", {})

    if "merge" not in state["done"]:
        index = load_index(gh)
        if not git.clean():
            return _err(f"{checkout} has uncommitted changes")
        reg = Registry.load(reg_path)
        try:  # sync needs every published sidecar locally; find out before merging
            CorpusFacts.from_manifest(hub.fetch_manifest(), tables)
        except SyncError as exc:
            return _err(str(exc))
        people: dict[int, dict[str, Any]] = {int(k): v for k, v in state.get("people", {}).items()}
        seen_keys: dict[str, str | None] = {}
        merged = state.setdefault("merged", [])
        for n in prs:
            if n in merged:  # merged by an earlier, interrupted run; already validated then
                seen_keys[people[n]["key"]] = people[n]["github"]
                continue
            pr = hub.pull_request(n)
            rep_path = staging / f"pr-{n}" / "report.json"
            if not rep_path.exists():
                return _err(f"PR #{n} has no verification report; run verify --pr {n}")
            rep = json.loads(rep_path.read_text())
            if rep["result"] != "pass":
                return _err(f"PR #{n}: the last verification failed")
            if pr.status != "open":
                return _err(f"PR #{n} is {pr.status}")
            if rep.get("head") != pr.head:
                return _err(f"PR #{n} changed after verification (verified {rep.get('head')}, "
                            f"now {pr.head}); run verify --pr {n} again")
            missing = _missing_staged(hub, pr, staging / f"pr-{n}" / "files")
            if missing:
                return _err(f"PR #{n}: staged files missing or of the wrong size: {', '.join(missing)}; "
                            f"run verify --pr {n} again")
            claim_no = parse_links(pr.description)[0]
            claim = next((c for c in index.claims if c.issue == claim_no), None) \
                or (index.claim_for(pr.materials[0]) if pr.materials else None)
            why = ownership_conflict(pr, claim, reg) if claim and not contributor else None
            if why:
                return _err(f"PR #{n}: {why} (the claims bot shows this as a conflict); "
                            "pass --contributor LOGIN")
            who = resolve_contributor(reg, pr, claim, contributor)
            if who is None:
                return _err(f"PR #{n} by HF user {pr.author}: no GitHub identity found; "
                            "pass --contributor LOGIN")
            known = reg.contributors.get(who.key)
            other = known.github if known else seen_keys.get(who.key)
            if (known or who.key in seen_keys) and (other or "").lower() != (who.github or "").lower():
                return _err(f"PR #{n}: registry key {who.key!r} already belongs to GitHub user "
                            f"{other!r}, not {who.github!r}; pass --contributor with the right login "
                            "or fix data/contributions.json")
            seen_keys[who.key] = who.github
            people[n] = {"key": who.key, "github": who.github, "hf": who.hf,
                         "display": who.display, "anonymous": who.anonymous,
                         "claim": claim.issue if claim else None}
            stored[str(n)] = {k: v for k, v in asdict(pr).items() if k != "num"}
        state["people"] = {str(k): v for k, v in people.items()}
        save()
        for n in prs:
            if n not in merged:
                hub.merge(n)
                merged.append(n)
                save()
        mark("merge")

    people = {int(k): v for k, v in state["people"].items()}
    pulls = {n: PullRequest(n, **stored[str(n)]) for n in prs}

    if "manifest" not in state["done"]:
        old = hub.fetch_manifest()
        man = manifest_from_hub(hub, old.get("generator_version", "unknown"))
        hub.commit({"manifest.json": json.dumps(man, indent=2, sort_keys=True).encode()},
                   f"Manifest after merging PR(s) {', '.join(f'#{n}' for n in prs)}")
        mark("manifest")

    if "local" not in state["done"]:
        for n, pr in pulls.items():
            for f in pr.files:
                src = staging / f"pr-{n}" / "files" / f
                if f.endswith((".hm", ".stats.json")) and src.exists():
                    shutil.move(str(src), tables / f)
        mark("local")

    card_path = state_path.with_suffix(".card.md")
    if "docs" not in state["done"]:
        branch = "data/accept-" + "-".join(map(str, sorted(prs)))
        lines = []
        for n, pr in pulls.items():
            p = people[n]
            credited = "an anonymous contributor" if p.get("anonymous") else p["display"]
            lines.append(f"- {', '.join(pr.materials)} contributed by {credited} "
                         f"(dataset PR #{n}" + (f", claim #{p['claim']}" if p["claim"] else "") + ").")
        mats = [m for pr in pulls.values() for m in pr.materials]
        title = f"Data: {len(mats)} table(s) from dataset PR(s) {', '.join(f'#{n}' for n in prs)}"
        if not sub("committed"):
            outside = [d for d in git.dirty_paths() if d not in DOCS_PATHS]
            if outside:
                return _err(f"{checkout} has uncommitted changes outside what accept writes: "
                            f"{', '.join(outside)}")
            if not state.get("docs_started"):
                if not git.clean():
                    return _err(f"{checkout} has uncommitted changes; commit or stash them first")
                state["docs_started"] = True  # from here on, leftovers in DOCS_PATHS are ours
                save()
            if "original" not in state:  # first attempt only: later ones may start on the data branch
                state["original"] = git.current()
                save()
            git.reset_to_origin_main(branch, DOCS_PATHS)
            reg = Registry.load(reg_path)
            for n, pr in pulls.items():
                p = people[n]
                if p["key"] not in reg.contributors:
                    reg.add_contributor(Contributor(p["key"], p["github"], p["hf"], p["display"],
                                                    anonymous=p.get("anonymous", False)))
                rep = json.loads((staging / f"pr-{n}" / "report.json").read_text())
                for m in pr.materials:
                    sc = json.loads((tables / f"{m}.stats.json").read_text())
                    reg.record_table(m, contributor=p["key"], hf_pr=n, claim=p["claim"],
                                     merged=today, generator_version=sc.get("generator_version", ""),
                                     verification={"tool": rep.get("tool"), "head": rep.get("head"),
                                                   "seed": rep.get("seed"), "result": rep["result"]})
            reg.save()
            cl = checkout / "CHANGELOG.md"
            text = cl.read_text()
            for line in lines:
                text = add_changelog_data(text, line)
            cl.write_text(text)
            sync(checkout, hub, gh, reg, tables, close_claims=False)
            card_path.write_bytes((checkout / "docs" / "hf-dataset-card.md").read_bytes())
            trailers = sorted({f"Co-authored-by: {p['github']} <{gh.user_id(p['github'])}+"
                               f"{p['github']}@users.noreply.github.com>"
                               for p in people.values()
                               if p["github"] and not reg.contributors[p["key"]].anonymous})
            git.commit_all(title + "\n\n" + "\n".join(lines) + "\n\n" + "\n".join(trailers))
            sub_done("committed")
        if "docs_pr" not in state:
            if not sub("pushed"):
                git.push(branch)
                sub_done("pushed")
            state["docs_pr"] = git.open_pr(title, "\n".join(lines), branch)
            save()
        if not sub("docs_merged"):
            git.wait_and_merge(state["docs_pr"])
            sub_done("docs_merged")
        git.back(state.get("original", "main"))
        mark("docs")

    if "card" not in state["done"]:  # only now: the public card must not credit a failed docs PR
        hub.commit({"README.md": card_path.read_bytes()}, "Dataset card: contributors and counts")
        mark("card")

    if "claims" not in state["done"]:
        for n, pr in pulls.items():
            c = people[n]["claim"]
            if c is not None and n not in state.setdefault("commented", []):
                gh.comment(c, f"Accepted: {', '.join(pr.materials)} ([HF PR #{n}]({pr.url})) — "
                              f"now in the dataset and credited in docs/MATERIALS.md. Thank you!")
                state["commented"].append(n)
                save()
        reg = Registry.load(reg_path)
        done = {f[:-3] for f in hub.fetch_manifest().get("files", {}) if f.endswith(".hm")}
        idx = load_index(gh)
        close_finished_claims(gh, idx, material_status(done, {}, idx, reg))
        mark("claims")
    state_path.unlink()
    card_path.unlink(missing_ok=True)
    return 0

def status(hub, gh, registry, staging: Path, checkout: Path) -> str:
    index = load_index(gh)
    rows = ["| HF PR | author | materials | claim | verification | |", "|---|---|---|---|---|---|"]
    for pr in hub.open_pull_requests():
        rep_path = staging / f"pr-{pr.num}" / "report.json"
        if rep_path.exists():
            rep = json.loads(rep_path.read_text())
            ver = rep["result"] + ("" if rep.get("head") == pr.head else " (stale: PR changed)")
        else:
            ver = "not verified"
        first = index.claim_for(pr.materials[0]) if pr.materials else None
        c = parse_links(pr.description)[0] or (first.issue if first else None)
        rows.append(f"| #{pr.num} | {pr.author} | {', '.join(pr.materials)} | "
                    f"{'#' + str(c) if c else '—'} | {ver} | |")
    try:
        last = subprocess.run(["git", "log", "-1", "--format=%cs", "--", "docs/DEEPEST.json"],
                              cwd=checkout, capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        last = ""
    newer = sum(1 for t in registry.tables.values() if last and t["merged"] > last)
    rows += ["", f"{newer} contributed table(s) merged since the last DEEPEST refresh ({last or '?'})."]
    return "\n".join(rows)
