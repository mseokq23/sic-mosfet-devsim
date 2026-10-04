"""EXPLORATORY (post hoc, not pre-registered): train on a pool whose 423 K physics is drawn at random from
several variants (uncertain temperature physics treated as a nuisance) and test on each variant.
  python scripts/robustness_mixed.py  -> results/summary/robustness_mixed.{json,md}, paper/tables/table2_robustness.{md,csv}"""
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

# Table 2 of the paper (nominal noise): same-physics / baseline-trained / mixture-trained S2 error
rb = json.load(open(ROOT / "results/summary/robustness.json"))["levels"]["nominal"]
mx = out["levels"]["nominal"]
lab = {"base": "기준(γ = +1, 정적 Q_it)", "gamma0": "γ = 0", "gamma_m1": "γ = −1", "qitT10": "Q_it 크기 −10% @423 K", "qitT30": "Q_it 크기 −30% @423 K"}
t2 = []
for k in ["base", *VARS_]:
    same = rb["baseline (in-model)"] if k == "base" else rb[f"{k} in-model"]
    oom = None if k == "base" else rb[f"{k} out-of-model"]
    t2.append(dict(scenario=lab[k], same_physics=same["S2"]["mean"], baseline_trained=None if oom is None else oom["S2"]["mean"],
                   mixture_trained=mx[f"all-mixed -> {k}"]["S2"]["mean"], s1=same["S1"]["mean"]))
sr = rb["series-R out-of-model"]
t2.append(dict(scenario="기생 직렬저항 (탐색적)", same_physics=None, baseline_trained=sr["S2"]["mean"], mixture_trained=None, s1=sr["S1"]["mean"]))
df = pd.DataFrame(t2); (ROOT / "paper/tables").mkdir(parents=True, exist_ok=True)
df.to_csv(ROOT / "paper/tables/table2_robustness.csv", index=False)
f = lambda x: "—" if x is None or pd.isna(x) else f"{x:.3f}"
md = ["| 423 K 물리 | 같은 물리로 학습 | 기준 물리로 학습 | 가정 혼합 학습 | S1 |", "|---|---|---|---|---|"]
md += [f"| {r.scenario} | {f(r.same_physics)} | {f(r.baseline_trained)} | {f(r.mixture_trained)} | {f(r.s1)} |" for r in df.itertuples()]
open(ROOT / "paper/tables/table2_robustness.md", "w").write("\n".join(md) + "\n")
L = ["# Exploratory: training over mixed 423 K physics (post hoc, GP, MAE/range)\n"]
for lv, rows in out["levels"].items():
    L += [f"\n## noise: {lv}\n", "| train mix -> test | S1 | S2 | gain | S2−S1 [95% CI] |", "|---|---|---|---|---|"]
    L += [f"| {k} | {r['S1']['mean']:.4f} | {r['S2']['mean']:.4f} | {100*r['rel_gain']:+.1f}% | {r['delta']:+.4f} [{r['ci'][0]:+.4f}, {r['ci'][1]:+.4f}] |" for k, r in rows.items()]
open(ROOT / "results/summary/robustness_mixed.md", "w").write("\n".join(L) + "\n")
print(open(ROOT / "paper/tables/table2_robustness.md").read())
