"""RQ1-RQ3 on pre-simulated pool/test sets.
  python scripts/run_al.py --pool results/pool --test results/test --seeds 10
RQ1: inverse-model accuracy for S1 (300 K) / S2 (300+423 K) / S3 (S2 + T-differences), train=pool, test=test.
RQ2/3: pool-based retrospective active learning for each policy and seed.
LLM policy calls Claude only with --llm-live and ANTHROPIC_API_KEY set; otherwise the dry-run stand-in."""
import argparse, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.alsim import run_policy
import yaml
from sicsim.analysis import add_noise, feature_set, fit_predict, metrics, wide_table
from sicsim.config import _Loader
from sicsim.design import VARS
ap = argparse.ArgumentParser()
ap.add_argument("--pool", required=True); ap.add_argument("--test", required=True)
ap.add_argument("--out", default=str(ROOT / "results" / "al"))
ap.add_argument("--seeds", type=int, default=10); ap.add_argument("--n-init", type=int, default=60)
ap.add_argument("--batch", type=int, default=10); ap.add_argument("--rounds", type=int, default=6)
ap.add_argument("--set", default="S2"); ap.add_argument("--model", default="rf")
ap.add_argument("--policies", nargs="+", default=["random", "sobol", "uncertainty", "llm"])
ap.add_argument("--llm-live", action="store_true"); ap.add_argument("--llm-model", default="claude-sonnet-5-5")
ap.add_argument("--noise", default="nominal", help="none|low|nominal|high (configs/noise_model.yaml)")
a = ap.parse_args()
out = Path(a.out) / a.noise; out.mkdir(parents=True, exist_ok=True)
pool = wide_table(pd.read_csv(Path(a.pool) / "runs.csv")).sort_index()     # C0000.. = Sobol order
test = wide_table(pd.read_csv(Path(a.test) / "runs.csv"))
nz = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)
lv = nz["levels"][a.noise]
pool = add_noise(pool, nz, lv, nz["seeds"]["pool"]); test = add_noise(test, nz, lv, nz["seeds"]["test"])
print(f"noise={a.noise} (x{lv}, {nz['version']})")
rq1 = {}
for S in ("S1", "S2", "S3"):
    for kind in ("rf", "et", "gp"):
        P = fit_predict(feature_set(pool, S).values, pool[VARS].values, feature_set(test, S).values, kind)
        rq1[f"{S}_{kind}"] = metrics(test[VARS].values, P)
json.dump(rq1, open(out / "rq1_feature_sets.json", "w"), indent=1)
print({k: round(v["mean_mae_norm"], 4) for k, v in rq1.items()})
llm_cfg = dict(dry_run=not a.llm_live, model=a.llm_model)
curves = []
for pol in a.policies:
    for s in range(a.seeds):
        curves.append(run_policy(pool, test, pol, seed=s, n_init=a.n_init, batch=a.batch, rounds=a.rounds,
                                 set_name=a.set, model=a.model, llm_cfg=llm_cfg, llm_log=out / "llm_calls.jsonl"))
        print(pol, s, round(curves[-1].mean_mae_norm.iloc[-1], 4), flush=True)
pd.concat(curves).to_csv(out / "al_curves.csv", index=False)
