"""v4.7 RQ3 ablation report (analysis plan: docs/PREDICTIONS_V47.md). No API calls.
  python scripts/rq3_ablation.py [--blind]
All v4.7 conditions are run in ONE environment and session (same 10 seeds, initial sets, budget; S2 features,
RF inverse model, nominal noise), because active-learning trajectories differ slightly between CPUs:
  A   LLM, original payload and prompt          results/al_v47/named/nominal
  B   LLM, anonymised payload and prompt        results/al_v47/anon/nominal
  C   LLM, shuffled information                 results/al_v47/shuffled/nominal
  D   random 10 of the uncertainty top-20       results/al_v47/numeric/nominal (policy top20_random)
  U   uncertainty policy (+ random, sobol)      results/al_v47/numeric/nominal
Published runs (other environment), reported for continuity and run-to-run variation only:
  A0  original RQ3 LLM run                      results/al_live/nominal
  U0  original uncertainty run                  results/al/nominal
-> results/summary/v47_rq3_ablation.json, v47_rq3_ablation.md"""
import argparse, datetime as dt, json, subprocess, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.ablation import call_stats
from sicsim.design import DESIGN_VARS, _spec, load_bounds

R = ROOT / "results"
V = R / "al_v47"
SESOI = 0.0025          # smallest effect of interest = published RQ2 uncertainty-vs-random final-round effect
COND = {"A": (V / "named/nominal", "llm"), "B": (V / "anon/nominal", "llm"), "C": (V / "shuffled/nominal", "llm"),
        "D": (V / "numeric/nominal", "top20_random"), "U": (V / "numeric/nominal", "uncertainty"),
        "random": (V / "numeric/nominal", "random"), "sobol": (V / "numeric/nominal", "sobol"),
        "A0": (R / "al_live/nominal", "llm"), "U0": (R / "al/nominal", "uncertainty")}
LABEL = {"A": "A LLM(원본 형식)", "B": "B LLM(익명화)", "C": "C LLM(정보 섞기)", "D": "D 상위20 내 무작위",
         "U": "불확실도", "random": "무작위", "sobol": "Sobol", "A0": "A0 LLM(논문 실행)", "U0": "불확실도(논문 실행)"}
PRIMARY = [("B", "A"), ("C", "A"), ("A", "U"), ("B", "U"), ("C", "U"), ("D", "U"), ("A", "D"), ("B", "D"), ("C", "D")]
SECONDARY = [("U", "random"), ("sobol", "random"), ("A0", "A")]


def per_seed(folder, policy):
    d = pd.read_csv(Path(folder) / "al_curves.csv")
    d = d[d.policy == policy]
    if d.empty:
        return None
    last = d.n_points.max()
    fin = d[d.n_points == last].set_index("seed").mean_mae_norm.sort_index()
    auc = d[d["round"] >= 1].groupby("seed").mean_mae_norm.mean().sort_index()      # rounds 1-6 (round 0 is shared)
    return fin, auc, int(last), d


def boot(diff, n_boot=5000, seed=1):
    b = np.random.default_rng(seed).choice(diff, (n_boot, len(diff))).mean(1)
    lo, hi = np.percentile(b, [2.5, 97.5]); l90, h90 = np.percentile(b, [5, 95])
    return dict(delta=float(diff.mean()), ci=[float(lo), float(hi)], ci90=[float(l90), float(h90)],
                wins=int((diff < 0).sum()), n=int(len(diff)), equivalent=bool(l90 > -SESOI and h90 < SESOI))


def coords():
    b = load_bounds()
    d = pd.read_csv(ROOT / "configs/design_pool.csv").set_index("candidate_id")
    lo = np.array([float(_spec(b, v)["low"]) for v in DESIGN_VARS]); hi = np.array([float(_spec(b, v)["high"]) for v in DESIGN_VARS])
    return pd.DataFrame((d[DESIGN_VARS].values.astype(float) - lo) / (hi - lo), index=d.index, columns=DESIGN_VARS)


