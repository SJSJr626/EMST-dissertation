from itertools import product
import argparse
import ast
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

# stdout reaches a redirected log (e.g. ... 2>&1 | tee <log>) one line at a time, as on a terminal.
sys.stdout.reconfigure(line_buffering=True)

# ---------------------------------------------------------------- settings (README, "Settings")
# The absolute project folder holding code/, dset/ and dervatives/ (README, "Paths"; EMST /home/sjsuss626/EMST_files/sjs_dissertation)
PROJECT_ROOT = "SET_ME"
# Concurrent lvl1.py processes (each runs with --n-jobs 1): the CPUs of your slice, e.g. 8 for taskset -c 0-7 (EMST 30).
# --workers replaces it.
SWEEP_WORKERS = "SET_ME"

# Locations: everything is inside PROJECT_ROOT.
_OUT = Path(PROJECT_ROOT) / "dervatives" / "practical_application_generic"
CODE_DIR = Path(PROJECT_ROOT) / "code" / "practical_application_generic"   # lvl1.py
ERR_DIR = CODE_DIR / "errors"            # failed configs: <outdir>_<config>.err (the folder is made at the first one)
LVL_OUTS = _OUT / "lvl_outs"                                               # the handoff is read from here
SWEEPS_DIR = _OUT / "sweeps"                                               # --outdir is created here

sys.dont_write_bytecode = True   # as python -B: importing sweep_provenance writes no __pycache__/
from sweep_provenance import check_outdir, grid_fingerprint, pipeline_fingerprint


def script_config(path, name):
    """The dict literal `name = {...}` of a generated script (the notebook's config cell), as Python values."""
    node = [n for n in ast.parse(Path(path).read_bytes()).body if isinstance(n, ast.Assign)
            and [getattr(t, "id", None) for t in n.targets] == [name]]
    if len(node) != 1:
        raise SystemExit(f"{Path(path).name}: {len(node)} top-level {name} assignments, not one")
    return ast.literal_eval(node[0].value)


def script_settings(path, names):
    """The literal values of the first top-level assignments `name = ...` of a generated script ([cell 0] / [cell 2]
    settings such as n_jobs), {name: value}; a name without a literal assignment is absent."""
    out = {}
    for n in ast.parse(Path(path).read_bytes()).body:
        if isinstance(n, ast.Assign) and len(n.targets) == 1 and getattr(n.targets[0], "id", None) in names:
            try:
                out.setdefault(n.targets[0].id, ast.literal_eval(n.value))
            except ValueError:
                pass
    return out


ap = argparse.ArgumentParser(description="LVL_1 knob sweep (random-subset capable); dynamic segmentation only. The "
                                         "grid is derived from lvl1.py's LVL_1_CONFIG (the LVL1 notebook's [cell 9]).")
ap.add_argument("--lvl0-input", required=True,
                help="LVL_0 handoff csv in LVL_OUTS, e.g. lv0_out_<ts>.csv")
ap.add_argument("--condition", default="all", choices=["all"],
                help="every condition of the handoff (the pooled run)")
ap.add_argument("--subsample", type=int, default=0, help="participants; 0 = all")
ap.add_argument("--seed", type=int, default=0, help="subsample draw / rep index")
ap.add_argument("--workers", type=int, default=None,
                help="concurrent lvl1.py processes; default SWEEP_WORKERS (top of this script)")
ap.add_argument("--limit", type=int, default=0, help="only run the first N configs")
ap.add_argument("--sample", default=None,
                help="random subset of the grid: a count (2000) or a fraction (0.05)")
ap.add_argument("--grid-seed", type=int, default=0,
                help="seed for the --sample draw; same seed = same subset")
ap.add_argument("--outdir", default="_sweep_lvl1_all",
                help="sweep folder, created in SWEEPS_DIR")
ap.add_argument("--check-only", action="store_true",
                help="validate --outdir provenance (see sweep_provenance.py) and exit; runs nothing")
args = ap.parse_args()

