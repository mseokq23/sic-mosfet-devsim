"""Paper tables/figures from results/al*:  python scripts/summarize_results.py [--equal-budget-seeds 5]
Writes results/summary/: rq1.md, rq1_equal_budget.md, rq2.md, rq3.md, fig_rq1.png, fig_learning_curves.png"""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.analysis import add_noise, censor_floor, feature_set, fit_predict, metrics, wide_table
from sicsim.config import _Loader
from sicsim.design import VARS
ap = argparse.ArgumentParser(); ap.add_argument("--equal-budget-seeds", type=int, default=5); a = ap.parse_args()
R, OUT = ROOT / "results", ROOT / "results" / "summary"; OUT.mkdir(parents=True, exist_ok=True)
NZ = [n for n in ("none", "nominal", "high") if (R / "al" / n / "rq1_feature_sets.json").exists()]
TAG = {"wjfet_scale": "Wjfet", "npwell_scale": "Npwell", "qit_eff_cm2": "Qit_eff"}
# ---------------- RQ1
L = ["# RQ1: 300 K(S1) vs 300+423 K(S2/S3) — 테스트 128점 mae_norm (괄호: macro-F1)\n"]
rq1 = {n: json.load(open(R / "al" / n / "rq1_feature_sets.json")) for n in NZ}
for n in NZ:
    L += [f"\n## noise = {n}\n", "| 특징셋_모델 | 평균 | " + " | ".join(TAG.values()) + " |", "|---|---|---|---|---|"]
    for k in sorted(rq1[n], key=lambda s: (s.split("_")[1], s)):
        m = rq1[n][k]
        L.append(f"| {k} | {m['mean_mae_norm']:.4f} | " + " | ".join(f"{m[v]['mae_norm']:.4f} ({m[v]['macro_f1']:.2f})" for v in VARS) + " |")
    for mdl in ("gp", "et", "rf"):
        r = {v: rq1[n][f"S2_{mdl}"][v]["mae_norm"] / rq1[n][f"S1_{mdl}"][v]["mae_norm"] for v in VARS}
        L.append(f"\nS2/S1 ({mdl}): " + ", ".join(f"{TAG[v]} {x:.2f}" for v, x in r.items()))
(OUT / "rq1.md").write_text("\n".join(L) + "\n")
fig, axs = plt.subplots(1, len(NZ), figsize=(4.2 * len(NZ), 3.4), sharey=True)
for ax, n in zip(np.atleast_1d(axs), NZ):
    x = np.arange(3)
    for i, S in enumerate(("S1", "S2")):
        ax.bar(x + (i - 0.5) * 0.38, [rq1[n][f"{S}_gp"][v]["mae_norm"] for v in VARS], 0.38, label={"S1": "300 K", "S2": "300+423 K"}[S])
    ax.set_xticks(x); ax.set_xticklabels(TAG.values()); ax.set_title(f"noise = {n} (GP)"); ax.grid(alpha=0.3)
np.atleast_1d(axs)[0].set_ylabel("MAE / DOE range"); np.atleast_1d(axs)[0].legend(fontsize=8)
fig.tight_layout(); fig.savefig(OUT / "fig_rq1.png", dpi=150)
# ---------------- RQ1 at equal DEVSIM budget (S1: n points x 1 run, S2: n/2 points x 2 runs), GP, nominal
nzc = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)
pool = wide_table(pd.read_csv(R / "pool" / "runs.csv")).sort_index(); test = wide_table(pd.read_csv(R / "test" / "runs.csv"))
lv = nzc["levels"]["nominal"]; fl = nzc.get("current_floor_A_per_cm")
pool = censor_floor(add_noise(pool, nzc, lv, nzc["seeds"]["pool"]), fl); test = censor_floor(add_noise(test, nzc, lv, nzc["seeds"]["test"]), fl)
E = ["# RQ1 — 같은 DEVSIM 실행 수에서 비교 (GP, nominal, 시드 %d개 평균 mae_norm)\n" % a.equal_budget_seeds,
     "| DEVSIM run 수 | S1 (점 수) | S2 (점 수) | S1 평균 | S2 평균 | S1 Wjfet | S2 Wjfet |", "|---|---|---|---|---|---|---|"]
