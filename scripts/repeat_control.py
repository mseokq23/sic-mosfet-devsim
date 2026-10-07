"""v4.7 repeated-measurement control for RQ1 (analysis plan: docs/PREDICTIONS_V47.md). No DEVSIM runs.
  python scripts/repeat_control.py                       # full plan (about 5 min on 1 core)
  python scripts/repeat_control.py --blind               # write outputs, print only reproduction checks
Feature sets (GP and Ridge inverse models, train = pool 512, test = 128):
  S1 (300 K), S1x2 (300 K measured twice, averaged) [primary control], S1x2cat (both repeats side by side),
  S2 (300 + 423 K), S3 (S2 + differences).
Noise: frozen noise-v1.1; the second 300 K realisation uses seed + 1000 (pool 1101, test 1202).
rho: correlation between the two measurements of a device (300/423 K for S2, 300/300 K for S1x2).
-> results/summary/v47_repeat_control.json, v47_repeat_control.md, v47_repeat_control_points.csv"""
import argparse, datetime as dt, json, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT / "scripts"))
from sicsim.analysis import _lohi, fit_predict, wide_table
from sicsim.config import _Loader
from sicsim.controls import compute_env, control_feature_set, noisy_tables, paired_boot, replicate_seeds
from sicsim.design import VARS, load_bounds
from sicsim.robust import apply_series_resistance

SETS = ["S1", "S1x2", "S1x2cat", "S2", "S3"]
CONTRASTS = [("S2", "S1x2"), ("S1x2", "S1"), ("S2", "S1"), ("S2", "S1x2cat"), ("S1x2cat", "S1x2"), ("S3", "S2")]
TAG = {"wjfet_scale": "W_JFET", "npwell_scale": "N_pw", "qit_eff_cm2": "Q_it,eff"}
PUBLISHED = {"S1": 0.112275, "S2": 0.072011, "ci": (-0.049, -0.031), "series_S1": 0.378, "series_S2": 0.261}
RHO_RANGE, RHO_SEED = (0.1, 0.3), 2026         # series-R draw, identical to scripts/robustness.py


def git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def crb_table(rhos):
    """Local Cramer-Rao bounds from Stage A (6 scalar features) with correlated repeat/temperature noise."""
    from identifiability import NUISANCE, TARGETS, jacobian, sigmas
    df = pd.read_csv(ROOT / "results/stage_a_v11/runs.csv")
    df = df[df.converged.astype(str).str.lower() == "true"]
    nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)
    tags = dict(TARGETS); tags.update(NUISANCE)
    J3, J4 = jacobian(df, 300, 0.1, tags), jacobian(df, 423, 0.1, tags)
    D = np.diag(sigmas(nz, nz["levels"]["nominal"]) ** 2)
    sd = lambda J, S: np.sqrt(np.diag(np.linalg.inv(J.T @ np.linalg.inv(S) @ J)))
    s1 = sd(J3, D)
    out = {"parameters": list(tags), "S2_over_S1": {}, "S1x2_over_S1": {}}
    for rho in rhos:
        S = np.block([[D, rho * D], [rho * D, D]])
        out["S2_over_S1"][str(rho)] = dict(zip(tags, map(float, sd(np.vstack([J3, J4]), S) / s1)))
        out["S1x2_over_S1"][str(rho)] = dict(zip(tags, map(float, sd(np.vstack([J3, J3]), S) / s1)))
    return out


def run_case(pool_w, test_w, nz, level, rho, model, k, floor):
    sp, st = replicate_seeds(nz["seeds"]["pool"], k), replicate_seeds(nz["seeds"]["test"], k)
    p1, p2 = noisy_tables(pool_w, nz, level, sp[0], rho, rho, floor=floor, repeat_seed=sp[1])
    t1, t2 = noisy_tables(test_w, nz, level, st[0], rho, rho, floor=floor, repeat_seed=st[1])
    lo, hi = _lohi(load_bounds())
    errs = {}
    for S in SETS:
        P = fit_predict(control_feature_set(p1, p2, S).values, pool_w[VARS].values,
                        control_feature_set(t1, t2, S).values, model, 0)
        errs[S] = np.abs(P - test_w[VARS].values) / (np.asarray(hi) - np.asarray(lo))      # (n_test, 3)
    return errs


