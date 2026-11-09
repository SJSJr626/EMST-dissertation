from itertools import product
import argparse
import ast
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pandas as pd
from joblib import Parallel, delayed

# Locations: everything is inside /home/sjsuss626/EMST_files/sjs_dissertation.
CODE_DIR   = Path("/home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst")                # lvl2.py
ERR_DIR    = Path("/home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst/errors")              # failed configs: <outdir>_<config>.err
LVL_OUTS   = Path("/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs")           # the handoff is read from here
SWEEPS_DIR = Path("/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/sweeps")             # --outdir is created here

sys.dont_write_bytecode = True   # as python -B: importing sweep_provenance writes no __pycache__/
from sweep_provenance import check_outdir, grid_fingerprint, pipeline_fingerprint


# Passed to every run. Defaults come from the notebook's LVL_2_CONFIG (baked into
# lvl2.py); analysis_method is set with --analysis-method. use_residuals / feature_rt_transform / ses_wise_drift /
# age_adjust_drift_residuals are LVL_1 knobs: they arrive resolved in rt_input via
# --lvl1-input, and lvl2.py rejects them as unknown.
fixed = {
    "analysis_method": "PELT_Attention_comp",
    "save_figures": False,
    "pr_stim_drop": 0,
    "min_rt_thresh": 0,
    "max_rt_thresh": 90,
    "exp_pre_transform": "boxcox",
    "control_block_count": "per_session",
    "irr_icc_form": "ICC2",
    "kmeans_bootstrap_reps": 0,   # bootstrap ARI only feeds the "stability" k-metric; silhouette ignores it
}

# Cluster / GMM sweep: one list per swept knob (Cartesian product); the same exponent
# grid for both knobs (19 x 19 = 361 configs). Config ids are grid POSITIONS, so changing
# this list renumbers everything and means starting in a fresh --outdir. Narrow the range
# in the report, not here.
EXP_ALL = [0.01, 0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 1.25, 1.5, 1.75, 2.0,
           2.25, 2.5, 2.75, 3.0, 3.25, 3.5, 3.75, 4.0]

cluster_knobs = {
    "kmeans_exp_entropy_exponent": EXP_ALL,   # keep this ORDER: config ids are grid positions
    "kmeans_exp_rt_var_exponent":  EXP_ALL,
}
# best_k_metric None: every k in the k list is its own method (cluster_2, cluster_3,
# mixture_gmm_2, mixture_gmm_3) and all downstream statistics report each separately.
cluster_fixed = {
    "irr_removal_methods": ["cluster", "mixture_gmm"],
    "cluster_k_list": [2, 3],
    "cluster_best_k_metric": None,
    "gmm_k_list": [2, 3],
    "gmm_best_k_metric": None,
    "mixture_gmm_max_iter": 500,             # 500 (notebook: 1000) to save time on sweeps
    # Every labelling rule in ONE run: each cluster / GMM fit is labelled under all
    # three, and the result files carry a Rule column. The report's RULES picks which
    # to show. "speed" is the primary rule (with k = 3 the smallest component is often
    # an attentive subtype -- see the LVL_2_CONFIG note in the notebook).
    "worst_cluster_idx": ["speed", "size", "irr"],
    # None = the GMM arm follows the SWEPT kmeans_exp_entropy_exponent / kmeans_exp_rt_var_exponent. The notebook
    # pins these to the calibrated values, and inheriting that pin makes
    # the GMM identical in every config -- the whole grid collapses to one result.
    "mixture_gmm_exp_entropy_exponent": None,
    "mixture_gmm_exp_rt_var_exponent": None,
}

GROUP = "cluster"

IRR_METRICS = ["alpha", "icc", "kappa", "splithalf_between", "splithalf_within"]

ap = argparse.ArgumentParser(description="LVL_2 knob sweep (random-subset capable)")
ap.add_argument("--lvl1-input", required=True,
                help="LVL_1 handoff prefix in LVL_OUTS, e.g. lv1_out_<ts>")
