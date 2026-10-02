"""Local identifiability from Stage A one-at-a-time runs: Cramer-Rao bound (CRB) under the
pre-registered noise model, for S1 (300 K features) vs S2 (300 + 423 K).
  python scripts/identifiability.py results/stage_a [--level 0.1] [--noise nominal]
J[k, j] = d feature_k / d(relative change of variable j), central differences at +-level.
Assumptions: linearised at the nominal point; noise independent across features and temperatures.
S3 (= S2 + temperature differences) has exactly the same Fisher information as S2, so any S3 gain
in RQ1 is an ML-representation effect, not additional information."""
import argparse, json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import _Loader
from sicsim.design import _spec, load_bounds
FEATS = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"]
TARGETS = {"wjfet_scale": "wjfet", "npwell_scale": "npwell", "qit_eff_cm2": "qit"}
NUISANCE = {"mu_channel_scale": "mu"}          # included automatically if Stage A has A_mu_* runs


def jacobian(df, T, level, tags):
    sub = df[np.isclose(df.temperature_K.astype(float), T)].set_index("candidate_id")
    base, pct = sub.loc["A_base"], f"{round(level * 100)}pct"
    J = np.zeros((len(FEATS), len(tags)))
    for j, tag in enumerate(tags.values()):
        fp, fm = sub.loc[f"A_{tag}_+{pct}"], sub.loc[f"A_{tag}_-{pct}"]
        for k, f in enumerate(FEATS):
            d = (float(fp[f]) - float(fm[f])) / (2 * level)
            J[k, j] = d if f == "vth_V" else d / float(base[f])
    return J


def sigmas(nz, mult):
    return np.array([nz["absolute"].get(f, nz["relative"].get(f, np.nan)) for f in FEATS]) * mult


def crb(J, sig):
    W = J / sig[:, None]
    C = np.linalg.inv(W.T @ W)
    s = np.sqrt(np.diag(C))
    return s, C / np.outer(s, s)


def analyse(df, level=0.1, noise="nominal"):
    nz = yaml.load(open(ROOT / "configs" / "noise_model.yaml"), Loader=_Loader)
    b = load_bounds()
    pct = f"{round(level * 100)}pct"
    TAGS = dict(TARGETS)
    TAGS.update({v: t for v, t in NUISANCE.items() if f"A_{t}_+{pct}" in set(df.candidate_id)})
    spec = lambda v: _spec(b, v)
    rng = np.array([(spec(v)["high"] - spec(v)["low"]) / abs(spec(v)["nominal"]) for v in TAGS])
    sig = sigmas(nz, nz["levels"][noise])
    J3, J4 = jacobian(df, 300, level, TAGS), jacobian(df, 423, level, TAGS)
    out = dict(level=level, noise=noise, parameters=list(TAGS), J300=J3.tolist(), J423=J4.tolist())
    for name, J, s in (("S1", J3, sig), ("S2", np.vstack([J3, J4]), np.concatenate([sig, sig]))):
        sd, corr = crb(J, s)
        out[name] = dict(crb_rel={v: float(x) for v, x in zip(TAGS, sd)},
                         crb_pct_of_range={v: float(100 * x / r) for v, x, r in zip(TAGS, sd, rng)},
                         corr_npwell_qit=float(corr[1, 2]))
    out["S2_over_S1"] = {v: out["S2"]["crb_rel"][v] / out["S1"]["crb_rel"][v] for v in TAGS}
    out["repetition_reference"] = 1 / np.sqrt(2)   # S2/S1 if 423 K were just a repeated 300 K measurement
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("stage_a_dir")
    ap.add_argument("--level", type=float, default=0.1); ap.add_argument("--noise", default="nominal")
    a = ap.parse_args()
    df = pd.read_csv(Path(a.stage_a_dir) / "runs.csv")
    df = df[df.converged.astype(str).str.lower() == "true"]
    res = analyse(df, a.level, a.noise)
    json.dump(res, open(Path(a.stage_a_dir) / f"identifiability_{a.noise}.json", "w"), indent=1)
    for S in ("S1", "S2"):
        print(S, "CRB (% of DOE range):", {k: round(v, 2) for k, v in res[S]["crb_pct_of_range"].items()},
              "| corr(npwell,qit):", round(res[S]["corr_npwell_qit"], 3))
    print("S2/S1 CRB ratio:", {k: round(v, 3) for k, v in res["S2_over_S1"].items()},
          "(0.707 = mere repetition)")
