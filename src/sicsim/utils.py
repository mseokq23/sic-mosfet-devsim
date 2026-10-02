from __future__ import annotations
import json, math, platform, subprocess, time
from pathlib import Path
import numpy as np
import devsim as ds


def reset_devsim():
    """Delete every device/mesh so a new simulation starts from a clean state."""
    for d in list(ds.get_device_list()):
        ds.delete_device(device=d)
        try:
            ds.delete_mesh(mesh=d + "_mesh")
        except ds.error:
            pass


class NpEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, (np.floating,)):
            return float(o)
        if isinstance(o, (np.integer,)):
            return int(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
        return super().default(o)


def save_json(obj, path):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(obj, f, indent=2, cls=NpEncoder)


def env_info() -> dict:
    info = ds.get_parameter(name="info")
    try:
        commit = subprocess.run(["git", "rev-parse", "--short", "HEAD"], capture_output=True,
                                text=True).stdout.strip() or None
    except Exception:
        commit = None
    return dict(devsim=info.get("version"), solver=info.get("direct_solver"),
                math=info.get("math_libraries"), extended=info.get("extended_precision"),
                python=platform.python_version(), platform=platform.platform(), commit=commit)


def rel_err(a, b):
    return abs(a - b) / max(abs(b), 1e-300)
