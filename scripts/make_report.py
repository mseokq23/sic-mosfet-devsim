"""Static HTML report of the committed results (reads result files only: no model fitting, no DEVSIM, no API).
  python scripts/make_report.py                       -> docs/report/index.html (Plotly loaded from jsDelivr)
  python scripts/make_report.py --embed-plotly        -> same page with plotly.js inlined (works offline;
                                                          needs `pip install -r requirements-viz.txt`)
  python scripts/make_report.py --out PATH [--fragment]
Every number on the page is read at build time from results/, configs/ and paper/tables/; the page lists the
files it read (size and SHA-256) in its last section. Template: scripts/report_template.html."""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import re
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SUM = ROOT / "results" / "summary"
VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]
DESIGN = VARS + ["mu_channel_scale"]
VARIANTS = ["gamma0", "gamma_m1", "qitT10", "qitT30"]
PLOTLY_CDN = "https://cdn.jsdelivr.net/npm/plotly.js-basic-dist-min@2.35.2/plotly-basic.min.js"
READ: dict[str, Path] = {}                       # provenance: every file the page is built from


# ----------------------------------------------------------------------------- helpers
def rd(rel) -> Path:
    p = ROOT / rel
    READ[str(Path(rel).as_posix())] = p
    return p


def jload(rel):
    return json.load(open(rd(rel), encoding="utf-8"))


def jlines(rel):
    return [json.loads(x) for x in open(rd(rel), encoding="utf-8") if x.strip()]


def cload(rel, **kw):
    return pd.read_csv(rd(rel), **kw)


def sig(x, n=5):
    """Round to n significant digits; non-finite -> None (keeps the embedded JSON small and valid)."""
    if x is None or isinstance(x, (bool, str)):
        return x
    if isinstance(x, (int, np.integer)):
        return int(x)
    x = float(x)
    if not math.isfinite(x):
        return None
    return 0.0 if x == 0 else float(f"{x:.{n}g}")


def tidy(o, n=5):
    if isinstance(o, dict):
        return {str(k): tidy(v, n) for k, v in o.items()}
    if isinstance(o, (list, tuple, np.ndarray)):
        return [tidy(v, n) for v in o]
    if isinstance(o, (np.floating, float, int, np.integer)) and not isinstance(o, bool):
        return sig(o, n)
    return o


def git(*args) -> str:
    try:
        return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, timeout=20).stdout.strip()
    except Exception:
        return ""


def mean_ci(E, n=2000, seed=7):
    """Column means and test-point bootstrap 95% CI, identical to scripts/make_v47_figures.py (seed 7, 2000)."""
    E = np.asarray(E, float)
    bi = np.random.default_rng(seed).integers(0, len(E), (n, len(E)))
    lo, hi = np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0)
    return E.mean(0), lo, hi


# ----------------------------------------------------------------------------- sections
def meta():
    builds = sorted(ROOT.glob("paper/final/build_v*.js"),
                    key=lambda p: int(re.search(r"(\d+)", p.stem).group(1)) if re.search(r"(\d+)", p.stem) else -1)
    m = re.search(r"build_v(\d)(\d+)", builds[-1].stem) if builds else None
    return dict(
        branch=git("rev-parse", "--abbrev-ref", "HEAD") or "unknown",
        head=git("rev-parse", "--short", "HEAD") or "unknown",
        data_commit=git("log", "-1", "--format=%h", "--", "results") or "unknown",
        data_date=git("log", "-1", "--format=%cs", "--", "results") or "",
        results_dirty=bool(git("status", "--porcelain", "--", "results", "configs")),
        generated=dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        manuscript=f"V{m.group(1)}.{m.group(2)}" if m else "",
        plotly=PLOTLY_CDN.split("@")[1].split("/")[0],
    )


