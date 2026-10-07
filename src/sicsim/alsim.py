"""Pool-based retrospective active-learning evaluation.

The candidate pool and an independent test set are simulated ONCE; each policy then 'queries' labels
(DEVSIM results) from the pool.  Same pool, same initial set and same budget for every policy and seed
-> fair multi-seed comparison at a fraction of the DEVSIM cost (RQ2/RQ3).
Policies: random | sobol (pool order) | uncertainty (forward-surrogate tree variance + diversity) | llm
          | top20_random (v4.7 ablation D: 10 drawn uniformly from the uncertainty top-20, no LLM)
LLM variants (llm_cfg['variant'], v4.7 ablation): named (A) | anon (B) | shuffled (C), see ablation.py.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import GroupKFold

from . import llm as llm_mod
from .ablation import shuffle_rng, top_random, transform_payload
from .analysis import feature_set, fit_predict, metrics
from .design import NUISANCE, VARS, _spec, load_bounds


def _proc_cols(df):
    """Design (simulation-input) columns: targets + nuisance variables present in the pool."""
    return VARS + [c for c in NUISANCE if c in df.columns]


def _norm_proc(df, bounds, cols=None):
    cols = cols or _proc_cols(df)
    lo = np.array([_spec(bounds, v)["low"] for v in cols])
    hi = np.array([_spec(bounds, v)["high"] for v in cols])
    return (df[cols].values - lo) / (hi - lo)


def forward_uncertainty(Ptr, Ftr, Pc, seed=0):
    """Mean (over standardised features) per-tree std of a forward RF surrogate process -> features."""
    mu, sd = Ftr.mean(0), Ftr.std(0) + 1e-12
    rf = RandomForestRegressor(n_estimators=200, random_state=seed, n_jobs=1).fit(Ptr, (Ftr - mu) / sd)
    per_tree = np.stack([t.predict(Pc) for t in rf.estimators_])          # (trees, n, feats)
    return per_tree.std(0).mean(1)


def _min_dist(Pc, Pref):
    if len(Pref) == 0:
        return np.ones(len(Pc))
    return np.sqrt(((Pc[:, None, :] - Pref[None, :, :]) ** 2).sum(-1)).min(1)


def diverse_top(ids, score, Pc, Ptr, k, top_factor=3):
    """Greedy: from the top (top_factor*k) by score, repeatedly take the candidate maximising
    score * distance to (train + already chosen)."""
    order = np.argsort(-score)[: max(k * top_factor, k)]
    chosen, ref = [], Ptr.copy()
    for _ in range(k):
        d = _min_dist(Pc[order], ref)
        j = order[int(np.argmax(score[order] * (d + 1e-9)))]
        chosen.append(ids[j])
        ref = np.vstack([ref, Pc[j]])
        order = order[order != j]
    return chosen


def run_policy(pool: pd.DataFrame, test: pd.DataFrame, policy: str, seed=0, n_init=40, batch=10, rounds=6,
               set_name="S2", model="rf", llm_cfg=None, llm_log=None, top_n=20) -> pd.DataFrame:
    """pool/test: wide tables (index candidate_id; process vars + features). pool row order = Sobol order."""
    bounds = load_bounds()
    rng = np.random.default_rng(seed)
    ids = list(pool.index)
    pcols = _proc_cols(pool)
    Xpool, Ppool = feature_set(pool, set_name).values, _norm_proc(pool, bounds, pcols)
    Xte, Yte = feature_set(test, set_name).values, test[VARS].values
    n_temps = 1 if set_name == "S1" else 2
    pos = {c: i for i, c in enumerate(ids)}
    sel = list(rng.choice(ids, n_init, replace=False))   # identical initial set for all policies (same seed)
    rows = []
    for r in range(rounds + 1):
        idx = [pos[c] for c in sel]
        P = fit_predict(Xpool[idx], pool[VARS].values[idx], Xte, model, seed)
        m = metrics(Yte, P, bounds)
        rows.append(dict(policy=policy, seed=seed, round=r, n_points=len(sel), n_devsim_runs=len(sel) * n_temps,
                         mean_mae_norm=m["mean_mae_norm"],
                         **{f"mae_norm_{v}": m[v]["mae_norm"] for v in VARS},
                         **{f"f1_{v}": m[v]["macro_f1"] for v in VARS}))
        if r == rounds:
            break
        rest = [c for c in ids if c not in set(sel)]
        if policy == "random":
            new = list(rng.choice(rest, batch, replace=False))
        elif policy == "sobol":
            new = rest[:batch]
        else:
            ridx = [pos[c] for c in rest]
            unc = forward_uncertainty(Ppool[idx], Xpool[idx], Ppool[ridx], seed)
            if policy == "uncertainty":
                new = diverse_top(rest, unc, Ppool[ridx], Ppool[idx], batch)
            elif policy == "top20_random":
                top = np.argsort(-unc)[:top_n]
                new = [rest[j] for j in top_random(top, batch, np.random.default_rng([seed, r, 2020]))]
            elif policy == "llm":
                top = np.argsort(-unc)[:top_n]
                dist = _min_dist(Ppool[ridx][top], Ppool[idx])
                # model summary from TRAINING data only (no test-set leakage into the selector)
                Ptr_cv = np.zeros((len(idx), len(VARS)))
                g = np.array(sel)
                for a, b in GroupKFold(n_splits=min(5, len(idx))).split(Xpool[idx], groups=g):
                    Ptr_cv[b] = fit_predict(Xpool[idx][a], pool[VARS].values[idx][a], Xpool[idx][b], model, seed)
                cvm = metrics(pool[VARS].values[idx], Ptr_cv, bounds)
                payload = dict(round=r, seed=seed, batch_size=batch,
                               model_summary=dict(n_train=len(idx), cv_mae_norm={v: round(cvm[v]["mae_norm"], 4) for v in VARS},
                                                  worst_target=max(VARS, key=lambda v: cvm[v]["mae_norm"])),
                               candidates=[dict(candidate_id=rest[j],
                                                **{v: round(float(Ppool[ridx][j][q]), 3) for q, v in enumerate(pcols)},
                                                predictive_uncertainty=round(float(unc[j]), 4),
                                                distance_to_train=round(float(dist[i]), 4))
                                           for i, j in enumerate(top)])
                cfg = llm_cfg or {"dry_run": True}
                variant = cfg.get("variant", "named")
                shown, truth = transform_payload(payload, variant, shuffle_rng(seed, r) if variant == "shuffled" else None)
                new, _ = llm_mod.select(shown, sel, cfg, llm_log, truth=truth)
                if new is None:                  # fixed fallback rule
                    new = diverse_top(rest, unc, Ppool[ridx], Ppool[idx], batch)
            else:
                raise ValueError(policy)
        sel += list(new)
    return pd.DataFrame(rows)