ap.add_argument("--analysis-method", default=fixed["analysis_method"],
                help="LVL_1 detector whose blocks are labelled (dynamic design), e.g. "
                     "PELT_Attention_comp or HMM_Attention_comp_3; one sweep (and --outdir) per method")
ap.add_argument("--condition", default="both", choices=["T2", "T3", "both"],
                help="restrict features, clustering, labelling and IRR to one condition")
ap.add_argument("--workers", type=int, default=31, help="concurrent lvl2.py processes")
ap.add_argument("--limit", type=int, default=0, help="only run the first N configs")
ap.add_argument("--sample", default=None,
                help="random subset of the grid: a count (50) or a fraction (0.25)")
ap.add_argument("--grid-seed", type=int, default=0,
                help="seed for the --sample draw; same seed = same subset")
ap.add_argument("--metrics", default="alpha,icc,kappa,splithalf_between,splithalf_within",
                help="IRR metrics Step 8 computes, comma-separated; e.g. alpha,kappa for a fast calibration sweep")
ap.add_argument("--outdir", default="_sweep_lvl2",
                help="sweep folder, created in SWEEPS_DIR")
# Supplementary grids (e.g. one new exponent value) go in their OWN --outdir; the LVL2
# report pools several SWEEP_DIRS. Omitted = EXP_ALL, i.e. the unchanged main grid.
ap.add_argument("--entropy-exponents", default=None,
                help="comma-separated kmeans_exp_entropy_exponent values (default: EXP_ALL)")
ap.add_argument("--rt-var-exponents", default=None,
                help="comma-separated kmeans_exp_rt_var_exponent values (default: EXP_ALL)")
ap.add_argument("--check-only", action="store_true",
                help="validate --outdir provenance (see sweep_provenance.py) and exit; runs nothing")
ap.add_argument("--stage", default="all", choices=["grid", "apriori", "stability", "all"],
                help="grid = the configurations; apriori = the a-priori standard (behavioural heuristic); "
                     "stability = bootstrap refits of the calibration candidates; all = the three in order")
args = ap.parse_args()
fixed["analysis_method"] = args.analysis_method

_exps = lambda v: EXP_ALL if v is None else [float(x) for x in v.split(",")]
cluster_knobs["kmeans_exp_entropy_exponent"] = _exps(args.entropy_exponents)
cluster_knobs["kmeans_exp_rt_var_exponent"] = _exps(args.rt_var_exponents)
runs_all = [{**fixed, **cluster_fixed, **dict(zip(cluster_knobs, v))}
            for v in product(*cluster_knobs.values())]
print(f"grid: {len(runs_all):,} configurations ({len(cluster_knobs['kmeans_exp_entropy_exponent'])}x"
      f"{len(cluster_knobs['kmeans_exp_rt_var_exponent'])} exponent pairs)")

L1_PREFIX = LVL_OUTS / str(args.lvl1_input).removesuffix("_long.csv")
_l1_missing = [s for s in ("_long.csv", "_features.csv", "_results.csv", "_meta.json")
               if not Path(f"{L1_PREFIX}{s}").is_file()]
if _l1_missing:
    raise SystemExit(f"--lvl1-input {args.lvl1_input!r}: missing {_l1_missing} beside {L1_PREFIX}")
_l1_blocks = json.load(open(f"{L1_PREFIX}_meta.json"))["block_columns"]
if f"block_{args.analysis_method}" not in _l1_blocks:
    raise SystemExit(f"--analysis-method {args.analysis_method!r}: {L1_PREFIX.name} has no "
                     f"block_{args.analysis_method} column; its detectors are "
                     f"{sorted(c.removeprefix('block_') for c in _l1_blocks if not c.startswith('block_Fixed_'))}")
ERR_DIR.mkdir(parents=True, exist_ok=True)
OUTDIR = SWEEPS_DIR / args.outdir               # created by check_outdir()
print(f"analysis method: {args.analysis_method}  (control: Fixed_{args.analysis_method}_based)")
# Keep each config's ORIGINAL grid index, so a sampled run is a down-payment on the
# full grid: a later full run into the same --outdir skips what already exists.
indexed = list(enumerate(runs_all))
if args.sample:
    import random
    n = float(args.sample)
    n = int(round(n * len(indexed))) if n < 1 else int(n)
    n = max(1, min(n, len(indexed)))
    random.Random(args.grid_seed).shuffle(indexed)
    indexed = sorted(indexed[:n], key=lambda t: t[0])
    print(f"random sample: {n:,} of {len(runs_all):,} configs, grid-seed={args.grid_seed}")
