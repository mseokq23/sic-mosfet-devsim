"""Data files for the interactive results page in site/ (GitHub Pages), built from the committed result files.
No DEVSIM runs and no API calls. Two things are fitted here, both from committed data only:
  - the GP inverse model of the paper (sicsim.analysis, same frozen noise realisation) -> per-device estimates,
    plus four further noise realisations for the page's 'draw the noise again' control;
  - a GP surrogate of the DEVSIM I-V curves over the four process variables (pool devices with complete curves) for the sliders
    at the top of the page. It is a visual aid only and is not used for any result.
  python scripts/make_site.py                     -> site/data/*.js  (about 2 min on one core)
  python scripts/make_site.py --only core llm     -> selected files only
Every data file sets one property of window.SITE, so the page also opens from file:// without a web server."""
from __future__ import annotations

import argparse
import ast
import json
import math
import shutil
import subprocess
import sys
import textwrap
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from sicsim.analysis import fit_predict, wide_table  # noqa: E402
from sicsim.config import _Loader  # noqa: E402
from sicsim.controls import control_feature_set, noisy_tables, replicate_seeds  # noqa: E402
from sicsim.design import NUISANCE, VARS, load_bounds  # noqa: E402

OUT = ROOT / "site" / "data"
REPO = "https://github.com/mseokq23/sic-mosfet-devsim"
P4 = VARS + NUISANCE                                   # wjfet_scale, npwell_scale, qit_eff_cm2, mu_channel_scale
TEMPS = (300, 423)
VARIANTS = ["gamma0", "gamma_m1", "qitT10", "qitT30"]
SETS = ["S1", "S1x2", "S2"]
LOG_FLOOR = -12.0                                      # transfer curves are drawn from 1e-12 A/cm up
VDS_GRID = [0.1, 0.2, 0.3, 0.4, 0.5, 1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0, 4.5, 5.0]
FEATURE_VGS = [4, 5, 6, 7, 8, 10, 12, 14, 16, 18, 20]
N_DRAWS = 5                                            # noise realisations for the estimates (k = 0 is the paper's)


# ------------------------------------------------------------------------------------------------ helpers
def git(*args) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True).stdout.strip()


def rn(x, nd=4):
    """Round to nd decimals; NaN/inf -> None (JSON null)."""
    if x is None:
        return None
    x = float(x)
    return None if not math.isfinite(x) else round(x, nd)


def sg(x, n=4):
    """Round to n significant digits; NaN/inf -> None."""
    if x is None:
        return None
    x = float(x)
    if not math.isfinite(x):
        return None
    if x == 0:
        return 0.0
    return float(f"{x:.{n - 1}e}")


def rl(a, nd=4):
    return [rn(v, nd) for v in a]


def jread(rel):
    return json.load(open(ROOT / rel, encoding="utf-8"))


def write_js(name: str, obj) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    p = OUT / f"{name}.js"
    body = json.dumps(obj, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    p.write_text(f"window.SITE=window.SITE||{{}};window.SITE.{name}={body};\n", encoding="utf-8")
    return p


def noise_cfg():
    return yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader)


def bounds_arrays():
    b = load_bounds()
    lo = np.array([b["variables"][v]["low"] if v in b["variables"] else b["nuisance"][v]["low"] for v in P4])
    hi = np.array([b["variables"][v]["high"] if v in b["variables"] else b["nuisance"][v]["high"] for v in P4])
    return b, lo, hi


def to_unit(df: pd.DataFrame) -> np.ndarray:
    _, lo, hi = bounds_arrays()
    return (df[P4].values.astype(float) - lo) / (hi - lo)


def transfer_log(d: dict) -> list:
    """log10 I_D of the transfer curve; samples under the solver current floor are None (not drawn)."""
    t = d["curves"]["transfer"]
    i = np.asarray(t["id"], float)
    floor = d["features"].get("kcl_floor_A_per_cm") or 0.0
    return [rn(np.log10(v), 3) if v > floor and v > 0 else None for v in i]


