"""Emit lvl0.py / lvl1.py / lvl2.py from the three level notebooks,
block_detection_and_removal_LVL{0,1,2}.ipynb, and write the LVL2 notebook's upstream-definitions cell, the
LVL2 run notebook block_detection_and_removal_LVL2_all_rep.ipynb from it, and the upstream-definitions
cell of LVL1_report.ipynb.

Cells are copied VERBATIM. The only code added is:
  * argparse -> per-knob overrides of the level's CONFIG dict (lvl1.py / lvl2.py: right after the config
    cell; lvl0.py: inside it, before the intake filters, so that a command-line intake knob takes effect)
  * matplotlib Agg (scripts run headless)
  * LVL_1 only: --condition / --subsample / --seed sample selection, and an
    --export switch so a sweep does not rewrite the LVL_1 handoff (EMST ~450 MB) per config
The handoff reads are the only notebook lines rewritten: the notebooks read the stamped
handoff named by their LVL0_HANDOFF / LVL1_HANDOFF pin; the scripts read --lvl0-input /
--lvl1-input.
Re-run this after editing a notebook to regenerate the scripts and the run notebook. The build never stops on a
setting that still holds "SET_ME": it builds the delivered state too, and the settings check of each level's
configuration cell stops the run instead (README, "Settings").
"""
import copy
import json
import re
from pathlib import Path

# CPUs of the LVL2 run notebook (its [cell 0] n_jobs); the template and the scripts keep [cell 0]'s value, so changing it
# changes no script; e.g. the CPU count of CPU_SET in submit_BDR_LVL2_notebooks_all.sh (EMST 31 over its three runs).
RUN_N_JOBS = "SET_ME"

# The three level notebooks. The first line of every code cell is its label:
#   "# [cell N]"          a pipeline cell. N is its pipeline-wide number and is what the
#                         "NOTEBOOK CELL n" banners print, so the scripts' bytes (and
#                         pipeline_fingerprint) do not depend on which notebook holds it.
#   "# [notebook only]"   never emitted: handoff pins and checks, lineage, the LVL2 upstream
#                         loader, notebook-only reporting.
# A cell in several notebooks (the [cell 0]-[cell 2] preamble) must be identical in each.
# Labels must increase down each notebook, because they fix the scripts' cell order. A new
# cell takes the next number and later labels are renumbered.
# An unlabelled code cell stops the build, so a cell can never silently drop out of a script.
NOTEBOOKS = [Path(f"block_detection_and_removal_LVL{n}.ipynb") for n in range(3)]
# Named in line 3 of every script. It is part of the scripts' bytes, so changing it changes
# every pipeline_fingerprint.
HEADER_NB = "block_detection_and_removal_LVL{0,1,2}.ipynb"
_LABEL = re.compile(r"# \[cell (\d+)\]")


def _merge_cells(paths):
    """{label: source} of every labelled code cell across the level notebooks."""
    cells, home = {}, {}
    for path in paths:
        last = -1
        for c in json.load(open(path))["cells"]:
            if c["cell_type"] != "code":
                continue
            src = "".join(c.get("source", []))
            first = src.split("\n", 1)[0]
            if first.startswith("# [notebook only]"):
                continue
            m = _LABEL.match(first)
            if not m:
                raise SystemExit(f"build_level_scripts: {path.name}: code cell without a '# [cell N]' "
                                 f"or '# [notebook only]' label: {first[:70]!r}")
            n = int(m.group(1))
            if n <= last:
                raise SystemExit(f"build_level_scripts: {path.name}: [cell {n}] comes after [cell {last}]; "
                                 "labels must increase down the notebook")
            last = n
            if n in cells and cells[n] != src:
                raise SystemExit(f"build_level_scripts: [cell {n}] differs between {home[n]} and "
                                 f"{path.name}; a shared cell must be an identical copy in each notebook")
            cells.setdefault(n, src)
            home.setdefault(n, path.name)
    return cells


C = _merge_cells(NOTEBOOKS)

# cell 0 sets BLAS env vars and must stay first, before numpy is imported
BLAS = C[0]

ARGS = '''
# ---------------------------------------------------------------- CLI
# Every key of {CFG} is settable as "--<key> <python-literal>"; parsing is
# deferred to the override block that runs right after the config cell.
import argparse, ast

_p = argparse.ArgumentParser(description="{DESC}")
_p.add_argument("--n-jobs", type=int, default=None,
                help="worker count; also forced into {CFG}['n_jobs']")
{EXTRA}_args, _rest = _p.parse_known_args()
if _args.n_jobs is not None:
    n_jobs = _args.n_jobs
    print(f"CPU cores to use: {{n_jobs}}  (--n-jobs)")

_overrides = {{}}
_i = 0
while _i < len(_rest):
    _k = _rest[_i].lstrip("-").replace("-", "_")
    _v = _rest[_i + 1]
    try:
        _overrides[_k] = ast.literal_eval(_v)
    except Exception:
        _overrides[_k] = _v
    _i += 2

import matplotlib
matplotlib.use("Agg")
'''

OVERRIDE = '''
# ---------------------------------------------------------------- knob overrides
for _k, _v in _overrides.items():
    if _k not in {CFG}:
        raise SystemExit(f"unknown knob for {CFG}: {{_k}}")
    {CFG}[_k] = _v
    print(f"  [cli] {CFG}[{{_k!r}}] = {{_v!r}}")

# --n-jobs must ALSO land in the config. run_block_detection reads config["n_jobs"]
# first (None = the module's n_jobs), so a number set there would otherwise win over
# --n-jobs, and each sweep worker would start a pool on every CPU. Only applied when
# --n-jobs was passed, so a standalone run keeps the notebook's own setting.
if _args.n_jobs is not None and "n_jobs" in {CFG}:
    {CFG}["n_jobs"] = _args.n_jobs
    print(f"  [cli] {CFG}['n_jobs'] = {{_args.n_jobs}}  (prevents nested oversubscription)")
'''


