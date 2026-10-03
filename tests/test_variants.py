"""v1.3 robustness variants: frozen baseline untouched, variants differ only in the intended key,
series-resistance helpers match analytic results."""
import glob, json
import numpy as np
from sicsim.config import ROOT, load_config
from sicsim.robust import fixed_point_current, series_linear
from sicsim.simulate import protocol_hashes

INTENDED = {"gamma_m1": ("material", "mu_surf_gamma", -1.0), "gamma0": ("material", "mu_surf_gamma", 0.0),
            "qitT10": ("interface", "qit_T_reduction_423", 0.10), "qitT30": ("interface", "qit_T_reduction_423", 0.30)}


def test_baseline_physics_hash_matches_committed_runs():
    rec = json.load(open(sorted(glob.glob(str(ROOT / "results/pool/runs/*_T423.json")))[0]))
    assert protocol_hashes(load_config(), False, False)["physics_hash"] == rec["physics_hash"]


def test_variants_change_only_intended_key():
    base = load_config()
    h0 = protocol_hashes(base, False, False)["physics_hash"]
    for name, (sec, key, val) in INTENDED.items():
        v = load_config(ROOT / "configs" / "variants" / f"{name}.yaml")
        assert v[sec][key] == val
        for s in base:
            if s == "version":
                continue
            a, b = dict(base[s]) if isinstance(base[s], dict) else base[s], dict(v[s]) if isinstance(v[s], dict) else v[s]
            if s == sec:
                a.pop(key, None); b.pop(key, None)
            assert a == b, (name, s)
        assert protocol_hashes(v, False, False)["physics_hash"] != h0


def test_series_resistance_helpers():
    assert np.isclose(series_linear(0.02, 0.5, 0.1), 0.1 / (0.1 / 0.02 + 0.5))
    vds = np.linspace(0.1, 5, 50)
    assert np.isclose(fixed_point_current(vds, vds / 5.0, 2.0, 0.5), 2.0 / 5.5, rtol=1e-6)