def output_on_grid(d: dict) -> list:
    """Output curve on the standard V_DS grid (refined sweeps carry extra points; early stops leave None)."""
    o = d["curves"]["output"]
    x, y = np.asarray(o["vds"], float), np.asarray(o["id"], float)
    out = []
    for v in VDS_GRID:
        j = np.flatnonzero(np.isclose(x, v, atol=1e-9))
        if len(j):
            out.append(sg(y[j[0]], 4))
        elif x.min() <= v <= x.max():
            out.append(sg(np.interp(v, x, y), 4))
        else:
            out.append(None)
    return out


def run_json(rel: str) -> dict:
    return jread(rel)


# ------------------------------------------------------------------------------------------------ meta, design
def meta() -> dict:
    commit = git("rev-parse", "HEAD")
    dirty = git("status", "--porcelain", "--", "src", "configs", "results")
    return dict(repo=REPO, commit=commit, short=commit[:7], date=git("log", "-1", "--format=%cs"), dirty=bool(dirty),
                pages="https://mseokq23.github.io/sic-mosfet-devsim/")


def design() -> dict:
    b, lo, hi = bounds_arrays()
    spec = {**b["variables"], **b["nuisance"]}
    cfg = yaml.load(open(ROOT / "configs/baseline.yaml"), Loader=_Loader)
    g = cfg["mosfet"]["geometry"]
    pts = {}
    for name in ("pool", "test"):
        d = pd.read_csv(ROOT / f"configs/design_{name}.csv")
        pts[name] = dict(id=d.candidate_id.tolist(), u=[rl(r, 4) for r in to_unit(d)])
    return dict(
        vars=P4,
        bounds={v: dict(low=spec[v]["low"], high=spec[v]["high"], nominal=spec[v]["nominal"]) for v in P4},
        points=pts,
        geometry={k: g[k] for k in ("tox_um", "x_pp_um", "d_pp_um", "x_ns0_um", "x_ns1_um", "d_ns_um", "x_pw_um",
                                    "d_pw_um", "wjfet_um", "d_jfet_um", "t_drift_um", "t_sub_um", "x_src_contact_um",
                                    "x_ox_start_um")},
    )


def stage_a() -> dict:
    """One-at-a-time runs (design centre and +-10/20 %) and their feature changes (stage_a_deltas.csv)."""
    names = ["base"] + [f"{p}_{lv}" for p in ("wjfet", "npwell", "qit", "mu")
                        for lv in ("-20pct", "-10pct", "+10pct", "+20pct")]
    runs = {}
    vgs = None
    for n in names:
        for T in TEMPS:
            d = run_json(f"results/stage_a/runs/A_{n}_T{T}.json")
            vgs = d["curves"]["transfer"]["vgs"]
            f = d["features"]
            runs[f"{n}@{T}"] = dict(t=transfer_log(d), o=output_on_grid(d), vth=rn(f["vth_V"], 4),
                                    ron=rn(f["ron_mohm_cm2"], 4), ss=rn(f["ss_mV_dec"], 2))
    dl = pd.read_csv(ROOT / "results/stage_a/stage_a_deltas.csv")
    feats = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2"]
    deltas = [dict(T=int(r["T"]), var=r["var"], level=r["level"], **{f: rn(r[f], 5) for f in feats}) for _, r in dl.iterrows()]
    return dict(vgs=vgs, vds=VDS_GRID, runs=runs, deltas=deltas)


def runs_table(name: str) -> pd.DataFrame:
    d = pd.read_csv(ROOT / f"results/{name}/runs.csv")
    return d[d["converged"].astype(str).str.lower() == "true"].copy()


