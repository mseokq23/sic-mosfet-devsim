"""Gate 2: 1D MOS capacitor - flat-band/threshold vs analytic, interface-charge sign, LF C-V, 300/423 K."""
import sys, time, math
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sicsim.config import load_config, material_from, gate_from
from sicsim import devices as dv, physics as ph
from sicsim.params import Q, EPS0, gate_offset
from sicsim.solver import ramp, STATS
from sicsim.utils import reset_devsim, save_json, env_info

OUT = Path(__file__).resolve().parents[1] / "results" / "pretest"
cfg = load_config(); mat = material_from(cfg); gate = gate_from(cfg); g = cfg["moscap"]
tol = cfg["numerics"]["tol"]
cox = 3.9 * EPS0 / (g["tox_um"] * 1e-4)
ph.set_extended_precision(True)


def analytic(T, qeff):
    d = mat.derived(T); NA = g["NA"]
    a = mat.gA / d["p1A"]; p0 = (-1 + math.sqrt(1 + 4 * a * NA)) / (2 * a)
    psib = -d["Vt"] * math.log(p0 / d["ni"])
    vfb = gate_offset(mat, gate, T) + psib - Q * qeff / cox
    phi2 = 2 * abs(psib)
    qd = math.sqrt(2 * mat.eps_r * EPS0 * Q * NA * phi2)
    return dict(psib=psib, vfb=vfb, vth=vfb + phi2 + qd / cox, p0=p0)


def run(T, qeff, dd=False, vmax=15.0):
    """dd=False: equilibrium Poisson (exact DC state of a MOSCAP: no current -> flat Fermi level).
    dd=True : full drift-diffusion (minority electrons must be supplied by generation -> SiC deep
              depletion makes DC inversion ill-conditioned; used only as a consistency check)."""
    reset_devsim(); t0 = time.time()
    lay = dv.build_moscap("mc", cfg)
    dv.setup_physics("mc", lay, mat, T, ii=True, intf_mode="static",
                     interface=dict(qf_cm2=0.0, qit_eff_cm2=qeff), gate=gate)
    stol = tol if dd else dv.PO_TOL
    if dd:
        dv.equilibrate("mc", lay, ii=True, intf_mode="static", tol=tol)
    else:
        from sicsim.solver import solve_dc
        solve_dc("mc", dv.PO_TOL)
    x = ph.node_array("mc", "sic", "x"); i_s = int(np.argmin(abs(x)))
    data = []
    def rec(v):
        psi = ph.node_array("mc", "sic", "Potential")
        data.append((v, psi[i_s], psi[-1], ph.contact_charge("mc", "gate")))
    rec(0.0)
    ramp("mc", "gate", -10.0, 0.25, callback=rec, tol=stol)
    ramp("mc", "gate", 0.0, 1.0, tol=stol)
    ramp("mc", "gate", vmax, 0.25, callback=rec, tol=stol)
    data.sort(); arr = np.array(data)
    vg, psis, psib, qg = arr.T
    a = analytic(T, qeff)
    vfb = float(np.interp(0.0, psis - psib, vg))                # psi_s = psi_b
    vth = float(np.interp(0.0, psis + psib, vg))                # psi_s = -psi_b (n_s = p_0)
    c = np.gradient(qg, vg)
    return dict(T=T, qeff=qeff, vfb_sim=vfb, vfb_ana=a["vfb"], vth_sim=vth, vth_ana=a["vth"],
                psib_sim=float(psib[0]), psib_ana=a["psib"], vg=vg.tolist(), psis=psis.tolist(),
                c_over_cox=(c / cox).tolist(), runtime_s=time.time() - t0)


res = []
for T in (300.0, 423.0):
    for qeff in (0.0, 1e12, -1e12):
        r = run(T, qeff); res.append(r)
        print(f"T={T:.0f} Qeff={qeff:+.0e}: Vfb sim/ana = {r['vfb_sim']:+.3f}/{r['vfb_ana']:+.3f} V, "
              f"Vth sim/ana = {r['vth_sim']:+.3f}/{r['vth_ana']:+.3f} V, psib {r['psib_sim']:.4f}/{r['psib_ana']:.4f}, t={r['runtime_s']:.1f}s")
# consistency: full DD in accumulation/depletion must reproduce the equilibrium solution
ddc = run(300.0, 0.0, dd=True, vmax=1.0)
po = [r for r in res if r["T"] == 300.0 and r["qeff"] == 0.0][0]
common = [v for v in ddc["vg"] if v <= 1.0]
diff = max(abs(np.interp(v, ddc["vg"], ddc["psis"]) - np.interp(v, po["vg"], po["psis"])) for v in common)
print(f"DD vs equilibrium-Poisson surface potential (300 K, -10..+1 V): max |diff| = {diff:.2e} V")
d0 = {T: [r for r in res if r["T"] == T] for T in (300.0, 423.0)}
for T, rs in d0.items():
    base = [r for r in rs if r["qeff"] == 0][0]
    for r in rs:
        if r["qeff"] != 0:
            print(f"  T={T:.0f}: dVfb(Qeff={r['qeff']:+.0e}) sim={r['vfb_sim']-base['vfb_sim']:+.4f} V,"
                  f" theory -qQ/Cox={-Q*r['qeff']/cox:+.4f} V")

fig, ax = plt.subplots(1, 2, figsize=(10, 4))
for r in res:
    ls = {0.0: "-", 1e12: "--", -1e12: ":"}[r["qeff"]]
    col = "C0" if r["T"] == 300 else "C3"
    ax[0].plot(r["vg"], r["psis"], ls, color=col, label=f"{r['T']:.0f} K, Q={r['qeff']:+.0e}")
    ax[1].plot(r["vg"], r["c_over_cox"], ls, color=col, label=f"{r['T']:.0f} K, Q={r['qeff']:+.0e}")
ax[0].set_xlabel("V$_G$ (V)"); ax[0].set_ylabel("surface potential (V)"); ax[0].legend(fontsize=6)
ax[1].set_xlabel("V$_G$ (V)"); ax[1].set_ylabel("C$_{LF}$/C$_{ox}$"); ax[1].set_ylim(0, 1.05)
ax[0].set_title("MOSCAP surface potential"); ax[1].set_title("quasi-static C-V")
fig.tight_layout(); fig.savefig(OUT / "fig_gate2_moscap.png", dpi=150)
save_json(dict(gate="G2_moscap", env=env_info(), stats=STATS.as_dict(), cox_F_cm2=cox,
               dd_vs_po_max_psis_diff_V=diff,
               cases=[{k: v for k, v in r.items() if k not in ("vg", "psis", "c_over_cox")} for r in res]),
          OUT / "gate2_moscap.json")