def _split_at_comment_block(src, anchor, what):
    """src split at the start of the comment block that holds `anchor` (which must occur once and start a line):
    (the code before it without trailing newlines, the rest)."""
    if src.count(anchor) != 1:
        raise SystemExit(f"build_level_scripts: {what} anchor matched {src.count(anchor)}x")
    at = src.index(anchor)
    lines = src[:at].split("\n")
    if lines[-1]:
        raise SystemExit(f"build_level_scripts: {what} anchor {anchor!r} does not start a line")
    j = len(lines) - 1
    while j > 0 and lines[j - 1].startswith("#"):
        j -= 1
    return "\n".join(lines[:j]).rstrip("\n"), "\n".join(lines[j:]) + src[at:]


def emit(path, cells, cfg, desc, extra="", inject=None, tail="", post_override="", override_before=None):
    """override_before: the knob overrides go inside the config cell, just before the comment block holding this
    line, instead of after the cell."""
    parts = [f'"""{desc}\n\nGenerated by build_level_scripts.py from '
             f'{HEADER_NB} -- do not edit directly.\n"""\n', BLAS,
             ARGS.format(CFG=cfg, DESC=desc, EXTRA=extra)]
    for i in cells:
        src = C[i]
        if inject:
            src = inject(i, src)
        banner = f"\n# ============================ NOTEBOOK CELL {i} ============================\n"
        if i == cfg_cell[cfg] and override_before is not None:
            head, rest = _split_at_comment_block(src, override_before, f"{path} knob overrides")
            parts += [banner + head, OVERRIDE.format(CFG=cfg) + post_override, rest]
            continue
        parts.append(banner + src)
        if i == cfg_cell[cfg]:
            parts.append(OVERRIDE.format(CFG=cfg) + post_override)
    parts.append(tail)
    Path(path).write_text("\n".join(parts))
    print(f"wrote {path}  ({sum(len(p) for p in parts):,} chars, {len(cells)} cells)")


def cell_index(needle, what, lo=0):
    """Resolve a cell by CONTENT, not position -- inserting a cell must not
    silently retarget an injection (str.replace no-ops when it misses)."""
    hits = [i for i, src in C.items() if i >= lo and needle in src]
    if len(hits) != 1:
        raise SystemExit(f"build_level_scripts: expected exactly one cell "
                         f"containing {needle!r} for {what}, found {hits}")
    return hits[0]


def _sub1(src, old, new, what):
    """Replace exactly one occurrence, or fail: a missed anchor must never no-op."""
    if src.count(old) != 1:
        raise SystemExit(f"build_level_scripts: {what} anchor matched {src.count(old)}x")
    return src.replace(old, new, 1)


# The warnings log in WARNINGS_OUTS belongs to the notebook run and to a full --export run. A sweep
# worker (no --export) keeps none: concurrent workers would truncate one shared file, and the
# launcher already saves a failing worker's output in its .err file.
LOG_FILE = 'filename=str(WARNINGS_OUTS / "suppressed_warnings.log"),'
LOG_FILE_SCRIPT = 'filename=str(WARNINGS_OUTS / "suppressed_warnings.log") if _args.export else os.devnull,'


def _log_inject(src):
    return _sub1(src, LOG_FILE, LOG_FILE_SCRIPT, "warnings log")


# The LVL_2 run's own warnings log (WARNINGS_OUTS/<LVL2_RUN_TAG>_warnings.log): likewise only for a --export run.
L2_RUN_LOG = 'LVL2_WARNINGS_LOG = WARNINGS_OUTS / f"{LVL2_RUN_TAG}_warnings.log"\n'
L2_RUN_LOG_SCRIPT = 'LVL2_WARNINGS_LOG = WARNINGS_OUTS / f"{LVL2_RUN_TAG}_warnings.log" if _args.export else None\n'


cfg_cell = {n: cell_index(f"{n} = {{", n)
            for n in ("LVL_0_CONFIG", "LVL_1_CONFIG", "LVL_2_CONFIG")}

# Every cell a script uses is resolved by CONTENT (cell_index fails unless exactly one
# cell matches), so inserting / moving notebook cells cannot silently retarget a script.
IMPORTS_CELL = cell_index("# IMPORTS, WARNING CONTROL", "imports cell")
DIRS_CELL = cell_index("# SET DIRECTORIES", "directories cell")
L0_QC = cell_index("def detect_periodic_patterns(", "LVL_0 response-style QC cell")
L0_CLEAN = cell_index("# CREATE CLEAN DATAFRAMES", "LVL_0 clean-dataframes cell")
L0_DRIFT = cell_index("def fit_drift_and_compute_residuals(", "LVL_0 drift cell")
L1_FILTERS = cell_index("def apply_rt_filters(", "RT filter cell")
L1_PIVOT = cell_index("def long_to_stim_level(", "long->stimulus pivot cell")
L1_RUN = cell_index("long_df = pd.read_csv(full_path)", "LVL_1 run cell")
L1_MERGE = cell_index("long_df = merge_block_labels_to_long(long_df, features_df)", "LVL_1 merge-to-long cell")
L1_SUMMARY = cell_index("plot_block_histogram(results_df, method_name=_hist_method)", "LVL_1 summary cell")
L1_EXPORT = cell_index("TIMESTAMPED LVL_1 HANDOFF", "LVL_1 handoff export cell")
L1_CONTROLS = cell_index("MERGING FIXED CONTROL BLOCKS TO LONG FORMAT", "LVL_1 fixed-control cell")
L1_CELLS = [IMPORTS_CELL, DIRS_CELL] + [i for i in sorted(C) if cfg_cell["LVL_1_CONFIG"] <= i <= L1_EXPORT]