def features() -> dict:
    """Per device and temperature: V_th, SS, g_m,max, I_on, R_on,sp and the 11 transfer samples (pool + test)."""
    out = {}
    for name in ("pool", "test"):
        d = runs_table(name)
        rec = {}
        for T in TEMPS:
            s = d[np.isclose(d.temperature_K, T)].set_index("candidate_id").sort_index()
            rec[T] = s
        ids = sorted(set(rec[300].index) & set(rec[423].index))
        out[name] = dict(id=ids, **{
            str(T): dict(vth=rl(rec[T].loc[ids, "vth_V"], 4), ss=rl(rec[T].loc[ids, "ss_mV_dec"], 2),
                         gm=rl(rec[T].loc[ids, "gm_max_S_per_cm"] * 1e3, 4),
                         ron=rl(rec[T].loc[ids, "ron_mohm_cm2"], 4),
                         ion=rl(rec[T].loc[ids, "ion_A_per_cm"] * 1e3, 4),
                         logid=[rl(r, 3) for r in rec[T].loc[ids, [f"logid_vg{v}" for v in FEATURE_VGS]].values])
            for T in TEMPS})
    out["feature_vgs"] = FEATURE_VGS
    return out


# ------------------------------------------------------------------------------------------------ I-V curves (lazy file)
def iv() -> dict:
    out = dict(vds=VDS_GRID)
    for name in ("pool", "test"):
        ids = pd.read_csv(ROOT / f"configs/design_{name}.csv").candidate_id.tolist()
        rec = {}
        for cid in ids:
            r = {}
            for T in TEMPS:
                p = ROOT / f"results/{name}/runs/{cid}_T{T}.json"
                d = json.load(open(p, encoding="utf-8"))
                out.setdefault("vgs", d["curves"]["transfer"]["vgs"])
                r[str(T)] = dict(t=transfer_log(d), o=output_on_grid(d)) if d.get("converged") else None
            rec[cid] = r
        out[name] = rec
    var = {}
    for v in VARIANTS:
        rec = {}
        for cid in pd.read_csv(ROOT / "configs/design_test.csv").candidate_id:
            p = ROOT / f"results/test_{v}/runs/{cid}_T423.json"
            if p.exists():
                d = json.load(open(p, encoding="utf-8"))
                if d.get("converged"):
                    rec[cid] = dict(t=transfer_log(d), o=output_on_grid(d))
        var[v] = rec
    out["variants423"] = var
    return out


# ------------------------------------------------------------------------------------------------ surrogate (hero sliders)
def _gp_group(U, Y, n_comp, seed=0):
    """PCA of Y (n, m) -> GP (anisotropic RBF) on the leading scores; returns the exportable model and a predictor."""
    from sklearn.gaussian_process import GaussianProcessRegressor
    from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
    mean = Y.mean(0)
    Yc = Y - mean
    _, s, Vt = np.linalg.svd(Yc, full_matrices=False)
    k = int(min(n_comp, len(s)))
    comp = Vt[:k]
    Z = Yc @ comp.T
    kern = ConstantKernel(1.0, (1e-3, 1e3)) * RBF([0.5] * U.shape[1], (1e-2, 1e2)) + WhiteKernel(1e-5, (1e-9, 1e-1))
    gp = GaussianProcessRegressor(kern, normalize_y=True, n_restarts_optimizer=2, random_state=seed).fit(U, Z)
    kp = gp.kernel_.get_params()
    amp = float(kp["k1__k1__constant_value"])
    ls = np.atleast_1d(kp["k1__k2__length_scale"]).astype(float)
    alpha = np.asarray(gp.alpha_).reshape(len(U), -1)
    ymu = np.atleast_1d(gp._y_train_mean).astype(float)
    ysd = np.atleast_1d(gp._y_train_std).astype(float)

    def predict(Unew):
        d = (Unew[:, None, :] - U[None, :, :]) / ls
        K = amp * np.exp(-0.5 * (d ** 2).sum(-1))
        z = (K @ alpha) * ysd + ymu
        return mean + z @ comp

    model = dict(amp=sg(amp, 8), ls=[sg(v, 8) for v in ls], alpha=[[sg(v, 8) for v in row] for row in alpha],
                 ymu=[sg(v, 8) for v in ymu], ysd=[sg(v, 8) for v in ysd], mean=[sg(v, 6) for v in mean],
                 comp=[[sg(v, 6) for v in row] for row in comp])
    return model, predict, gp


