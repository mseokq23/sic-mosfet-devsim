"""RQ3 selection statistics quoted in the paper (Section 4.4), recomputed from the committed LLM log.
  python scripts/rq3_diversity.py
 - overlap of the LLM batch with the uncertainty top-10 (mean over accepted calls)
 - calls whose batch is more spread out than the top-10 (mean pairwise distance, normalized 4-D design space)
 - calls whose batch is more spread along the target first named in the rationale (std of that variable)"""
import itertools, json, re, sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.design import load_bounds

calls = [json.loads(x) for x in open(ROOT / "results/al_live/nominal/llm_calls.jsonl")]
acc = [r for r in calls if r["validator_status"] == "accepted"]
cols = ["wjfet_scale", "npwell_scale", "qit_eff_cm2", "mu_channel_scale"]
B = load_bounds(); allb = {**B["variables"], **B.get("nuisance", {})}
lo = np.array([float(allb[c]["low"]) for c in cols]); hi = np.array([float(allb[c]["high"]) for c in cols])
d = pd.read_csv(ROOT / "configs/design_pool.csv").set_index("candidate_id")
P = pd.DataFrame((d[cols].values.astype(float) - lo) / (hi - lo), index=d.index, columns=cols)   # candidate_ids are in uncertainty order

def mpd(ids):
    X = P.loc[ids].values
    return np.mean([np.linalg.norm(a - b) for a, b in itertools.combinations(X, 2)])

overlap = np.mean([len(set(r["selected_ids"]) & set(r["candidate_ids"][:10])) / 10 for r in acc])
wider = sum(mpd(r["selected_ids"]) > mpd(r["candidate_ids"][:10]) for r in acc)
key = {"wjfet_scale": r"w_?jfet|jfet", "npwell_scale": r"n_?pw|npwell|p-well|pwell", "qit_eff_cm2": r"q_?it|qit"}
consistent = 0
for r in acc:
    t = r["short_rationale"].lower()
    pos = {c: (m.start() if (m := re.search(p, t)) else 10**9) for c, p in key.items()}
    c = min(pos, key=pos.get)
    if pos[c] < 10**9 and P.loc[r["selected_ids"], c].std() > P.loc[r["candidate_ids"][:10], c].std():
        consistent += 1
print(f"accepted calls: {len(acc)}/{len(calls)}")
print(f"mean overlap with uncertainty top-10: {overlap:.2f}")
print(f"wider batch than top-10 (mean pairwise distance): {wider}/{len(acc)}")
print(f"wider along the first-named target (std): {consistent}/{len(acc)}")
