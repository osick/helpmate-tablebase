"""verify: run V2-V7 on tables in a directory; V1 and downloading for PRs."""
from __future__ import annotations

import json
import secrets
from dataclasses import dataclass
from pathlib import Path

from .checks import (
    Check, TableReport, check_block_integrity, check_deepest, check_header, check_sidecar,
)
from .consistency import check_consistency
from .oracle import check_oracle
from .tablefile import read_header


@dataclass
class VerifyOptions:
    samples: int = 2000
    oracle_samples: int = 20
    oracle_plies: int = 3
    seed: int | None = None

    def resolved_seed(self) -> int:
        if self.seed is None:
            self.seed = secrets.randbelow(2**31)
        return self.seed


def verify_table(material: str, tables: Path, opts: VerifyOptions,
                 installed_version: str) -> TableReport:
    rep = TableReport(material)
    path = tables / f"{material}.hm"
    if not path.exists():
        rep.checks.append(Check("V2", "header and identity", "fail", f"{path} not found"))
        return rep
    for check in (lambda: check_header(path, installed_version),
                  lambda: check_block_integrity(path)):
        rep.checks.append(check())
        if not rep.passed:
            return rep  # later checks would only restate a structural failure
    rep.checks.append(check_sidecar(path))
    rep.checks.append(check_deepest(path, tables))
    if read_header(path).marker:
        rep.checks.append(Check("V6", "local consistency", "skip", "marker table"))
        rep.checks.append(Check("V7", "independent solver", "skip", "marker table"))
        return rep
    seed = opts.resolved_seed()
    sc = json.loads(path.with_name(f"{material}.stats.json").read_text())
    extra = list(sc.get("deepest", [])) + list(sc.get("deepest_unique", []))
    v6, fens = check_consistency(material, tables, opts.samples, seed, extra)
    rep.checks.append(v6)
    rep.checks.append(check_oracle(material, tables, samples=opts.oracle_samples,
                                   max_plies=opts.oracle_plies, seed=seed, others=fens))
    return rep
