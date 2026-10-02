#!/usr/bin/env bash
# Runs once when the Codespace is created.  NOTE: `pip install devsim` alone fails at import
# ("Error loading math libraries") -> mkl is pinned in requirements.txt.
set -euo pipefail
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
python scripts/gate0_check.py || echo "WARNING: gate0 check failed - see output above"
bash scripts/lock_env.sh