def surrogate() -> tuple[dict, dict]:
    """GP surrogate of the transfer (log10 I_D), output (I_D) curves and four features at 300 and 423 K."""
    pool = pd.read_csv(ROOT / "configs/design_pool.csv").set_index("candidate_id")
    test = pd.read_csv(ROOT / "configs/design_test.csv").set_index("candidate_id")
    groups = {}
    for name, design_ in (("pool", pool), ("test", test)):
        rows = {f"t{T}": [] for T in TEMPS} | {f"o{T}": [] for T in TEMPS} | {f"f{T}": [] for T in TEMPS}
        ids = []
        for cid in design_.index:
            recs = {}
            for T in TEMPS:
                d = json.load(open(ROOT / f"results/{name}/runs/{cid}_T{T}.json", encoding="utf-8"))
                if not d.get("converged"):
                    break
                recs[T] = d
            if len(recs) < 2:
                continue
            ok = True
            for T, d in recs.items():
                t = np.asarray(d["curves"]["transfer"]["id"], float)
                o = output_on_grid(d)
                if any(v is None for v in o):
                    ok = False
                    break
                rows[f"t{T}"].append(np.log10(np.clip(t, 10 ** LOG_FLOOR, None)))
                rows[f"o{T}"].append(np.asarray(o, float))
                f = d["features"]
                rows[f"f{T}"].append([f["vth_V"], f["ss_mV_dec"], np.log10(f["gm_max_S_per_cm"]),
                                      np.log10(f["ron_mohm_cm2"])])
            if ok:
                ids.append(cid)
        groups[name] = (ids, {k: np.array(v[:len(ids)]) for k, v in rows.items()})
    ids_p, Yp = groups["pool"]
    ids_t, Yt = groups["test"]
    Up, Ut = to_unit(pool.loc[ids_p]), to_unit(test.loc[ids_t])
    ncomp = {"t": 10, "o": 6, "f": 4}
    models, check = {}, {}
    for key in Yp:
        m, pred, _ = _gp_group(Up, Yp[key], ncomp[key[0]])
        models[key] = m
        P = pred(Ut)
        check[key] = P
    # validation on the 128 test devices (never used for fitting)
    val = {}
    for T in TEMPS:
        F, Fh = Yt[f"f{T}"], check[f"f{T}"]
        val[str(T)] = dict(
            vth_mV_median=rn(np.median(np.abs(Fh[:, 0] - F[:, 0])) * 1e3, 1),
            vth_mV_p95=rn(np.percentile(np.abs(Fh[:, 0] - F[:, 0]), 95) * 1e3, 1),
            ron_pct_median=rn(np.median(np.abs(10 ** (Fh[:, 3] - F[:, 3]) - 1)) * 100, 2),
            logid_rmse=rn(np.sqrt(np.mean((check[f"t{T}"] - Yt[f"t{T}"])[Yt[f"t{T}"] > -11] ** 2)), 3))
    nominal = to_unit(pd.DataFrame([{v: (-1.0e12 if v == "qit_eff_cm2" else 1.0) for v in P4}]))[0]
    return dict(train_u=[rl(r, 5) for r in Up], models=models, n_train=len(ids_p), n_test=len(ids_t),
                validation=val, nominal_u=rl(nominal, 5), log_floor=LOG_FLOOR), dict(Up=Up, models=models)


