#!/usr/bin/env bash
# Runs the three LVL2 run notebooks (T2, T3, T2+T3) in parallel, each executed in place so the notebook keeps its outputs, and
# each on CPUs 0-30 (taskset; n_jobs 9 + 9 + 13). Run it inside tmux:
#   tmux new -s lvl2runs
#   bash /home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst/submit_BDR_LVL2_notebooks_all.sh
# Before running: set LVL1_HANDOFF and LVL2_SWEEP in each run notebook (n_jobs is set by build_level_scripts.py). The
# script stops first if a pin is unset, the handoff is missing, or the LVL2 sweep's selection was made on a different
# handoff.
# Logs: dervatives/practical_application_emst/lvl_outs/run_logs/run_<notebook>_<start time>.log
set -u
CODE=/home/sjsuss626/EMST_files/sjs_dissertation/code/practical_application_emst
LOGS=/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs/run_logs
NOTEBOOKS=(block_detection_and_removal_LVL2_T2_rep block_detection_and_removal_LVL2_T3_rep)
# the T2 + T3 run notebook
NOTEBOOKS+=(block_detection_and_removal_LVL2_T2+T3_rep)
export PYTHONDONTWRITEBYTECODE=1
cd "$CODE" || exit 1
mkdir -p "$LOGS"

/usr/bin/python3 -B - "${NOTEBOOKS[@]}" <<'EOF' || exit 1
import json, re, sys
from pathlib import Path
LVL_OUTS = Path("/home/sjsuss626/EMST_files/sjs_dissertation/dervatives/practical_application_emst/lvl_outs")
bad = []
for nb in sys.argv[1:]:
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
  taskset -c 0-30 /usr/bin/python3 -B -m nbconvert --to notebook --execute --inplace \
    --ExecutePreprocessor.kernel_name=block_detection_irt --ExecutePreprocessor.timeout=-1 \
    "${nb}.ipynb" > "$LOGS/run_${nb}_${STAMP}.log" 2>&1 &
  PID[$nb]=$!
  echo "$(date '+%F %T') started $nb (pid ${PID[$nb]}), log $LOGS/run_${nb}_${STAMP}.log"
  sleep 15            # staggered starts give each run its own run-tag second
done

FAILED=0
for nb in "${NOTEBOOKS[@]}"; do
  if wait "${PID[$nb]}"; then
    echo "$(date '+%F %T') finished $nb"
  else
    echo "$(date '+%F %T') FAILED $nb (see $LOGS/run_${nb}_${STAMP}.log)"; FAILED=1
  fi
done
# the newest run tag of each run notebook (run notebook block_detection_and_removal_LVL2_<run>_rep -> lv2_out_<method>_<run>_<ts>)
echo "run tags written:"
for nb in "${NOTEBOOKS[@]}"; do
  run=${nb#block_detection_and_removal_LVL2_}; run=${run%_rep}
  ls "$CODE/../../dervatives/practical_application_emst/lvl_outs" | grep -oE "^lv2_out_[A-Za-z_]+_${run//+/\\+}_[0-9]{8}_[0-9]{6}" | sort -u | tail -1
done
exit $FAILED