def behaviour(log, X):
    if not Path(log).exists():
        return None
    L = [json.loads(x) for x in open(log) if x.strip()]
    st = [s for s in (call_stats(r, X) for r in L) if s]
    out = dict(calls=len(L), accepted=sum(r["validator_status"] == "accepted" for r in L),
               modes=sorted({str(r.get("mode")) for r in L}), variants=sorted({r.get("variant", "named") for r in L}),
               models=sorted({str(r.get("model_id")) for r in L}),
               tokens_in=int(sum(r.get("input_tokens", 0) for r in L)), tokens_out=int(sum(r.get("output_tokens", 0) for r in L)),
               latency_s=float(np.mean([r.get("latency_s", 0) for r in L])) if L else None,
               reject_reasons=pd.Series([(r.get("reject_reason") or "")[:30] for r in L if r["validator_status"] != "accepted"],
                                        dtype=object).value_counts().to_dict(),
               reason_codes=pd.Series([c for r in L for c in (r.get("reason_codes") or [])], dtype=object).value_counts().to_dict(),
               n_stats=len(st))
    if st:
        df = pd.DataFrame(st)
        for c in ("overlap_true", "overlap_shown", "p_wider_mpd_random", "p_widen_displayed_random", "p_widen_true_random"):
            if c in df:
                out[c] = float(df[c].mean())
        for c in ("wider_mpd", "widen_displayed", "widen_true"):
            if c in df:
                out[c] = int(df[c].sum())
        if "widen_displayed" in df:
            out["worst_target_wrong"] = int((df.worst_displayed.astype(str) != df.worst_true.astype(str)).sum())
    return out


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--blind", action="store_true"); a = ap.parse_args()
    git = lambda *g: subprocess.run(["git", *g], cwd=ROOT, capture_output=True, text=True).stdout.strip()
    data = {}
    for k, (folder, pol) in COND.items():
        if (Path(folder) / "al_curves.csv").exists():
            got = per_seed(folder, pol)
            if got is not None:
                data[k] = got
    missing = sorted(set(COND) - set(data))
    metas = {k: json.load(open(Path(COND[k][0]) / "meta.json")) for k in data if (Path(COND[k][0]) / "meta.json").exists()}
    envs = {k: (m.get("env") or {}).get("cpu") for k, m in metas.items() if k in ("A", "B", "C", "D", "U")}
    res = dict(meta=dict(plan="docs/PREDICTIONS_V47.md", plan_commit=git("log", "-1", "--format=%h", "--", "docs/PREDICTIONS_V47.md"),
                         code_commit=git("rev-parse", "--short", "HEAD"), sesoi=SESOI, missing=missing,
                         v47_cpus=sorted({str(v) for v in envs.values()}), v47_code_commits=sorted({str(m.get("code_commit")) for k, m in metas.items() if k in envs}),
                         created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
               final={k: dict(mean=float(v[0].mean()), sd=float(v[0].std()), n_points=v[2]) for k, v in data.items()},
               mean_rounds_1_6={k: dict(mean=float(v[1].mean()), sd=float(v[1].std())) for k, v in data.items()},
               compare={}, secondary={}, behaviour={})
    if len(res["meta"]["v47_cpus"]) > 1:
        print("WARNING: v4.7 conditions were run on different CPUs:", res["meta"]["v47_cpus"])
    for group, pairs in (("compare", PRIMARY), ("secondary", SECONDARY)):
        for x, y in pairs:
            if x in data and y in data:
                fx, fy = data[x][0], data[y][0]
                assert list(fx.index) == list(fy.index), f"seed mismatch {x}/{y}"
                res[group][f"{x}-{y}"] = dict(final=boot((fx - fy).values), mean_rounds_1_6=boot((data[x][1] - data[y][1]).values))
    if "U" in data and "U0" in data:              # environment diagnostic: does this environment reproduce the published runs?
        u, u0 = (data[k][3].sort_values(["seed", "round"]).mean_mae_norm.values for k in ("U", "U0"))
        res["meta"]["U_vs_published_max_abs_diff"] = float(np.abs(u - u0).max()) if len(u) == len(u0) else None
    X = coords()
    for k in ("A", "B", "C", "A0"):
        res["behaviour"][k] = behaviour(Path(COND[k][0]) / "llm_calls.jsonl", X)
    out = R / "summary"; out.mkdir(parents=True, exist_ok=True)
    json.dump(res, open(out / "v47_rq3_ablation.json", "w"), indent=1)
    (out / "v47_rq3_ablation.md").write_text(report(res))
    print(f"conditions found: {sorted(data)}; missing: {missing or 'none'}")
    if "U_vs_published_max_abs_diff" in res["meta"]:
        d = res["meta"]["U_vs_published_max_abs_diff"]
        print(f"environment check: uncertainty curves vs published run, max |diff| = {d}"
              + (" (identical environment)" if d == 0 else " (different environment: compare v4.7 conditions only with each other)"))
    if not a.blind:
        print((out / "v47_rq3_ablation.md").read_text())
    print("-> results/summary/v47_rq3_ablation.{json,md}")


def report(res):
    f = lambda c: f"{c['delta']:+.4f} [{c['ci'][0]:+.4f}, {c['ci'][1]:+.4f}]"
    m = res["meta"]
    L = ["# v4.7 RQ3 절제 실험 (계획: docs/PREDICTIONS_V47.md)\n",
         f"계획 커밋 {m['plan_commit']}, 코드 {m['code_commit']} (v4.7 실행 코드 {', '.join(m['v47_code_commits']) or '—'}), "
         f"CPU {', '.join(m['v47_cpus']) or '—'}. 시드 10개 짝지은 비교, 부트스트랩 5,000회. "
         f"동등 판정: 90% CI가 ±{SESOI}(논문 RQ2의 불확실도−무작위 효과) 안.\n"]
    if m["missing"]:
        L.append(f"**아직 없는 조건: {', '.join(m['missing'])}**\n")
    if m.get("U_vs_published_max_abs_diff") is not None:
        L.append(f"환경 점검: 불확실도 정책 곡선의 논문 실행 대비 최대 차이 {m['U_vs_published_max_abs_diff']:.2e} "
                 "(0이 아니면 다른 CPU 환경이므로 v4.7 조건끼리만 비교한다).\n")
    L += ["## 최종 오차(120점)와 라운드 1–6 평균\n", "| 조건 | 최종 평균 ± SD | 라운드 1–6 평균 |", "|---|---|---|"]
    for k, v in res["final"].items():
        L.append(f"| {LABEL[k]} | {v['mean']:.4f} ± {v['sd']:.4f} | {res['mean_rounds_1_6'][k]['mean']:.4f} |")
    for title, grp in (("주 비교(같은 환경)", "compare"), ("보조 비교", "secondary")):
        L += [f"\n## {title}\n", "| 비교 | 최종 Δ [95% CI] | 왼쪽 우세/10 | 동등(±δ) | 라운드 1–6 Δ [95% CI] |", "|---|---|---|---|---|"]
        for k, c in res[grp].items():
            x, y = k.split("-")
            L.append(f"| {LABEL[x]} − {LABEL[y]} | {f(c['final'])} | {c['final']['wins']} | "
                     f"{'예' if c['final']['equivalent'] else '아니오'} | {f(c['mean_rounds_1_6'])} |")
    L += ["\n## LLM 선택 행동\n",
          "| 조건 | 통과 | 실제 상위10 겹침 | 표시 상위10 겹침 | 상위10보다 넓음 (무작위 기대) | 표시 최악변수 방향 확대 (무작위 기대) | 실제 최악변수 방향 확대 (무작위 기대) | 토큰 입/출력 |",
          "|---|---|---|---|---|---|---|---|"]
    for k, b in res["behaviour"].items():
        if not b:
            L.append(f"| {LABEL[k]} | — | — | — | — | — | — | — |"); continue
        n = b.get("n_stats", 0)
        g = lambda key, p: f"{b[key]}/{n} ({100 * b[p]:.0f}%)" if key in b and p in b else "—"
        o = lambda key: f"{b[key]:.2f}" if key in b else "—"
        L.append(f"| {LABEL[k]} | {b['accepted']}/{b['calls']} | {o('overlap_true')} | {o('overlap_shown')} | "
                 f"{g('wider_mpd', 'p_wider_mpd_random')} | {g('widen_displayed', 'p_widen_displayed_random')} | "
                 f"{g('widen_true', 'p_widen_true_random')} | {b['tokens_in']}/{b['tokens_out']} |")
    L.append("\n무작위 기대: 같은 20개 후보에서 10개를 무작위로 골랐을 때의 확률(호출별 2,000회 표본의 평균). "
             "실제 상위10 겹침의 무작위 기대값은 0.50이다. C에서는 표시된 최악 변수가 항상 실제와 다르다. "
             "A0은 표시 정보(payload)가 기록되지 않은 논문 실행이어서 최악 변수 통계를 계산하지 않는다.")
    return "\n".join(L) + "\n"


if __name__ == "__main__":
    main()
