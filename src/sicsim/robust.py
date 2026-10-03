"""Robustness study v1.3: combine baseline 300 K runs with 423 K variant runs, out-of-model
perturbations (parasitic series resistance) and paired S1-vs-S2 evaluation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from .analysis import _lohi, add_noise, censor_floor, feature_set, fit_predict, metrics, wide_table
from .design import VARS, load_bounds
from .extract import gm_max


def combine_runs(base_runs: pd.DataFrame, variant_runs: pd.DataFrame, t_low=300.0, t_high=423.0) -> pd.DataFrame:
    """300 K rows from the frozen baseline + 423 K rows from a variant (300 K physics is identical)."""
    lo = base_runs[np.isclose(base_runs["temperature_K"].astype(float), t_low)]
    hi = variant_runs[np.isclose(variant_runs["temperature_K"].astype(float), t_high)]
    return pd.concat([lo, hi], ignore_index=True)


# ---------- parasitic series resistance (drain-side, first order; out-of-model test only) ----------
def series_linear(i, r_d, vds):
    """Linear-region current with a series resistance r_d (ohm*cm per cm width): I/(1 + I r_d / V_DS)."""
    i = np.asarray(i, float)
    return i / (1.0 + i * r_d / vds)


def fixed_point_current(vds, idd, v_target, r_d, iters=80):
    """Solve I = f(V_target - I r_d) on a tabulated output curve f (monotone)."""
    v = np.concatenate([[0.0], np.asarray(vds, float)]); y = np.concatenate([[0.0], np.asarray(idd, float)])
    f = lambda x: float(np.interp(x, v, y))
    lo, hi = 0.0, f(v_target)
    for _ in range(iters):                      # g(I) = I - f(V - I r) is increasing in I
        mid = 0.5 * (lo + hi)
        if mid - f(v_target - mid * r_d) > 0:
            hi = mid
        else:
            lo = mid
    return 0.5 * (lo + hi)


def apply_series_resistance(runs: pd.DataFrame, runs_dir: Path, rho_mohm: dict, vds_lin=0.1, vds_req=2.0) -> pd.DataFrame:
    """Add a device-specific specific series resistance rho (mOhm*cm^2) to measured features:
    Ron,sp + rho; linear-region currents (Ion, logid samples) and gm via the transfer curve; Id@2V by a
    fixed point on the output curve. Vth/SS (currents <= 1e-4 A/cm, I*R << V_DS) are unchanged."""
    out = runs.copy()
    logcols = [c for c in out.columns if str(c).startswith("logid_vg")]
    for idx, r in out.iterrows():
        if str(r.get("converged")).lower() != "true":
            continue
        rho = float(rho_mohm[r["candidate_id"]])
        rec = json.load(open(Path(runs_dir) / f"{r['run_id']}.json"))
        r_d = rho * 1e-3 / float(rec["width_cm"])                       # ohm*cm (per cm width)
        out.at[idx, "ion_A_per_cm"] = float(series_linear(r["ion_A_per_cm"], r_d, vds_lin))
        for c in logcols:
            if pd.notna(r[c]):
                out.at[idx, c] = float(np.log10(series_linear(10.0 ** r[c], r_d, vds_lin)))
        tr = rec["curves"]["transfer"]; vg, idd = np.asarray(tr["vgs"], float), np.asarray(tr["id"], float)
        g0 = gm_max(vg, idd)[0]; g1 = gm_max(vg, series_linear(idd, r_d, vds_lin))[0]
        out.at[idx, "gm_max_S_per_cm"] = float(r["gm_max_S_per_cm"]) * g1 / g0
        oc = rec["curves"]["output"]
        i0 = float(np.interp(vds_req, np.concatenate([[0.0], oc["vds"]]), np.concatenate([[0.0], oc["id"]])))
        i1 = fixed_point_current(oc["vds"], oc["id"], vds_req, r_d)
        out.at[idx, "id_vds_req_A_per_cm"] = float(r["id_vds_req_A_per_cm"]) * i1 / i0
        out.at[idx, "ron_mohm_cm2"] = float(r["ron_mohm_cm2"]) + rho
    return out


# ---------- evaluation ----------
def evaluate(pool_runs, test_runs, nz: dict, level: str, model="gp", n_boot=5000, seed=7) -> dict:
    """S1 vs S2 on one (train, test) pair with the frozen noise model; paired bootstrap of S2-S1."""
    fl = nz.get("current_floor_A_per_cm")
    pool = censor_floor(add_noise(wide_table(pool_runs).sort_index(), nz, nz["levels"][level], nz["seeds"]["pool"]), fl)
    test = censor_floor(add_noise(wide_table(test_runs).sort_index(), nz, nz["levels"][level], nz["seeds"]["test"]), fl)
    lo, hi = _lohi(load_bounds())
    res, per_pt = dict(n_pool=len(pool), n_test=len(test)), {}
    for S in ("S1", "S2"):
        P = fit_predict(feature_set(pool, S).values, pool[VARS].values, feature_set(test, S).values, model, 0)
        m = metrics(test[VARS].values, P)
        res[S] = dict(mean=m["mean_mae_norm"], **{v: m[v]["mae_norm"] for v in VARS})
        per_pt[S] = (np.abs(P - test[VARS].values) / (np.asarray(hi) - np.asarray(lo))).mean(axis=1)
    d = per_pt["S2"] - per_pt["S1"]
    b = np.random.default_rng(seed).choice(d, (n_boot, len(d))).mean(axis=1)
    res["delta"] = float(d.mean()); res["ci"] = [float(np.percentile(b, 2.5)), float(np.percentile(b, 97.5))]
    res["rel_gain"] = 1.0 - res["S2"]["mean"] / res["S1"]["mean"]
    return res
