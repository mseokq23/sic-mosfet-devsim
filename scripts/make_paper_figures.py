"""Figures and tables of the paper, drawn from the committed result files (no DEVSIM, no model fitting, no API calls).
  python scripts/make_paper_figures.py                  # everything (a few seconds)
  python scripts/make_paper_figures.py fig3 tables      # a subset: fig1 fig2 fig3 tables
  python scripts/make_paper_figures.py --out /tmp/p     # write to /tmp/p/figures and /tmp/p/tables instead
-> paper/figures/fig1_structure_flow, fig2_validation, fig3_rq1 (.png 600 dpi + .pdf), figure_data.json
   paper/tables/table1_sensitivity, table2_physics, table3_policies, model_parameters (.md + .csv)

Figures are drawn at their printed size (column width 8.0 cm, text >= 6 pt). With the pinned packages
(requirements.txt) the PNGs are pixel-identical to the images in the paper; text hinting is fixed below because
matplotlib builds differ in their default. Proceedings: Fig. 1-3. Review version: Fig. 1 = Fig. 1, Fig. 2 = Fig. 3.
Sources:
  Fig. 1  configs/baseline.yaml (half-cell geometry)
  Fig. 2  results/stage_a/runs (design-center device, Q_it,eff +-10/20 %), results/validation/gate3 (mesh study)
  Fig. 3  results/summary/repeat_control_points.csv, repeat_control.json (test-point bootstrap: seed 7, 2,000)
  Table 1 results/stage_a/stage_a_deltas.csv, stage_a_summary.json
  Table 2 results/summary/posthoc_stats.json (part 1), repeat_control.json
  Table 3 results/summary/rq3_ablation.json, posthoc_stats.json (part 3)
  model parameters: src/sicsim/params.py defaults with the material overrides of configs/baseline.yaml"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Rectangle
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.config import _Loader, load_config, material_from
from sicsim.params import parameter_table

R, S = ROOT / "results", ROOT / "results" / "summary"
FIG, TAB = ROOT / "paper" / "figures", ROOT / "paper" / "tables"
VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]
TAG = {"wjfet_scale": "$W_{JFET}$", "npwell_scale": "$N_{pw}$", "qit_eff_cm2": "$Q_{it,eff}$"}
C_S1, C_S1X2, C_S2 = "#c9c9c9", "#5e9ad6", "#2f5597"     # S1 gray, then a blue ramp
W = 8.0 / 2.54                                            # printed width (inch) = column width
FS, FT, FL, FA = 7.0, 6.5, 6.3, 6.0                       # base, ticks, legend, annotations (pt)
plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": FS, "axes.labelsize": FS,
                     "xtick.labelsize": FT, "ytick.labelsize": FT, "legend.fontsize": FL, "axes.linewidth": 0.6,
                     "lines.linewidth": 1.0, "xtick.major.width": 0.6, "ytick.major.width": 0.6, "xtick.major.size": 2.5,
                     "ytick.major.size": 2.5, "legend.frameon": False, "svg.fonttype": "path", "pdf.fonttype": 42,
                     "text.hinting": "no_hinting"})
J = lambda p: json.load(open(p, encoding="utf-8"))
cfg = load_config()
NOTES = {}


def plabel(ax, s, x, y):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=7.5, fontweight="bold", va="bottom", ha="left")


def save(fig, name):
    FIG.mkdir(parents=True, exist_ok=True)
    fig.savefig(FIG / f"{name}.png", dpi=600); fig.savefig(FIG / f"{name}.pdf", metadata={"CreationDate": None})
    w, h = fig.get_size_inches(); NOTES.setdefault("size_cm", {})[name] = [round(w * 2.54, 2), round(h * 2.54, 2)]
    plt.close(fig)


def pts(level="nominal", rho=0.0, model="gp"):
    """Per-test-point errors of the repeated-measurement control (scripts/repeat_control.py)."""
    d = pd.read_csv(S / "repeat_control_points.csv")
    return d[(d.level == level) & np.isclose(d.rho, rho) & (d.model == model)]


def mean_ci(E, n=2000, seed=7):
    """E: (n_points, k) per-point errors -> column means and 95 % CI (test-point bootstrap)."""
    bi = np.random.default_rng(seed).integers(0, len(E), (n, len(E)))
    return E.mean(0), np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0)


# ---------------------------------------------------------------- Fig. 1: half-cell cross-section + workflow
def fig1(h=2.62):
    g = cfg["mosfet"]["geometry"]
    xh = g["x_pw_um"] + 0.5 * g["wjfet_um"]
    td, ts = g["t_drift_um"], g["t_sub_um"]
    Y = lambda y: y if y <= 1.4 else (1.4 + (y - 1.4) / (td - 1.4) * 0.6 if y <= td else 2.0 + (y - td) / ts * 0.3)
    fig = plt.figure(figsize=(W, h))
    ax = fig.add_axes([0.03, 0.47, 0.955, 0.50])

    def rect(x0, x1, y0, y1, fc, z, ec="none", lw=0.0):
        ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fc=fc, ec=ec, lw=lw, zorder=z))
    tox = 0.08
    rect(0, xh, 0, Y(td), "#dce9f5", 1)
    rect(g["x_pw_um"], xh, 0, Y(g["d_jfet_um"]), "#b9d3ec", 2)
    rect(0, g["x_pw_um"], 0, Y(g["d_pw_um"]), "#f7d3c5", 3)
    rect(0, g["x_pp_um"], 0, Y(g["d_pp_um"]), "#e58e72", 4)
    rect(g["x_ns0_um"], g["x_ns1_um"], 0, Y(g["d_ns_um"]), "#5b9bd5", 4)
    rect(0, xh, Y(td), Y(td + ts), "#5b9bd5", 2)
    rect(0, xh, Y(td + ts), Y(td + ts) + 0.08, "#a6a6a6", 5)
    rect(g["x_ox_start_um"], xh, -tox, 0, "#f3efb4", 5, "k", 0.3)
    rect(g["x_ox_start_um"], xh, -tox - 0.19, -tox, "#7f7f7f", 5)
    rect(0, g["x_src_contact_um"], -0.19, 0, "#bfbfbf", 5)
    xs = np.linspace(0, xh, 80); zz = 1.70 + 0.03 * np.sin(xs * 8)
    ax.fill_between(xs, zz - 0.04, zz + 0.04, color="white", zorder=6)
    ax.plot(xs, zz - 0.04, "k", lw=0.4, zorder=7); ax.plot(xs, zz + 0.04, "k", lw=0.4, zorder=7)
    ax.plot([g["x_ox_start_um"], xh], [0, 0], color="#c00000", lw=1.3, ls=(0, (2, 1)), zorder=8)
    t = dict(fontsize=6.5, ha="center", va="center", zorder=9)
    ax.text(0.25, 0.17, "p$^+$", **t); ax.text(1.15, 0.13, "n$^+$", color="white", **t)
    ax.text(0.80, 0.56, "P-well ($N_{pw}$)", **t); ax.text(2.88, 0.50, "JFET", **t)
    ax.text(1.75, 1.20, "n$^-$ drift (10 µm, 10$^{16}$ cm$^{-3}$)", **t)
    ax.text(1.75, 2.15, "n$^+$ substrate", color="white", **t)
    ax.text(1.75, Y(td + ts) + 0.24, "Drain", **t)
    ax.text(0.62, -0.095, "Source", fontsize=6.2, ha="center", va="center", zorder=9)
    ax.text(2.6, -tox - 0.095, "Gate", color="white", fontsize=6.2, ha="center", va="center", zorder=9)
    ax.annotate("channel ($s_{\\mu}$)", xy=(0.5 * (g["x_ns1_um"] + g["x_pw_um"]), 0.02), xytext=(1.62, 0.36),
                fontsize=6.2, ha="center", va="center", zorder=9,
                arrowprops=dict(arrowstyle="->", lw=0.5, shrinkA=1, shrinkB=0))
    ax.annotate("$Q_{it,eff}$", xy=(3.3, 0.0), xytext=(3.12, 0.26), fontsize=6.5, color="#c00000", zorder=9,
                ha="center", va="center", arrowprops=dict(arrowstyle="-", lw=0.5, color="#c00000", shrinkA=2, shrinkB=0))
    ax.annotate("", xy=(xh, 0.88), xytext=(g["x_pw_um"], 0.88), arrowprops=dict(arrowstyle="<->", lw=0.6), zorder=9)
    ax.text(0.5 * (g["x_pw_um"] + xh), 0.77, "$W_{JFET}/2$", **t)
    ax.annotate("", xy=(xh, -0.50), xytext=(0, -0.50), arrowprops=dict(arrowstyle="<->", lw=0.6))
    ax.text(0.5 * xh, -0.56, "half-pitch 3.5 µm (fixed; not to scale)", fontsize=6.2, ha="center", va="bottom")
    ax.set_xlim(-0.05, xh + 0.05); ax.set_ylim(Y(td + ts) + 0.36, -0.74)
    ax.set_xticks([]); ax.set_yticks([])
    for s in ("left", "right", "top", "bottom"):
        ax.spines[s].set_visible(False)
    fig.text(0.004, 0.955, "(a)", fontsize=7.5, fontweight="bold", va="bottom", ha="left")

    bx = fig.add_axes([0.0, 0.0, 1.0, 0.445]); bx.set_xlim(0, 1); bx.set_ylim(0, 1); bx.axis("off")

    def box(x, y, w, hh, text, fc):
        bx.add_patch(FancyBboxPatch((x - w / 2, y - hh / 2), w, hh, boxstyle="round,pad=0.004,rounding_size=0.02",
                                    fc=fc, ec="#404040", lw=0.6))
        bx.text(x, y, text, ha="center", va="center", fontsize=6.0, linespacing=1.15)

    def arrow(p0, p1, both=False, cs="arc3,rad=0"):
        bx.add_patch(FancyArrowPatch(p0, p1, arrowstyle="<|-|>" if both else "-|>", mutation_scale=6.5, lw=0.6,
                                     color="#404040", connectionstyle=cs))

    def note(x, y, s, **kw):
        bx.text(x, y, s, fontsize=5.8, color="#303030", style="italic", linespacing=1.0, **kw)
    top, bot, h1, h2 = 0.785, 0.175, 0.40, 0.33
    X = [0.112, 0.371, 0.629, 0.888]; w1 = 0.214
    T = ["Process point\n$W_{JFET}$, $N_{pw}$,\n$Q_{it,eff}$ + $s_{\\mu}$",
         "DEVSIM 2-D\ndrift–diffusion\n300 K & 423 K",
         "17 features / T\n+ assumed noise\n(S1×2: 2nd draw)",
         "Inverse model\nGP / RF / Ridge\n→ $\\hat{\\theta}$"]
    for x, s_, fc in zip(X, T, ["#fff2cc", "#dae8fc", "#e1d5e7", "#d5e8d4"]):
        box(x, top, w1, h1, s_, fc)
    for i in range(3):
        arrow((X[i] + w1 / 2 + 0.004, top), (X[i + 1] - w1 / 2 - 0.004, top))
    w2 = 0.255
    Bx = [0.137, 0.50, 0.863]
    B = ["Pre-simulated pool\n512 Sobol × 2 T\n(+ test set, 128)", "Selection policy\nrandom | Sobol |\nuncertainty | LLM",
         "LLM (Claude):\ntop-20 → JSON\n→ validator"]
    for x, s_, fc in zip(Bx, B, ["#f5f5f5", "#f5f5f5", "#f8cecc"]):
        box(x, bot, w2, h2, s_, fc)
    arrow((Bx[1] - w2 / 2 - 0.004, bot), (Bx[0] + w2 / 2 + 0.004, bot)); note(0.3185, bot + 0.035, "query", ha="center", va="bottom")
    arrow((Bx[1] + w2 / 2 + 0.004, bot), (Bx[2] - w2 / 2 - 0.004, bot), both=True)
    ymid = 0.5 * (top - h1 / 2 + bot + h2 / 2)
    arrow((0.075, bot + h2 / 2 + 0.006), (0.075, top - h1 / 2 - 0.006))
    note(0.092, ymid, "selected points", ha="left", va="center")
    yh = ymid - 0.015                                     # inverse model -> selection policy (elbow)
    bx.plot([0.80, 0.80, 0.56], [top - h1 / 2 - 0.006, yh, yh], color="#404040", lw=0.6)
    arrow((0.56, yh), (0.56, bot + h2 / 2 + 0.006))
    note(0.68, yh + 0.012, "uncertainty, CV error", ha="center", va="bottom")
    plabel(bx, "(b)", 0.005, 0.99)
    save(fig, "fig1_structure_flow")


# ---------------------------------------------------------------- Fig. 2: device validation (2 x 2)
def fig2(h=2.42):
    b3, b4 = J(R / "stage_a/runs/A_base_T300.json"), J(R / "stage_a/runs/A_base_T423.json")
    Wd = b3["width_cm"]
    fig, ax = plt.subplots(2, 2, figsize=(W, h))
    for r, T, ls, c in ((b3, 300, "-", "#1f4e79"), (b4, 423, "--", "#c00000")):
        t = r["curves"]["transfer"]; vg = np.array(t["vgs"]); jd = np.abs(np.array(t["id"])) / Wd
        m = jd > 1e-7
        ax[0, 0].semilogy(vg[m], jd[m], ls, color=c, label=f"{T} K")
        ax[0, 0].plot([r["features"]["vth_V"]], [1e-4 / Wd], "o", ms=2.3, color=c)
        o = r["curves"]["output"]; ax[0, 1].plot(o["vds"], np.array(o["id"]) / Wd, ls, color=c, label=f"{T} K")
    ax[0, 0].set(xlabel="$V_{GS}$ (V)", ylabel="$|J_D|$ (A/cm$^2$)", xlim=(0, 20), ylim=(1e-7, 2e2))
    ax[0, 0].set_yticks([1e-6, 1e-3, 1e0])
    ax[0, 0].text(0.96, 0.07, "$V_{DS}$ = 0.1 V", transform=ax[0, 0].transAxes, ha="right", fontsize=FA)
    ax[0, 0].legend(loc="center right", handlelength=1.4, borderaxespad=0.2)
    ax[0, 1].set(xlabel="$V_{DS}$ (V)", ylabel="$J_D$ (A/cm$^2$)", xlim=(0, 5), ylim=(0, None))
    ax[0, 1].text(0.05, 0.86, "$V_{GS}$ = 18 V", transform=ax[0, 1].transAxes, fontsize=FA)
    fine = J(R / "validation/gate3/ms1.0_dp_300.json")
    vgf, tf = np.array(fine["curves"]["transfer"]["vgs"]), np.array(fine["curves"]["transfer"]["id"])
    mesh = {}
    for name, lab, c in (("ms2.0_dp_300", "coarse 6.3k", "0.6"), ("ms1.5_dp_300", "standard 11.0k", "#1f4e79")):
        rr = J(R / f"validation/gate3/{name}.json")
        vg, ti = np.array(rr["curves"]["transfer"]["vgs"]), np.array(rr["curves"]["transfer"]["id"])
        assert np.allclose(vg, vgf)
        m = vg >= 4.0
        ax[1, 0].plot(vg[m], 100 * (ti[m] / tf[m] - 1), color=c, label=lab)
        mesh[name] = dict(n_nodes=rr["n_nodes"], min_pct=float((100 * (ti[m] / tf[m] - 1)).min()))
    mesh["ms1.0_dp_300"] = dict(n_nodes=fine["n_nodes"])
    ax[1, 0].axhline(0, color="k", lw=0.4)
    ax[1, 0].set(xlabel="$V_{GS}$ (V)", ylabel="$\\Delta I_D$ vs. fine (%)", xlim=(4, 20), ylim=(-5.4, 1.9))
    ax[1, 0].legend(loc="lower right", handlelength=1.2, borderaxespad=0.2)
    ax[1, 0].text(0.04, 0.88, "fine: 23.6k nodes", transform=ax[1, 0].transAxes, fontsize=FA)
    runs = {p.stem: J(p) for p in (R / "stage_a/runs").glob("A_*.json")}
    q, eps0, tox = 1.602176634e-19, 8.8541878128e-14, cfg["mosfet"]["geometry"]["tox_um"] * 1e-4
    slope = q * tox / (3.9 * eps0) * 1e12; dev = []                 # |dVth/dQit| = q/C_ox (V per 1e12 cm^-2)
    for T, mk, c, ms, mf in ((300, "o", "#1f4e79", 2.3, "#1f4e79"), (423, "s", "#c00000", 4.4, "none")):
        base = runs[f"A_base_T{T}"]; xs, ys = [0.0], [0.0]
        for lv in ("-20pct", "-10pct", "+10pct", "+20pct"):
            r = runs[f"A_qit_{lv}_T{T}"]
            dq = (r["qit_eff_cm2"] - base["qit_eff_cm2"]) / 1e12
            xs.append(dq); ys.append(r["features"]["vth_V"] - base["features"]["vth_V"]); dev.append(abs(ys[-1] + slope * dq))
        ax[1, 1].plot(xs, ys, mk, ms=ms, mfc=mf, mew=0.8, color=c, label=f"{T} K", zorder=3 if T == 300 else 2)
    xx = np.linspace(-0.25, 0.25, 5)
    ax[1, 1].plot(xx, -slope * xx, "k-", lw=0.6, label="theory")
    ax[1, 1].set(xlabel="$\\Delta Q_{it,eff}$ (10$^{12}$ cm$^{-2}$)", ylabel="$\\Delta V_{th}$ (V)", xlim=(-0.25, 0.25))
    ax[1, 1].legend(loc="upper right", handlelength=1.0, borderaxespad=0.2)
    for a in ax.flat:
        a.grid(alpha=0.25, lw=0.4); a.tick_params(pad=1.5)
        a.xaxis.labelpad = 1; a.yaxis.labelpad = 1
    fig.tight_layout(pad=0.25, w_pad=0.5, h_pad=0.9, rect=(0, 0, 1, 0.965))
    for a, s in zip(ax.flat, "abcd"):
        pos = a.get_position(); fig.text(pos.x0 - 0.115 if s in "ac" else pos.x0 - 0.10, pos.y1 + 0.006, f"({s})",
                                         fontsize=7.5, fontweight="bold", va="bottom")
    save(fig, "fig2_validation")
    f3_, f4_ = b3["features"], b4["features"]
    NOTES["fig2"] = dict(vth_V=[f3_["vth_V"], f4_["vth_V"]], ss_mV_dec=[f3_["ss_mV_dec"], f4_["ss_mV_dec"]],
                         ron_mohm_cm2=[f3_["ron_mohm_cm2"], f4_["ron_mohm_cm2"]], mesh=mesh,
                         qit_theory_slope_V=slope, qit_max_dev_mV=1e3 * max(dev))


# ---------------------------------------------------------------- Fig. 3: RQ1 (per parameter, noise correlation)
def fig3(h=2.32):
    fig, ax = plt.subplots(2, 1, figsize=(W, h), gridspec_kw=dict(height_ratios=[1.3, 1.0]))
    d = pts()
    spec = [("S1", "S1: 300 K", C_S1), ("S1x2", "S1×2: 300 K twice", C_S1X2), ("S2", "S2: 300 + 423 K", C_S2)]
    x = np.arange(3); wd = 0.26; out = {}
    a = ax[0]
    for i, (s, lab, c) in enumerate(spec):
        E = d[d.set == s].sort_values("candidate_id")[[f"err_{v}" for v in VARS]].values
        m, ci = mean_ci(E)
        a.bar(x + (i - 1) * wd, m, wd * 0.92, color=c, edgecolor="k", lw=0.3, label=lab,
              yerr=[m - ci[0], ci[1] - m], error_kw=dict(lw=0.6, capsize=1.5))
        out[s] = dict(mean=[round(float(v), 4) for v in m], lo=[round(float(v), 4) for v in ci[0]],
                      hi=[round(float(v), 4) for v in ci[1]])
    rc = J(S / "repeat_control.json")
    case = next(c for c in rc["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp")
    for j, v in enumerate(VARS):                          # temperature-specific gain: S2 vs S1x2, paired CI < 0
        con = case["contrasts"]["S2-S1x2"][v]
        if con["ci"][1] < 0:
            top = out["S1x2"]["hi"][j] + 0.012
            a.plot([x[j], x[j], x[j] + wd, x[j] + wd], [top - 0.005, top, top, top - 0.005], color="k", lw=0.5)
            a.text(x[j] + wd / 2, top + 0.004, f"−{100 * (1 - con['ratio']):.0f}% vs S1×2", ha="center", va="bottom",
                   fontsize=FA)
            out.setdefault("significant_vs_S1x2", {})[v] = round(100 * (con["ratio"] - 1), 1)
    a.axhline(0.25, color="k", lw=0.5, ls="--")
    a.text(2.45, 0.243, "no information (midpoint guess)", fontsize=FA, ha="right", va="top")
    a.set_xticks(x); a.set_xticklabels([TAG[v] for v in VARS]); a.set_ylabel("MAE / range")
    a.set_ylim(0, 0.33); a.set_yticks([0, 0.1, 0.2, 0.3])
    a.legend(loc="upper center", ncol=3, columnspacing=0.8, handlelength=1.2, borderaxespad=0.15, handletextpad=0.4)
    a.grid(alpha=0.25, lw=0.4, axis="y"); a.tick_params(axis="x", pad=1.5)
    NOTES["fig3a"] = out
    b = ax[1]; rhos = [0.0, 0.5, 0.9]; outb = {}
    specb = [("S1", "S1", "0.45", "o", (0, (3, 2)), "white", -0.024), ("S1x2", "S1×2", C_S1X2, "s", "-", C_S1X2, -0.008),
             ("S2", "S2", C_S2, "D", "-", C_S2, 0.008), ("S3", "S3 (S2 + differences)", C_S2, "^", (0, (1, 1.2)), "white", 0.024)]
    for s, lab, c, mk, ls, mf, dx in specb:
        m, lo, hi = [], [], []
        for r in rhos:
            E = pts(rho=r)
            E = E[E.set == s].sort_values("candidate_id")[[f"err_{v}" for v in VARS]].values.mean(1, keepdims=True)
            mm, ci = mean_ci(E)
            m.append(mm[0]); lo.append(ci[0][0]); hi.append(ci[1][0])
        m, lo, hi = map(np.array, (m, lo, hi))
        b.errorbar(np.array(rhos) + dx, m, yerr=[m - lo, hi - m], color=c, marker=mk, ms=3.0, mfc=mf, mec=c, ls=ls,
                   lw=0.9, capsize=1.5, label=lab)
        outb[s] = dict(rho=rhos, mean=[round(float(v), 4) for v in m], lo=[round(float(v), 4) for v in lo],
                       hi=[round(float(v), 4) for v in hi])
    b.set_xticks(rhos); b.set_xlim(-0.08, 0.98); b.set_ylim(0.055, 0.15); b.set_yticks([0.06, 0.08, 0.10, 0.12, 0.14])
    b.set_xlabel(r"noise correlation between the two measurements, $\rho$", labelpad=1)
    b.set_ylabel(r"MAE$_{norm}$")
    b.legend(loc="upper center", ncol=4, handlelength=1.9, columnspacing=0.7, borderaxespad=0.15, handletextpad=0.35)
    b.grid(alpha=0.25, lw=0.4, axis="y"); b.tick_params(axis="x", pad=1.5)
    NOTES["fig3b"] = outb
    fig.tight_layout(pad=0.25, h_pad=0.9, rect=(0, 0, 1, 0.965))
    for a_, s in zip(ax, "ab"):
        pos = a_.get_position(); fig.text(0.008, pos.y1 + 0.005, f"({s})", fontsize=7.5, fontweight="bold", va="bottom")
    save(fig, "fig3_rq1")


# ---------------------------------------------------------------- tables
def write_table(name, rows, columns, notes, csv_rows=None):
    TAB.mkdir(parents=True, exist_ok=True)
    md = ["| " + " | ".join(columns) + " |", "|" + "---|" * len(columns)]
    md += ["| " + " | ".join(str(r[c]) for c in columns) + " |" for r in rows]
    (TAB / f"{name}.md").write_text("\n".join(md) + "\n\n" + "\n".join(notes) + "\n", encoding="utf-8")
    pd.DataFrame(csv_rows if csv_rows is not None else rows).to_csv(TAB / f"{name}.csv", index=False)
    NOTES[name] = csv_rows if csv_rows is not None else rows


def table1():
    """Nominal values, ranges and one-at-a-time sensitivities to a +20 % change (300 K / 423 K)."""
    sa = pd.read_csv(R / "stage_a/stage_a_deltas.csv")
    dv = J(R / "stage_a/stage_a_summary.json")["dvth_T"]
    bnd = yaml.load(open(ROOT / "configs/parameter_bounds.yaml"), Loader=_Loader)
    v_, nu = bnd["variables"], bnd["nuisance"]["mu_channel_scale"]
    g, dop = cfg["mosfet"]["geometry"], cfg["mosfet"]["doping"]
    pm = lambda s: f"±{100 * (s['high'] - s['nominal']) / s['nominal']:.0f}%"
    e12 = lambda x: f"{x / 1e12:+.1f}".replace("+", "")
    feats = [("ΔV_th (mV)", "vth_V", 1e3), ("SS (%)", "ss_mV_dec", 100), ("g_m,max (%)", "gm_max_S_per_cm", 100),
             ("I_on (%)", "ion_A_per_cm", 100), ("R_on,sp (%)", "ron_mohm_cm2", 100), ("I_D @ V_DS=2 V (%)", "id_vds_req_A_per_cm", 100)]
    varsx = [("wjfet", "W_JFET"), ("npwell", "N_pw"), ("qit", "Q_it,eff"), ("mu", "s_μ (nuisance)")]
    fmt = lambda v: "0.0" if abs(v) < 0.05 else f"{v:+.1f}"
    rows = [{"feature (+20% change)": "nominal (range)",
             "W_JFET": f"{g['wjfet_um']:g} µm ({pm(v_['wjfet_scale'])})",
             "N_pw": f"{dop['N_pw']:.0e} cm⁻³ ({pm(v_['npwell_scale'])})".replace("e+", "e"),
             "Q_it,eff": f"{e12(v_['qit_eff_cm2']['nominal'])}e12 cm⁻² ({e12(v_['qit_eff_cm2']['low'])} to {e12(v_['qit_eff_cm2']['high'])}e12)",
             "s_μ (nuisance)": f"{nu['nominal']:g} ({nu['low']:g} to {nu['high']:g})"}]
    for name, col, sc in feats:
        row = {"feature (+20% change)": name}
        for v, vn in varsx:
            a = sa[(sa["var"] == v) & (sa.level == "+20pct")].set_index("T")[col]
            row[vn] = f"{fmt(sc * a[300])} / {fmt(sc * a[423])}"
        rows.append(row)
    row = {"feature (+20% change)": "Δ[V_th(423 K) - V_th(300 K)] (mV)"}
    for v, vn in varsx:
        row[vn] = fmt(1e3 * (dv[f"A_{v}_+20pct"] - dv["A_base"]))
    rows.append(row)
    b3, b4 = J(R / "stage_a/runs/A_base_T300.json")["features"], J(R / "stage_a/runs/A_base_T423.json")["features"]
    write_table("table1_sensitivity", rows, list(rows[0]), [
        "Values: 300 K / 423 K, change from the design-center device when one parameter is raised by 20 % "
        "(Q_it,eff: magnitude, -1.0 -> -1.2e12 cm⁻²).",
        f"Design-center device: V_th = {b3['vth_V']:.3f} V (300 K), {b4['vth_V']:.3f} V (423 K). "
        "Last row: change of V_th(423 K) - V_th(300 K) from the design center."])


def table2():
    """Mean MAE_norm of S2 (GP, nominal noise) for each 423 K physics assumption of the test data."""
    p1 = J(S / "posthoc_stats.json")["part1"]; rc = J(S / "repeat_control.json")
    s1, s1x2 = p1["reference"]["S1"]["mean"], p1["reference"]["S1x2"]["mean"]
    names = {"base": "baseline (γ = +1, r = 0)", "gamma0": "γ = 0", "gamma_m1": "γ = -1", "qitT10": "r = 0.1", "qitT30": "r = 0.3"}
    bold = lambda v, s: f"**{s}**" if v > s1 else s

    def cell(rec, pct=True):
        if rec is None:
            return "—"
        v, c = rec["mean"], rec["vs_S1x2"]["mean"]
        s = f"{v:.3f}"
        if pct:
            s += f" ({100 * (v / s1x2 - 1):+.0f}%){'*' if c['ci'][1] < 0 else ''}"
        return bold(v, s)
    rows, raw = [], []
    for k, lab in names.items():
        sc = p1["scenarios"][k]
        mis = sc["nominal"] if k != "base" else None
        rows.append({"423 K physics of the test data": lab, "Oracle": cell(sc["matched"]),
                     "Mismatch": cell(mis, pct=False), "Mixture (post hoc)": cell(sc["mixed"])})
        for train, rec in (("oracle", sc["matched"]), ("mismatch", mis), ("mixture", sc["mixed"])):
            if rec is not None:
                c = rec["vs_S1x2"]["mean"]
                raw.append(dict(scenario=k, training=train, S2_mean=rec["mean"], **{f"S2_{v}": rec[v] for v in VARS},
                                delta_vs_S1x2=c["delta"], ci_lo=c["ci"][0], ci_hi=c["ci"][1]))
    sr = rc["series_r"]["sets"]
    rows.append({"423 K physics of the test data": "series resistance (test data only)", "Oracle": "—",
                 "Mismatch": bold(sr["S2"]["mean"], f"{sr['S2']['mean']:.3f}"), "Mixture (post hoc)": "—"})
    raw += [dict(scenario="series_r", training="nominal", feature_set=k, S2_mean=sr[k]["mean"], **{f"S2_{v}": sr[k][v] for v in VARS})
            for k in ("S1", "S1x2", "S2")]
    write_table("table2_physics", rows, list(rows[0]), [
        f"S1 = {s1:.3f}, S1×2 = {s1x2:.3f} (300 K features only, the same in every scenario). "
        "Oracle: trained with the test physics; Mismatch: trained with the baseline physics only; "
        "Mixture: trained on the five assumptions mixed (post hoc).",
        "( ): change from S1×2; *: paired bootstrap 95 % CI of S2 - S1×2 below 0; bold: above S1. "
        f"Series resistance 0.1–0.3 mΩ·cm² added to the test devices only (S1 {sr['S1']['mean']:.3f}, "
        f"S1×2 {sr['S1x2']['mean']:.3f}, S2 {sr['S2']['mean']:.3f})."], csv_rows=raw)


def table3():
    """Final MAE_norm of the selection policies (S2, RF, nominal noise, 10 seeds) and LLM selection behaviour."""
    ab, p3 = J(S / "rq3_ablation.json"), J(S / "posthoc_stats.json")["part3"]
    fin, beh = ab["final"], ab["behaviour"]
    k3 = lambda x: f"{1e3 * x:+.1f}"

    def vs_u(k):                                          # seed-paired difference to the uncertainty policy, x1e-3
        if k == "U":
            return None
        if k in ("random", "sobol"):                      # stored as U − k: flip sign and interval
            c = p3[f"final:U-{k}"]; return -c["delta"], -c["boot95"][1], -c["boot95"][0]
        c = p3[f"final:{k}-U"]; return c["delta"], c["boot95"][0], c["boot95"][1]
    spec = [("random", "Random"), ("sobol", "Sobol"), ("U", "Uncertainty"), ("A0", "A0 LLM, first run"),
            ("A", "A LLM, original payload"), ("B", "B LLM, anonymized"), ("C", "C LLM, perturbed input"),
            ("D", "D random 10 of top-20")]
    rows, raw = [], []
    for k, lab in spec:
        d = vs_u(k); b = beh.get(k)
        rows.append({"policy / condition": lab, "final MAE_norm": f"{fin[k]['mean']:.4f}",
                     "Δ vs uncertainty (×10⁻³) [95% CI]": "—" if d is None else f"{k3(d[0])} [{k3(d[1])}, {k3(d[2])}]",
                     "top-10 overlap (actual/displayed)": "—" if not b else f"{b['overlap_true']:.2f}/{b['overlap_shown']:.2f}"})
        raw.append(dict(condition=k, final_mean=fin[k]["mean"], final_sd=fin[k]["sd"],
                        delta_vs_U=None if d is None else d[0], ci_lo=None if d is None else d[1], ci_hi=None if d is None else d[2],
                        mde80=None if k in ("U", "random", "sobol") else p3[f"final:{k}-U"]["mde80"],
                        overlap_true=b["overlap_true"] if b else None, overlap_shown=b["overlap_shown"] if b else None,
                        calls=b["calls"] if b else None, accepted=b["accepted"] if b else None))
    write_table("table3_policies", rows, list(rows[0]), [
        "Initial 60 devices + 10 × 6 rounds, S2 features, RF inverse model, nominal noise; mean over 10 seeds (the seed "
        "changes the initial set and the RF; the noise realisation is fixed). Δ: seed-paired difference from the "
        "uncertainty policy with a seed bootstrap 95 % CI.",
        "Overlap: share of the 10 picks in the actual / displayed uncertainty top-10 (random 0.50). A0 is the first "
        "run of A in another environment; A, B, C, D, uncertainty, random and Sobol ran in one session."], csv_rows=raw)


def model_parameters():
    """4H-SiC material and mobility-model constants used by every run (the paper refers to the repository for them)."""
    rows = parameter_table(material_from(cfg))
    write_table("model_parameters", rows, ["name", "value"], [
        f"Configuration {cfg['version']}: defaults of src/sicsim/params.py (sources listed in its docstring) with the "
        "material overrides of configs/baseline.yaml. Gate work function "
        f"{cfg['gate']['phi_m']} eV, fixed oxide charge Q_f = {cfg['interface']['qf_cm2']:.0e} cm⁻².".replace("e+", "e")])


PARTS = {"fig1": fig1, "fig2": fig2, "fig3": fig3, "tables": lambda: (table1(), table2(), table3(), model_parameters())}

if __name__ == "__main__":
    args = sys.argv[1:]
    if "--out" in args:
        i = args.index("--out"); FIG, TAB = Path(args[i + 1]) / "figures", Path(args[i + 1]) / "tables"; del args[i:i + 2]
    which = args or list(PARTS)
    for w in which:
        PARTS[w]()
    if which == list(PARTS):
        FIG.mkdir(parents=True, exist_ok=True)
        json.dump(NOTES, open(FIG / "figure_data.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False, default=float)
    print("->", ", ".join(sorted(p.name for p in FIG.glob("*.png"))), "|", ", ".join(sorted(p.name for p in TAB.glob("*.md"))))
