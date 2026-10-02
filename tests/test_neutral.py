import numpy as np
from sicsim.params import SiC4H
from sicsim.physics import neutral_potential


def test_charge_neutrality_with_incomplete_ionization():
    m = SiC4H()
    d = {**m.derived(300.0), "gD": m.gD, "gA": m.gA}
    don, acc = np.array([1e16, 0.0, 2e19]), np.array([0.0, 1e17, 0.0])
    psi = neutral_potential(don, acc, d, ii=True)
    n, p = d["ni"] * np.exp(psi / d["Vt"]), d["ni"] * np.exp(-psi / d["Vt"])
    rho = p - n + don / (1 + m.gD * n / d["n1D"]) - acc / (1 + m.gA * p / d["p1A"])
    assert np.all(np.abs(rho) <= 1e-6 * (don + acc))
    assert psi[0] > 0 > psi[1]


def test_full_ionization_limit():
    m = SiC4H()
    d = {**m.derived(300.0), "gD": m.gD, "gA": m.gA}
    psi = neutral_potential(np.array([1e16]), np.array([0.0]), d, ii=False)
    assert abs(d["ni"] * np.exp(psi[0] / d["Vt"]) / 1e16 - 1) < 1e-6
