"""EXPLORATORY (post hoc, not pre-registered): train on a pool whose 423 K physics is drawn at random from
several variants (uncertain temperature physics treated as a nuisance) and test on each variant.
  python scripts/robustness_mixed.py  -> results/summary/robustness_mixed.{json,md}
(Table 2 of the paper is drawn by scripts/make_paper_figures.py from results/summary/posthoc_stats.json.)"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import _Loader
from sicsim.robust import combine_runs, evaluate

nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)
R = lambda f: pd.read_csv(ROOT / "results" / f / "runs.csv")
bp, bt = R("pool"), R("test")
VARS_ = ["gamma0", "gamma_m1", "qitT10", "qitT30"]
P = {"base": bp[bp.temperature_K == 423], **{v: R(f"pool_{v}") for v in VARS_}}
T = {"base": bt, **{v: combine_runs(bt, R(f"test_{v}")) for v in VARS_}}
FAMILIES = {"gamma-mixed": ["base", "gamma0", "gamma_m1"], "qit-mixed": ["base", "qitT10", "qitT30"],
            "all-mixed": ["base", "gamma0", "gamma_m1", "qitT10", "qitT30"]}
SEED = 11


def mixed_pool(names):
    cids = sorted(bp.candidate_id.unique())
    pick = dict(zip(cids, np.random.default_rng(SEED).choice(names, len(cids))))
    hi = pd.concat([P[n][P[n].candidate_id.map(pick) == n] for n in names])
    return pd.concat([bp[bp.temperature_K == 300], hi], ignore_index=True), pd.Series(pick).value_counts().to_dict()


out = dict(note="exploratory, post hoc", seed=SEED, levels={})
for lv in ("nominal", "high"):
    rows = {}
    for fam, names in FAMILIES.items():
        pool, counts = mixed_pool(names)
        for tn in names:
            r = evaluate(pool, T[tn], nz, lv, "gp"); r["train_counts"] = {str(k): int(v) for k, v in counts.items()}
            rows[f"{fam} -> {tn}"] = r
            print(f"[{lv}] {fam:12s} -> {tn:9s} S1 {r['S1']['mean']:.4f} S2 {r['S2']['mean']:.4f} gain {100*r['rel_gain']:+.1f}%", flush=True)
    out["levels"][lv] = rows
(ROOT / "results/summary").mkdir(parents=True, exist_ok=True)
json.dump(out, open(ROOT / "results/summary/robustness_mixed.json", "w"), indent=1)

L = ["# Exploratory: training over mixed 423 K physics (post hoc, GP, MAE/range)\n"]
for lv, rows in out["levels"].items():
    L += [f"\n## noise: {lv}\n", "| train mix -> test | S1 | S2 | gain | S2−S1 [95% CI] |", "|---|---|---|---|---|"]
    L += [f"| {k} | {r['S1']['mean']:.4f} | {r['S2']['mean']:.4f} | {100*r['rel_gain']:+.1f}% | {r['delta']:+.4f} [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}] |" for k, r in rows.items()]
open(ROOT / "results/summary/robustness_mixed.md", "w").write("\n".join(L) + "\n")
print(open(ROOT / "results/summary/robustness_mixed.md").read())
