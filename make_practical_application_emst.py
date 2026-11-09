#!/usr/bin/env python3
"""Generate code/practical_application_emst from the validation pipeline code/cpd_and_blk_rep_anaylsis.

The practical-application folder applies the block detection pipeline to the EMST data for the published norms: both
sweeps calibrate on all data (--condition both) and the pooled T2 + T3 run is active. It is the validation folder with
  M  the pooled pathway's marker blocks restored (their "#> " prefixes removed),
  P  its paths pointed at this folder and at dervatives/practical_application_emst,
  C  the calibration checks and filters that name T2 opened to the calibration on all data ("both"),
  R  the dataset labels named by meaning (H1's calibration sessions "T2+T3 calibration", the T2 run "T2 only", the run
     on the calibration data the pooled run) and the sweep folders _sweep_lvl1_all and _sweep_lvl2_all_<detector>,
  H  H3 reported for the pooled datasets in the final report,
  T  the behavioural heuristic's thresholds = the all-data 99th-percentile markers of LVL_0 (21 / 9 / 11 / 13 / 8),
  J  the three run notebooks' n_jobs (9 / 9 / 13),
  X  the wording that names T2 as the calibration set, T3 as the hold-out or a result as a replication,
  K  the notebooks' outputs cleared and their kernelspec set,
and its own README. Every edit is an exact-text anchor with a count; any mismatch stops the script, which lists every
mismatch first. The validation folder is only read, and its build never runs.

  /usr/bin/python3 -B /home/sjsuss626/EMST_files/sjs_dissertation/code/make_practical_application_emst.py --check
  /usr/bin/python3 -B /home/sjsuss626/EMST_files/sjs_dissertation/code/make_practical_application_emst.py

--check transforms in memory, runs the static checks and compares the result with the current practical folder; it
writes nothing. Without it, the script writes a new staging folder beside the target, runs build_level_scripts.py
there, checks the result and the validation folder, then moves an existing practical folder (executed notebooks
included) to sjs_dissertation/archive/practical_application_emst_<stamp> and the staging folder into its place. It
prints the pins and calibration values the archived folder held. Nothing is deleted; a staging folder that fails a
check is kept as <staging>_FAILED. dervatives/ is never written.
"""
import argparse
import datetime
import difflib
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/sjsuss626/EMST_files/sjs_dissertation")
SRC = ROOT / "code" / "cpd_and_blk_rep_anaylsis"
DST = ROOT / "code" / "practical_application_emst"
ARCHIVE = ROOT / "archive"
KERNELSPEC = {"display_name": "Python (block_detection_irt)", "language": "python", "name": "block_detection_irt"}

NB_LVL0, NB_LVL1, NB_LVL2 = ("block_detection_and_removal_LVL0.ipynb", "block_detection_and_removal_LVL1.ipynb",
                             "block_detection_and_removal_LVL2.ipynb")
NB_DEMO, NB_L0R, NB_L1R = "demographic_report.ipynb", "LVL0_report.ipynb", "LVL1_report.ipynb"
NB_L1SR, NB_L2SR = "LVL1_sweep_report.ipynb", "LVL2_sweep_report.ipynb"
NB_FIG, NB_REP = "make_replication_figures.ipynb", "Replication_and_final_report.ipynb"
LAUNCH1, LAUNCH2 = "launch_LV1_sweep_random.py", "launch_LV2_sweep_random.py"
PROV, BUILD, SUBMIT, README, GITIGNORE = ("sweep_provenance.py", "build_level_scripts.py",
                                          "submit_BDR_LVL2_notebooks_all.sh", "README.md", ".gitignore")
NOTEBOOKS = [NB_LVL0, NB_LVL1, NB_LVL2, NB_DEMO, NB_L0R, NB_L1R, NB_L1SR, NB_L2SR, NB_FIG, NB_REP]
TEXTS = [LAUNCH1, LAUNCH2, PROV, BUILD, SUBMIT, README, GITIGNORE]
GENERATED = NOTEBOOKS + TEXTS                                   # written by this script (17)
BUILT_SRC = ["lvl0.py", "lvl1.py", "lvl2.py", "block_detection_and_removal_LVL2_T2_rep.ipynb",
             "block_detection_and_removal_LVL2_T3_rep.ipynb"]   # the validation build's outputs: not copied
RUN_NBS = {"block_detection_and_removal_LVL2_T2_rep.ipynb": (9, '["T2"]'),
           "block_detection_and_removal_LVL2_T3_rep.ipynb": (9, '["T3"]'),
           "block_detection_and_removal_LVL2_T2+T3_rep.ipynb": (13, '["T2","T3"]')}
BUILT = ["lvl0.py", "lvl1.py", "lvl2.py"] + list(RUN_NBS)      # written here by the build (6)
SKIPPED_DIRS = ("errors", "__pycache__", ".ipynb_checkpoints")  # never copied (the launchers create errors/)
SKIPPED_SUFFIX = "_executed.ipynb"                              # executed copies of command-line runs

# ---- P: paths, applied longest first. Expected counts per file: (S1, S2, S3, S4).
PATHS = [(f"{ROOT}/code/cpd_and_blk_rep_anaylsis", f"{ROOT}/code/practical_application_emst"),
         (f"{ROOT}/dervatives/dynamic_qc", f"{ROOT}/dervatives/practical_application_emst"),
         ("dervatives/dynamic_qc", "dervatives/practical_application_emst"),
         ("code/cpd_and_blk_rep_anaylsis", "code/practical_application_emst")]
PATH_COUNTS = {NB_LVL0: (1, 3, 0, 0), NB_LVL1: (1, 4, 0, 0), NB_LVL2: (1, 3, 0, 0), NB_DEMO: (0, 1, 0, 0),
               NB_L0R: (0, 1, 0, 0), NB_L1R: (0, 1, 0, 0), NB_L1SR: (1, 2, 0, 0), NB_L2SR: (1, 3, 0, 0),
               NB_FIG: (1, 3, 0, 0), NB_REP: (1, 3, 0, 0), LAUNCH1: (2, 2, 0, 0), LAUNCH2: (2, 2, 0, 0),
               PROV: (0, 0, 0, 0), BUILD: (0, 0, 0, 0), SUBMIT: (2, 2, 2, 0), GITIGNORE: (0, 1, 0, 0),
               README: (3, 8, 6, 1)}
DATASET = f"{ROOT}/dset/all_subjects_long.csv"                  # shared by both folders, never substituted

# ---- M: the pooled pathway's marker blocks. Expected (headers, restored lines) per file.
MARKER = re.compile(r"^# \[pooled pathway: practical-application folder\] (.*)$")
MARKER_COUNTS = {NB_LVL1: (3, 9), NB_LVL2: (2, 3), NB_FIG: (2, 2), NB_REP: (3, 5), BUILD: (1, 1), SUBMIT: (1, 1)}