# ---------------------------------------------------------------- settings check
# Stops listing every setting this sweep needs that still holds "SET_ME": the two above (SWEEP_WORKERS only when
# configurations run), every value of lvl1.py's LVL_1_CONFIG (each would stop every lvl1.py run of the sweep; in dynamic
# segmentation every LVL_1 setting is required), and lvl1.py's own n_jobs, PROJECT_ROOT and INPUT_LONG_FILE. The values
# are read from lvl1.py, which is built from the level notebooks: a value is set in its notebook cell (LVL_1_CONFIG: the
# LVL1 notebook's [cell 9]), and build_level_scripts.py writes it into lvl1.py.
WORKERS = args.workers or SWEEP_WORKERS
_SET_ME = [("PROJECT_ROOT", PROJECT_ROOT, "top of this script",
             'the absolute project folder holding code/, dset/ and dervatives/ (README, "Paths"); EMST '
             '/home/sjsuss626/EMST_files/sjs_dissertation'),
           ("SWEEP_WORKERS (or --workers)", None if args.check_only else WORKERS, "top of this script",
            "concurrent lvl1.py processes (each with --n-jobs 1): the CPUs of your slice, e.g. 8 for taskset -c 0-7; EMST 30")]
_L1 = {}
if PROJECT_ROOT != "SET_ME":
    if not Path(PROJECT_ROOT).is_absolute():
        raise SystemExit(f'PROJECT_ROOT = {PROJECT_ROOT!r} is not an absolute path (top of this script; README, "Paths")')
    if not (CODE_DIR / "lvl1.py").is_file():
        raise SystemExit(f"{CODE_DIR / 'lvl1.py'} is missing: build it from the level notebooks "
                         "(python -B build_level_scripts.py; README, step 4)")
    _L1 = script_config(CODE_DIR / "lvl1.py", "LVL_1_CONFIG")
    if _L1.get("segmentation") == "predefined":
        raise SystemExit(f"lvl1.py: LVL_1_CONFIG['segmentation'] is 'predefined' (blocks from column "
                         f"{_L1.get('predefined_block_col')!r}): predefined segmentation has no LVL1 sweep (README). "
                         "Skip steps 5-6 and run the LVL1 notebook with LVL1_SWEEP = None.")
    # what to set and the EMST value: the level notebooks' own guide (SET_ME_GUIDE, [cell 2], built into lvl1.py)
    _GUIDE = script_config(CODE_DIR / "lvl1.py", "SET_ME_GUIDE")
    _what = lambda key, how: f"{_GUIDE[key][1]}; {how}" if key in _GUIDE else how
    _SET_ME += [(f"LVL_1_CONFIG[{k!r}]", v, "lvl1.py, built from the LVL1 notebook [cell 9]",
                 _what(f"LVL_1_CONFIG[{k!r}]", "set it in the LVL1 notebook [cell 9] and rebuild (python -B "
                       "build_level_scripts.py)"))
                for k, v in _L1.items()]
    # The script's own [cell 0] / [cell 2] settings. lvl1.py stops on an unset path itself, but every sweep run replaces
    # n_jobs (--n-jobs 1): an unset n_jobs would pass, and setting it later changes lvl1.py's fingerprint, so the sweep
    # would describe another script.
    _own = script_settings(CODE_DIR / "lvl1.py", ("n_jobs", "PROJECT_ROOT", "INPUT_LONG_FILE"))
    _SET_ME += [(k, _own.get(k), f"lvl1.py, built from [cell {c}] of the three level notebooks",
                 _what(k, f"set it in [cell {c}] of the three level notebooks (identical copies) and rebuild (python -B "
                          "build_level_scripts.py)")) for k, c in (("n_jobs", 0), ("PROJECT_ROOT", 2), ("INPUT_LONG_FILE", 2))]
_unset = [s for s in _SET_ME if isinstance(s[1], str) and s[1] == "SET_ME"]
if _unset:
    raise SystemExit(f'settings check (launch_LV1_sweep_random.py): {len(_unset)} setting(s) still hold "SET_ME". Set '
                     'each, then run again (README, "Settings"):\n'
                     + "\n".join(f"  - {k}  ({where})\n      {what}" for k, _, where, what in _unset))
