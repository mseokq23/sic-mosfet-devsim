"""RQ1-RQ3 on pre-simulated pool/test sets.
  python scripts/run_al.py --pool results/pool --test results/test --seeds 10
RQ1: inverse-model accuracy for S1 (300 K) / S2 (300+423 K) / S3 (S2 + T-differences), train=pool, test=test.
RQ2/3: pool-based retrospective active learning for each policy and seed.
LLM policy: dry-run stand-in by default; --llm-live calls Claude with the key from ANTHROPIC_API_KEY or MSEOKQ_CLAUDE
(or --api-key-env NAME). Live mode aborts if no key is found or the API keeps failing (never silently dry-run).
v4.7 ablation (docs/PREDICTIONS_V47.md):
  --llm-variant named|anon|shuffled   what the LLM is shown (named = original RQ3 condition A)
  --replay-log PATH                   re-feed a logged LLM run (no API) to regenerate its payloads and curves
  --policies top20_random             condition D: 10 drawn uniformly from the uncertainty top-20 (no LLM)
  --skip-rq1                          do not recompute the RQ1 feature-set table
An existing log with live LLM calls is never overwritten unless --overwrite is given."""
import argparse, json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.alsim import run_policy
import yaml
from sicsim.analysis import add_noise, censor_floor, feature_set, fit_predict, metrics, wide_table
from sicsim.config import _Loader
from sicsim import llm as llm_mod
from sicsim.controls import compute_env
import datetime as dt, subprocess
from sicsim.design import VARS
ap = argparse.ArgumentParser()
ap.add_argument("--pool", required=True); ap.add_argument("--test", required=True)
ap.add_argument("--out", default=str(ROOT / "results" / "al"))
ap.add_argument("--seeds", type=int, default=10); ap.add_argument("--n-init", type=int, default=60)
ap.add_argument("--batch", type=int, default=10); ap.add_argument("--rounds", type=int, default=6)
ap.add_argument("--set", default="S2"); ap.add_argument("--model", default="rf")
ap.add_argument("--policies", nargs="+", default=["random", "sobol", "uncertainty", "llm"])
ap.add_argument("--llm-live", action="store_true"); ap.add_argument("--llm-model", default="claude-sonnet-5-5")
ap.add_argument("--noise", default="nominal", help="none|low|nominal|high (configs/noise_model.yaml)")
ap.add_argument("--api-key-env", default=None, help="env var holding the API key (default: ANTHROPIC_API_KEY, MSEOKQ_CLAUDE)")
ap.add_argument("--llm-variant", default="named", choices=["named", "anon", "shuffled"])
ap.add_argument("--replay-log", default=None, help="llm_calls.jsonl of a previous run to replay (no API calls)")
ap.add_argument("--skip-rq1", action="store_true"); ap.add_argument("--overwrite", action="store_true")
a = ap.parse_args()
out = Path(a.out) / a.noise; out.mkdir(parents=True, exist_ok=True)
if a.llm_live and a.replay_log:
    sys.exit("ERROR: --llm-live and --replay-log are exclusive")
if a.replay_log and a.llm_variant != "named":
    sys.exit("ERROR: --replay-log replays the original (named) condition only")
old_log = out / "llm_calls.jsonl"
if old_log.exists() and not a.overwrite and any(json.loads(x).get("mode") == "live" for x in open(old_log) if x.strip()):
    sys.exit(f"ERROR: {old_log} holds live LLM calls; choose another --out or pass --overwrite")
replay = None
if a.replay_log:
    recs = [json.loads(x) for x in open(a.replay_log) if x.strip()]
    replay = {(r["seed"], r["round"]): r for r in recs}
    if len(replay) != len(recs):
        sys.exit("ERROR: replay log has duplicate (seed, round) entries")
    print(f"REPLAY: {len(recs)} logged calls from {a.replay_log}")
