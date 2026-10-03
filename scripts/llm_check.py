"""Pre-flight check: ONE small structured-output request (API key, model, output_config, validator).
  python scripts/llm_check.py [--model claude-sonnet-5-5] [--api-key-env MSEOKQ_CLAUDE]
The key is read from the environment and never printed."""
import argparse, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim import llm
from sicsim.schema import validate_selection
ap = argparse.ArgumentParser(); ap.add_argument("--model", default="claude-sonnet-5-5"); ap.add_argument("--api-key-env", default=None)
a = ap.parse_args()
key, name = llm.api_key_from_env(a.api_key_env)
if not key:
    sys.exit(f"NO KEY in env {a.api_key_env or ' / '.join(llm.API_KEY_ENVS)} -> check the Codespaces secret (repository access) and restart the codespace")
payload = dict(round=0, seed=0, batch_size=2,
               model_summary=dict(n_train=60, cv_mae_norm={"wjfet_scale": 0.15, "npwell_scale": 0.15, "qit_eff_cm2": 0.08}, worst_target="npwell_scale"),
               candidates=[dict(candidate_id=f"C{i:04d}", wjfet_scale=0.2 * i, npwell_scale=1 - 0.2 * i, qit_eff_cm2=0.5,
                                mu_channel_scale=0.5, predictive_uncertainty=round(0.1 + 0.05 * i, 3), distance_to_train=round(0.3 - 0.05 * i, 3))
                          for i in range(5)])
allowed = [c["candidate_id"] for c in payload["candidates"]]
raw, usage = llm.call_claude(payload, allowed, a.model, key)
sel, reason = validate_selection(raw, allowed, 2)
print(f"key env: ${name} | model: {a.model} | latency {usage['latency_s']} s | tokens in/out {usage['input_tokens']}/{usage['output_tokens']}"
      f" | stop: {usage['stop_reason']} | validator: {'ACCEPTED' if sel else 'REJECTED: ' + reason}")
print("response:", raw[:400])
sys.exit(0 if sel else 2)
