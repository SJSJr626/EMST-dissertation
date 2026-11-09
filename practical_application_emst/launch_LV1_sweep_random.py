from itertools import product
import argparse
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

# Locations: everything is inside /home/sjsuss626/EMST_files/sjs_dissertation.
CODE_DIR   = Path("/home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst")                # lvl1.py
ERR_DIR    = Path("/home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst/errors")              # failed configs: <outdir>_<config>.err
LVL_OUTS   = Path("/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs")           # the handoff is read from here
SWEEPS_DIR = Path("/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/sweeps")             # --outdir is created here

sys.dont_write_bytecode = True   # as python -B: importing sweep_provenance writes no __pycache__/
from sweep_provenance import check_outdir, grid_fingerprint, pipeline_fingerprint


knobs = {
    # feature_rt_transform options include "raw" | "log" | "boxcox"; fixed to "log".
    # Decision based on literature review and the properties of the residuals.
    # See [list of references].
    "feature_rt_transform": ["log"],
    "use_residuals": True, 

    # Remember: filtering needs to be reset; all RTs/residuals are imported from LVL_0.
    "pr_stim_drop": 0,    
    "min_rt_thresh": 0,            
    "max_rt_thresh": 90, # If "use_residuals": True, sensor resdiuals from RTs this high
    # How a rating rejected by min/max_rt_thresh reaches the Level-1 RT features (LVL_1_CONFIG
    # notes in the notebook). NO default: lvl1.py refuses to run without it, so it is always
    # passed. Fixed at "bfill" (an a-priori choice); list all four modes here to sweep
    # them (48 configs).
    "rt_threshold_na_handling": ["bfill"],
    "ses_wise_drift": True,
    "age_adjust_drift_residuals": True,  # bool: regress out linear age effect

    # Set smoothing type
    "smoothing_method": "gaussian",

    # With these settings above, I am importing age-adjusted for LVL2 handoff,
    # log-transformed RT residuals from LVL_0.
    # Age adjustments do not affect LVL1, as segmentation is within particpant.

    ### List ###
    #"min_block_size": [20, 25, 30, 35, 40],
    "min_block_size": [20], # based on average time spent on stimulus Esterman "4min" in/out zone epoch

    # Whatever list is used, pelt_jump MUST always be divisible by min_block size.
    "pelt_jump_even_min_block_size": [1, 2, 5], 
    #"pelt_jump_odd_min_block_size": [1, 5],

    # EXAMPLE:"cp_k": [1.5, 2, 2.5, 3, 3.5, 4, 4.5, 5],
    # EXAMPLE: "smoothing_window": [1, 3, 5, 7, 9, 11],
    "cp_k": [3], # currently fixed to a priori value often used
    "smoothing_window": [1, 3, 5, 7], # our per stimulu estimates larger that Esterman, so sweeping below filer size

    #"derivative_filter_size": [5, 7, 9, 11, 13, 15, 17, 19],
    #"mad_window_size": [5, 7, 9, 11, 13, 15, 17, 19],
    "derivative_filter_size": [9], # based on average time spent on stimulus Esterman 2min windows
    "mad_window_size": [9], # based on average time spent on stimulus Esterman 2min windows
    # Rolling-window minimum (non-missing) observations: centred window 9 -> first
    # estimate at stimulus 4; edges stay NaN and inherit the neighbouring block.
    "min_periods": 8,
    # HMM EM stops when |delta log-likelihood| < hmm_tol (not the signed delta).
    "hmm_tol": 1e-8,
    # EM iteration cap: 2,500 converges every fit at hmm_tol=1e-8 (slowest 1,616).
    "hmm_n_iter": 2500,

    # "HMM_states": [2, 3],  # Already baked into the methods list.

    # Assure correct validation test is being ran to get correct effect size
    "validate_test": "kruskal",

    # --- sweep-mode suppression -------------------------------------------------
    # None of these change the numbers. They remove per-config work that only the
    # winning run needs, which 30 concurrent workers were otherwise duplicating.
    #
    # Never render PNGs during a sweep: all 30 workers share one FIG_DIR and one
    # figure counter, so they collide and the images are meaningless anyway.
    "save_figures": False,

    # None => skip sister/control block generation. The LVL_1 summary (effect size,
    # sig%, corr%) comes from results_df, which that step never touches. Regenerate
    # controls by running the winning config in the notebook with "per_session".
    "control_block_count": None,

}


