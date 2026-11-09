# Block detection pipeline — general tool

Version 1.0.1.

The pipeline finds blocks of careless responding in rating tasks and tests whether removing them improves inter-rater
reliability (IRR). In a rating task, participants (the raters) rate stimuli on one or more scales, in one or more
sessions; every rating has a response code and a response time (RT). The raters of one condition rate the same stimuli,
so their agreement is measured per scale × condition cell (Krippendorff's α; ICC, Fleiss' κ and split-half reliability
as secondary measures).

Three levels, one notebook each:

- **LVL0** checks the data format, describes response patterns (straight-lining, periodic patterns, a stimulus-linked
  pattern) against per-session permutation nulls, and fits the RT drift model (the warm-up and fatigue trend of each
  scale). Its drift residuals are the RT signal of the later levels.
- **LVL1** computes three stimulus-level features of every participant-session (the drift-adjusted RT level, its
  sliding-window variance and the sliding-window response entropy) and the session's blocks.
- **LVL2** computes three block features, labels the careless blocks (a behavioural heuristic, k-means and a Gaussian
  mixture model, GMM) and compares the IRR after removing the flagged blocks with the IRR after removing as much data at
  random, and after removing whole sessions or whole participants instead.

**Two segmentations** (`LVL_1_CONFIG["segmentation"]`; section 1, [Predefined blocks](#predefined-blocks)):

- **dynamic:** 16 change-point detectors (MAD threshold, PELT and HMM families) find each session's blocks. The LVL1
  sweep calibrates them, H1 compares them, and LVL2 analyses the selected detector's blocks beside matched fixed-size
  control blocks.
- **predefined:** a column of the data gives the blocks (blocks set by the task design, or blocks too short to detect).
  LVL1 computes the features only. There are no detectors, no LVL1 sweep, no H1 and no control blocks.

**Hypotheses.**

- **H1** (dynamic segmentation only): the detectors' blocks differ on the three features. Per detector: η²_H (the
  Kruskal-Wallis effect size, mean over the three features) and Corr% (the share of sessions whose blocks differ
  significantly, sessions with one block counted as not significant); every pair of detectors is tested.
- **H2:** the flagged blocks behave like careless responding. Size: they are a minority (their share is below the
  equal-profile share 1/k of a k-component fit). Speed: they are faster than the unflagged blocks. IRR: their responses
  agree less than the unflagged responses (α, a two-sided test).
- **H3:** removing the flagged blocks raises IRR more than removing as much data at random, and the gain is compared
  with removing the flagged sessions, the flagged participants and, in dynamic segmentation, the flagged control blocks.

**One run on all data.** The sweeps (the LVL2 sweep only, in predefined segmentation) calibrate on every condition and
participant, and the LVL2 run fits every condition at once; its one dataset is "All data". The condition column still
defines the IRR cells (scale × condition); one condition is valid. Every result is in-sample.

**The labelling rule.** In every k-means and GMM fit the fastest component (the lowest mean `adj_rt_level_block`) is the
inattentive one. The other block features are printed as each component's profile; they do not decide the label.

Every result is computed once, by the notebook that owns it, and exported; the reports and the figures read those
exports.

**Sections.** [1. Data format](#1-data-format) · [2. Folder contents](#2-folder-contents) · [3. Setup](#3-setup) ·
[4. Run order](#4-run-order) · [5. Pins, checks and lineage](#5-pins-checks-and-lineage) ·
[6. Calibration](#6-calibration) · [7. The LVL2 run](#7-the-lvl2-run) · [8. Reading the outputs](#8-reading-the-outputs)
· [9. Troubleshooting](#9-troubleshooting) ·
[10. Running from a clean state; changing the pipeline](#10-running-from-a-clean-state-changing-the-pipeline)

---

## 1. Data format

One CSV file in long format: one row per rating, that is, per participant × session × stimulus × scale. It lives in
`<PROJECT_ROOT>/dset/` and is named by `INPUT_LONG_FILE` (section 3, [Paths](#paths)). The input check of the LVL0
notebook (`check_input_data`, `[cell 3]`) reads it before anything else, changes nothing, and stops on every broken
rule, listing the rule, the count and up to 20 offending rows (row = the 0-based data row; file line = row + 2).

### Required columns

| Column | Rule |
|---|---|
| `id` | whole number; one `condition` per id; `age` constant within id |
| `condition` | non-numeric text (e.g. "A"); constant within id; a condition's raters rate one stimulus set; IRR cells are scale × condition; one condition is valid |
| `session` | whole number; participants may differ in their number of sessions |
| `scale` | text; the keys of `scale_ranges`/`scale_types` (LVL1 stops otherwise); one row per stimulus × scale (duplicates stop; a missing scale row is allowed and is a missing rating — EMST has 64 such stimuli); scales answered in a fixed order |
| `stim_order` | whole number ≥ 1; the stimulus position within the session; the first `pr_stim_drop` are practice (LVL0 drift fits only) |
| `resp_order` | whole number; the participant's keypress order (may run on across sessions); no missing values |
| `stim_label` | int or text; the same on every scale row of a stimulus; the IRR item; a rater's second rating of the same `stim_label` is a repeat exposure |
| `response` | integer code within `scale_ranges[scale]`; missing allowed; out of range → missing in LVL1 (Table 0.11) and `invalid_resp` in the LVL2 export |
| `rt_sec` | seconds > 0 (≤ 0 stops); missing allowed |

The check also requires a value of `stim_label` in every row and, when the file has an `age` column, a number in every
row of it. "A fixed order" means: within a participant-session the scale rows of every stimulus, ordered by
`resp_order`, follow the order of the session's most frequent complete stimulus (a stimulus may lack a scale row).

### Optional columns

- `age`: numeric, constant per id. Without it, `max_age`, `age_group_split` and the age-adjustment switches must be None
  or False (the check stops otherwise).
- `sex`: tabulated by `demographic_report`.
- The predefined block column ([Predefined blocks](#predefined-blocks)).
- Any other column passes through to the LVL2 export; a column without a description is listed as undocumented.
- `trial_label` is rebuilt by LVL1.

### Example

Two stimuli of one session, rated on three scales (`design_block` is an optional predefined block column):

| id | condition | session | scale | stim_order | resp_order | stim_label | response | rt_sec | age | sex | design_block |
|---|---|---|---|---|---|---|---|---|---|---|---|
| 101 | A | 1 | valence | 1 | 1 | img_017 | 3 | 2.41 | 24 | female | 1 |
| 101 | A | 1 | arousal | 1 | 2 | img_017 | 6 | 1.87 | 24 | female | 1 |
| 101 | A | 1 | threat | 1 | 3 | img_017 | 2 | 1.12 | 24 | female | 1 |
| 101 | A | 1 | valence | 2 | 4 | img_042 | 7 | 3.05 | 24 | female | 1 |
| 101 | A | 1 | arousal | 2 | 5 | img_042 |  | 4.30 | 24 | female | 1 |
| 101 | A | 1 | threat | 2 | 6 | img_042 | 4 | 0.98 | 24 | female | 1 |

The fifth row has no response (an empty cell is a missing value). With these scales, `scale_ranges` could be
`{"valence": (1, 9), "arousal": (1, 9), "threat": (1, 5)}` and `scale_types`
`{"valence": "ordinal", "arousal": "ordinal", "threat": "ordinal"}`. The scales, their codes and the stimuli per session
come from the data and these two settings; the periodic-pattern markers use the periods 2 … S − 1 of S scales (none with
S ≤ 2).

### Conditions, sessions and repeat exposures

- **Conditions.** A condition is a group of raters who rate one stimulus set; each participant belongs to one. The IRR
  of each scale is computed within each condition and summarised over the scale × condition cells. The LVL2 run fits all
  conditions together; one condition is valid. Condition labels are text (e.g. "A", "B").
- **Sessions.** Participants may have different numbers of sessions. When at least one participant has 2 or more, the
  LVL2 run adds the session design (flagged sessions removed); with one session each, the per-session fit is reported as
  the participant design, and the export's `*_bb_session` columns equal `*_bb_participant`. In dynamic segmentation a
  session needs at least 2 × `min_block_size` stimuli (room for two blocks): LVL1 skips a shorter one (it is not
  segmented and is absent from the LVL_1 handoff and every later step) and prints
  `skipped: participant <id>, session <s>: <n> stimuli < 2 x min_block_size = <2 × min_block_size>` for each.
- **Repeat exposures.** A rater's later rating of a `stim_label` they had already rated (ordered by session, then
  `stim_order`) is a repeat exposure. It stays in every feature but is masked from every IRR measure (the first exposure
  is kept). When the data hold repeat exposures, the run adds a sensitivity analysis with the sessions that hold them
  dropped (Tables 5.12–5.13).

### Predefined blocks

In predefined segmentation the blocks come from a column of the data, named by `LVL_1_CONFIG["predefined_block_col"]`
(LVL1 notebook `[cell 9]`); the name must not start with `block_`. A block is an id within one participant-session: ids
may restart each session (block 1 of session 1 and block 1 of session 2 are different blocks), and they may be numbers
or text. `validate_predefined_blocks` (`[cell 19]`, run by `[cell 20]` on the rows of the LVL_0 handoff) checks four
rules:

1. every rating row has a block id;
2. a stimulus (id × session × stim_order) has one block id, the same on all its scale rows;
3. within a participant-session a block id is one unbroken run of its stimuli in stim_order (ids may restart each
   session; a block never spans sessions);
4. every block has 2 or more stimuli.

A violation stops LVL1 before any detection, with the message
`predefined blocks (<column>) break the block-id rules; every offending row: <LVL_OUTS>/predefined_block_violations.csv. Fix the data and rerun from LVL_0:`
followed by each broken rule, its row count and up to 30 rows. `predefined_block_violations.csv` holds every offending
row, with the columns `id, session, stim_order`, `scale` (rules 1 and 2), the block column and `rule` (e.g.
`4 block of fewer than 2 stimuli`). The block column passes through LVL0 unchanged, so after fixing the data rerun from
step 1.

LVL1 numbers the blocks 0 … k − 1 in stimulus order within each session (column `block_Predefined`), validates them with
the tests it applies to a detector's blocks (`results.csv`), and hands them to LVL2 as the one method `Predefined`. Rule
4 counts stimuli, not valid RTs: a block with fewer than 2 valid RTs has a missing RT variance and still counts as a
unit. Short blocks change the heuristic's block rule: a block is flagged when more than
`inattent_behav_block_percent_thresh` % of its trials (rating rows with an RT) carry a marker, and one marked stimulus
in a block of k stimuli is 100/k % of it. Set it to at least 100/k of the smallest blocks (25 when the smallest blocks
have 4 stimuli), and expect run-length markers (e.g. a straight-line run) to span several blocks. LVL1 prints the block
sizes at step 7 (`predefined blocks (<column>): <n> blocks in <m> sessions; stimuli per block median … (min …, max …)`);
the setting is needed from step 8's build on.

---

## 2. Folder contents

| File | Role |
|---|---|
| `block_detection_and_removal_LVL{0,1,2}.ipynb` | The pipeline, the source of the scripts. The LVL2 notebook is the template of the run notebook; it stops at its first code cell when run itself. |
| `block_detection_and_removal_LVL2_all_rep.ipynb` | The LVL2 run notebook (step 10), written by the build: the template with `RUN_NAME` and `n_jobs` set. Never edit it except its two pins. |
| `build_level_scripts.py` | Builds `lvl0.py`, `lvl1.py`, `lvl2.py`, the run notebook and the upstream-definitions cells of the LVL2 notebook and of `LVL1_report`, and checks them. `RUN_N_JOBS` (top) is the run notebook's CPU count. |
| `lvl0.py`, `lvl1.py`, `lvl2.py` | Command-line levels written by the build (step 4); never edit them. `lvl1.py` and `lvl2.py` are the sweep workers; the final report runs `lvl2.py` read-only through its Step 5 (`[cell 9]`). No step runs `lvl0.py` (its handoff lacks the LVL0 notebook's decay-fit exports, which `LVL0_report` and the figures read). |
| `launch_LV1_sweep_random.py`, `launch_LV2_sweep_random.py` | The sweep launchers (section 6); the LVL1 sweep exists in dynamic segmentation only. They write their sweep folders and, when a configuration fails, the `errors/` folder beside the code (one `<outdir>_<config>.err` file per failed configuration). |
| `submit_BDR_LVL2_notebooks_all.sh` | Runs the run notebook, executed in place, on the CPUs of `CPU_SET` (step 10 (b)). |
| `sweep_provenance.py` | Provenance checks of the sweep folders, used by the launchers and the sweep reports. |
| `demographic_report.ipynb` | Sample description: Table 0.1 (sample by condition), the sample flow, the sample characteristics, sessions per participant and the participants with fewer sessions, with an optional ledger of reasons. |
| `LVL0_report.ipynb` | Session duration, RT limits, drift-model tables. |
| `LVL1_sweep_report.ipynb` | LVL1 calibration tables and the selection (dynamic segmentation). |
| `LVL1_report.ipynb` | Chosen participants' sessions from a LVL_1 handoff: the three features, the detectors' smoothing (dynamic) and every block method's blocks (draws only). |
| `LVL2_sweep_report.ipynb` | LVL2 calibration (DSC with the a-priori standard, stability, dose-response) and the selection. |
| `make_replication_figures.ipynb` | Every figure, from the exports, with a provenance sidecar. |
| `Replication_and_final_report.ipynb` | Assembles every table into one Markdown report (+ the supplementary tables as LaTeX), lists every check it ran in Table 7.3 and links the figures. |
| `README.md`, `.gitignore` | This file; the outputs and executed copies kept out of version control. |

**Who computes what.** Each result has one owner; everything downstream reads its exports.

| Results (report tables) | Owner | Exports (in `LVL_OUTS` unless noted) | Read by |
|---|---|---|---|
| Sample by condition, sample flow, sample characteristics, sessions per participant (0.1, 0.7–0.10) | `demographic_report` | `lv0_out_<ts>_demographics_*.csv` | report |
| Preprocessing, drift fits | LVL0 notebook | `lv0_out_<ts>.csv`, `_parameters.json`, `_decay_fits.csv`, `_decay_curves.csv` | LVL1, `LVL0_report`, figures |
| Session duration, RT limits, drift tables (0.2, 0.2b, 0.4–0.6) | `LVL0_report` | `lv0_out_<ts>_report_*.csv` | report |
| LVL1 calibration (1.1–1.4; dynamic) | LVL1 sweep (launcher) → `LVL1_sweep_report` | `sweeps/_sweep_lvl1_all/`; `_sweep_lvl1_all_report_*.csv`, `_selection.json` | LVL1 notebook, report, figures |
| Segmentation; H1 (2.1–2.6, 2.10; dynamic); behavioural features, out-of-range responses, age check (0.3, 0.11–0.13) | LVL1 notebook | `lv1_out_<ts>_{long,features,results}.csv`, `_meta.json`, `_parameters.json`, `_h1_*.csv` (dynamic), `_report_*.csv` | LVL2, `LVL1_report`, report, figures |
| LVL2 calibration: DSC, stability, dose-response (3.1–3.7) | LVL2 sweep (launcher) → `LVL2_sweep_report` | `sweeps/_sweep_lvl2_all_<method>/`; `<sweep>_report_*.csv`, `_selection.json` | LVL2 run, report, figures |
| H2, H3, secondary measures, post hoc analyses (3.8–5.21) | the LVL2 run notebook | `lv2_out_<method>_all_<ts>_*` (section 7) | report, figures |
| H1 method-level association (2.8–2.9; dynamic); the claims (6.1); the BH families stated under its tables; the summaries of 5.11 and 5.18–5.19; the exact-zero folded units (4.30–4.32, from a read-only rebuild by `lvl2.py`, `[cell 9]`) | `Replication_and_final_report` | `final_replication_publication_report.md`, `final_replication_supp_tables.tex` | — |
| Figures | `make_replication_figures` | `figures/pub_figures/**/fig_*.png` + `.json` | report (links, sidecar check) |

**What is written where.** The pipeline writes its outputs to `LVL_OUTS`, `SWEEPS_DIR` and `FIG_DIR` (section 3). Into
this folder it writes only the build's outputs (`lvl0.py`, `lvl1.py`, `lvl2.py`, the run notebook and the two
upstream-definitions cells), the launchers' `errors/` folder (made at the first failed sweep configuration), the `*_executed.ipynb`
copies of command-line notebook runs (section 3, [The command line](#the-command-line)) and the outputs the run notebook
keeps when it is executed in place (step 10 (b)).

---

## 3. Setup

### Python, packages and the Jupyter kernel

- **Python 3** with numpy, pandas, scipy, scikit-learn, statsmodels, hmmlearn, ruptures, joblib, matplotlib and seaborn,
  and Jupyter (nbconvert, ipykernel, IPython) to run notebooks. Versions as tested: Python 3.10.12, numpy 1.26.4, pandas
  2.2.1, scipy 1.12.0, scikit-learn 1.7.2, statsmodels 0.14.6, hmmlearn 0.3.3, ruptures 1.1.10, joblib 1.5.3, matplotlib
  3.10.8, seaborn 0.13.2, nbconvert 7.16.6, ipykernel 6.29.4, IPython 8.22.2. Optional: pyarrow or fastparquet (a
  Parquet copy of the run's annotated export; without them the run prints "Parquet export skipped"), and rpy2 with the R
  package TOSTER (only for `LVL_1_CONFIG["merge_method"]` "robust_tost"; the default is "wilcoxon").
- **Linux and `taskset`** (util-linux) pin a run to a set of CPUs. Without `taskset`, set `PIN=""`
  ([The command line](#the-command-line)) and `CPU_SET = ""`: nothing is pinned.
- **The interpreter.** Every notebook, script and launcher must run with the interpreter that has the packages (`PY` of
  [the command line](#the-command-line); `PYTHON` of the submit script). Every level's run log
  (`<stem>_parameters.json`) records the pipeline version (`pipeline_version`) and the interpreter and package versions
  (`software`); the LVL0, LVL1 and LVL2 notebooks print them in their first code cell.
- **The kernel.** The notebooks are saved with the kernel `python3` ("Python 3 (ipykernel)"). A kernel is a name bound
  to an interpreter: `jupyter kernelspec list` (or `$PY -m jupyter kernelspec list`) lists the kernels and their
  folders, and each folder's `kernel.json` names its interpreter (the first entry of `argv`). If `python3` runs an
  interpreter without the packages (e.g. another virtual environment), register one that runs `PY` and use its name:
  `$PY -m ipykernel install --user --name <name>`. On the command line it is `KERNEL` ([below](#the-command-line)); in
  Jupyter pick it under Kernel → Change kernel; for step 10 (b) it is `JUPYTER_KERNEL`. A `kernel.json` whose `argv`
  starts with a bare `python` runs the interpreter that runs Jupyter or nbconvert: `PY` in `NB` and `PYTHON` in the
  submit script, whichever environment holds the kernel's folder; Jupyter itself needs a kernel that names `PY`.
- **No bytecode.** Scripts run with `python -B` and the launchers pass `-B` to every worker; the notebooks import
  `sweep_provenance.py` without writing `__pycache__/`; command-line notebook runs set `PYTHONDONTWRITEBYTECODE=1` (the
  `NB` function below).
- **Long runs** can go in `tmux` (optional): a `tmux` session keeps running when the terminal or a remote (SSH)
  connection closes (`tmux new -s <name>`; detach Ctrl-b d; `tmux attach -t <name>` to return).

### The command line

The steps of section 4 run from this folder. Set up each shell once:

```bash
cd <PROJECT_ROOT>/code/practical_application_generic
PY=/usr/bin/python3; KERNEL=python3; PIN="taskset -c 0-7"   # PIN="" = no pinning
LOGS=../../dervatives/practical_application_generic/lvl_outs/run_logs; mkdir -p "$LOGS"
NB() { PYTHONDONTWRITEBYTECODE=1 $PIN $PY -m nbconvert --to notebook --execute --ExecutePreprocessor.kernel_name=$KERNEL --ExecutePreprocessor.timeout=-1 --output "${1%.ipynb}_executed.ipynb" "$1" 2>&1 | tee "$LOGS/run_${1%.ipynb}_$(date +%Y%m%d_%H%M%S).log"; return ${PIPESTATUS[0]}; }
```

- `PY`: the interpreter with the packages; `KERNEL`: a kernel that runs it (above, "The kernel"); `PIN`: the CPUs of the
  command-line steps (as many as `n_jobs`).
- `NB <notebook>` executes the notebook and writes the executed copy `<notebook>_executed.ipynb` beside it; the notebook
  itself is unchanged. Its log is `LVL_OUTS/run_logs/run_<notebook>_<stamp>.log`.
- A stop (a check, a missing input) ends the output with `SystemExit: <message>` and writes no executed copy. `NB`
  returns nbconvert's exit status (`${PIPESTATUS[0]}`: 0 for a complete run, non-zero for a stop), so
  `NB <notebook> && …` runs the next command only after a complete run.

### Paths

`PROJECT_ROOT` is the absolute project folder holding `code/`, `dset/` and `dervatives/` (spelled so). Everything the
pipeline reads and writes is inside it:

```
<PROJECT_ROOT>/
  code/practical_application_generic/        this folder (CODE_DIR)
  dset/<INPUT_LONG_FILE>                     the data (INPUT_LONG_PATH)
  dervatives/practical_application_generic/
    lvl_outs/                                LVL_OUTS
      run_logs/                              the step logs (section 4)
      warnings/                              WARNINGS_OUTS
    sweeps/                                  SWEEPS_DIR
    figures/                                 FIG_DIR of the levels (save_figures True only)
      pub_figures/{main_text,supplement}/    the figures of make_replication_figures
```

| Name | Path | Contents |
|---|---|---|
| `INPUT_LONG_PATH` | `<PROJECT_ROOT>/dset/<INPUT_LONG_FILE>` | the long-format data (section 1) |
| `LVL_OUTS` | `<PROJECT_ROOT>/dervatives/practical_application_generic/lvl_outs` | every handoff, run log, export and report |
| `SWEEPS_DIR` | `<PROJECT_ROOT>/dervatives/practical_application_generic/sweeps` | the sweep folders |
| `FIG_DIR` | `<PROJECT_ROOT>/dervatives/practical_application_generic/figures` | the levels' figures (only when a level's `save_figures` is True) and `LVL2_sweep_report`'s (only when one of its `*_SAVE` names is set); the figures notebook and the report use its `pub_figures/` |
| `WARNINGS_OUTS` | `<LVL_OUTS>/warnings` | `suppressed_warnings.log` (each level run overwrites it) and each LVL2 run's `<run tag>_warnings.log` |
| `CODE_DIR` | `<PROJECT_ROOT>/code/practical_application_generic` | this folder: `lvl1.py`, `lvl2.py`, the launchers' `errors/` |

Every file that names a path holds `PROJECT_ROOT = "SET_ME"` (in the submit script `PROJECT_ROOT="SET_ME"`): the three
level notebooks (`[cell 2]`), the six reports and the figures notebook (`[cell 1]`), both launchers and the submit
script (top). **Step 0**, once: put the data file in `<PROJECT_ROOT>/dset/`, then, from this folder, set `PROJECT_ROOT`
in every file and the data file and CPU count in the three level notebooks:

```bash
cd <PROJECT_ROOT>/code/practical_application_generic
ROOT="$(cd ../.. && pwd)"; sed -i -e 's|PROJECT_ROOT = "SET_ME"|PROJECT_ROOT = "'"$ROOT"'"|' -e 's|PROJECT_ROOT = \\"SET_ME\\"|PROJECT_ROOT = \\"'"$ROOT"'\\"|' -e 's|PROJECT_ROOT="SET_ME"|PROJECT_ROOT="'"$ROOT"'"|' *.ipynb *.py *.sh
sed -i -e 's|INPUT_LONG_FILE = \\"SET_ME\\"|INPUT_LONG_FILE = \\"<file>.csv\\"|' -e 's|n_jobs = \\"SET_ME\\"|n_jobs = 8|' block_detection_and_removal_LVL[012].ipynb
```

Replace `<file>.csv` by the data file's name and `8` by the CPUs a run may use ([CPUs](#cpus)). The first command
changes one line in each of the 13 files that name a path (in a built folder also one in `lvl0.py`, `lvl1.py`, `lvl2.py`
and the run notebook, which the build rewrites anyway); the second changes two lines in each level notebook. The
notebooks stay valid JSON. The path must not contain `|`, `&`, `\` or `"`. A path set by hand must be absolute
(`[cell 2]` stops otherwise). `PROJECT_ROOT` is the only path setting.

### Settings

Every dataset- or machine-specific setting holds the string `"SET_ME"` until it is set. Each level's configuration cell
ends with a settings check (`check_settings`, defined in `[cell 2]`) that stops, listing every setting of that level
still at `"SET_ME"`, where it lives and what to set; the other notebooks, the launchers and the submit script check
their own settings the same way and name themselves by their file name (e.g. `settings check (LVL0_report.ipynb)`,
`settings check (launch_LV2_sweep_random.py)`). Every entry gives what to set and the EMST value. This is what
`lvl0.py` prints with nothing set:

```
settings check (LVL_0): 9 setting(s) still hold "SET_ME". Set each, then run again (README, "Settings"; a script is built from its notebook: set the value there and rerun build_level_scripts.py):
  - n_jobs  ([cell 0] of the three level notebooks; before step 1)
      the CPUs a run may use (your taskset slice), e.g. 8 for taskset -c 0-7; keep it once the scripts are built (step 4); the LVL2 run notebook's is RUN_N_JOBS (build_level_scripts.py); EMST 31
  …
  - LVL_0_CONFIG['max_age']  (LVL0 notebook [cell 3]; before step 1)
      years: the upper age of the target population, older participants are excluded; None = no filter (required without an age column); EMST 30
  …
```

- **The check reads the values written in the cells**, so a script's command-line knob override does not stand in for a
  placeholder (only `--n-jobs`, applied before every cell, stands in for `n_jobs`), and the launchers read the values
  from `lvl1.py` / `lvl2.py`. Set a value in its notebook cell, then build (step 4).
- **Mode.** The LVL1 check knows the segmentation: the dynamic-only settings (L18–L22 below) may stay `"SET_ME"` in
  predefined segmentation. While `segmentation` itself is `"SET_ME"`, every setting is listed, the dynamic-only ones
  marked `; dynamic segmentation only`.
- **The build never stops on `"SET_ME"`:** it builds the delivered placeholder state too, and prints
  `notice: RUN_N_JOBS (top of build_level_scripts.py) holds "SET_ME": …` while `RUN_N_JOBS` is unset.
- **Set each value before the build that precedes the step needing it** (the table's "Before step"): the scripts carry
  the configuration, and every sweep records its script's fingerprint (section 6), so a value changed after a sweep
  makes that sweep stale.

The table gives every placeholder: its key as the check reports it, where it lives, the mode that needs it (B both, D
dynamic, P predefined), the step before which to set it, the EMST value and the recommendation from the author's tests.
"Suggested settings" is the last cell of the LVL0 notebook, which prints starting values from your data (step 1).

| # | Key | File and cell | Mode | Before step | EMST | Recommendation |
|---|---|---|---|---|---|---|
| L1 | `n_jobs` | `[cell 0]` of the three level notebooks | B | 1 (step 0 sets it) | 31 | the CPUs a run may use, e.g. 8 for `taskset -c 0-7`; keep it once the scripts are built ([CPUs](#cpus)) |
| L2 | `PROJECT_ROOT` | `[cell 2]` of the three level notebooks | B | 1 (step 0 sets it) | the author's project folder | the absolute project folder ([Paths](#paths)) |
| L3 | `INPUT_LONG_FILE` | `[cell 2]` of the three level notebooks | B | 1 (step 0 sets it) | `all_subjects_long.csv` | the data file's name in `<PROJECT_ROOT>/dset` |
| L4 | `LVL_0_CONFIG['max_age']` | LVL0 `[cell 3]` | B | 1 | 30 | years: the upper age of the target population (older participants are excluded); None = no filter (required without an age column) |
| L5 | `LVL_0_CONFIG['age_group_split']` | LVL0 `[cell 3]` | B | 1 | 18 | years: younger = age < split, older = the rest (the age groups of the reports); None = no groups (required without an age column) |
| L6 | `LVL_0_CONFIG['pr_stim_drop']` | LVL0 `[cell 3]` | B | 1 | 3 | warm-up stimuli at the start of each session, left out of the drift fits only; 0 = none |
| L7 | `LVL_0_CONFIG['max_rt_thresh']` | LVL0 `[cell 3]` | B | 1 | 90 | seconds: above the 99.5–99.9th percentile of `rt_sec` (suggested settings) or the task's time-out; 0 = off (EMST p99.9: 62.8 s) |
| L8 | `LVL_0_CONFIG['min_rt_thresh']` | LVL0 `[cell 3]` | B | 1 | 0.15 | seconds: 0.15–0.30, the same as L32; read the shares of RTs below 0.15 and 0.30 s (suggested settings; EMST 2.0 % below 0.15 s); 0 = off |
| L9 | `LVL_0_CONFIG['age_adjust_drift_residuals']` | LVL0 `[cell 3]` | B | 1 | True | True when the ages span a range over which RT changes; False without an age column |
| L10 | `LVL_1_CONFIG['segmentation']` | LVL1 `[cell 9]` | B | 4 | "dynamic" | "dynamic", or "predefined" for blocks the data give or blocks too fine to detect |
| L11 | `LVL_1_CONFIG['predefined_block_col']` | LVL1 `[cell 9]` | B | 4 | None | predefined: the block-id column (not starting with `block_`); dynamic: None |
| L12 | `LVL_1_CONFIG['scale_ranges']` | LVL1 `[cell 9]` | B | 4 | `{"valence": (1, 9), "arousal": (1, 9), "emotion": (1, 7), "similarity": (1, 6), "threat": (1, 5)}` | `{scale: (lowest, highest) valid code}`; the keys are exactly the data's scales |
| L13 | `LVL_1_CONFIG['scale_types']` | LVL1 `[cell 9]` | B | 4 | emotion "nominal", the others "ordinal" | `{scale: "ordinal" or "nominal"}`, the keys of L12; "nominal" for unordered categories |
| L14 | `LVL_1_CONFIG['max_rt_thresh']` | LVL1 `[cell 9]` | B | 4 | 90 | as L7; a rejected RT reaches the features as `rt_threshold_na_handling` says |
| L15 | `LVL_1_CONFIG['age_adjust_drift_residuals']` | LVL1 `[cell 9]` | B | 4 | True | = L9 (LVL1 stops if LVL0 wrote no `_age` residual columns) |
| L16 | `LVL_1_CONFIG['derivative_filter_size']` | LVL1 `[cell 9]` | B | 4 | 9 | an odd number of stimuli spanning about 2 min of task time (suggested settings; Esterman et al., 2013) |
| L17 | `LVL_1_CONFIG['min_periods']` | LVL1 `[cell 9]` | B | 4 | 8 | the window − 1, i.e. L16 − 1 |
| L18 | `LVL_1_CONFIG['mad_window_size']` | LVL1 `[cell 9]` | D | 4 | 9 | = L16 (odd), or None for one global MAD |
| L19 | `LVL_1_CONFIG['min_block_size']` | LVL1 `[cell 9]` | D | 4 | 20 | the multiple of 10 stimuli spanning about 4 min (suggested settings), so the PELT jumps 1, 2 and 5 all divide it |
| L20 | `LVL_1_CONFIG['pelt_pen_uni']` | LVL1 `[cell 9]` | D | 4 | 5.298 | ln(n), n = the median stimuli per session (suggested settings; EMST n = 200) |
| L21 | `LVL_1_CONFIG['pelt_pen_multi']` | LVL1 `[cell 9]` | D | 4 | 15.895 | 3 ln(n), one ln(n) per feature of the three-feature composite |
| L22 | `LVL_1_CONFIG['hmm_transmat_self_prior']` | LVL1 `[cell 9]` | D | 4 | 200 | n, the median stimuli per session: a pseudo-count against the ~n − 1 transitions of a session |
| L23 | `LVL_2_CONFIG['scale_ranges']` | LVL2 `[cell 28]` | B | 8 | as L12 | = L12 (`[cell 29]` checks it against the LVL_1 handoff) |
| L24 | `LVL_2_CONFIG['scale_types']` | LVL2 `[cell 28]` | B | 8 | as L13 | = L13 (checked likewise) |
| L25 | `LVL_2_CONFIG['max_rt_thresh']` | LVL2 `[cell 28]` | B | 8 | 90 | = L14 |
| L26 | `LVL_2_CONFIG['analysis_method']` | LVL2 `[cell 28]` | B | 8 | "PELT_Attention_comp" | dynamic: the detector of the LVL1 sweep's selection; predefined: "Predefined" |
| L27 | `LVL_2_CONFIG['age_adjust_variance']` | LVL2 `[cell 28]` | B | 8 | True | True when the ages span a range over which the RT variance changes (EMST: variance d = +0.31); False without an age column |
| L28 | `LVL_2_CONFIG['age_adjust_entropy']` | LVL2 `[cell 28]` | B | 8 | True | as L27; entropy is also an outcome (α uses the same responses), see the comment beside it |
| L29 | `LVL_2_CONFIG['inattent_behav_sl_thresh']` | LVL2 `[cell 28]` | B | 8 | 21 | the ALL 99th column of the LVL0 marker table (about 1 % of participant-sessions under the null); the 95th (about 5 %) is more liberal (EMST 14) |
| L30 | `LVL_2_CONFIG['inattent_behav_periodic_thresh']` | LVL2 `[cell 28]` | B | 8 | `{2: 9, 3: 11, 4: 13}` | `{period: run length}` for the periods 2 … S − 1 of S scales, from the ALL 99th column (95th: EMST `{2: 8, 3: 9, 4: 11}`); `{}` with S ≤ 2 |
| L31 | `LVL_2_CONFIG['inattent_behav_ip_thresh']` | LVL2 `[cell 28]` | B | 8 | 8 | the stimulus-linked pattern (stimuli), from the ALL 99th column (95th: EMST 4) |
| L32 | `LVL_2_CONFIG['inattent_behav_fast_rt_thresh']` | LVL2 `[cell 28]` | B | 8 | 0.15 | seconds: 0.15–0.30, = L8 |
| L33 | `LVL_2_CONFIG['inattent_behav_block_percent_thresh']` | LVL2 `[cell 28]` | B | 8 | 5.0 | % of a block's trials (rating rows with an RT) carrying a marker: one marked stimulus in a block of k stimuli is 100/k %, so at least 100/k of the smallest blocks, from LVL1's step-7 line `predefined blocks (…): …; stimuli per block median … (min …, max …)` (smallest blocks of 4 stimuli: 25); dynamic: 5.0 |
| R1 | `RUN_N_JOBS` | `build_level_scripts.py`, top | B | 10 | 31 (9 + 9 + 13 over its three runs) | the run notebook's CPUs (its `[cell 0]` `n_jobs`), = the CPU count of `CPU_SET`; changing it changes no script |
| R2 | `SWEEP_WORKERS (or --workers)` | `launch_LV1_sweep_random.py`, top | D | 5 | 30 | concurrent `lvl1.py` processes (each `--n-jobs 1`): the CPUs of your slice; `--workers` replaces it |
| R3 | `SWEEP_WORKERS (or --workers)` | `launch_LV2_sweep_random.py`, top | B | 8 | 30 | concurrent `lvl2.py` processes of the grid stage and the joblib workers of the a-priori and stability stages; `--workers` replaces it |
| R4 | `PROJECT_ROOT` | both launchers and the submit script (top); `demographic_report`, `LVL0_report`, `LVL1_report`, `LVL1_sweep_report`, `LVL2_sweep_report`, `make_replication_figures`, `Replication_and_final_report` (`[cell 1]`) | B | each step (step 0 sets it) | as L2 | as L2 |
| R5 | `PYTHON` | `submit_BDR_LVL2_notebooks_all.sh`, top | B | 10 (b) | `/usr/bin/python3` | the interpreter with the packages (`PY`) |
| R6 | `JUPYTER_KERNEL` | `submit_BDR_LVL2_notebooks_all.sh`, top | B | 10 (b) | `block_detection_irt` | a kernel that runs `PYTHON` (`jupyter kernelspec list`; `KERNEL`) |
| R7 | `CPU_SET` | `submit_BDR_LVL2_notebooks_all.sh`, top | B | 10 (b) | `0-30` | the taskset CPU list of the run, with `RUN_N_JOBS` CPUs, e.g. `0-7`; "" = no pinning |
| R8 | `CPU_SET` | `Replication_and_final_report` `[cell 1]` | B | 12 | `0-30` | the taskset CPU list of `[cell 9]`'s `lvl2.py` rebuild, e.g. "0-7"; "" = no pinning |
| R9 | `REPORT_N_JOBS` | `Replication_and_final_report` `[cell 1]` | B | 12 | 31 | the joblib workers of that rebuild, e.g. 8 |
| R10 | `SWITCHERS` | `LVL1_report` `[cell 1]` | B | 7a | 30 ids | participant ids to draw (e.g. suspected attention shifts on manual review); `[]` = none |
| R11 | `PARTICIPANT_FIGURES` | `make_replication_figures` `[cell 1]` | B | 11 | `[4064, 1051]` | analysed ids to draw, one figure each; `[]` = none |
| R12 | `MOSAIC_PARTICIPANTS` | `make_replication_figures` `[cell 1]` | B | 11 | `[4064, 1051]` | dynamic: two analysed ids with clear blocks, the two columns of the LVL1 calibration figure; predefined: `[]` |

**Not placeholders.**

- **Pins** (section 5): `LVL0_HANDOFF`, `LVL1_HANDOFF`, `LVL1_SWEEP`, `LVL2_SWEEP`, `SWEEP_DIR`, `SWEEP_DIRS` and
  `RUN_TAGS["all"]` hold `None` until set; a pin at `None` stops the notebook (the handoff pins list the files
  available). `LVL1_SWEEP` stays `None` in predefined segmentation.
- **Optional records** (`demographic_report` `[cell 2]`, empty by default): `SESSION_MISSING_REASONS` (why a participant
  has fewer sessions: `{id: (category, description)}`), `WITHDRAWN` (`{id: description}`), `CORRECTIONS`
  (`[(field, what, why)]`) and `COVARIATES` (`{column: label}`, participant-level columns described in the
  sample-characteristics table). `COVARIATE_DESCRIPTIONS` (LVL2 `[cell 56]`, `{column: description}`) documents the
  pass-through columns in the run's data dictionary; it is part of `lvl2.py`, so fill it before step 8's build.
- **Method defaults**, kept with a comment: the replicate counts, seeds, α levels, BH families, the `h2_*` settings
  (`h2_robustness_a_min_stimuli` 20 and `h2_robustness_b_min_raters` 10: lower them with few stimuli per participant),
  `irr_min_units` (at least 1), `stability_refits` (5,000; the LVL2 sweep's stability stage refits as often), the sweep
  reports' `CV_MAX` (0.60) and `DEGENERATE_DSC` (0.20) and the report's `P1_NCHK` (62). `LVL_1_CONFIG` and
  `LVL_2_CONFIG` keep `min_rt_thresh` 0 and `pr_stim_drop` 0 (off;
  the EMST values): LVL0's L6–L8 shape its drift fits and RT diagnostics, and the heuristic's fast-RT floor is L32.
- **Calibrated starting values:** `smoothing_window` 7 and `pelt_jump` 1 (LVL1 `[cell 9]`), the exponents 0.05 / 2.75 /
  0.05 / 0.10 and the k lists `[2]` / `[2]` (LVL2 `[cell 28]`). They are the validation pipeline's selections on the
  EMST data; set them from your sweeps' selections (steps 7 and 10), and the calibration checks stop until they match.

### CPUs

- **`n_jobs`** (`[cell 0]`, L1): the joblib workers of LVL0, LVL2 and LVL1's detection (`LVL_1_CONFIG["n_jobs"]` None =
  this value). It is part of every script, so set it at step 0 (e.g. 8 for `taskset -c 0-7`) and keep it once the
  scripts are built: changing it changes every script's fingerprint, and the sweeps then describe other scripts (step 4
  again, both sweeps again). `lvl*.py --n-jobs` replaces it for one run; the launchers pass `--n-jobs 1` to every
  worker.
- **`--workers` / `SWEEP_WORKERS`** (R2, R3): the launchers' concurrent processes, one CPU each, and the LVL2 sweep's
  a-priori and stability workers; the CPUs of your slice.
- **`RUN_N_JOBS`** (R1): the run notebook's `n_jobs`, written by the build into its `[cell 0]` only; the template and
  the scripts keep `[cell 0]`'s value, so it can change at any build.
- **`CPU_SET`** (R7, R8) and **`PIN`** ([The command line](#the-command-line)): the `taskset` CPU lists of the submit
  script, of the report's rebuild and of the command-line steps; give each as many CPUs as its worker count.
  `REPORT_N_JOBS` (R9) is the report rebuild's worker count.
- Worker counts and CPU pinning change no result: every random draw is seeded.

---

## 4. Run order

Every step runs from this folder, in a shell set up as in section 3 ([The command line](#the-command-line)). A notebook
runs top to bottom, in Jupyter (open it, pick the kernel, Run All) or on the command line with the `NB` function. Before
each step, set what the table names: its pins (the first lines of its first code cell) to the outputs of the earlier
steps, and its settings (section 3). Each command-line step writes its log to `LVL_OUTS/run_logs/`.

**Before step 1**, once: the shell of [The command line](#the-command-line), then step 0 of [Paths](#paths) (the data
file and two commands).

### Dynamic segmentation

| Step | Before it, set | Command | Writes |
|---|---|---|---|
| 1 | `LVL_0_CONFIG` L4–L9 (LVL0 `[cell 3]`) | `NB block_detection_and_removal_LVL0.ipynb` | `lv0_out_<ts>.csv`, `_parameters.json`, `_decay_fits.csv`, `_decay_curves.csv`; prints the suggested settings |
| 2 | `LVL0_HANDOFF`; optionally the records and `COVARIATES` of `[cell 2]` | `NB demographic_report.ipynb` | `lv0_out_<ts>_demographics_*.csv` |
| 3 | `LVL0_HANDOFF` | `NB LVL0_report.ipynb` | `lv0_out_<ts>_report_*.csv` |
| 4 | `LVL_1_CONFIG` L10–L22 (LVL1 `[cell 9]`); `LVL_2_CONFIG` L23–L25, L27–L33 (LVL2 `[cell 28]`; at the latest before step 8); `RUN_N_JOBS` (at the latest before step 10) | `$PY -B build_level_scripts.py` | `lvl0.py`, `lvl1.py`, `lvl2.py`, the run notebook, the upstream-definitions cells |
| 5 | `SWEEP_WORKERS` or `--workers` | the LVL1 sweep (below) | `sweeps/_sweep_lvl1_all/` |
| 6 | `SWEEP_DIR` | `NB LVL1_sweep_report.ipynb` | `_sweep_lvl1_all_report_*.csv`, `_sweep_lvl1_all_selection.json` |
| 7 | the selection's `smoothing_window` / `pelt_jump` in `[cell 9]` (if they differ: step 4, step 5 into a fresh `--outdir`, step 6); `LVL0_HANDOFF`, `LVL1_SWEEP` | `NB block_detection_and_removal_LVL1.ipynb` | `lv1_out_<ts>_{long,features,results}.csv`, `_meta.json`, `_parameters.json`, `_h1_*.csv`, `_report_*.csv` |
| 7a | `LVL1_HANDOFF`, `SWITCHERS` (optional step) | `NB LVL1_report.ipynb` | nothing (figures in the notebook) |
| 8 | `analysis_method` (L26) = the selected detector; step 4 again; `SWEEP_WORKERS` or `--workers` | the LVL2 sweep (below) | `sweeps/_sweep_lvl2_all_<detector>/` with `apriori/` and `stability/` |
| 9 | `SWEEP_DIRS`, `LVL1_HANDOFF` | `NB LVL2_sweep_report.ipynb` | `<sweep>_report_*.csv`, `<sweep>_selection.json` |
| 10 | the selection's family knobs in `[cell 28]`; step 4 again; the run notebook's `LVL1_HANDOFF`, `LVL2_SWEEP` | (a) Jupyter, or (b) the submit script (below) | `lv2_out_<detector>_all_<ts>_*` |
| 11 | `LVL0_HANDOFF`, `LVL1_HANDOFF`, `LVL1_SWEEP`, `LVL2_SWEEP`, `RUN_TAGS["all"]`, R11, R12 | `NB make_replication_figures.ipynb` | `figures/pub_figures/**/fig_*.png` + `.json` |
| 12 | as step 11, and R8, R9 | `NB Replication_and_final_report.ipynb` | `final_replication_publication_report.md`, `final_replication_supp_tables.tex` |

The steps that are not notebooks:

```bash
# step 4 (and again before steps 8 and 10)
$PY -B build_level_scripts.py 2>&1 | tee "$LOGS/run_step4_$(date +%Y%m%d_%H%M%S).log"

# step 5: the LVL1 sweep
$PIN $PY -B launch_LV1_sweep_random.py --lvl0-input lv0_out_<ts>.csv --condition all --workers 8 --outdir _sweep_lvl1_all 2>&1 | tee "$LOGS/run_step5_$(date +%Y%m%d_%H%M%S).log"

# step 8: the LVL2 sweep, three stages
$PIN $PY -B launch_LV2_sweep_random.py --lvl1-input lv1_out_<ts> --condition all --analysis-method <detector> --workers 8 --outdir _sweep_lvl2_all_<detector> --metrics alpha --stage all 2>&1 | tee "$LOGS/run_step8_$(date +%Y%m%d_%H%M%S).log"

# step 10 (b): the run notebook, executed in place (set PYTHON, JUPYTER_KERNEL and CPU_SET at the top of the script first)
bash submit_BDR_LVL2_notebooks_all.sh 2>&1 | tee "$LOGS/run_step10_$(date +%Y%m%d_%H%M%S).log"
```

The launchers write their output line by line, so the log follows the sweep as it runs. `<ts>` is the stamp the step
printed (e.g. `lv0_out_20261108_173533.csv`); `<detector>` is the selection's `detector` (e.g. `PELT_Attention_comp`).

**The steps in detail.**

- **Step 1, LVL0.** Set L4–L9 in `[cell 3]` (`max_age`, `age_group_split`, `pr_stim_drop`, `max_rt_thresh`,
  `min_rt_thresh`, `age_adjust_drift_residuals`); `sessions` and `conditions` are "all" or a list (intake filters). The
  run checks the settings and the data format (section 1), applies the intake filters (age, then sessions and
  conditions), builds the permutation nulls of the response-pattern markers (`periodic_n_perms` 1,000 per
  participant-session), fits the drift models and writes the stamped handoff `lv0_out_<ts>.csv` with its run log
  `lv0_out_<ts>_parameters.json` and the decay-fit exports. Read two printouts before step 4: the marker table
  `PERMUTATION-NULL MARKERS (run length at the 95th / 99th percentile of each null)`, whose `ALL 99th` column gives
  L29–L31, and the last cell, `SUGGESTED SETTINGS FOR LVL_1 AND LVL_2 (printed only)`, which prints those thresholds in
  `LVL_2_CONFIG` syntax (99th, then the more liberal 95th), the `rt_sec` percentiles and the shares below 0.15 and 0.30
  s, the stimuli per session, and `LVL_1_CONFIG` lines for L16–L22.
- **Step 2, sample description.** Pin `LVL0_HANDOFF` (the file name, e.g. `"lv0_out_20261108_173533.csv"`). Optionally
  fill the records of `[cell 2]`. It checks that the dataset after the LVL0 intake filters has the handoff's
  participants and sessions.
- **Step 3, LVL0 report.** Pin `LVL0_HANDOFF`.
- **Step 4, build.** Set the LVL1 settings the mode needs (dynamic L10–L22, predefined L10–L17), the LVL2 settings
  L23–L25 and L27–L33 (from the suggested settings; they may also wait for step 8's build) and `RUN_N_JOBS` (needed by
  step 10); L26 waits for step 8. The build writes and verifies the scripts and the run notebook, and prints each file
  it wrote.
- **Step 5, LVL1 sweep.** The grid is derived from `lvl1.py`'s `LVL_1_CONFIG` (section 6); e.g. with `min_block_size`
  20 it is the 12 configurations of `pelt_jump` (1, 2, 5) × `smoothing_window` (1, 3, 5, 7). The launcher checks its
  settings, `lvl1.py`'s settings and the sweep folder's provenance, then runs `lvl1.py` once per configuration.
- **Step 6, LVL1 sweep report.** Pin `SWEEP_DIR` (the `--outdir`, e.g. `"_sweep_lvl1_all"`). It writes Tables 1.1–1.4
  and the selection: the detector with the highest η²_H and its knob values.
- **Step 7, LVL1.** Copy the selection's `LVL_1_CONFIG` values (`smoothing_window`, `pelt_jump`, printed by step 6 and
  held in `_sweep_lvl1_all_selection.json`) into `[cell 9]`. If they differ from `[cell 9]`, `lvl1.py` must become the
  script a sweep ran: run step 4, then step 5 into a fresh `--outdir`, then step 6 on it. Pin `LVL0_HANDOFF` and
  `LVL1_SWEEP` in the first code cell. The calibration check stops until `[cell 9]` holds the selection; the H1 cells
  test every pair of detectors in the two H1 datasets, "Calibration" (the sweep's sessions, each detector at its own
  optimum) and "All data" (this handoff at the selected configuration).
- **Step 7a, participants' sessions** (optional). Pin `LVL1_HANDOFF` (the prefix, e.g. `"lv1_out_20261108_173759"`) and
  set `SWITCHERS`; `METHODS` (None = every block method) narrows the strips.
- **Step 8, LVL2 sweep.** Set `analysis_method` (L26) to the selected detector, run step 4 again, then the launcher: the
  grid (361 exponent pairs, each fitted as k-means and GMM with k = 2 and 3), the a-priori stage (the behavioural
  heuristic of `LVL_2_CONFIG`, the gold standard) and the stability stage (`stability_refits` bootstrap refits, 5,000 by
  default, of each arm's best configurations). `--metrics alpha` scores α only; without it every configuration also
  computes ICC, κ and split-half,
  which multiplies the run time.
- **Step 9, LVL2 sweep report.** Pin `SWEEP_DIRS` (a list, e.g. `["_sweep_lvl2_all_PELT_Attention_comp"]`) and
  `LVL1_HANDOFF`. It writes Tables 3.1–3.7 and the selection: per family (k-means, GMM) the carried arm, its
  configuration, k and exponents.
- **Step 10, the LVL2 run.** Copy the selection's family knobs into `[cell 28]`: `kmeans_exp_entropy_exponent`,
  `kmeans_exp_rt_var_exponent`, `cluster_k_list` (k-means) and `mixture_gmm_exp_entropy_exponent`,
  `mixture_gmm_exp_rt_var_exponent`, `gmm_k_list` (GMM), as printed by step 9 (`families` in `<sweep>_selection.json`).
  Run step 4: it rewrites the run notebook `block_detection_and_removal_LVL2_all_rep.ipynb` with its pins at `None`. In
  the run notebook's first code cell (`LVL_2 INPUT`), set `LVL1_HANDOFF` and `LVL2_SWEEP`. Then EITHER (a) open the run
  notebook in Jupyter and run all (not pinned to CPUs, no step log; it runs only while the Jupyter session stays open),
  OR (b) run the submit script: set `PYTHON`, `JUPYTER_KERNEL` and `CPU_SET` at its top (step 0 set its `PROJECT_ROOT`);
  it stops before running anything if a setting holds `"SET_ME"`, the run notebook is missing, a pin is unset, the
  handoff is missing, or the LVL2 selection is missing or was made on another handoff. It executes the notebook in place
  (the run notebook keeps its outputs), logs to
  `LVL_OUTS/run_logs/run_block_detection_and_removal_LVL2_all_rep_<stamp>.log` and prints, under `run tag written:`,
  this run's tag `lv2_out_<detector>_all_<ts>` (the newest stamped at or after the run's start), or `none` when the run
  failed.
- **Step 11, figures.** Pin the four handoffs and sweeps and `RUN_TAGS = {"all": "<run tag>"}`; set R11 and R12.
  Draw into a `FIG_DIR/pub_figures` that holds only this run's figures: the report's Table 7.3 checks every figure
  sidecar under `FIG_DIR/pub_figures` against its pins, so the figures of an earlier run, or of the other segmentation
  (e.g. `fig_lvl1_calibration.png` after a switch to predefined), fail it. Move an older `pub_figures` folder out of
  `dervatives/practical_application_generic` first (section 10).
- **Step 12, final report.** Pin as in step 11; set `CPU_SET` and `REPORT_N_JOBS` (R8, R9).

`demographic_report` and `LVL0_report` follow LVL0 because they check the sample against its handoff; the figures come
before the report because the report links them and checks their sidecars.

### Predefined segmentation

- Steps 1–4 are the same. At step 4 set, in `LVL_1_CONFIG` (`[cell 9]`): `segmentation` "predefined",
  `predefined_block_col` the block column, `cpd_method_types` `[]`, `control_block_count` None and `fixed_block_sizes`
  None (`[cell 11]` stops otherwise). L18–L22 may stay `"SET_ME"`. L33 can wait for step 7: LVL1 prints the block sizes
  (`predefined blocks (<column>): …; stimuli per block median … (min k, max …)`); set L33 to at least 100/k before step
  8's build ([Predefined blocks](#predefined-blocks)). `LVL_2_CONFIG["control_block_count"]` (`[cell 28]`) is for dynamic
  segmentation only and is ignored in predefined segmentation; it may keep its value.
- Steps 5 and 6 are skipped: there is no LVL1 sweep (`launch_LV1_sweep_random.py` stops on a predefined `lvl1.py`).
- Step 7: `LVL1_SWEEP = None`. The declaration check stops unless the block column is a column of the LVL_0 handoff, and
  `[cell 20]` checks the four block-id rules. LVL1 writes no `_h1_*` files.
- Step 8: `analysis_method` "Predefined" (L26), step 4 again, then the LVL2 sweep with
  `--analysis-method Predefined --outdir _sweep_lvl2_all_Predefined`.
- Steps 9–12 as above, with `LVL1_SWEEP = None` and `MOSAIC_PARTICIPANTS = []`. The report omits sections 1–2 and the
  figures omit the LVL1 calibration figure.

### Run times

Times grow with the number of participants and of stimuli per session, with the LVL2 sweep's grid (361 configurations by
default) and stability refits (5,000 per candidate), and with the replicate counts of `LVL_2_CONFIG`; the LVL2 sweep and
the LVL2 run take most of the time.

| Step | 24-participant subsample, dynamic | 24-participant subsample, predefined | EMST data (EMST folder's README) |
|---|---|---|---|
| 1 | 31 s | 31 s | ~20 min |
| 2, 3 | 2 s, 3 s | 2 s, 3 s | < 1 min each |
| 4 | seconds | seconds | seconds |
| 5 | 125 s | — | ~20 min (estimate) |
| 6 | 3 s | — | < 1 min |
| 7 | 21 s | 9 s | ~10 min |
| 7a | 5 s | 3 s | < 2 min |
| 8 | 1,730 s (grid ≈ 14 min, a-priori and stability ≈ 15 min) | 1,077 s | ~20 h (estimate) |
| 9 | 8 s | 8 s | < 5 min |
| 10 | 36 s | 34 s | ~6–8 h (estimate, the all-data run at `n_jobs` 13) |
| 11 | 24 s | 22 s | < 10 min |
| 12 | 8 s | 9 s | < 30 min (estimate) |

The first two columns are measured: steps 1–12 run in both segmentations on 24 participants of the EMST data (two
conditions, two sessions of about 200 stimuli, five scales; the predefined run with blocks of 5 stimuli, 4 at the end
of a 199-stimulus session), each on 8 CPUs while the other ran beside it, with reduced settings: `periodic_n_perms` 100,
an LVL2 sweep of 2 × 2 exponent pairs (`--entropy-exponents 0.5,1.0 --rt-var-exponents 0.5,1.0`), and in `[cell 28]`
`h2_boot_n` 200, `stability_refits` 50, `kmeans_bootstrap_reps` 0, `h2_robustness_b_splits` 20, `irr_between_draws`
500, `splithalf_bootstrap_reps` 20, `irr_null_reps` `{"alpha": 200, "kappa": 20, "icc": 20, "splithalf": 20}`, the
`irr_boot` `n` 200 (alpha) and 20 (kappa, icc, splithalf), and `irr_mm_icc`, `irr_mm_kappa`, `irr_mm_splithalf_between`
and `irr_mm_splithalf_within` False. The EMST data are 282 participants (552,281 rating rows) on 31 CPUs with the
default settings.

---

## 5. Pins, checks and lineage

A pin is a file name (a handoff, a run tag) in `LVL_OUTS` or a folder name in `SWEEPS_DIR`. There is no default and no
"newest file" rule: a pin left at `None` stops the notebook. Every consumer checks its inputs and stops on a missing or
mismatched one:

| Consumer | Checks |
|---|---|
| LVL0 notebook | the settings check; the input file exists; the data format (`check_input_data`, section 1); the intake filters keep rows |
| LVL1 notebook | the LVL_0 handoff and its single run log; the raw input's name and SHA-256 equal the run log's; the segmentation settings (`validate_segmentation`, `[cell 11]`); dynamic: the **calibration check** (`LVL_1_CONFIG` holds the LVL1 selection's knob values, made on this LVL_0 handoff); predefined: the **declaration check** (`LVL1_SWEEP` is None; the block column is a column of the LVL_0 handoff) and the block-id rules (`[cell 20]`); the data's scales are the keys of `scale_ranges`; the age-adjusted residuals exist when `age_adjust_drift_residuals` is True |
| LVL2 run notebook | the LVL_1 handoff's four files; the raw input's SHA-256 equals the one the handoff records; the **calibration check**: the handoff records an `analysis_method` (a handoff of the LVL1 notebook), `LVL_2_CONFIG` holds the LVL2 selection's knob values (each family's exponents and k list), its `analysis_method` is the selection's and the handoff's, and the selection was made on this handoff; `[cell 29]`: the handoff's segmentation, its block column (and, dynamic, its control column), the periodic thresholds' keys, `scale_ranges` / `scale_types` equal to LVL1's |
| launchers | their settings and the script's (`lvl1.py` / `lvl2.py`); LVL1: dynamic segmentation; LVL2: `--analysis-method` = `lvl2.py`'s `analysis_method` and the handoff's (predefined: `Predefined`), the block and control columns exist; `_provenance.json` of the sweep folder (script fingerprint, handoff, condition, grid), and the result files already in it match it |
| sweep reports | the sweep is complete: its result files are the launcher's whole grid (configuration ids 0 … N − 1, each with its companion files, `sessions_` for LVL1, `_h2` and `_flagged` for LVL2, and their `cfg_` columns rebuild the grid hashed in `_provenance.json`), or the report lists the missing and incomplete configurations and the launcher's `errors/` files and stops; every result file matches `_provenance.json` (script fingerprint, handoff, condition); the sweep's script copy has the sweep's fingerprint (section 6), while a current `lvl1.py` / `lvl2.py` with another fingerprint only prints a warning. `LVL1_sweep_report`: the script copy's segmentation is dynamic. `LVL2_sweep_report`: the pinned LVL_1 handoff is complete and is the sweep's; the a-priori and stability files were made by the sweep's script on that handoff, each refitted `stability_refits` times (the sweep's script); its stability candidates are the stability stage's |
| `demographic_report` | the LVL_0 handoff and its single run log; the dataset's SHA-256 equals the run log's; the dataset after the LVL_0 intake filters has the handoff's participants and sessions |
| `LVL0_report` | the LVL_0 handoff and its single run log; the decay-fit export exists and selects the run log's drift models |
| `LVL1_report` | the handoff's features, `_meta.json` and the LVL1 notebook's method-summary export exist |
| `make_replication_figures` | its settings and the id lists (analysed ids; dynamic: two `MOSAIC_PARTICIPANTS`; predefined: none); every input it reads exists; before anything is drawn, checks (a)–(e) below and the handoffs: the LVL_1 handoff (and the LVL1 sweep) were made on the pinned LVL_0 handoff, the LVL2 sweep and the run on the pinned LVL_1 handoff, and the run analysed every condition of the handoff; dynamic: the LVL1 selection is the sweep's η²_H winner; the dose-response contrasts are Table 3.6's distinct-solution test and agree with the dose fits |
| `Replication_and_final_report` | every pinned input, and every post hoc export the run's index lists, exists. Table 7.3 records the checks: the run's conditions, designs, LVL_1 handoff and `LVL_2_CONFIG` equal the handoff's and the selection's; the sweeps and handoffs come from the same upstream handoffs; checks (a)–(e); the pipeline version recorded by every level's run log equals the report's `PIPELINE_VERSION` (`[cell 1]`); one behavioural heuristic; one row per figure sidecar in `FIG_DIR/pub_figures` (linked or not): its pins equal the report's, its PNG exists, and every input it lists equals the current file (bytes, SHA-256) |

Checks (a)–(e) compare what ran with the calibration. Each sweep report writes into its `_selection.json` the path of
the sweep's script copy (`script_copy`) and that script's whole configuration with the selected values
(`LVL_1_CONFIG_full` / `LVL_2_CONFIG_full`).

- **(a)** dynamic: the LVL_1 handoff's `lvl1_config` (`_meta.json`) equals `LVL_1_CONFIG_full` on every key but
  `n_jobs`, `parallel_verbose` and `save_figures`, which cannot change a result. Predefined: the handoff declares
  predefined segmentation, with its block column and the one block column `block_Predefined`.
- **(b)** the run's recorded LVL_2 configuration (`_parameters.json`, `_config.json`) equals `LVL_2_CONFIG_full` on
  every key both record but `save_figures` and `conditions` (checked against the handoff's conditions).
- **(c)** dynamic: `lvl1.py` has the LVL1 sweep's fingerprint. Both: `lvl2.py` has the LVL2 sweep's fingerprint, or
  every line on which it differs from the sweep's script copy (difflib, on either side, each line in the cell of the
  NOTEBOOK CELL banner above it) is admitted by one of two rules: (i) a comment or blank line (by Python's tokenizer, so
  a line inside a string is code); (ii) a line setting one of the selection's family knobs in NOTEBOOK CELL 28 (what
  step 10 writes). Any other differing line fails the check; its detail lists each differing cell and the lines each
  rule admitted.
- **(d)** the LVL2 sweep and the run analyse the handoff's method (`_meta.json` `analysis_method`); dynamic: the LVL1
  selection's detector.
- **(e)** the sweeps were calibrated on all data (`condition` "all"): both sweeps in dynamic segmentation, the LVL2
  sweep in predefined segmentation.

**Lineage.** `lv2_out_<…>_config.json` → `lv1_out_<ts>_meta.json` (`lvl1_config`, `segmentation`,
`predefined_block_col`, `analysis_method`, `block_columns`, `lvl0_input`, `lvl0_record`, `input_long_sha256`) →
`lv0_out_<ts>_parameters.json` (the LVL_0 configuration, drift models and fits, the raw input's SHA-256). Every run log
also records the pipeline version and the software versions. Keep the stamp at the start of a renamed output
(`lv0_out_<stamp>…`) and rename a handoff's files together.

---

## 6. Calibration

**The LVL1 sweep** (step 5; dynamic segmentation only). The grid comes from `lvl1.py`'s `LVL_1_CONFIG` (the LVL1
notebook's `[cell 9]`), so nothing is set twice: every knob at its configured value except the two swept,
`smoothing_window` (the odd widths 1, 3, 5, 7 below `min_block_size`) and `pelt_jump` (those of 1, 2, 5 that divide
`min_block_size`); with `min_block_size` 20 that is 12 configurations. Each runs `lvl1.py --n-jobs 1` on every
participant of the LVL_0 handoff, without the fixed-block controls (`control_block_count` None). Output per
configuration: `cfgNNNNNN.csv` (one row per detector) and `sessions_cfgNNNNNN.csv` (per session), then
`sweep_results.csv` and `sweep_ranking.csv`. `LVL1_sweep_report` (step 6) reads the sweep folder: the quality filters,
Tables 1.1–1.2 (the variance in η²_H and in Corr% explained by `smoothing_window`, `pelt_jump` and their interaction,
per detector), Tables 1.3–1.4 (how often each value is a detector's best), each detector's best configuration
(`best_per_detector`, `best_eta`, `best_corr`, `configs`), the `pelt_jump` × `smoothing_window` heatmap and
`_sweep_lvl1_all_selection.json`: the detector and configuration with the highest η²_H (`criterion` `avg_effsize`), its
knob values (`LVL_1_CONFIG`), `script_copy` and `LVL_1_CONFIG_full`.

**The LVL2 sweep** (step 8). The grid is the two block-feature exponents, `kmeans_exp_entropy_exponent` ×
`kmeans_exp_rt_var_exponent`, each over `EXP_ALL` (19 values, 0.01 … 4.0: 361 configurations), every configuration
fitted as k-means k = 2, 3 and GMM k = 2, 3 (the GMM follows the swept exponents) and labelled under the rules `speed`,
`size` and `irr` in one run; the reports read the `speed` rows, the labelling rule of section 7. The keys
`pr_stim_drop`, `min_rt_thresh`, `max_rt_thresh`, `exp_pre_transform`, `control_block_count` and `irr_icc_form` are read
from `lvl2.py`'s `LVL_2_CONFIG`. Three stages (`--stage all`, or one at a time with `--stage grid|apriori|stability`):

- **grid:** `lvl2.py --n-jobs 1` per configuration, scored on Krippendorff's α only with `--metrics alpha`:
  `clusterNNNNNN.csv`, `_flagged.csv` and `_h2.csv` per configuration, then `sweep_results.csv` and `sweep_ranking.csv`;
- **apriori:** the behavioural heuristic of `LVL_2_CONFIG` (`inattent_behav`, L29–L33), run once by `lvl2.py`: the
  a-priori gold standard, in `apriori/` (`inattent999000.csv`, `inattent999000_flagged.csv`, `inattent999000_h2.csv`,
  `inattent999000_heuristic.json`, which also records the designs);
- **stability:** for each arm (`cluster_2`, `cluster_3`, `mixture_gmm_2`, `mixture_gmm_3`), the configuration whose
  flagged blocks of the analysis method overlap the a-priori standard most (Dice, DSC) and every exact tie, refitted
  `stability_refits` times (`lvl2.py`'s `LVL_2_CONFIG`, 5,000 by default; the launcher's `STAB_REPS`, recorded as
  `reps` in each `<config>.json`) on blocks resampled with replacement, in `stability/` (`<config>.json` summaries,
  `<config>.npz` the ARI of every refit, `<config>__<arm>_profiles.csv`). A configuration whose `lvl2.py` could not fit
  the arm on the analysed blocks ([section 7](#7-the-lvl2-run), "A fit Step 5 cannot make") has no DSC for it; an arm
  without one has no candidate.

When no configuration of the grid succeeds, the launcher stops before the a-priori and stability stages with
`no configuration of the grid succeeded …`, naming the end of the first configuration's `errors/` file.

`--entropy-exponents` and `--rt-var-exponents` give a supplementary grid, into its own `--outdir`; `LVL2_sweep_report`
pools the folders of `SWEEP_DIRS`. `LVL2_sweep_report` (step 9) reads the sweep folder(s) and the LVL_1 handoff the
sweep ran on: DSC with the a-priori standard, its variance shares and maxima (Tables 3.1–3.3b), stability (Table 3.4),
the dose-response fits of the α gain (Table 3.5; fitted when an arm and design has 6 or more eligible configurations),
their AUC contrasts between designs (Table 3.6, a paired bootstrap over each arm's distinct solutions; Table 3.6b
resamples the configurations, a sensitivity analysis), the calibrated configurations on their curves (Table 3.7) and
`<sweep>_selection.json`: per family (k-means, GMM) the configuration whose flagged `dynamic` blocks overlap the
standard most, exact ties broken by stability (median bootstrap ARI), the more stable of the family's two arms carried;
with its k, exponents (`LVL_2_CONFIG`), `script_copy` and `LVL_2_CONFIG_full`. A fit a configuration could not make
(its `_h2.csv` row has `n_flagged` empty and the reason in `fit_failure`) is never counted as flagging 0 units: it is
left out of the DSC tables and listed, with its reason, in `<sweep>_report_dsc_not_fitted.csv` (the final report
states it under Tables 3.1 and 3.3, where such a fit shows "—"); and an arm whose
calibrated configuration was not fitted on every design is not its family's pick (the LVL2 run labels every design
with the pick).

**The a-priori standard.** The heuristic marks trials: a straight-line run, a periodic run of each period and a
stimulus-linked run at or above their thresholds (L29–L31, the ALL 99th column of the LVL0 marker table, from the
per-session permutation nulls), and `rt_sec` below the fast-RT floor (L32). A marker flags a block when more than
`inattent_behav_block_percent_thresh` % (L33) of its trials carry it; the block is flagged when any marker flags it
(`inattent_behav_rule` "or"). The same definition labels the run's `inattent_behav` arm (Table 7.3 checks that they are
one).

**Sweep rules.**

- A fresh `--outdir` per script fingerprint, handoff or grid: the launchers resume only into a folder whose provenance
  matches, and refuse any other (`--check-only` checks without running). Re-issuing the same command resumes an
  interrupted sweep.
- Build the scripts (step 4) before a sweep whenever a notebook changed: any change to a level's code or configuration
  changes its fingerprint.
- A sweep report reads the script the sweep ran from its byte copy in the sweep folder (`_script_lvl1.py` /
  `_script_lvl2.py`) and stops unless the copy has the sweep's fingerprint. A missing copy is written from the current
  `lvl1.py` / `lvl2.py` while that script still has the sweep's fingerprint (before the rebuild of step 8 or 10 changes
  it); otherwise the report stops. The copy is the only file a sweep report writes into a sweep folder.
- The stability stage refits each candidate `stability_refits` times (`[cell 28]`, read from `lvl2.py`; 5,000 by
  default), and `LVL2_sweep_report` `[cell 6]` reads the count from the sweep's script copy and stops on stability files
  with another. The LVL2 run refits its carried fits as often, and Table 7.3 compares the sweep's refits with the run's.
  Changing `stability_refits` changes `lvl2.py`, so it means a new sweep (step 8).

---

## 7. The LVL2 run

The build writes the run notebook `block_detection_and_removal_LVL2_all_rep.ipynb` from the template, with
`RUN_NAME = "all"` and `n_jobs` = `RUN_N_JOBS`. A later build rewrites it whenever its code differs from what the build
writes (pins `None`), which clears the saved outputs of a notebook that ran; the exports in `LVL_OUTS` stay.

**One dataset.** The run analyses every condition of the LVL_1 handoff in one fit (`LVL_2_CONFIG["conditions"]` "all");
its one dataset is "All data". The condition column still defines the IRR cells (scale × condition).

**Designs** (`[cell 29]`, from the handoff's `_meta.json`). The design key `dynamic` means the blocks of
`analysis_method` in both segmentations; `DESIGN_LABEL` names it in tables and figures.

| Design | Units removed | Dynamic segmentation | Predefined segmentation |
|---|---|---|---|
| `dynamic` | the flagged blocks of `analysis_method` | the selected detector's blocks, labelled "Dynamic" | the data's blocks, method `Predefined`, labelled "Predefined" |
| `control` | the flagged matched fixed-size blocks (`block_Fixed_<method>_based`: with `control_block_count` "per_session", each session cut into as many equal blocks as the detector found there) | yes, labelled "Control" | none |
| `session` | the flagged sessions | when a participant has 2 or more sessions | when a participant has 2 or more sessions |
| `participant` | every session of a flagged participant | always | always |

`<run tag>_config.json` and `_parameters.json` record `segmentation`, `control_method`, `designs`, `design_labels` and
`multi_session`; the reports and figures read them and never recompute the designs.

**Labelling.** Each design's units are labelled three ways: the behavioural heuristic (`inattent_behav`), k-means and
the GMM on the three block features (Adj RT Level (Block) `adj_rt_level_block`, Exp RT Var (Block) `exp_rt_var_block`,
Exp Entropy (Block) `exp_entropy_block`; the GMM with its own exponents). In every k-means and GMM fit the fastest
component (the lowest mean `adj_rt_level_block`) is the inattentive one (`worst_cluster_idx` "speed",
`identify_inattentive_cluster_by_speed`, `[cell 38]`). When the fastest component is only marginally faster than the
next, that is a stability issue of the fit (Table 4.24 reports the speed margin and the share of refits in which the
labelled component stays fastest).

**Outputs.** Every file of the run starts with its run tag `lv2_out_<method>_all_<start time>` (printed by `[cell 29]`),
in `LVL_OUTS`:

| Files | Content |
|---|---|
| `_step8_multimetric.csv`, `_step8_null_overall.csv`, `_step8_null_iterations.npz` | the removal comparison per metric × design × removal method × scale cell, and over the cells: reference, post-removal and matched-random values; D and D per trial removed with their Monte Carlo interval and p; the change vs baseline (and per trial) with its stimulus-paired bootstrap |
| `_step9_design_tests.csv`, `_step9_cell_tests.csv`, `_step9_null_contrasts.csv`, `_step9_design_summary.csv` | the `dynamic` design vs each other design in four quantities (D per trial, D, gain per trial, gain), over the cells and per cell, with each comparison's eligibility (`Eligible`, `Ineligible_Reason`); the null D-difference contrasts; the bars |
| `_post_<table>.csv`, `_post_replicates.npz`, `_units.csv`, `_post_index.csv` | Steps 5e and 10: H2 and its robustness, overlap with the heuristic, stability and components of every fit, the primary H3 table, GMM posterior thresholds, repeat exposures; `_units.csv` holds every block's features, flags, posterior and component; the index lists every file |
| `_annotated.csv`, `_participant_summary.csv`, `_data_dictionary.csv`, `_config.json`, `_parameters.json` | the analysed trials with block ids and flags; the run log |
| `WARNINGS_OUTS/<run tag>_warnings.log` | every warning the run shows from `[cell 29]` on (RuntimeWarning, UserWarning and FutureWarning once per source line); warnings raised in the parallel workers go to the workers' stderr |

**Split-half and the coverage floor.** Every split-half score of a scale × condition cell (baseline, post-removal, each
matched random removal and each bootstrap replicate) uses the cell's one split set of `splithalf_bootstrap_reps` random
splits, seeded from `splithalf_seed` with the scale and condition. The coverage floor `h2_min_coverage` (the share of
the condition's stimuli rated at least twice, 0.80) applies to the H2 IRR matrices, to each robustness B split and to
the H3 post-removal matrices.

**A condition where a design flags no unit.** With several conditions, a design can flag units in one condition and
none in another. Its removal then takes no response in that condition, and each scale cell of the condition counts as
exactly zero change: the measure after removal equals the reference, the matched random removal removes nothing, so the
change, D and every bootstrap and null replicate are 0 there. Step 8 writes these cells as rows with `Trials_Removed` 0
(in `_step8_multimetric.csv`, and in the LVL2 sweep's result files); a per-trial value is not defined in such a cell
and is left empty. Over a scope's cells, the totals (the change, D) average every cell, the per-trial values only the
cells with trials removed; a design contrast's per-trial value uses the cells where both designs removed trials. The
condition's units count as unflagged in the minority profile. Step 9 and STEP 10 apply this one rule (so do the GMM
posterior thresholds and the repeat-exposure sensitivity, which reuse STEP 10's engine). They also share the
eligibility rule, so Step 9's eligible designs are STEP 10's: over the conditions of a comparison, a design is excluded
when its minority profile is below `irr_min_units` (at least 1; `[cell 29]` stops otherwise), when it removes every
response of a condition (degenerate), or when a post-removal cell rates fewer than `h2_min_coverage` of the stimuli at
least twice. A design that flags no unit at all has no Step 8 rows (its minority profile is 0).

**A fit Step 5 cannot make.** A GMM with k components needs at least 5·k units with every feature in a design's unit
matrix, and k-means needs two or more features. With few participants or sessions the per-session (or participant)
matrix can be too small: 12 participants with one session each carry a GMM with k = 2 (10 units needed) but not k = 3
(15). Step 5 fits each k on its own and records a fit it cannot make, with the reason (`FIT_FAILURES`, `[cell 42]`);
that arm then has no flags in that design, never an empty flag set, so it is never counted as flagging 0 units. A
sweep run writes it as an `_h2.csv` row with `n_flagged` empty and the reason in `fit_failure` (section 6, for how the
sweep report treats it), and the run stops at Step 5d (`Step 5 could not fit a carried solution on every design's
units: …`) when a carried solution was not fitted on a design: carry a k that every design can fit, i.e. the LVL2
sweep report's selection.

**Figures in the run notebook** (notebook-only cells; nothing is written): the block cluster profiles of the k-means and
GMM solutions, the agreement between the removal methods for the block designs, and, per IRR measure, the Step 9 bars
(the `dynamic` design vs each other design, with the figure tests) beside the same means against the % of trials
removed.

---

## 8. Reading the outputs

**Start with the final report**, `LVL_OUTS/final_replication_publication_report.md`. Its title names the analysis
method. Sections:

| Section | Content | Dynamic | Predefined |
|---|---|---|---|
| 0 | Sample, session duration, behavioural features, drift models, out-of-range responses, age check (Tables 0.1–0.13; 0.12–0.13 with an age column) | yes | yes |
| 1 | LVL1 calibration on all data (Tables 1.1–1.4, Figure 1.1) | yes | omitted |
| 2 | H1 segmentation (Tables 2.1–2.10) | yes | omitted |
| 3 | LVL2 classification calibration (Tables 3.1–3.14) | yes | yes |
| 4 | H2: flagged vs unflagged blocks, robustness, classification, exact-zero folded units (Tables 4.1–4.32) | yes | yes |
| 5 | H3: inter-rater reliability, sensitivities (Tables 5.1–5.21) | yes | yes (no Table 5.21) |
| 6 | Consolidated results: the claims, the sanity check, the exclusions (Tables 6.1–6.3) | yes | yes |
| 7 | Statistical notes, repeat exposures, the checks, the provenance (Tables 7.1–7.4) | yes | yes |

In predefined segmentation the report prints, in place of sections 1–2: "Sections 1–2 (LVL1 calibration and H1) are not
part of this report: the LVL_1 handoff declares predefined segmentation (blocks from column <column>), so LVL1 detected
no blocks and was not calibrated." Table numbers are fixed: numbers the tool never uses (2.3c–e, 4.8, 4.11–4.18 and
5.10, tables of the multi-dataset EMST report) and tables a run does not produce leave gaps; with one dataset, Tables
5.2 and 5.3 have only 5.2a and 5.2f, and 5.3a, 5.3f and 5.3g. Some tables depend on the
data: Tables 0.12–0.13 and Figure 0.3 need an age column (0.13 also `age_group_split`), Figure 3.1 needs dose fits,
Tables 5.12–5.13 need repeat exposures, Table 5.21 needs the control design, and a secondary measure switched off
(`irr_mm_*` False) leaves its Table 5.6 empty, with a note. An appendix holds the supporting tables (2.6, 3.5, 3.6b,
3.7–3.14, 4.4, 4.5, 4.10, 4.21–4.23, 5.1a–b, 5.3f–g, 5.5, 5.6g, 5.11–5.13 and Figure 5.1).
`final_replication_supp_tables.tex` holds the supplementary tables as LaTeX: the H1 detector-pair matrices (Tables
2.10a–d, dynamic), Table 5.20 and, with a control design, Table 5.21.

**First, Table 7.3** lists every check the report ran. A complete, consistent run has no "no" in it; a "no" names what
differs (section 9). Table 7.4 lists the sources: the pins, the scripts' fingerprints, the selections, the pipeline and
software versions.

**Key tables.**

- **H1** (dynamic): Tables 2.1–2.3 describe η²_H and Corr% of every detector in "Calibration" and "All data"; Tables
  2.4a–d (η²_H) and 2.5a–d (Corr%) test each detector and all detector pairs (BH within each test); Tables 2.8–2.9 the
  method-level association of mean η²_H and mean Corr%; Tables 2.10a–d the pair differences as matrices.
- **Calibration:** Table 3.3 gives the DSC of each arm's calibrated configuration with the a-priori standard, by design;
  Table 3.4 the stability (bootstrap ARI) of the carried solutions.
- **H2:** Table 4.1 (size: the flagged share of the blocks against 1/k, one-sided), Table 4.2 (speed: flagged vs
  unflagged block RT level, one-sided), Table 4.3 (IRR: α of flagged vs unflagged responses, two-sided); robustness A–C
  in Tables 4.4–4.6; the overlap with the behavioural standard in Tables 4.7–4.7b; stability in Table 4.9; the labelled
  component of every fit, its speed margin and profile in Tables 4.24–4.26.
- **H3:** Table 5.2a (α after each removal design and method, vs baseline and vs matched random removal), Table 5.2f
  (per scale and overall), Table 5.3a (the `dynamic` design vs the other designs), Tables 5.6a–g (the secondary
  measures), Tables 5.14–5.17 (GMM posterior thresholds), Tables 5.18–5.19 (the changes across the scale cells) and
  Tables 5.20–5.21 (per scale, every measure).
- **Claims:** Table 6.1 states every hypothesis claim and whether it holds in each dataset; Table 6.3 lists what was
  excluded, unavailable or statistically ineligible.

**Units.** D = the post-removal value minus the matched-null value (positive: the flagged removal leaves the higher
measure). Per trial = an absolute change in the measure divided by the stimulus-trials removed (vs the matched null:
each random removal by its own count), shown × 10⁻⁶; % of trials removed is reported beside it as the volume. Summaries
are median [Q1, Q3] (sMAD, the scaled MAD 1.4826 × MAD); bootstrap p = (count + 1) / (B + 1); BH = Benjamini–Hochberg,
the family stated under each table; † marks the selected method.

**Labels.** Design keys print as the run's labels (Dynamic or Predefined, Control, Session, Participant); conditions as
the data name them; the carried solutions as k-means (k) and GMM (k). In every k-means and GMM fit the fastest component
is the inattentive (flagged) one; Table 4.24 gives each fit's speed margin over the next component.

**Figures** (`make_replication_figures`, in `FIG_DIR/pub_figures`; each PNG has a JSON sidecar listing its inputs with
their sizes, SHA-256 and times, the pins and the time of drawing):

| Figure | File | Drawn |
|---|---|---|
| Decay curves and log-RT distributions (raw and Box-Cox in the supplement) | `main_text/fig_decay_curves.png`, `supplement/fig_decay_curves_{raw,boxcox}.png` | always |
| LVL1 calibration and two segmented sessions (`MOSAIC_PARTICIPANTS`) | `main_text/fig_lvl1_calibration.png` | dynamic segmentation |
| RT, RT variance and entropy distributions | `supplement/fig_feature_distributions.png` | always |
| Age associations of the features (younger vs older when `age_group_split` is set) | `supplement/fig_age_by_feature.png` | with an age column |
| Dose-response of the α gain across the LVL2 sweep | `supplement/fig_dose_response.png` | when the LVL2 sweep report fitted dose curves |
| GMM posterior P(inattentive) per block | `supplement/fig_gmm_posterior.png` | always |
| One participant's sessions: features, blocks, the flagged blocks (`PARTICIPANT_FIGURES`) | `supplement/participants/fig_participant_<id>.png` | per id |
| Method agreement (DSC) between the heuristic and the carried solutions | `supplement/fig_method_agreement.png` | always |
| Overlap with the heuristic across the LVL2 sweep | `supplement/fig_sweep_overlap.png` | always |
| Profiles of the calibrated configurations | `supplement/fig_sweep_profiles.png` | always |
| H3: the designs compared | `main_text/fig_h3_designs.png` | always |
| H3: every reliability measure by design | `supplement/fig_irr_designs_all.png` | always |

The dose figure needs dose fits: a small LVL2 sweep (e.g. a 2 × 2 grid) fits none, writes header-only `dose_*` tables
and draws no dose figure. The sweep reports and the level notebooks also draw their own figures in the notebook (not
written to `FIG_DIR`).

**The run's own exports** (section 7) are for further analysis: `<run tag>_annotated.csv` is the analysed data with the
block ids (`block_<method>`, and in dynamic segmentation `block_Fixed_<method>_based`), one flag per removal method and
design (`<method>_bb_<design>`, e.g. `cluster_2_bb_dynamic`), `consensus_bad_*`, `detector_agreement_*` and
`invalid_resp`; `_data_dictionary.csv` describes every added column. `<run tag>_units.csv` has one row per block: its
features, each labeller's flag, the GMM posterior `p_inattentive_*`, the component and the labelled component.

---

## 9. Troubleshooting

- **A complete run:** every notebook ends without an exception, and so does every step log
  (`LVL_OUTS/run_logs/run_<notebook>_<stamp>.log`, `run_step<N>_<stamp>.log`); the run notebook's log
  (`run_block_detection_and_removal_LVL2_all_rep_<stamp>.log`) ends with nbconvert's "Writing …" line; the run tag has
  its `_post_index.csv` and every file it lists; the report's Table 7.3 has no "no".
- **`settings check (<level or file>): N setting(s) still hold "SET_ME"`:** `<level or file>` is `LVL_0`, `LVL_1` or
  `LVL_2` (a level notebook or `lvl*.py`) or the file's name (e.g. `LVL0_report.ipynb`, `launch_LV1_sweep_random.py`,
  `submit_BDR_LVL2_notebooks_all.sh`). Set each listed setting where the message says (section 3,
  [Settings](#settings)). For a script (`lvl*.py`, or the launchers' listing of `lvl1.py` / `lvl2.py` values), set it in
  the notebook cell and run the build again (step 4): a script is built from its notebook.
- **`input check (<file>): N rule(s) broken`:** the data break a rule of section 1, or a `LVL_0_CONFIG` setting has the
  wrong type (the age settings; the RT limits, a number of seconds ≥ 0, 0 = off; `pr_stim_drop`, a whole number ≥ 0)
  or does not fit the data (the age settings without an age column); each rule is listed with its count and up to 20
  rows (row = the 0-based data row, file line = row + 2).
  Fix the data file (or `[cell 3]`) and run step 1 again. `required column(s) [...] missing` lists the file's columns.
- **`the input file … does not exist`:** put the data in `<PROJECT_ROOT>/dset` and set `INPUT_LONG_FILE` to its name
  (`[cell 2]`). **`PROJECT_ROOT = '…' is not an absolute path`:** set it to an absolute path (step 0 does).
- **No age column:** set `max_age` and `age_group_split` to None and `age_adjust_drift_residuals` to False (LVL0; the
  input check stops otherwise), LVL1's `age_adjust_drift_residuals` to False (LVL1 stops otherwise:
  `LVL_1 age_adjust_drift_residuals=True but LVL_0 did not hand over …`) and LVL2's `age_adjust_variance` and
  `age_adjust_entropy` to False (LVL2 `[cell 29]` stops otherwise: `the data have no age column, so the LVL_2 age
  adjustment must be off`). The age tables (0.12–0.13) and the age figure are then not produced; without
  `age_group_split` there are no age groups.
- **Predefined blocks:** `predefined blocks (<column>) break the block-id rules; every offending row: …` lists each
  broken rule ([Predefined blocks](#predefined-blocks)) and writes `LVL_OUTS/predefined_block_violations.csv`; fix the
  block column and rerun from step 1. `declaration check:` names an `LVL1_SWEEP` that is not None or a block column that
  is not in the LVL_0 handoff. `[LVL_1_CONFIG] N segmentation violation(s)` (`[cell 11]`) names a mode setting that does
  not fit the segmentation (e.g. `cpd_method_types` not `[]` in predefined segmentation, or a block column in dynamic
  segmentation).
- **Scales:** `the scales of <handoff>, [...], are not the keys of LVL_1_CONFIG['scale_ranges'], [...]` (LVL1
  `[cell 20]`): set `scale_ranges` and `scale_types` to exactly the data's scales.
  `LVL_2_CONFIG differs from the LVL_1 handoff's configuration (_meta.json lvl1_config)` (LVL2 `[cell 29]`): set L23–L24
  to LVL1's values and rebuild.
  `LVL_2_CONFIG['inattent_behav_periodic_thresh'] = … must be a dict with the periods [...] as keys`: one run length per
  period 2 … S − 1, from the ALL 99th column of the LVL0 marker table.
- **The analysis method:**
  `the LVL_1 handoff records no analysis_method (written by lvl1.py --export): use the LVL1 notebook's handoff` — the
  LVL2 run needs the handoff the LVL1 notebook wrote (step 7), whose lineage cell records the method.
  `LVL_2_CONFIG['analysis_method'] = '…', but the LVL_1 handoff analyses '…' (_meta.json): set it in [cell 28] and rebuild`,
  and the launcher's `--analysis-method '…', but lvl2.py's LVL_2_CONFIG['analysis_method'] is '…'`: set L26 to the
  handoff's method (dynamic: the selected detector; predefined: "Predefined"), rebuild, and pass the same
  `--analysis-method`.
  `the LVL_1 handoff's _meta.json records segmentation None: use a handoff written by this pipeline's LVL_1`.
- **Pins:** `… is not set` / `not an existing … handoff`: a pin is `None` or names a missing stamp (the handoff messages
  list the files available). `set SWEEP_DIRS (a list of LVL_2 sweep folders) and LVL1_HANDOFF at the top of this cell`
  (`LVL2_sweep_report`), `pins not set (top of this cell)` (figures) and `set every input at the top of this cell`
  (report) name the unset pins. `LVL1_SWEEP = …, but the LVL_1 handoff declares … segmentation`: `LVL1_SWEEP` is None
  exactly in predefined segmentation. `[cell 1] settings:` (figures): an id list is not a list, names ids outside the
  analysed sample, or `MOSAIC_PARTICIPANTS` is not two ids (dynamic) or not `[]` (predefined).
- **Calibration:** `LVL_1_CONFIG differs from <sweep>_selection.json ({knob: (LVL_1_CONFIG, selection)}): …` and
  `LVL_2_CONFIG differs from <sweep>_selection.json ({knob: (LVL_2_CONFIG, selection)}): …` list each differing knob:
  copy the selection's values (steps 7, 10). `the sweep … ran on …, not on …`: the sweep was made on another handoff.
  `<sweep>_selection.json is missing: run …_sweep_report.ipynb on the sweep … first`: run the sweep report (step 6 or
  9).
- **Stale code:** a pin pointing at an older stamp; `lvl1.py` with a fingerprint other than the LVL1 sweep's, or
  `lvl2.py` differing from the LVL2 sweep's script copy on a line check (c) does not admit (section 5; after step 10,
  `LVL2_sweep_report`'s warning that `lvl2.py` has changed since the sweep is expected); a figure whose sidecar pins or
  inputs differ from the report's pins or the current files. `make_replication_figures` stops on stale code
  (`lineage check failed (nothing drawn)`, listing each failure); Table 7.3 shows "no" for stale code and stale figures.
  A project that switched mode keeps its old figures (e.g. `fig_lvl1_calibration.png`), which Table 7.3 also checks:
  move them aside (section 10).
- **Sweeps:** a launcher refusing an `--outdir` (`[provenance] … was written under a different provenance`): its script
  fingerprint, handoff or grid differs; use a new folder. Failed configurations leave their output in `errors/` (beside
  the code); a sweep folder with fewer result files than its grid is incomplete, and the sweep reports stop on it
  (re-issue the same launcher command to resume). `predefined segmentation has no LVL1 sweep (README)`: skip steps 5–6.
  **An LVL2 sweep that barely advances:** `--metrics alpha` is missing (step 8). The stability stage refits up to 5
  candidate configurations at once, each with an equal share of the `--workers` CPUs.
  `no configuration of the grid succeeded …` (the LVL2 launcher): every `lvl2.py` run stopped; the message ends with
  the last line of the first one's `errors/` file. Fix the cause, rebuild if a notebook changed, and run the launcher
  again into a fresh `--outdir`.
- **Small data and the GMM:** `GMM k=3 not fitted on participant: Too few units with every feature (12) for GMM with 3
  components (needs 15)` (Step 5) means that design's unit matrix is too small for that k (at least 5·k units with
  every feature;
  [section 7](#7-the-lvl2-run)). The sweep carries on: `LVL2_sweep_report` lists the fit in `dsc_not_fitted` and does
  not pick that arm. `Step 5 could not fit a carried solution on every design's units: …` (the LVL2 run, Step 5d): set
  `gmm_k_list` / `cluster_k_list` in `[cell 28]` to the LVL2 sweep report's selection and rebuild.
  `no mixture_gmm arm's calibrated configuration was fitted on every design's units` (`LVL2_sweep_report`): even k = 2
  needs 10 units in every design's matrix, so the data hold too few participants (or sessions) for the GMM.
- **`the sweep selections lack …`** or **`… is not the distinct-solution test`:** the selection files or the dose
  contrasts lack the fields the checks read; rerun `LVL1_sweep_report` and `LVL2_sweep_report` (steps 6, 9).
- **`… is missing in … and lvl1.py / lvl2.py does not have the sweep's fingerprint`:** the sweep folder has no script
  copy and the script changed after the sweep; run the sweep again in a fresh `--outdir`.
- **`inputs not found`:** an earlier step has not written its exports (the message lists them).
- **Table 7.3, `Exact-zero diagnostics: the sweep's stability refits of … = the run's (same resamples and order)`:** the
  check compares the sweep's refits with the run's, so it needs the run's `stability_refits` equal to the sweep's
  (5,000 by default; section 6): set it back, or sweep again with the new value.
- **Run messages that are not errors:** `Parquet export skipped` (no pyarrow or fastparquet) and
  `N exported column(s) have no data-dictionary entry` (pass-through columns without a `COVARIATE_DESCRIPTIONS` entry).

---

## 10. Running from a clean state; changing the pipeline

**From a clean state.**

1. Keep `dset/<INPUT_LONG_FILE>` and the code folder. Safe to clear: `dervatives/practical_application_generic/`
   (`lvl_outs`, `sweeps`, `figures`), the `errors/` folder and the `*_executed.ipynb` files beside the code. To keep the
   outputs, move them outside `dervatives/practical_application_generic`, never into a subfolder of it: the report
   searches `LVL_OUTS`, `SWEEPS_DIR` and `FIG_DIR` recursively. This holds for `figures/pub_figures` in particular:
   Table 7.3 checks every figure sidecar there, so a project that switches segmentation, or reruns from step 1, draws
   into an empty `pub_figures`.
2. Run section 4 from step 1, setting each step's pins to the stamps the previous steps printed. The new handoffs,
   sweeps and runs carry new stamps and fingerprints; nothing older is reused.

**Changing the pipeline.**

- This folder is maintained by hand; nothing regenerates it. Fixes from the validation folder
  (`code/cpd_and_blk_rep_anaylsis`) are ported by hand.
- Edit the notebooks, then run `build_level_scripts.py`; never edit `lvl*.py` or the run notebook by hand.
- The first line of every code cell is its label. `# [cell N]` is a pipeline cell (N is unique across the three level
  notebooks and increasing; it is the `NOTEBOOK CELL N` banner in the scripts). `# [notebook only]` cells (pins, checks,
  lineage, exports for the reports, figures) never reach a script. `[cell 0]`–`[cell 2]` are identical copies in the
  three notebooks (the build stops if they differ); `[cell 0]` (the thread limits and `n_jobs`) opens every script,
  without a banner. `[cell 30]` (LVL2's condition check) is labelled but not emitted: `lvl2.py` selects with
  `--condition all`.
- The build, the launchers and the reports find cells and lines by content anchors (e.g. `LVL_0_CONFIG = {`,
  `TIMESTAMPED LVL_1 HANDOFF`, `STEP 10:`, the stability stage's cut line in `lvl2.py`); each must match exactly once,
  or they stop. The step-0 commands match the exact forms `PROJECT_ROOT = "SET_ME"`, `INPUT_LONG_FILE = "SET_ME"` and
  `n_jobs = "SET_ME"`. Keep them when editing.
- Every knob is read as `CONFIG["key"]`; a missing key stops the run. A new knob is added to the level's config dict and
  becomes a script flag (`--<knob> <python literal>`). The config dicts stay literals (the launchers and the sweep
  reports parse them with `ast.literal_eval`), and a new dataset-specific setting holds `"SET_ME"` with an entry in
  `SET_ME_GUIDE` (`[cell 2]`).
- `PIPELINE_VERSION = "1.0.1"` stands in `[cell 2]` of the three level notebooks and in `Replication_and_final_report`
  `[cell 1]`, which checks it against the run logs (Table 7.3); the header of this README and the heading of the
  report's `*[cell 0]*` ("Final report (block detection pipeline 1.0.1)") repeat it. A new version is
  written into all of them; it changes every script's fingerprint and the version every run log records, so section 4 is
  run again from step 1, both sweeps included.
- The labelling rule (`worst_cluster_idx = "speed"`, `identify_inattentive_cluster_by_speed`, `[cell 38]`): in every
  k-means and GMM fit the component with the lowest mean `adj_rt_level_block` is the inattentive one. The other block
  features are printed as each component's profile; they do not decide the label.