if args.limit:
    indexed = indexed[:args.limit]
runs = [(GROUP, i, p) for i, p in indexed]
print(f"running {len(runs):,} configs on {args.workers} workers -> {OUTDIR}  (condition={args.condition}, metrics={args.metrics})")


METRIC_PREFIX = {"alpha": ("Alpha_",), "icc": ("ICC1_", "ICC2_", "ICC3_"), "kappa": ("Kappa_",),
                 "splithalf_between": ("SH_Between_",), "splithalf_within": ("SH_Within_",)}
ROW_KEY = ["Scale", "Condition", "Removal_Method", "Design"]


def metric_cols(cols, m):
    return [c for c in cols if c.startswith(METRIC_PREFIX[m])]


def metric_done(old, m):
    """True when an existing result file holds metric m: one of its post-removal value columns (<metric>_Post) has a
    value. Its replicate counters (_Null_Valid / _Null_Invalid) are written as 0 when the metric is switched off."""
    return bool(old[[c for c in metric_cols(old.columns, m) if c.endswith("_Post")]].notna().any().any())


def stale_knobs(idx, params):
    """Knobs whose value in an EXISTING result file differs from this run's.

    Resume skips any config whose file exists, and config ids are grid positions,
    so a file written under different knobs (e.g. worst_cluster_idx 'size' vs
    'speed') would otherwise be reused silently as if it were this run's result."""
    out = OUTDIR / f"{GROUP}{idx:06d}.csv"
    if not out.exists():
        return []
    old = pd.read_csv(out, nrows=1)
    if old.empty:                          # header-only file: a config that flagged nothing
        return []
    diffs = []
    for k, v in params.items():
        col = f"cfg_{k}"
        if col not in old.columns:
            continue
        s = old[col].iloc[0]
        if v is None and pd.isna(s):
            continue
        if isinstance(s, str):
            try:
                s = ast.literal_eval(s)
            except (ValueError, SyntaxError):
                pass
        if s != v:
            diffs.append(f"{k}: {s!r} -> {v!r}")
    return diffs


def run_one(group, idx, params):
    out = OUTDIR / f"{group}{idx:06d}.csv"
    todo = args.metrics.split(",")
    if out.exists():                       # resumable: only compute requested metrics the file lacks
        old = pd.read_csv(out)
        todo = [] if old.empty else [m for m in todo if not metric_done(old, m)]
        if not todo:
            (ERR_DIR / f"{OUTDIR.name}_{group}{idx:06d}.err").unlink(missing_ok=True)
            return str(out)
    dest = OUTDIR / f"{group}{idx:06d}.tmp.csv" if out.exists() else out
    cmd = [sys.executable, "-B", str(CODE_DIR / "lvl2.py"), "--n-jobs", "1",
           "--lvl1-input", str(L1_PREFIX), "--condition", args.condition, "--out", str(dest),
           "--override-source", "launch_LV2_sweep_random.py"]
    for name, value in params.items():
        cmd += [f"--{name}", repr(value) if isinstance(value, (list, str)) else str(value)]
    for m in IRR_METRICS:
        if m not in todo:
            cmd += [f"--irr_mm_{m}", "False"]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=CODE_DIR)
    if r.returncode != 0:
        (ERR_DIR / f"{OUTDIR.name}_{group}{idx:06d}.err").write_text(r.stdout[-4000:] + r.stderr[-4000:])
        return None
    if dest != out:                        # merge the new metric columns into the existing table
        new = pd.read_csv(dest)
        cols = [c for m in todo for c in metric_cols(new.columns, m)]
        key = ROW_KEY + [c for c in ("Rule",) if c in old.columns and c in new.columns]
        merged = old.drop(columns=[c for c in cols if c in old.columns]).merge(new[key + cols], on=key, how="left")
        merged.to_csv(OUTDIR / f"{group}{idx:06d}.merge.csv", index=False)
        os.replace(OUTDIR / f"{group}{idx:06d}.merge.csv", out)
        for suffix in (".tmp.csv", ".tmp_h2.csv", ".tmp_flagged.csv"):
            (OUTDIR / f"{group}{idx:06d}{suffix}").unlink(missing_ok=True)
    (ERR_DIR / f"{OUTDIR.name}_{group}{idx:06d}.err").unlink(missing_ok=True)   # an earlier failure's record
    return str(out)


