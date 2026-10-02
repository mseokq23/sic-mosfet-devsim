"""Robust DC solving: backup/restore, bias ramping with step halving, retry logging.

Retry rule (identical for every policy, as required by the draft):
  1st failure -> halve bias step;  repeated failures -> keep halving down to min_step;
  if still failing -> raise ConvergenceError (run is logged as converged=False).
"""
from __future__ import annotations

import contextlib
import io
import time
import devsim as ds

from .physics import bias_name

SOLUTION_VARS = ("Potential", "Electrons", "Holes")


class ConvergenceError(RuntimeError):
    pass


class SolveStats:
    def __init__(self):
        self.n_solves = 0
        self.n_fail = 0
        self.n_iter = 0
        self.t_solve = 0.0

    def as_dict(self):
        return dict(n_solves=self.n_solves, n_fail=self.n_fail, n_iter=self.n_iter,
                    t_solve_s=round(self.t_solve, 3))


STATS = SolveStats()
QUIET = True          # DEVSIM prints iteration logs through sys.stdout; capture them
LOG = io.StringIO()   # last solve log (useful for debugging failures)


def quiet():
    global LOG
    if not QUIET:
        return contextlib.nullcontext()
    LOG = io.StringIO()
    return contextlib.redirect_stdout(LOG)

DEFAULT_TOL = dict(absolute_error=1e10, relative_error=1e-9, maximum_iterations=40)


def _backup(dev):
    snap = {}
    for reg in ds.get_region_list(device=dev):
        names = ds.get_node_model_list(device=dev, region=reg)
        for v in SOLUTION_VARS:
            if v in names:
                snap[(reg, v)] = ds.get_node_model_values(device=dev, region=reg, name=v)
    return snap


def _restore(dev, snap):
    for (reg, v), vals in snap.items():
        ds.set_node_values(device=dev, region=reg, name=v, values=vals)


def solve_dc(dev, tol=None, restore_on_fail=True):
    tol = {**DEFAULT_TOL, **(tol or {})}
    snap = _backup(dev) if restore_on_fail else None
    t0 = time.time()
    STATS.n_solves += 1
    try:
        with quiet():
            info = ds.solve(type="dc", info=True, **tol)
        STATS.n_iter += len(info.get("iterations", [])) if isinstance(info, dict) else 0
        if isinstance(info, dict) and not info.get("converged", True):
            raise ds.error("Convergence failure (info)")
    except ds.error as e:
        STATS.n_fail += 1
        if snap is not None:
            _restore(dev, snap)
        raise ConvergenceError(str(e)) from e
    finally:
        STATS.t_solve += time.time() - t0


def ramp(dev, contact, target, step, min_step=1e-3, max_step=None, tol=None, callback=None,
         grow=1.5):
    """Ramp contact bias to target. Calls callback(v) after each converged point."""
    bn = bias_name(contact)
    v = ds.get_parameter(device=dev, name=bn)
    step = abs(step)
    max_step = max_step or step
    while abs(target - v) > 1e-12:
        s = 1.0 if target > v else -1.0
        nv = v + s * min(step, abs(target - v))
        ds.set_parameter(device=dev, name=bn, value=nv)
        try:
            solve_dc(dev, tol)
        except ConvergenceError:
            ds.set_parameter(device=dev, name=bn, value=v)
            step *= 0.5
            if step < min_step:
                raise ConvergenceError(f"{contact}: min step reached at {v:.4g} V -> {target:.4g} V")
            continue
        v = nv
        if callback:
            callback(v)
        step = min(step * grow, max_step)
    return v


def sweep(dev, contact, values, min_step=1e-3, tol=None, callback=None):
    """Visit an explicit list of bias values (each reached by ramping from the previous)."""
    out = []
    for target in values:
        cur = ds.get_parameter(device=dev, name=bias_name(contact))
        ramp(dev, contact, target, step=max(abs(target - cur), 1e-6), min_step=min_step, tol=tol)
        if callback:
            out.append(callback(target))
    return out