# ---- C, R, H, T, J, X: per notebook, (first-line prefix of the cell, [(old, new, count), ...]); applied in order,
# the specific anchors of a cell before its bare label renames.
P2, P3 = "Pooled, T2", "Pooled, T3"
NOTE_SHARE = "the pooled datasets share their participants with T2 only and T3 only"
NB_EDITS = {
    NB_LVL1: [
        ("*[notebook only]*", [
            ("H1 in T2 calibration and T3 only (descriptives; every pair of detectors tested)",
             "H1 in T2+T3 calibration, T3 only and the pooled datasets (descriptives; every pair of detectors tested in "
             "T2+T3 calibration and in T3 only)", 1)]),
        ("# [notebook only] LVL_1 INPUT", [
            ("and the H1 tests read the sweep's T2\n# sessions at each detector's best configuration.",
             "and the H1 tests read the sweep's\n# sessions (T2 and T3) at each detector's best configuration.", 1),
            ('LVL1_SWEEP = "_sweep_lvl1_T2"', 'LVL1_SWEEP = "_sweep_lvl1_all"', 1)]),
        ("# [notebook only] LVL_1 CALIBRATION CHECK", [
            ("# LVL_1_CONFIG must hold the T2 calibration:", "# LVL_1_CONFIG must hold the all-data calibration:", 1)]),
        ("# [notebook only] H1: SESSION-LEVEL DATA", [
            ('h1_check("sessions: T2 calibration = the handoff\'s T2 sessions; T3 only = its T3 sessions",\n'
             '         _n_ses["T2 calibration"] == _n_handoff["T2"] and',
             'h1_check("sessions: T2+T3 calibration = the handoff\'s T2 and T3 sessions; T3 only = its T3 sessions",\n'
             '         _n_ses["T2+T3 calibration"] == _n_handoff["T2"] + _n_handoff["T3"] and', 1),
            ("T2 calibration", "T2+T3 calibration", 9)]),
        ("# [notebook only] H1: DESCRIPTIVES", [
            ("† = the T2-selected detector.", "† = the selected detector.", 1)]),
        ("# [notebook only] H1: TESTS", [
            ("(T2 sweep)", "(T2+T3 sweep)", 2),
            ("T2 calibration", "T2+T3 calibration", 4)]),
        ("# [notebook only] H1: REPLICATION SUMMARY", [
            ("H1: REPLICATION SUMMARY AND METHOD-LEVEL ASSOCIATION",
             "H1: SUMMARY ACROSS THE DATASETS AND METHOD-LEVEL ASSOCIATION", 1)]),
        ("# [notebook only] H1: FIGURE", [
            ("OPTIMAL CONFIGURATION (T2)", "OPTIMAL CONFIGURATION (T2 + T3)", 1),
            ("the groups of H1: REPLICATION SUMMARY)", "the groups of H1: SUMMARY ACROSS THE DATASETS)", 1),
            ("T2 calibration", "T2+T3 calibration", 2)]),
    ],
    NB_LVL2: [
        ("*[notebook only]*", [
            ("writes the two run notebooks `block_detection_and_removal_LVL2_{T2,T3}_rep.ipynb` from it",
             "writes the three run notebooks `block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb` from it", 1),
            ("(`[cell 0]`; 15 in each, 15 + 15 within the 31 CPUs)", "(`[cell 0]`; 9, 9 and 13, within the 31 CPUs)", 1),
            (" Pooled pathway: the T2 + T3 run (one fit on both conditions) belongs to the practical-application folder; "
             "its lines here are commented out under `# [pooled pathway: practical-application folder]`.",
             " The T2 + T3 run is one fit on both conditions; its datasets are Pooled, overall and its restrictions to "
             "each condition, Pooled, T2 and Pooled, T3.", 1)]),
        ("# [notebook only] LVL_2 INPUT", [
            ("# This notebook is the template of the two run notebooks (block_detection_and_removal_LVL2_{T2,T3}_rep.ipynb),",
             "# This notebook is the template of the three run notebooks\n"
             "# (block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb),", 1),
            ("block_detection_and_removal_LVL2_<T2 | T3>_rep.ipynb",
             "block_detection_and_removal_LVL2_<T2 | T3 | T2+T3>_rep.ipynb", 1)]),
        ("# [cell 28]", [
            ("    # Values = the T2 calibration picks (maximum DSC overlap with the a-priori\n"
             "    # inattent_behav standard; exact ties broken by median bootstrap ARI): kmeans_* =\n"
             "    # cluster_2's pick, mixture_gmm_exp_* = mixture_gmm_2's pick.\n",
             "    # Values = the calibration picks on all data, T2 and T3, set from the LVL2 sweep report's\n"
             "    # selection (README section 3, step 10): maximum DSC overlap with the a-priori inattent_behav\n"
             "    # standard, exact ties broken by median bootstrap ARI; kmeans_* = the carried k-means arm's\n"
             "    # pick, mixture_gmm_exp_* = the carried GMM arm's pick.\n", 1),
            ("# T2 calibration: k=2/k=3 DSC 0.723 vs 0.721; k=2 chosen by stability (median ARI 0.836 vs 0.791)",
             "# the carried k-means arm's k (the LVL2 sweep report's selection)", 1),
            ("# T2 calibration: GMM-2/GMM-3 DSC 0.685 vs 0.683; k=2 chosen by stability (median ARI 0.947 vs 0.924)",
             "# the carried GMM arm's k (the LVL2 sweep report's selection)", 1),
            ("    # flagged, the T2 99th-percentile markers of the LVL_0 permutation nulls (the LVL_0\n"
             "    # marker table, [cell 5]; runs counted within the participant-session). 0 disables one.\n",
             "    # flagged, the all-data 99th-percentile markers of the LVL_0 permutation nulls (the ALL\n"
             "    # column of the LVL_0 marker table, [cell 5]; runs counted within the participant-session).\n"
             "    # 0 disables one.\n", 1),
            ('"inattent_behav_sl_thresh": 20,', '"inattent_behav_sl_thresh": 21,', 1),
            ('"inattent_behav_periodic_p2_thresh": 9,', '"inattent_behav_periodic_p2_thresh": 9,', 1),
            ('"inattent_behav_periodic_p3_thresh": 11,', '"inattent_behav_periodic_p3_thresh": 11,', 1),
            ('"inattent_behav_periodic_p4_thresh": 13,', '"inattent_behav_periodic_p4_thresh": 13,', 1),
            ('"inattent_behav_ip_thresh": 9,', '"inattent_behav_ip_thresh": 8,', 1)]),
        ("# [notebook only] LVL_2 CALIBRATION CHECK", [
            ("# LVL_2_CONFIG must hold the T2 calibration:", "# LVL_2_CONFIG must hold the all-data calibration:", 1)]),
        ("# [cell 49]", [
            ('#   DATASETS  the run\'s datasets: the T2 run is "T2 calibration", the T3 run "T3 only"',
             '#   DATASETS  the run\'s datasets: the T2 run is "T2 only", the T3 run "T3 only", the T2 + T3 run\n'
             '#             "Pooled, overall", "Pooled, T2" and "Pooled, T3"', 1),
            ('DATASETS = {"T2": {"T2 calibration": ("T2", ["T2"], "independent")},',
             'DATASETS = {"T2": {"T2 only": ("T2", ["T2"], "independent")},', 1)]),
    ],
    NB_L1SR: [
        ("*[cell 0]*", [
            ("# LVL_1 Sweep Report — T2 calibration", "# LVL_1 Sweep Report — calibration on all data", 1),
            ("`launch_LV1_sweep_random.py` (T2 only).", "`launch_LV1_sweep_random.py` (T2 and T3: every participant).", 1)]),
        ("# [cell 1]", [('"_sweep_lvl1_T2"', '"_sweep_lvl1_all"', 2)]),
        ("*[cell 12]*", [("for the T2 calibration rows.", "for the T2+T3 calibration rows.", 1)]),
        ("# [cell 13]", [("read the T2 calibration sessions of these configurations.",
                          "read the T2+T3 calibration sessions of these configurations.", 1)]),
    ],
    NB_L2SR: [
        ("*[cell 0]*", [
            ("# LVL_2 Sweep Report — T2 calibration (a-priori gold standard)",
             "# LVL_2 Sweep Report — calibration on all data (a-priori gold standard)", 1),
            ("T2 is **calibration**: this report picks the configurations carried into the LVL2 runs (T2 and T3), where the\n"
             "hypotheses are tested.",
             "The **calibration** is on all data (T2 and T3): this report picks the configurations carried into the LVL2\n"
             "runs (T2, T3 and T2 + T3), where the hypotheses are tested.", 1),
            ("this report\ncalibrates on T2 (CA).", "this report\ncalibrates on T2 and T3 (CA and CB).", 1),
            ("(the T2 99th-percentile markers of the LVL_0 permutation nulls)",
             "(the all-data 99th-percentile markers of the LVL_0 permutation nulls)", 1)]),
        ("# [cell 1]", [("_sweep_lvl2_T2_", "_sweep_lvl2_all_", 2)]),
        ("# [cell 3]", [('APRIORI_COND = "T2"', 'APRIORI_COND = "both"', 1)]),
        ("# [cell 11]", [("# over the 5 scales, against the % of trials removed.",
                          "# over the scale x condition cells, against the % of trials removed.", 1)]),
        ("# [cell 16]", [('print(f"CARRY TO T3:  {CARRY}")', 'print(f"CARRY TO THE LVL2 RUNS:  {CARRY}")', 1)]),
        ("# [cell 20]", [
            ("_l1[_l1.condition == SWEEP_COND]", '_l1[(_l1.condition == SWEEP_COND) | (SWEEP_COND == "both")]', 1),
            ('"fig_lvl2_T2_profiles.pdf"', '"fig_lvl2_all_profiles.pdf"', 1)]),
        ("# [cell 24]", [('"fig_lvl2_T2_designs.pdf"', '"fig_lvl2_all_designs.pdf"', 1)]),
        ("# [cell 26]", [('"fig_lvl2_T2_overlap.pdf"', '"fig_lvl2_all_overlap.pdf"', 1)]),
    ],
    NB_FIG: [
        ("*[cell 0]*", [
            ("# Replication figures", "# Figures", 1),
            ("both sweeps were calibrated on T2;", "both sweeps were calibrated on all data (T2 and T3);", 1)]),
        ("# [cell 1]", [
            ('"_sweep_lvl1_T2"', '"_sweep_lvl1_all"', 1),
            ('"_sweep_lvl2_T2_', '"_sweep_lvl2_all_', 1),
            ("(e) both sweeps were calibrated on T2.", "(e) both sweeps were calibrated on all data (T2 and T3).", 1),
            ('if sel.get("condition") != "T2"]', 'if sel.get("condition") != "both"]', 1),
            ('"both selections\' condition = T2")', '"both selections\' condition = both (T2 and T3)")', 1),
            ("T2 calibration", "T2+T3 calibration", 2)]),
        ("# [cell 3]", [
            ("(T2 SWEEP)", "(T2+T3 SWEEP)", 1),
            ('(CA)", "', '(CA and CB)", "', 2),
            ("T2 calibration", "T2+T3 calibration", 2)]),
        ("# [cell 6]", [("(CA data)", "(CA and CB data)", 1)]),
        ("# [cell 7]", [('("T2 calibration", COHORT["T2"])', '("T2 only", COHORT["T2"])', 1)]),
        ("# [cell 11]", [("T2 calibration", "T2+T3 calibration", 1)]),
        ("# [cell 12]", [
            ('_l1b[_l1b.condition == SEL2["condition"]]',
             '_l1b[(_l1b.condition == SEL2["condition"]) | (SEL2["condition"] == "both")]', 1),
            ("T2 calibration", "T2+T3 calibration", 1)]),
    ],
    NB_REP: [
        ("*[cell 0]*", [
            ("# Final replication report — publication statistics",
             "# Final report, practical application (calibration on all data) — publication statistics", 1),
            ("| 1 | LVL1 — T2 calibration |", "| 1 | LVL1 — calibration on all data |", 1),
            ("| 2 | LVL1 — H1 segmentation and replication |", "| 2 | LVL1 — H1 segmentation across the datasets |", 1),
            ("| 3 | LVL2 — T2 classification calibration | LVL2_sweep_report; LVL2 T2 run |",
             "| 3 | LVL2 — classification calibration on all data | LVL2_sweep_report; LVL2 T2 + T3 run |", 1),
            ("| 6 | Consolidated replication results and exclusions |", "| 6 | Consolidated results and exclusions |", 1),
            ("(the change in DSC from T2 to T3, the replication summaries and the claims table)",
             "(the change in DSC between the datasets, the summaries across the datasets and the claims table)", 1),
            ("**Datasets.** T2 calibration (the T2 run, the sweeps' configuration) and T3 only (hold-out, refitted on T3 "
             "with the T2-chosen configuration). The code lines under a `# [pooled pathway: practical-application "
             "folder]` marker, each prefixed `#> `, belong to the pooled T2 + T3 pathway, which this pipeline does not run.",
             "**Datasets.** T2 only (the T2 run), T3 only (the T3 run) and the T2 + T3 run's Pooled, overall (one fit on "
             "both conditions), with its restrictions to each condition, Pooled, T2 and Pooled, T3. The configuration was "
             f"calibrated on all data (T2 and T3), so every dataset is in-sample; {NOTE_SHARE}. H1 (the LVL1 notebook's "
             "exports) has T2+T3 calibration (the LVL1 sweep's sessions, each detector at its own optimal "
             "configuration), T3 only and the pooled datasets.", 1)]),
        ("# [cell 1]", [
            ('"_sweep_lvl1_T2"', '"_sweep_lvl1_all"', 1),
            ('"_sweep_lvl2_T2_', '"_sweep_lvl2_all_', 1),
            ("# the T2-selected LVL_1 detector", "# the selected LVL_1 detector", 1),
            ("T2 calibration", "T2+T3 calibration", 2)]),
        ("# [cell 2]", [
            ('1: "LVL1 — T2 calibration",', '1: "LVL1 — calibration on all data",', 1),
            ('2: "LVL1 — H1 segmentation and replication", 3: "LVL2 — T2 classification calibration",',
             '2: "LVL1 — H1 segmentation across the datasets", 3: "LVL2 — classification calibration on all data",', 1),
            ('6: "Consolidated replication results",', '6: "Consolidated results",', 1)]),
        ("# [cell 3]", [
            ('DATASETS = {"T2 calibration":  ("T2",', 'DATASETS = {"T2 only":         ("T2",', 1),
            ('H3_DS = ["T2 calibration", "T3 only"]     # H3 is reported for the independent datasets',
             'IND_DS = ["T2 only", "T3 only"]           # the independent datasets\n'
             'H3_DS = DS                                # H3 is reported for every dataset\n'
             'H1_DS = ["T2+T3 calibration", "T3 only"] + POOLED_DS   # the datasets of the LVL1 notebook\'s H1 exports', 1),
            ('check("Calibration on T2: both sweeps and their selections", all(v == "T2" for v in _CAL.values()), str(_CAL))',
             'check("Calibration on all data (T2 and T3): both sweeps and their selections",\n'
             '      all(v == "both" for v in _CAL.values()), str(_CAL))', 1),
            ('"a-priori (T2 sweep)"', '"a-priori (T2+T3 sweep)"', 1)]),
        ("*[cell 5]*", [
            ("## 1. LVL1 — T2 calibration", "## 1. LVL1 — calibration on all data", 1),
            ("for every detector on the T2 sessions.", "for every detector on all sessions (T2 and T3).", 1)]),
        ("# [cell 6]", [
            ("over each detector's segmented T2 sessions (split into ≥ 2 blocks: ",
             "over each detector's segmented sessions (T2 and T3; split into ≥ 2 blocks: ", 1),
            ("over all {_n_t2} T2 sessions", "over all {_n_t2} sessions, T2 and T3", 1),
            ("LVL1 calibration (T2 sweep)", "LVL1 calibration (T2+T3 sweep)", 1),
            ("T2 calibration", "T2+T3 calibration", 1)]),
        ("*[cell 7]*", [
            ("## 2. LVL1 — H1 segmentation performance and replication",
             "## 2. LVL1 — H1 segmentation performance across the datasets", 1),
            ("**Datasets.** T2 calibration = each detector at its own η²_H-optimal sweep configuration (in the Corr% test, "
             "at its own Corr%-optimal configuration). T3 only uses the LVL_1 handoff (every detector at the T2-selected "
             "configuration).",
             "**Datasets.** T2+T3 calibration = each detector at its own η²_H-optimal configuration in the sweep on all "
             "data (in the Corr% test, at its own Corr%-optimal configuration). T3 only and the pooled datasets use the "
             "LVL_1 handoff (every detector at the selected configuration).", 1),
            ("η²_H and Corr% in T2 calibration, and η²_H and Corr% in T3 only.",
             "η²_H and Corr% in T2+T3 calibration, and η²_H and Corr% in T3 only.", 1)]),
        ("# [cell 8]", [
            ("d.Dataset.isin(DS)].reset_index(drop=True)      # this report's datasets",
             "d.Dataset.isin(H1_DS)].reset_index(drop=True)   # the H1 datasets", 1),
            ("for i, ds in enumerate(DS):", "for i, ds in enumerate(H1_DS):", 1),
            ("_mao = _mao[_mao.index.isin(DS)]", "_mao = _mao[_mao.index.isin(H1_DS)]", 1),
            ('if ds != "T2 calibration"}', 'if ds != "T2 only"}', 1),
            ("† = the T2-selected \"", "† = the selected \"", 1),
            ("\"detector. T2 calibration = each detector at its own η²_H-optimal T2-sweep configuration, in every column \"",
             "\"detector. T2+T3 calibration = each detector at its own η²_H-optimal sweep configuration, in every column \"",
             1),
            ('check("H1 T2 tests: ', 'check("H1 T2+T3 calibration tests: ', 1),
            ("# the selected LVL_1 configuration vs each contender's own T2 optimum (LVL1 sweep), and the T2 winner's margin",
             "# the selected LVL_1 configuration vs each contender's own optimum (LVL1 sweep), and the winner's margin", 1),
            ('"Table 2.6. H1 replication: numerical winner and statistically supported superiority per test"',
             '"Table 2.6. H1 across the datasets: numerical winner and statistically supported superiority per test"', 1),
            ("configuration in the LVL1 sweep; T3 runs every detector",
             "configuration in the LVL1 sweep; T3 only runs every detector", 1),
            ("of the T2 winner's η²_H lose", "of the winner's η²_H lose", 1),
            ("(T2 winner's margin over the runner-up", "(the winner's margin over the runner-up", 1),
            ("T2 calibration", "T2+T3 calibration", 11)]),
        ("# [cell 9]", [
            ('    for a_, g in P1_TIE.groupby("Arm", sort=False)) if len(P1_TIE) else ""\n',
             '    for a_, g in P1_TIE.groupby("Arm", sort=False)) if len(P1_TIE) else ""\n'
             'if len(P1_TIE) and not (len(P1_ZI[("both", "dynamic", "entropy")]) or len(P1_ZI[("both", "dynamic", "rt_var")])):\n'
             '    P1_TIE_TXT = " ".join(        # the pooled run\'s dynamic matrix has no exact-zero block\n'
             '        f"Tie-break of {FAM_LABEL[a_.rsplit(\'_\', 1)[0]]} ({a_.rsplit(\'_\', 1)[1]}): "\n'
             '        + " vs ".join(f"{r.Config} median {r.Median:.3f} ({r.lt50:.1f}% < .50)" for r in g.itertuples(index=False))\n'
             '        + " over all refits (the pooled run\'s dynamic matrix has no exact-zero block)."\n'
             '        for a_, g in P1_TIE.groupby("Arm", sort=False))\n', 1),
            ('_n2 = len(P1_M[("T2", "dynamic")])', '_n2 = len(P1_M[("both", "dynamic")])', 1),
            ('ce, cr = _p1_draws("T2", len(a), _n2)', 'ce, cr = _p1_draws("both", len(a), _n2)', 1),
            ('P1_M[("T2", des)][["id", "session", "block"]].values] for des in _p1_src("T2")}',
             'P1_M[("both", des)][["id", "session", "block"]].values] for des in _p1_src("both")}', 1),
            ('P1_ZK[("T2", des, f)]', 'P1_ZK[("both", des, f)]', 1),
            ('REPL["T2"][f"ari|{arm}"]', 'REPL["both"][f"ari|{arm}"]', 1),
            ("# the T2 sweep's stability tie-breaks (Table 3.4)", "# the sweep's stability tie-breaks (Table 3.4)", 1),
            ("exact-zero block of the T2 dynamic matrix, ", "exact-zero block of the pooled run's dynamic matrix, ", 1),
            ("(T2 matrices; Tables 3.5-3.6)", "(the pooled run's matrices; Tables 3.5-3.6)", 1),
            ("= the T2 run's (same resamples and order)", "= the pooled run's (same resamples and order)", 1),
            ("a unit of the rebuilt T2 matrices", "a unit of the pooled run's rebuilt matrices", 1)]),
        ("*[cell 12]*", [
            ("## 3. LVL2 — T2 classification calibration", "## 3. LVL2 — classification calibration on all data", 1),
            ("on the T2 dynamic blocks of the selected detector", "on the dynamic blocks (T2 and T3) of the selected detector",
             1)]),
        ("# [cell 13]", [
            ("the carried solutions' blocks (T2 run)", "the carried solutions' blocks (T2 + T3 run)", 1),
            ("the participant design of the carried solutions from the T2 run",
             "the participant design of the carried solutions from the pooled run", 1),
            ('by design (T2)", _dp,', 'by design (Pooled, overall)", _dp,', 1),
            ("only for the two carried solutions (T2 run);", "only for the two carried solutions (T2 + T3 run);", 1),
            ('and the tied candidates, T2",', 'and the tied candidates, T2 and T3",', 1),
            ("The carried solutions' refits are the T2 run's (Table 7.3). ",
             "The carried solutions' refits are the pooled run's (Table 7.3). ", 1),
            ('dose–response curve (T2)", S2("dose_picks")', 'dose–response curve (T2 and T3)", S2("dose_picks")', 1),
            ("(T2 here; the other datasets in Tables 4.10-4.16)",
             "(Pooled, overall here; the other datasets in Tables 4.10-4.16)", 1),
            ("T2 calibration", "Pooled, overall", 6)]),
        ("# [cell 20]", [
            ("counts, features; replication ", "counts, features; T2 vs T3 ", 1),
            ("the a-priori heuristic of the T2 sweep (T2 calibration)",
             "the a-priori heuristic of the T2+T3 sweep (Pooled, overall)", 1),
            ('P("dsc_designs", ["T2 calibration", "T3 only"]).assign(', 'P("dsc_designs", H3_DS).assign(', 1),
            ('"Table 4.8. Replication of the calibration criterion: change in DSC"',
             '"Table 4.8. Change in DSC between the datasets"', 1),
            ("{'T3 and pooled datasets' if POOLED_DS else 'T3 only'} — {fam}\",\n"
             "         FEAT_SHOW(P(f\"block_features_{i}\", DS[1:])), _FEAT_NOTE + \" T2 calibration: Tables 3.9–3.14.\")",
             "{'T2 only, T3 only and the pooled-derived datasets' if POOLED_DS else 'T2 only and T3 only'} — {fam}\",\n"
             "         FEAT_SHOW(P(f\"block_features_{i}\", [ds for ds in DS if ds != \"Pooled, overall\"])),\n"
             "         _FEAT_NOTE + \" Pooled, overall: Tables 3.9–3.14.\")", 1),
            ("# replication: direction and significance of the three primary tests, and independent vs pooled-derived change",
             "# T2 only vs T3 only: direction and significance of the three primary tests, and independent vs pooled-derived "
             "change", 1),
            ('"Replicates T2 → T3 (direction and q ≤ .05)"', '"Holds in T2 and T3 (direction and q ≤ .05)"', 1),
            ('"Table 4.17. H2 replication: estimate (q, BH within row) of each primary test across datasets"',
             '"Table 4.17. H2 across the datasets: estimate (q, BH within row) of each primary test"', 1),
            ('IRR: Δα. T2 calibration is "\n'
             '          "in-sample (the configuration was chosen on it); T3 only is the hold-out"\n'
             '          + ("; pooled rows share participants with the independent rows and are not independent replications."',
             'IRR: Δα. Every dataset is "\n'
             '          "in-sample (the configuration was chosen on all data, T2 and T3)"\n'
             '          + ("; the pooled rows share their participants with T2 only and T3 only."', 1),
            ("t.Dataset.isin(H3_DS).to_numpy()", "t.Dataset.isin(IND_DS).to_numpy()", 1),
            ("# calibration and T3 only tests, each once", "# only and T3 only tests, each once", 1),
            ("_hq.Dataset.isin(H3_DS)", "_hq.Dataset.isin(IND_DS)", 1),
            ("(the a-priori standard of the T2 sweep; the same ", "(the a-priori standard of the T2+T3 sweep; the same ", 1),
            ("T2 calibration", "T2 only", 11)]),
        ("# [cell 24]", [
            ('"removal volumes: Tables 5.2f–g. "', '"removal volumes: Tables 5.2f–j. "', 1),
            ('+ ("Pooled T2 + T3: not reported for H3 (it is not an independent replication). " if POOLED_DS else "")',
             '+ ("The pooled datasets share their participants with T2 only and T3 only. " if POOLED_DS else "")', 1),
            ('_LET = {"T2 calibration": ("a", "f"), "T3 only": ("b", "g")}',
             '_LET = {"T2 only": ("a", "f"), "T3 only": ("b", "g"), "Pooled, overall": ("c", "h"), "Pooled, T2": ("d", "i"),\n'
             '        "Pooled, T3": ("e", "j")}', 1),
            ('DS_SCOPE = {"T2 calibration": ("T2", "T2"), "T3 only": ("T3", "T3")}',
             'DS_SCOPE = {"T2 only": ("T2", "T2"), "T3 only": ("T3", "T3"), "Pooled, overall": ("both", "all"),\n'
             '            "Pooled, T2": ("both", "T2"), "Pooled, T3": ("both", "T3")}', 1)]),
        ("# [cell 26]", [
            ("m8 = STEP8[run][STEP8[run].Condition == cond]",
             'm8 = STEP8[run][(STEP8[run].Condition == cond) | (cond == "all")]', 1)]),
        ("# [cell 28]", [
            ("# ---- 5f. H3 replication T2 -> T3 and agreement with the secondary measures ",
             "# ---- 5f. H3 across the datasets and agreement with the secondary measures ", 1),
            ('"Replicates T2 → T3 (direction and q ≤ .05)"', '"Holds in T2 and T3 (direction and q ≤ .05)"', 1),
            ('"Table 5.10. H3 replication: Δα (q) of every removal contrast, T2 calibration and T3"',
             '"Table 5.10. H3 across the datasets: Δα (q) of every removal contrast"', 1),
            ('per trial × 10⁻⁶. T2 calibration is "\n          "in-sample; T3 only is the hold-out.")',
             'per trial × 10⁻⁶. Every dataset is "\n          "in-sample (calibration on all data); the pooled datasets '
             'share their participants with T2 only and "\n          "T3 only.")', 1),
            ('"split the rows by significance and sign (they add to 100%; the first two add to the significance share).",',
             '"split the rows by significance and sign (they add to 100%; the first two add to the significance share). "\n'
             '          "The pooled rows share their participants with T2 only and T3 only.",', 1),
            ("T2 calibration", "T2 only", 3)]),
        ("# [cell 30]", [
            ('            g = _cells(ds, sol, "dynamic", col)\n            if not len(g):\n',
             '            g = _cells(ds, sol, "dynamic", col)\n'
             '            if not len(g) or not ((H3T.Dataset == ds) & (H3T.Solution == sol) & (H3T.Design == "dynamic")).any():\n', 1),
            ("T2 calibration (left) and T3 only (right)", "T2 only (left) and T3 only (right)", 1),
            ('+ "Tests: α Tables 5.2a–b (vs baseline), 5.2f–g (vs null) and 5.3a–b (designs); secondary measures "\n'
             '                       "Tables 5.6a–f.")',
             '+ "Tests: α Tables 5.2a–e (vs baseline), 5.2f–j (vs null) and 5.3a–e (designs); secondary measures "\n'
             '                       "Tables 5.6a–f. Pooled, overall is not listed: its cells are those of Pooled, T2 and "\n'
             '                       "Pooled, T3. The pooled rows share their participants with T2 only and T3 only.")', 1),
            ('Overall, the row tests of Tables 5.2a–b (α) and 5.6a–e (BH across the eligible "\n'
             '                 "designs).")',
             'Overall, the row tests of Tables 5.2a–e (α) and 5.6a–e (BH across the eligible "\n'
             '                 "designs). Pooled, overall is not listed: its cells are those of Pooled, T2 and Pooled, T3.")', 1),
            ("for ds, n in _N9.items())",
             "for ds, n in _N9.items()\n"
             "                                 if (ds in IND_DS if short else ds != \"Pooled, overall\"))", 1),
            ("Tables 5.3a–b, 5.6f)", "Tables 5.3a–e, 5.6f)", 1),
            ('"(independent draws of each design\'s D), is in Table 5.3g (α).")',
             '"(independent draws of each design\'s D), is in Table 5.3g (α). Pooled, overall is not listed: its cells "\n'
             '                 "are those of Pooled, T2 and Pooled, T3.")', 1)]),
        ("*[cell 31]*", [("## 6. Consolidated replication results", "## 6. Consolidated results", 1)]),
        ("# [cell 32]", [
            ('_p1c = lambda c: any(c.startswith(f"{sol} —") and (f" {des} removal" in c or f"− {des}:" in c) for _, des, sol in _p1d)\n',
             '_p1i = [k for k in _p1d if k[0] in IND_DS]                     # the degenerate designs of T2 only and T3 only\n'
             '_p1c = lambda c: any(c.startswith(f"{sol} —") and (f" {des} removal" in c or f"− {des}:" in c) for _, des, sol in _p1i)\n', 1),
            (">= P1_MIN for k in _p1d)", ">= P1_MIN for k in _p1i)", 1),
            ('for ds, des, sol in _p1d) + ")"', 'for ds, des, sol in _p1i) + ")"', 1),
            ('+ ". " + p1_deg_text(H3_DS)) if len(_p1nt) else "")', '+ ". " + p1_deg_text(IND_DS)) if len(_p1nt) else "")', 1),
            ("# ---- 6. consolidated replication tables ", "# ---- 6. consolidated tables ", 1),
            (".reindex(columns=DS)", '.reindex(columns=["T2+T3 calibration"] + DS)', 1),
            ('zip(_w["T2 calibration"], _w["T3 only"])', 'zip(_w["T2 only"], _w["T3 only"])', 1),
            ('"Table 6.1. Replication of every hypothesis claim across the datasets"',
             '"Table 6.1. Every hypothesis claim across the datasets"', 1),
            ('"— = not tested (excluded" + (", not applicable, or pooled H3, which is not reported" if POOLED_DS else " or not "\n'
             '          "applicable") + "). T2 calibration is in-sample; T3 "\n'
             '          "only is the hold-out. H2 speed holds by construction in every dataset that is its own fit, T2 calibration and "\n'
             '          "T3 only included: the labelling rule',
             '"— = not tested (excluded or not applicable). Every dataset is in-sample (calibration on all data); the "\n'
             '          "pooled datasets share their participants with T2 only and T3 only. H1 is tested in T2+T3 calibration "\n'
             '          "and in T3 only, so its \'Holds in T2 and T3\' is not tested. H2 speed holds by construction in every "\n'
             '          "dataset that is its own fit, T2 only, T3 only and Pooled, overall included: the labelling rule', 1),
            ('"D > 0 and q ≤ .05. Per scale: Tables 5.2f–g."',
             '"D > 0 and q ≤ .05. Per scale: Tables 5.2f–j. The pooled rows share their participants with T2 only and "\n'
             '          "T3 only."', 1),
            ('("H1", "T3 test at each detector\'s own T2-optimal configuration", "blocked",\n'
             '     "the LVL_1 handoff holds every detector at the single selected configuration only; needs LVL_1 runs on T3 (a sweep)"),',
             '("H1", "T2 and T3 tested separately at each detector\'s own optimal configuration", "not computed",\n'
             '     "the sweep\'s sessions (T2 and T3) are tested together at each detector\'s own optimum; T3 only at the "\n'
             '     "selected configuration (the LVL_1 handoff)"),', 1),
            ('if POOLED_DS:\n'
             '    ex += [{"Analysis": "H3", "Item": "pooled T2 + T3 removal comparisons (Tables 5.2c–e, 5.2h–j, 5.3c–e)",\n'
             '            "Status": "not reported", "Reason": "the pooled run shares its participants with T2 and T3, so it is not an "\n'
             '            "independent replication; the LVL_2 run still computes and exports it"}]\n', "", 1)]),
        ("# [cell 34]", [
            ("η²_H and Corr% in T2 calibration (each detector at its own",
             "η²_H and Corr% in T2+T3 calibration (every session, each detector at its own", 1),
            ("and across rows the T2 calibration and T3 only rows, each test once",
             "and across rows the T2 only and T3 only rows, each test once", 1),
            ('("Selection", "T2 chose the LVL_1 detector and configuration, the LVL_2 exponents and k, and the heuristic '
             'thresholds: T2 results are in-sample; T3 only is the hold-out (LVL_0 drift models were fitted on T2 + T3)."),',
             '("Selection", "all data (T2 and T3) chose the LVL_1 detector and configuration, the LVL_2 exponents and k, and '
             'the heuristic thresholds (the all-data 99th-percentile markers of LVL_0): every result is in-sample (LVL_0 '
             'drift models were fitted on T2 + T3)."),', 1),
            ('"the pooled run (one joint fit) and its T2 / T3 subsets are reported for H1 (descriptives), H2 and the '
             'classification tables; its H3 removal comparisons are not reported (it shares its participants with T2 and T3)."',
             '"the pooled run (one joint fit, on the calibration data) and its T2 / T3 subsets are reported for H1 '
             '(descriptives), H2, H3 and the classification tables; they share their participants with T2 only and T3 only."',
             1)]),
        ("# [cell 35]", [
            ('lines = [f"# Final replication report — {ANALYSIS_METHOD}", "",',
             'lines = [f"# Final report, practical application (calibration on all data) — {ANALYSIS_METHOD}", "",', 1),
            ('_ndes = H3T.groupby(["Dataset", "Solution"], sort=False).size()',
             '_ndes = H3T[H3T.Dataset.isin(IND_DS)].groupby(["Dataset", "Solution"], sort=False).size()', 1),
            ('for ds, dlab in (("T2 calibration", "T2"), ("T3 only", "T3")):',
             'for ds, dlab in (("T2 only", "T2"), ("T3 only", "T3")):', 1)]),
    ],
}