# Provenance of this run. Resuming (including adding metrics to existing configs) is
# allowed ONLY into a directory written by the same lvl2.py (byte hash), LVL_1 handoff,
# condition and grid; otherwise the launcher stops. stale_knobs below is a second,
# per-file check of the knob values.
PROVENANCE = {"script": "lvl2.py", "pipeline_fingerprint": pipeline_fingerprint(CODE_DIR / "lvl2.py"),
              "lvl1_input": L1_PREFIX.name,
              "condition": args.condition, "grid": grid_fingerprint(runs_all)}
FILE_KEYS = {k: PROVENANCE[k] for k in ("pipeline_fingerprint", "lvl1_input", "condition")}


# ---------------------------------------------------------------- stages after the grid
# --stage apriori: the a-priori standard, the behavioural heuristic of LVL_2_CONFIG run once by lvl2.py on the sweep's
# handoff and condition (apriori/inattent999000.csv, _flagged.csv, _h2.csv, _heuristic.json).
# --stage stability: the candidates of the calibration -- per arm (cluster_2, cluster_3, mixture_gmm_2, mixture_gmm_3)
# the configuration(s) whose flagged dynamic blocks overlap the a-priori standard most (DSC; every exact tie) -- refitted
# STAB_REPS times on blocks resampled with replacement (stability/<config>.json: summaries; stability/<config>.npz: the
# ARI of every refit; stability/<config>__<arm>_profiles.csv: the full-data fit's profiles). The sweep report breaks
# DSC ties with these and checks that its candidates are these.
APRIORI_CONFIG = "inattent999000"
APRIORI_FIXED = {"save_figures": False, "pr_stim_drop": 0, "min_rt_thresh": 0, "max_rt_thresh": 90,
                 "exp_pre_transform": "boxcox", "control_block_count": "per_session", "irr_icc_form": "ICC2",
                 "kmeans_bootstrap_reps": 0, "irr_removal_methods": ["inattent_behav"]}