# ------------------------------------------------------------------------------------------------ inverse estimates
def estimates() -> dict:
    """GP inverse model (as in scripts/repeat_control.py, rho = 0): estimates of every test device for S1, S1x2, S2
    at the nominal and the 2x noise level, for the frozen noise realisation (k = 0) and four more (k = 1..4)."""
    nz = noise_cfg()
    fl = nz.get("current_floor_A_per_cm")
    pool_w = wide_table(pd.read_csv(ROOT / "results/pool/runs.csv")).sort_index()
    test_w = wide_table(pd.read_csv(ROOT / "results/test/runs.csv")).sort_index()
    b, lo, hi = bounds_arrays()
    lo3, hi3 = lo[:3], hi[:3]
    truth = (test_w[VARS].values - lo3) / (hi3 - lo3)
    pts = pd.read_csv(ROOT / "results/summary/repeat_control_points.csv")
    est, err_check = {}, {}
    for level in ("nominal", "high"):
        lv = nz["levels"][level]
        for k in range(N_DRAWS):
            sp, st = replicate_seeds(nz["seeds"]["pool"], k), replicate_seeds(nz["seeds"]["test"], k)
            p1, p2 = noisy_tables(pool_w, nz, lv, sp[0], 0.0, 0.0, floor=fl, repeat_seed=sp[1])
            t1, t2 = noisy_tables(test_w, nz, lv, st[0], 0.0, 0.0, floor=fl, repeat_seed=st[1])
            for S in SETS:
                P = fit_predict(control_feature_set(p1, p2, S).values, pool_w[VARS].values,
                                control_feature_set(t1, t2, S).values, "gp", 0)
                U = (P - lo3) / (hi3 - lo3)
                est[f"{level}|{k}|{S}"] = [rl(r, 4) for r in U]
                if k == 0:                                     # must equal the committed per-device errors
                    ref = pts[(pts.level == level) & np.isclose(pts.rho, 0) & (pts.model == "gp") & (pts.set == S)]
                    ref = ref.set_index("candidate_id").loc[test_w.index, [f"err_{v}" for v in VARS]].values
                    err_check[f"{level}|{S}"] = float(np.abs(np.abs(U - truth) - ref).max())
    return dict(ids=list(test_w.index), truth=[rl(r, 4) for r in truth], est=est, draws=N_DRAWS,
                check_max_abs_diff=err_check)


# ------------------------------------------------------------------------------------------------ RQ1 summaries
def mean_ci(E, n=2000, seed=7):
    """Column means and 95 % CI over test devices (bootstrap seed 7, 2000 resamples, as the README figures)."""
    E = np.asarray(E, float)
    bi = np.random.default_rng(seed).integers(0, len(E), (n, len(E)))
    lo, hi = np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0)
    return E.mean(0), lo, hi


