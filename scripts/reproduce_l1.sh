#!/usr/bin/env bash
# Reproduce the paper's tables and figures from the committed raw data (level L1: no DEVSIM, no API calls) in a
# throw-away git worktree of the current commit, then compare every regenerated file with the committed one.
#   bash scripts/reproduce_l1.sh             # analyses, summaries, figures, report   (about 10 min on one core)
#   bash scripts/reproduce_l1.sh --with-al   # + active-learning re-runs: run_al x 3 noise levels, al_ninit (+20 min)
#   KEEP=1 bash scripts/reproduce_l1.sh      # keep the worktree afterwards (its path is printed)
# Your working tree is not touched. Commit (or stash) local changes first: the worktree is made from HEAD.
set -euo pipefail
ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"
WITH_AL=0
[ "${1:-}" = "--with-al" ] && WITH_AL=1
export MKL_NUM_THREADS=1 OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1 PYTHONHASHSEED=0
WT="$(mktemp -d "${TMPDIR:-/tmp}/sicsim-l1-XXXXXX")"
git worktree add --detach "$WT" HEAD >/dev/null
cleanup() {
  if [ "${KEEP:-0}" = "1" ]; then echo "worktree kept: $WT  (remove later: git worktree remove --force $WT)"
  else git -C "$ROOT" worktree remove --force "$WT"; fi
}
trap cleanup EXIT
cd "$WT"
LOG="$WT/reproduce_l1.log"
CPU="$( (grep -m1 'model name' /proc/cpuinfo 2>/dev/null || echo ': unknown CPU') | cut -d: -f2 | sed 's/^ *//')"
echo "commit $(git rev-parse --short HEAD) · $CPU · log: $LOG"
step() {   # step <label> <command...>
  local label="$1"; shift; local t0=$SECONDS
  printf '  %-44s' "$label"
  if "$@" >>"$LOG" 2>&1; then echo "ok ($((SECONDS - t0)) s)"; else echo "FAILED, see $LOG"; KEEP=1; exit 1; fi
}
step "result audit"                 python scripts/audit_results.py results/pool configs/design_pool.csv results/test configs/design_test.csv
step "Stage A sensitivity (Table 1)" python scripts/stage_a_report.py results/stage_a_v11
step "local identifiability (CRB)"  python scripts/identifiability.py results/stage_a_v11
step "RQ1 ridge baseline"           python scripts/ridge_rq1.py
step "RQ1 repeated measurement S1x2" python scripts/repeat_control.py
step "robustness (Table 2)"         python scripts/robustness.py
step "mixed-physics training"       python scripts/robustness_mixed.py
step "post hoc comparisons (v4.8)"  python scripts/v48_extra_stats.py
step "RQ3 ablation summary (Table 3)" python scripts/rq3_ablation.py
if [ "$WITH_AL" = "1" ]; then
  for nz in none nominal high; do
    step "active learning, noise=$nz"  python scripts/run_al.py --pool results/pool --test results/test --seeds 10 --noise "$nz"
  done
  step "initial-set size (n_init 30/90)" python scripts/al_ninit.py --n-init 30 90 --seeds 10
fi
step "RQ1-RQ3 summaries"            python scripts/summarize_results.py
step "figures 1-2 and Table 1"      python scripts/make_paper_figures.py
step "figures 3-4 (V4.7-V4.9)"      python scripts/make_v47_figures.py
if [ -f scripts/make_report.py ]; then step "results report (HTML)" python scripts/make_report.py; fi
echo
echo "Regenerated files that differ from the committed versions:"
python scripts/compare_outputs.py results paper docs/report
cat <<'EOF'

How to read this: JSON/CSV numbers that differ only in the last digits (max |Δ| below 1e-6) are floating-point
differences between CPUs; the Markdown summaries and every number quoted in the paper should be unchanged apart
from header lines naming the code commit or CPU. Active-learning curves (--with-al) depend on the CPU from
round 1: random and Sobol policies reproduce exactly, the uncertainty and LLM-dry-run policies only on the CPU
type used for the paper runs (AMD EPYC 7763, GitHub Codespaces). Figures differ in bytes when fonts differ.
EOF
