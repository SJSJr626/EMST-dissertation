# Block detection pipeline: practical application (EMST data)

Version 0.0.1 (development series; 1.0.1 will be the general tool).

Detects blocks of careless responding in a rating task and tests whether removing them improves inter-rater
reliability (IRR). Three levels, one notebook each: LVL0 (response-style diagnostics, RT drift model), LVL1 (16
change-point detectors and their validation), LVL2 (block labelling and the IRR removal comparison). This folder
applies the pipeline to the EMST data for the published norms: the sweeps calibrate LVL1 and LVL2 on all data (T2 and
T3), and the calibrated configuration is run on T2, on T3 and on T2 + T3 (one fit on both conditions). Every result is
computed once, by the notebook that owns it, and exported; the reports and the figures read those exports.

**Generated folder.** `/home/sjsuss626/EMST_files/sjs_dissertation/code/make_practical_application_emst.py` writes
this folder from the validation pipeline, `code/cpd_and_blk_rep_anaylsis` (calibrated on T2 and tested on T3), with its
pooled pathway active, its paths pointing here and at `dervatives/practical_application_emst`, its calibration on all
data and its reports worded for that. Change the pipeline there and regenerate (section 10); by hand, set only the
pins and the calibration values (section 3).

**Conditions.** T2 and T3 are the dataset's two conditions (different participants rating different stimuli). The
manuscript calls them cohorts: T2 = Cohort A (CA), T3 = Cohort B (CB). The code, file names, exports and the final
report keep T2 and T3; `make_replication_figures` prints CA and CB.

**Heuristic thresholds.** The trial-level thresholds of the behavioural heuristic (`LVL_2_CONFIG`, `[cell 28]`) are
the all-data 99th-percentile markers of the LVL_0 permutation nulls, the ALL column of the LVL_0 marker table: straight
line 21; periodic p = 2 / 3 / 4: 9 / 11 / 13; 5-response stimulus-linked pattern 8. The LVL0 notebook is the
validation pipeline's: its printout of the marker table and its `[cell 3]` comment (copied into the LVL2 notebook's
upstream-definitions cell, `lvl0.py` and `lvl2.py`) name the T2 columns, which apply to the validation pipeline only.

---

## 1. Folder contents

