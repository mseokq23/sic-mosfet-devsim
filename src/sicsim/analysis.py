"""Inverse-model analysis: wide tables per process point, feature sets S1/S2/S3, models, GroupKFold CV."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import ExtraTreesRegressor, RandomForestRegressor
from sklearn.gaussian_process import GaussianProcessRegressor
from sklearn.gaussian_process.kernels import RBF, ConstantKernel, WhiteKernel
from sklearn.metrics import f1_score
from sklearn.model_selection import GroupKFold
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from .design import NUISANCE, VARS, load_bounds

SCALAR = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"]
LOGT = {"gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"}   # used as log10


def feature_columns(df) -> list[str]:
    samples = sorted([c for c in df.columns if str(c).startswith("logid_vg")], key=lambda c: float(c[8:]))
    return [c for c in SCALAR if c in df.columns] + samples


def wide_table(runs: pd.DataFrame, temps=(300, 423)) -> pd.DataFrame:
    """One row per candidate: process variables + features at each temperature (inner join =
    candidates converged at every temperature)."""
    ok = runs[runs["converged"].astype(str).str.lower() == "true"].copy()
    feats = feature_columns(ok)
    parts = []
    for T in temps:
        sub = ok[np.isclose(ok["temperature_K"].astype(float), T)].set_index("candidate_id")[feats].astype(float)
        for c in LOGT & set(feats):
            sub[c] = np.log10(sub[c].clip(lower=1e-30))
        sub.columns = [f"{c}@{int(T)}" for c in sub.columns]
        parts.append(sub)
    X = pd.concat(parts, axis=1, join="inner")
    nuis = [c for c in NUISANCE if c in ok.columns]               # kept for the policies, never a model input
    meta = ok.drop_duplicates("candidate_id").set_index("candidate_id")[["process_group_id"] + VARS + nuis]
    return meta.join(X, how="inner")


def feature_set(wide: pd.DataFrame, name: str, temps=(300, 423)) -> pd.DataFrame:
    c1 = [c for c in wide.columns if str(c).endswith(f"@{temps[0]}")]
    if name == "S1":
        return wide[c1]
    X = wide[[c for c in wide.columns if "@" in str(c)]].copy()
    if name == "S2":
        return X
    if name == "S3":                       # + temperature differences (= log-ratios for log features)
        for c in c1:
            b = c.rsplit("@", 1)[0]
            X[f"d_{b}"] = wide[f"{b}@{temps[1]}"] - wide[c]
        return X
    raise ValueError(name)


def add_noise(wide: pd.DataFrame, noise_cfg: dict, level: float = 1.0, seed: int = 0) -> pd.DataFrame:
    """Return a copy of a wide table with measurement-like noise on every '<feature>@<T>' column.
    vth_V: absolute sigma; listed features: relative sigma (log10 columns get log10(1+eps));
    logid_vg* samples: relative sigma in the log domain.  level=0 -> unchanged copy."""
    out = wide.copy()
    if level <= 0:
        return out
    rng = np.random.default_rng(seed)
    for c in [c for c in wide.columns if "@" in str(c)]:
        f = c.rsplit("@", 1)[0]
        n = len(out)
        if f in noise_cfg.get("absolute", {}):
            out[c] = out[c] + rng.normal(0, noise_cfg["absolute"][f] * level, n)
            continue
        rel = noise_cfg.get("relative", {}).get(f)
        if rel is None and f.startswith("logid_vg"):
            rel = noise_cfg.get("logid_samples", 0.0)
        if not rel:
            continue
        eps = np.clip(rng.normal(0, rel * level, n), -0.5, 0.5)
        if f in LOGT or f.startswith("logid_vg"):
            out[c] = out[c] + np.log10(1 + eps)
        else:
            out[c] = out[c] * (1 + eps)
    return out


def _lohi(bounds):
    lo = np.array([bounds["variables"][v]["low"] for v in VARS])
    hi = np.array([bounds["variables"][v]["high"] for v in VARS])
    return lo, hi


def make_model(kind="rf", seed=0):
    if kind == "rf":
        return RandomForestRegressor(n_estimators=300, random_state=seed, n_jobs=1)
    if kind == "et":
        return ExtraTreesRegressor(n_estimators=300, random_state=seed, n_jobs=1)
    if kind == "gp":
        k = ConstantKernel(1.0) * RBF(1.0) + WhiteKernel(1e-3)
        return make_pipeline(StandardScaler(), GaussianProcessRegressor(k, normalize_y=True, random_state=seed))
    if kind == "xgb":
        from sklearn.multioutput import MultiOutputRegressor
        from xgboost import XGBRegressor
        return MultiOutputRegressor(XGBRegressor(n_estimators=400, max_depth=4, learning_rate=0.05,
                                                 subsample=0.9, random_state=seed, n_jobs=1))
    raise ValueError(kind)


def metrics(Y, P, bounds=None, n_bins=3) -> dict:
    """Per-target MAE/RMSE/R2 (physical units), range-normalised MAE, macro-F1 on equal-width bins."""
    bounds = bounds or load_bounds()
    lo, hi = _lohi(bounds)
    Y, P = np.asarray(Y, float), np.asarray(P, float)
    out = {}
    for j, v in enumerate(VARS):
        e = P[:, j] - Y[:, j]
        ss = np.sum((Y[:, j] - Y[:, j].mean()) ** 2)
        edges = np.linspace(lo[j], hi[j], n_bins + 1)[1:-1]
        out[v] = dict(mae=float(np.mean(np.abs(e))), rmse=float(np.sqrt(np.mean(e ** 2))),
                      r2=float(1 - np.sum(e ** 2) / ss) if ss > 0 else float("nan"),
                      mae_norm=float(np.mean(np.abs(e)) / (hi[j] - lo[j])),
                      macro_f1=float(f1_score(np.digitize(Y[:, j], edges), np.digitize(P[:, j], edges),
                                              average="macro")))
    out["mean_mae_norm"] = float(np.mean([out[v]["mae_norm"] for v in VARS]))
    return out


def fit_predict(Xtr, Ytr, Xte, kind="rf", seed=0, bounds=None):
    bounds = bounds or load_bounds()
    lo, hi = _lohi(bounds)
    m = make_model(kind, seed)
    m.fit(np.asarray(Xtr, float), (np.asarray(Ytr, float) - lo) / (hi - lo))
    return lo + np.asarray(m.predict(np.asarray(Xte, float))).reshape(len(Xte), -1) * (hi - lo)


def cv_evaluate(wide: pd.DataFrame, set_name="S2", kind="rf", n_splits=5, seed=0) -> dict:
    X, Y = feature_set(wide, set_name).values, wide[VARS].values
    groups = wide["process_group_id"].values
    P = np.zeros_like(Y, dtype=float)
    for tr, te in GroupKFold(n_splits=min(n_splits, len(np.unique(groups)))).split(X, Y, groups):
        P[te] = fit_predict(X[tr], Y[tr], X[te], kind, seed)
    return metrics(Y, P)
