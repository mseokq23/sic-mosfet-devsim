"""v4.7 control analyses on the stored features (no new DEVSIM runs).

Repeated-measurement control (S1x2): is the 300 K -> 300+423 K gain more than measuring the same device
twice?  Under noise-v1.1 the 300 K and 423 K features carry independent noise, so S2 also averages two
noise realisations.  S1x2 gives the 300 K features a second, independent realisation instead of the
423 K measurement:
  S1x2     mean of the two 300 K realisations (17 features, the usual way to use a repeat)  [primary]
  S1x2cat  both realisations side by side (34 features, dimension-matched to S2)           [secondary]
Cross-temperature (or repeat) noise correlation rho: z2 = rho*z1 + sqrt(1-rho^2)*z2_independent.
rho = 0 reproduces the frozen noise realisation of S1/S2 bit for bit.
"""
from __future__ import annotations

import platform

import numpy as np
import pandas as pd

from .analysis import LOGT, censor_floor, feature_set

REPEAT_SEED_OFFSET = 1000        # second 300 K realisation: frozen set seed + 1000 (pool 1101, test 1202)
REPLICATE_SEED_STRIDE = 10000    # replicate k >= 1 shifts both realisations by k * 10000


def _sigma(noise_cfg, f):
    """('abs', sigma) | ('rel', sigma) | (None, 0) exactly as analysis.add_noise decides."""
    if f in noise_cfg.get("absolute", {}):
        return "abs", noise_cfg["absolute"][f]
    rel = noise_cfg.get("relative", {}).get(f)
    if rel is None and f.startswith("logid_vg"):
        rel = noise_cfg.get("logid_samples", 0.0)
    return ("rel", rel) if rel else (None, 0.0)


def noise_draws(wide: pd.DataFrame, noise_cfg: dict, seed: int) -> dict:
    """Standard-normal draws in exactly the order analysis.add_noise consumes its generator:
    {column: z array} for noisy columns, None for noise-free ones."""
    rng = np.random.default_rng(seed)
    z = {}
    for c in [c for c in wide.columns if "@" in str(c)]:
        kind, _ = _sigma(noise_cfg, c.rsplit("@", 1)[0])
        z[c] = rng.standard_normal(len(wide)) if kind else None
    return z


def apply_draws(wide: pd.DataFrame, noise_cfg: dict, level: float, z: dict) -> pd.DataFrame:
    """Same arithmetic as analysis.add_noise, but with given draws (identical output for its own draws)."""
    out = wide.copy()
    if level <= 0:
        return out
    for c, zc in z.items():
        if zc is None:
            continue
        f = c.rsplit("@", 1)[0]
        kind, s = _sigma(noise_cfg, f)
        scale = s * level
        if kind == "abs":
            out[c] = out[c] + scale * zc
            continue
        eps = np.clip(scale * zc, -0.5, 0.5)
        if f in LOGT or f.startswith("logid_vg"):
            out[c] = out[c] + np.log10(1 + eps)
        else:
            out[c] = out[c] * (1 + eps)
    return out


def correlate(z_ref, z_other, rho: float):
    """rho*z_ref + sqrt(1-rho^2)*z_other; rho = 0 returns z_other unchanged (bit for bit)."""
    if z_other is None:
        return None
    if rho == 0:
        return np.array(z_other, copy=True)
    return rho * np.asarray(z_ref) + np.sqrt(1.0 - rho ** 2) * np.asarray(z_other)


def _pairs(columns, temps):
    lo = [c for c in columns if str(c).endswith(f"@{temps[0]}")]
    return [(c, f"{c.rsplit('@', 1)[0]}@{temps[1]}") for c in lo]