L2_FIRST = cfg_cell["LVL_2_CONFIG"]
# Notebook-only LVL_2 cells: reporting / condition selection that lvl2.py does not need
# (lvl2.py selects conditions with --condition). Not emitted into lvl2.py.
L2_NOTEBOOK_ONLY = {cell_index(t, t, lo=L2_FIRST) for t in (
    "LVL_2 CONDITION SELECTION (notebook only)",
)}
L2_CELLS = [i for i in sorted(C) if i >= L2_FIRST and i not in L2_NOTEBOOK_ONLY]
L2_LOAD = cell_index('long_df_with_blocks = pd.read_csv(f"{LVL1_HANDOFF}_long.csv")', "LVL_2 load", lo=L2_FIRST)
L2_SAVE = cell_index("multimetric_df.to_csv(_out, index=False)", "LVL_2 save", lo=L2_FIRST)
L2_SKIP_TITLES = (
    "STEP 5d:",
    "STEP 5e:",
    "STEP 9:",
    "STEP 10:",
    "STEP 12:",
)
L2_SKIP = {cell_index(t, t, lo=L2_FIRST) for t in L2_SKIP_TITLES}

# ---------------------------------------------------------------- LVL_0
# The knob overrides go before the intake filters of the LVL_0 config cell (age, sessions, conditions), so that
# lvl0.py --max_age / --sessions / --conditions select the participants and rows it analyses; the notebook is unaffected.
L0_INTAKE = "# Apply the intake filters: age, then sessions and conditions"
emit("lvl0.py", [IMPORTS_CELL, DIRS_CELL, cfg_cell["LVL_0_CONFIG"], L0_QC, L0_CLEAN, L0_DRIFT], "LVL_0_CONFIG",
     "LVL_0: response-style QC + drift modelling.", override_before=L0_INTAKE)
_l0_txt = Path("lvl0.py").read_text()
if not (_l0_txt.count(L0_INTAKE) == 1 and _l0_txt.count(OVERRIDE.format(CFG="LVL_0_CONFIG")) == 1
        and _l0_txt.index("LVL_0_CONFIG = {") < _l0_txt.index(OVERRIDE.format(CFG="LVL_0_CONFIG"))
        < _l0_txt.index(L0_INTAKE)):
    raise SystemExit("build_level_scripts: lvl0.py failed verification: the knob overrides must follow LVL_0_CONFIG "
                     "and precede the intake filters")
print("verified lvl0.py: knob overrides between LVL_0_CONFIG and the intake filters")

# ---------------------------------------------------------------- LVL_1
L1_EXTRA = '''_p.add_argument("--lvl0-input", required=True,
                help="LVL_0 handoff csv in LVL_OUTS, e.g. lv0_out_<ts>.csv")
_p.add_argument("--condition", default="all", choices=["all"], help="every condition of the handoff (the pooled run)")
_p.add_argument("--subsample", type=int, default=0, help="participants to keep; 0 = all")
_p.add_argument("--seed", type=int, default=0, help="subsample draw seed (rep index)")
_p.add_argument("--out", default=None, help="write the method-summary table here")
_p.add_argument("--export", action="store_true", help="write the full LVL_1 handoff CSVs")
'''

# rt_threshold_na_handling has NO default. The notebook's LVL_1_CONFIG value (None until
# a mode is chosen) must never act as one for a script run, so lvl1.py stops unless the
# mode is on its command line. Emitted right after the knob overrides, before any data
# is read; the value itself is then validated by the notebook's knob check (cell 11).
L1_REQUIRED_KNOBS = '''
# ---------------------------------------------------------------- required knobs (no default)
if "rt_threshold_na_handling" not in _overrides:
    raise SystemExit("lvl1.py: --rt_threshold_na_handling is required (one of 'partial', "
                     "'drop_stimulus', 'bfill', 'ffill'); it has no default.")
'''

L1_SELECT = '''
# ---------------------------------------------------------------- sample selection
if _args.condition != "all":
    long_df = long_df[long_df["condition"] == _args.condition]
if _args.subsample:
    _ids = long_df["id"].drop_duplicates()
    _ids = _ids.sample(n=min(_args.subsample, len(_ids)), random_state=_args.seed)
    long_df = long_df[long_df["id"].isin(_ids)]
print(f"  [sample] condition={_args.condition} subsample={_args.subsample} "
      f"seed={_args.seed} -> {long_df['id'].nunique()} participants, {len(long_df):,} rows")
'''


def _guard(src, cond="if _args.export:"):
    """Indent a whole cell under a guard."""
    body = "\n".join("    " + ln if ln.strip() else ln for ln in src.split("\n"))
    return cond + "\n" + body


def l1_inject(i, src):
    """Sweep-specific edits. Every anchor is checked (_sub1 / cell_index): if the notebook
    changes so that one no longer matches, the build fails instead of emitting a script
    that silently runs the full data set or rewrites the handoff for every config."""
    if i == DIRS_CELL:
        return _log_inject(src)
    if i == L1_RUN:
        anchor = 'long_df = pd.read_csv(full_path)'
        src = _sub1(src, anchor, anchor + "\n" + L1_SELECT, "LVL_1 sample selection")
        # the notebook reads its LVL0_HANDOFF pin; the script reads --lvl0-input (a file
        # name in LVL_OUTS, as for the pin)
        src = _sub1(src, 'full_path = Path(LVL0_HANDOFF)',
                    'full_path = LVL_OUTS / _args.lvl0_input', "LVL_1 input path")
        return src
    if i == L1_MERGE:                 # merge-to-long
        return _guard(src)            # does not touch results_df -> summary unaffected
    if i == L1_CONTROLS:              # the fixed controls reach the long format only with --export (merge-to-long)
        return _sub1(src, "    if len(cols_to_merge) > 0:\n",
                     "    if len(cols_to_merge) > 0 and not _args.export:\n"
                     "        print(\"  not merged: the long format is built only with --export\")\n"
                     "    elif len(cols_to_merge) > 0:\n", "LVL_1 fixed-control merge")
    if i == L1_SUMMARY:               # keep the summary, drop the histogram render
        return _sub1(src, 'plot_block_histogram(results_df, method_name=_hist_method)',
                     'if _args.export:\n    plot_block_histogram(results_df, method_name=_hist_method)',
                     "LVL_1 histogram")
    if i == L1_EXPORT:                # guard the heavy handoff export
        return _guard(src)
    return src