def runs_overview():
    sets = ["pool", "test"] + [f"{d}_{v}" for v in VARIANTS for d in ("pool", "test")]
    rows, rt = [], []
    for s in sets:
        df = cload(f"results/{s}/runs.csv")
        conv = int((df["converged"].astype(str).str.lower() == "true").sum())
        rows.append(dict(set=s, runs=len(df), converged=conv,
                         temps="/".join(str(int(t)) for t in sorted(df["temperature_K"].unique())),
                         median_runtime_s=float(df["runtime_s"].median())))
        rt.append(df["runtime_s"].values)
    allrt = np.concatenate(rt)
    return dict(sets=rows, total=int(sum(r["runs"] for r in rows)), converged=int(sum(r["converged"] for r in rows)),
                median_runtime_s=float(np.median(allrt)))


def curve(path):
    d = json.load(open(path, encoding="utf-8"))
    t, o, f = d["curves"]["transfer"], d["curves"]["output"], d["features"]
    return dict(ti=[sig(v, 4) for v in t["id"]], ov=[sig(v, 4) for v in o["vds"]], oi=[sig(v, 4) for v in o["id"]],
                f=dict(vth=sig(f.get("vth_V"), 5), ss=sig(f.get("ss_mV_dec"), 4), ron=sig(f.get("ron_mohm_cm2"), 4),
                       ion=sig(f.get("ion_A_per_cm"), 4), gm=sig(f.get("gm_max_S_per_cm"), 4))), d


def device():
    base = ROOT / "results" / "stage_a_v11" / "runs"
    READ["results/stage_a_v11/runs/*.json"] = base
    vgs = None
    stage = {}
    for p in sorted(base.glob("A_*_T*.json")):
        name, T = p.stem.rsplit("_T", 1)
        c, d = curve(p)
        vgs = vgs or [round(v, 3) for v in d["curves"]["transfer"]["vgs"]]
        stage.setdefault(name.replace("A_", "", 1), {})[T] = c
    test = ROOT / "results" / "test" / "runs"
    READ["results/test/runs/*.json"] = test
    for v in VARIANTS:
        READ[f"results/test_{v}/runs/*.json"] = ROOT / "results" / f"test_{v}" / "runs"
    cands = []
    for p in sorted(test.glob("*_T300.json")):
        cid = p.stem.rsplit("_T", 1)[0]
        c300, d = curve(p)
        c423, _ = curve(test / f"{cid}_T423.json")
        item = dict(id=cid, p=[sig(d[k], 5) for k in DESIGN], c={"300": c300, "423": c423})
        for v in VARIANTS:
            q = ROOT / "results" / f"test_{v}" / "runs" / f"{cid}_T423.json"
            if q.exists():
                item["c"][v] = curve(q)[0]
        cands.append(item)
    t1 = cload("paper/tables/table1_sensitivity.csv")
    return dict(vgs=vgs, stage=stage, cands=cands, table1=dict(columns=list(t1.columns), rows=t1.astype(str).values.tolist()))


def rq1():
    rc = jload("results/summary/v47_repeat_control.json")
    pts = cload("results/summary/v47_repeat_control_points.csv")
    design = cload("configs/design_test.csv").set_index("candidate_id")

    def case(level, rho, model="gp"):
        return next(c for c in rc["cases"] if c["level"] == level and abs(c["rho"] - rho) < 1e-9 and c["model"] == model
                    and c.get("replicate", 0) == 0)

    def sel(rho=0.0, level="nominal", model="gp"):
        return pts[(pts.level == level) & np.isclose(pts.rho, rho) & (pts.model == model)]

    errc = [f"err_{v}" for v in VARS]
    bars = {}
    for s in ("S1", "S1x2", "S2"):
        E = sel()[lambda d: d.set == s].sort_values("candidate_id")[errc].values
        m, lo, hi = mean_ci(E)
        bars[s] = dict(mean=m.tolist(), lo=lo.tolist(), hi=hi.tolist())
    c0 = case("nominal", 0.0)
    contrast = {v: c0["contrasts"]["S2-S1x2"][v] for v in VARS + ["mean"]}
    rho = {}
    for s in ("S1", "S1x2", "S2", "S3"):
        m_, lo_, hi_ = [], [], []
        for r in (0.0, 0.5, 0.9):
            E = sel(r)[lambda d: d.set == s].sort_values("candidate_id")[errc].values.mean(1, keepdims=True)
            m, lo, hi = mean_ci(E)
            m_.append(m[0]); lo_.append(lo[0]); hi_.append(hi[0])
        rho[s] = dict(rho=[0.0, 0.5, 0.9], mean=m_, lo=lo_, hi=hi_)
    rho_cases = {f"{r}": {"sets": case("nominal", r)["sets"], "S2-S1x2": case("nominal", r)["contrasts"]["S2-S1x2"]["mean"]}
                 for r in (0.0, 0.5, 0.9)}
    P = sel()
    paired = {}
    for s in ("S1", "S1x2", "S2"):
        d = P[P.set == s].sort_values("candidate_id")
        paired[s] = {v: d[f"err_{v}"].tolist() for v in VARS}
    ids = P[P.set == "S2"].sort_values("candidate_id")["candidate_id"].tolist()
    truth = design.loc[ids, DESIGN].values.tolist()
    v48 = jload("results/summary/v48_extra_stats.json")
    budget = v48["part2"]
    crb = rc["crb"]
    return dict(bars=bars, contrast=contrast, rho=rho, rho_cases=rho_cases, paired=paired, ids=ids, truth=truth,
                budget=budget, crb=crb, high=case("high", 0.0)["sets"], ridge=case("nominal", 0.0, "ridge")["sets"],
                cases_meta=rc["meta"])