def noisy_tables(wide: pd.DataFrame, noise_cfg: dict, level: float, seed: int, rho_t: float = 0.0,
                 rho_r: float = 0.0, temps=(300, 423), floor=None, repeat_seed=None):
    """Two noisy copies of one set (pool or test):
      n1: the frozen-style realisation of all features (423 K draws correlated with 300 K draws by rho_t)
      n2: a second 300 K realisation (correlated with n1's 300 K draws by rho_r); only its 300 K columns are used.
    Both are censored at the current floor after noise, as in the frozen pipeline."""
    z1 = noise_draws(wide, noise_cfg, seed)
    for c_lo, c_hi in _pairs(z1, temps):
        if c_hi in z1:
            z1[c_hi] = correlate(z1[c_lo], z1[c_hi], rho_t)
    rs = seed + REPEAT_SEED_OFFSET if repeat_seed is None else repeat_seed
    z2_raw = noise_draws(wide, noise_cfg, rs)
    lo_cols = [c for c in z1 if str(c).endswith(f"@{temps[0]}")]
    z2 = {c: correlate(z1[c], z2_raw[c], rho_r) for c in lo_cols}
    n1 = censor_floor(apply_draws(wide, noise_cfg, level, z1), floor)
    n2 = censor_floor(apply_draws(wide, noise_cfg, level, z2), floor)
    n2 = n2[[c for c in n2.columns if "@" not in str(c) or c in lo_cols]]   # repeat exists at 300 K only
    return n1, n2


def control_feature_set(n1: pd.DataFrame, n2: pd.DataFrame, name: str, temps=(300, 423)) -> pd.DataFrame:
    """S1 / S2 / S3 from the first realisation (frozen definitions) or the repeat controls."""
    if name in ("S1", "S2", "S3"):
        return feature_set(n1, name, temps)
    c1 = [c for c in n1.columns if str(c).endswith(f"@{temps[0]}")]
    if name == "S1x2":
        return (n1[c1] + n2[c1]) / 2.0
    if name == "S1x2cat":
        b = n2[c1].copy()
        b.columns = [f"{c}r" for c in c1]
        return pd.concat([n1[c1], b], axis=1)
    raise ValueError(name)


def replicate_seeds(base_seed: int, k: int):
    """(first, repeat) noise seeds of replicate k; k = 0 is the frozen realisation."""
    first = base_seed + REPLICATE_SEED_STRIDE * k
    return first, first + REPEAT_SEED_OFFSET


def compute_env() -> dict:
    """Numerical environment of an analysis run. Active-learning trajectories depend on it: on a different CPU
    the published uncertainty/LLM curves reproduce at round 0 but drift from round 1, because the forward
    surrogate's candidate ranking changes slightly (most likely last-bit differences in SIMD reductions that
    flip near-tie tree splits). The inverse models and the GP results of RQ1 reproduce exactly."""
    import sklearn
    cpu = None
    try:
        cpu = next((ln.split(":", 1)[1].strip() for ln in open("/proc/cpuinfo") if ln.startswith("model name")), None)
    except OSError:
        pass
    try:
        feats = [k for k, v in np._core._multiarray_umath.__cpu_features__.items() if v]
    except AttributeError:
        feats = None
    simd = [f for f in ("SSE42", "AVX2", "FMA3", "AVX512F", "AVX512_SKX", "AVX512_ICL", "AVX512_SPR") if feats and f in feats]
    return dict(python=platform.python_version(), numpy=np.__version__, sklearn=sklearn.__version__,
                pandas=pd.__version__, platform=platform.platform(), cpu=cpu, numpy_simd=simd)


def paired_boot(err_a: np.ndarray, err_b: np.ndarray, n_boot=5000, seed=7) -> dict:
    """Paired bootstrap over test points of mean(err_a) - mean(err_b) and mean(err_a)/mean(err_b).
    err_*: (n_points,) per-point errors. Resampling indices are drawn as in robust.evaluate."""
    n = len(err_a)
    idx = np.random.default_rng(seed).choice(np.arange(n), (n_boot, n))
    ma, mb = err_a[idx].mean(1), err_b[idx].mean(1)
    d = ma - mb
    r = ma / mb
    return dict(delta=float(err_a.mean() - err_b.mean()),
                ci=[float(np.percentile(d, 2.5)), float(np.percentile(d, 97.5))],
                ci90=[float(np.percentile(d, 5)), float(np.percentile(d, 95))],
                ratio=float(err_a.mean() / err_b.mean()),
                ratio_ci=[float(np.percentile(r, 2.5)), float(np.percentile(r, 97.5))])
