"""Candidate pools and fixed designs (Stage A one-at-a-time, Sobol pool, random test set)."""
from __future__ import annotations

import numpy as np
import pandas as pd
import yaml
from scipy.stats import qmc

from .config import ROOT, _Loader

VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]          # estimation targets
NUISANCE = ["mu_channel_scale"]                                 # varied, known to simulator, not estimated
DESIGN_VARS = VARS + NUISANCE


def load_bounds(path=ROOT / "configs" / "parameter_bounds.yaml") -> dict:
    with open(path) as f:
        return yaml.load(f, Loader=_Loader)


def _spec(bounds, v):
    for block in ("variables", "nuisance", "optional"):
        if v in (bounds.get(block) or {}):
            return bounds[block][v]
    raise KeyError(v)


def _scale(u, bounds, names):
    """names may include optional nuisance variables (e.g. mu_channel_scale) from the 'optional' block."""
    lo = np.array([_spec(bounds, v)["low"] for v in names])
    hi = np.array([_spec(bounds, v)["high"] for v in names])
    return lo + u * (hi - lo)


def _frame(x, prefix, names, start=0):
    ids = [f"{prefix}{i + start:04d}" for i in range(len(x))]
    df = pd.DataFrame(x, columns=names)
    df.insert(0, "candidate_id", ids)
    df.insert(1, "process_group_id", ids)
    return df


def sobol_pool(n, bounds=None, seed=0, prefix="C", names=DESIGN_VARS) -> pd.DataFrame:
    """Scrambled Sobol pool; row order = Sobol order (used by the 'Sobol-fixed' policy)."""
    bounds = bounds or load_bounds()
    s = qmc.Sobol(d=len(names), scramble=True, seed=seed)
    m = int(np.ceil(np.log2(max(n, 2))))
    u = s.random_base2(m)[:n]
    return _frame(_scale(u, bounds, names), prefix, names)


def random_set(n, bounds=None, seed=12345, prefix="T", names=DESIGN_VARS) -> pd.DataFrame:
    """Independent uniform-random test set (never offered to any policy)."""
    bounds = bounds or load_bounds()
    u = np.random.default_rng(seed).random((n, len(names)))
    return _frame(_scale(u, bounds, names), prefix, names)


def stage_a(bounds=None, levels=(-0.2, -0.1, 0.1, 0.2), names=DESIGN_VARS) -> pd.DataFrame:
    """Baseline + one-variable-at-a-time relative changes around the nominal point."""
    bounds = bounds or load_bounds()
    nom = {v: _spec(bounds, v)["nominal"] for v in names}
    rows = [dict(candidate_id="A_base", **nom)]
    for v in names:
        for lv in levels:
            r = dict(nom)
            r[v] = nom[v] * (1.0 + lv)
            rows.append(dict(candidate_id=f"A_{v.split('_')[0]}_{lv:+.0%}".replace("%", "pct"), **r))
    df = pd.DataFrame(rows)
    df.insert(1, "process_group_id", df["candidate_id"])
    return df
