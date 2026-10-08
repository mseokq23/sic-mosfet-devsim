"""v4.8 additional comparisons from existing results (no DEVSIM runs), added after the manuscript review.
  python scripts/v48_extra_stats.py            -> results/summary/v48_extra_stats.{json,md}
1. 423 K physics scenarios against the repeat-measurement control S1x2 (GP, nominal noise, rho = 0):
   S2 with matched training, with nominal training (raw and with predictions clipped to the DOE box) and with
   mixed-physics training (all five assumptions, as scripts/robustness_mixed.py), paired bootstrap over the
   128 test points (same resampling as robust.evaluate and controls.paired_boot).
2. Equal DEVSIM budget with S1x2 added (the second 300 K measurement is a noise draw, so S1x2 costs one run per
   point like S1); 5 random subsets per budget as in scripts/summarize_results.py.
3. Seed-level statistics for RQ2/RQ3 (10 seeds): published bootstrap, t interval, exact sign-flip test,
   SD of the paired differences and the minimum detectable effect (paired t test, alpha 0.05, power 0.8).
Labels: everything here is post hoc (after the v4.7 results), reported as secondary analysis."""
import itertools, json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
from scipy import optimize, stats
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from sicsim.analysis import _lohi, add_noise, censor_floor, feature_set, fit_predict, wide_table
from sicsim.config import _Loader
from sicsim.controls import control_feature_set, noisy_tables, paired_boot
from sicsim.design import VARS, load_bounds
from sicsim.robust import combine_runs

OUT = ROOT / "results" / "summary"
NZ = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)
FL, LV = NZ.get("current_floor_A_per_cm"), NZ["levels"]["nominal"]
LO, HI = (np.asarray(x, float) for x in _lohi(load_bounds()))
SP, ST = NZ["seeds"]["pool"], NZ["seeds"]["test"]
R = lambda f: pd.read_csv(ROOT / "results" / f / "runs.csv")
BP, BT = R("pool"), R("test")
VAR = ["gamma0", "gamma_m1", "qitT10", "qitT30"]
TAG = {"wjfet_scale": "W_JFET", "npwell_scale": "N_pw", "qit_eff_cm2": "Q_it,eff"}


def noisy(runs, seed):
    return censor_floor(add_noise(wide_table(runs).sort_index(), NZ, LV, seed), FL)


def s2_errors(pool_runs, test_runs, clip=False):
    pool, test = noisy(pool_runs, SP), noisy(test_runs, ST)
    P = fit_predict(feature_set(pool, "S2").values, pool[VARS].values, feature_set(test, "S2").values, "gp", 0)
    if clip:
        P = np.clip(P, LO, HI)
    return pd.DataFrame(np.abs(P - test[VARS].values) / (HI - LO), index=test.index, columns=VARS)


def mixed_pool(names, seed=11):                                  # identical to scripts/robustness_mixed.py
    P = {"base": BP[BP.temperature_K == 423], **{v: R(f"pool_{v}") for v in VAR}}
    cids = sorted(BP.candidate_id.unique())
    pick = dict(zip(cids, np.random.default_rng(seed).choice(names, len(cids))))
    hi = pd.concat([P[n][P[n].candidate_id.map(pick) == n] for n in names])
    return pd.concat([BP[BP.temperature_K == 300], hi], ignore_index=True)


def contrast(a: pd.DataFrame, b: pd.DataFrame) -> dict:
    a, b = a.sort_index(), b.loc[a.sort_index().index]
    out = dict(mean=paired_boot(a.mean(axis=1).values, b.mean(axis=1).values))
    out.update({v: paired_boot(a[v].values, b[v].values) for v in VARS})
    return out


