"""Pipeline tests with an ANALYTIC stand-in for DEVSIM (no simulation)."""
import json
import numpy as np
import pandas as pd
from sicsim.alsim import run_policy
from sicsim.analysis import cv_evaluate
from sicsim.design import VARS, random_set, sobol_pool, stage_a
from sicsim.runner import expand


def synth_wide(df):
    """Analytic stand-in: channel mobility (nuisance) and JFET width both act on Ron, with different
    temperature weights (channel ~T^+1, drift ~T^-2.4) -> separable only with two temperatures."""
    w, n, q = df.wjfet_scale.values, df.npwell_scale.values, df.qit_eff_cm2.values / 1e12
    m = df["mu_channel_scale"].values if "mu_channel_scale" in df else np.ones(len(df))
    out = pd.DataFrame(index=df.candidate_id.values)
    out["process_group_id"] = df.candidate_id.values
    for v in VARS + (["mu_channel_scale"] if "mu_channel_scale" in df else []):
        out[v] = df[v].values
    for T in (300, 423):
        s, t = (T - 300) / 123, T / 300
        out[f"vth_V@{T}"] = 3.8 + 1.2 * (n - 1) * (1 - 0.3 * s) - 2.32 * (q + 1) - 0.2 * s
        out[f"ss_mV_dec@{T}"] = 112 * t * (1 + 0.17 * (n - 1))
        out[f"ron_mohm_cm2@{T}"] = np.log10(1.2 / (m * t) + 0.8 * t ** 2.4 / w ** 1.5)
    return out


def test_designs():
    assert len(stage_a()) == 17 and "mu_channel_scale" in stage_a().columns
    p = sobol_pool(64, seed=1)
    assert p.candidate_id.is_unique and p[VARS].min().ge([0.8, 0.8, -1.5e12]).all()
    jobs = expand(stage_a(levels=(-0.2, 0.2)), [300, 423])
    assert len(jobs) == 18 and jobs[0]["run_id"].endswith("_T300")


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


def test_noise_model_and_nuisance_pool():
    import yaml
    from sicsim.analysis import add_noise
    from sicsim.config import ROOT, _Loader
    nz = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)
    w = synth_wide(sobol_pool(32, seed=4))
    assert add_noise(w, nz, 0.0).equals(w)
    a, b = add_noise(w, nz, 1.0, seed=7), add_noise(w, nz, 1.0, seed=7)
    assert a.equals(b) and not a.equals(w)
    assert abs((a["vth_V@300"] - w["vth_V@300"]).std() - 0.010) < 0.006
    p4 = sobol_pool(16, seed=1, names=VARS + ["mu_channel_scale"])
    assert p4["mu_channel_scale"].between(0.8, 1.2).all()


def test_nuisance_is_kept_but_never_a_model_input():
    from sicsim.analysis import feature_set, wide_table
    pool = sobol_pool(8, seed=5)
    rows = []
    for _, r in pool.iterrows():
        for T in (300, 423):
            rows.append(dict(candidate_id=r.candidate_id, process_group_id=r.candidate_id, temperature_K=T,
                             converged=True, **{v: r[v] for v in VARS + ["mu_channel_scale"]},
                             vth_V=3.7 + 0.1 * r.npwell_scale, ss_mV_dec=112.0, ion_A_per_cm=0.017 * r.mu_channel_scale))
    w = wide_table(pd.DataFrame(rows))
    assert "mu_channel_scale" in w.columns
    assert not any("mu_channel" in c for c in feature_set(w, "S3").columns)


def test_identifiability_with_nuisance():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from identifiability import analyse
    rows = []
    for _, r in stage_a().iterrows():
        for T in (300, 423):
            t, q = T / 300, r.qit_eff_cm2 / -1e12
            m, w, n = r.mu_channel_scale, r.wjfet_scale, r.npwell_scale
            rows.append(dict(candidate_id=r.candidate_id, temperature_K=T,
                             vth_V=3.76 + 2.6 * (n - 1) + 2.32 * (q - 1) - 0.21 * (t - 1) / 0.41 - 0.05 * (m - 1),
                             ss_mV_dec=112 * t * (1 + 0.18 * (n - 1)), gm_max_S_per_cm=3.9e-3 * m / n ** 0.25,
                             ion_A_per_cm=0.0176 / (1.2 / (m * t) + 0.8 * t ** 2.4 / w), ron_mohm_cm2=1.2 / (m * t) + 0.8 * t ** 2.4 / w,
                             id_vds_req_A_per_cm=0.33 * w ** 0.2 * m ** 0.5 / t))
    res = analyse(pd.DataFrame(rows), 0.1, "nominal")
    assert res["parameters"][-1] == "mu_channel_scale"
    assert all(np.isfinite(v) for v in res["S2"]["crb_rel"].values())
