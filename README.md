# Block detection pipeline: the code folders

A pipeline that finds blocks of careless responding in rating tasks (participants rate stimuli on several scales, with
response times) and tests whether removing them improves inter-rater reliability: H1 compares change-point detectors'
blocks, H2 tests whether the flagged blocks behave like careless responding, and H3 compares the reliability after
removing the flagged blocks with matched random removal and with removing whole sessions or participants. This folder
holds three versions of it, each a complete, self-contained pipeline with its own README.

## 1. The three folders

| Folder | What it is | Version | Outputs |
|---|---|---|---|
| [`cpd_and_blk_rep_anaylsis/`](cpd_and_blk_rep_anaylsis/README.md) | The validation pipeline of the dissertation: both sweeps calibrated on condition T2 of the EMST data, and the calibrated configuration run, unchanged, on T2 and on T3. Frozen: its run of record (LVL0 handoff `lv0_out_20261106_180438`, LVL1 handoff `lv1_out_20261106_190046`, LVL2 runs `..._20261107_192158`, final report 2026-11-08) is the dissertation's. | 0.0.1 | `dervatives/dynamic_qc` |
| [`practical_application_emst/`](practical_application_emst/README.md) | The EMST data for the published norms: both sweeps calibrated on all data (T2 and T3), and the calibrated configuration run on T2, on T3 and on T2 + T3. It is the validation pipeline with its pooled pathway active, written by [`make_practical_application_emst.py`](make_practical_application_emst.py). | 0.0.1 | `dervatives/practical_application_emst` |
| [`practical_application_generic/`](practical_application_generic/README.md) | The general tool, for any dataset in the same long format: one pooled run on all data, blocks detected (dynamic segmentation) or given by a column of the data (predefined segmentation), every dataset-specific setting marked `"SET_ME"`, paths from one `PROJECT_ROOT`. | 1.0.1 | `<PROJECT_ROOT>/dervatives/practical_application_generic` |

**How they relate.**

- `cpd_and_blk_rep_anaylsis` is the source of the EMST folder. `make_practical_application_emst.py` writes
  `practical_application_emst` from it by exact-text edits (among them: its pooled pathway restored, its paths pointed
  at the EMST outputs, its calibration opened to all data) and runs the EMST folder's build. By hand, set only the EMST
  folder's pins and calibration values; every other change goes into the validation folder, and the EMST folder is
  regenerated: `/usr/bin/python3 -B make_practical_application_emst.py --check` first (it transforms in memory, checks
  and compares with the current folder; it writes nothing), then without `--check`. A regeneration moves the old folder,
  executed notebooks included, to `sjs_dissertation/archive/practical_application_emst_<stamp>`, prints the pins and
  calibration values it held, and never writes `dervatives/`; a staging folder that fails a check is kept as
  `.practical_application_emst.staging_<stamp>_FAILED`.
- `practical_application_generic` is its own code: it began as a one-time copy of the EMST folder, is maintained by hand
  and is never regenerated. Fixes made in the validation folder are ported to it by hand.
- The validation and EMST folders hold the author's absolute paths (`/home/sjsuss626/EMST_files/sjs_dissertation`, with
  the data at `dset/all_subjects_long.csv`), so they run only in that project folder. The generic folder takes every
  path from its `PROJECT_ROOT` setting.

## 2. Which folder to use

| To … | Use |
|---|---|
| reproduce the dissertation's analyses (calibration on T2, test on T3) | `cpd_and_blk_rep_anaylsis` |
| compute the EMST norms (the EMST data, calibrated on all data) | `practical_application_emst` |
| analyse new data in the long format, or data whose blocks the task design gives or are too fine to detect | `practical_application_generic` (start with [its README](practical_application_generic/README.md): data format, settings, run order) |

## 3. Outputs