TEXT_EDITS = {
    BUILD: [
        ("two LVL2 run notebooks block_detection_and_removal_LVL2_{T2,T3}_rep.ipynb",
         "three LVL2 run notebooks block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb", 1),
        ("# The LVL2 notebook is the template of the two run notebooks (T2, T3).",
         "# The LVL2 notebook is the template of the three run notebooks (T2, T3, T2 + T3).", 1),
        ("n_jobs 15 + 15: the two runs share CPUs 0-30.", "n_jobs 9 + 9 + 13: the three runs share CPUs 0-30.", 1),
        ("REP_RUNS = {\"T2\": ('[\"T2\"]', 15), \"T3\": ('[\"T3\"]', 15),",
         "REP_RUNS = {\"T2\": ('[\"T2\"]', 9), \"T3\": ('[\"T3\"]', 9),", 1)],
    SUBMIT: [
        ("# Runs the two LVL2 run notebooks (T2, T3) in parallel", "# Runs the three LVL2 run notebooks (T2, T3, T2+T3) in parallel",
         1),
        ("(taskset; n_jobs 15 + 15)", "(taskset; n_jobs 9 + 9 + 13)", 1)],
}

# ---- README: a generated header and section 6 datasets paragraph; sections 1-10 of the validation README otherwise.
README_SEP = "\n---\n\n## 1. Folder contents\n"
README_HEAD_SHA = "ca32cb7f787b26b7daa63e10f3236d6a96449a9570c12dd9f556537524f1cc08"   # sha256 of the validation README's header (everything before README_SEP)
README_HEAD = """# Block detection pipeline: practical application (EMST data)

{version}

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

{conditions}

**Heuristic thresholds.** The trial-level thresholds of the behavioural heuristic (`LVL_2_CONFIG`, `[cell 28]`) are
the all-data 99th-percentile markers of the LVL_0 permutation nulls, the ALL column of the LVL_0 marker table: straight
line 21; periodic p = 2 / 3 / 4: 9 / 11 / 13; 5-response stimulus-linked pattern 8. The LVL0 notebook is the
validation pipeline's: its printout of the marker table and its `[cell 3]` comment (copied into the LVL2 notebook's
upstream-definitions cell, `lvl0.py` and `lvl2.py`) name the T2 columns, which apply to the validation pipeline only.
"""
README_DATASETS = """**Datasets.** The T2 run's dataset is "T2 only" and the T3 run's "T3 only"; the T2 + T3 run (one fit on both
conditions) gives "Pooled, overall" and its restrictions to each condition, "Pooled, T2" and "Pooled, T3". The
configuration was calibrated on all data, so every dataset is in-sample, and the pooled datasets share their
participants with T2 only and T3 only. H1 has "T2+T3 calibration" (the LVL1 sweep's sessions, each detector at its own
η²_H-optimal configuration for η²_H, its own Corr%-optimal configuration for Corr%), "T3 only" (the selected
configuration) and the pooled datasets; its tests compare every pair of detectors in T2+T3 calibration and in T3 only,
each test with its own BH family. H2, H3 and the heuristic as a classifier are reported for every dataset (the
heuristic's BH family: T2 only and T3 only; the pooled rows carry no q); the supplementary LaTeX tables for T2 only
and T3 only.
"""
README_REGENERATE = """- This folder is generated: change the pipeline in `code/cpd_and_blk_rep_anaylsis`, then run
  `/usr/bin/python3 -B /home/sjsuss626/EMST_files/sjs_dissertation/code/make_practical_application_emst.py`
  (`--check` first: it writes nothing). By hand, set only the pins and the calibration values (section 3); never edit
  `lvl*.py` or the run notebooks. A regeneration moves this folder, executed notebooks included, to
  `sjs_dissertation/archive/practical_application_emst_<stamp>`, prints the pins and calibration values it held, and
  leaves `dervatives/practical_application_emst` untouched.
"""
README_EDITS = [
    ("the connection closes (line above). Before each step, set its **pins**",
     "the connection closes (line above). `submit_BDR_LVL2_notebooks_all.sh` and the report's `[cell 9]` (its `lvl2.py` "
     "rebuilds) set `taskset -c 0-30` themselves, so an outer `taskset` does not narrow them; with fewer CPUs, run step 10 "
     "by (a) with lower `n_jobs` in the run notebooks (`n_jobs` does not change a result). Before each step, set its "
     "**pins**", 1),
    ("The LVL2 notebook is the template of the two run notebooks. |",
     "The LVL2 notebook is the template of the three run notebooks. |", 1),
    ("| `block_detection_and_removal_LVL2_{T2,T3}_rep.ipynb` | The two LVL2 runs (generated",
     "| `block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb` | The three LVL2 runs (generated", 1),
    ("the two run notebooks and `LVL1_report`'s upstream-definitions cell",
     "the three run notebooks and `LVL1_report`'s upstream-definitions cell", 1),
    ("| Runs the two LVL2 run notebooks in parallel", "| Runs the three LVL2 run notebooks in parallel", 1),
    ("| the two LVL2 runs (one template) |", "| the three LVL2 runs (one template) |", 1),
    ("ΔDSC, replication summaries, claims", "ΔDSC, the summaries across the datasets, claims", 1),
    ("the outputs the two\nrun notebooks keep (section 6)", "the outputs the three\nrun notebooks keep (section 6)", 1),
    ("the two LVL2 runs' `n_jobs` 15 + 15)", "the three LVL2 runs' `n_jobs` 9 + 9 + 13)", 1),
    ("--condition T2 --subsample 0 --workers 30 --outdir _sweep_lvl1_T2` (command below) | `--lvl0-input` | "
     "`sweeps/_sweep_lvl1_T2/` | ~10 min |",
     "--condition both --subsample 0 --workers 30 --outdir _sweep_lvl1_all` (command below) | `--lvl0-input` | "
     "`sweeps/_sweep_lvl1_all/` | ~20 min (estimate) |", 1),
    ("| `sweeps/_sweep_lvl2_T2_<detector>/` with `apriori/` and `stability/` | ~9.5 h |",
     "| `sweeps/_sweep_lvl2_all_<detector>/` with `apriori/` and `stability/` | ~20 h (estimate) |", 1),
    ("| 10 | **The two LVL2 run notebooks** (T2, T3): see *Step 10* below the table |",
     "| 10 | **The three LVL2 run notebooks** (T2, T3, T2 + T3): see *Step 10* below the table |", 1),
    ("| ~4–4.5 h (T2 4.3 h, T3 3.9 h at `n_jobs` 10 per run) |", "| ~6–8 h (estimate; the T2 + T3 run sets the time) |", 1),
    ("`final_replication_supp_tables.tex` | < 20 min |", "`final_replication_supp_tables.tex` | < 30 min (estimate) |", 1),
    ("**Step 10, the two LVL2 run notebooks** (`block_detection_and_removal_LVL2_T2_rep.ipynb`,\n"
     "`block_detection_and_removal_LVL2_T3_rep.ipynb`):",
     "**Step 10, the three LVL2 run notebooks** (`block_detection_and_removal_LVL2_T2_rep.ipynb`,\n"
     "`block_detection_and_removal_LVL2_T3_rep.ipynb`, `block_detection_and_removal_LVL2_T2+T3_rep.ipynb`):", 1),
    ("It rewrites both run notebooks, with their pins at `None`.", "It rewrites the three run notebooks, with their pins at `None`.",
     1),
    ("4. Run the two in parallel, EITHER", "4. Run the three in parallel, EITHER", 1),
    ("--condition T2", "--condition both", 3),
    ("_sweep_lvl1_T2", "_sweep_lvl1_all", 6),
    ("_sweep_lvl2_T2_", "_sweep_lvl2_all_", 3),
    ("before the report because the report links them and checks their sidecars.\n",
     "before the report because the report links them and checks their sidecars. After step 1, check that the ALL\n"
     "99th-percentile column of the LVL_0 marker table reads 21 / 9 / 11 / 13 / 8, the heuristic thresholds (top of this\n"
     "README).\n", 1),
    ("Calibration is on T2 only (steps 5–9); the T3 run uses the T2 configuration unchanged.",
     "Calibration is on all data, T2 and T3 (steps 5–9); the three runs use that configuration unchanged.", 1),
    ("- (e) Both sweeps were calibrated on T2.", "- (e) Both sweeps were calibrated on all data (`--condition both`).", 1),
    ("The build writes `block_detection_and_removal_LVL2_{T2,T3}_rep.ipynb` from the template (conditions `[\"T2\"]` and\n"
     "`[\"T3\"]`; `n_jobs` 15 / 15, the two runs sharing CPUs 0–30).",
     "The build writes `block_detection_and_removal_LVL2_{T2,T3,T2+T3}_rep.ipynb` from the template (conditions `[\"T2\"]`,\n"
     "`[\"T3\"]` and `[\"T2\", \"T3\"]`; `n_jobs` 9 / 9 / 13, the three runs sharing CPUs 0–30).", 1),
    ("(pins `None`, `n_jobs` 15 / 15)", "(pins `None`, `n_jobs` 9 / 9 / 13)", 1),
    (re.compile(r"\*\*Datasets\.\*\* The T2 run is the calibration.*?own BH family\.\n", re.S), README_DATASETS, 1),
    ("- Edit the notebooks, then run `build_level_scripts.py`; never edit `lvl*.py` or the run notebooks by hand.\n",
     README_REGENERATE, 1),
    (re.compile(r"- Pooled pathway \(top of this README\):.*?and mark pooled code the same way\.\n", re.S), "", 1),
]