def verify_l1_script(path):
    """Post-build check that the sweep-specific edits really landed in lvl1.py."""
    txt = Path(path).read_text()
    must = {
        "condition selection": 'long_df = long_df[long_df["condition"] == _args.condition]',
        "input from --lvl0-input": "full_path = LVL_OUTS / _args.lvl0_input",
        "histogram only with --export": "if _args.export:\n    plot_block_histogram(results_df, method_name=_hist_method)",
        "merge-to-long only with --export": "\n    long_df = merge_block_labels_to_long(long_df, features_df)",
        "fixed-control merge only with --export": "    if len(cols_to_merge) > 0 and not _args.export:\n",
        "handoff export only with --export": "\n    long_df_with_blocks.to_csv(_lvl1_long, index=False)",
        "result provenance column": "pipeline_fingerprint=_PIPELINE_FP",
        "rt_threshold_na_handling required on the CLI": L1_REQUIRED_KNOBS.strip(),
        "warnings log only with --export": LOG_FILE_SCRIPT,
    }
    must_not = {
        "unguarded merge-to-long": "\nlong_df = merge_block_labels_to_long(long_df, features_df)",
        "unguarded handoff export": "\nlong_df_with_blocks.to_csv(_lvl1_long, index=False)",
    }
    bad = [k for k, v in must.items() if v not in txt] + [k for k, v in must_not.items() if v in txt]
    if bad:
        raise SystemExit(f"build_level_scripts: {path} failed verification: {bad}")
    print(f"verified {path}: {len(must)} sweep edits present, {len(must_not)} unguarded forms absent")


L1_TAIL = '''
# ---------------------------------------------------------------- sweep result row
if _args.out:
    # Provenance: hash of THIS script's bytes (see sweep_provenance.py); the launcher
    # refuses to resume a directory whose results carry a different value.
    import hashlib as _hashlib
    _PIPELINE_FP = _hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    summary_df.assign(
        condition=_args.condition, subsample=_args.subsample, seed=_args.seed,
        lvl0_input=Path(_args.lvl0_input).name, pipeline_fingerprint=_PIPELINE_FP,
        **{f"cfg_{_k}": repr(_v) for _k, _v in _overrides.items()},
    ).to_csv(_args.out, index=False)
    print(f"  [out] {_args.out}")

    # Per-session validation p-values / effect sizes, so the report can run PAIRED
    # tests between detectors (McNemar on session-level significance). Named
    # sessions_cfgNNNNNN.csv so the report's cfg*.csv glob does not pool it.
    _o = Path(_args.out)
    _sess_cols = ["id", "session", "method", "n_blocks"] + [
        c for c in results_df.columns if c.endswith(("_p", "_effsize"))]
    results_df[[c for c in _sess_cols if c in results_df.columns]].to_csv(
        _o.with_name(f"sessions_{_o.name}"), index=False)
'''

emit("lvl1.py", L1_CELLS,
     "LVL_1_CONFIG", "LVL_1: block detection + external validation.",
     extra=L1_EXTRA, inject=l1_inject, tail=L1_TAIL, post_override=L1_REQUIRED_KNOBS)
verify_l1_script("lvl1.py")

# ---------------------------------------------------------------- LVL_2
# The LVL_0 config cell supplies LVL_0_CONFIG and all_data (an age source for LVL_2);
# from the LVL_0 QC cell ONLY the definitions LVL_2 calls are emitted
# (add_trial_markers and what it needs) -- not its permutation nulls and plots; the
# filter / pivot cells supply apply_rt_filters and long_to_stim_level.
L2_EXTRA = '''_p.add_argument("--lvl1-input", required=True,
                help="LVL_1 handoff prefix in LVL_OUTS, e.g. lv1_out_<ts>")
_p.add_argument("--condition", default="all", choices=["all"], help="every condition of the handoff (the pooled run)")
_p.add_argument("--out", default=None, help="write the multimetric removal table here")
_p.add_argument("--export", action="store_true", help="also run the H2 tests, the design tests, the post hoc analyses and the exports (Steps 5d-5e, 9, 10 and 12)")
_p.add_argument("--override-source", default="",
                help="who passes the knob overrides (e.g. the launcher or a report); recorded as their source")
'''

# Every knob set on the lvl2.py command line is recorded with who passed it; [cell 29]
# prints the behavioural heuristic's settings with these sources (the rest come from
# LVL_2_CONFIG). LVL_2 only, so lvl0.py / lvl1.py are unchanged by it.
L2_OVERRIDE_SOURCE = '''
# ---------------------------------------------------------------- override sources
CONFIG_OVERRIDE_SOURCE = {_k: "command line" + (f" ({_args.override_source})" if _args.override_source else "")
                          for _k in _overrides}
'''