STAB_REPS = 5000
STAB_PARALLEL = 5
STAB_ARMS = ["cluster_2", "cluster_3", "mixture_gmm_2", "mixture_gmm_3"]
_STAB_RUNNER = r'''
import os, sys, json
out_path, reps, arms = sys.argv[1], int(sys.argv[2]), sys.argv[3].split(",")
sys.argv = ["lvl2.py"] + sys.argv[4:]
src = open("lvl2.py").read()
CUT = "block_matrix = block_matrices.get(ANALYSIS_METHOD, block_matrix)"
assert src.count(CUT) == 1, "lvl2.py changed: stability cut point not found"
G = {"__name__": "__main__", "__file__": "lvl2.py"}
exec(compile(src[:src.index(CUT)], "lvl2.py", "exec"), G)
import numpy as np
from joblib import Parallel, delayed
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.mixture import GaussianMixture
from sklearn.metrics import adjusted_rand_score
cfg, seed, n_jobs = G["LVL_2_CONFIG"], G["RANDOM_SEED"], G["N_JOBS"]
bm = G["block_matrices"][G["ANALYSIS_METHOD"]]
def gmm_worker(Xs, k, b, ref, seed0, cov, n_init, max_iter):
    rng = np.random.RandomState(seed0 + b)
    idx = rng.choice(len(Xs), size=len(Xs), replace=True)
    g = GaussianMixture(n_components=k, covariance_type=cov, random_state=seed0 + b,
                        n_init=n_init, max_iter=max_iter).fit(Xs[idx])
    return adjusted_rand_score(ref[idx], g.predict(Xs[idx]))
GA = (cfg["random_seed"], cfg["mixture_gmm_covariance_type"], int(cfg["mixture_gmm_n_init"]),
      int(cfg["mixture_gmm_max_iter"]))
_rule = "speed" if "speed" in G["WCI_RULES"] else G["WCI_RULES"][0]
_flag = G["bad_blocks_by_method"][G["ANALYSIS_METHOD"]]
_key = lambda d: d["id"].astype(str) + "_" + d["session"].astype(str) + "_" + d["block"].astype(str)
res, raw = {}, {}
for arm in arms:
    fam, k = arm.rsplit("_", 1); k = int(k)
    if fam == "cluster":      # exactly cluster_units_parallel's input and reference fit
        X = bm[[c for c in G["CLUSTER_FEATURE_COLS"] if c in bm.columns]].dropna()
        rows = bm.loc[X.index]
        Xs = StandardScaler().fit_transform(X)
        ref = KMeans(n_clusters=k, random_state=seed, n_init=10).fit_predict(Xs)
        ari = [a for a, _ in Parallel(n_jobs=n_jobs)(
            delayed(G["_kmeans_bootstrap_worker"])(Xs, k, seed, b, ref) for b in range(reps))]
    else:                     # exactly fit_gmm_mixture's input, scaling and reference fit
        _Xdf = bm[[c for c in G["GMM_FEATURE_COLS"] if c in bm.columns]].dropna()
        rows, X = bm.loc[_Xdf.index], _Xdf.to_numpy(float)
        sd = X.std(axis=0, ddof=1); sd[sd == 0] = 1.0
        Xs = (X - X.mean(axis=0)) / sd
        ref = GaussianMixture(n_components=k, covariance_type=GA[1], random_state=GA[0],
                              n_init=GA[2], max_iter=GA[3]).fit(Xs).predict(Xs)
        ari = Parallel(n_jobs=n_jobs)(delayed(gmm_worker)(Xs, k, b, ref, *GA) for b in range(reps))
    lab = rows[["id", "session", "block"] + [c for c in G["CLUSTER_FEATURE_COLS"] + G["GMM_FEATURE_COLS"]
                                             if c in rows.columns]].copy()
    lab["profile"] = ref
    _fb = _flag.get(G["rule_arm"](arm, _rule))
    lab["flagged"] = _key(lab).isin(set(_key(_fb))) if _fb is not None and len(_fb) else False
    lab.to_csv(out_path.replace(".json", f"_{arm}_profiles.csv"), index=False)
    ari = np.asarray(ari, float); raw[arm] = ari
    res[arm] = dict(mean_ari=float(np.nanmean(ari)), sd_ari=float(np.nanstd(ari, ddof=1)),
                    median_ari=float(np.nanmedian(ari)), q25=float(np.nanpercentile(ari, 25)),
                    q75=float(np.nanpercentile(ari, 75)),
                    q025=float(np.nanpercentile(ari, 2.5)), q975=float(np.nanpercentile(ari, 97.5)),
                    n_blocks=int(len(X)), reps=reps)
json.dump(res, open(out_path, "w"), indent=1)
np.savez_compressed(out_path.replace(".json", ".npz"), **raw)
'''


def _dsc(a, b):
    return (2 * len(a & b) / (len(a) + len(b))) if (a or b) else float("nan")


def _block_keys(d):
    return {f"{int(float(i))}_{int(float(s))}_{int(float(b))}" for i, s, b in d[["id", "session", "block"]].values}


