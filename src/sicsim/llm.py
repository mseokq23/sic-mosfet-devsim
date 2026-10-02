"""LLM-assisted batch selection (Claude API structured output) + dry-run stand-in + JSONL logging.

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


def _h(obj) -> str:
    s = obj if isinstance(obj, str) else json.dumps(obj, sort_keys=True)
    return hashlib.sha256(s.encode()).hexdigest()[:16]


def call_claude(payload: dict, allowed_ids, model: str, max_tokens=1024, temperature=None):
    import anthropic
    client = anthropic.Anthropic()
    kw = dict(model=model, max_tokens=max_tokens, system=SYSTEM_PROMPT.format(k=payload["batch_size"]),
              messages=[{"role": "user", "content": json.dumps(payload, sort_keys=True)}])
    fmt = {"format": {"type": "json_schema", "schema": selection_json_schema(allowed_ids)}}
    if temperature is not None:
        kw["temperature"] = temperature
    t0 = time.time()
    try:
        resp = client.messages.create(**kw, output_config=fmt)
    except TypeError:                                   # older SDK without the named argument
        resp = client.messages.create(**kw, extra_body={"output_config": fmt})
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


def select(payload: dict, already_evaluated, cfg: dict, log_path=None):
    """Return (selected_ids or None, log_record)."""
    allowed = [d["candidate_id"] for d in payload["candidates"]]
    k = payload["batch_size"]
    model = cfg.get("model", "claude-sonnet-5-5")
    use_api = (not cfg.get("dry_run", True)) and bool(os.environ.get("ANTHROPIC_API_KEY"))
    usage = dict(input_tokens=0, output_tokens=0, latency_s=0.0, stop_reason=None)
    try:
        if use_api:
            raw, usage = call_claude(payload, allowed, model, cfg.get("max_tokens", 1024), cfg.get("temperature"))
        else:
            raw, model = dry_run(payload), "dry-run"
        sel, reason = validate_selection(raw, allowed, k, already_evaluated)
    except Exception as e:  # API/network errors are logged as rejections
        raw, sel, reason = "", None, f"API_ERROR: {type(e).__name__}: {e}"[:300]
    rec = dict(request_id=str(uuid.uuid4()), model_id=model,
               prompt_hash=_h(SYSTEM_PROMPT.format(k=k)), input_hash=_h(payload), candidate_ids=allowed,
               selected_ids=sel.selected_ids if sel else None,
               reason_codes=[r.value for r in sel.reason_codes] if sel else None,
               short_rationale=sel.short_rationale if sel else None,
               validator_status="accepted" if sel else "rejected", reject_reason=reason, raw_response=raw,
               temperature=cfg.get("temperature"), sdk=_sdk_version(), **usage,
               created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
               round=payload.get("round"), seed=payload.get("seed"))
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
