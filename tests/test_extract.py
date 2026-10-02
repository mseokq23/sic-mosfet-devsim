import math
import numpy as np
from sicsim.extract import current_at, gm_max, kcl_floor, ron_sp, subthreshold_swing, vth_constant_current


def synth(ss=0.150, vt=3.0, i0=1e-4):
    vg = np.arange(0, 10.001, 0.25)
    lin = i0 * (1 + (vg - vt) * math.log(10) / ss)          # C1-continuous above vt
    return vg, np.where(vg < vt, i0 * 10 ** ((vg - vt) / ss), lin)


def test_vth_constant_current():
    vg, i = synth()
    assert abs(vth_constant_current(vg, i, 1e-4) - 3.0) < 1e-9


def test_ss_exact_in_exponential_region():
    vg, i = synth(ss=0.150)
    assert abs(subthreshold_swing(vg, i, 1e-10, 1e-6) - 150.0) < 1e-6


def test_not_reached_is_nan():
    vg, i = synth()
    assert math.isnan(vth_constant_current(vg, i, 1.0))


def test_ron_and_gm():
    vds = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 1.0])
    assert abs(ron_sp(vds, vds / 2.0, 0.5, 3.5e-4) - 0.7) < 1e-9      # g = 0.5 A/(cm V)
    vg = np.linspace(0, 5, 21)
    assert abs(gm_max(vg, 2 * vg)[0] - 2.0) < 1e-9


def test_floor_and_interp():
    assert kcl_floor([1.0, 2.0], [-1.0, -2.5]) == 0.5
    assert abs(current_at([0, 1], [1e-6, 1e-4], 0.5) - 1e-5) < 1e-12
