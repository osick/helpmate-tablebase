"""Argument wiring for the contribution subcommands of helpmate-tables.
Module level stays import-light: see tables_cli's constraint."""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import DATASET_REPO, DEFAULT_STAGING, GITHUB_REPO

CONTRIB_COMMANDS = {"verify", "status", "accept", "sync", "claims"}


class UsageError(Exception):
    pass


def add_parsers(sub) -> None:
    v = sub.add_parser("verify", help="check tables (yours before a PR, or a dataset PR)")
    v.add_argument("--tables", required=True, metavar="DIR",
                   help="directory holding the table and every published sub-table")
    what = v.add_mutually_exclusive_group(required=True)
    what.add_argument("--material", action="append", metavar="M")
    what.add_argument("--pr", action="append", type=int, metavar="N",
                      help="maintainer: verify a pull request on the dataset")
    v.add_argument("--repo", default=DATASET_REPO, metavar="USER/DATASET")
    v.add_argument("--github-repo", default=GITHUB_REPO)
    v.add_argument("--samples", type=int, default=2000)
    v.add_argument("--oracle-samples", type=int, default=20)
    v.add_argument("--seed", type=int)
    v.add_argument("--report", metavar="FILE", help="also write the JSON report here")
    v.add_argument("--staging", type=Path, default=DEFAULT_STAGING)
    v.add_argument("--plan-only", action="store_true", help="--pr: list files and sizes, then stop")
    v.add_argument("--yes", action="store_true", help="--pr: download without asking")
    v.add_argument("--no-post", action="store_true", help="--pr: do not comment anywhere")


def _installed_version() -> str:
    try:
        import helpmate
        return helpmate.__version__
    except ImportError as exc:
        raise UsageError("verify needs the helpmate bindings: run `make install`") from exc


def _require_verify_deps() -> None:
    try:
        import chess  # noqa: F401
        import numpy  # noqa: F401
        import zstandard  # noqa: F401
    except ImportError as exc:
        raise UsageError("verify needs its extra: pip install './src/packages/api[verify]' "
                         f"(missing: {exc.name})") from exc


def _tool() -> str:
    from .. import __version__
    return f"helpmate-tables {__version__}"


def run(a: argparse.Namespace, hub_factory=None, gh_factory=None) -> int:
    try:
        if a.cmd == "verify":
            return _verify(a, hub_factory, gh_factory)
        raise UsageError(f"{a.cmd}: not implemented yet")
    except UsageError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


def _verify(a, hub_factory, gh_factory) -> int:
    from .consistency import MissingSubtable
    from .materials import canonical
    from .report import render_markdown, report_json
    from .verify import VerifyOptions, verify_table

    _require_verify_deps()
    version = _installed_version()
    opts = VerifyOptions(samples=a.samples, oracle_samples=a.oracle_samples, seed=a.seed)
    if a.pr:
        from .verify import verify_prs
        return verify_prs(a, opts, version, _tool(), hub_factory, gh_factory)
    tables = Path(a.tables).expanduser()
    for m in a.material:
        if canonical(m) != m:
            raise UsageError(f"{m!r} is not a canonical material name"
                             + (f" (did you mean {canonical(m)}?)" if canonical(m) else ""))
    try:
        reports = [verify_table(m, tables, opts, version) for m in a.material]
    except MissingSubtable as exc:
        # An incomplete tables directory, not a defect in the table.
        raise UsageError(str(exc)) from exc
    seed = opts.resolved_seed()
    print(render_markdown(reports, heading="Verification", seed=seed, tool=_tool()))
    if a.report:
        Path(a.report).write_text(json.dumps(
            report_json(reports, seed=seed, tool=_tool(), head=None, pr=None), indent=2))
    return 0 if all(r.passed for r in reports) else 1
