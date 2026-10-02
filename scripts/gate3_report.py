"""Gate-3 report: mesh independence vs pre-registered tolerances, precision, repeatability, temperature."""
import json, sys
from pathlib import Path
import numpy as np, yaml
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import load_config, _Loader
from sicsim.extract import extract_features
from sicsim.utils import save_json
D = ROOT / "results" / "pretest" / "gate3"
cfg = load_config(); proto = yaml.load(open(ROOT / "configs" / "sweep_protocol.yaml"), Loader=_Loader)
R = {}
for p in D.glob("*.json"):
    if p.name.endswith(".job.json"): continue
    r = json.load(open(p)); r["features"] = extract_features(r, cfg) if r["converged"] else {}; R[p.stem] = r
KEYS = ["vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm", "ron_mohm_cm2", "id_vds_req_A_per_cm"]
def diff(a, b):
    out = {}
    for k in KEYS:
        x, y = a["features"].get(k, np.nan), b["features"].get(k, np.nan)
        out[k] = (x - y) if k == "vth_V" else (x - y) / y
    return out
tol = proto["mesh_study"]["tolerance"]; tmap = dict(vth_V="vth_V", ss_mV_dec="ss_rel", ron_mohm_cm2="ron_rel",
                                                   gm_max_S_per_cm="gm_rel", ion_A_per_cm="ion_rel")
mesh = {lv: R[f"ms{ms}_dp_300"] for lv, ms in (("coarse", "2.0"), ("medium", "1.5"), ("fine", "1.0"))}
summary = dict(mesh={lv: dict(nodes=r["n_nodes"], runtime_s=r["runtime_s"], n_solves=r["n_solves"], n_fail=r["n_fail"],
                              output_truncated_at_V=r.get("output_truncated_at_V"),
                              **{k: r["features"][k] for k in KEYS}) for lv, r in mesh.items()})
dm, dc = diff(mesh["medium"], mesh["fine"]), diff(mesh["coarse"], mesh["fine"])
summary["medium_vs_fine"] = dm; summary["coarse_vs_fine"] = dc
summary["medium_pass"] = {k: bool(abs(dm[k]) <= tol[t]) for k, t in tmap.items()}
summary["medium_accepted"] = all(summary["medium_pass"].values())
xp, dp = R["ms1.5_xp_300"], R["ms1.5_dp_300"]
summary["precision_dp_vs_xp"] = {k: v for k, v in diff(dp, xp).items() if k in ("vth_V", "ss_mV_dec", "gm_max_S_per_cm", "ion_A_per_cm")}
summary["kcl_floor"] = dict(double=dp["features"]["kcl_floor_A_per_cm"], extended=xp["features"]["kcl_floor_A_per_cm"])
summary["runtime_dp_vs_xp_transfer_only_s"] = dict(extended=xp["runtime_s"], extended_solves=xp["n_solves"])
rep = R["ms1.5_dp_300_rep"]
same = all(np.array_equal(np.array(dp["curves"][c][k]), np.array(rep["curves"][c][k]))
           for c, ks in (("transfer", ("vgs", "id", "is_")), ("output", ("vds", "id"))) for k in ks)
summary["repeatability_bitwise_identical"] = bool(same)
hot = R["ms1.5_dp_423"]
summary["temperature_300_to_423"] = {k: dict(T300=dp["features"][k], T423=hot["features"][k]) for k in KEYS}
summary["env"] = dp.get("env")
save_json(summary, ROOT / "results" / "pretest" / "gate3_summary.json")
print(json.dumps({k: summary[k] for k in ("medium_vs_fine", "coarse_vs_fine", "medium_pass", "medium_accepted",
                                           "precision_dp_vs_xp", "kcl_floor", "repeatability_bitwise_identical")}, indent=1, default=float))
for k in KEYS: print(f"{k}: 300K {dp['features'][k]:.4g} -> 423K {hot['features'][k]:.4g}")
# ---- figure
W = dp["width_cm"]
fig, ax = plt.subplots(2, 2, figsize=(10, 7.5))
for r, lab, st in ((dp, "300 K", "-"), (hot, "423 K", "--")):
    t = r["curves"]["transfer"]; vg = np.array(t["vgs"]); j = np.abs(np.array(t["id"])) / W
    ax[0, 0].semilogy(vg, j, st, label=f"{lab} (double)"); ax[0, 1].plot(vg, j, st, label=lab)
    o = r["curves"]["output"]; ax[1, 0].plot(o["vds"], np.array(o["id"]) / W, st, label=f"{lab}, VGS={o['vgs']:g} V")
t = xp["curves"]["transfer"]; ax[0, 0].semilogy(t["vgs"], np.abs(t["id"]) / W, ":", label="300 K (128-bit)")
ax[0, 0].axhline(cfg["extract"]["icc_A_per_cm"] / W, color="gray", lw=0.6)
for lo in cfg["extract"]["ss_window_A_per_cm"]: ax[0, 0].axhline(lo / W, color="gray", lw=0.4, ls=":")
ax[0, 0].axhline(summary["kcl_floor"]["double"] / W, color="r", lw=0.6, ls="-.", label="double-prec. floor")
ax[0, 0].set(xlabel="VGS (V)", ylabel="|JD| (A/cm²)  @VDS=0.1 V", title="(a) transfer (log)", ylim=(1e-28, 1e3))
ax[0, 1].set(xlabel="VGS (V)", ylabel="JD (A/cm²)", title="(b) transfer (linear)")
ax[1, 0].set(xlabel="VDS (V)", ylabel="JD (A/cm²)", title="(c) output")
for lv, st in (("coarse", ":"), ("medium", "-"), ("fine", "--")):
    t = mesh[lv]["curves"]["transfer"]; ax[1, 1].plot(t["vgs"], np.array(t["id"]) / W, st, label=f"{lv} ({mesh[lv]['n_nodes']} nodes)")
ax[1, 1].set(xlabel="VGS (V)", ylabel="JD (A/cm²)", title="(d) mesh study, 300 K")
for a in ax.flat: a.legend(fontsize=7); a.grid(alpha=0.3)
fig.suptitle("Gate 3: 2D half-cell 4H-SiC planar MOSFET (unipolar DD, baseline)")
fig.tight_layout(); fig.savefig(ROOT / "results" / "pretest" / "fig_gate3_mosfet.png", dpi=130)