def summarise(errs, n_boot, contrasts=CONTRASTS):
    sets = {S: dict(mean=float(e.mean()), **{v: float(e[:, j].mean()) for j, v in enumerate(VARS)}) for S, e in errs.items()}
    con = {}
    for a, b in contrasts:
        if a in errs and b in errs:
            con[f"{a}-{b}"] = dict(mean=paired_boot(errs[a].mean(1), errs[b].mean(1), n_boot),
                                   **{v: paired_boot(errs[a][:, j], errs[b][:, j], n_boot) for j, v in enumerate(VARS)})
    return dict(sets=sets, contrasts=con)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--levels", nargs="+", default=["nominal", "high"])
    ap.add_argument("--rhos", nargs="+", type=float, default=[0.0, 0.5, 0.9])
    ap.add_argument("--models", nargs="+", default=["gp", "ridge"])
    ap.add_argument("--replicates", type=int, default=5, help="noise realisations for the secondary check (k=0 frozen)")
    ap.add_argument("--n-boot", type=int, default=5000)
    ap.add_argument("--no-series-r", action="store_true")
    ap.add_argument("--blind", action="store_true", help="do not print control results (pipeline check only)")
    ap.add_argument("--out", default=str(ROOT / "results" / "summary"))
    a = ap.parse_args()
    nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)
    fl = nz.get("current_floor_A_per_cm")
    bpool, btest = pd.read_csv(ROOT / "results/pool/runs.csv"), pd.read_csv(ROOT / "results/test/runs.csv")
    pool_w, test_w = wide_table(bpool).sort_index(), wide_table(btest).sort_index()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    meta = dict(analysis="v4.7 repeated-measurement control", plan="docs/PREDICTIONS_V47.md",
                plan_commit=git("log", "-1", "--format=%h", "--", "docs/PREDICTIONS_V47.md"),
                code_commit=git("rev-parse", "--short", "HEAD"), code_dirty=bool(git("status", "--porcelain", "--", "src", "scripts", "configs")),
                noise_version=nz["version"], current_floor=fl, levels=a.levels, rhos=a.rhos, models=a.models,
                replicates=a.replicates, n_boot=a.n_boot, n_pool=len(pool_w), n_test=len(test_w),
                seeds=dict(rule="replicate k: first = frozen seed + 10000k, repeat = first + 1000",
                           pool=nz["seeds"]["pool"], test=nz["seeds"]["test"]),
                env=compute_env(), created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
    res = dict(meta=meta, crb=crb_table(sorted(set([0.0] + a.rhos))), cases=[], replicates=[], series_r=None)
    points = []
    for lv in a.levels:
        for rho in a.rhos:
            for m in a.models:
                errs = run_case(pool_w, test_w, nz, nz["levels"][lv], rho, m, 0, fl)
                res["cases"].append(dict(level=lv, rho=rho, model=m, replicate=0, **summarise(errs, a.n_boot)))
                for S, e in errs.items():
                    points.append(pd.DataFrame(e, columns=[f"err_{v}" for v in VARS]).assign(
                        level=lv, rho=rho, model=m, set=S, candidate_id=test_w.index.values))
                print(f"done {lv} rho={rho} {m}", flush=True)
    for k in range(1, a.replicates):                    # secondary: other noise realisations (GP, nominal, rho=0)
        errs = run_case(pool_w, test_w, nz, nz["levels"]["nominal"], 0.0, "gp", k, fl)
        res["replicates"].append(dict(replicate=k, **summarise(errs, a.n_boot, [("S2", "S1x2"), ("S1x2", "S1"), ("S2", "S1")])))
        print(f"done replicate {k}", flush=True)
    if not a.no_series_r:                               # exploratory: drain-side series R on the test devices only
        rng = np.random.default_rng(RHO_SEED)
        ids = sorted(btest["candidate_id"].unique())
        rho_map = dict(zip(ids, rng.uniform(*RHO_RANGE, len(ids))))
        test_rs = wide_table(apply_series_resistance(btest, ROOT / "results/test/runs", rho_map)).sort_index()
        errs = run_case(pool_w, test_rs, nz, nz["levels"]["nominal"], 0.0, "gp", 0, fl)
        errs = {S: errs[S] for S in ("S1", "S1x2", "S2")}
        res["series_r"] = summarise(errs, a.n_boot, [("S2", "S1x2"), ("S1x2", "S1"), ("S2", "S1")])
    # reproduction check against the published frozen baseline (safe to print in blind mode)
    base = next((c for c in res["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp"), None)
    if base:
        s1, s2 = base["sets"]["S1"]["mean"], base["sets"]["S2"]["mean"]
        ci = base["contrasts"]["S2-S1"]["mean"]["ci"]
        exact = abs(s1 - PUBLISHED["S1"]) < 5e-7 and abs(s2 - PUBLISHED["S2"]) < 5e-7
        close = abs(s1 - PUBLISHED["S1"]) < 5e-4 and abs(s2 - PUBLISHED["S2"]) < 5e-4
        res["meta"]["reproduction"] = dict(S1=s1, S2=s2, ci=ci, exact=exact, close=close)
        print(f"reproduction: S1 {s1:.6f} S2 {s2:.6f} CI [{ci[0]:+.3f}, {ci[1]:+.3f}] -> "
              f"{'EXACT' if exact else ('CLOSE' if close else 'MISMATCH')} "
              f"(published {PUBLISHED['S1']} / {PUBLISHED['S2']}, CI {PUBLISHED['ci']})")
        if not close:
            print("WARNING: the frozen S1/S2 baseline is not reproduced - check the environment before using these results")
    if res["series_r"]:
        sr = res["series_r"]["sets"]
        print(f"reproduction (series R): S1 {sr['S1']['mean']:.3f} S2 {sr['S2']['mean']:.3f} "
              f"(published {PUBLISHED['series_S1']} / {PUBLISHED['series_S2']})")
    json.dump(res, open(out / "v47_repeat_control.json", "w"), indent=1)
    pd.concat(points).to_csv(out / "v47_repeat_control_points.csv", index=False)
    (out / "v47_repeat_control.md").write_text(report(res))
    if not a.blind:
        print((out / "v47_repeat_control.md").read_text())
    print("-> results/summary/v47_repeat_control.{json,md}, v47_repeat_control_points.csv")


def report(res):
    f3 = lambda x: f"{x:.3f}"
    ci = lambda c: f"{c['delta']:+.4f} [{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}]"
    L = ["# v4.7 반복 측정 통제 (RQ1 보강, 계획: docs/PREDICTIONS_V47.md)\n",
         f"코드 {res['meta']['code_commit']}{' (dirty)' if res['meta']['code_dirty'] else ''}, 계획 커밋 {res['meta']['plan_commit']}, "
         f"잡음 {res['meta']['noise_version']}, 시험점 {res['meta']['n_test']}, 부트스트랩 {res['meta']['n_boot']}회.\n",
         "MAE_norm = 절대오차/DOE 범위. 대비(Δ)는 시험점 짝지은 부트스트랩 95% CI, 비는 평균 오차의 비.\n"]
    rp = res["meta"].get("reproduction")
    if rp:
        L.append(f"동결 기준 재현: S1 {rp['S1']:.6f}, S2 {rp['S2']:.6f} (논문 0.112275, 0.072011) → "
                 f"{'정확히 일치' if rp['exact'] else ('근사 일치' if rp['close'] else '불일치 — 결과 사용 전 환경 확인')}\n")
    for c in res["cases"]:
        L += [f"\n## {c['level']} 잡음, ρ = {c['rho']}, {c['model'].upper()}\n",
              "| 특징 집합 | 평균 | " + " | ".join(TAG.values()) + " |", "|---|---|---|---|---|"]
        for S, s in c["sets"].items():
            L.append(f"| {S} | {f3(s['mean'])} | " + " | ".join(f3(s[v]) for v in VARS) + " |")
        L += ["", "| 대비 | 평균 Δ [95% CI] | " + " | ".join(f"{t} Δ [95% CI] (비)" for t in TAG.values()) + " |", "|---|---|---|---|---|"]
        for k, con in c["contrasts"].items():
            L.append(f"| {k} | {ci(con['mean'])} | " + " | ".join(f"{ci(con[v])} ({con[v]['ratio']:.2f})" for v in VARS) + " |")
    if res["replicates"]:
        L += ["\n## 다른 잡음 실현(이차 분석, GP, nominal, ρ = 0)\n",
              "| 실현 | S1 | S1x2 | S2 | S2−S1x2 W_JFET Δ [95% CI] | S2−S1x2 N_pw | S2−S1x2 Q_it,eff |", "|---|---|---|---|---|---|---|"]
        for r in res["replicates"]:
            s, c = r["sets"], r["contrasts"]["S2-S1x2"]
            L.append(f"| {r['replicate']} | {f3(s['S1']['mean'])} | {f3(s['S1x2']['mean'])} | {f3(s['S2']['mean'])} | "
                     + " | ".join(ci(c[v]) for v in VARS) + " |")
    if res["series_r"]:
        s, c = res["series_r"]["sets"], res["series_r"]["contrasts"]
        L += ["\n## 기생 직렬저항(탐색적, 시험 데이터에만 적용, GP, nominal)\n",
              "| 특징 집합 | 평균 | " + " | ".join(TAG.values()) + " |", "|---|---|---|---|---|"]
        L += [f"| {S} | {f3(v['mean'])} | " + " | ".join(f3(v[x]) for x in VARS) + " |" for S, v in s.items()]
        L += [f"\nS2−S1x2 평균 {ci(c['S2-S1x2']['mean'])}, S1x2−S1 평균 {ci(c['S1x2-S1']['mean'])}"]
    L += ["\n## 국소 CRB 비(Stage A, 6개 스칼라 특징, nominal 잡음)\n",
          "| ρ | 집합 | " + " | ".join(TAG.values()) + " |", "|---|---|---|---|---|"]
    for rho, d in res["crb"]["S2_over_S1"].items():
        L.append(f"| {rho} | S2/S1 | " + " | ".join(f"{d[v]:.3f}" for v in VARS) + " |")
        e = res["crb"]["S1x2_over_S1"][rho]
        L.append(f"| {rho} | S1x2/S1 | " + " | ".join(f"{e[v]:.3f}" for v in VARS) + " |")
    L.append("\n423 K 물리 변형(γ, r)은 300 K 특징을 바꾸지 않으므로 S1과 S1x2의 오차는 표 2의 모든 시나리오에서 위 기준값과 같다.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
