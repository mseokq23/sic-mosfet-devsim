#!/usr/bin/env bash
# Environment lock written next to every result set (draft reproducibility checklist).
{
  python --version
  python -c "import platform; print(platform.platform())"
  python -c "import devsim; i=devsim.get_parameter(name='info'); print('devsim', i.get('version'), i.get('direct_solver'), i.get('math_libraries'))"
  git rev-parse HEAD 2>/dev/null || echo "no-git"
  pip freeze
} > environment.txt
echo "wrote environment.txt"