def physics():
    v48 = jload("results/summary/v48_extra_stats.json")["part1"]
    rob = jload("results/summary/robustness.json")
    rc = jload("results/summary/v47_repeat_control.json")
    nom = rob["levels"]["nominal"]
    scen = {}
    for key, s in v48["scenarios"].items():
        row = {}
        for k in ("matched", "mixed", "nominal", "nominal_clipped"):
            if k in s:
                row[k] = dict(mean=s[k]["mean"], **{v: s[k][v] for v in VARS},
                              d=s[k]["vs_S1x2"]["mean"]["delta"], ci=s[k]["vs_S1x2"]["mean"]["ci"],
                              ratio=s[k]["vs_S1x2"]["mean"]["ratio"],
                              vr={v: s[k]["vs_S1x2"][v]["ratio"] for v in VARS},
                              vci={v: s[k]["vs_S1x2"][v]["ci"] for v in VARS})
        scen[key] = row
    series = rc["series_r"]["sets"]
    # 423 K feature shifts of each variant against the frozen physics, test set (median over 128 devices)
    base = cload("results/test/runs.csv")
    base = base[np.isclose(base.temperature_K, 423)].set_index("candidate_id")
    shifts = {}
    for v in VARIANTS:
        d = cload(f"results/test_{v}/runs.csv").set_index("candidate_id")
        j = d.join(base, rsuffix="_b", how="inner")
        shifts[v] = dict(dvth_mV=float(np.median((j.vth_V - j.vth_V_b) * 1e3)),
                         ion_pct=float(np.median((j.ion_A_per_cm / j.ion_A_per_cm_b - 1) * 100)),
                         ron_pct=float(np.median((j.ron_mohm_cm2 / j.ron_mohm_cm2_b - 1) * 100)),
                         gm_pct=float(np.median((j.gm_max_S_per_cm / j.gm_max_S_per_cm_b - 1) * 100)),
                         ss_pct=float(np.median((j.ss_mV_dec / j.ss_mV_dec_b - 1) * 100)), n=int(len(j)))
    return dict(reference=v48["reference"], scenarios=scen, series=series, shifts=shifts,
                rob_nominal={k: dict(S1=nom[k]["S1"]["mean"], S2=nom[k]["S2"]["mean"], ci=nom[k]["ci"]) for k in nom})


POLICY_DIR = {"random": "results/al_v47/numeric/nominal", "sobol": "results/al_v47/numeric/nominal",
              "uncertainty": "results/al_v47/numeric/nominal", "top20_random": "results/al_v47/numeric/nominal",
              "A": "results/al_v47/named/nominal", "B": "results/al_v47/anon/nominal",
              "C": "results/al_v47/shuffled/nominal", "A0": "results/al_live/nominal"}


