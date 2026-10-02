"""FIXED feature-extraction protocol (defined before the DOE; never tuned on results).

Units: currents per cm of device depth (A/cm) for the half-cell; Ron,sp uses the half-cell width
(area normalisation: Ron,sp = (dV/dI) * W_half  [ohm cm^2]).
"""
from __future__ import annotations

import math
import numpy as np


def _arr(x):
    return np.asarray(x, dtype=float)


def vg_at_current(vg, idd, i0):
    """First gate voltage where ID reaches i0 (log-linear interpolation). NaN if never reached."""
    vg, idd = _arr(vg), _arr(idd)
    above = np.where(idd >= i0)[0]
    if len(above) == 0 or above[0] == 0:
        return float("nan")
    k = above[0]
    i_lo, i_hi = idd[k - 1], idd[k]
    if i_lo <= 0:
        return float(vg[k])
    f = (math.log10(i0) - math.log10(i_lo)) / (math.log10(i_hi) - math.log10(i_lo))
    return float(vg[k - 1] + f * (vg[k] - vg[k - 1]))


def vth_constant_current(vg, idd, icc):
    return vg_at_current(vg, idd, icc)


def subthreshold_swing(vg, idd, lo, hi):
    """SS [mV/dec] = gate-voltage span between the two window currents / decades spanned."""
    v_lo, v_hi = vg_at_current(vg, idd, lo), vg_at_current(vg, idd, hi)
    if not (np.isfinite(v_lo) and np.isfinite(v_hi)):
        return float("nan")
    return 1e3 * (v_hi - v_lo) / math.log10(hi / lo)


def gm_max(vg, idd):
    vg, idd = _arr(vg), _arr(idd)
    if len(vg) < 3:
        return float("nan"), float("nan")
    gm = np.gradient(idd, vg)
    k = int(np.argmax(gm))
    return float(gm[k]), float(vg[k])


def current_at(x, y, x0):
    """log-linear interpolation of a positive current; linear if any value <= 0."""
    x, y = _arr(x), _arr(y)
    if x0 < x.min() - 1e-9 or x0 > x.max() + 1e-9:
        return float("nan")
    if np.all(y > 0):
        return float(10 ** np.interp(x0, x, np.log10(y)))
    return float(np.interp(x0, x, y))


def ron_sp(vds, idd, vmax, width_cm):
    """Low-VDS on-resistance from a least-squares slope through the origin (VDS <= vmax)."""
    vds, idd = _arr(vds), _arr(idd)
    m = vds <= vmax + 1e-12
    if m.sum() < 2:
        return float("nan")
    g = float(np.sum(vds[m] * idd[m]) / np.sum(vds[m] ** 2))     # A/(cm V)
    return 1e3 * width_cm / g if g > 0 else float("nan")          # mOhm cm^2


def kcl_floor(idd, iss):
    """Numerical current floor: max |ID + IS| (Kirchhoff balance error of the discretisation)."""
    return float(np.max(np.abs(_arr(idd) + _arr(iss)))) if len(idd) else float("nan")


def extract_features(rec: dict, cfg: dict) -> dict:
    ex = cfg["extract"]
    tr, out = rec["curves"]["transfer"], rec["curves"]["output"]
    vg, idd = tr["vgs"], tr["id"]
    lo, hi = ex["ss_window_A_per_cm"]
    floor = kcl_floor(tr["id"], tr["is_"])
    gm, vgm = gm_max(vg, idd)
    va = rec.get("vg_at_current") or {}
    key = lambda t: f"{t:.3e}"
    vth_i, ss_i = vth_constant_current(vg, idd, ex["icc_A_per_cm"]), subthreshold_swing(vg, idd, lo, hi)
    vth = va.get(key(ex["icc_A_per_cm"])) or vth_i            # bias-refined value preferred
    ss = (1e3 * (va[key(hi)] - va[key(lo)]) / math.log10(hi / lo)
          if va.get(key(hi)) and va.get(key(lo)) else ss_i)
    f = dict(
        vth_V=vth, ss_mV_dec=ss, vth_interp_V=vth_i, ss_interp_mV_dec=ss_i,
        refined=bool(va),
        gm_max_S_per_cm=gm, vg_at_gm_max_V=vgm,
        ion_A_per_cm=current_at(vg, idd, ex["vgs_on"]),
        ron_mohm_cm2=ron_sp(out["vds"], out["id"], ex["ron_vds_max"], rec.get("width_cm", float("nan"))),
        id_vds_req_A_per_cm=current_at(out["vds"], out["id"], cfg["bias"].get("vds_required", 2.0))
        if out["id"] else float("nan"),
        vds_reached_V=float(max(out["vds"])) if out["vds"] else float("nan"),
        ioff_A_per_cm=abs(float(idd[0])) if len(idd) else float("nan"),
        kcl_floor_A_per_cm=floor,
    )
    f["ron_norm"] = f["ron_mohm_cm2"]                     # draft column name
    f["ioff_below_floor"] = bool(f["ioff_A_per_cm"] < 10 * floor) if np.isfinite(floor) else None
    f["ss_window_resolved"] = bool(np.isfinite(f["ss_mV_dec"]) and lo > 10 * floor)
    for v in ex["feature_vgs"]:
        i = current_at(vg, idd, float(v))
        f[f"logid_vg{v:g}"] = math.log10(i) if i > 0 else float("nan")
    return f
