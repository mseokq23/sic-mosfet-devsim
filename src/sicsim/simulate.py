"""One DEVSIM experiment = one (process point, temperature) on the 2D half-cell 4H-SiC DMOSFET.

Fixed bias protocol (configs/baseline.yaml -> bias):
  equilibrium -> VDS = vds_lin -> transfer VGS 0 -> 20 V (segments) -> VGS = vgs_on -> output VDS sweep.
Every bias point starts from the previous solution; failures halve the step (solver.ramp).
For DOE work always run this in a fresh process (worker.py / runner.py): DEVSIM keeps global state.
"""
from __future__ import annotations

import hashlib
import json
import math
import time

import devsim as ds

from . import devices as dv, physics as ph, solver
from .config import material_from, gate_from
from .solver import ramp, ConvergenceError, SolveStats
from .utils import reset_devsim


def _hash(obj) -> str:
    return hashlib.sha1(json.dumps(obj, sort_keys=True, default=str).encode()).hexdigest()[:12]


def protocol_hashes(cfg, extended, holes) -> dict:
    physics = dict(material=cfg.get("material"), gate=cfg.get("gate"), qf=cfg["interface"]["qf_cm2"],
                   numerics={k: v for k, v in cfg["numerics"].items() if k != "tol"},
                   doping=cfg["mosfet"]["doping"], geometry=cfg["mosfet"]["geometry"], holes=holes)
    qT = float(cfg["interface"].get("qit_T_reduction_423", 0.0) or 0.0)
    if qT:                                   # robustness variant only; baseline hash unchanged
        physics["qit_T_reduction_423"] = qT
    solv = dict(tol=cfg["numerics"]["tol"], extended=extended, bias=cfg["bias"])
    return dict(physics_hash=_hash(physics), solver_hash=_hash(solv))