if not args.check_only and (isinstance(WORKERS, bool) or not isinstance(WORKERS, int) or WORKERS < 1):
    raise SystemExit(f"SWEEP_WORKERS (or --workers) = {WORKERS!r}: a positive whole number of processes")
_MBS = _L1["min_block_size"]
if isinstance(_MBS, bool) or not isinstance(_MBS, int) or _MBS < 1:
    raise SystemExit(f"lvl1.py: LVL_1_CONFIG['min_block_size'] = {_MBS!r}: a positive whole number of stimuli "
                     "(the LVL1 notebook [cell 9])")


# ---------------------------------------------------------------- the grid
# Every value comes from lvl1.py's LVL_1_CONFIG (the LVL1 notebook's [cell 9], where each is documented), so nothing is
# set twice. A list is swept (its values are positions of the grid); a scalar is passed to every run. Both are recorded
# in the cfg_ columns of every result file.
knobs = {
    "feature_rt_transform": [_L1["feature_rt_transform"]],
    "use_residuals": _L1["use_residuals"],

    # The RTs and residuals arrive from LVL_0; LVL_1 applies its own row-level RT filters.
    "pr_stim_drop": _L1["pr_stim_drop"],
    "min_rt_thresh": _L1["min_rt_thresh"],
    "max_rt_thresh": _L1["max_rt_thresh"],
    # How a rating rejected by min/max_rt_thresh reaches the Level-1 RT features. NO default: lvl1.py refuses to run
    # without it on its command line, so it is always passed.
    "rt_threshold_na_handling": [_L1["rt_threshold_na_handling"]],
    "ses_wise_drift": _L1["ses_wise_drift"],
    "age_adjust_drift_residuals": _L1["age_adjust_drift_residuals"],

    "smoothing_method": _L1["smoothing_method"],

    "min_block_size": [_MBS],
    # pelt_jump must divide min_block_size, so the nominal minimum block is the effective one: the jumps of 1, 2 and 5
    # that do (jumps_for, LVL1 [cell 11]).
    "pelt_jump": [j for j in (1, 2, 5) if _MBS % j == 0],

    "cp_k": [_L1["cp_k"]],
    # The smoothing window (stimuli): the odd widths 1-7 below min_block_size (LVL1 [cell 11]: a centred window is odd,
    # and a window as wide as the minimum block cannot resolve it).
    "smoothing_window": [w for w in (1, 3, 5, 7) if w < _MBS],

    "derivative_filter_size": [_L1["derivative_filter_size"]],
    "mad_window_size": [_L1["mad_window_size"]],
    # Rolling-window minimum (non-missing) observations; window edges stay NaN and inherit the neighbouring block.
    "min_periods": _L1["min_periods"],
    # HMM EM stops when |delta log-likelihood| < hmm_tol (not the signed delta), within hmm_n_iter iterations.
    "hmm_tol": _L1["hmm_tol"],
    "hmm_n_iter": _L1["hmm_n_iter"],

    # The validation test behind the effect size
    "validate_test": _L1["validate_test"],

    # --- sweep-mode suppression -------------------------------------------------
    # None of these change the numbers. They remove per-config work that only the
    # winning run needs, which the concurrent workers would otherwise duplicate.
    #
    # Never render PNGs during a sweep: the workers share one FIG_DIR and one
    # figure counter, so they collide and the images are meaningless anyway.
    "save_figures": False,

    # None => skip sister/control block generation. The LVL_1 summary (effect size,
    # sig%, corr%) comes from results_df, which that step never touches. The LVL1
    # notebook run (step 7) writes the controls with LVL_1_CONFIG's control_block_count.
    "control_block_count": None,
}

SWEPT = ["min_block_size", "feature_rt_transform", "pelt_jump", "cp_k",
         "smoothing_window", "derivative_filter_size", "mad_window_size",
         "rt_threshold_na_handling"]