# ---- forbidden wording and leftovers, scanned in every file of the result. ALLOWED: (file, phrase) a hit may sit in.
FORBIDDEN = [r"dynamic_qc", r"\[pooled pathway", r"(?m)^[ \t]*#>", r"T2 calibration", r"hold-out", r"held out",
             r"out-of-sample", r"T2-selected", r"T2-chosen", r"T2-optimal", r"T2 optim", r"T2 winner", r"T2 sweep",
             r"T2 SWEEP", r"T2-sweep", r"Replicates T2", r"_sweep_lvl[12]_T2", r"--condition T2", r"calibrat\w* on T2(?! and)",
             r"Calibration on T2", r"CARRY TO T3", r"two run notebooks", r"two LVL2 run", r"the two runs", r"15 \+ 15",
             r"15 / 15", r"(?<!Cohort A )\(CA\)", r"CA data", r"(?<!_)[Rr]eplications?(?!_)", r"REPLICATION",
             r"fig_lvl2_T2_"]
ALLOWED = {(f, "bootstrap replications") for f in ["block_detection_and_removal_LVL2.ipynb", "lvl2.py",
                                                   *["block_detection_and_removal_LVL2_T2_rep.ipynb",
                                                     "block_detection_and_removal_LVL2_T3_rep.ipynb",
                                                     "block_detection_and_removal_LVL2_T2+T3_rep.ipynb"]]}


