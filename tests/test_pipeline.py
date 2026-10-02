"""Pipeline tests with an ANALYTIC stand-in for DEVSIM (no simulation)."""
import json
import numpy as np
import pandas as pd
from sicsim.alsim import run_policy
from sicsim.analysis import cv_evaluate
from sicsim.design import VARS, random_set, sobol_pool, stage_a
from sicsim.runner import expand


def synth_wide(df):
    w, n, q = df.wjfet_scale.values, df.npwell_scale.values, df.qit_eff_cm2.values / 1e12
    out = pd.DataFrame(index=df.candidate_id.values)
    out["process_group_id"] = df.candidate_id.values
    for v in VARS:
        out[v] = df[v].values
    for T in (300, 423):
        s = (T - 300) / 123
        out[f"vth_V@{T}"] = 3.8 + 1.2 * (n - 1) * (1 - 0.3 * s) - 2.32 * (q + 1) - 0.2 * s
        out[f"ss_mV_dec@{T}"] = 112 * (T / 300)
        out[f"ron_mohm_cm2@{T}"] = np.log10(2.0 * (T / 300) ** 1.5 / w ** 1.5)
    return out


def test_designs():
    assert len(stage_a()) == 13
    p = sobol_pool(64, seed=1)
    assert p.candidate_id.is_unique and p[VARS].min().ge([0.8, 0.8, -1.5e12]).all()
    jobs = expand(stage_a(levels=(-0.2, 0.2)), [300, 423])
    assert len(jobs) == 14 and jobs[0]["run_id"].endswith("_T300")


def test_policies_and_llm_log(tmp_path):
    pool, test = synth_wide(sobol_pool(128, seed=1)), synth_wide(random_set(64, seed=2))
    log = tmp_path / "llm.jsonl"
    for pol in ("random", "sobol", "uncertainty", "llm"):
        df = run_policy(pool, test, pol, seed=0, n_init=16, batch=8, rounds=2, llm_cfg={"dry_run": True},
                        llm_log=log)
        assert df.n_points.tolist() == [16, 24, 32] and df.mean_mae_norm.notna().all()
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert len(recs) == 2 and all(r["validator_status"] == "accepted" for r in recs)


def test_cv_metrics_keys():
    wide = synth_wide(sobol_pool(64, seed=3))
    m = cv_evaluate(wide, "S3", "rf", n_splits=4)
    assert set(VARS) <= set(m) and 0 <= m["mean_mae_norm"] < 1


def test_flatten_fills_feature_columns():
    from sicsim.runner import flatten
    row = flatten({"run_id": "x", "converged": True, "features": {"vth_V": 3.7, "ss_mV_dec": 112.0}})
    assert row["vth_V"] == 3.7 and row["ss_mV_dec"] == 112.0