def run_mosfet(cfg, T, wjfet_scale=1.0, npwell_scale=1.0, qit_eff_cm2=None, mu_channel_scale=1.0,
               mesh_scale=None, extended=None, holes=None, output_curve=True) -> dict:
    num, b = cfg["numerics"], cfg["bias"]
    ext = bool(num.get("extended_precision", False)) if extended is None else bool(extended)
    holes = bool(num.get("holes", False)) if holes is None else bool(holes)
    ms = float(cfg["mosfet"].get("mesh_scale", 1.0)) if mesh_scale is None else float(mesh_scale)
    tol = num["tol"]
    ii = num.get("incomplete_ionization", True)
    mode = num.get("interface_mode", "static")
    intf = dict(cfg["interface"])
    if qit_eff_cm2 is not None:
        intf["qit_eff_cm2"] = float(qit_eff_cm2)
    qit_nominal = float(intf["qit_eff_cm2"])            # DOE label (defined at 300 K)
    qT = float(intf.get("qit_T_reduction_423", 0.0) or 0.0)
    if qT:   # robustness variant: |Qit_eff| decreases linearly with T, by the fraction qT at 423 K (none at 300 K)
        intf["qit_eff_cm2"] = qit_nominal * (1.0 - qT * (float(T) - 300.0) / 123.0)
    mat = material_from(cfg)
    mat.mu_surf300 *= float(mu_channel_scale)
    gate = gate_from(cfg)

    solver.STATS = SolveStats()
    reset_devsim()
    ph.set_extended_precision(ext)
    t0 = time.time()
    rec = dict(temperature_K=float(T), wjfet_scale=float(wjfet_scale), npwell_scale=float(npwell_scale),
               qit_eff_cm2=qit_nominal, qit_eff_at_T_cm2=float(intf["qit_eff_cm2"]), mu_channel_scale=float(mu_channel_scale),
               mesh_scale=ms, extended=ext, holes=holes, converged=False, error_code=None, stage=None)
    tr = dict(vgs=[], id=[], is_=[])
    out = dict(vgs=float(b["vgs_on"]), vds=[], id=[])
    try:
        rec["stage"] = "build"
        with solver.quiet():
            lay = dv.build_dmosfet("m", cfg, wjfet_scale, npwell_scale, ms)
            dv.setup_physics("m", lay, mat, T, ii=ii, intf_mode=mode, interface=intf, gate=gate)
        rec.update(n_nodes=lay["info"]["n_nodes"], mesh_hash=lay["info"]["mesh_hash"],
                   width_cm=lay["info"]["area_cm"])
        rec["stage"] = "equilibrium"
        dv.equilibrate("m", lay, ii=ii, intf_mode=mode, tol=tol, holes=holes)
        rec["stage"] = "vds_lin"
        ramp("m", "drain", b["vds_lin"], 0.05, tol=tol)

        ex = cfg.get("extract", {})
        targets = sorted({*ex.get("ss_window_A_per_cm", []), ex.get("icc_A_per_cm", 1e-4)})
        vg_at = {}

        def refine(t, v0, i0, v1, i1, iters=4):
            """Secant on log10(ID) between bracketing transfer points -> VGS where ID = t (removes
            grid-interpolation error from Vth/SS; extra solves are not added to the curve)."""
            lt = math.log10(t)
            for _ in range(iters):
                if i0 > 0 and i1 > 0:
                    f = (lt - math.log10(i0)) / (math.log10(i1) - math.log10(i0))
                    v = v0 + min(max(f, 0.02), 0.98) * (v1 - v0)
                else:
                    v = 0.5 * (v0 + v1)
                ds.set_parameter(device="m", name=ph.bias_name("gate"), value=v)
                try:
                    solver.solve_dc("m", tol)
                except ConvergenceError:
                    return None
                i = ph.contact_current("m", "drain")
                if i > 0 and abs(math.log10(i) - lt) < 1e-5:
                    return v
                if i < t:
                    v0, i0 = v, i
                else:
                    v1, i1 = v, i
            return v

        def rec_tr(v):
            tr["vgs"].append(float(v))
            tr["id"].append(ph.contact_current("m", "drain"))
            tr["is_"].append(ph.contact_current("m", "source"))
            if len(tr["vgs"]) > 1:
                v0, i0, i1 = tr["vgs"][-2], tr["id"][-2], tr["id"][-1]
                for t in targets:
                    if f"{t:.3e}" not in vg_at and i0 < t <= i1:
                        vg_at[f"{t:.3e}"] = refine(t, v0, i0, float(v), i1)

        rec_tr(0.0)
        rec["stage"] = "transfer"
        for stop, step in b["vgs_segments"]:
            ramp("m", "gate", stop, step, tol=tol, callback=rec_tr)
        if output_curve:
            rec["stage"] = "output"
            ramp("m", "gate", b["vgs_on"], 0.5, tol=tol)

            def rec_out(v):
                out["vds"].append(float(v))
                out["id"].append(ph.contact_current("m", "drain"))

            rec_out(b["vds_lin"])
            try:
                for stop, step in b["vds_segments"]:
                    ramp("m", "drain", stop, step, tol=tol, callback=rec_out)
            except ConvergenceError as e:
                # protocol rule: output curve may stop early if it reached vds_required (Ron and
                # id@vds_required stay defined); otherwise the run fails
                if not out["vds"] or max(out["vds"]) < b.get("vds_required", 2.0) - 1e-9:
                    raise
                rec["output_truncated_at_V"] = max(out["vds"])
                rec["output_note"] = str(e)[:200]
        rec["converged"] = True
        rec["stage"] = "done"
        rec["vg_at_current"] = vg_at
    except ConvergenceError as e:
        rec["error_code"] = f"CONVERGENCE@{rec['stage']}: {e}"[:300]
    except Exception as e:  # noqa: BLE001 - logged, never silently dropped
        rec["error_code"] = f"{type(e).__name__}@{rec['stage']}: {e}"[:300]
    rec["runtime_s"] = round(time.time() - t0, 3)
    st = solver.STATS.as_dict()
    rec.update(st, retry_count=st["n_fail"])
    rec["curves"] = dict(transfer=tr, output=out)
    rec.update(protocol_hashes(cfg, ext, holes))
    return rec
