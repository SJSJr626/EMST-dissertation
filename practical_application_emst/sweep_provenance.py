"""Provenance guard for sweep output directories (used by both launchers and reports).

A sweep --outdir is only resumable, or readable by a report, if every result in it
was produced by the same generated script (lvl1.py / lvl2.py, identified by a hash
of its bytes) from the same upstream handoff, condition and grid. The launcher
writes that identity to `_provenance.json` when it starts a fresh directory; each
result file also carries it in its own columns. Anything else fails loudly: no
result is ever reused on the strength of its filename alone.
"""
import hashlib
import json
import re
from pathlib import Path

import pandas as pd

MANIFEST = "_provenance.json"


def pipeline_fingerprint(script):
    """First 16 hex digits of the SHA-256 of a generated script's bytes. Any change to
    the notebook that reaches the script (code, config, comments) changes it."""
    return hashlib.sha256(Path(script).read_bytes()).hexdigest()[:16]


def grid_fingerprint(runs):
    """Hash of the full config list; config ids are positions in it."""
    return hashlib.sha256(json.dumps(runs, sort_keys=True, default=repr).encode()).hexdigest()[:16]


def result_files(outdir, stem_regex):
    """Result files whose stem matches stem_regex exactly (e.g. r"cfg\\d{6}")."""
    return sorted(p for p in Path(outdir).glob("*.csv") if re.fullmatch(stem_regex, p.stem))


def _fail(msg):
    raise SystemExit(f"[provenance] {msg}\n  Start a fresh --outdir (or move this one aside); "
                     "results from a different pipeline/handoff are never reused.")


def check_outdir(outdir, expected, stem_regex, file_keys, write=True):
    """Validate `outdir` against `expected` (the manifest dict) before resuming.

    - results but no manifest              -> fail (unknown provenance, treated as stale)
    - manifest != expected                 -> fail, naming the differing keys
    - a non-empty result file whose file_keys columns are missing or differ -> fail
    - otherwise OK; writes the manifest for a fresh directory when write=True.
    Returns the number of existing result files."""
    outdir = Path(outdir)
    man_path = outdir / MANIFEST
    files = result_files(outdir, stem_regex)
    if man_path.exists():
        got = json.loads(man_path.read_text())
        diff = {k: (got.get(k), v) for k, v in expected.items() if str(got.get(k)) != str(v)}
        if diff:
            _fail(f"{outdir} was written under a different provenance: "
                  + "; ".join(f"{k}: {a!r} -> {b!r}" for k, (a, b) in diff.items()))
    elif files:
        _fail(f"{outdir} holds {len(files)} result file(s) but no {MANIFEST}: provenance "
              "unknown (not written by the current launchers), so they are stale.")
    for f in files:
        row = pd.read_csv(f, nrows=1)
        if row.empty:                                   # header-only: covered by the manifest
            continue
        for col, want in file_keys.items():
            if col not in row.columns:
                _fail(f"{f.name} has no '{col}' column (not written by the current pipeline).")
            if str(row[col].iloc[0]) != str(want):
                _fail(f"{f.name}: {col} = {row[col].iloc[0]!r}, expected {want!r}.")
    if write and not man_path.exists():
        outdir.mkdir(parents=True, exist_ok=True)
        man_path.write_text(json.dumps(expected, indent=1))
    return len(files)


def read_sweep(outdir, stem_regex, file_keys):
    """For reports: the manifest of a finished/partial sweep, after checking that every
    non-empty result file matches it on file_keys (a manifest key -> column map)."""
    outdir = Path(outdir)
    man_path = outdir / MANIFEST
    if not man_path.exists():
        _fail(f"{outdir} has no {MANIFEST}: not produced by the current launcher, so stale.")
    man = json.loads(man_path.read_text())
    for f in result_files(outdir, stem_regex):
        row = pd.read_csv(f, nrows=1)
        if row.empty:
            continue
        for key, col in file_keys.items():
            if col not in row.columns or str(row[col].iloc[0]) != str(man[key]):
                _fail(f"{f.name} does not match {man_path.name} on {col}.")
    return man