if knobs["rt_threshold_na_handling"] == [None]:
    raise SystemExit("rt_threshold_na_handling must be set (LVL_1_CONFIG, the LVL1 notebook [cell 9]): it has no default")

runs = list(product(*(knobs[k] for k in SWEPT)))
print(f"grid: {len(runs):,} configurations")
if not runs:
    raise SystemExit(f"the grid is empty: no smoothing window below min_block_size = {_MBS}")
GRID = list(runs)                       # full grid; config ids are positions in it


# =============================================================================
# DRIVER
# =============================================================================
# Fixed (non-list) entries in `knobs` are passed to EVERY run, so the overrides
# declared above take effect. lvl1.py rejects any knob that is not in LVL_1_CONFIG,
# so a typo fails loudly.
FIXED = {k: v for k, v in knobs.items() if not isinstance(v, list)}

LVL0_INPUT = LVL_OUTS / args.lvl0_input
if not LVL0_INPUT.is_file():
    raise SystemExit(f"--lvl0-input {args.lvl0_input!r}: {LVL0_INPUT} not found")
OUTDIR = SWEEPS_DIR / args.outdir               # created by check_outdir()

# Pair every config with its ORIGINAL position in the full grid. Output files are
# named by that original index, not by position in the sampled order, so a random
# subset is a down-payment on the full sweep: run the full grid into the same
# --outdir later and it skips whatever this run already produced.
indexed = list(enumerate(runs))

if args.sample:
    import random
    n = float(args.sample)
    n = int(round(n * len(indexed))) if n < 1 else int(n)
    n = max(1, min(n, len(indexed)))
    random.Random(args.grid_seed).shuffle(indexed)
    indexed = indexed[:n]
    indexed.sort()                      # run in grid order for readable progress
    print(f"random sample: {n:,} of {len(runs):,} configs "
          f"({100*n/len(runs):.1f}%), grid-seed={args.grid_seed}")
if args.limit:
    indexed = indexed[:args.limit]

runs = indexed
print(f"checking {len(runs):,} configs -> {OUTDIR}" if args.check_only else f"running {len(runs):,} configs on {WORKERS} workers -> {OUTDIR}")
print(f"condition={args.condition} subsample={args.subsample or 'all'} seed={args.seed}")
print(f"swept: {', '.join(f'{k} {knobs[k]}' for k in SWEPT)}")
print(f"fixed overrides: {FIXED}")


def _same(a, b):
    """cfg_* values are written as repr() of the parsed CLI value ('partial' -> "'partial'")."""
    a, b = str(a).strip("'\""), str(b).strip("'\"")
    try:
        return float(a) == float(b)
    except ValueError:
        return a == b


def run_one(idx, params):
    out = OUTDIR / f"cfg{idx:06d}.csv"
    if out.exists():                       # resumable -- only if it holds THIS grid position
        row = pd.read_csv(out, nrows=1)
        stale = {k: (row[f"cfg_{k}"].iloc[0] if f"cfg_{k}" in row.columns else None, v)
                 for k, v in zip(SWEPT, params)
                 if not len(row) or f"cfg_{k}" not in row.columns or not _same(row[f"cfg_{k}"].iloc[0], v)}
        if stale:
            raise SystemExit(f"{out.name} was written with different swept knobs "
                             f"(knob: file vs grid): {stale}. Use a fresh --outdir.")
        (ERR_DIR / f"{OUTDIR.name}_cfg{idx:06d}.err").unlink(missing_ok=True)   # an earlier failure's record
        return str(out)
    cmd = [sys.executable, "-B", str(CODE_DIR / "lvl1.py"), "--n-jobs", "1",
           "--lvl0-input", str(LVL0_INPUT),
           "--condition", args.condition, "--subsample", str(args.subsample),
           "--seed", str(args.seed), "--out", str(out)]
    for name, value in zip(SWEPT, params):
        cmd += [f"--{name}", str(value)]
    for name, value in FIXED.items():
        cmd += [f"--{name}", str(value)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=CODE_DIR)
    if r.returncode != 0:
        ERR_DIR.mkdir(parents=True, exist_ok=True)
        (ERR_DIR / f"{OUTDIR.name}_cfg{idx:06d}.err").write_text(r.stdout[-4000:] + r.stderr[-4000:])
        return None
    (ERR_DIR / f"{OUTDIR.name}_cfg{idx:06d}.err").unlink(missing_ok=True)       # an earlier failure's record
    return str(out)