class Plan:
    """Collects every mismatch, so one run lists them all."""

    def __init__(self):
        self.errors, self.notes = [], []

    def fail(self, msg):
        self.errors.append(msg)

    def sub(self, where, text, old, new, count):
        if isinstance(old, re.Pattern):
            n = len(old.findall(text))
            if n != count:
                self.fail(f"{where}: pattern {old.pattern[:80]!r} matches {n} times, expected {count}")
                return text
            return old.sub(lambda m: new, text)
        n = text.count(old)
        if n != count:
            self.fail(f"{where}: {old[:100]!r} occurs {n} times, expected {count}")
            return text
        return text.replace(old, new)


def strip_markers(text):
    """Restore the marker blocks: a header line '# [pooled pathway: ...] <note>' followed by '#> <line>' / '#>' lines
    becomes '# <note>' and the lines; a header without lines is dropped. Returns (text, headers, lines, bad)."""
    lines, out, nh, nl, bad = text.split("\n"), [], 0, 0, []
    i = 0
    while i < len(lines):
        m = MARKER.match(lines[i])
        if not m:
            if "[pooled pathway: practical-application folder]" in lines[i] and lines[i].lstrip().startswith("#"):
                bad.append(lines[i])
            out.append(lines[i]); i += 1
            continue
        j, block = i + 1, []
        while j < len(lines) and (lines[j] == "#>" or lines[j].startswith("#> ")):
            block.append(lines[j][3:]); j += 1
        nh += 1; nl += len(block)
        if block:
            out.append("# " + m.group(1)); out.extend(block)
        i = j
    return "\n".join(out), nh, nl, bad


