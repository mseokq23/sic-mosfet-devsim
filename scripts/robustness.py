"""Robustness of the multi-temperature gain (pre-registered in docs/PREDICTIONS_ROBUSTNESS.md).
  in-model : train/test both from variant physics (300 K baseline + 423 K variant)
  out-model: train on the frozen baseline, test on variant physics or with a parasitic series resistance
  python scripts/robustness.py [--model gp|ridge] [--levels nominal high]
-> results/summary/robustness.json, robustness.md"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import _Loader
from sicsim.robust import apply_series_resistance, combine_runs, evaluate

VARIANTS = {"gamma0": "μ_surf 지수 0", "gamma_m1": "μ_surf 지수 −1", "qitT10": "|Q_it| −10% @423 K", "qitT30": "|Q_it| −30% @423 K"}
RHO_RANGE = (0.1, 0.3)          # mOhm*cm^2, device-specific parasitic series resistance (~5-15% of Ron,sp at 300 K)

ap = argparse.ArgumentParser(); ap.add_argument("--model", default="gp"); ap.add_argument("--levels", nargs="+", default=["nominal", "high"])
a = ap.parse_args()
nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)
R = lambda f: pd.read_csv(ROOT / "results" / f / "runs.csv")
bpool, btest = R("pool"), R("test")
avail = [v for v in VARIANTS if (ROOT / f"results/pool_{v}/runs.csv").exists() and (ROOT / f"results/test_{v}/runs.csv").exists()]
rng = np.random.default_rng(2026)
rho = dict(zip(sorted(btest["candidate_id"].unique()), rng.uniform(*RHO_RANGE, btest["candidate_id"].nunique())))
btest_rs = apply_series_resistance(btest, ROOT / "results/test/runs", rho)

out = dict(model=a.model, variants=avail, rho_range_mohm_cm2=RHO_RANGE, levels={})
for lv in a.levels:
    rows = {"baseline (in-model)": evaluate(bpool, btest, nz, lv, a.model)}
    for v in avail:
        vp, vt = R(f"pool_{v}"), R(f"test_{v}")
        rows[f"{v} in-model"] = evaluate(combine_runs(bpool, vp), combine_runs(btest, vt), nz, lv, a.model)
        rows[f"{v} out-of-model"] = evaluate(bpool, combine_runs(btest, vt), nz, lv, a.model)
    rows["series-R out-of-model"] = evaluate(bpool, btest_rs, nz, lv, a.model)
    out["levels"][lv] = rows
    print(f"[{lv}]"); [print(f"  {k:28s} S1 {r['S1']['mean']:.4f}  S2 {r['S2']['mean']:.4f}  gain {100*r['rel_gain']:+.1f}%  "
                            f"d {r['delta']:+.4f} [{r['ci'][0]:+.4f},{r['ci'][1]:+.4f}]  n={r['n_pool']}/{r['n_test']}") for k, r in rows.items()]
(ROOT / "results/summary").mkdir(parents=True, exist_ok=True)
json.dump(out, open(ROOT / "results/summary/robustness.json", "w"), indent=1)
L = [f"# Robustness of the 423 K gain (model={a.model}; MAE/range, test 128 pts)\n",
     f"Variants available: {', '.join(avail) or '(none yet)'}; series R ~ U{RHO_RANGE} mOhm·cm² per device (out-of-model only).\n"]
for lv, rows in out["levels"].items():
    L += [f"\n## noise: {lv}\n", "| scenario | S1 | S2 | gain | S2−S1 [95% CI] | W_JFET S1→S2 | N_pw S1→S2 | Q_it S1→S2 | n (train/test) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, r in rows.items():
        t = lambda v: f"{r['S1'][v]:.3f}→{r['S2'][v]:.3f}"
        L.append(f"| {k} | {r['S1']['mean']:.4f} | {r['S2']['mean']:.4f} | {100*r['rel_gain']:+.1f}% | {r['delta']:+.4f} [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}] | "
                 f"{t('wjfet_scale')} | {t('npwell_scale')} | {t('qit_eff_cm2')} | {r['n_pool']}/{r['n_test']} |")
open(ROOT / "results/summary/robustness.md", "w").write("\n".join(L) + "\n")
print("-> results/summary/robustness.json, robustness.md")