| Folder | Outputs (`LVL_OUTS`, `SWEEPS_DIR`, `FIG_DIR`) |
|---|---|
| `cpd_and_blk_rep_anaylsis` | `/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/dynamic_qc/{lvl_outs,sweeps,figures}` |
| `practical_application_emst` | `/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/{lvl_outs,sweeps,figures}` |
| `practical_application_generic` | `<PROJECT_ROOT>/dervatives/practical_application_generic/{lvl_outs,sweeps,figures}` |

Outputs never go into a code folder. Besides the files each folder's build writes (`lvl0.py`, `lvl1.py`, `lvl2.py` and
the LVL2 run notebooks), a run writes into its code folder only the launchers' `errors/` folder, the `*_executed.ipynb`
copies of command-line notebook runs and, when the submit script executes them in place, the LVL2 run notebooks'
outputs. Each folder's `.gitignore` keeps `errors/`, the executed copies, logs and stray output files out of the
repository.

## 4. Review guidance

- **Read order** (the generic folder; the other two have the same cells, with the LVL2 designs in `[cell 49]`): the
  folder's README; `[cell 2]` of a level notebook (the paths, the settings and the settings check, the version); the
  configuration cells (`LVL_0_CONFIG` in LVL0 `[cell 3]`, `LVL_1_CONFIG` in LVL1 `[cell 9]`, `LVL_2_CONFIG` in LVL2
  `[cell 28]`); the LVL1 detection (`[cell 19]`, `[cell 20]`); the LVL2 designs (`[cell 29]`); then the reports. The
  first line of every code cell is its label: `# [cell N]` cells form the scripts `lvl*.py`, `# [notebook only]` cells
  never reach them.
- **Comparing the folders.** Notebooks as scripts, and the built scripts, compare with `diff`:

  ```bash
  /usr/bin/python3 -m nbconvert --to script --stdout practical_application_emst/block_detection_and_removal_LVL1.ipynb > /tmp/emst_LVL1.py
  /usr/bin/python3 -m nbconvert --to script --stdout practical_application_generic/block_detection_and_removal_LVL1.ipynb > /tmp/generic_LVL1.py
  diff /tmp/emst_LVL1.py /tmp/generic_LVL1.py
  diff practical_application_emst/lvl1.py practical_application_generic/lvl1.py
  ```

  `/usr/bin/python3` is the interpreter with the packages (nbconvert among them). The generic folder ships its scripts
  built in the placeholder state (`"SET_ME"` values); `build_level_scripts.py` rebuilds them after a notebook change.
  The generic folder differs from the EMST folder in: one LVL2 run on all data (run key `all`, dataset "All data") in
  place of the EMST folder's three runs; the predefined segmentation (blocks from a column of the data, with four
  block-id rules) beside the dynamic one; the `"SET_ME"` settings with their checks, and `PROJECT_ROOT` in place of
  fixed paths; the LVL0 input check of the data format and its suggested-settings cell; the data's own scales (the
  periodic markers' periods 2 … S − 1 of S scales), conditions (one or more) and sessions (any number per participant),
  and an optional age column; in H3, a condition where a design flags no unit counts as cells of exactly zero change
  (Step 9 and STEP 10 alike), where the EMST folder's STEP 10 leaves such a design out; a k-means or GMM fit that a
  small design matrix cannot carry is recorded and never counted as flagging 0 units; version 1.0.1.
- **Checks of a run.** Each folder's final report lists every lineage and consistency check it ran in its Table 7.3
  (pins, configurations against the sweeps' selections, script fingerprints, pipeline version, figure sidecars); a
  complete, consistent run has no "no" there.
- **SHA-256 snapshots.** To confirm later that a folder is the state you reviewed, record its checksums outside it and
  check them:

  ```bash
  (cd practical_application_emst && find . -maxdepth 1 -type f | sort | xargs sha256sum) > ~/emst_folder.sha256
  (cd practical_application_emst && sha256sum -c --quiet ~/emst_folder.sha256) && echo unchanged
  ```

- **Not in the repository.** [`.gitignore`](.gitignore) keeps private review material, earlier states of the project and
  the generator's staging folders out of the repository.