def sub_paths(text):
    counts = []
    for old, new in PATHS:
        counts.append(text.count(old)); text = text.replace(old, new)
    return text, counts


def nb_dump(nb):
    return json.dumps(nb, indent=1, ensure_ascii=False) + "\n"


def cell_text(c):
    return "".join(c.get("source", []))


def first_line(c):
    return cell_text(c).split("\n", 1)[0]


def compiles(src, name):
    try:
        compile(src, name, "exec")
        return True
    except SyntaxError:
        return False


def transform_notebook(name, raw, plan):
    """M, P, the cell edits and K on one notebook. Returns its new text."""
    if nb_dump(json.loads(raw)) != raw:
        plan.fail(f"{name}: does not round-trip through json.dumps(indent=1, ensure_ascii=False); format changed")
    nb = json.loads(raw)
    paths, nh, nl = [0, 0, 0, 0], 0, 0
    labels = [first_line(c) for c in nb["cells"]]
    edits = {}
    for prefix, anchors in NB_EDITS.get(name, []):
        idx = [i for i, lab in enumerate(labels) if lab.startswith(prefix)]
        if len(idx) != 1:
            plan.fail(f"{name}: {len(idx)} cells start with {prefix!r}, expected 1")
            continue
        edits[idx[0]] = (prefix, anchors)
    for i, c in enumerate(nb["cells"]):
        old = cell_text(c)
        new, h, ln, bad = strip_markers(old)
        nh += h; nl += ln
        for b in bad:
            plan.fail(f"{name} cell {i}: unrecognised marker line {b[:80]!r}")
        new, pc = sub_paths(new)
        paths = [a + b for a, b in zip(paths, pc)]
        if i in edits:
            prefix, anchors = edits[i]
            for a_old, a_new, cnt in anchors:
                new = plan.sub(f"{name} [{prefix}]", new, a_old, a_new, cnt)
        if c["cell_type"] == "code" and compiles(old, f"{name}:{i}") and not compiles(new, f"{name}:{i}"):
            plan.fail(f"{name} cell {i} ({labels[i][:40]}): no longer compiles")
        if new != old:
            c["source"] = new.splitlines(keepends=True)
        if c["cell_type"] == "code":
            c["outputs"], c["execution_count"] = [], None
        c.get("metadata", {}).pop("execution", None)
    nb.setdefault("metadata", {})["kernelspec"] = dict(KERNELSPEC)
    if tuple(paths) != PATH_COUNTS[name]:
        plan.fail(f"{name}: path substitutions {tuple(paths)}, expected {PATH_COUNTS[name]}")
    if (nh, nl) != MARKER_COUNTS.get(name, (0, 0)):
        plan.fail(f"{name}: marker blocks (headers, lines) {(nh, nl)}, expected {MARKER_COUNTS.get(name, (0, 0))}")
    return nb_dump(nb)


