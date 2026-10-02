"""Rebuild <out>/runs.csv from <out>/runs/*.json (e.g. after downloading GitHub Actions artifacts)."""
import json, sys
from pathlib import Path
import pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from sicsim.runner import flatten
out = Path(sys.argv[1])
rows = [flatten(json.load(open(p))) for p in sorted((out / "runs").glob("*.json")) if not p.name.endswith(".job.json")]
pd.DataFrame(rows).sort_values("run_id").to_csv(out / "runs.csv", index=False)
print(f"{len(rows)} runs -> {out / 'runs.csv'}")
