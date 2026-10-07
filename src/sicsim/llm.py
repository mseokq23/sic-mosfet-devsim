"""LLM-assisted batch selection (Claude API structured output) + dry-run stand-in + replay + JSONL logging.

The LLM only RANKS/CHOOSES among numerically pre-screened candidate IDs; it never runs code or DEVSIM.
Every response passes schema.validate_selection; on rejection the fixed fallback (uncertainty
policy) is used and the rejection is logged.
"""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
import time
import uuid

from .schema import selection_json_schema, validate_selection

# Environment variables searched for the API key (names only; the key itself is never printed or logged).
# MSEOKQ_CLAUDE = the user's Codespaces secret name.
API_KEY_ENVS = ("ANTHROPIC_API_KEY", "MSEOKQ_CLAUDE")


class LLMUnavailable(RuntimeError):
    """Live LLM mode was requested but cannot be served -> abort; never silently substitute dry-run."""


def api_key_from_env(name=None):
    for n in ((name,) if name else API_KEY_ENVS):
        v = os.environ.get(n)
        if v:
            return v, n
    return None, None

SYSTEM_PROMPT = """You choose the next batch of TCAD (DEVSIM) simulation candidates in an active-learning
study that estimates three latent process variables of a 4H-SiC planar MOSFET (JFET width scale, P-well
doping scale, effective interface charge) from multi-temperature electrical features.
Rules:
- Choose ONLY candidate IDs from the provided list; never invent IDs or parameter values.
- Return exactly {k} distinct IDs.
- Do not select only by predictive_uncertainty; balance it with diversity (distance_to_train, spread of
  process values) and the current worst-estimated target described in model_summary.
- reason_codes must come from the allowed enum; short_rationale: at most two sentences.
- Never claim that the selection guarantees an improvement."""

# v4.7 ablation B: same rules, no device/physics context (variables are x1..x4, see ablation.ANON).
SYSTEM_PROMPT_ANON = """You choose the next batch of simulation candidates in an active-learning study that
estimates three latent input variables (x1, x2, x3) of a simulator from its outputs; x4 is varied but not
estimated.
Rules:
- Choose ONLY candidate IDs from the provided list; never invent IDs or parameter values.
- Return exactly {k} distinct IDs.
- Do not select only by predictive_uncertainty; balance it with diversity (distance_to_train, spread of
  input values) and the current worst-estimated target described in model_summary.
- reason_codes must come from the allowed enum; short_rationale: at most two sentences.
- Never claim that the selection guarantees an improvement."""

PROMPTS = {"named": SYSTEM_PROMPT, "shuffled": SYSTEM_PROMPT, "anon": SYSTEM_PROMPT_ANON}


def _h(obj) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def call_claude(payload: dict, allowed_ids, model: str, api_key: str, max_tokens=1024, temperature=None, retries=3,
                system_prompt=SYSTEM_PROMPT):
    import anthropic
    client = anthropic.Anthropic(api_key=api_key)
    transient = tuple(getattr(anthropic, n) for n in ("APIConnectionError", "RateLimitError", "InternalServerError")
                      if hasattr(anthropic, n))
    kw = dict(model=model, max_tokens=max_tokens, system=system_prompt.format(k=payload["batch_size"]),
              messages=[{"role": "user", "content": json.dumps(payload, sort_keys=True)}])
    fmt = {"format": {"type": "json_schema", "schema": selection_json_schema(allowed_ids)}}
    if temperature is not None:
        kw["temperature"] = temperature
    t0 = time.time()
    for attempt in range(retries):
        try:
            try:
                resp = client.messages.create(**kw, output_config=fmt)
            except TypeError:                           # older SDK without the named argument
                resp = client.messages.create(**kw, extra_body={"output_config": fmt})
            break
        except transient:
            if attempt == retries - 1:
                raise
            time.sleep(2 * 2 ** attempt)
    text = next((b.text for b in resp.content if getattr(b, "type", "") == "text"), "")
    return text, dict(input_tokens=resp.usage.input_tokens, output_tokens=resp.usage.output_tokens,
                      latency_s=round(time.time() - t0, 3), stop_reason=resp.stop_reason)