L2_SELECT = '''
# ---------------------------------------------------------------- condition selection
if _args.condition != "all":
    long_df_with_blocks = long_df_with_blocks[long_df_with_blocks["condition"] == _args.condition]
    features_df = features_df[features_df["condition"] == _args.condition]
    results_df = results_df[results_df["id"].isin(features_df["id"].unique())]
    LVL_2_CONFIG["conditions"] = [_args.condition]
elif "condition" in features_df.columns:
    LVL_2_CONFIG["conditions"] = [str(c) for c in sorted(features_df["condition"].dropna().unique())]
print(f"  [sample] condition={_args.condition} -> {features_df['id'].nunique()} participants, "
      f"{len(features_df):,} feature rows")
'''


import ast as _ast
import builtins as _builtins


def _top_names(src):
    """Names bound at the top level of a cell (imports, defs, assignments)."""
    out = set()
    for n in _ast.parse(src).body:
        if isinstance(n, (_ast.Import, _ast.ImportFrom)):
            out |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, (_ast.FunctionDef, _ast.ClassDef)):
            out.add(n.name)
        else:
            out |= {x.id for x in _ast.walk(n) if isinstance(x, _ast.Name) and isinstance(x.ctx, _ast.Store)}
    return out


def _unbound_loads(src):
    """Names a cell reads that it never binds itself (anywhere in the cell)."""
    tree = _ast.parse(src)
    loads = {x.id for x in _ast.walk(tree) if isinstance(x, _ast.Name) and isinstance(x.ctx, _ast.Load)}
    bound = ({x.id for x in _ast.walk(tree) if isinstance(x, _ast.Name) and isinstance(x.ctx, (_ast.Store, _ast.Del))}
             | {x.arg for x in _ast.walk(tree) if isinstance(x, _ast.arg)}
             | {x.name for x in _ast.walk(tree) if isinstance(x, (_ast.FunctionDef, _ast.ClassDef))}
             | {(a.asname or a.name).split(".")[0] for x in _ast.walk(tree) if isinstance(x, (_ast.Import, _ast.ImportFrom))
                for a in x.names}
             | _top_names(src))
    return loads - bound - set(dir(_builtins))


def extract_defs(src, roots, provided, what, header=None):
    """Verbatim subset of a cell: the functions in `roots`, every function / literal
    constant of the same cell they need (transitively), in source order. Fails if a
    needed name is neither in the cell (as a def or a single literal assignment) nor in
    `provided` (names bound by the cells emitted before this one)."""
    tree = _ast.parse(src)
    funcs = {n.name: n for n in tree.body if isinstance(n, _ast.FunctionDef)}
    consts = {}
    for n in tree.body:
        if isinstance(n, _ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], _ast.Name):
            consts.setdefault(n.targets[0].id, []).append(n)
    keep, todo = set(), list(roots)
    while todo:
        name = todo.pop()
        if name in keep:
            continue
        if name in funcs:
            keep.add(name)
            todo += sorted(_unbound_loads(_ast.get_source_segment(src, funcs[name])))
        elif name in consts:
            if len(consts[name]) != 1:
                raise SystemExit(f"build_level_scripts: {what}: {name} is assigned {len(consts[name])}x")
            try:
                _ast.literal_eval(consts[name][0].value)
            except ValueError:
                raise SystemExit(f"build_level_scripts: {what}: {name} is not a literal constant")
            keep.add(name)
        elif name not in provided:
            raise SystemExit(f"build_level_scripts: {what}: {name!r} is not defined in the cell "
                             "or by the cells emitted before it")
    parts = [_ast.get_source_segment(src, n) for n in tree.body
             if (isinstance(n, _ast.FunctionDef) and n.name in keep)
             or (isinstance(n, _ast.Assign) and len(n.targets) == 1
                 and isinstance(n.targets[0], _ast.Name) and n.targets[0].id in keep)]
    if header is None:
        header = (f"# Definitions extracted from the LVL_0 QC cell for LVL_2: {sorted(keep)}.\n"
                  "# The cell's permutation nulls, threshold diagnostics and plots are NOT run here.\n")
    else:
        header = header.format(keep=sorted(keep))
    return keep, header + "\n" + "\n\n\n".join(parts) + "\n"


L2_QC_ROOTS = ("add_trial_markers", "periodic_periods")
_L2_PRE = [IMPORTS_CELL, DIRS_CELL, cfg_cell["LVL_0_CONFIG"]]
_provided = set().union(_top_names(BLAS),
                        _top_names(ARGS.format(CFG="LVL_2_CONFIG", DESC="", EXTRA=L2_EXTRA)),
                        _top_names(OVERRIDE.format(CFG="LVL_2_CONFIG")),
                        *(_top_names(C[i]) for i in _L2_PRE))
_L2_QC_KEEP, L2_QC_SRC = extract_defs(C[L0_QC], L2_QC_ROOTS, _provided, "LVL_0 QC cell")
# Nothing else of the QC cell may be needed downstream: any name it defines but we did
# not keep must not be read (without being bound locally) by an LVL_2-script cell.
_dropped = _top_names(C[L0_QC]) - _L2_QC_KEEP
for _i in [L1_FILTERS, L1_PIVOT] + L2_CELLS:
    _hit = _unbound_loads(C[_i]) & _dropped
    if _hit:
        raise SystemExit(f"build_level_scripts: cell {_i} reads {sorted(_hit)} from the LVL_0 QC "
                         "cell, which lvl2.py does not run in full")