def part1():
    pts = pd.read_csv(OUT / "v47_repeat_control_points.csv")
    ref = {}
    for S in ("S1", "S1x2"):
        d = pts[(pts.level == "nominal") & (pts.rho == 0.0) & (pts.model == "gp") & (pts.set == S)]
        ref[S] = d.set_index("candidate_id")[[f"err_{v}" for v in VARS]].rename(columns=lambda c: c[4:])
    tests = {"base": BT, **{v: combine_runs(BT, R(f"test_{v}")) for v in VAR}}
    matched_pool = {"base": BP, **{v: combine_runs(BP, R(f"pool_{v}")) for v in VAR}}
    mix = mixed_pool(["base", *VAR])
    res = {}
    for name, T in tests.items():
        e = dict(matched=s2_errors(matched_pool[name], T), mixed=s2_errors(mix, T))
        if name != "base":
            e["nominal"] = s2_errors(BP, T)
            e["nominal_clipped"] = s2_errors(BP, T, clip=True)
        res[name] = {k: dict(mean=float(x.values.mean()), **{v: float(x[v].mean()) for v in VARS},
                             vs_S1x2=contrast(x, ref["S1x2"]), vs_S1=contrast(x, ref["S1"])) for k, x in e.items()}
        print(f"part1 {name}: " + ", ".join(f"{k} {r['mean']:.4f}" for k, r in res[name].items()), flush=True)
    ref_means = {S: dict(mean=float(x.values.mean()), **{v: float(x[v].mean()) for v in VARS}) for S, x in ref.items()}
    return dict(reference=ref_means, scenarios=res)