key_env = None
if a.llm_live and "llm" in a.policies:
    key, key_env = llm_mod.api_key_from_env(a.api_key_env)
    if not key:
        sys.exit("ERROR: --llm-live but no API key found in env "
                 f"{a.api_key_env or ' / '.join(llm_mod.API_KEY_ENVS)}. Check the Codespaces secret's repository access "
                 "and restart the codespace.")
    print(f"LLM LIVE: model={a.llm_model}, key from ${key_env}")
(out / "llm_calls.jsonl").unlink(missing_ok=True)          # never mix logs of different runs
pool = wide_table(pd.read_csv(Path(a.pool) / "runs.csv")).sort_index()     # C0000.. = Sobol order
test = wide_table(pd.read_csv(Path(a.test) / "runs.csv"))
nz = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)
lv = nz["levels"][a.noise]
pool = add_noise(pool, nz, lv, nz["seeds"]["pool"]); test = add_noise(test, nz, lv, nz["seeds"]["test"])
fl = nz.get("current_floor_A_per_cm")
pool, test = censor_floor(pool, fl), censor_floor(test, fl)
print(f"noise={a.noise} (x{lv}, {nz['version']}, floor={fl} A/cm)")
if not a.skip_rq1:
    rq1 = {}
    for S in ("S1", "S2", "S3"):
        for kind in ("rf", "et", "gp"):
            P = fit_predict(feature_set(pool, S).values, pool[VARS].values, feature_set(test, S).values, kind)
            rq1[f"{S}_{kind}"] = metrics(test[VARS].values, P)
    json.dump(rq1, open(out / "rq1_feature_sets.json", "w"), indent=1)
    print({k: round(v["mean_mae_norm"], 4) for k, v in rq1.items()})
llm_cfg = dict(dry_run=not a.llm_live, model=a.llm_model, api_key_env=key_env, variant=a.llm_variant, replay=replay)
git = lambda *g: subprocess.run(["git", *g], cwd=ROOT, capture_output=True, text=True).stdout.strip()
commit = git("rev-parse", "--short", "HEAD")
llm_mode = "replay" if replay is not None else ("live" if a.llm_live else "dry-run")
json.dump(dict(noise=a.noise, noise_version=nz["version"], current_floor=fl, seeds=a.seeds, n_init=a.n_init, batch=a.batch,
               rounds=a.rounds, feature_set=a.set, model=a.model, policies=a.policies,
               llm_mode=llm_mode, llm_model=a.llm_model if a.llm_live else None, llm_variant=a.llm_variant,
               replay_log=a.replay_log, api_key_env=key_env, code_commit=commit,
               code_dirty=bool(git("status", "--porcelain", "--", "src", "scripts", "configs")),
               plan_commit=git("log", "-1", "--format=%h", "--", "docs/PREDICTIONS_V47.md") or None,
               env=compute_env(), created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")),
          open(out / "meta.json", "w"), indent=1)
curves = []
for pol in a.policies:
    for s in range(a.seeds):
        curves.append(run_policy(pool, test, pol, seed=s, n_init=a.n_init, batch=a.batch, rounds=a.rounds,
                                 set_name=a.set, model=a.model, llm_cfg=llm_cfg, llm_log=out / "llm_calls.jsonl"))
        print(pol, s, round(curves[-1].mean_mae_norm.iloc[-1], 4), flush=True)
pd.concat(curves).to_csv(out / "al_curves.csv", index=False)
logp = out / "llm_calls.jsonl"
if logp.exists():
    L = [json.loads(x) for x in open(logp)]
    acc = sum(r["validator_status"] == "accepted" for r in L)
    print(f"LLM calls: {len(L)} | mode {sorted({r['mode'] for r in L})} | variant {sorted({r.get('variant', 'named') for r in L})} | "
          f"accepted {acc} | rejected->fallback {len(L) - acc} | tokens in/out {sum(r['input_tokens'] for r in L)}/{sum(r['output_tokens'] for r in L)}")
    if replay is not None:
        hm = [r.get("replay_hash_match") for r in L]
        print(f"replay: payload hash identical to the original log in {sum(map(bool, hm))}/{len(hm)} calls")
