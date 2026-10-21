#!/usr/bin/env bash
# Repeated-measurement control (RQ1) and the RQ3 selection ablation, run in one session.
#   bash scripts/run_rq3_ablation.sh check     # committed code, unit tests (no API)
#   bash scripts/run_rq3_ablation.sh control   # RQ1 repeated-measurement control S1x2 (no API, ~5 min)
#   bash scripts/run_rq3_ablation.sh numeric   # D + uncertainty/random/sobol in this environment (no API, ~10 min)
#   bash scripts/run_rq3_ablation.sh llm       # A (named), B (anon), C (shuffled): 3 x 60 Claude calls (~30-40 min)
#   bash scripts/run_rq3_ablation.sh report    # results/summary/rq3_ablation.{md,json}
#   bash scripts/run_rq3_ablation.sh all       # all of the above, in this order
# Run every RQ3 stage in the SAME session: active-learning curves depend slightly on the CPU.
# The committed runs are in results/al_ablation/<condition>/nominal; a finished folder is never re-run,
# so a new run needs a fresh output folder (or delete the committed one first).
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0
STAGE="${1:-all}"
AL=(python scripts/run_al.py --pool results/pool --test results/test --seeds 10 --noise nominal --skip-rq1)

check() {
  if [ -n "$(git status --porcelain -- src scripts configs)" ]; then
    echo "ERROR: uncommitted changes in src/, scripts/ or configs/. Commit them first (runs record the code commit)."
    git status --short -- src scripts configs
    exit 1
  fi
  echo "code:  $(git rev-parse --short HEAD)"
  python -m pytest -q -m "not slow" tests/test_controls.py tests/test_ablation.py tests/test_llm.py
}

control() { python scripts/repeat_control.py; }

done_or_park() {   # 0 = finished earlier (skip); otherwise park an aborted attempt under results/al_ablation/_aborted/
  local d="results/al_ablation/$1/nominal"
  if [ -f "$d/al_curves.csv" ]; then echo "skip $1: already finished ($d). Delete that folder to run it again."; return 0; fi
  if [ -d "$d" ]; then
    local park="results/al_ablation/_aborted/$1-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$(dirname "$park")"; mv "$d" "$park"; echo "moved an unfinished attempt of $1 to $park"
  fi
  return 1
}

numeric() {
  done_or_park numeric || "${AL[@]}" --policies uncertainty random sobol top20_random --out results/al_ablation/numeric
}

llm() {
  python scripts/llm_check.py                       # one small call: key, model, structured output
  for v in named anon shuffled; do
    done_or_park "$v" || "${AL[@]}" --policies llm --llm-live --llm-variant "$v" --out "results/al_ablation/$v"
  done
}

report() { python scripts/rq3_ablation.py; }

case "$STAGE" in
  check) check ;;
  control) check; control ;;
  numeric) check; numeric ;;
  llm) check; llm ;;
  report) report ;;
  all) check; control; numeric; llm; report ;;
  *) echo "usage: bash scripts/run_rq3_ablation.sh [check|control|numeric|llm|report|all]"; exit 2 ;;
esac