for budget in (120, 240, 480):
    res = {"S1": [], "S2": []}
    for s in range(a.equal_budget_seeds):
        rng = np.random.default_rng(1000 + s)
        for S, npts in (("S1", budget), ("S2", budget // 2)):
            idx = rng.choice(len(pool), npts, replace=False)
            P = fit_predict(feature_set(pool, S).values[idx], pool[VARS].values[idx], feature_set(test, S).values, "gp", s)
            res[S].append(metrics(test[VARS].values, P))
    mm = {S: np.mean([m["mean_mae_norm"] for m in res[S]]) for S in res}
    ww = {S: np.mean([m["wjfet_scale"]["mae_norm"] for m in res[S]]) for S in res}
    E.append(f"| {budget} | {budget} | {budget // 2} | {mm['S1']:.4f} | {mm['S2']:.4f} | {ww['S1']:.4f} | {ww['S2']:.4f} |")
(OUT / "rq1_equal_budget.md").write_text("\n".join(E) + "\n")
# ---------------- RQ2 (+ dry-run llm baseline)
Q = ["# RQ2: 정책 비교 (S2, RF 역추정, 초기 60점 + 10점 x 6라운드, 시드 10개)\n"]
fig, axs = plt.subplots(1, len(NZ), figsize=(4.2 * len(NZ), 3.4), sharey=False)
boot = np.random.default_rng(0)
for ax, n in zip(np.atleast_1d(axs), NZ):
    d = pd.read_csv(R / "al" / n / "al_curves.csv")
    meta = json.load(open(R / "al" / n / "meta.json")) if (R / "al" / n / "meta.json").exists() else {}
    piv = d.pivot_table(index=["policy", "seed"], columns="n_points", values="mean_mae_norm"); cols = sorted(d.n_points.unique())
    rnd = piv.loc["random"]; target = rnd[cols[-1]].mean()
    Q += [f"\n## noise = {n}  (llm 모드: {meta.get('llm_mode', 'dry-run(추정)')})\n",
          "| 정책 | 최종 mae_norm | random 대비 Δ [95% CI] | 승/10 | random 최종 오차 도달 점 수 |", "|---|---|---|---|---|"]
    for p in [q for q in ("random", "sobol", "uncertainty", "llm") if q in piv.index.get_level_values(0)]:
        m = piv.loc[p]; mean = m.mean(); ci = 1.96 * m.std() / np.sqrt(len(m))
        lab = p if p != "llm" or meta.get("llm_mode") == "live" else "llm(dry-run)"
        ax.plot(cols, mean.values, marker="o", ms=3, label=lab); ax.fill_between(cols, (mean - ci).values, (mean + ci).values, alpha=0.15)
        reach = next((cols[i - 1] + (cols[i] - cols[i - 1]) * (mean.iloc[i - 1] - target) / (mean.iloc[i - 1] - mean.iloc[i])
                      for i in range(1, len(cols)) if mean.iloc[i] <= target), None)
        if p == "random":
            Q.append(f"| {lab} | {m[cols[-1]].mean():.4f} ± {m[cols[-1]].std():.4f} | — | — | {cols[-1]} |")
            continue
        diff = (m[cols[-1]] - rnd[cols[-1]]).values
        bs = [boot.choice(diff, len(diff)).mean() for _ in range(5000)]; lo, hi = np.percentile(bs, [2.5, 97.5])
        Q.append(f"| {lab} | {m[cols[-1]].mean():.4f} ± {m[cols[-1]].std():.4f} | {diff.mean():+.4f} [{lo:+.4f}, {hi:+.4f}] | "
                 f"{int((diff < 0).sum())} | {f'{reach:.0f}' if reach else '미도달'} |")
    ax.set_title(f"noise = {n}"); ax.set_xlabel("process points (x2 runs)"); ax.grid(alpha=0.3)
np.atleast_1d(axs)[0].set_ylabel("mean MAE / range (test)"); np.atleast_1d(axs)[0].legend(fontsize=7)
fig.tight_layout(); fig.savefig(OUT / "fig_learning_curves.png", dpi=150)
(OUT / "rq2.md").write_text("\n".join(Q) + "\n")
# ---------------- RQ3 (live LLM log + paired comparison with the same seeds/initial sets)
from sicsim.summary import rq3_section

if __name__ == "__main__":
    (OUT / "rq3.md").write_text("\n".join(rq3_section(R)) + "\n")
    print("wrote", sorted(p.name for p in OUT.iterdir()))