| File | Role |
|---|---|
| `block_detection_and_removal_LVL{0,1,2}.ipynb` | The pipeline (source of truth for all pipeline code). The LVL2 notebook is the template of the three run notebooks. |
| `block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb` | The three LVL2 runs (generated from the template by the build; never edit them). |
| `build_level_scripts.py` | Builds `lvl0.py`, `lvl1.py`, `lvl2.py` from the notebooks, the LVL2 notebook's upstream-definitions cell, the three run notebooks and `LVL1_report`'s upstream-definitions cell; checks them. |
| `lvl0.py`, `lvl1.py`, `lvl2.py` | Generated command-line levels; `lvl1.py` and `lvl2.py` are the sweep workers, and the final report runs `lvl2.py` read-only through its Step 5 (`[cell 9]`). No step runs `lvl0.py` (its handoff lacks the LVL0 notebook's decay-fit exports, which `LVL0_report` and the figures read). Never edit by hand. |
| `launch_LV1_sweep_random.py`, `launch_LV2_sweep_random.py` | Sweep launchers; they write their sweep folders (a sweep report adds only the sweep's script copy, section 5). |
| `submit_BDR_LVL2_notebooks_all.sh` | Runs the three LVL2 run notebooks in parallel, each executed in place (section 6). |
| `sweep_provenance.py` | Provenance checks of the sweep folders. |
| `demographic_report.ipynb` | Sample description: flow, single-session reasons (a documented ledger), Table 0.1, the demographics table, session intervals, out-of-range responses. |
| `LVL0_report.ipynb` | Session duration, RT limits, drift-model tables. |
| `LVL1_sweep_report.ipynb` | LVL1 calibration tables and the selection. |
| `LVL1_report.ipynb` | Chosen participants' sessions from a LVL_1 handoff: the detection features, the detectors' smoothing and every detector's blocks (draws only). |
| `LVL2_sweep_report.ipynb` | LVL2 calibration (DSC with the a-priori standard, stability, dose-response) and the selection. |
| `make_replication_figures.ipynb` | Every figure, from the exports, with a provenance sidecar. |
| `Replication_and_final_report.ipynb` | Assembles every table into one Markdown report (+ the supplementary tables as LaTeX); besides the cross-dataset comparisons it computes Tables 2.8–2.9, the BH families stated under its tables, the summaries of Tables 5.11 and 5.18–5.19 and the exact-zero folded-unit diagnostics of Tables 4.30–4.32, for which `[cell 9]` executes `lvl2.py` once per LVL2 run, read-only and in a subprocess (without `--export`; nothing is written), through its Step 5 to rebuild the run's block matrices and refit the carried labellers. |

**Who computes what.** Each result has one owner; everything downstream reads its exports.

| Results (report tables) | Owner | Exports (in `LVL_OUTS` unless noted) | Read by |
|---|---|---|---|
| Sample flow, demographics, session intervals, out-of-range responses (0.1, 0.7–0.11) | `demographic_report` | `lv0_out_<ts>_demographics_*.csv` | report |
| Preprocessing, drift fits (0.5–0.6) | LVL0 notebook | `lv0_out_<ts>.csv`, `_parameters.json`, `_decay_fits.csv`, `_decay_curves.csv` | LVL1, LVL0_report, figures |
| Session duration, RT limits, drift tables (0.2–0.6) | `LVL0_report` | `lv0_out_<ts>_report_*.csv` | report |
| LVL1 calibration (1.1–1.4) | LVL1 sweep (launcher) → `LVL1_sweep_report` | `sweeps/_sweep_lvl1_all/`; `_sweep_lvl1_all_report_*.csv`, `_selection.json` | LVL1 notebook, report, figures |
| Segmentation, H1 (2.1–2.6), behavioural features and age check (0.3, 0.12–0.13) | LVL1 notebook | `lv1_out_<ts>_{long,features,results}.csv`, `_meta.json`, `_h1_*.csv`, `_report_*.csv` | LVL2, report, figures |
| LVL2 calibration: DSC, stability, dose-response (3.1–3.7) | LVL2 sweep (launcher) → `LVL2_sweep_report` | `sweeps/_sweep_lvl2_all_<detector>/`; `<sweep>_report_*.csv`, `_selection.json` | LVL2 runs, report, figures |
| H2, H3, secondary measures, post hoc variants (3.8–5.21) | the three LVL2 runs (one template) | `lv2_out_<run>_step8_*`, `_step9_*`, `_post_*.csv`, `_post_replicates.npz`, `_units.csv` | report, figures |
| H1 method-level association and outliers (2.8–2.9: mean η²_H vs mean Corr%, Wilks' exact test; the LVL1 notebook's Mahalanobis export, of mean η²_H and mean blocks, is only reproduced as a check); cross-dataset comparisons: ΔDSC, the summaries across the datasets, claims (4.8, 4.17, 5.10–5.11, 6.1); the BH families stated under its tables; the descriptives of 5.18–5.19; the exact-zero folded units (4.30–4.32: the runs' block matrices rebuilt read-only by `lvl2.py`, `[cell 9]`) | `Replication_and_final_report` | `final_replication_publication_report.md`, `final_replication_supp_tables.tex` | — |
| Figures | `make_replication_figures` | `figures/pub_figures/**/fig_*.png` + `.json` | report (links, sidecar check) |

The pipeline's outputs go to `LVL_OUTS`, `SWEEPS_DIR` and `FIG_DIR` (section 2). Only the launchers' `errors/` folder
(failed sweep configurations), the executed copies of command-line notebook runs (section 3) and the outputs the three
run notebooks keep (section 6) are written here. Earlier states of the project are in
`sjs_dissertation/archive/`; audits and reference documents are in `sjs_dissertation/audit_history/`. Neither is read
by any notebook or script.

---

## 2. Setup

- **Python:** run every notebook, script and launcher with `/usr/bin/python3` (Jupyter kernel `block_detection_irt`).
  Tested with Python 3.10.12, numpy 1.26.4, pandas 2.2.1, scipy 1.12.0, scikit-learn 1.7.2, statsmodels 0.14.6,
  hmmlearn 0.3.3, ruptures 1.1.10, joblib 1.5.3, matplotlib 3.10.8. Every notebook is saved with the kernel
  `block_detection_irt` (`/usr/bin/python3`); the command lines of sections 3 and 6 also set it. Every level's run
  log (`<stem>_parameters.json`) records the pipeline version (`pipeline_version`) and the interpreter and package
  versions (`software`).
- **No `__pycache__/`:** call scripts with `python3 -B`; the launchers pass `-B` to every worker, and the notebooks
  import `sweep_provenance.py` without writing bytecode. Running notebooks from the command line, set
  `PYTHONDONTWRITEBYTECODE=1`.
- **Locations** (written out in full where they are used; everything is inside `/home/sjsuss626/EMST_files/sjs_dissertation`):

  | Name | Path under `sjs_dissertation/` | Contents |
  |---|---|---|
  | `INPUT_LONG_PATH` | `dset/all_subjects_long.csv` | the analysis dataset (one row per rating) |
  | `LVL_OUTS` | `dervatives/practical_application_emst/lvl_outs` | every handoff, run log, export and report |
  | `SWEEPS_DIR` | `dervatives/practical_application_emst/sweeps` | the sweep folders |
  | `FIG_DIR` | `dervatives/practical_application_emst/figures/pub_figures/{main_text,supplement}` | the figures and their sidecars |
  | `WARNINGS_OUTS` | `dervatives/practical_application_emst/lvl_outs/warnings` | the warnings logs: `suppressed_warnings.log`; each LVL2 run's `<run tag>_warnings.log` (section 6) |

- **Long runs** can go in `tmux` (optional): a `tmux` session keeps running when the terminal or a remote (SSH)
  connection closes (`tmux new -s <name>`; detach Ctrl-b d; `tmux attach -t <name>` to return).

---

## 3. Execution order

Run from `code/practical_application_emst`. A notebook is run top to bottom, in Jupyter or as
`PYTHONDONTWRITEBYTECODE=1 /usr/bin/python3 -m nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=block_detection_irt --ExecutePreprocessor.timeout=-1 --output <name>_executed.ipynb <name>.ipynb`.
The long steps (1, 5, 7, 8, 10) run on CPUs 0–30 (`taskset -c 0-30`, 31 CPUs: the LVL1 notebook's `n_jobs` 31, the
launchers' 30 workers, the three LVL2 runs' `n_jobs` 9 + 9 + 13), each with its log in `LVL_OUTS/run_logs/`; their
commands follow the table. Running them inside `tmux` is optional: it lets a step run on independently of the
terminal, e.g. when working remotely and the connection closes (line above). `submit_BDR_LVL2_notebooks_all.sh` and the report's `[cell 9]` (its `lvl2.py` rebuilds) set `taskset -c 0-30` themselves, so an outer `taskset` does not narrow them; with fewer CPUs, run step 10 by (a) with lower `n_jobs` in the run notebooks (`n_jobs` does not change a result). Before each step, set its **pins** (the first lines of its
first code cell) to the outputs of the earlier steps.

| # | Step | Pins | Writes | Time |
|---|---|---|---|---|
| 1 | `block_detection_and_removal_LVL0.ipynb` (command below) | — (`LVL_0_CONFIG`, `[cell 3]`) | `lv0_out_<ts>.csv`, `_parameters.json`, `_decay_fits.csv`, `_decay_curves.csv` | ~20 min |
| 2 | `demographic_report.ipynb` | `LVL0_HANDOFF` | `lv0_out_<ts>_demographics_*.csv` | < 1 min |
| 3 | `LVL0_report.ipynb` | `LVL0_HANDOFF` | `lv0_out_<ts>_report_*.csv` | < 1 min |
| 4 | `/usr/bin/python3 -B build_level_scripts.py` | — | `lvl0/1/2.py`, the LVL2 and LVL1_report upstream cells, the run notebooks | seconds |
| 5 | The LVL1 sweep, `launch_LV1_sweep_random.py --lvl0-input lv0_out_<ts>.csv --condition both --subsample 0 --workers 30 --outdir _sweep_lvl1_all` (command below) | `--lvl0-input` | `sweeps/_sweep_lvl1_all/` | ~20 min (estimate) |
| 6 | `LVL1_sweep_report.ipynb` | `SWEEP_DIR` | `_sweep_lvl1_all_report_*.csv`, `_sweep_lvl1_all_selection.json`; the sweep's script copy when it is missing (section 5) | < 1 min |
| 7 | Set `LVL_1_CONFIG` (`[cell 9]`) to the selection's `LVL_1_CONFIG` values, then run `block_detection_and_removal_LVL1.ipynb` (command below) | `LVL0_HANDOFF`, `LVL1_SWEEP` | `lv1_out_<ts>_{long,features,results}.csv`, `_meta.json`, `_parameters.json`, `_h1_*.csv`, `_report_*.csv` | ~10 min |
| 7a | `LVL1_report.ipynb` (participants' sessions; optional) | `LVL1_HANDOFF`, `SWITCHERS`, `METHODS` | nothing (figures in the notebook) | < 2 min |
| 8 | Set `analysis_method` (`[cell 28]`) to the selected detector; step 4 again (LVL_1_CONFIG reaches `lvl1.py`, `analysis_method` `lvl2.py`); then the LVL2 sweep, three stages: `launch_LV2_sweep_random.py --lvl1-input lv1_out_<ts> --condition both --analysis-method <selected detector> --workers 30 --outdir _sweep_lvl2_all_<detector> --metrics alpha --stage all` (command below) | `--lvl1-input`, `--analysis-method` | `sweeps/_sweep_lvl2_all_<detector>/` with `apriori/` and `stability/` | ~20 h (estimate) |
| 9 | `LVL2_sweep_report.ipynb` | `SWEEP_DIRS`, `LVL1_HANDOFF` | `<sweep>_report_*.csv`, `<sweep>_selection.json`; the sweep's script copy when it is missing (section 5) | < 5 min |
| 10 | **The three LVL2 run notebooks** (T2, T3, T2 + T3): see *Step 10* below the table | `LVL1_HANDOFF`, `LVL2_SWEEP` (each run notebook) | `lv2_out_<detector>_<conditions>_<ts>_*` | ~6–8 h (estimate; the T2 + T3 run sets the time) |
| 11 | `make_replication_figures.ipynb` | `LVL0_HANDOFF`, `LVL1_HANDOFF`, `LVL1_SWEEP`, `LVL2_SWEEP`, `RUN_TAGS` | `figures/pub_figures/**/fig_*.png` + `.json` | < 10 min |
| 12 | `Replication_and_final_report.ipynb` | as step 11 | `final_replication_publication_report.md`, `final_replication_supp_tables.tex` | < 30 min (estimate) |

**Step 10, the three LVL2 run notebooks** (`block_detection_and_removal_LVL2_T2_rep.ipynb`,
`block_detection_and_removal_LVL2_T3_rep.ipynb`, `block_detection_and_removal_LVL2_T2+T3_rep.ipynb`):

1. In the template `block_detection_and_removal_LVL2.ipynb`, set `LVL_2_CONFIG` (`[cell 28]`) to the LVL2 selection's
   `LVL_2_CONFIG` values (each family's exponents and k list).
2. Run step 4 (the build). It rewrites the three run notebooks, with their pins at `None`.
3. In each run notebook, set `LVL1_HANDOFF` and `LVL2_SWEEP` (its first code cell, the `LVL_2 INPUT` cell).
4. Run the three in parallel, EITHER
   - (a) directly: open each run notebook in Jupyter and run all (not pinned to CPUs 0–30, no step log; it runs only
     while the Jupyter session stays open), OR
   - (b) jointly: `submit_BDR_LVL2_notebooks_all.sh` (command `# step 10 (b)` below; section 6).

The long steps, run from the code folder after `run_logs/` is created (once, before step 1):

```bash
cd /home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst
mkdir -p /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs

# step 1
PYTHONDONTWRITEBYTECODE=1 taskset -c 0-30 /usr/bin/python3 -m nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=block_detection_irt --ExecutePreprocessor.timeout=-1 --output block_detection_and_removal_LVL0_executed.ipynb block_detection_and_removal_LVL0.ipynb 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step1_$(date +%Y%m%d_%H%M%S).log

# step 5
taskset -c 0-30 /usr/bin/python3 -B launch_LV1_sweep_random.py --lvl0-input lv0_out_<ts>.csv --condition both --subsample 0 --workers 30 --outdir _sweep_lvl1_all 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step5_$(date +%Y%m%d_%H%M%S).log

# step 7
PYTHONDONTWRITEBYTECODE=1 taskset -c 0-30 /usr/bin/python3 -m nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=block_detection_irt --ExecutePreprocessor.timeout=-1 --output block_detection_and_removal_LVL1_executed.ipynb block_detection_and_removal_LVL1.ipynb 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step7_$(date +%Y%m%d_%H%M%S).log

# step 8
taskset -c 0-30 /usr/bin/python3 -B launch_LV2_sweep_random.py --lvl1-input lv1_out_<ts> --condition both --analysis-method <selected detector> --workers 30 --outdir _sweep_lvl2_all_<detector> --metrics alpha --stage all 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step8_$(date +%Y%m%d_%H%M%S).log

# step 10 (b)
taskset -c 0-30 bash /home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst/submit_BDR_LVL2_notebooks_all.sh 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step10_$(date +%Y%m%d_%H%M%S).log
```

`demographic_report` and `LVL0_report` follow LVL0 because they check the sample against its handoff; the figures come
before the report because the report links them and checks their sidecars. After step 1, check that the ALL
99th-percentile column of the LVL_0 marker table reads 21 / 9 / 11 / 13 / 8, the heuristic thresholds (top of this
README).

Calibration is on all data, T2 and T3 (steps 5–9); the three runs use that configuration unchanged. The calibration-check
cells of the LVL1 and LVL2 notebooks stop unless `LVL_1_CONFIG` / `LVL_2_CONFIG` hold the calibrated values of the
sweep reports' `_selection.json` (the knobs the LVL1 sweep varied; each LVL2 family's exponents and k list, and
`analysis_method`). `make_replication_figures` and the report check every other configuration key and the code
(checks (a)–(e), section 4). `lvl1.py` must be the script the LVL1 sweep ran, so when step 7 changes `[cell 9]`, steps
4–6 are run again (a fresh `--outdir`) before the LVL1 notebook. `lvl2.py` may differ from the LVL2 sweep's script
only on comment and blank lines and on the lines step 10 writes (the family knobs of NOTEBOOK CELL 28; check (c),
section 4).

---

## 4. Pins, checks and lineage

A pin is a file name (handoff, run tag) in `LVL_OUTS` or a folder name in `SWEEPS_DIR`. There is no default and no
"newest file" rule: a pin left at `None` stops the notebook. Every consumer checks
its inputs and stops on a missing or mismatched one:

| Consumer | Checks |
|---|---|
| LVL1 notebook | the LVL_0 handoff and its single run log; the raw input's name and SHA-256 equal the run log's; `LVL_1_CONFIG` holds the LVL1 selection's knob values (its `LVL_1_CONFIG`), made on this LVL_0 handoff |
| LVL2 notebook (and run notebooks) | the LVL_1 handoff's four files; the raw input's SHA-256 equals the one the LVL_1 handoff records; `LVL_2_CONFIG` holds the LVL2 selection's knob values (each family's exponents and k list) and its `analysis_method`, made on this LVL_1 handoff |
| launchers | `_provenance.json` of the sweep folder (script fingerprint, handoff, condition, grid), and the result files already in it match it |
| sweep reports | the sweep is complete: its result files are the launcher's whole grid (configuration ids 0 … N − 1, each with its companion files, `sessions_` for LVL1, `_h2` and `_flagged` for LVL2, and their `cfg_` columns rebuild the grid hashed in `_provenance.json`), or the report lists the missing and incomplete configurations and the launcher's `errors/` files and stops; every result file matches the sweep folder's `_provenance.json` (script fingerprint, handoff, condition); the sweep's script copy has the sweep's fingerprint (section 5), while a current `lvl1.py` / `lvl2.py` with another fingerprint only prints a warning. `LVL1_sweep_report`: `sweep_results.csv` holds every configuration file's rows. `LVL2_sweep_report`: the pinned LVL_1 handoff is complete and is the sweep's; the a-priori and stability files were made by the sweep's script on that handoff; its stability candidates are the stability stage's |
| `demographic_report` | the LVL_0 handoff and its single run log; the dataset's SHA-256 equals the run log's; the dataset after the LVL_0 intake filters has the handoff's participants and sessions |
| `LVL0_report` | the LVL_0 handoff and its single run log; the decay-fit export exists and selects the run log's drift models |
| `make_replication_figures` | every input it reads exists; before anything is drawn, checks (a)–(e) below and the handoffs: the LVL_1 handoff and the LVL1 sweep were made on the pinned LVL_0 handoff, the LVL2 sweep and every run on the pinned LVL_1 handoff, and each run's conditions are its `RUN_TAGS` key's; the LVL1 selection is the sweep's η²_H winner; the dose-response contrasts are Table 3.6's distinct-solution test and agree with the dose fits (AUCs, stars) |
| `Replication_and_final_report` | every pinned input, and every post hoc export the runs' indexes list, exists. Table 7.3 records the lineage checks: the runs' LVL_1 handoff and `LVL_2_CONFIG` equal the pins and the LVL2 selection; the sweeps and handoffs come from the same upstream handoffs; checks (a)–(e) below; the pipeline version recorded by every level's run log (the LVL_0 and LVL_1 handoffs' and each run's `_parameters.json`) equals the report's `PIPELINE_VERSION` (`[cell 1]`); one behavioural heuristic; the same post hoc tables in every run; one row per figure sidecar in `FIG_DIR` (linked or not): its pins equal the report's, its PNG exists, and every input it lists equals the current file (bytes, SHA-256) |

Checks (a)–(e) compare what ran with the calibration. Each sweep report writes into its `_selection.json` the path of
the sweep's script copy (`script_copy`) and that script's whole configuration with the selected values
(`LVL_1_CONFIG_full` / `LVL_2_CONFIG_full`; section 5).

- (a) The LVL_1 handoff's `lvl1_config` (`_meta.json`) equals `LVL_1_CONFIG_full` on every key but `n_jobs`,
  `parallel_verbose` and `save_figures`, which cannot change a result.
- (b) Each run's recorded LVL_2 configuration (`_parameters.json`, `_config.json`) equals `LVL_2_CONFIG_full` on every
  key both record but `save_figures` and `conditions` (compared with the run's `RUN_TAGS` key).
- (c) `lvl1.py` has the LVL1 sweep's fingerprint. `lvl2.py` has the LVL2 sweep's, or every line on which it differs
  from the sweep's script copy (difflib, on either side, each line in the cell of the NOTEBOOK CELL banner above it)
  is admitted by one of two rules: (i) a comment or blank line (by Python's tokenizer, so a line inside a string is
  code); (ii) a line setting one of the selection's family knobs in NOTEBOOK CELL 28 (what step 10 writes). Any other
  differing line fails the check. Its detail lists each differing cell and the number of lines each rule admitted
  there. Each selection's fingerprint and script copy match its sweep's `_provenance.json`.
- (d) The LVL2 selection and every run use the LVL1 selection's detector.
- (e) Both sweeps were calibrated on all data (`--condition both`).

Lineage: `lv2_out_<…>_config.json` → `lv1_out_<ts>_meta.json` (`lvl1_config`, `lvl0_input`, `lvl0_record`,
`input_long_sha256`) → `lv0_out_<ts>_parameters.json` (LVL_0 configuration, drift models and fits, the raw input's
SHA-256). Every run log also records the pipeline version and the software versions (section 2). Keep a stamp at the
start of a renamed output (`lv0_out_<stamp>…`) and rename a handoff's files together.

---

## 5. Calibration

**LVL1 sweep** (step 5). The grid is `knobs` in `launch_LV1_sweep_random.py` (a list is swept, a scalar fixed). Output
per configuration: `cfgNNNNNN.csv` (one row per detector) and `sessions_cfgNNNNNN.csv` (per session), then
`sweep_results.csv` and `sweep_ranking.csv`. `LVL1_sweep_report` (step 6) reads the sweep folder: Tables 1.1–1.4,
each detector's best configuration (`best_per_detector`, `best_eta`, `best_corr`, `configs`), and
`_sweep_lvl1_all_selection.json` (the η²_H winner and its knob values; `script_copy`; `LVL_1_CONFIG_full`, every key of
the script copy's `LVL_1_CONFIG` with those knob values).

**LVL2 sweep** (step 8). `fixed`, `EXP_ALL` and `cluster_fixed` in `launch_LV2_sweep_random.py` set the grid (`EXP_ALL`:
the exponents of the two power-transformed block features, RT variance and entropy, `exp_rt_var_block` and
`exp_entropy_block`; every configuration fitted as k-means k = 2, 3 and GMM k = 2, 3), scored on Krippendorff's α only (`--metrics alpha`; the default adds ICC, κ and split-half and multiplies the run time). `--stage all` runs the grid, then `--stage apriori` (the
behavioural heuristic of `LVL_2_CONFIG`, run once by `lvl2.py`: the a-priori gold standard, in `apriori/`), then
`--stage stability` (each arm's highest-DSC configuration and every exact tie, refitted 5,000 times on resampled
blocks, in `stability/`). The stages can be run one at a time with `--stage grid|apriori|stability`. Labelling: in
every fit the fastest component (lowest mean `adj_rt_level_block`) is the inattentive one; the reports read the
`speed` rows of the sweep files. `LVL2_sweep_report` (step 9) reads the sweep folder and the LVL_1 handoff the sweep
ran on: DSC with the a-priori standard, its variance shares and maxima (Tables 3.1–3.3b), stability (Table 3.4), the
dose-response fits (Table 3.5), their AUC contrasts between designs (Table 3.6: a paired bootstrap over each arm's
distinct solutions, the configurations that flag the same units in every design counting as one solution, which sets
the stars of Table 3.5 and Figure 3.1; Table 3.6b, in the appendix: the same contrasts resampling the configurations, a
sensitivity analysis whose p and q are descriptive), the calibrated configurations on their curves (Table 3.7), and
`<sweep>_selection.json` (per family the carried arm, its configuration, k and exponents; `script_copy`;
`LVL_2_CONFIG_full`, every key of the script copy's `LVL_2_CONFIG` with each family's values).

**Sweep rules.** A fresh `--outdir` per script fingerprint, handoff or grid; the launchers resume only into a folder
whose provenance matches (`--check-only` checks without running). Rebuild the scripts (step 4) before a sweep when a
notebook changed: any change to a level's code changes its fingerprint. A sweep report reads the script the sweep ran
from its byte copy in the sweep folder (`_script_lvl1.py` / `_script_lvl2.py`) and stops unless the copy has the
sweep's fingerprint. A missing copy is written from the current `lvl1.py` / `lvl2.py` while that script still has the
sweep's fingerprint (before the rebuild of step 8 or 10 changes it); otherwise the report stops. The copy is the only
file a sweep report writes into a sweep folder.

---

## 6. The LVL2 runs

The build writes `block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb` from the template (conditions `["T2"]`,
`["T3"]` and `["T2", "T3"]`; `n_jobs` 9 / 9 / 13, the three runs sharing CPUs 0–30). With their pins set, run them in parallel, either each
notebook directly in Jupyter or jointly with this script (step 10 (a) / (b); `tmux` optional; `run_logs/` created first):

```bash
mkdir -p /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs
taskset -c 0-30 bash /home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst/submit_BDR_LVL2_notebooks_all.sh 2>&1 | tee /home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs/run_step10_$(date +%Y%m%d_%H%M%S).log
```

The script stops before running anything if a run notebook's `LVL1_HANDOFF` or `LVL2_SWEEP` is unset (it reads them
from the notebook's second cell, the `LVL_2 INPUT` cell), the handoff is missing, or the LVL2 sweep's selection is
missing or was made on another handoff; it does not check `n_jobs`. It executes each notebook in place with nbconvert
(kernel `block_detection_irt`), so the run notebooks keep the run's outputs, and starts them 15 s apart, so that each
run tag has its own second; each run's log is `LVL_OUTS/run_logs/run_<notebook>_<stamp>.log`. A later build (step 4)
rewrites a run notebook whose code differs from what the build writes (pins `None`, `n_jobs` 9 / 9 / 13), which clears
the saved outputs of a notebook that ran; the exports in `LVL_OUTS` stay.

Each run writes, under its run tag `lv2_out_<detector>_<conditions>_<start time>` (printed by `[cell 29]`):

| Files | Content |
|---|---|
| `_step8_multimetric.csv`, `_step8_null_overall.csv`, `_step8_null_iterations.npz` | the removal comparison per metric × design × removal method × scale cell, and over the cells: reference, post-removal and matched-random values; D and D per trial removed with their Monte Carlo interval and p; the change vs baseline (and per trial) with its stimulus-paired bootstrap |
| `_step9_design_tests.csv`, `_step9_cell_tests.csv`, `_step9_null_contrasts.csv`, `_step9_design_summary.csv` | dynamic vs control / session / participant in four quantities (D per trial, D, gain per trial, gain), over the cells and per cell; the null D-difference contrasts; the bars |
| `_post_<table>.csv`, `_post_replicates.npz`, `_units.csv`, `_post_index.csv` | Steps 5e and 10: H2 and its robustness, overlap with the heuristic, stability and components of every fit, the primary H3 table, GMM posterior thresholds, repeat exposures; the index lists every file |
| `_annotated.csv`, `_participant_summary.csv`, `_data_dictionary.csv`, `_config.json`, `_parameters.json` | the analysed trials with block IDs and flags; the run log |
| `WARNINGS_OUTS/<run tag>_warnings.log` | every warning the run shows from `[cell 29]` on (RuntimeWarning, UserWarning and FutureWarning once per source line); warnings raised in the parallel workers go to the workers' stderr |

**Split-half and the coverage floor.** Every split-half score of a scale × condition cell (baseline, post-removal,
each matched random removal and each bootstrap replicate) uses the cell's one split set of `splithalf_bootstrap_reps`
random splits, seeded from `splithalf_seed` with the scale and condition (`splithalf_split_set`, `[cell 37]`). The
coverage floor `h2_min_coverage` (the share of the condition's stimuli rated at least twice) applies to the H2 IRR
matrices, to each robustness B split (only the splits that meet it in both matrices of every cell enter its Δα, CI and
p; the share of such splits is exported) and to the H3 post-removal matrices.

**Figures in the run notebooks** (notebook-only cells; nothing is written): the block cluster profiles of the k-means and GMM solutions, the agreement (overlap) between the removal methods for dynamic and control blocks, and, per IRR measure, the Step 9 bars (dynamic vs each design, with the figure tests) beside the same means against the % of trials removed.

**Datasets.** The T2 run's dataset is "T2 only" and the T3 run's "T3 only"; the T2 + T3 run (one fit on both
conditions) gives "Pooled, overall" and its restrictions to each condition, "Pooled, T2" and "Pooled, T3". The
configuration was calibrated on all data, so every dataset is in-sample, and the pooled datasets share their
participants with T2 only and T3 only. H1 has "T2+T3 calibration" (the LVL1 sweep's sessions, each detector at its own
η²_H-optimal configuration for η²_H, its own Corr%-optimal configuration for Corr%), "T3 only" (the selected
configuration) and the pooled datasets; its tests compare every pair of detectors in T2+T3 calibration and in T3 only,
each test with its own BH family. H2, H3 and the heuristic as a classifier are reported for every dataset (the
heuristic's BH family: T2 only and T3 only; the pooled rows carry no q); the supplementary LaTeX tables for T2 only
and T3 only.

---

## 7. Figures and the final report

`make_replication_figures` checks the lineage of its pins (section 4), draws every figure from the exports and writes
`<name>.png` with `<name>.json` (every file the figure is drawn from, the selection files and run logs that decide what
it shows included, with sizes, SHA-256 and times; the pins; the time of drawing). The manuscript's
`task_example_long.png` and `matrix_example3.png` are external assets, kept with the manuscript: they are not in this
folder and nothing here reads them.
`PARTICIPANT_FIGURES` (top of its first cell) lists the participants drawn as `supplement/participants/fig_participant_<id>.png`
(features, every detector's blocks, the flagged blocks); `MOSAIC_PARTICIPANTS` are the two shown in the LVL1 calibration
figure.
The sweep reports and the level notebooks also draw their own figures (in the notebook, not written to `FIG_DIR`): `LVL1_sweep_report` the knobs' main effects and the `pelt_jump` x `smoothing_window` heatmap; the LVL1 notebook the MAD-CPD per-gap diagnostics and the effect size against corrected significance at each detector's optimal configuration; `LVL2_sweep_report` (section 4) the overlap across the sweep, the profiles of the calibrated configurations, the overlap against each exponent, the removal outcome by design and the method agreement.
`Replication_and_final_report` prints every table (its numbering is the report's; an appendix holds the supporting
analyses the manuscript does not cite), links the figures (checking every figure's sidecar), lists every check it ran in
Table 7.3, and writes `LVL_OUTS/final_replication_publication_report.md` and
`LVL_OUTS/final_replication_supp_tables.tex`.

**Units.** Per trial = an absolute change in the measure divided by the stimulus-trials removed (vs the matched null:
each random removal by its own count), shown × 10⁻⁶. % of trials removed is reported beside it as the volume.

**Condition names.** The figures of `make_replication_figures` print the manuscript's cohort names, CA for T2 and CB
for T3 (`COHORT`, `[cell 1]`); everything else, the run notebooks' own figures included, keeps T2 and T3 (Conditions,
at the top of this README).

---

## 8. Checking a run

- **Complete:** every notebook ends without an exception, and so does every step log
  (`LVL_OUTS/run_logs/run_step<N>_<stamp>.log`); each LVL2 run's log (`LVL_OUTS/run_logs/run_<notebook>_<stamp>.log`)
  ends with the nbconvert "Writing …" line; each run tag has its `_post_index.csv` and every file it lists; the
  report's Table 7.3 has no "no".
- **Stale:** a pin pointing at an older stamp; code that is not the script a sweep ran: `lvl1.py` with a fingerprint
  other than the LVL1 sweep's `pipeline_fingerprint`, or `lvl2.py` differing from the LVL2 sweep's script copy on a
  line check (c) does not admit (section 4; after step 10, `LVL2_sweep_report`'s warning that `lvl2.py` has
  changed since the sweep is expected); a figure whose sidecar pins or inputs differ from the report's pins or the
  current files. `make_replication_figures` stops on stale code; Table 7.3 shows "no" for stale code and stale figures.
- **Failed sweep configurations** leave their output in `errors/` (beside the code); a sweep folder with fewer result
  files than its grid is incomplete: the sweep reports stop on it (re-issue the same launcher command to resume).
- **Common stops and their cause:**
  - "… is not set" / "not an existing … handoff": a pin is `None` or names a missing stamp.
  - "… is not the file … was built from (content differs)": the dataset changed after LVL_0 ran; re-run from step 1.
  - "LVL_1_CONFIG / LVL_2_CONFIG differs from … _selection.json": the configuration was not frozen to the sweep report's
    selection (steps 7, 10).
  - "the sweep … ran on …, not on …": the sweep was made on another handoff.
  - A launcher refusing an `--outdir`: its provenance (script fingerprint, handoff, grid) differs; use a new folder.
  - "inputs not found": an earlier step has not written its exports (the message lists them).
  - "the sweep selections lack …" or "… is not the distinct-solution test": the selection files or the dose contrasts
    lack the fields the checks read; rerun `LVL1_sweep_report` and `LVL2_sweep_report` (steps 6, 9).
  - "… is missing in … and lvl1.py / lvl2.py does not have the sweep's fingerprint": the sweep folder has no script
    copy and the script changed after the sweep; run the sweep again in a fresh `--outdir`.
  - "lineage check failed (nothing drawn)": a check of `make_replication_figures` failed (section 4); the message lists
    each failure.
  - An LVL2 sweep that barely advances: `--metrics alpha` is missing (step 8).

---

## 9. Running from a clean state

1. Keep `dset/all_subjects_long.csv`, the code folder, `sjs_dissertation/archive/` and `audit_history/`. Safe to
   clear: `dervatives/practical_application_emst/lvl_outs`, `sweeps` and `figures`, the `errors/` folder, and the `*_executed.ipynb`
   files beside the code. To keep the three output folders, move them aside outside `dervatives/practical_application_emst` (e.g.
   into `sjs_dissertation/archive/`), never into a subfolder of them: the report searches `LVL_OUTS`, `SWEEPS_DIR`
   and `FIG_DIR` recursively. Nothing outside these is written by the pipeline but the outputs the run notebooks keep
   (section 6).
2. Create `LVL_OUTS/run_logs/` (`mkdir -p`, section 3), then run section 3, steps 1–12, in order, setting each step's
   pins to the stamps the previous steps printed.
3. The new handoffs, sweeps and runs carry new stamps and fingerprints; nothing older is reused.

---

## 10. Changing the pipeline

- This folder is generated: change the pipeline in `code/cpd_and_blk_rep_anaylsis`, then run
  `/usr/bin/python3 -B /home/sjsuss626/EMST_files/sjs_dissertation/code/make_practical_application_emst.py`
  (`--check` first: it writes nothing). By hand, set only the pins and the calibration values (section 3); never edit
  `lvl*.py` or the run notebooks. A regeneration moves this folder, executed notebooks included, to
  `sjs_dissertation/archive/practical_application_emst_<stamp>`, prints the pins and calibration values it held, and
  leaves `dervatives/practical_application_emst` untouched.
- The first line of every code cell is its label. `# [cell N]` is a pipeline cell (N is unique across the three level
  notebooks and increasing; it is the `NOTEBOOK CELL N` banner in the scripts). `# [notebook only]` cells (pins,
  checks, lineage, exports for the reports, figures) never reach a script. `[cell 0]`–`[cell 2]` are identical copies in the
  three notebooks; `[cell 0]` (the thread limits) opens every script, without a banner. `[cell 30]` (LVL2's condition
  selection) is labelled but not emitted: `lvl2.py` selects the condition with `--condition`.
- `PIPELINE_VERSION` (`[cell 2]`, the same literal in the three level notebooks) is the pipeline's version;
  `dump_level_json` records it, with the software versions, in every level's run log. `Replication_and_final_report`
  holds its own copy of the literal (`[cell 1]`) and checks it against the run logs (Table 7.3). A new version is
  written into both places; it changes every script's fingerprint and the version every run log records, so section 3
  is run again from step 1, both sweeps included.
- The build, the launchers and the reports find cells and lines by content anchors (e.g. `LVL_0_CONFIG = {`,
  `TIMESTAMPED LVL_1 HANDOFF`, `STEP 10:`, the stability stage's cut line in `lvl2.py`); each must match exactly once,
  or they stop. Keep them when editing.
- Every knob is read as `CONFIG["key"]`; a missing key stops the run. A new knob is added to the level's config dict
  and becomes a script flag (`--<knob> <python literal>`).
- Labelling rule (`worst_cluster_idx = "speed"`, `identify_inattentive_cluster_by_speed`, `[cell 38]`): in every
  k-means and GMM fit the component with the lowest mean `adj_rt_level_block` is the inattentive one. The other block
  features (the power-transformed RT variance and entropy) are printed as each component's profile; they do not decide
  the label.