def l2_inject(i, src):
    if i == DIRS_CELL:
        return _log_inject(src)
    if i == L0_QC:                    # definitions only; see extract_defs
        return L2_QC_SRC
    if i == L2_LOAD:
        for _f in ("long", "features", "results"):   # notebook: LVL1_HANDOFF pin; script: --lvl1-input
            src = _sub1(src, 'pd.read_csv(f"{LVL1_HANDOFF}_%s.csv")' % _f,
                        'pd.read_csv(f"{_L1}_%s.csv")' % _f, f"LVL_2 {_f} load")
        anchor = 'results_df          = pd.read_csv(f"{_L1}_results.csv")'
        src = _sub1(src, anchor, anchor + L2_SELECT, "LVL_2 condition select")
        src = _sub1(src, 'open(f"{LVL1_HANDOFF}_meta.json")', 'open(f"{_L1}_meta.json")', "LVL_2 meta load")
        src = _sub1(src, L2_RUN_LOG, L2_RUN_LOG_SCRIPT, "LVL_2 warnings log")
        return '_L1 = str(LVL_OUTS / str(_args.lvl1_input).removesuffix("_long.csv"))\n' + src
    if i == L2_SAVE:                  # shared files; only the full run writes them
        _save = ('multimetric_df.to_csv(_out, index=False)\n'
                 '    print(f"\\nSaved: {_out}  ({len(multimetric_df)} rows)")\n'
                 '    _mm_save_null()')
        return _sub1(src, _save, 'if _args.export:\n        ' + _save.replace('\n', '\n    '),
                     "LVL_2 save")
    if i in L2_SKIP:                  # H2 tests, design tests, post hoc analyses, exports; Step 8 needs none
        return _guard(src)
    return src


L2_TAIL = '''
# ---------------------------------------------------------------- sweep result rows
if _args.out:
    _stem = str(_args.out).removesuffix(".csv")
    _cfg = {f"cfg_{_k}": repr(_v) for _k, _v in _overrides.items()}
    _design = SOURCE_DESIGN               # the design each block matrix's own fit reports ([cell 29])
    _key = lambda d: (d["id"].astype(str) + "_" + d["session"].astype(float).astype(int).astype(str)
                      + "_" + d["block"].astype(float).astype(int).astype(str))

    def _rule_cols(d):
        """Split multi-rule arm names "<arm>·<rule>" into Removal_Method + Rule.
        Rule is NaN for inattent_behav and for single-rule runs."""
        if len(d) and "Removal_Method" in d.columns:
            _parts = d["Removal_Method"].astype(str).str.split("·", n=1)
            d = d.assign(Removal_Method=_parts.str[0], Rule=_parts.str[1])
        return d

    # H2: flagged vs unflagged blocks on the three features, and the flagged block keys
    _h2, _flagged = [], []
    for _src, _bm in block_matrices.items():
        for _rm, _bb in bad_blocks_by_method.get(_src, {}).items():
            if not isinstance(_bb, pd.DataFrame) or len(_bm) == 0:
                continue
            _is = _key(_bm).isin(set(_key(_bb)) if len(_bb) else set())
            _flagged.append(_bb[["id", "session", "block"]].assign(Design=_design[_src], Removal_Method=_rm))
            _row = {"Design": _design[_src], "Removal_Method": _rm, "n_blocks": len(_bm),
                    "n_flagged": int(_is.sum()), "pct_blocks_flagged": 100 * _is.mean(),
                    "pct_trials_flagged": 100 * _bm.loc[_is, "n_trials"].sum() / _bm["n_trials"].sum()}
            for _f in ("adj_rt_level_block", "exp_rt_var_block", "exp_entropy_block", "rt_var_block", "entropy_block",
                       "rt_var_tr", "entropy_tr"):
                _a, _b = _bm.loc[_is, _f].dropna(), _bm.loc[~_is, _f].dropna()
                _ok = len(_a) > 1 and len(_b) > 1
                _sd = np.sqrt(((len(_a) - 1) * _a.var() + (len(_b) - 1) * _b.var()) / (len(_a) + len(_b) - 2)) if _ok else np.nan
                _row[f"{_f}_flagged"], _row[f"{_f}_unflagged"] = _a.mean(), _b.mean()
                _row[f"{_f}_d"] = (_a.mean() - _b.mean()) / _sd if _ok and _sd > 0 else np.nan
                _row[f"{_f}_p"] = stats.mannwhitneyu(_a, _b).pvalue if _ok else np.nan
            _h2.append(_row)
    # A labeller Step 5 could not fit on a block matrix (FIT_FAILURES, [cell 42]) has no flags: one row with n_flagged
    # empty and the reason in fit_failure, so the sweep never counts it as flagging 0 units (no fit_failure column when
    # every fit was made).
    for (_src, _rm), _why in FIT_FAILURES.items():
        _h2.append({"Design": _design[_src], "Removal_Method": _rm, "n_blocks": len(block_matrices.get(_src, [])),
                    "n_flagged": np.nan, "fit_failure": _why})
    # Provenance: hash of THIS script's bytes (see sweep_provenance.py).
    import hashlib as _hashlib
    _PIPELINE_FP = _hashlib.sha256(Path(__file__).read_bytes()).hexdigest()[:16]
    _rule_cols(pd.DataFrame(_h2)).assign(pipeline_fingerprint=_PIPELINE_FP, **_cfg).to_csv(f"{_stem}_h2.csv", index=False)
    _rule_cols(pd.concat(_flagged) if _flagged else
               pd.DataFrame(columns=["id", "session", "block", "Design", "Removal_Method"])).to_csv(f"{_stem}_flagged.csv",
                                                                                                 index=False)
    # The behavioural heuristic this run applied, every setting with its source ([cell 29]).
    if "inattent_behav" in LVL_2_CONFIG["irr_removal_methods"]:
        with open(f"{_stem}_heuristic.json", "w") as _f:
            json.dump({"heuristic": TRIAL_MARKER_CONFIG, "lvl1_input": Path(_L1).name,
                       "condition": _args.condition, "segmentation": SEGMENTATION, "designs": DESIGNS,
                       "design_labels": {d: DESIGN_LABEL[d] for d in DESIGNS}, "pipeline_fingerprint": _PIPELINE_FP},
                      _f, indent=2, default=str)
        print(f"  [out] {_stem}_heuristic.json")

    # H3: multimetric removal table. Written LAST -- the sweep treats its existence as "done".
    # A config that flags nothing produces no rows; write the header so it still counts as done.
    if multimetric_df.empty:
        multimetric_df = pd.DataFrame(columns=["Scale", "Condition", "Removal_Method", "Design", "Pct_Removed"])
    _k_src = {**DESIGN_SRC, "participant": "participant"}
    _rule_cols(multimetric_df.assign(
        lvl1_input=Path(_L1).name, condition=_args.condition, pipeline_fingerprint=_PIPELINE_FP,
        selected_k=[best_k_by_method.get(_k_src.get(d), {}).get(rm)
                    for d, rm in zip(multimetric_df["Design"], multimetric_df["Removal_Method"])],
        **_cfg,
    )).to_csv(_args.out, index=False)
    print(f"  [out] {_args.out}  (+ _h2.csv, _flagged.csv)")
'''

