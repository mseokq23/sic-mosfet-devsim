"""Gate 3: 2D half-cell DMOSFET - mesh independence (3 levels), precision, temperature, repeatability.
Each case runs in an isolated process (python -m sicsim.worker)."""
import json, os, subprocess, sys, time
from pathlib import Path
import numpy as np
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "pretest" / "gate3"
OUT.mkdir(parents=True, exist_ok=True)
env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "MKL_NUM_THREADS": "1", "OMP_NUM_THREADS": "1"}
cases = [
    ("ms2.0_dp_300", dict(temperature_K=300, mesh_scale=2.0, extended=False)),
    ("ms1.5_dp_300", dict(temperature_K=300, mesh_scale=1.5, extended=False)),
    ("ms1.0_dp_300", dict(temperature_K=300, mesh_scale=1.0, extended=False)),
    ("ms1.5_dp_423", dict(temperature_K=423, mesh_scale=1.5, extended=False)),
    ("ms1.5_dp_300_rep", dict(temperature_K=300, mesh_scale=1.5, extended=False)),
    ("ms1.5_xp_300", dict(temperature_K=300, mesh_scale=1.5, extended=True, output_curve=False)),
]
only = sys.argv[1:]
for name, kw in cases:
    if only and name not in only:
        continue
    res = OUT / f"{name}.json"
    if res.exists():
        print("skip", name); continue
    job = OUT / f"{name}.job.json"
    json.dump(dict(run_id=name, wjfet_scale=1.0, npwell_scale=1.0, qit_eff_cm2=None, **kw), open(job, "w"))
    t0 = time.time()
    p = subprocess.run([sys.executable, "-m", "sicsim.worker", str(job), str(res)], env=env,
                       capture_output=True, text=True)
    if p.returncode != 0:
        print(name, "WORKER ERROR", p.stderr[-1500:]); continue
    r = json.load(open(res))
    f = r["features"]
    print(f"{name}: conv={r['converged']} nodes={r.get('n_nodes')} t={r['runtime_s']:.0f}s solves={r['n_solves']} "
          f"fail={r['n_fail']} err={r['error_code']}", flush=True)
    if f:
        print("   " + ", ".join(f"{k}={v:.4g}" for k, v in f.items() if isinstance(v, float) and not k.startswith("logid")), flush=True)
