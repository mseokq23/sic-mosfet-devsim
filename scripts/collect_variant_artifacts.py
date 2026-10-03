"""Move downloaded robustness artifacts (<dir>/rob-<variant>-<pool|test>-<shard>/) into
results/<design>_<variant>/runs/ and rebuild runs.csv; prints convergence counts."""
import re, shutil, subprocess, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]
src = Path(sys.argv[1] if len(sys.argv) > 1 else "artifacts")
pat = re.compile(r"^rob-(?P<variant>[A-Za-z0-9_]+)-(?P<design>pool|test)-(?P<shard>\d+)$")
outs = set()
for d in sorted(p for p in src.iterdir() if p.is_dir()):
    m = pat.match(d.name)
    if not m:
        print("skip", d.name); continue
    dst = ROOT / "results" / f"{m['design']}_{m['variant']}" / "runs"; dst.mkdir(parents=True, exist_ok=True)
    for f in d.rglob("*.json"):
        if not f.name.endswith(".job.json"):
            shutil.copy2(f, dst / f.name)
    outs.add(dst.parent)
for o in sorted(outs):
    subprocess.run([sys.executable, str(ROOT / "scripts" / "merge_runs.py"), str(o)], check=True)
    r = pd.read_csv(o / "runs.csv"); ok = (r["converged"].astype(str).str.lower() == "true").sum()
    print(f"{o.name}: {ok}/{len(r)} converged; physics_hash={sorted(r['physics_hash'].dropna().unique()) if 'physics_hash' in r else '?'}")