def transform_readme(raw, plan):
    if raw.count(README_SEP) != 1:
        plan.fail("README.md: the separator before section 1 is not unique")
        return raw
    head, body = raw.split(README_SEP)
    sha = hashlib.sha256(head.encode()).hexdigest()
    if sha != README_HEAD_SHA:
        plan.fail(f"README.md: the validation header changed (sha256 {sha}); check README_HEAD, then set README_HEAD_SHA")
    version = re.findall(r"(?m)^Version .*$", head)
    conditions = re.findall(r"(?ms)^\*\*Conditions\.\*\* .*?(?=\n\n)", head)
    if len(version) != 1 or len(conditions) != 1:
        plan.fail("README.md: the header's Version line or Conditions paragraph is not unique")
        return raw
    body, pc = sub_paths(body)
    if tuple(pc) != PATH_COUNTS[README]:
        plan.fail(f"README.md: path substitutions {tuple(pc)}, expected {PATH_COUNTS[README]}")
    for old, new, cnt in README_EDITS:
        body = plan.sub("README.md", body, old, new, cnt)
    return README_HEAD.format(version=version[0], conditions=conditions[0]) + README_SEP + body


def transform_text(name, raw, plan):
    if name == README:
        return transform_readme(raw, plan)
    new, nh, nl, bad = strip_markers(raw)
    for b in bad:
        plan.fail(f"{name}: unrecognised marker line {b[:80]!r}")
    if (nh, nl) != MARKER_COUNTS.get(name, (0, 0)):
        plan.fail(f"{name}: marker blocks (headers, lines) {(nh, nl)}, expected {MARKER_COUNTS.get(name, (0, 0))}")
    new, pc = sub_paths(new)
    if tuple(pc) != PATH_COUNTS[name]:
        plan.fail(f"{name}: path substitutions {tuple(pc)}, expected {PATH_COUNTS[name]}")
    for old, a_new, cnt in TEXT_EDITS.get(name, []):
        new = plan.sub(name, new, old, a_new, cnt)
    if name.endswith(".py") and not compiles(new, name):
        plan.fail(f"{name}: does not compile")
    return new


def texts_of(name, content):
    """The text a scan reads: a notebook's cell sources, otherwise the file."""
    if name.endswith(".ipynb"):
        return "\n".join(cell_text(c) for c in json.loads(content)["cells"])
    return content


def scan(files, plan):
    """The forbidden wording, the validation folder's name and the dataset path over a {name: content} result."""
    n_src, n_data = 0, 0
    for name, content in sorted(files.items()):
        text = texts_of(name, content)
        for pat in FORBIDDEN:
            for m in re.finditer(pat, text):
                line = text[text.rfind("\n", 0, m.start()) + 1: text.find("\n", m.end()) if "\n" in text[m.end():] else None]
                if any(name == f and phrase in line for f, phrase in ALLOWED):
                    continue
                plan.fail(f"{name}: forbidden {pat!r}: {line.strip()[:110]!r}")
        n_src += text.count("cpd_and_blk_rep_anaylsis") * (name == README)
        if name != README and "cpd_and_blk_rep_anaylsis" in text:
            plan.fail(f"{name}: names the validation folder")
        n_data += text.count(DATASET)
    return n_src, n_data


def snapshot(folder):
    """sha256 and mode of every entry under a folder (directories included)."""
    out = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames.sort()
        for d in dirnames:
            p = Path(dirpath) / d
            out[str(p.relative_to(folder)) + "/"] = ("dir", os.stat(p).st_mode)
        for f in sorted(filenames):
            p = Path(dirpath) / f
            out[str(p.relative_to(folder))] = (hashlib.sha256(p.read_bytes()).hexdigest(), os.stat(p).st_mode)
    return out


def generate(plan):
    """Read and transform the validation folder in memory. Returns ({name: text}, {name: mode})."""
    entries = sorted(os.listdir(SRC))
    known = set(GENERATED) | set(BUILT_SRC)
    for e in entries:
        if e in known or e in SKIPPED_DIRS or e.endswith(SKIPPED_SUFFIX):
            continue
        plan.fail(f"validation folder: unknown entry {e!r} (add it to GENERATED or the skipped entries)")
    for f in GENERATED + BUILT_SRC:
        if not (SRC / f).is_file():
            plan.fail(f"validation folder: {f} is missing")
    if plan.errors:
        return {}, {}
    files, modes = {}, {}
    for name in GENERATED:
        raw = (SRC / name).read_text(encoding="utf-8")
        files[name] = transform_notebook(name, raw, plan) if name.endswith(".ipynb") else transform_text(name, raw, plan)
        modes[name] = os.stat(SRC / name).st_mode & 0o7777
    # static checks over the result
    r = subprocess.run(["bash", "-n"], input=files[SUBMIT], text=True, capture_output=True)
    if r.returncode:
        plan.fail(f"{SUBMIT}: bash -n: {r.stderr.strip()[:200]}")
    n_src, n_data = scan(files, plan)
    if n_src != 2:
        plan.fail(f"README.md names the validation folder {n_src} times, expected 2")
    if n_data != 4:
        plan.fail(f"the dataset path occurs {n_data} times, expected 4")
    shared = []
    for name in (NB_LVL0, NB_LVL1, NB_LVL2):
        cells = {first_line(c): cell_text(c) for c in json.loads(files[name])["cells"]}
        shared.append([cells.get(f"# [cell {k}]") for k in (0, 1, 2)])
    if not shared[0] == shared[1] == shared[2] or None in shared[0]:
        plan.fail("[cell 0]-[cell 2] differ between the three level notebooks")
    l2 = {first_line(c): cell_text(c) for c in json.loads(files[NB_LVL2])["cells"]}
    for lab, anchor in (("# [cell 0]", "n_jobs = 31\n"), ("# [cell 28]", '"conditions": ["T2"],')):
        if l2.get(lab, "").count(anchor) != 1:
            plan.fail(f"{NB_LVL2} {lab}: the build anchor {anchor!r} is not unique")
    inp = [t for lab, t in l2.items() if lab.startswith("# [notebook only] LVL_2 INPUT")]
    if len(inp) != 1 or inp[0].count("RUN_NAME = None") != 1:
        plan.fail(f"{NB_LVL2}: the build anchor 'RUN_NAME = None' is not unique in the input cell")
    return files, modes