def part2(n_sub=5):
    pool_w, test_w = wide_table(BP).sort_index(), wide_table(BT).sort_index()
    p1, p2 = noisy_tables(pool_w, NZ, LV, SP, 0.0, 0.0, floor=FL, repeat_seed=SP + 1000)
    t1, t2 = noisy_tables(test_w, NZ, LV, ST, 0.0, 0.0, floor=FL, repeat_seed=ST + 1000)
    X = {S: (control_feature_set(p1, p2, S).values, control_feature_set(t1, t2, S).values) for S in ("S1", "S1x2", "S2")}
    out = {}
    for budget in (120, 240, 480):
        vals = {S: [] for S in ("S1", "S1x2", "S2")}
        for s in range(n_sub):                      # same subset draws as scripts/summarize_results.py; S1x2 uses the S1 points
            rng = np.random.default_rng(1000 + s)
            i1 = rng.choice(len(pool_w), budget, replace=False)
            i2 = rng.choice(len(pool_w), budget // 2, replace=False)
            for S, idx in (("S1", i1), ("S1x2", i1), ("S2", i2)):
                P = fit_predict(X[S][0][idx], pool_w[VARS].values[idx], X[S][1], "gp", s)
                vals[S].append(float((np.abs(P - test_w[VARS].values) / (HI - LO)).mean()))
        row = {S: dict(points=(budget // 2 if S == "S2" else budget), mean=float(np.mean(v)), sd=float(np.std(v, ddof=1)))
               for S, v in vals.items()}
        out[str(budget)] = row
        print(f"part2 budget {budget}: " + ", ".join(f"{S} {r['mean']:.4f}" for S, r in row.items()), flush=True)
    return out


def mde(sd, n=10, alpha=0.05, power=0.8):
    df, tc = n - 1, stats.t.ppf(1 - alpha / 2, n - 1)
    f = lambda d: stats.nct.sf(tc, df, d / (sd / np.sqrt(n))) - power      # lower tail is negligible for d > 0
    return float(optimize.brentq(f, 1e-9, 3 * sd))


def signflip(d):
    d = np.asarray(d); obs = abs(d.mean())
    vals = [abs((d * np.array(s)).mean()) >= obs - 1e-15 for s in itertools.product([1, -1], repeat=len(d))]
    return float(np.mean(vals))


def part3():
    from rq3_ablation import COND, boot, per_seed
    F, M = {}, {}
    for k in ("A", "A0", "B", "C", "D", "U", "sobol", "random"):
        F[k], M[k], _, _ = per_seed(*COND[k])
    pairs = [("U", "random"), ("sobol", "random"), ("U", "sobol"), ("A", "U"), ("A0", "U"), ("B", "U"), ("C", "U"), ("D", "U"),
             ("A0", "A"), ("B", "A"), ("C", "A"), ("A", "D"), ("C", "D")]
    out = {}
    for metric, src in (("final", F), ("rounds_1_6", M)):
        for a, b in pairs:
            d = (src[a] - src[b]).values
            bt = boot(d)
            t95 = stats.t.interval(0.95, len(d) - 1, loc=d.mean(), scale=stats.sem(d))
            t90 = stats.t.interval(0.90, len(d) - 1, loc=d.mean(), scale=stats.sem(d))
            sd = float(d.std(ddof=1))
            out[f"{metric}:{a}-{b}"] = dict(delta=float(d.mean()), boot95=bt["ci"], boot90=bt["ci90"], t95=list(map(float, t95)),
                                           t90=list(map(float, t90)), sd=sd, signflip_p=signflip(d), wins=int((d < 0).sum()),
                                           mde80=mde(sd), equivalent_boot90=bool(bt["ci90"][0] > -0.0025 and bt["ci90"][1] < 0.0025),
                                           equivalent_t90=bool(t90[0] > -0.0025 and t90[1] < 0.0025))
    return out


def report(res):
    f = lambda c: f"{c['delta']:+.4f} [{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}]"
    L = ["# v4.8 추가 비교 (사후 분석, 새 DEVSIM 계산 없음)\n",
         "기존 결과에서 다시 계산한 값이다. 모두 v4.7 결과를 본 뒤 원고 검토 과정에서 추가한 사후 분석이다.\n",
         "## 1. 423 K 물리 시나리오별 S2와 반복 측정 통제 S1×2 비교 (GP, nominal, ρ = 0, 시험 128점)\n",
         f"기준: S1 {res['part1']['reference']['S1']['mean']:.4f}, S1×2 {res['part1']['reference']['S1x2']['mean']:.4f} "
         "(300 K 특징만 쓰므로 모든 시나리오에서 같다). Δ = S2 − S1×2, 시험점 짝지은 부트스트랩 95% CI.\n",
         "| 시험 물리 | 학습 | S2 평균 | S2−S1×2 평균 | W_JFET (비) | N_pw (비) | Q_it,eff (비) |", "|---|---|---|---|---|---|---|"]
    for name, rows in res["part1"]["scenarios"].items():
        for k, r in rows.items():
            c = r["vs_S1x2"]
            L.append(f"| {name} | {k} | {r['mean']:.4f} | {f(c['mean'])} | " +
                     " | ".join(f"{f(c[v])} ({c[v]['ratio']:.2f})" for v in VARS) + " |")
    L += ["\n## 2. 같은 DEVSIM 실행 수 비교 (S1×2 추가, GP, nominal, 부분집합 5개 평균)\n",
          "S1×2의 두 번째 측정은 잡음 실현이므로 시뮬레이션 비용은 S1과 같다(점당 1회). S2는 점당 2회.\n",
          "| 실행 수 | S1 (점) | S1×2 (점) | S2 (점) |", "|---|---|---|---|"]
    for b, row in res["part2"].items():
        L.append(f"| {b} | " + " | ".join(f"{row[S]['mean']:.4f} ({row[S]['points']})" for S in ("S1", "S1x2", "S2")) + " |")
    L += ["\n## 3. 시드 수준 비교 (시드 10개): 부트스트랩·t 구간·부호 뒤집기 검정·최소 검출 효과\n",
          "MDE: 짝지은 t 검정(양측 α = 0.05, 검정력 0.8)으로 검출 가능한 최소 차이. 동등: 90% 구간이 ±0.0025 안.\n",
          "| 비교 | Δ | 부트스트랩 95% | t 95% | 부호 뒤집기 p | 우세/10 | SD | MDE | 동등(부트/t) |", "|---|---|---|---|---|---|---|---|---|"]
    for k, r in res["part3"].items():
        L.append(f"| {k} | {r['delta']:+.4f} | [{r['boot95'][0]:+.4f}, {r['boot95'][1]:+.4f}] | [{r['t95'][0]:+.4f}, {r['t95'][1]:+.4f}] | "
                 f"{r['signflip_p']:.3f} | {r['wins']} | {r['sd']:.4f} | {r['mde80']:.4f} | "
                 f"{'예' if r['equivalent_boot90'] else '아니오'}/{'예' if r['equivalent_t90'] else '아니오'} |")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    res = dict(note="post hoc secondary analysis for the v4.8 manuscript; no new DEVSIM runs",
               part1=part1(), part2=part2(), part3=part3())
    json.dump(res, open(OUT / "v48_extra_stats.json", "w"), indent=1)
    (OUT / "v48_extra_stats.md").write_text(report(res))
    print((OUT / "v48_extra_stats.md").read_text())
