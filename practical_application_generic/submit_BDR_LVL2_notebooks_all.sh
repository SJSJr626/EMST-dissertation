#!/usr/bin/env bash
# Runs the LVL2 run notebook block_detection_and_removal_LVL2_all_rep.ipynb, executed in place so the notebook keeps its
# outputs, on the CPUs of CPU_SET (taskset; the notebook's n_jobs is RUN_N_JOBS of build_level_scripts.py). Run it inside
# tmux:
#   tmux new -s lvl2run
#   bash <PROJECT_ROOT>/code/practical_application_generic/submit_BDR_LVL2_notebooks_all.sh
# Before running: set the four settings below, and LVL1_HANDOFF and LVL2_SWEEP in the run notebook (n_jobs is set by
# build_level_scripts.py). The script stops first if a setting holds "SET_ME", a pin is unset, the handoff is missing,
# or the LVL2 sweep's selection was made on a different handoff.
# Logs: <PROJECT_ROOT>/dervatives/practical_application_generic/lvl_outs/run_logs/run_<notebook>_<start time>.log
set -u
# the absolute project folder holding code/, dset/ and dervatives/ (README, "Paths"; EMST /home/sjsuss626/EMST_files/sjs_dissertation)
PROJECT_ROOT="SET_ME"
# the interpreter with the packages (README, "Setup"; EMST /usr/bin/python3)
PYTHON="SET_ME"
# a Jupyter kernel that runs PYTHON (jupyter kernelspec list; EMST block_detection_irt)
JUPYTER_KERNEL="SET_ME"
# taskset CPU list of the run, e.g. 0-7, with as many CPUs as RUN_N_JOBS; "" = no pinning (EMST 0-30)
CPU_SET="SET_ME"

_unset=()
[ "$PROJECT_ROOT" = "SET_ME" ] && _unset+=("PROJECT_ROOT (top of this script): the absolute project folder (README, Paths; EMST /home/sjsuss626/EMST_files/sjs_dissertation)")
[ "$PYTHON" = "SET_ME" ] && _unset+=("PYTHON (top of this script): the interpreter with the packages (README, Setup; EMST /usr/bin/python3)")
[ "$JUPYTER_KERNEL" = "SET_ME" ] && _unset+=("JUPYTER_KERNEL (top of this script): a Jupyter kernel that runs PYTHON, see jupyter kernelspec list (EMST block_detection_irt)")
[ "$CPU_SET" = "SET_ME" ] && _unset+=("CPU_SET (top of this script): the taskset CPU list, e.g. 0-7; \"\" = no pinning (EMST 0-30)")
if [ ${#_unset[@]} -gt 0 ]; then printf 'settings check (submit_BDR_LVL2_notebooks_all.sh): %s setting(s) still hold "SET_ME". Set each, then run again (README, "Settings"):\n' "${#_unset[@]}"; printf '  - %s\n' "${_unset[@]}"; exit 1; fi

CODE="$PROJECT_ROOT/code/practical_application_generic"
LVL_OUTS="$PROJECT_ROOT/dervatives/practical_application_generic/lvl_outs"
LOGS="$LVL_OUTS/run_logs"
NOTEBOOKS=(block_detection_and_removal_LVL2_all_rep)
PIN=(); [ -n "$CPU_SET" ] && PIN=(taskset -c "$CPU_SET")
export PYTHONDONTWRITEBYTECODE=1
cd "$CODE" || exit 1
mkdir -p "$LOGS"

"$PYTHON" -B - "$LVL_OUTS" "${NOTEBOOKS[@]}" <<'EOF' || exit 1
import json, re, sys
from pathlib import Path
LVL_OUTS = Path(sys.argv[1])
bad = []
for nb in sys.argv[2:]:
    if not Path(f"{nb}.ipynb").is_file():
        bad.append(f"{nb}.ipynb not found: write it with build_level_scripts.py (README step 4)"); continue
    src = "".join(json.load(open(f"{nb}.ipynb"))["cells"][1]["source"])
    pins = dict(re.findall(r'^(LVL1_HANDOFF|LVL2_SWEEP)\s*=\s*"([^"]+)"', src, re.M))
    if len(pins) != 2:
        bad.append(f"{nb}: LVL1_HANDOFF / LVL2_SWEEP not set"); continue
    if not (LVL_OUTS / f"{pins['LVL1_HANDOFF']}_meta.json").is_file():
        bad.append(f"{nb}: handoff {pins['LVL1_HANDOFF']} not found in lvl_outs")
    sel = LVL_OUTS / f"{pins['LVL2_SWEEP']}_selection.json"
    if not sel.is_file():
        bad.append(f"{nb}: {sel.name} not found (run LVL2_sweep_report first)")
    elif json.load(open(sel))["lvl1_input"] != pins["LVL1_HANDOFF"]:
        bad.append(f"{nb}: {sel.name} was made on {json.load(open(sel))['lvl1_input']}, not {pins['LVL1_HANDOFF']}")
    print(f"{nb}: {pins}")
if bad:
    sys.exit("stopped before running:\n  " + "\n  ".join(bad))
EOF

STAMP=$(date +%Y%m%d_%H%M%S)
declare -A PID
for nb in "${NOTEBOOKS[@]}"; do
  ${PIN[@]+"${PIN[@]}"} "$PYTHON" -B -m nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.kernel_name="$JUPYTER_KERNEL" --ExecutePreprocessor.timeout=-1 \
    "${nb}.ipynb" > "$LOGS/run_${nb}_${STAMP}.log" 2>&1 &
  PID[$nb]=$!
  echo "$(date '+%F %T') started $nb (pid ${PID[$nb]}), log $LOGS/run_${nb}_${STAMP}.log"
done

FAILED=0
for nb in "${NOTEBOOKS[@]}"; do
  if wait "${PID[$nb]}"; then
    echo "$(date '+%F %T') finished $nb"
  else
    echo "$(date '+%F %T') FAILED $nb (see $LOGS/run_${nb}_${STAMP}.log)"; FAILED=1
  fi
done
# this run's tag lv2_out_<method>_all_<ts>: the newest one stamped at or after the run's start (STAMP); none after a failure
echo "run tag written:"
TAG=""
if [ "$FAILED" = 0 ]; then
  TAG=$(ls "$LVL_OUTS" | grep -oE "^lv2_out_[A-Za-z0-9_]+_all_[0-9]{8}_[0-9]{6}" | sort -u \
        | awk -v s="$STAMP" '{t = substr($0, length($0) - 14)} t >= s {print t, $0}' | sort | tail -1 | cut -d" " -f2)
fi
echo "${TAG:-none}"
exit $FAILED