def cell_diffs(a_text, b_text):
    """Changed lines between two notebooks' cell sources, by cell label."""
    out = []
    a = {first_line(c): cell_text(c) for c in json.loads(a_text)["cells"]}
    b = {first_line(c): cell_text(c) for c in json.loads(b_text)["cells"]}
    for lab in list(dict.fromkeys(list(a) + list(b))):
        if a.get(lab) != b.get(lab):
            d = [l for l in difflib.unified_diff((a.get(lab) or "").split("\n"), (b.get(lab) or "").split("\n"),
                                                 lineterm="", n=0) if l[:1] in "+-" and l[:3] not in ("+++", "---")]
            out.append((lab, d))
    return out


def compare_with_current(files):
    """--check: the generated files against the current practical folder (notebooks by cell source)."""
    if not DST.exists():
        print(f"{DST} does not exist yet")
        return
    same = []
    for name, content in files.items():
        p = DST / name
        if not p.exists():
            print(f"  {name}: missing in the current folder"); continue
        cur = p.read_text(encoding="utf-8")
        if name.endswith(".ipynb"):
            d = cell_diffs(cur, content)
            if d:
                print(f"  {name}: {len(d)} cell(s) differ (pins and calibration values set by hand show here)")
                for lab, lines in d:
                    print(f"    {lab[:60]}"); [print(f"      {l[:150]}") for l in lines[:12]]
                continue
        elif cur != content:
            print(f"  {name}: differs"); continue
        same.append(name)
    print(f"{len(same)} of {len(files)} generated files equal the current folder's")


def check_built(stage, files, out, plan):
    """The gates after build_level_scripts.py ran in the staging folder."""
    for must in ("verified lvl0.py: knob overrides", "sweep edits present", "no notebook-only names",
                 f"verified {len(RUN_NBS)} LVL2 run notebooks", "verified LVL1_report.ipynb"):
        if must not in out:
            plan.fail(f"build: {must!r} not printed")
    for nb in RUN_NBS:
        if f"wrote {nb}" not in out:
            plan.fail(f"build: {nb} not written")
    if "wrote the upstream-definitions cell" in out:
        plan.fail("build: rewrote an upstream-definitions cell (the generated notebooks are not the validation build's)")
    have = sorted(str(p.relative_to(stage)) for p in stage.rglob("*"))
    want = sorted(GENERATED + BUILT)
    if have != want:
        plan.fail(f"staging holds {sorted(set(have) - set(want))} extra, {sorted(set(want) - set(have))} missing")
    for name in (NB_LVL2, NB_L1R):
        if (stage / name).read_text(encoding="utf-8") != files[name]:
            plan.fail(f"build: changed {name}")
    for nb, (n_jobs, conds) in RUN_NBS.items():
        p = stage / nb
        if not p.exists():
            continue
        d = json.loads(p.read_text(encoding="utf-8"))
        cells = {first_line(c): cell_text(c) for c in d["cells"]}
        if f"n_jobs = {n_jobs}\n" not in cells.get("# [cell 0]", "") or f'"conditions": {conds},' not in cells.get("# [cell 28]", ""):
            plan.fail(f"{nb}: n_jobs {n_jobs} / conditions {conds} not set")
        if any(c.get("outputs") for c in d["cells"]) or d["metadata"].get("kernelspec") != KERNELSPEC:
            plan.fail(f"{nb}: outputs or kernelspec")
    banner = re.compile(r"^# =+ NOTEBOOK CELL (\d+) =+$", re.M)

    def sections(text):
        parts = banner.split(text)
        return {"preamble": parts[0], **{int(parts[k]): parts[k + 1] for k in range(1, len(parts), 2)}}
    for script, allowed in (("lvl0.py", {2}), ("lvl1.py", {2}), ("lvl2.py", {2, 28, 49})):
        a, b = sections((SRC / script).read_text(encoding="utf-8")), sections((stage / script).read_text(encoding="utf-8"))
        if set(a) != set(b):
            plan.fail(f"{script}: the NOTEBOOK CELL banners differ from validation's")
            continue
        diff = sorted(k for k in a if a[k] != b[k])
        if set(diff) - allowed or not diff:
            plan.fail(f"{script}: differs from validation's in {diff}, expected within {sorted(allowed)}")
        plan.notes.append(f"{script}: differs from validation's in NOTEBOOK CELL {diff}")
    built = {n: (stage / n).read_text(encoding="utf-8") for n in BUILT}
    scan(built, plan)


def manual_settings(old_dir, new_dir):
    """The pins and calibration values the archived folder held (its cells that differ from the new generation)."""
    print(f"\nsettings in the archived folder {old_dir} that the new folder resets:")
    any_ = False
    for name in NOTEBOOKS + list(RUN_NBS):
        a, b = old_dir / name, new_dir / name
        if a.exists() and b.exists():
            for lab, lines in cell_diffs(b.read_text(encoding="utf-8"), a.read_text(encoding="utf-8")):
                any_ = True
                print(f"  {name} {lab[:50]}")
                for l in lines:
                    if l.startswith("+"):
                        print(f"    {l[1:][:150]}")
    if not any_:
        print("  none")


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--check", action="store_true", help="transform in memory and check; write nothing")
    args = ap.parse_args()
    plan = Plan()
    before = snapshot(SRC)
    files, modes = generate(plan)
    if plan.errors:
        print(f"{len(plan.errors)} problem(s); nothing written:")
        for e in plan.errors:
            print("  " + e)
        sys.exit(1)
    print(f"transformed {len(files)} files of {SRC} in memory: every anchor, path, marker and scan check passed")
    if args.check:
        compare_with_current(files)
        if snapshot(SRC) != before:
            sys.exit("the validation folder changed during the check")
        return
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    stage = DST.parent / f".practical_application_emst.staging_{stamp}"
    stage.mkdir()                                     # fails if it exists

    def write(name, text):
        p = (stage / name).resolve()
        assert p.parent == stage.resolve(), p
        p.write_text(text, encoding="utf-8")
        os.chmod(p, modes[name])
    for name, text in files.items():
        write(name, text)
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    r = subprocess.run(["/usr/bin/python3", "-B", BUILD], cwd=stage, env=env, capture_output=True, text=True)
    out = r.stdout + r.stderr
    print("build_level_scripts.py in the staging folder:\n" + "\n".join("  " + l for l in out.strip().split("\n")))
    if r.returncode:
        plan.fail(f"build exited with {r.returncode}")
    else:
        check_built(stage, files, out, plan)
    if snapshot(SRC) != before:
        plan.fail("the validation folder changed")
    if plan.errors:
        failed = stage.with_name(stage.name + "_FAILED")
        stage.rename(failed)
        print(f"{len(plan.errors)} problem(s); kept as {failed}; {DST} unchanged:")
        for e in plan.errors:
            print("  " + e)
        sys.exit(1)
    for n in plan.notes:
        print(n)
    archived = None
    if DST.exists():
        archived = ARCHIVE / f"practical_application_emst_{stamp}"
        if archived.exists():
            sys.exit(f"{archived} exists; {stage} kept, {DST} unchanged")
        DST.rename(archived)
    try:
        stage.rename(DST)
    except OSError:
        if archived:
            archived.rename(DST)
        raise
    fp = {s: hashlib.sha256((DST / s).read_bytes()).hexdigest()[:16] for s in ("lvl0.py", "lvl1.py", "lvl2.py")}
    print(f"\nwrote {DST} ({len(GENERATED) + len(BUILT)} files); script fingerprints {fp}")
    if archived:
        print(f"the previous folder is {archived}")
        manual_settings(archived, DST)
    print("next: the README's section 3, from step 1 (create LVL_OUTS/run_logs first)")


if __name__ == "__main__":
    main()