def stability_candidates(outdir):
    """{config: set(arms)}: per arm, the configuration(s) whose speed-rule dynamic flags overlap the a-priori standard
    most (DSC, every exact tie)."""
    ap_ = pd.read_csv(outdir / "apriori" / f"{APRIORI_CONFIG}_flagged.csv")
    G = _block_keys(ap_[(ap_.Design == "dynamic") & (ap_.Removal_Method == "inattent_behav")])
    scores = {a: {} for a in STAB_ARMS}
    for f in sorted(outdir.glob("cluster[0-9][0-9][0-9][0-9][0-9][0-9]_flagged.csv")):
        fl = pd.read_csv(f)
        fl = fl[(fl.Design == "dynamic") & ((fl.Rule == "speed") if "Rule" in fl.columns else True)]
        for a in STAB_ARMS:
            scores[a][f.stem.removesuffix("_flagged")] = _dsc(_block_keys(fl[fl.Removal_Method == a]), G)
    out = {}
    for a, sc in scores.items():
        top = max(v for v in sc.values() if v == v)
        for c, v in sc.items():
            if abs(v - top) <= 1e-12:
                out.setdefault(c, set()).add(a)
    return out


def run_apriori():
    d = OUTDIR / "apriori"; d.mkdir(exist_ok=True)
    out = d / f"{APRIORI_CONFIG}.csv"
    if out.exists():
        o = pd.read_csv(out, nrows=1)
        if str(o["pipeline_fingerprint"].iloc[0]) != PROVENANCE["pipeline_fingerprint"] or \
                str(o["lvl1_input"].iloc[0]) != PROVENANCE["lvl1_input"]:
            raise SystemExit(f"{out} was written by another lvl2.py or handoff; move it aside")
        print(f"a-priori standard present: {out}"); return
    cmd = [sys.executable, "-B", str(CODE_DIR / "lvl2.py"), "--n-jobs", str(args.workers), "--lvl1-input", str(L1_PREFIX),
           "--condition", args.condition, "--out", str(out), "--override-source", "launch_LV2_sweep_random.py",
           "--analysis_method", repr(args.analysis_method), "--irr_mm_icc", "False", "--irr_mm_kappa", "False",
           "--irr_mm_splithalf_between", "False", "--irr_mm_splithalf_within", "False"]
    for k, v in APRIORI_FIXED.items():
        cmd += [f"--{k}", repr(v) if isinstance(v, (list, str)) else str(v)]
    r = subprocess.run(cmd, capture_output=True, text=True, cwd=CODE_DIR)
    if r.returncode != 0:
        (ERR_DIR / f"{OUTDIR.name}_{APRIORI_CONFIG}.err").write_text(r.stdout[-4000:] + r.stderr[-4000:])
        raise SystemExit("the a-priori lvl2.py run failed (see errors/)")
    print(f"a-priori standard -> {out}")