emit("lvl2.py", _L2_PRE + [L0_QC, L1_FILTERS, L1_PIVOT] + L2_CELLS, "LVL_2_CONFIG",
     "LVL_2: block features, labelling, IRR removal comparison.",
     extra=L2_EXTRA, inject=l2_inject, tail=L2_TAIL, post_override=L2_OVERRIDE_SOURCE)

# The handoff pins and records are bound only by "# [notebook only]" cells. A script that still
# mentions one would fail with NameError at run time, so the build stops instead.
_NOTEBOOK_ONLY_NAMES = ("LVL0_HANDOFF", "LVL1_HANDOFF", "LVL0_RECORD", "LVL0_RECORD_PATH", "LVL1_META",
                        "LVL1_SWEEP", "LVL1_SELECTION", "LVL2_SWEEP", "LVL2_SELECTION")
for _s in ("lvl0.py", "lvl1.py", "lvl2.py"):
    _hits = sorted(n for n in _NOTEBOOK_ONLY_NAMES if re.search(rf"\b{n}\b", Path(_s).read_text()))
    if _hits:
        raise SystemExit(f"build_level_scripts: {_s} references notebook-only names {_hits}")
print("verified lvl0.py / lvl1.py / lvl2.py: no notebook-only names")


# ---------------------------------------------------------------- LVL_2 notebook: upstream cell and run notebook
# The LVL2 notebook is the template of the run notebook block_detection_and_removal_LVL2_all_rep.ipynb. Its notebook-only
# upstream cell holds the upstream code lvl2.py embeds (the LVL_0 config cell, the LVL_0 QC definitions LVL_2 uses, the
# RT-filter and pivot cells), written here, so the notebook runs exactly the script's upstream code and reads no other
# notebook. The run notebook is the template with RUN_NAME and n_jobs ([cell 0]: RUN_N_JOBS, top of this file) set. It
# is rewritten when its code differs from that (its outputs are kept when nothing changed); afterwards it is checked to
# differ from the template in those two settings only.
UPSTREAM_HEAD = "# [notebook only] UPSTREAM DEFINITIONS (written by build_level_scripts.py)"
REP_RUNS = ("all",)
L2_PATH = NOTEBOOKS[2]
if RUN_N_JOBS != "SET_ME" and (isinstance(RUN_N_JOBS, bool) or not isinstance(RUN_N_JOBS, int) or RUN_N_JOBS == 0):
    raise SystemExit(f"build_level_scripts: RUN_N_JOBS = {RUN_N_JOBS!r} (top of this file) must be a CPU count (int) "
                     'or "SET_ME"')


def _nb_write(path, nb):
    Path(path).write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


def _cell_src(c):
    return "".join(c.get("source", []))


def _set_src(c, text):
    c["source"] = text.splitlines(keepends=True)


def upstream_source():
    banner = lambda i: f"\n\n# ---------------- from [cell {i}] ----------------\n"
    return (UPSTREAM_HEAD + "\n# The upstream code lvl2.py embeds: the LVL_0 config cell ([cell 3]), the LVL_0 QC definitions LVL_2 "
            "uses ([cell 5]),\n# the RT filters ([cell 12]) and the long -> stimulus pivot ([cell 13]). Edit them in the "
            "LVL0 / LVL1 notebooks and rebuild."
            + banner(cfg_cell["LVL_0_CONFIG"]) + C[cfg_cell["LVL_0_CONFIG"]] + banner(L0_QC) + L2_QC_SRC
            + banner(L1_FILTERS) + C[L1_FILTERS] + banner(L1_PIVOT) + C[L1_PIVOT] + "\n")


_tpl = json.load(open(L2_PATH, encoding="utf-8"))
_up = [c for c in _tpl["cells"] if c["cell_type"] == "code" and _cell_src(c).startswith(UPSTREAM_HEAD)]
if len(_up) != 1:
    raise SystemExit(f"build_level_scripts: {L2_PATH.name}: expected one cell starting {UPSTREAM_HEAD!r}, found {len(_up)}")
if _cell_src(_up[0]) != upstream_source():
    _set_src(_up[0], upstream_source()); _up[0]["outputs"], _up[0]["execution_count"] = [], None
    _nb_write(L2_PATH, _tpl)
    print(f"wrote the upstream-definitions cell of {L2_PATH.name}")
# Every LVL2 notebook cell, notebook-only ones included, may read only the [cell 5] names the upstream cell defines.
for _c in _tpl["cells"]:
    if _c["cell_type"] == "code" and not _cell_src(_c).startswith(UPSTREAM_HEAD):
        _hit = _unbound_loads(_cell_src(_c)) & _dropped
        if _hit:
            raise SystemExit(f"build_level_scripts: an LVL2 notebook cell reads {sorted(_hit)} from the LVL_0 QC cell, "
                             f"which the upstream cell does not define: {_cell_src(_c)[:70]!r}")


