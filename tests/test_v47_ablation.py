"""v4.7 RQ3 ablation: payload transforms, prompt choice, replay, condition D and the guard on live logs."""
import json
import subprocess
import sys
import types
from pathlib import Path

import numpy as np
import pandas as pd

from sicsim import llm
from sicsim.ablation import ANON, call_stats, shuffle_rng, top_random, transform_payload
from sicsim.alsim import run_policy
from sicsim.design import DESIGN_VARS, VARS, random_set, sobol_pool

ROOT = Path(__file__).resolve().parents[1]
PHYSICS_WORDS = ["sic", "mosfet", "jfet", "p-well", "pwell", "tcad", "devsim", "interface", "doping", "mobility",
                 "temperature", "wjfet", "npwell", "qit", "mu_channel"]


def payload(n=20, seed=3, rnd=2):
    rng = np.random.default_rng(0)
    u = np.sort(rng.uniform(0.1, 0.9, n))[::-1]
    cands = [dict(candidate_id=f"C{i:04d}", **{v: round(float(x), 3) for v, x in zip(DESIGN_VARS, rng.uniform(0, 1, 4))},
                  predictive_uncertainty=round(float(u[i]), 4), distance_to_train=round(float(rng.uniform(0, 0.5)), 4))
             for i in range(n)]
    return dict(round=rnd, seed=seed, batch_size=10, candidates=cands,
                model_summary=dict(n_train=60, cv_mae_norm={"wjfet_scale": 0.15, "npwell_scale": 0.19, "qit_eff_cm2": 0.08},
                                   worst_target="npwell_scale"))


def test_anon_hides_every_physics_name():
    p = payload()
    shown, truth = transform_payload(p, "anon")
    text = json.dumps(shown).lower() + llm.SYSTEM_PROMPT_ANON.lower()
    assert not [w for w in PHYSICS_WORDS if w in text]
    assert shown["model_summary"]["worst_target"] == "x2" and truth["mapping"] == ANON
    assert [c["candidate_id"] for c in shown["candidates"]] == [c["candidate_id"] for c in p["candidates"]]
    assert all(s["x1"] == c["wjfet_scale"] and s["predictive_uncertainty"] == c["predictive_uncertainty"]
               for s, c in zip(shown["candidates"], p["candidates"]))
    assert transform_payload(p, "named") == (p, None)


def test_shuffled_keeps_values_but_breaks_their_meaning():
    p = payload()
    shown, truth = transform_payload(p, "shuffled", shuffle_rng(3, 2))
    orig = {c["candidate_id"]: c for c in p["candidates"]}
    pairs = lambda cs: sorted((c["predictive_uncertainty"], c["distance_to_train"]) for c in cs)
    assert pairs(shown["candidates"]) == pairs(p["candidates"])                       # same values, new owners
    assert all(s[v] == orig[s["candidate_id"]][v] for s in shown["candidates"] for v in DESIGN_VARS)   # coordinates kept
    u = [c["predictive_uncertainty"] for c in shown["candidates"]]
    assert u == sorted(u, reverse=True)                                               # listed by displayed uncertainty
    assert shown["model_summary"]["worst_target"] != p["model_summary"]["worst_target"]
    assert sorted(shown["model_summary"]["cv_mae_norm"].values()) == sorted(p["model_summary"]["cv_mae_norm"].values())
    assert truth["true_order"] == [c["candidate_id"] for c in p["candidates"]] and truth["true_worst_target"] == "npwell_scale"
    assert transform_payload(p, "shuffled", shuffle_rng(3, 2))[0] == shown                # deterministic per (seed, round)
    assert p["candidates"][0]["predictive_uncertainty"] == max(c["predictive_uncertainty"] for c in p["candidates"])  # input untouched


def _fake_anthropic(captured, text):
    class Messages:
        def create(self, **kw):
            captured.update(kw)
            return types.SimpleNamespace(content=[types.SimpleNamespace(type="text", text=text)],
                                         usage=types.SimpleNamespace(input_tokens=10, output_tokens=5), stop_reason="end_turn")

    class Client:
        def __init__(self, api_key=None):
            self.messages = Messages()
    return types.SimpleNamespace(Anthropic=Client, __version__="fake")


def test_anon_variant_sends_the_anon_prompt_and_logs_what_was_shown(monkeypatch, tmp_path):
    cap = {}
    p = payload()
    shown, truth = transform_payload(p, "anon")
    ids = [c["candidate_id"] for c in p["candidates"][:10]]
    monkeypatch.setitem(sys.modules, "anthropic", _fake_anthropic(cap, json.dumps(
        dict(selected_ids=ids, reason_codes=["DIVERSITY"], short_rationale="ok"))))
    monkeypatch.setenv("MSEOKQ_CLAUDE", "k")
    log = tmp_path / "log.jsonl"
    sel, rec = llm.select(shown, [], {"dry_run": False, "variant": "anon"}, log, truth=truth)
    assert sel == ids and cap["system"] == llm.SYSTEM_PROMPT_ANON.format(k=10)
    rec = json.loads(log.read_text())
    assert rec["variant"] == "anon" and rec["payload"] == shown and rec["truth"]["mapping"] == ANON
    llm.select(p, [], {"dry_run": False, "variant": "shuffled"})
    assert cap["system"] == llm.SYSTEM_PROMPT.format(k=10)                           # C keeps the original prompt


