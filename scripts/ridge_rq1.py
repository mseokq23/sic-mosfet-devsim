"""RQ1 with a linear ridge-regression inverse baseline (S1/S2/S3 x noise levels) -> results/summary/ridge_rq1.json"""
import json, sys
from pathlib import Path
import pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.analysis import add_noise, censor_floor, feature_set, fit_predict, metrics, wide_table
from sicsim.config import _Loader
from sicsim.design import VARS
nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader); fl = nz.get("current_floor_A_per_cm")
pool0 = wide_table(pd.read_csv(ROOT / "results/pool/runs.csv")).sort_index(); test0 = wide_table(pd.read_csv(ROOT / "results/test/runs.csv"))
out = {}
for lv in ("none", "nominal", "high"):
    pool = censor_floor(add_noise(pool0, nz, nz["levels"][lv], nz["seeds"]["pool"]), fl)
    test = censor_floor(add_noise(test0, nz, nz["levels"][lv], nz["seeds"]["test"]), fl)
    for S in ("S1", "S2", "S3"):
        m = metrics(test[VARS].values, fit_predict(feature_set(pool, S).values, pool[VARS].values, feature_set(test, S).values, "ridge", 0))
        out[f"{lv}_{S}"] = dict(mean=m["mean_mae_norm"], **{v: m[v]["mae_norm"] for v in VARS})
        print(lv, S, round(m["mean_mae_norm"], 4))
json.dump(out, open(ROOT / "results/summary/ridge_rq1.json", "w"), indent=1)
