"""Active-learning sensitivity to the initial random-set size (random / sobol / uncertainty, nominal noise, S2, RF).
  python scripts/al_ninit.py --n-init 30 90 --seeds 10     (n_init=60 is taken from results/al/nominal)
-> results/summary/al_ninit_curves.csv, al_ninit_summary.csv"""
import argparse, os, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.analysis import add_noise, censor_floor, wide_table
from sicsim.alsim import run_policy
from sicsim.config import _Loader
ap = argparse.ArgumentParser(); ap.add_argument("--n-init", type=int, nargs="+", default=[30, 90]); ap.add_argument("--seeds", type=int, default=10)
a = ap.parse_args()
nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader); fl = nz.get("current_floor_A_per_cm"); lv = nz["levels"]["nominal"]
pool = censor_floor(add_noise(wide_table(pd.read_csv(ROOT / "results/pool/runs.csv")).sort_index(), nz, lv, nz["seeds"]["pool"]), fl)
test = censor_floor(add_noise(wide_table(pd.read_csv(ROOT / "results/test/runs.csv")), nz, lv, nz["seeds"]["test"]), fl)
curves = []
for n0 in a.n_init:
    for s in range(a.seeds):
        for pol in ("random", "sobol", "uncertainty"):
            df = run_policy(pool, test, pol, seed=s, n_init=n0, batch=10, rounds=6, set_name="S2", model="rf"); df["n_init"] = n0; curves.append(df)
        print(f"n_init={n0} seed={s}", flush=True)
d = pd.concat(curves)
b = pd.read_csv(ROOT / "results/al/nominal/al_curves.csv"); b = b[b.policy.isin(["random", "sobol", "uncertainty"])].copy(); b["n_init"] = 60
d = pd.concat([d, b[d.columns]]); d.to_csv(ROOT / "results/summary/al_ninit_curves.csv", index=False)
rng, rows = np.random.default_rng(5), []
for n0, g in d.groupby("n_init"):
    last = g.n_points.max(); fin = g[g.n_points == last].pivot_table(index="seed", columns="policy", values="mean_mae_norm")
    piv = g.pivot_table(index=["policy", "seed"], columns="n_points", values="mean_mae_norm"); cols = sorted(g.n_points.unique()); tgt = fin["random"].mean()
    for p in ("sobol", "uncertainty"):
        m = piv.loc[p].mean(); r = next((cols[i-1] + (cols[i]-cols[i-1]) * (m.iloc[i-1]-tgt) / (m.iloc[i-1]-m.iloc[i]) for i in range(1, len(cols)) if m.iloc[i] <= tgt), None)
        dd = (fin[p] - fin["random"]).values; lo, hi = np.percentile(rng.choice(dd, (10000, len(dd))).mean(1), [2.5, 97.5])
        rows.append(dict(n_init=n0, final_n=last, policy=p, random_final=tgt, delta=dd.mean(), ci_lo=lo, ci_hi=hi, wins=int((dd < 0).sum()),
                         reach_n=r, saving_pct=None if r is None else 100 * (last - r) / last))
pd.DataFrame(rows).to_csv(ROOT / "results/summary/al_ninit_summary.csv", index=False); print(pd.DataFrame(rows).round(4).to_string(index=False))