def run_stability():
    from concurrent.futures import ThreadPoolExecutor
    sdir = OUTDIR / "stability"; sdir.mkdir(exist_ok=True)
    runner = sdir / "_runner.py"; runner.write_text(_STAB_RUNNER)
    meta = dict(pipeline_fingerprint=PROVENANCE["pipeline_fingerprint"], lvl1_input=PROVENANCE["lvl1_input"],
                condition=args.condition, reps=STAB_REPS)
    req = stability_candidates(OUTDIR)
    (sdir / "_candidates.json").write_text(json.dumps({c: sorted(a) for c, a in sorted(req.items())}, indent=1))
    todo = []
    for cfg, arms in sorted(req.items()):
        path = sdir / f"{cfg}.json"
        cached = json.loads(path.read_text()) if path.exists() else None
        if not (cached and cached.get("meta") == meta and set(arms) <= set(cached["arms"])
                and (sdir / f"{cfg}.npz").exists()):
            todo.append((cfg, sorted(arms), path))
    n_each = max(1, (os.cpu_count() - 1) // max(1, min(STAB_PARALLEL, len(todo))))

    def _one(t):
        cfg, arms, path = t
        r = pd.read_csv(OUTDIR / f"{cfg}.csv", nrows=1, keep_default_na=False, dtype=str)
        a_ = ["--lvl1-input", str(L1_PREFIX), "--condition", args.condition, "--n-jobs", str(n_each)]
        for c in r.columns:
            if c.startswith("cfg_") and r[c].iloc[0] != "" and c != "cfg_kmeans_bootstrap_reps":
                a_ += [f"--{c[4:]}", r[c].iloc[0]]
        a_ += ["--kmeans_bootstrap_reps", "0"]
        tmp = path.with_suffix(".arms.json")
        p = subprocess.run([sys.executable, "-B", str(runner), str(tmp), str(STAB_REPS), ",".join(arms)] + a_,
                           capture_output=True, text=True, cwd=str(CODE_DIR))
        if p.returncode != 0:
            raise SystemExit(f"stability run failed for {cfg}:\n{p.stderr[-2000:]}")
        res = json.loads(tmp.read_text()); tmp.unlink()
        os.replace(tmp.with_suffix(".npz"), path.with_suffix(".npz"))
        for a in arms:
            Path(str(tmp).replace(".json", f"_{a}_profiles.csv")).replace(path.with_name(f"{cfg}__{a}_profiles.csv"))
        path.write_text(json.dumps({"meta": meta, "arms": res}, indent=1))
        return cfg
    print(f"stability: {len(req)} candidate configuration(s); {len(todo)} to refit ({STAB_REPS} refits each)")
    with ThreadPoolExecutor(max_workers=STAB_PARALLEL) as ex:
        for cfg in ex.map(_one, todo):
            print(f"  stability -> {cfg}")


if __name__ == "__main__":
    _n = check_outdir(OUTDIR, PROVENANCE, r"cluster\d{6}", FILE_KEYS, write=not args.check_only)
    print(f"provenance OK: {OUTDIR} ({_n} existing result file(s) match "
          f"lvl2.py {PROVENANCE['pipeline_fingerprint']} / {PROVENANCE['lvl1_input']})")
    if args.check_only:
        raise SystemExit(0)
    if args.stage in ("apriori", "stability"):
        run_apriori() if args.stage == "apriori" else run_stability()
        raise SystemExit(0)
    stale = {i: d for _, i, p in runs if (d := stale_knobs(i, p))}
    if stale:
        i0, d0 = next(iter(stale.items()))
        raise SystemExit(
            f"{len(stale)} existing result file(s) in {OUTDIR} were written with different "
            f"knob values (e.g. {GROUP}{i0:06d}: {'; '.join(d0)}). Resuming would reuse them "
            f"silently. Use a fresh --outdir, or move {OUTDIR} aside first.")
    t0 = time.time()
    paths = Parallel(n_jobs=args.workers, backend="loky", batch_size=1, verbose=10)(
        delayed(run_one)(g, i, p) for g, i, p in runs)
    el = time.time() - t0
    ok = [p for p in paths if p]
    print(f"\n{len(ok)}/{len(runs)} ok in {el/3600:.2f} h ({el/max(len(runs),1):.1f}s per config)")
    failed = [f"{g}{i:06d}" for (g, i, _), p in zip(runs, paths) if not p]
    if failed:
        print(f"FAILED: {len(failed)} configuration(s) are not in the pooled table (their output: "
              f"{ERR_DIR}/{OUTDIR.name}_<config>.err): {', '.join(failed)}")

    if ok:
        df = pd.concat([pd.read_csv(p).assign(group=Path(p).stem.rstrip("0123456789"))
                        for p in ok], ignore_index=True)
        res = OUTDIR / "sweep_results.csv"
        df.to_csv(res, index=False)
        print(f"pooled -> {res}  ({len(df):,} rows)")

        # H3 primary: dynamic-design alpha excess over matched random removal
        cfg = [c for c in df.columns if c.startswith("cfg_")]
        dyn = df[df["Design"] == "dynamic"]
        rank = (dyn.groupby(["Removal_Method"] + cfg, dropna=False)
                   [["Alpha_Excess", "Alpha_Improvement_PerTrial", "Trials_Removed", "Pct_Removed"]].mean()
                   .reset_index().sort_values("Alpha_Excess", ascending=False))
        rank.to_csv(OUTDIR / "sweep_ranking.csv", index=False)
        print("\nTOP 15 dynamic configs by Alpha_Excess:")
        print(rank.head(15).to_string(index=False))
    if args.stage == "all":
        run_apriori()
        run_stability()
