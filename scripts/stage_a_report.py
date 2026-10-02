"""Stage A report: one-at-a-time sensitivities, sign check vs PRE-STATED expectations, effect vs
mesh discretisation error, temperature contrast (dVth = Vth(423)-Vth(300))."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]
out = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results" / "pretest" / "stage_a"
df = pd.read_csv(out / "runs.csv")
F = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"]
# expected sign of d(feature)/d(+20% change) written before the runs (0 = ~no effect expected)
EXPECT = {"wjfet": dict(vth_V=0, ss_mV_dec=0, ion_A_per_cm=+1, ron_mohm_cm2=-1, id_vds_req_A_per_cm=+1),
          "npwell": dict(vth_V=+1, ss_mV_dec=+1, ion_A_per_cm=-1),
          "qit": dict(vth_V=+1, ss_mV_dec=0, ion_A_per_cm=-1),      # +20% = more negative charge
          # v1.0 (written before the v1.0 runs): higher channel mobility -> constant-current Vth slightly lower
          "mu": dict(vth_V=-1, ss_mV_dec=0, gm_max_S_per_cm=+1, ion_A_per_cm=+1, ron_mohm_cm2=-1, id_vds_req_A_per_cm=+1)}
gate3 = json.load(open(ROOT / "results" / "pretest" / "gate3_summary.json"))
mesh_err = {k: abs(v) for k, v in gate3["medium_vs_fine"].items()}   # Vth absolute (V), others relative
rows, ok = [], df[df["converged"].astype(str).str.lower() == "true"]
VARS_PRESENT = [t for t in ("wjfet", "npwell", "qit", "mu") if f"A_{t}_+20pct" in set(ok.candidate_id)]
for T in (300, 423):
    sub = ok[np.isclose(ok.temperature_K, T)].set_index("candidate_id")
    base = sub.loc["A_base"]
    for var in VARS_PRESENT:
        for lv in ("-20pct", "+20pct"):
            cid = f"A_{var}_{lv}"
            if cid not in sub.index: continue
            r = dict(T=T, var=var, level=lv)
            for f in F:
                d = sub.loc[cid, f] - base[f]
                r[f] = d if f == "vth_V" else d / base[f]          # Vth: volts, others: relative
            rows.append(r)
S = pd.DataFrame(rows)
S.to_csv(out / "stage_a_deltas.csv", index=False)
print(S.to_string(float_format=lambda x: f"{x:+.4f}"))
print("\nsign check (+20% runs) and |effect| / mesh error:")
checks = []
for (T, var), g in S[S.level == "+20pct"].groupby(["T", "var"]):
    for f, sgn in EXPECT[var].items():
        v = float(g[f].iloc[0]); ratio = abs(v) / max(mesh_err.get(f, 1e-9), 1e-9)
        good = (np.sign(v) == sgn) if sgn != 0 else (ratio < 10 or abs(v) < 0.02 * (1 if f != "vth_V" else 1))
        checks.append(dict(T=T, var=var, feature=f, delta=v, expected=sgn, ratio_to_mesh_err=ratio, pass_=bool(good)))
C = pd.DataFrame(checks); print(C.to_string(float_format=lambda x: f"{x:+.4g}"))
dv = {cid: float(ok[(ok.candidate_id == cid) & np.isclose(ok.temperature_K, 423)].vth_V.iloc[0] -
                 ok[(ok.candidate_id == cid) & np.isclose(ok.temperature_K, 300)].vth_V.iloc[0])
      for cid in sorted(set(ok.candidate_id)) if len(ok[ok.candidate_id == cid]) == 2}
print("\ndVth(423-300) per point [V]:", json.dumps({k: round(v, 4) for k, v in dv.items()}))
json.dump(dict(checks=C.to_dict("records"), dvth_T=dv, n_runs=int(len(df)), n_converged=int(len(ok))),
          open(out / "stage_a_summary.json", "w"), indent=1, default=float)
fig, ax = plt.subplots(1, 2, figsize=(11, 3.8), sharey=True)
for a, T in zip(ax, (300, 423)):
    g = S[(S["T"] == T) & (S.level == "+20pct")].set_index("var")
    x = np.arange(len(F)); w = 0.8 / len(VARS_PRESENT)
    for i, var in enumerate(VARS_PRESENT):
        if var in g.index:
            vals = [g.loc[var, f] * (10 if f == "vth_V" else 1) for f in F]
            a.bar(x + (i - (len(VARS_PRESENT) - 1) / 2) * w, vals, w, label=f"{var} +20%")
    a.set_xticks(x); a.set_xticklabels(["Vth×10 (V)", "SS", "gm,max", "Ion", "Ron,sp", "ID@2V"], rotation=20)
    a.axhline(0, color="k", lw=0.6); a.set_title(f"{T} K: change vs baseline (relative)"); a.grid(alpha=0.3)
ax[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(out / "fig_stage_a.png", dpi=130)