def dry_run(payload: dict) -> str:
    """Deterministic stand-in with the same I/O contract (pipeline tests, no API cost):
    rank by uncertainty*distance, take the top k."""
    c = sorted(payload["candidates"], key=lambda d: -d["predictive_uncertainty"] * (0.5 + d["distance_to_train"]))
    return json.dumps(dict(selected_ids=[d["candidate_id"] for d in c[:payload["batch_size"]]],
                           reason_codes=["HIGH_UNCERTAINTY", "DIVERSITY"],
                           short_rationale="dry-run: uncertainty weighted by distance to training set."))


def select(payload: dict, already_evaluated, cfg: dict, log_path=None, truth=None):
    """Return (selected_ids or None, log_record).
    cfg: dry_run (default True), model, api_key_env, max_tokens, temperature,
         variant ('named' | 'anon' | 'shuffled': only picks the system prompt; the payload is already transformed),
         replay ({(seed, round): logged record}: re-feed a logged response through the validator, no API call)."""
    allowed = [d["candidate_id"] for d in payload["candidates"]]
    k = payload["batch_size"]
    model = cfg.get("model", "claude-sonnet-5-5")
    variant = cfg.get("variant", "named")
    if variant not in PROMPTS:
        raise ValueError(f"unknown LLM variant {variant!r}")
    prompt = PROMPTS[variant]
    replay = cfg.get("replay")
    live = replay is None and not cfg.get("dry_run", True)
    key, key_env = api_key_from_env(cfg.get("api_key_env")) if live else (None, None)
    if live and not key:
        raise LLMUnavailable("live LLM requested but no API key in env " + ", ".join((cfg.get("api_key_env"),) if cfg.get("api_key_env") else API_KEY_ENVS))
    usage = dict(input_tokens=0, output_tokens=0, latency_s=0.0, stop_reason=None)
    extra = {}
    if replay is not None:
        src = replay.get((payload.get("seed"), payload.get("round")))
        if src is None:
            raise LLMUnavailable(f"replay: no logged call for seed={payload.get('seed')} round={payload.get('round')}")
        raw, model, mode = src["raw_response"], src["model_id"], "replay"
        extra = dict(replay_of=src.get("request_id"), replay_hash_match=src.get("input_hash") == _h(payload))
    elif live:
        try:
            raw, usage = call_claude(payload, allowed, model, key, cfg.get("max_tokens", 1024), cfg.get("temperature"),
                                     system_prompt=prompt)
        except Exception as e:                          # after retries -> abort the run (no silent fallback)
            raise LLMUnavailable(f"Claude API call failed: {type(e).__name__}: {str(e)[:200]}") from e
        mode = "live"
    else:
        raw, model, mode = dry_run(payload), "dry-run", "dry-run"
    sel, reason = validate_selection(raw, allowed, k, already_evaluated)   # rejection -> pre-registered fallback
    rec = dict(request_id=str(uuid.uuid4()), model_id=model, mode=mode, variant=variant, api_key_env=key_env,
               prompt_hash=_h(prompt.format(k=k)), input_hash=_h(payload), candidate_ids=allowed,
               selected_ids=sel.selected_ids if sel else None,
               reason_codes=[r.value for r in sel.reason_codes] if sel else None,
               short_rationale=sel.short_rationale if sel else None,
               validator_status="accepted" if sel else "rejected", reject_reason=reason, raw_response=raw,
               temperature=cfg.get("temperature"), sdk=_sdk_version(), **usage,
               created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               round=payload.get("round"), seed=payload.get("seed"), payload=payload, truth=truth, **extra)
    if log_path:
        with open(log_path, "a") as f:
            f.write(json.dumps(rec) + "\n")
    return (sel.selected_ids if sel else None), rec


def _sdk_version():
    try:
        import anthropic
        return anthropic.__version__
    except Exception:
        return None
