"""Audit of DOE results: provenance, design<->run match, re-extraction, physics consistency, outliers.
  python scripts/audit_results.py results/pool configs/design_pool.csv [results/test configs/design_test.csv]
Writes <out>/audit.json. A second (out, design) pair is also checked against a surrogate fitted on the first."""
import json, sys
from itertools import combinations_with_replacement
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import load_config
from sicsim.extract import extract_features
from sicsim.design import DESIGN_VARS

Q, EPS0, EPS_OX = 1.602176634e-19, 8.8541878128e-14, 3.9
FEATS = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"]
LOGF = {"gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"}


def load(out):
    return {p.stem: json.load(open(p)) for p in sorted(Path(out, "runs").glob("*.json")) if not p.name.endswith(".job.json")}


def provenance(recs, design):
    rep, bad = {}, []
    for _, r in design.iterrows():
        for T in (300, 423):
            rid = f"{r.candidate_id}_T{T}"
            if rid not in recs:
                bad.append(f"missing {rid}"); continue
            x = recs[rid]
            for v in DESIGN_VARS:
                if not np.isclose(float(x[v]), float(r[v]), rtol=0, atol=abs(float(r[v])) * 1e-12):
                    bad.append(f"{rid}: {v} {x[v]} != design {r[v]}")
            if float(x["temperature_K"]) != T:
                bad.append(f"{rid}: T mismatch")
    rep["n_design"], rep["n_runs"] = len(design), len(recs)
    rep["extra_runs"] = sorted(set(recs) - {f"{c}_T{T}" for c in design.candidate_id for T in (300, 423)})
    rep["mismatches"] = bad[:20]; rep["n_mismatches"] = len(bad)
    for k in ("config_version", "physics_hash", "solver_hash", "mesh_scale", "extended", "holes", "code_commit"):
        rep[k] = sorted({str(x.get(k)) for x in recs.values()})
    rep["devsim"] = sorted({str((x.get("env") or {}).get("devsim")) for x in recs.values()})
    rep["converged_all"] = all(x.get("converged") for x in recs.values())
    return rep


def reextract(recs, cfg):
    worst = {}
    for rid, x in recs.items():
        f = extract_features(x, cfg)
        for k in FEATS + [c for c in f if c.startswith("logid_vg")]:
            a, b = x["features"].get(k), f.get(k)
            d = 0.0 if (a == b or (a is not None and b is not None and np.isnan(a) and np.isnan(b))) else abs(a - b) / max(abs(b), 1e-30)
            worst[k] = max(worst.get(k, 0.0), d)
    return {k: float(v) for k, v in worst.items()}


def poly(X, deg=3):
    cols = [np.ones(len(X))]
    for d in range(1, deg + 1):
        for c in combinations_with_replacement(range(X.shape[1]), d):
            cols.append(np.prod(X[:, c], axis=1))
    return np.column_stack(cols)


def table(recs):
    rows = []
    for rid, x in recs.items():
        r = {v: float(x[v]) for v in DESIGN_VARS}
        r.update(run_id=rid, candidate_id=x["candidate_id"], T=float(x["temperature_K"]), retry=int(x.get("retry_count", 0)),
                 vds_reached=float(x["features"].get("vds_reached_V", np.nan)))
        for k in FEATS:
            r[k] = np.log10(x["features"][k]) if k in LOGF else x["features"][k]
        rows.append(r)
    return pd.DataFrame(rows)


def norm(df):
    lo = {"wjfet_scale": 0.8, "npwell_scale": 0.8, "qit_eff_cm2": -1.5e12, "mu_channel_scale": 0.8}
    hi = {"wjfet_scale": 1.2, "npwell_scale": 1.2, "qit_eff_cm2": -0.5e12, "mu_channel_scale": 1.2}
    return np.column_stack([(df[v] - lo[v]) / (hi[v] - lo[v]) * 2 - 1 for v in DESIGN_VARS])


def physics(df, cfg):
    tox = cfg["mosfet"]["geometry"]["tox_um"] * 1e-4
    slope_theory = -Q * tox / (EPS_OX * EPS0)                     # dVth/dQit [V cm^2] (Qit signed, cm^-2)
    out = {"dVth_dQit_theory_V_per_1e12": slope_theory * 1e12}
    for T in (300, 423):
        s = df[df["T"] == T]
        others = poly(norm(s)[:, [0, 1, 3]], 4)                    # flexible in wjfet, npwell, mu
        A = np.column_stack([others, s["qit_eff_cm2"].values / 1e12])
        for k in ("vth_V", "ss_mV_dec"):
            c, *_ = np.linalg.lstsq(A, s[k].values, rcond=None)
            res = s[k].values - A @ c
            out[f"{k}@{T}"] = dict(qit_coef_per_1e12=float(c[-1]), resid_rms=float(res.std()), resid_max=float(np.abs(res).max()))
    w = df.pivot_table(index="candidate_id", columns="T", values="vth_V")
    dv = (w[423] - w[300]).rename("dvth")
    m = df[df["T"] == 300].set_index("candidate_id")[DESIGN_VARS].join(dv)
    out["dVth_T_corr"] = {v: float(np.corrcoef(m[v], m["dvth"])[0, 1]) for v in DESIGN_VARS}
    out["dVth_T_range"] = [float(m.dvth.min()), float(m.dvth.max())]
    return out


def surrogate(train, test=None, deg=3):
    rep, flags = {}, []
    for T in (300, 423):
        a = train[train["T"] == T]
        Xa = poly(norm(a), deg)
        for k in FEATS:
            c, *_ = np.linalg.lstsq(Xa, a[k].values, rcond=None)
            res = a[k].values - Xa @ c
            mad = 1.4826 * np.median(np.abs(res - np.median(res))) + 1e-15
            z = res / mad
            r = dict(rms=float(res.std()), max_abs_z=float(np.abs(z).max()),
                     retry_mean_abs_z=float(np.abs(z[a.retry.values > 0]).mean()) if (a.retry > 0).any() else None,
                     noretry_mean_abs_z=float(np.abs(z[a.retry.values == 0]).mean()))
            for i in np.where(np.abs(z) > 8)[0]:
                flags.append(dict(run=a.run_id.iloc[i], feature=k, z=float(z[i]), retry=int(a.retry.iloc[i]), vds_reached=float(a.vds_reached.iloc[i])))
            if test is not None:
                b = test[test["T"] == T]
                e = b[k].values - poly(norm(b), deg) @ c
                r.update(test_rms=float(e.std()), test_max_abs=float(np.abs(e).max()), test_max_over_train_rms=float(np.abs(e).max() / (res.std() + 1e-15)))
            rep[f"{k}@{T}"] = r
    return rep, flags


if __name__ == "__main__":
    cfg = load_config()
    out, design = Path(sys.argv[1]), pd.read_csv(sys.argv[2])
    recs = load(out)
    rep = dict(provenance=provenance(recs, design), reextract_max_rel_diff=reextract(recs, cfg))
    df = table(recs)
    rep["physics"] = physics(df, cfg)
    test_df = None
    if len(sys.argv) >= 5:
        trecs = load(sys.argv[3])
        rep["test_provenance"] = provenance(trecs, pd.read_csv(sys.argv[4]))
        rep["test_reextract_max_rel_diff"] = reextract(trecs, cfg)
        test_df = table(trecs)
    rep["surrogate"], rep["outlier_flags"] = surrogate(df, test_df)
    json.dump(rep, open(out / "audit.json", "w"), indent=1, default=str)
    print(json.dumps(rep, indent=1, default=str)[:6000])
