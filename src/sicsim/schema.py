"""Experiment / LLM-selection schemas and the validator (the validator has final authority:
structured output constrains FORMAT only, not physical or protocol correctness)."""
from __future__ import annotations

import json
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ReasonCode(str, Enum):
    HIGH_UNCERTAINTY = "HIGH_UNCERTAINTY"
    TARGET_CONFUSION_REGION = "TARGET_CONFUSION_REGION"
    BOUNDARY_COVERAGE = "BOUNDARY_COVERAGE"
    DIVERSITY = "DIVERSITY"
    TEMPERATURE_CONTRAST = "TEMPERATURE_CONTRAST"
    LOW_TRAIN_DENSITY = "LOW_TRAIN_DENSITY"


class Experiment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    run_id: str
    candidate_id: str
    process_group_id: str
    policy: str = "manual"
    round: int = Field(default=0, ge=0)
    temperature_K: float = Field(ge=300, le=423)
    wjfet_scale: float = Field(ge=0.8, le=1.2)
    npwell_scale: float = Field(ge=0.8, le=1.2)
    qit_eff_cm2: float = Field(ge=-3e12, le=3e12)
    mu_channel_scale: float = Field(default=1.0, ge=0.5, le=1.5)
    seed: int = 0


# run table columns (draft section "실험 로그") + extra numerics/feature columns
RUN_COLUMNS = [
    "run_id", "policy", "round", "candidate_id", "process_group_id",
    "temperature_K", "wjfet_scale", "npwell_scale", "qit_eff_cm2", "mu_channel_scale",
    "mesh_hash", "physics_hash", "solver_hash", "seed",
    "converged", "retry_count", "runtime_s",
    "vth_V", "ron_norm", "ss_mV_dec", "ion_A_per_cm", "ioff_A_per_cm",
    "code_commit", "created_at",
]
LLM_LOG_FIELDS = [
    "request_id", "model_id", "prompt_hash", "input_hash", "candidate_ids",
    "selected_ids", "validator_status", "reject_reason",
    "input_tokens", "output_tokens", "latency_s", "created_at",
]


class LLMSelection(BaseModel):
    model_config = ConfigDict(extra="forbid")
    selected_ids: list[str] = Field(min_length=1)
    reason_codes: list[ReasonCode] = Field(min_length=1)
    short_rationale: str = Field(max_length=400)


def selection_json_schema(allowed_ids) -> dict:
    """JSON schema sent as output_config.format (array length / uniqueness are NOT expressible in
    the supported schema subset -> enforced by validate_selection)."""
    return {
        "type": "object",
        "properties": {
            "selected_ids": {"type": "array", "items": {"type": "string", "enum": list(allowed_ids)}},
            "reason_codes": {"type": "array",
                             "items": {"type": "string", "enum": [r.value for r in ReasonCode]}},
            "short_rationale": {"type": "string"},
        },
        "required": ["selected_ids", "reason_codes", "short_rationale"],
        "additionalProperties": False,
    }


def validate_selection(raw, allowed_ids, batch_size: int, already_evaluated=()):
    """Return (LLMSelection, None) if accepted, else (None, reject_reason). Any violation rejects
    the WHOLE response (no partial acceptance)."""
    try:
        data = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
    except json.JSONDecodeError as e:
        return None, f"INVALID_JSON: {e.msg}"
    try:
        sel = LLMSelection.model_validate(data)
    except ValidationError as e:
        err = e.errors()[0]
        return None, f"SCHEMA: {'.'.join(map(str, err['loc']))}: {err['msg']}"
    ids = sel.selected_ids
    if len(ids) != batch_size:
        return None, f"BATCH_SIZE: got {len(ids)}, expected {batch_size}"
    if len(set(ids)) != len(ids):
        return None, "DUPLICATE_IDS"
    allowed = set(allowed_ids)
    bad = [i for i in ids if i not in allowed]
    if bad:
        return None, f"OUT_OF_LIST: {bad[:5]}"
    done = set(already_evaluated)
    rerun = [i for i in ids if i in done]
    if rerun:
        return None, f"ALREADY_EVALUATED: {rerun[:5]}"
    return sel, None
