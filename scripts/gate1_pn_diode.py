"""Gate 1: 1D 4H-SiC PN diode - equilibrium, II on/off, 300/423 K, precision noise floor."""
import sys, time, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sicsim.config import load_config, material_from
from sicsim import devices as dv, physics as ph
from sicsim.solver import ramp, STATS
from sicsim.params import Q, EPS0
from sicsim.utils import reset_devsim, save_json, env_info

OUT = Path(__file__).resolve().parents[1] / "results" / "pretest"
cfg = load_config(); mat = material_from(cfg); g = cfg["pn_diode"]
tol = cfg["numerics"]["tol"]


def analytic(T, ii):
    d = mat.derived(T); NA, ND = g["NA"], g["ND"]
    if ii:
        a = mat.gA / d["p1A"]; p0 = (-1 + math.sqrt(1 + 4 * a * NA)) / (2 * a)
        b = mat.gD / d["n1D"]; n0 = (-1 + math.sqrt(1 + 4 * b * ND)) / (2 * b)
    else:
        p0, n0 = NA, ND
    vbi = d["Vt"] * math.log(p0 * n0 / d["ni"] ** 2)
    eps = mat.eps_r * EPS0
    W = math.sqrt(2 * eps * vbi / Q * (NA + ND) / (NA * ND))
    return dict(p0=p0, n0=n0, vbi=vbi, xn_um=W * NA / (NA + ND) * 1e4, xp_um=W * ND / (NA + ND) * 1e4, ni=d["ni"])


def run(T, ii, extended=True, iv=True):
    reset_devsim(); ph.set_extended_precision(extended)
    t0 = time.time()
    lay = dv.build_pn_diode("pn", cfg)
    dv.setup_physics("pn", lay, mat, T, ii=ii)
    dv.equilibrate("pn", lay, ii=ii, tol=tol)
    x = ph.node_array("pn", "sic", "x") * 1e4
    psi = ph.node_array("pn", "sic", "Potential")
    n = ph.node_array("pn", "sic", "Electrons"); p = ph.node_array("pn", "sic", "Holes")
    a = analytic(T, ii); xj = g["xj_um"]
    i_p = np.argmin(abs(x - 0.5)); i_n = np.argmin(abs(x - 8.0))
    # depletion edges: carrier density reaches 50% of its neutral value
    xn = x[(x > xj) & (n >= 0.5 * n[i_n])].min() - xj
    xp = xj - x[(x < xj) & (p >= 0.5 * p[i_p])].max()
    res = dict(T=T, ii=ii, extended=extended, vbi_sim=psi[-1] - psi[0], vbi_ana=a["vbi"],
               p_neutral_sim=p[i_p], p_neutral_ana=a["p0"], n_neutral_sim=n[i_n], n_neutral_ana=a["n0"],
               ionized_frac_p=p[i_p] / g["NA"], xn_um_sim=xn, xn_um_ana=a["xn_um"],
               xp_um_sim=xp, xp_um_ana=a["xp_um"], ni=a["ni"],
               profile=dict(x=x.tolist(), psi=psi.tolist(), n=n.tolist(), p=p.tolist()))
    if iv:
        V, I = [], []
        ramp("pn", "anode", 3.2, 0.1, callback=lambda v: (V.append(v), I.append(ph.contact_current("pn", "anode"))))
        res.update(V=V, I=I)
    res["runtime_s"] = time.time() - t0
    return res


results = []
for T in (300.0, 423.0):
    for ii in (True, False):
        r = run(T, ii); results.append(r)
        print(f"T={T:.0f} II={ii}: Vbi sim/ana = {r['vbi_sim']:.4f}/{r['vbi_ana']:.4f} V, "
              f"p0 sim/ana = {r['p_neutral_sim']:.3e}/{r['p_neutral_ana']:.3e} (ionized {100*r['ionized_frac_p']:.1f}%), "
              f"xn sim/ana = {r['xn_um_sim']:.3f}/{r['xn_um_ana']:.3f} um, t={r['runtime_s']:.1f}s")
dbl = run(300.0, True, extended=False)
print("double precision 300K: |I| at 0.1..1.0 V:", ["%.1e" % i for i in dbl["I"][:10]])

# ---------------- figure
fig, ax = plt.subplots(1, 2, figsize=(10, 4))
for r in results:
    if not r["ii"]:
        continue
    pr = r["profile"]; x = np.array(pr["x"])
    ax[0].semilogy(x, pr["n"], label=f"n, {r['T']:.0f} K"); ax[0].semilogy(x, pr["p"], "--", label=f"p, {r['T']:.0f} K")
ax[0].set_xlim(0, 5); ax[0].set_ylim(1e-40, 1e19); ax[0].set_xlabel("x (um)"); ax[0].set_ylabel("carrier density (cm$^{-3}$)")
ax[0].set_title("Equilibrium carriers (II on)"); ax[0].legend(fontsize=7)
for r in results:
    ax[1].semilogy(r["V"], np.abs(r["I"]), label=f"{r['T']:.0f} K, II {'on' if r['ii'] else 'off'}")
ax[1].semilogy(dbl["V"], np.abs(dbl["I"]), "k:", label="300 K, double precision")
ax[1].set_xlabel("V$_{anode}$ (V)"); ax[1].set_ylabel("|J| (A/cm$^2$)"); ax[1].set_title("Forward I-V"); ax[1].legend(fontsize=7)
fig.tight_layout(); fig.savefig(OUT / "fig_gate1_pn_diode.png", dpi=150)

summary = dict(gate="G1_pn_diode", env=env_info(), stats=STATS.as_dict(),
               cases=[{k: v for k, v in r.items() if k not in ("profile",)} for r in results],
               double_precision_300K=dict(V=dbl["V"], I=dbl["I"]))
save_json(summary, OUT / "gate1_pn_diode.json")
print("saved", OUT / "gate1_pn_diode.json")