def synth_wide(df):
    w, n, q = df.wjfet_scale.values, df.npwell_scale.values, df.qit_eff_cm2.values / 1e12
    m = df["mu_channel_scale"].values if "mu_channel_scale" in df else np.ones(len(df))
    out = pd.DataFrame(index=df.candidate_id.values)
    out["process_group_id"] = df.candidate_id.values
    for v in VARS + ["mu_channel_scale"]:
        out[v] = df[v].values if v in df else 1.0
    for T in (300, 423):
        s, t = (T - 300) / 123, T / 300
        out[f"vth_V@{T}"] = 3.8 + 1.2 * (n - 1) * (1 - 0.3 * s) - 2.32 * (q + 1) - 0.2 * s
        out[f"ss_mV_dec@{T}"] = 112 * t * (1 + 0.17 * (n - 1))
        out[f"ron_mohm_cm2@{T}"] = np.log10(1.2 / (m * t) + 0.8 * t ** 2.4 / w ** 1.5)
    return out


def test_replay_reproduces_a_logged_run_exactly(tmp_path):
    pool = synth_wide(sobol_pool(128, seed=1, names=VARS + ["mu_channel_scale"]))
    test = synth_wide(random_set(48, seed=2))
    log1, log2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    kw = dict(seed=0, n_init=16, batch=8, rounds=2, top_n=12)
    c1 = run_policy(pool, test, "llm", llm_cfg={"dry_run": True}, llm_log=log1, **kw)
    recs = [json.loads(x) for x in log1.read_text().splitlines()]
    c2 = run_policy(pool, test, "llm", llm_cfg={"replay": {(r["seed"], r["round"]): r for r in recs}}, llm_log=log2, **kw)
    rep = [json.loads(x) for x in log2.read_text().splitlines()]
    assert c1.equals(c2) and all(r["mode"] == "replay" and r["replay_hash_match"] for r in rep)
    assert [r["selected_ids"] for r in rep] == [r["selected_ids"] for r in recs]


def test_condition_d_and_shuffled_variant_run(tmp_path):
    pool = synth_wide(sobol_pool(128, seed=1, names=VARS + ["mu_channel_scale"]))
    test = synth_wide(random_set(48, seed=2))
    d = run_policy(pool, test, "top20_random", seed=0, n_init=16, batch=8, rounds=2, top_n=12)
    assert d.n_points.tolist() == [16, 24, 32] and d.mean_mae_norm.notna().all()
    log = tmp_path / "c.jsonl"
    run_policy(pool, test, "llm", seed=0, n_init=16, batch=8, rounds=2, top_n=12,
               llm_cfg={"dry_run": True, "variant": "shuffled"}, llm_log=log)
    recs = [json.loads(x) for x in log.read_text().splitlines()]
    assert all(r["variant"] == "shuffled" and r["truth"]["true_worst_target"] != r["payload"]["model_summary"]["worst_target"]
               for r in recs)
    top = np.arange(20)
    pick = top_random(top, 10, np.random.default_rng(0))
    assert len(set(pick)) == 10 and set(pick) <= set(top)


def test_call_stats_on_a_logged_call():
    p = payload()
    coords = pd.DataFrame({c["candidate_id"]: [c[v] for v in DESIGN_VARS] for c in p["candidates"]}, index=DESIGN_VARS).T
    shown, truth = transform_payload(p, "shuffled", shuffle_rng(3, 2))
    sel = [c["candidate_id"] for c in shown["candidates"][:10]]                     # 'follows the displayed numbers'
    st = call_stats(dict(validator_status="accepted", selected_ids=sel, payload=shown, truth=truth), coords, n_mc=200)
    assert st["overlap_shown"] == 1.0 and 0 <= st["overlap_true"] <= 1
    assert st["worst_displayed"] != st["worst_true"]
    assert all(0 <= st[k] <= 1 for k in ("p_wider_mpd_random", "p_widen_displayed_random", "p_widen_true_random"))
    assert call_stats(dict(validator_status="rejected"), coords) is None


def test_run_al_refuses_to_overwrite_live_calls(tmp_path):
    out = tmp_path / "nominal"; out.mkdir()
    (out / "llm_calls.jsonl").write_text(json.dumps({"mode": "live"}) + "\n")
    r = subprocess.run([sys.executable, str(ROOT / "scripts/run_al.py"), "--pool", "x", "--test", "y", "--out", str(tmp_path)],
                       capture_output=True, text=True)
    assert r.returncode != 0 and "holds live LLM calls" in r.stderr
    assert (out / "llm_calls.jsonl").exists()


def test_call_stats_without_payload_uses_the_candidate_order():
    p = payload()
    coords = pd.DataFrame({c["candidate_id"]: [c[v] for v in DESIGN_VARS] for c in p["candidates"]}, index=DESIGN_VARS).T
    ids = [c["candidate_id"] for c in p["candidates"]]
    st = call_stats(dict(validator_status="accepted", selected_ids=ids[5:15], candidate_ids=ids), coords, n_mc=100)
    assert st["overlap_true"] == st["overlap_shown"] == 0.5 and "widen_displayed" not in st
