import copy
import pytest
from sicsim.config import load_config
from sicsim.devices import dmosfet_geometry


def _cfg(mode):
    c = copy.deepcopy(load_config())
    c["mosfet"]["geometry"]["wjfet_mode"] = mode
    return c


def test_nominal_geometry_identical_in_both_modes():
    a, b = dmosfet_geometry(_cfg("fixed_pitch"), 1.0), dmosfet_geometry(_cfg("pitch_scaling"), 1.0)
    for k in ("x_half_um", "x_pw_um", "x_ns1_um", "wjfet_um"):
        assert a[k] == pytest.approx(b[k])


@pytest.mark.parametrize("s", [0.8, 0.9, 1.1, 1.2])
def test_fixed_pitch_keeps_pitch_and_channel_length(s):
    g0, g = dmosfet_geometry(_cfg("fixed_pitch"), 1.0), dmosfet_geometry(_cfg("fixed_pitch"), s)
    assert g["x_half_um"] == pytest.approx(g0["x_half_um"])                                   # pitch fixed
    assert g["x_pw_um"] - g["x_ns1_um"] == pytest.approx(g0["x_pw_um"] - g0["x_ns1_um"])      # L_ch fixed
    assert 2 * (g["x_half_um"] - g["x_pw_um"]) == pytest.approx(g["wjfet_um"])                # JFET width


def test_pitch_scaling_changes_pitch_and_invalid_geometry_raises():
    assert dmosfet_geometry(_cfg("pitch_scaling"), 1.2)["x_half_um"] > dmosfet_geometry(_cfg("pitch_scaling"), 1.0)["x_half_um"]
    with pytest.raises(ValueError):
        dmosfet_geometry(_cfg("fixed_pitch"), 2.0)       # n+ edge would cross the gate-oxide edge
