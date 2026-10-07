"""v4.7 repeated-measurement control: the new noise path must reproduce the frozen one exactly at rho = 0."""
import numpy as np
import pandas as pd
import yaml

from sicsim.analysis import add_noise, censor_floor
from sicsim.config import ROOT, _Loader
from sicsim.controls import (apply_draws, control_feature_set, correlate, noise_draws, noisy_tables, paired_boot,
                             replicate_seeds)
from sicsim.design import VARS

NZ = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)


def wide(n=64, seed=0):
    """Synthetic wide table with every noise kind: absolute (vth), relative linear (ss), relative log (ion),
    log transfer samples (logid_vg*) and a noise-free feature (foo)."""
    rng = np.random.default_rng(seed)
    ids = [f"C{i:04d}" for i in range(n)]
    w = pd.DataFrame(index=ids)
    w["process_group_id"] = ids
    for v in VARS:
        w[v] = rng.uniform(0, 1, n)
    for T in (300, 423):
        w[f"vth_V@{T}"] = 3.7 + rng.normal(0, 0.1, n)
        w[f"ss_mV_dec@{T}"] = 112 + rng.normal(0, 3, n)
        w[f"ion_A_per_cm@{T}"] = -1.7 + rng.normal(0, 0.05, n)
        w[f"logid_vg4@{T}"] = -11.5 + rng.normal(0, 0.8, n)        # partly below the 1e-11 floor
        w[f"logid_vg10@{T}"] = -3 + rng.normal(0, 0.1, n)
        w[f"foo@{T}"] = rng.normal(0, 1, n)
    return w


def test_draws_reproduce_add_noise_bit_for_bit():
    w = wide()
    for lv in (0.0, 1.0, 2.0):
        for seed in (101, 202, 7):
            assert apply_draws(w, NZ, lv, noise_draws(w, NZ, seed)).equals(add_noise(w, NZ, lv, seed))


def test_rho0_tables_equal_the_frozen_pipeline():
    w, fl = wide(), NZ["current_floor_A_per_cm"]
    n1, n2 = noisy_tables(w, NZ, 1.0, 101, 0.0, 0.0, floor=fl)
    assert n1.equals(censor_floor(add_noise(w, NZ, 1.0, 101), fl))
    assert not any(str(c).endswith("@423") for c in n2.columns)
    s1, s1x2, cat = (control_feature_set(n1, n2, s) for s in ("S1", "S1x2", "S1x2cat"))
    assert list(s1.columns) == list(s1x2.columns) and cat.shape[1] == 2 * s1.shape[1]
    assert np.allclose(s1x2.values, (n1[s1.columns].values + n2[s1.columns].values) / 2)
    assert not np.allclose(n1[s1.columns].values, n2[s1.columns].values)          # an independent second measurement
    assert control_feature_set(n1, n2, "S2").equals(n1[[c for c in n1.columns if "@" in c]])


def test_correlation_of_the_two_measurements():
    w = wide(n=6000, seed=1)
    for rho in (0.0, 0.5, 0.9):
        n1, n2 = noisy_tables(w, NZ, 1.0, 11, rho, rho)
        r_t = np.corrcoef(n1["vth_V@300"] - w["vth_V@300"], n1["vth_V@423"] - w["vth_V@423"])[0, 1]
        r_r = np.corrcoef(n1["vth_V@300"] - w["vth_V@300"], n2["vth_V@300"] - w["vth_V@300"])[0, 1]
        assert abs(r_t - rho) < 0.04 and abs(r_r - rho) < 0.04
        assert np.isclose((n2["vth_V@300"] - w["vth_V@300"]).std(), 0.010, rtol=0.05)   # marginal sigma unchanged
    z = np.arange(5.0)
    assert correlate(z, z + 1, 0.0).tolist() == (z + 1).tolist() and correlate(z, None, 0.5) is None


def test_paired_boot_uses_the_robust_evaluate_resampling():
    rng = np.random.default_rng(3)
    a, b = rng.uniform(0, 0.2, 128), rng.uniform(0, 0.2, 128)
    d = a - b
    ref = np.random.default_rng(7).choice(d, (5000, len(d))).mean(axis=1)       # as in robust.evaluate
    out = paired_boot(a, b)
    assert np.isclose(out["ci"][0], np.percentile(ref, 2.5)) and np.isclose(out["ci"][1], np.percentile(ref, 97.5))
    assert np.isclose(out["delta"], d.mean()) and np.isclose(out["ratio"], a.mean() / b.mean())


def test_replicate_seeds():
    assert replicate_seeds(101, 0) == (101, 1101) and replicate_seeds(202, 2) == (20202, 21202)
