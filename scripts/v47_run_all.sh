#!/usr/bin/env bash
# v4.7 control experiments (plan: docs/PREDICTIONS_V47.md, steps: docs/V47_RUNBOOK.md)
#   bash scripts/v47_run_all.sh check     # branch, committed plan/code, unit tests (no API)
#   bash scripts/v47_run_all.sh control   # RQ1 repeated-measurement control S1x2 (no API, ~5 min)
#   bash scripts/v47_run_all.sh numeric   # RQ3 D + uncertainty/random/sobol in this environment (no API, ~10 min)
#   bash scripts/v47_run_all.sh llm       # RQ3 A (named), B (anon), C (shuffled): 3 x 60 Claude calls (~30 min)
#   bash scripts/v47_run_all.sh report    # summaries in results/summary/v47_*
#   bash scripts/v47_run_all.sh all       # all of the above, in this order
# Run every RQ3 stage in the SAME codespace session: active-learning curves depend slightly on the CPU.
set -euo pipefail
cd "$(git rev-parse --show-toplevel)"
export MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0
STAGE="${1:-all}"
AL=(python scripts/run_al.py --pool results/pool --test results/test --seeds 10 --noise nominal --skip-rq1)

check() {
  local branch; branch=$(git rev-parse --abbrev-ref HEAD)
  [ "$branch" = "exp/v4.7-controls" ] || echo "WARNING: current branch is $branch (expected exp/v4.7-controls)"
  if [ -n "$(git status --porcelain -- src scripts configs docs/PREDICTIONS_V47.md)" ]; then
    echo "ERROR: uncommitted changes in src/, scripts/, configs/ or the plan. Commit them first (the plan must be committed before running)."
    git status --short -- src scripts configs docs/PREDICTIONS_V47.md
    exit 1
  fi
  echo "plan:  $(git log -1 --format='%h %ci' -- docs/PREDICTIONS_V47.md)"
  echo "code:  $(git rev-parse --short HEAD)"
  python -m pytest -q -m "not slow" tests/test_v47_controls.py tests/test_v47_ablation.py tests/test_llm.py
}

control() { python scripts/repeat_control.py; }

done_or_park() {   # 0 = finished earlier (skip); otherwise park an aborted attempt under results/al_v47/_aborted/
  local d="results/al_v47/$1/nominal"
  if [ -f "$d/al_curves.csv" ]; then echo "skip $1: already finished ($d). Delete that folder to run it again."; return 0; fi
  if [ -d "$d" ]; then
    local park="results/al_v47/_aborted/$1-$(date -u +%Y%m%dT%H%M%SZ)"
    mkdir -p "$(dirname "$park")"; mv "$d" "$park"; echo "moved an unfinished attempt of $1 to $park"
  fi
  return 1
}

numeric() {
  done_or_park numeric || "${AL[@]}" --policies uncertainty random sobol top20_random --out results/al_v47/numeric
}

llm() {
  python scripts/llm_check.py                       # one small call: key, model, structured output
  for v in named anon shuffled; do
    done_or_park "$v" || "${AL[@]}" --policies llm --llm-live --llm-variant "$v" --out "results/al_v47/$v"
  done
}

report() {
  python scripts/rq3_ablation.py
  echo
  echo "Next: git add results/al_v47 results/summary/v47_* && git commit -m 'v4.7 control results' && git push"
}

case "$STAGE" in
  check) check ;;
  control) check; control ;;
  numeric) check; numeric ;;
  llm) check; llm ;;
  report) report ;;
  all) check; control; numeric; llm; report ;;
  *) echo "usage: bash scripts/v47_run_all.sh [check|control|numeric|llm|report|all]"; exit 2 ;;
esac