def selection():
    curves = {}
    for key, folder in POLICY_DIR.items():
        d = cload(f"{folder}/al_curves.csv")
        pol = "llm" if key in ("A", "B", "C", "A0") else key
        d = d[d.policy == pol]
        g = d.groupby("n_points").mean_mae_norm
        curves[key] = dict(n=g.mean().index.tolist(), mean=g.mean().tolist(), sd=g.std(ddof=1).tolist(),
                           seeds=int(d.seed.nunique()))
    ab = jload("results/summary/v47_rq3_ablation.json")
    p3 = jload("results/summary/v48_extra_stats.json")["part3"]

    def row(label, rec, grp):
        f = rec["final"] if "final" in rec else rec
        ci = f.get("ci") or f.get("boot95")
        return dict(label=label, d=f["delta"] * 1e3, lo=ci[0] * 1e3, hi=ci[1] * 1e3, wins=f["wins"], group=grp)
    forest = [row("불확실도 − 무작위", ab["secondary"]["U-random"], "U"),
              row("Sobol − 무작위", ab["secondary"]["sobol-random"], "S"),
              row("상위 20 무작위(D) − 불확실도", ab["compare"]["D-U"], "D"),
              row("LLM 1차 실행(A0) − 불확실도", p3["final:A0-U"], "A0"),
              row("LLM 재실행(A) − 불확실도", ab["compare"]["A-U"], "A"),
              row("LLM 익명화(B) − 불확실도", ab["compare"]["B-U"], "B"),
              row("LLM 정보 섞기(C) − 불확실도", ab["compare"]["C-U"], "C")]
    seedstats = {k.split(":", 1)[1]: dict(delta=v["delta"], boot95=v["boot95"], t95=v["t95"], p=v["signflip_p"],
                                          wins=v["wins"], mde=v["mde80"], eq=v["equivalent_boot90"])
                 for k, v in p3.items() if k.startswith("final:")}
    ni = cload("results/summary/al_ninit_summary.csv")
    if "ci_lo" not in ni.columns and "ci" in ni.columns:          # committed file stores the CI as "[lo, hi]"
        lohi = ni["ci"].astype(str).str.strip("[]").str.split(",", expand=True).astype(float)
        ni["ci_lo"], ni["ci_hi"] = lohi[0], lohi[1]
    num = lambda x: None if pd.isna(x) else float(x)
    ninit = [dict(n_init=int(r.n_init), final_n=int(r.final_n), policy=r.policy, random_final=num(r.random_final),
                  delta=num(r.delta), ci_lo=num(r.ci_lo), ci_hi=num(r.ci_hi), wins=int(r.wins), reach_n=num(r.reach_n),
                  saving_pct=num(r.saving_pct)) for r in ni.itertuples()]
    return dict(curves=curves, forest=forest, final=ab["final"], seedstats=seedstats, ninit=ninit, sesoi=ab["meta"]["sesoi"])


LLM_LOGS = {"A0": "results/al_live/nominal/llm_calls.jsonl", "A": "results/al_v47/named/nominal/llm_calls.jsonl",
            "B": "results/al_v47/anon/nominal/llm_calls.jsonl", "C": "results/al_v47/shuffled/nominal/llm_calls.jsonl"}


def llm():
    ab = jload("results/summary/v47_rq3_ablation.json")
    calls = []
    for cond, rel in LLM_LOGS.items():
        for r in jlines(rel):
            item = dict(k=cond, s=int(r["seed"]), r=int(r["round"]), ok=r["validator_status"] == "accepted",
                        rej=r.get("reject_reason"), rc=r.get("reason_codes") or [], why=r.get("short_rationale") or "",
                        lat=sig(r.get("latency_s"), 3), tin=r.get("input_tokens"), tout=r.get("output_tokens"),
                        sel=r.get("selected_ids") or [], model=r.get("model_id"))
            pay = r.get("payload")
            if pay:                                   # what the model was shown (A, B, C; not recorded for A0)
                ms = pay.get("model_summary", {})
                item["worst"] = ms.get("worst_target")
                item["cv"] = ms.get("cv_mae_norm")
                item["cand"] = [[c["candidate_id"], sig(c["predictive_uncertainty"], 4), sig(c["distance_to_train"], 4)]
                                for c in pay["candidates"]]
            tr = r.get("truth")
            if tr and tr.get("variant") == "shuffled":
                item["true_u"] = {k: sig(v, 4) for k, v in tr["true_uncertainty"].items()}
                item["true_d"] = {k: sig(v, 4) for k, v in tr["true_distance"].items()}
                item["true_worst"] = tr.get("true_worst_target")
            calls.append(item)
    calls.sort(key=lambda c: (["A0", "A", "B", "C"].index(c["k"]), c["s"], c["r"]))
    return dict(calls=calls, behaviour=ab["behaviour"])


