"""v4.7 RQ3 ablation (analysis plan: docs/PREDICTIONS_V47.md).

What the LLM is shown in each round, and how its batch relates to what it was shown.
  named     unchanged payload (condition A, the original RQ3 run)
  anon      variable names replaced by x1..x4 and a physics-free system prompt (condition B)
  shuffled  per round, the (predictive_uncertainty, distance_to_train) pairs are permuted across the 20
            candidates and listed in the displayed-uncertainty order; the cross-validation errors are
            cyclically shifted across the three targets, so the displayed worst target is always wrong
            (condition C). Candidate IDs and their design coordinates are unchanged.
Condition D (random 10 of the uncertainty top-20, no LLM) is the 'top20_random' policy in alsim.py.
"""
from __future__ import annotations

import copy
import itertools

import numpy as np

from .design import NUISANCE, VARS

VARIANTS = ("named", "anon", "shuffled")
ANON = {v: f"x{i + 1}" for i, v in enumerate(VARS + NUISANCE)}       # wjfet->x1, npwell->x2, qit->x3, mu->x4
SHUFFLE_SALT = 47                                                   # rng = default_rng([seed, round, 47])


def shuffle_rng(seed: int, rnd: int):
    return np.random.default_rng([int(seed), int(rnd), SHUFFLE_SALT])


def transform_payload(payload: dict, variant: str, rng=None):
    """Return (payload shown to the LLM, truth record for the log). 'named' returns the payload itself."""
    if variant == "named":
        return payload, None
    p = copy.deepcopy(payload)
    ms = p.get("model_summary", {})
    if variant == "anon":
        p["candidates"] = [{ANON.get(k, k): v for k, v in c.items()} for c in p["candidates"]]
        if "cv_mae_norm" in ms:
            ms["cv_mae_norm"] = {ANON.get(k, k): v for k, v in ms["cv_mae_norm"].items()}
        if "worst_target" in ms:
            ms["worst_target"] = ANON.get(ms["worst_target"], ms["worst_target"])
        return p, dict(variant="anon", mapping=ANON)
    if variant == "shuffled":
        if rng is None:
            rng = shuffle_rng(payload.get("seed", 0), payload.get("round", 0))
        cands = p["candidates"]
        vals = [(c["predictive_uncertainty"], c["distance_to_train"]) for c in cands]
        perm = rng.permutation(len(cands))
        for c, j in zip(cands, perm):
            c["predictive_uncertainty"], c["distance_to_train"] = vals[j]
        cands.sort(key=lambda c: -c["predictive_uncertainty"])        # displayed-uncertainty order, like A
        truth = dict(variant="shuffled", true_order=[c["candidate_id"] for c in payload["candidates"]],
                     true_uncertainty={c["candidate_id"]: c["predictive_uncertainty"] for c in payload["candidates"]},
                     true_distance={c["candidate_id"]: c["distance_to_train"] for c in payload["candidates"]})
        if "cv_mae_norm" in ms:
            keys = list(ms["cv_mae_norm"])
            shift = int(rng.integers(1, len(keys)))
            rolled = np.roll(np.array([ms["cv_mae_norm"][k] for k in keys], float), shift)
            ms["cv_mae_norm"] = {k: float(v) for k, v in zip(keys, rolled)}
            truth["true_worst_target"] = payload["model_summary"].get("worst_target")
            truth["cv_shift"] = shift
            ms["worst_target"] = max(keys, key=lambda k: ms["cv_mae_norm"][k])
        return p, truth
    raise ValueError(f"unknown LLM variant {variant!r}; choose from {VARIANTS}")


def top_random(top_idx, k: int, rng):
    """Condition D: k distinct entries drawn uniformly from the uncertainty top-N indices."""
    return list(rng.choice(np.asarray(top_idx), k, replace=False))


# ---------------------------------------------------------------- behaviour of one logged call
def _mpd(X):
    return float(np.mean([np.linalg.norm(a - b) for a, b in itertools.combinations(X, 2)]))


def call_stats(rec: dict, coords, n_mc=2000, mc_seed=0) -> dict | None:
    """Batch statistics of one accepted call. coords: DataFrame (index candidate_id; columns VARS+NUISANCE,
    normalised to [0, 1]). Uses rec['payload'] (logged since v4.7); for older logs without it, the candidate
    list (true uncertainty order) is used and the worst-target statistics are skipped."""
    if rec.get("validator_status") != "accepted":
        return None
    pay, truth = rec.get("payload") or {"candidates": [{"candidate_id": c} for c in rec["candidate_ids"]]}, rec.get("truth") or {}
    shown = [c["candidate_id"] for c in pay["candidates"]]            # displayed-uncertainty order
    true_order = truth.get("true_order", shown)
    inv = {v: k for k, v in (truth.get("mapping") or {}).items()}
    w_disp = pay.get("model_summary", {}).get("worst_target")
    w_disp = inv.get(w_disp, w_disp)
    w_true = truth.get("true_worst_target", w_disp)
    sel = list(rec["selected_ids"])
    k = len(sel)
    top_shown, top_true = shown[:k], true_order[:k]
    C = coords.loc[shown]
    out = dict(seed=rec.get("seed"), round=rec.get("round"), worst_displayed=w_disp, worst_true=w_true,
               overlap_true=len(set(sel) & set(top_true)) / k, overlap_shown=len(set(sel) & set(top_shown)) / k,
               wider_mpd=_mpd(coords.loc[sel].values) > _mpd(coords.loc[top_shown].values))
    rng = np.random.default_rng(mc_seed)
    subs = [rng.choice(len(shown), k, replace=False) for _ in range(n_mc)]
    ref_mpd = _mpd(coords.loc[top_shown].values)
    out["p_wider_mpd_random"] = float(np.mean([_mpd(C.values[s]) > ref_mpd for s in subs]))
    for tag, v in (("displayed", w_disp), ("true", w_true)):
        if v in coords.columns:
            ref = coords.loc[top_shown, v].std()
            out[f"widen_{tag}"] = bool(coords.loc[sel, v].std() > ref)
            out[f"p_widen_{tag}_random"] = float(np.mean([C[v].values[s].std(ddof=1) > ref for s in subs]))
    return out
