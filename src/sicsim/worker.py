"""Isolated single-run worker:  python -m sicsim.worker job.json result.json

job.json keys: run_id, temperature_K, wjfet_scale, npwell_scale, qit_eff_cm2 [, mu_channel_scale,
mesh_scale, extended, holes, output_curve, config]."""
from __future__ import annotations

import json
import sys

from .config import load_config, ROOT
from .simulate import run_mosfet
from .extract import extract_features
from .utils import save_json, env_info


def run_job(job: dict) -> dict:
    cfg = load_config(job.get("config") or ROOT / "configs" / "baseline.yaml")
    rec = run_mosfet(cfg, job["temperature_K"], job.get("wjfet_scale", 1.0), job.get("npwell_scale", 1.0),
                     job.get("qit_eff_cm2"), job.get("mu_channel_scale", 1.0), job.get("mesh_scale"),
                     job.get("extended"), job.get("holes"), job.get("output_curve", True))
    feats = extract_features(rec, cfg) if rec["converged"] else {}
    return {**job, **{k: v for k, v in rec.items() if k != "curves"}, "config_version": cfg.get("version"),
            "features": feats, "curves": rec["curves"], "env": env_info()}


if __name__ == "__main__":
    save_json(run_job(json.load(open(sys.argv[1]))), sys.argv[2])