def headline(r1, ph, sel, ll, ov):
    c = r1["contrast"]["mean"]
    s = r1["rho_cases"]["0.0"]["sets"]
    acc = sum(x["ok"] for x in ll["calls"])
    ni = [x for x in sel["ninit"] if x["n_init"] == 60 and x["policy"] == "uncertainty"]
    return dict(S1=s["S1"]["mean"], S1x2=s["S1x2"]["mean"], S2=s["S2"]["mean"], gain=c["delta"], gain_ci=c["ci"],
                g0=ph["scenarios"]["gamma0"]["nominal"]["mean"], gm1=ph["scenarios"]["gamma_m1"]["nominal"]["mean"],
                u_rand=sel["seedstats"]["U-random"]["delta"], u_rand_ci=sel["seedstats"]["U-random"]["boot95"],
                saving=ni[0]["saving_pct"] if ni else None, llm_ok=acc, llm_n=len(ll["calls"]),
                runs=ov["total"], conv=ov["converged"], rt=ov["median_runtime_s"])


def provenance():
    out = []
    for rel, p in sorted(READ.items()):
        if p.is_dir():
            files = sorted(p.glob("*.json"))
            h = hashlib.sha256()
            for f in files:
                h.update(f.name.encode()); h.update(f.read_bytes())
            out.append(dict(path=rel, size=sum(f.stat().st_size for f in files), files=len(files), sha=h.hexdigest()[:12]))
        else:
            b = p.read_bytes()
            out.append(dict(path=rel, size=len(b), files=1, sha=hashlib.sha256(b).hexdigest()[:12]))
    return out


# ----------------------------------------------------------------------------- page
def build(embed_plotly: bool, fragment: bool) -> str:
    data = dict(meta=meta())
    data["overview"] = runs_overview()
    data["device"] = device()
    data["rq1"] = rq1()
    data["physics"] = physics()
    data["selection"] = selection()
    data["llm"] = llm()
    data["headline"] = headline(data["rq1"], data["physics"], data["selection"], data["llm"], data["overview"])
    data["sources"] = provenance()
    blob = json.dumps(tidy(data), ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    blob = blob.replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026")   # safe inside <script>
    tpl = (ROOT / "scripts" / "report_template.html").read_text(encoding="utf-8")
    if embed_plotly:
        try:
            from plotly.offline import get_plotlyjs
        except ImportError as e:
            raise SystemExit("--embed-plotly needs the plotly package: pip install -r requirements-viz.txt") from e
        lib = "<script>" + get_plotlyjs().replace("</script", "<\\/script") + "</script>"
    else:
        lib = f'<script src="{PLOTLY_CDN}"></script>'
    html = tpl.replace("__PLOTLY__", lib).replace("__DATA__", blob)
    if fragment:                                   # page content only (for hosts that add their own skeleton)
        html = re.sub(r"(?is)^.*?<!--\s*BEGIN PAGE\s*-->", "", html)
        html = re.sub(r"(?is)<!--\s*END PAGE\s*-->.*$", "", html)
        html = re.sub(r"(?s)<!--\s*HEAD/BODY\s*-->.*?<!--\s*/HEAD/BODY\s*-->", "", html)
    return html


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default=str(ROOT / "docs" / "report" / "index.html"))
    ap.add_argument("--embed-plotly", action="store_true", help="inline plotly.js (offline viewing)")
    ap.add_argument("--fragment", action="store_true", help="write the page body only, without <html>/<head>")
    a = ap.parse_args()
    html = build(a.embed_plotly, a.fragment)
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    print(f"wrote {out} ({out.stat().st_size / 1e6:.2f} MB, {len(READ)} sources)")


if __name__ == "__main__":
    main()