# The run notebook's n_jobs line: [cell 0]'s one "n_jobs = ..." line, whatever value the template holds.
RUN_N_JOBS_LINE = re.compile(r"^n_jobs = .*$", flags=re.M)


def _rep_expected(run):
    nb = copy.deepcopy(_tpl)
    subs = {"input": ('RUN_NAME = None\n', f'RUN_NAME = "{run}"\n')}
    done = set()
    for c in nb["cells"]:
        if c["cell_type"] != "code":
            continue
        text = _cell_src(c)
        m = _LABEL.match(text.split("\n", 1)[0])
        key = int(m.group(1)) if m else ("input" if text.startswith("# [notebook only] LVL_2 INPUT") else None)
        if key in subs:
            old, new = subs[key]
            if text.count(old) != 1:
                raise SystemExit(f"build_level_scripts: run notebook {run}: anchor {old!r} found {text.count(old)}x")
            _set_src(c, text.replace(old, new, 1)); done.add(key)
        elif key == 0:
            _line = f"n_jobs = {RUN_N_JOBS!r}   # the run's CPUs: RUN_N_JOBS of build_level_scripts.py"
            text, _n = RUN_N_JOBS_LINE.subn(lambda _m: _line, text)
            if _n != 1:
                raise SystemExit(f"build_level_scripts: run notebook {run}: [cell 0] has {_n} lines matching "
                                 f"{RUN_N_JOBS_LINE.pattern!r}, not one")
            _set_src(c, text); done.add(key)
        c["outputs"], c["execution_count"] = [], None
    if done != set(subs) | {0}:
        raise SystemExit(f"build_level_scripts: run notebook {run}: settings not found {(set(subs) | {0}) - done}")
    return nb


if RUN_N_JOBS == "SET_ME":
    print('notice: RUN_N_JOBS (top of build_level_scripts.py) holds "SET_ME": the LVL2 run notebook stops at its '
          'settings check until it is set and the build rerun (README, "Settings")')
for _run in REP_RUNS:
    _path = L2_PATH.with_name(f"block_detection_and_removal_LVL2_{_run}_rep.ipynb")
    _exp = _rep_expected(_run)
    _old = json.load(open(_path, encoding="utf-8")) if _path.exists() else None
    _code = lambda nb: [(c["cell_type"], _cell_src(c)) for c in nb["cells"]]
    if _old is None or _code(_old) != _code(_exp):
        if _old is not None:
            _diff = [i for i, (a, b) in enumerate(zip(_code(_old), _code(_exp))) if a != b]
            print(f"  {_path.name}: {len(_diff)} cell(s) differed from the template (positions {_diff[:8]})")
        _nb_write(_path, _exp)
        print(f"wrote {_path.name}")
    _chk = json.load(open(_path, encoding="utf-8"))
    if _code(_chk) != _code(_exp):
        raise SystemExit(f"build_level_scripts: {_path.name} differs from the template beyond RUN_NAME / n_jobs")
    print(f"verified {_path.name}: the template with RUN_NAME and n_jobs set")


# ---------------------------------------------------------------- LVL1_report: upstream definitions
# LVL1_report.ipynb draws participants' sessions from a LVL_1 handoff with the LVL_1 detectors' feature columns and
# smoothing. Its notebook-only upstream cell holds the definitions it needs from the LVL_1 detection-methods cell,
# written here verbatim, so the report reads no other notebook.
L1R_PATH = Path("LVL1_report.ipynb")
L1_DETECT = cell_index("def apply_smoothing(", "LVL_1 detection-methods cell")
_L1R_KEEP, _L1R_DEFS = extract_defs(
    C[L1_DETECT], ("get_feature_column", "apply_smoothing"), {"np", "pd"}, "LVL_1 detection-methods cell",
    header=(f"# The definitions LVL1_report needs from the LVL_1 detection-methods cell ([cell {L1_DETECT}]): "
            "{keep}.\n# Edit them in the LVL1 notebook and rebuild.\n"))


def l1r_upstream_source():
    return UPSTREAM_HEAD + "\n" + _L1R_DEFS


_l1r = json.load(open(L1R_PATH, encoding="utf-8"))
_up1 = [c for c in _l1r["cells"] if c["cell_type"] == "code" and _cell_src(c).startswith(UPSTREAM_HEAD)]
if len(_up1) != 1:
    raise SystemExit(f"build_level_scripts: {L1R_PATH.name}: expected one cell starting {UPSTREAM_HEAD!r}, found {len(_up1)}")
if _cell_src(_up1[0]) != l1r_upstream_source():
    _set_src(_up1[0], l1r_upstream_source()); _up1[0]["outputs"], _up1[0]["execution_count"] = [], None
    _nb_write(L1R_PATH, _l1r)
    print(f"wrote the upstream-definitions cell of {L1R_PATH.name}")
# The report's other cells may read nothing else of the detection-methods cell.
_dropped1 = _top_names(C[L1_DETECT]) - _L1R_KEEP
for _c in _l1r["cells"]:
    if _c["cell_type"] == "code" and not _cell_src(_c).startswith(UPSTREAM_HEAD):
        _hit = _unbound_loads(_cell_src(_c)) & _dropped1
        if _hit:
            raise SystemExit(f"build_level_scripts: a {L1R_PATH.name} cell reads {sorted(_hit)} from the LVL_1 "
                             f"detection-methods cell, which its upstream cell does not define: {_cell_src(_c)[:70]!r}")
print(f"verified {L1R_PATH.name}: upstream definitions {sorted(_L1R_KEEP)} from [cell {L1_DETECT}]")