def rq1() -> dict:
    pts = pd.read_csv(ROOT / "results/summary/repeat_control_points.csv")
    errc = [f"err_{v}" for v in VARS]
    bars = {}
    for (level, rho, model), g in pts.groupby(["level", "rho", "model"]):
        rec = {}
        for S, s in g.groupby("set"):
            E = s.sort_values("candidate_id")[errc].values
            E = np.column_stack([E, E.mean(1)])
            m, lo, hi = mean_ci(E)
            rec[S] = dict(mean=rl(m, 4), lo=rl(lo, 4), hi=rl(hi, 4))
        bars[f"{level}|{rho:g}|{model}"] = rec
    ph = jread("results/summary/posthoc_stats.json")
    budget = {b: {S: dict(points=v["points"], mean=rn(v["mean"], 4), sd=rn(v["sd"], 4)) for S, v in rec.items()}
              for b, rec in ph["part2"].items()}
    scen = {}
    for s, rec in ph["part1"]["scenarios"].items():
        scen[s] = {k: rn(v["mean"], 4) for k, v in rec.items() if isinstance(v, dict) and "mean" in v}
    ref = {S: rn(v["mean"], 4) for S, v in ph["part1"]["reference"].items()}
    rc = jread("results/summary/repeat_control.json")
    nom = next(c for c in rc["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp")
    series = dict(plain={S: rn(nom["sets"][S]["mean"], 4) for S in ("S1", "S1x2", "S2")},
                  series_r={S: rn(rc["series_r"]["sets"][S]["mean"], 4) for S in ("S1", "S1x2", "S2")})
    return dict(bars=bars, budget=budget, scenarios=scen, reference=ref, series=series, no_information=0.25)


# ------------------------------------------------------------------------------------------------ selection (RQ2, RQ3)
POLICY_SRC = {"random": ("al_ablation/numeric/nominal", "random"), "sobol": ("al_ablation/numeric/nominal", "sobol"),
              "uncertainty": ("al_ablation/numeric/nominal", "uncertainty"),
              "top20_random": ("al_ablation/numeric/nominal", "top20_random"),
              "A0": ("al_live/nominal", "llm"), "A": ("al_ablation/named/nominal", "llm"),
              "B": ("al_ablation/anon/nominal", "llm"), "C": ("al_ablation/shuffled/nominal", "llm")}


def _curves(rel, policy):
    d = pd.read_csv(ROOT / f"results/{rel}/al_curves.csv")
    d = d[d.policy == policy]
    n = sorted(d.n_points.unique())
    seeds = sorted(d.seed.unique())
    piv = d.pivot_table(index="seed", columns="n_points", values="mean_mae_norm").loc[seeds, n]
    return dict(n=[int(v) for v in n], seeds=[[rn(v, 5) for v in row] for row in piv.values],
                mean=rl(piv.mean(axis=0).values, 5), sd=rl(piv.std(axis=0, ddof=1).values, 5))


def selection() -> dict:
    curves = {k: _curves(*v) for k, v in POLICY_SRC.items()}
    levels = {}
    for lvl in ("none", "nominal", "high"):
        levels[lvl] = {p: _curves(f"al/{lvl}", p) for p in ("random", "sobol", "uncertainty")}
    p3 = jread("results/summary/posthoc_stats.json")["part3"]
    keys = [("U-random", "uncertainty", "random"), ("sobol-random", "sobol", "random"), ("U-sobol", "uncertainty", "sobol"),
            ("D-U", "top20_random", "uncertainty"), ("A0-U", "A0", "uncertainty"), ("A-U", "A", "uncertainty"),
            ("B-U", "B", "uncertainty"), ("C-U", "C", "uncertainty")]
    diffs = []
    for k, a, b in keys:
        r = p3[f"final:{k}"]
        diffs.append(dict(key=k, a=a, b=b, delta=rn(r["delta"], 6), lo=rn(r["boot95"][0], 6), hi=rn(r["boot95"][1], 6),
                          wins=int(r["wins"]), n=10))
    ab = jread("results/summary/rq3_ablation.json")
    return dict(curves=curves, levels=levels, diffs=diffs, sesoi=ab["meta"]["sesoi"])


def llm() -> dict:
    """LLM calls of conditions A (named), B (anonymised) and C (shuffled): what was shown, what was chosen, and the
    training set at that round (the seed's random initial 60 + the batches chosen before). The batch of the fallback
    rule after a rejected response is not logged (and the forest behind it is CPU dependent), so later rounds of that
    seed carry 'missing' = number of training devices that cannot be listed."""
    pool = pd.read_csv(ROOT / "configs/design_pool.csv").set_index("candidate_id").sort_index()
    ids = list(pool.index)
    U = pd.DataFrame(to_unit(pool), index=pool.index, columns=P4)
    meta_ = jread("results/al_ablation/named/nominal/meta.json")
    n_init = int(meta_.get("n_init", 60))
    init = {s: list(np.random.default_rng(s).choice(ids, n_init, replace=False)) for s in range(10)}
    anon = {"x1": P4[0], "x2": P4[1], "x3": P4[2], "x4": P4[3]}
    out = dict(pool_u={c: rl(U.loc[c].values, 3) for c in ids}, init=init, conditions={}, n_init=n_init)
    dist_check = 0.0
    for cond, rel in (("A", "named"), ("B", "anon"), ("C", "shuffled")):
        calls = [json.loads(line) for line in open(ROOT / f"results/al_ablation/{rel}/nominal/llm_calls.jsonl", encoding="utf-8")]
        calls.sort(key=lambda r: (r["seed"], r["round"]))
        chosen_before: dict[int, list] = {}
        recs = []
        for r in calls:
            p = r["payload"]
            ms = p["model_summary"]
            cands = []
            for c in p["candidates"]:
                c = {anon.get(k, k): v for k, v in c.items()}
                cands.append(dict(id=c["candidate_id"], unc=c["predictive_uncertainty"], dist=c["distance_to_train"]))
            rec = dict(seed=r["seed"], round=r["round"], status=r["validator_status"], reject=r.get("reject_reason"),
                       selected=r["selected_ids"], reasons=r["reason_codes"], rationale=r["short_rationale"],
                       tin=r["input_tokens"], tout=r["output_tokens"], latency=r["latency_s"],
                       n_train=ms["n_train"], cv={anon.get(k, k): v for k, v in ms["cv_mae_norm"].items()},
                       worst=anon.get(ms["worst_target"], ms["worst_target"]), cands=cands)
            true_ud = {c["id"]: (c["unc"], c["dist"]) for c in cands}
            if cond == "C" and r.get("truth"):
                t = r["truth"]
                rec["true"] = {c["id"]: [t["true_uncertainty"][c["id"]], t["true_distance"][c["id"]]] for c in cands}
                rec["true_worst"] = t.get("true_worst_target")
                true_ud = {k: tuple(v) for k, v in rec["true"].items()}
            train = init[r["seed"]] + chosen_before.get(r["seed"], [])
            missing = ms["n_train"] - len(train)
            tu = U.loc[train].values
            for cid, (_, dd) in true_ud.items():
                dmin = np.sqrt(((tu - U.loc[cid].values) ** 2).sum(1)).min()
                if missing == 0:                            # complete training set: must reproduce the logged distances
                    dist_check = max(dist_check, abs(dmin - dd))
                elif dmin < dd - 5e-5:                      # incomplete: listed devices can only be farther
                    raise SystemExit(f"LLM replay {cond} seed {r['seed']} round {r['round']}: distance check")
            if missing:
                rec["missing"] = int(missing)
            chosen_before[r["seed"]] = chosen_before.get(r["seed"], []) + (r["selected_ids"] or [])
            recs.append(rec)
        out["conditions"][cond] = recs
    out["dist_check_max_abs"] = rn(dist_check, 6)
    from sicsim.llm import SYSTEM_PROMPT
    out["system_prompt"] = SYSTEM_PROMPT.format(k=10)
    return out


# ------------------------------------------------------------------------------------------------ code excerpts
CODE = [  # (section, file, object name, short label)
    ("design", "src/sicsim/design.py", "sobol_pool", "후보 풀: Sobol 설계"),
    ("design", "src/sicsim/devices.py", "dmosfet_geometry", "JFET 폭 변화(셀 피치 고정)"),
    ("data", "src/sicsim/simulate.py", "run_mosfet", "DEVSIM 바이어스 스윕(전달·출력 특성)"),
    ("data", "src/sicsim/extract.py", "vth_constant_current", "V_th 추출(정전류)"),
    ("data", "src/sicsim/extract.py", "extract_features", "특징 17개 추출"),
    ("estimate", "src/sicsim/analysis.py", "add_noise", "측정 잡음"),
    ("estimate", "src/sicsim/controls.py", "control_feature_set", "S1·S1×2·S2 특징 세트"),
    ("estimate", "src/sicsim/analysis.py", "make_model", "역추정 모델(GP·RF·Ridge)"),
    ("estimate", "src/sicsim/analysis.py", "fit_predict", "학습과 예측"),
    ("select", "src/sicsim/alsim.py", "run_policy", "표본 선택 루프"),
    ("select", "src/sicsim/alsim.py", "diverse_top", "불확실도 정책"),
    ("select", "src/sicsim/schema.py", "validate_selection", "LLM 응답 검증"),
]


_KC = {"True", "False", "None"}
_OW = {"and", "or", "not", "in", "is"}
_PUNCT = set("()[]{},:.;")


def highlight_py(text: str) -> str:
    """Python source -> HTML with token classes (k, kc, ow, nf, nc, nd, nb, s, c1, m, o; punctuation plain), standard
    library only. Stripping the tags and unescaping gives the source text back exactly (checked by the tests)."""
    import builtins
    import html
    import io
    import keyword
    import tokenize
    starts = [0]
    for line in text.splitlines(keepends=True):
        starts.append(starts[-1] + len(line))
    fstr = {getattr(tokenize, n) for n in ("FSTRING_START", "FSTRING_MIDDLE", "FSTRING_END") if hasattr(tokenize, n)}
    out, pos, prev = [], 0, None
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type == tokenize.ENDMARKER:
            break
        a = starts[tok.start[0] - 1] + tok.start[1]
        b = starts[tok.end[0] - 1] + tok.end[1]
        if a < pos:                                     # zero-width or overlapping tokens (dedent, f-string parts)
            continue
        out.append(html.escape(text[pos:a], quote=False))
        t, cls = text[a:b], None
        if tok.type == tokenize.NAME:
            if t in _KC:
                cls = "kc"
            elif t in _OW:
                cls = "ow"
            elif keyword.iskeyword(t):
                cls = "k"
            elif prev == "def":
                cls = "nf"
            elif prev == "class":
                cls = "nc"
            elif prev == "@":
                cls = "nd"
            elif hasattr(builtins, t):
                cls = "nb"
        elif tok.type == tokenize.STRING or tok.type in fstr:
            cls = "s"
        elif tok.type == tokenize.COMMENT:
            cls = "c1"
        elif tok.type == tokenize.NUMBER:
            cls = "m"
        elif tok.type == tokenize.OP and t not in _PUNCT:
            cls = "nd" if t == "@" and (prev is None or prev in ("\n", "")) else "o"
        esc = html.escape(t, quote=False)
        out.append(f'<span class="{cls}">{esc}</span>' if cls and t.strip() else esc)
        if tok.type not in (tokenize.NL, tokenize.NEWLINE, tokenize.INDENT, tokenize.DEDENT, tokenize.COMMENT):
            prev = t
        elif tok.type in (tokenize.NL, tokenize.NEWLINE):
            prev = "\n"
        pos = b
    out.append(html.escape(text[pos:], quote=False))
    return "".join(out)


def code() -> dict:
    commit = git("rev-parse", "HEAD")
    items = []
    for section, rel, name, label in CODE:
        src = (ROOT / rel).read_text(encoding="utf-8")
        node = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, (ast.FunctionDef, ast.ClassDef))
                    and n.name == name)
        start = min([d.lineno for d in getattr(node, "decorator_list", [])] + [node.lineno])
        text = textwrap.dedent("\n".join(src.splitlines()[start - 1:node.end_lineno]))
        items.append(dict(section=section, file=rel, name=name, label=label, start=start, end=node.end_lineno,
                          html=highlight_py(text), url=f"{REPO}/blob/{commit}/{rel}#L{start}-L{node.end_lineno}"))
    return dict(items=items)


# ------------------------------------------------------------------------------------------------ main
PARTS = ["core", "surrogate", "iv", "estimates", "llm", "code"]


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", nargs="*", choices=PARTS)
    a = ap.parse_args()
    todo = a.only if a.only is not None else PARTS
    if "core" in todo:
        p = write_js("core", dict(meta=meta(), design=design(), stage_a=stage_a(), features=features(), rq1=rq1(),
                                  selection=selection()))
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB")
        img = ROOT / "site" / "assets" / "img"
        img.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(ROOT / "paper/figures/fig2_validation.png", img / "fig2_validation.png")
    if "surrogate" in todo:
        s, _ = surrogate()
        p = write_js("surrogate", s)
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB", "validation:", s["validation"])
    if "iv" in todo:
        p = write_js("iv", iv())
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB")
    if "estimates" in todo:
        e = estimates()
        p = write_js("estimates", e)
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB", "check vs committed errors:", e["check_max_abs_diff"])
    if "llm" in todo:
        L = llm()
        p = write_js("llm", L)
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB", "distance check:", L["dist_check_max_abs"])
    if "code" in todo:
        p = write_js("code", code())
        print(p.name, f"{p.stat().st_size / 1024:.0f} KB")


if __name__ == "__main__":
    main()
