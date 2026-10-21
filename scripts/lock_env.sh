#!/usr/bin/env bash
# Environment lock (package versions, DEVSIM solver, code commit).
#   bash scripts/lock_env.sh                        -> environment.txt (the committed record of the paper runs)
#   bash scripts/lock_env.sh environment.local.txt  -> a local record that git ignores
OUT="${1:-environment.txt}"
{
  python --version
  python -c "import platform; print(platform.platform())"
  python -c "import devsim; i=devsim.get_parameter(name='info'); print('devsim', i.get('version'), i.get('direct_solver'), i.get('math_libraries'))"
  git rev-parse HEAD 2>/dev/null || echo "no-git"
  pip freeze
} > "$OUT"
echo "wrote $OUT"
