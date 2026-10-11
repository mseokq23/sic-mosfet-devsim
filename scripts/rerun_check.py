"""Re-simulate a few stored DEVSIM runs and compare them with the committed raw data (reproduction level L2).
  python scripts/rerun_check.py                                   # T0000 of the test set, 300 and 423 K (~1 min with 2 cores)
  python scripts/rerun_check.py --ids T0000 T0005 --jobs 2
  python scripts/rerun_check.py --set results/test_gamma0 --config configs/variants/gamma0.yaml --temps 423
The runs are written to a temporary folder (nothing under results/ changes). Reports whether the physics, solver and
mesh hashes match and the largest relative difference of the extracted features and of the I-V curves.
Exit code 1 if a hash differs or a feature differs by more than --tol (default 1e-9)."""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def rel(a, b):
    a, b = np.asarray(a, float), np.asarray(b, float)
    if a.shape != b.shape:
        return float("inf")
    den = np.maximum(np.abs(a), np.abs(b))
    with np.errstate(divide="ignore", invalid="ignore"):
        r = np.where(den > 0, np.abs(a - b) / den, 0.0)
    return float(np.max(r)) if r.size else 0.0


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--set", default="results/test", help="stored result set (folder with runs/*.json)")
    ap.add_argument("--design", default=None, help="design CSV (default: configs/design_<test|pool>.csv from --set)")
    ap.add_argument("--ids", nargs="+", default=["T0000"], help="candidate ids to re-simulate")
    ap.add_argument("--temps", type=float, nargs="+", default=[300, 423])
    ap.add_argument("--config", default=None, help="variant config YAML (robustness sets)")
    ap.add_argument("--jobs", type=int, default=2)
    ap.add_argument("--tol", type=float, default=1e-9)
    a = ap.parse_args()

    store = ROOT / a.set
    design = Path(a.design) if a.design else ROOT / "configs" / ("design_pool.csv" if "pool" in store.name else "design_test.csv")
    d = pd.read_csv(design)
    d = d[d.candidate_id.isin(a.ids)]
    if d.empty:
        sys.exit(f"none of {a.ids} found in {design}")
    with tempfile.TemporaryDirectory(prefix="rerun_") as tmp:
        tmp = Path(tmp)
        d.to_csv(tmp / "design.csv", index=False)
        cmd = [sys.executable, "-m", "sicsim.runner", str(tmp / "design.csv"), "--out", str(tmp / "out"), "--jobs", str(a.jobs),
               "--temps", *[str(t) for t in a.temps]] + (["--config", a.config] if a.config else [])
        env = dict(os.environ, MKL_NUM_THREADS="1", OMP_NUM_THREADS="1")
        env["PYTHONPATH"] = str(ROOT / "src") + os.pathsep + env.get("PYTHONPATH", "")
        print("running:", " ".join(cmd[1:]), flush=True)
        subprocess.run(cmd, cwd=ROOT, env=env, check=True)
        rows, bad = [], False
        for p in sorted((tmp / "out" / "runs").glob("*.json")):
            q = store / "runs" / p.name
            if not q.exists():
                print(f"{p.name}: no stored run in {store}/runs"); bad = True; continue
            new, old = json.load(open(p)), json.load(open(q))
            hashes = all(new.get(h) == old.get(h) for h in ("physics_hash", "solver_hash", "mesh_hash"))
            fk = [k for k, v in old["features"].items() if isinstance(v, float) and isinstance(new["features"].get(k), float)]
            fr = max((rel(old["features"][k], new["features"][k]) for k in fk), default=0.0)
            tr = rel(old["curves"]["transfer"]["id"], new["curves"]["transfer"]["id"])
            orr = rel(old["curves"]["output"]["id"], new["curves"]["output"]["id"])
            ok = hashes and new.get("converged") and fr <= a.tol
            bad |= not ok
            rows.append(dict(run=p.stem, hashes="same" if hashes else "DIFFERENT", converged=new.get("converged"),
                             max_feature_rel=f"{fr:.1e}", transfer_rel=f"{tr:.1e}", output_rel=f"{orr:.1e}",
                             vth_V=f"{new['features'].get('vth_V', float('nan')):.6f}", result="OK" if ok else "CHECK"))
        print(pd.DataFrame(rows).to_string(index=False))
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