# Build runs so pelt_jump depends on whether min_block_size is odd or even.
runs = []

for min_block_size in knobs["min_block_size"]:

    if min_block_size % 2 == 0:
        pelt_jumps = knobs["pelt_jump_even_min_block_size"]
    else:
        pelt_jumps = knobs["pelt_jump_odd_min_block_size"]

    for values in product(
        knobs["feature_rt_transform"],
        pelt_jumps,
        knobs["cp_k"],
        knobs["smoothing_window"],
        knobs["derivative_filter_size"],
        knobs["mad_window_size"],
        knobs["rt_threshold_na_handling"],
    ):
        runs.append((
            min_block_size,
            *values,
        ))


print(f"grid: {len(runs):,} configurations")
GRID = list(runs)                       # full grid; config ids are positions in it


# =============================================================================
# DRIVER
# =============================================================================
# Fixed (non-list) entries in `knobs` are passed to EVERY run, so the overrides
# declared above take effect. lvl1.py rejects any knob that is not in LVL_1_CONFIG,
# so a typo fails loudly.
FIXED = {k: v for k, v in knobs.items()
         if not isinstance(v, list) and not k.startswith("pelt_jump_")}

SWEPT = ["min_block_size", "feature_rt_transform", "pelt_jump", "cp_k",
         "smoothing_window", "derivative_filter_size", "mad_window_size",
         "rt_threshold_na_handling"]
if "rt_threshold_na_handling" not in SWEPT and "rt_threshold_na_handling" not in FIXED:
    raise SystemExit("rt_threshold_na_handling must be set (swept or fixed): it has no default")

ap = argparse.ArgumentParser(description="LVL_1 knob sweep (random-subset capable)")
ap.add_argument("--lvl0-input", required=True,
                help="LVL_0 handoff csv in LVL_OUTS, e.g. lv0_out_<ts>.csv")
ap.add_argument("--condition", default="both", choices=["T2", "T3", "both"])
ap.add_argument("--subsample", type=int, default=0, help="participants; 0 = all")
ap.add_argument("--seed", type=int, default=0, help="subsample draw / rep index")
ap.add_argument("--workers", type=int, default=31, help="concurrent lvl1.py processes")
ap.add_argument("--limit", type=int, default=0, help="only run the first N configs")
ap.add_argument("--sample", default=None,
                help="random subset of the grid: a count (2000) or a fraction (0.05)")
ap.add_argument("--grid-seed", type=int, default=0,
                help="seed for the --sample draw; same seed = same subset")
ap.add_argument("--outdir", default="_sweep_lvl1",
                help="sweep folder, created in SWEEPS_DIR")
ap.add_argument("--check-only", action="store_true",
                help="validate --outdir provenance (see sweep_provenance.py) and exit; runs nothing")
args = ap.parse_args()

LVL0_INPUT = LVL_OUTS / args.lvl0_input
if not LVL0_INPUT.is_file():
    raise SystemExit(f"--lvl0-input {args.lvl0_input!r}: {LVL0_INPUT} not found")
ERR_DIR.mkdir(parents=True, exist_ok=True)
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
print(f"running {len(runs):,} configs on {args.workers} workers -> {OUTDIR}")
print(f"condition={args.condition} subsample={args.subsample or 'all'} seed={args.seed}")
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
    paths = Parallel(n_jobs=args.workers, backend="loky", verbose=10)(
        delayed(run_one)(i, p) for i, p in runs)
    el = time.time() - t0
    ok = [p for p in paths if p]
    print(f"\n{len(ok)}/{len(runs)} ok in {el/3600:.2f} h ({el/max(len(runs),1):.1f}s per config)")
    failed = [f"cfg{i:06d}" for (i, _), p in zip(runs, paths) if not p]
    if failed:
        print(f"FAILED: {len(failed)} configuration(s) are not in the pooled table (their output: "
              f"{ERR_DIR}/{OUTDIR.name}_<config>.err): {', '.join(failed)}")

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