# Provenance of this run. Resuming is allowed ONLY into a directory written by the same
# lvl1.py (byte hash), LVL_0 handoff, sample and grid; otherwise the launcher stops.
PROVENANCE = {"script": "lvl1.py", "pipeline_fingerprint": pipeline_fingerprint(CODE_DIR / "lvl1.py"),
              "lvl0_input": LVL0_INPUT.name, "condition": args.condition,
              "subsample": args.subsample, "seed": args.seed,
              "grid": grid_fingerprint([list(r) for r in GRID] + [FIXED])}
FILE_KEYS = {k: PROVENANCE[k] for k in
             ("pipeline_fingerprint", "lvl0_input", "condition", "subsample", "seed")}


if __name__ == "__main__":
    _n = check_outdir(OUTDIR, PROVENANCE, r"cfg\d{6}", FILE_KEYS, write=not args.check_only)
    print(f"provenance OK: {OUTDIR} ({_n} existing result file(s) match "
          f"lvl1.py {PROVENANCE['pipeline_fingerprint']} / {PROVENANCE['lvl0_input']})")
    if args.check_only:
        raise SystemExit(0)
    t0 = time.time()
    paths = Parallel(n_jobs=WORKERS, backend="loky", verbose=10)(
        delayed(run_one)(i, p) for i, p in runs)
    el = time.time() - t0
    ok = [p for p in paths if p]
    print(f"\n{len(ok)}/{len(runs)} ok in {el/3600:.2f} h ({el/max(len(runs),1):.1f}s per config)")
    failed = [f"cfg{i:06d}" for (i, _), p in zip(runs, paths) if not p]
    if failed:
        print(f"FAILED: {len(failed)} configuration(s) are not in the pooled table (their output: "
              f"{ERR_DIR}/{OUTDIR.name}_<config>.err): {', '.join(failed)}")
    if runs and not ok:
        _err = ERR_DIR / f"{OUTDIR.name}_{failed[0]}.err"
        _last = [ln for ln in _err.read_text().splitlines() if ln.strip()][-1:] if _err.is_file() else []
        raise SystemExit(f"no configuration of the grid succeeded ({len(runs)} run), so there is nothing to pool: each "
                         f"lvl1.py run's output is in {ERR_DIR}/{OUTDIR.name}_<config>.err"
                         + (f"; {_err.name} ends: {_last[0]}" if _last else "")
                         + ". Fix the cause (e.g. a setting in [cell 9], then rebuild) and run the launcher again into a "
                           "fresh --outdir")

    if ok:
        df = pd.concat([pd.read_csv(p) for p in ok], ignore_index=True)
        res = OUTDIR / "sweep_results.csv"
        df.to_csv(res, index=False)
        print(f"pooled -> {res}  ({len(df):,} rows)")

        # ---- winner: highest effect size, with the two significance rates shown ----
        eff = "avg_effsize"
        cfg = [c for c in df.columns if c.startswith("cfg_")]
        keep = [c for c in [eff, "avg_sig%", "avg_corr_sig%", "blocks_mean",
                            "n_validatable"] if c in df.columns]
        rank = (df.groupby(["method"] + cfg, dropna=False)[keep].mean()
                  .reset_index().sort_values(eff, ascending=False))
        rank.to_csv(OUTDIR / "sweep_ranking.csv", index=False)
        print(f"\nTOP 15 by {eff} (method x config):")
        print(rank.head(15).to_string(index=False))
        print(f"\nBEST METHOD overall (mean {eff} across configs):")
        print(df.groupby("method")[keep].mean().sort_values(eff, ascending=False)
                .head(10).round(4).to_string())
