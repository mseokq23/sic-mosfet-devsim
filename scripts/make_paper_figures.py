"""Paper figures and table from the committed results (single source of truth).
  python scripts/make_paper_figures.py
-> paper/figures/fig1_structure_flow, fig2_validation, fig3_rq1, fig4_policies (.png 300 dpi + .pdf)
   paper/tables/table1_sensitivity.(md|csv), paper/captions.md"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd, yaml
from scipy import stats
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch, Patch, Rectangle
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.analysis import add_noise, censor_floor, feature_set, fit_predict, wide_table
from sicsim.config import _Loader, load_config
from sicsim.design import VARS

R, OUT = ROOT / "results", ROOT / "paper"
FIG, TAB = OUT / "figures", OUT / "tables"
FIG.mkdir(parents=True, exist_ok=True); TAB.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "STIXGeneral", "mathtext.fontset": "stix", "font.size": 8, "axes.labelsize": 8,
                     "axes.titlesize": 8, "legend.fontsize": 6.5, "xtick.labelsize": 7, "ytick.labelsize": 7,
                     "axes.linewidth": 0.6, "lines.linewidth": 1.0, "xtick.major.width": 0.6, "ytick.major.width": 0.6,
                     "legend.frameon": False})
C1, C2 = 3.4, 7.0                                     # single / double column width (inch)
PC = {"random": "#7f7f7f", "sobol": "#1f77b4", "uncertainty": "#2ca02c", "llm": "#d62728"}
TAG = {"wjfet_scale": "$W_{JFET}$", "npwell_scale": "$N_{pw}$", "qit_eff_cm2": "$Q_{it,eff}$"}
LO, HI = np.array([0.8, 0.8, -1.5e12]), np.array([1.2, 1.2, -0.5e12])
J = lambda p: json.load(open(p))
cfg = load_config()
NOTES = {}


def label(ax, s, x=-0.2, y=1.02):
    ax.text(x, y, s, transform=ax.transAxes, fontsize=8, fontweight="bold", va="bottom")


def save(fig, name):
    fig.savefig(FIG / f"{name}.png", dpi=300, bbox_inches="tight"); fig.savefig(FIG / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


# ------------------------------------------------------------------ Fig. 1 structure + flow
def fig1():
    g = cfg["mosfet"]["geometry"]
    xh = g["x_pw_um"] + 0.5 * g["wjfet_um"]
    td, ts = g["t_drift_um"], g["t_sub_um"]
    Y = lambda y: y if y <= 1.4 else (1.4 + (y - 1.4) / (td - 1.4) * 0.6 if y <= td else 2.0 + (y - td) / ts * 0.3)
    fig = plt.figure(figsize=(C2, 2.6))
    ax = fig.add_axes([0.035, 0.12, 0.30, 0.80])
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
    rect(g["x_ox_start_um"], xh, -tox - 0.13, -tox, "#7f7f7f", 5)
    rect(0, g["x_src_contact_um"], -0.13, 0, "#bfbfbf", 5)
    xs = np.linspace(0, xh, 60); zz = 1.70 + 0.025 * np.sin(xs * 8)
    ax.fill_between(xs, zz - 0.035, zz + 0.035, color="white", zorder=6)
    ax.plot(xs, zz - 0.035, "k", lw=0.4, zorder=7); ax.plot(xs, zz + 0.035, "k", lw=0.4, zorder=7)
    ax.plot([g["x_ox_start_um"], xh], [0, 0], color="#c00000", lw=1.3, ls=(0, (2, 1)), zorder=8)
    t = dict(fontsize=6.5, ha="center", va="center", zorder=9)
    ax.text(0.25, 0.15, "p$^+$", **t); ax.text(1.15, 0.125, "n$^+$", color="white", **t)
    ax.text(0.95, 0.50, "P-well ($N_{pw}$)", **t); ax.text(2.9, 0.42, "JFET", **t)
    ax.text(1.75, 1.22, "n$^-$ drift (10 µm, 10$^{16}$ cm$^{-3}$)", **t); ax.text(1.75, 2.15, "n$^+$ substrate", color="white", **t)
    ax.text(1.75, Y(td + ts) + 0.2, "Drain", **t); ax.text(0.7, -0.065, "Source", fontsize=6, ha="center", va="center", zorder=9)
    ax.text(2.5, -tox - 0.065, "Gate", color="white", fontsize=6, ha="center", va="center", zorder=9)
    ax.annotate("channel ($s_{\\mu}$)", xy=(0.5 * (g["x_ns1_um"] + g["x_pw_um"]), 0.02), xytext=(2.02, 0.34),
                fontsize=6, ha="center", zorder=9, arrowprops=dict(arrowstyle="->", lw=0.5, shrinkA=0, shrinkB=0))
    ax.annotate("$Q_{it,eff}$", xy=(3.15, 0.0), xytext=(3.12, 0.22), fontsize=6.5, color="#c00000", zorder=9,
                arrowprops=dict(arrowstyle="-", lw=0.5, color="#c00000"))
    ax.annotate("", xy=(xh, 0.86), xytext=(g["x_pw_um"], 0.86), arrowprops=dict(arrowstyle="<->", lw=0.6), zorder=9)
    ax.text(0.5 * (g["x_pw_um"] + xh), 0.77, "$W_{JFET}/2$", **t)
    ax.annotate("", xy=(xh, -0.42), xytext=(0, -0.42), arrowprops=dict(arrowstyle="<->", lw=0.6))
    ax.text(0.5 * xh, -0.50, "half-pitch 3.5 µm (fixed)", fontsize=6.5, ha="center", va="bottom")
    ax.set_xlim(-0.08, xh + 0.08); ax.set_ylim(Y(td + ts) + 0.32, -0.62)
    ax.set_xticks([0, 1, 2, 3]); ax.set_yticks([]); ax.set_xlabel("$x$ (µm)", labelpad=1)
    for s in ("left", "right", "top"):
        ax.spines[s].set_visible(False)
    label(ax, "(a)", -0.04, 1.0)
    bx = fig.add_axes([0.36, 0.02, 0.635, 0.94]); bx.set_xlim(0, 1); bx.set_ylim(0, 1); bx.axis("off")
    def box(x, y, w, h, text, fc):
        bx.add_patch(FancyBboxPatch((x - w / 2, y - h / 2), w, h, boxstyle="round,pad=0.006,rounding_size=0.02",
                                    fc=fc, ec="#404040", lw=0.6))
        bx.text(x, y, text, ha="center", va="center", fontsize=6.2, linespacing=1.25)
    def arrow(p0, p1, text=None, tx=None, rad=0.0):
        bx.add_patch(FancyArrowPatch(p0, p1, arrowstyle="-|>", mutation_scale=7, lw=0.6, color="#404040",
                                     connectionstyle=f"arc3,rad={rad}"))
        if text:
            bx.text(*tx, text, fontsize=5.8, ha="center", va="center", color="#404040", style="italic")
    top, bot, w, h = 0.76, 0.24, 0.178, 0.34
    X = [0.095, 0.295, 0.495, 0.695, 0.900]
    T = ["Process point\n$W_{JFET}$, $N_{pw}$, $Q_{it,eff}$\n+ nuisance $s_{\\mu}$",
         "DEVSIM 2-D\ndrift–diffusion\nhalf-cell\n300 K & 423 K",
         "Features\n$V_{th}$, SS, $g_{m,max}$,\n$I_{on}$, $R_{on,sp}$, $I_D$(2 V),\nlog $I_D(V_{GS})$",
         "Measurement noise\n+ current floor\n(S1×2: second\n300 K draw)",
         "Inverse model\n(GP / RF / Ridge)\nfeatures → $\\hat{x}$"]
    for x, s, fc in zip(X, T, ["#fff2cc", "#dae8fc", "#dae8fc", "#e1d5e7", "#d5e8d4"]):
        box(x, top, w, h, s, fc)
    for i in range(4):
        arrow((X[i] + w / 2 + 0.005, top), (X[i + 1] - w / 2 - 0.005, top))
    box(0.17, bot, 0.30, 0.30, "Pre-simulated pool\n512 Sobol points × 2 T\n(+ independent test set, 128)", "#f5f5f5")
    box(0.52, bot, 0.27, 0.30, "Selection policy\n(batch 10 × 6 rounds)\nrandom | Sobol | uncertainty | LLM", "#f5f5f5")
    box(0.85, bot, 0.28, 0.30, "LLM (Claude): top-20 candidates\n→ JSON-schema answer\n→ validator\n(reject → uncertainty)", "#f8cecc")
    arrow((0.52 - 0.135 - 0.005, bot), (0.17 + 0.15 + 0.005, bot), "query", (0.355, bot + 0.04))
    arrow((0.17, bot + 0.15 + 0.005), (X[0], top - h / 2 - 0.005), "selected points", (0.065, 0.465))
    arrow((X[4], top - h / 2 - 0.005), (0.56, bot + 0.15 + 0.005), "uncertainty,\nmodel summary", (0.80, 0.47), rad=-0.15)
    bx.add_patch(FancyArrowPatch((0.52 + 0.135 + 0.003, bot), (0.85 - 0.14 - 0.003, bot), arrowstyle="<|-|>",
                                 mutation_scale=7, lw=0.6, color="#404040"))
    bx.text(0.03, 0.985, "(b)", fontsize=8, fontweight="bold", va="top")
    save(fig, "fig1_structure_flow")


# ------------------------------------------------------------------ Fig. 2 validation
def fig2():
    b3, b4 = J(R / "stage_a_v11/runs/A_base_T300.json"), J(R / "stage_a_v11/runs/A_base_T423.json")
    W = b3["width_cm"]
    fig, ax = plt.subplots(2, 2, figsize=(C1, 3.15))
    for r, T, ls, c in ((b3, 300, "-", "#1f4e79"), (b4, 423, "--", "#c00000")):
        t = r["curves"]["transfer"]; vg = np.array(t["vgs"]); jd = np.abs(np.array(t["id"])) / W
        m = jd > 1e-7
        ax[0, 0].semilogy(vg[m], jd[m], ls, color=c, label=f"{T} K")
        ax[0, 0].plot([r["features"]["vth_V"]], [1e-4 / W], "o", ms=2.5, color=c)
        o = r["curves"]["output"]; ax[0, 1].plot(o["vds"], np.array(o["id"]) / W, ls, color=c, label=f"{T} K")
    ax[0, 0].axhline(1e-4 / W, color="0.55", lw=0.5, ls=":")
    ax[0, 0].text(10.5, 1e-4 / W * 3, "$I_{cc}$", fontsize=6, color="0.4")
    ax[0, 0].set(xlabel="$V_{GS}$ (V)", ylabel="$|J_D|$ (A/cm$^2$)", xlim=(0, 20), ylim=(1e-7, 2e2))
    ax[0, 0].text(0.97, 0.06, "$V_{DS}$ = 0.1 V", transform=ax[0, 0].transAxes, ha="right", fontsize=6)
    ax[0, 0].legend(loc="center right")
    ax[0, 1].set(xlabel="$V_{DS}$ (V)", ylabel="$J_D$ (A/cm$^2$)", xlim=(0, 5), ylim=(0, None))
    ax[0, 1].text(0.05, 0.9, "$V_{GS}$ = 18 V", transform=ax[0, 1].transAxes, fontsize=6)
    fine = J(R / "pretest/gate3/ms1.0_dp_300.json")
    vgf, tf = np.array(fine["curves"]["transfer"]["vgs"]), np.array(fine["curves"]["transfer"]["id"])
    for name, lab, c in (("ms2.0_dp_300", "coarse 6.3k", "0.6"), ("ms1.5_dp_300", "medium 11.0k (used)", "#1f4e79")):
        rr = J(R / f"pretest/gate3/{name}.json")
        vg, ti = np.array(rr["curves"]["transfer"]["vgs"]), np.array(rr["curves"]["transfer"]["id"])
        assert np.allclose(vg, vgf)
        m = vg >= 4.0
        ax[1, 0].plot(vg[m], 100 * (ti[m] / tf[m] - 1), color=c, label=lab)
    ax[1, 0].axhline(0, color="k", lw=0.4)
    ax[1, 0].set(xlabel="$V_{GS}$ (V)", ylabel="$\\Delta I_D$ vs. fine (%)", xlim=(4, 20), ylim=(-5.4, 1.7))
    g3 = J(R / "pretest/gate3_summary.json")["medium_vs_fine"]
    ax[1, 0].legend(loc="lower right", fontsize=6, handlelength=1.2)
    ax[1, 0].text(0.04, 0.92, "300 K, fine = 23.6k nodes", transform=ax[1, 0].transAxes, fontsize=6)
    ax[1, 0].text(0.04, 0.83, f"medium: $\\Delta V_{{th}}$ = {1e3 * g3['vth_V']:.2f} mV, $\\Delta R_{{on,sp}}$ = {100 * g3['ron_mohm_cm2']:+.1f}%",
                  transform=ax[1, 0].transAxes, fontsize=5.6)
    runs = {p.stem: J(p) for p in (R / "stage_a_v11/runs").glob("A_*.json")}
    q, eps0, tox = 1.602176634e-19, 8.8541878128e-14, cfg["mosfet"]["geometry"]["tox_um"] * 1e-4
    slope = q * tox / (3.9 * eps0) * 1e12
    dev = []
    for T, mk, c, ms, mf in ((300, "o", "#1f4e79", 2.4, "#1f4e79"), (423, "s", "#c00000", 5.0, "none")):
        base = runs[f"A_base_T{T}"]
        xs, ys = [0.0], [0.0]
        for lv in ("-20pct", "-10pct", "+10pct", "+20pct"):
            r = runs[f"A_qit_{lv}_T{T}"]
            dq = (r["qit_eff_cm2"] - base["qit_eff_cm2"]) / 1e12
            xs.append(dq); ys.append(r["features"]["vth_V"] - base["features"]["vth_V"]); dev.append(abs(ys[-1] + slope * dq))
        ax[1, 1].plot(xs, ys, mk, ms=ms, mfc=mf, mew=0.8, color=c, label=f"{T} K", zorder=3 if T == 300 else 2)
    xx = np.linspace(-0.25, 0.25, 5)
    ax[1, 1].plot(xx, -slope * xx, "k-", lw=0.6, label="theory")
    ax[1, 1].set(xlabel="$\\Delta Q_{it,eff}$ (10$^{12}$ cm$^{-2}$)", ylabel="$\\Delta V_{th}$ (V)", xlim=(-0.25, 0.25))
    ax[1, 1].legend(loc="upper right", handlelength=1.0, fontsize=6, borderaxespad=0.3)
    for a, s in zip(ax.flat, "abcd"):
        label(a, f"({s})", -0.30, 1.0); a.grid(alpha=0.25, lw=0.4)
    fig.tight_layout(pad=0.3, w_pad=0.6, h_pad=0.6)
    save(fig, "fig2_validation")
    NOTES["fig2"] = dict(vth300=b3["features"]["vth_V"], vth423=b4["features"]["vth_V"], ron300=b3["features"]["ron_mohm_cm2"],
                         ron423=b4["features"]["ron_mohm_cm2"], ss300=b3["features"]["ss_mV_dec"], ss423=b4["features"]["ss_mV_dec"],
                         qit_max_dev_mV=1e3 * max(dev), slope=slope)


# ------------------------------------------------------------------ Fig. 3 RQ1
def fig3():
    nz = yaml.load(open(ROOT / "configs/noise_model.yaml"), Loader=_Loader); fl = nz.get("current_floor_A_per_cm")
    pool0 = wide_table(pd.read_csv(R / "pool/runs.csv")).sort_index(); test0 = wide_table(pd.read_csv(R / "test/runs.csv"))
    noisy = lambda w, lv, s: censor_floor(add_noise(w, nz, nz["levels"][lv], nz["seeds"][s]), fl)
    res = {}
    for lv in ("nominal", "high"):
        pool, test = noisy(pool0, lv, "pool"), noisy(test0, lv, "test")
        for S in ("S1", "S2"):
            P = fit_predict(feature_set(pool, S).values, pool[VARS].values, feature_set(test, S).values, "gp", 0)
            E = np.abs(P - test[VARS].values) / (HI - LO)
            bi = np.random.default_rng(7).integers(0, len(E), (2000, len(E)))
            res[(lv, S)] = (E.mean(0), np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0))
    ref = J(R / "al/nominal/rq1_feature_sets.json")
    assert abs(res[("nominal", "S2")][0][0] - ref["S2_gp"]["wjfet_scale"]["mae_norm"]) < 1e-6, "mismatch with run_al RQ1"
    pool, test = noisy(pool0, "nominal", "pool"), noisy(test0, "nominal", "test")
    budgets, eb = [60, 120, 240, 480], {"S1": [], "S2": []}
    for b in budgets:
        for S, n in (("S1", b), ("S2", b // 2)):
            v = []
            for s in range(5):
                idx = np.random.default_rng(1000 + s).choice(len(pool), n, replace=False)
                P = fit_predict(feature_set(pool, S).values[idx], pool[VARS].values[idx], feature_set(test, S).values, "gp", s)
                v.append((np.abs(P - test[VARS].values) / (HI - LO)).mean())
            eb[S].append((np.mean(v), np.std(v)))
    fig, ax = plt.subplots(2, 1, figsize=(C1, 3.5), gridspec_kw=dict(height_ratios=[1.25, 1]))
    x = np.arange(3); wd = 0.19
    spec = [("nominal", "S1", -1.5, "#c9c9c9", None), ("nominal", "S2", -0.5, "#2f5597", None),
            ("high", "S1", 0.5, "#c9c9c9", "////"), ("high", "S2", 1.5, "#2f5597", "////")]
    for lv, S, off, c, hatch in spec:
        m, ci = res[(lv, S)]
        ax[0].bar(x + off * wd, m, wd, color=c, hatch=hatch, edgecolor="k", lw=0.3,
                  yerr=[m - ci[0], ci[1] - m], error_kw=dict(lw=0.6, capsize=1.5))
    ax[0].axhline(0.25, color="k", lw=0.5, ls="--"); ax[0].text(2.52, 0.244, "no information (uniform guess)", fontsize=6, ha="right", va="top")
    ax[0].set_xticks(x); ax[0].set_xticklabels([TAG[v] for v in VARS]); ax[0].set_ylabel("MAE / DOE range"); ax[0].set_ylim(0, 0.315)
    ax[0].legend(handles=[Patch(fc="#c9c9c9", ec="k", lw=0.3, label="300 K only (S1)"), Patch(fc="#2f5597", ec="k", lw=0.3, label="300 + 423 K (S2)"),
                          Patch(fc="white", ec="k", lw=0.3, hatch="////", label="2× noise")], loc="upper left", ncol=3, fontsize=6, columnspacing=0.8, handlelength=1.6)
    for S, c, mk, lab in (("S1", "0.45", "o", "300 K only (S1): $n$ points"), ("S2", "#2f5597", "s", "300 + 423 K (S2): $n$/2 points")):
        m = np.array([e[0] for e in eb[S]]); s = np.array([e[1] for e in eb[S]])
        ax[1].errorbar(budgets, m, yerr=s, color=c, marker=mk, ms=3, capsize=1.5, lw=0.9, label=lab)
    ax[1].set_xscale("log", base=2); ax[1].set_xticks(budgets); ax[1].set_xticklabels([str(b) for b in budgets])
    ax[1].set(xlabel="DEVSIM runs (training)", ylabel="mean MAE / range"); ax[1].legend(loc="center right")
    for a, s in zip(ax, "ab"):
        label(a, f"({s})", -0.15, 1.0); a.grid(alpha=0.25, lw=0.4, axis="y")
    fig.tight_layout(pad=0.3, h_pad=0.8)
    save(fig, "fig3_rq1")
    NOTES["fig3"] = dict(res={f"{k[0]}_{k[1]}": [round(float(v), 4) for v in res[k][0]] for k in res},
                         equal_budget={S: [(b, round(m, 4), round(s, 4)) for b, (m, s) in zip(budgets, eb[S])] for S in eb})


# ------------------------------------------------------------------ Fig. 4 policies
def fig4():
    base, live = pd.read_csv(R / "al/nominal/al_curves.csv"), pd.read_csv(R / "al_live/nominal/al_curves.csv")
    assert J(R / "al_live/nominal/meta.json")["llm_mode"] == "live"
    d = pd.concat([base[base.policy != "llm"], live[live.policy == "llm"]])
    fig, ax = plt.subplots(2, 1, figsize=(C1, 3.6), gridspec_kw=dict(height_ratios=[1.45, 1]))
    tq = stats.t.ppf(0.975, 9)
    for p, lab in (("random", "Random"), ("sobol", "Sobol (fixed order)"), ("uncertainty", "Uncertainty"), ("llm", "LLM-assisted (Claude)")):
        gg = d[d.policy == p].groupby("n_points").mean_mae_norm
        m, s, n = gg.mean(), gg.std(), gg.count()
        ax[0].plot(m.index, m.values, marker="o", ms=2.5, color=PC[p], label=lab)
    ax[0].set(xlabel="process points (2 DEVSIM runs each)", ylabel="mean MAE / range (test)", xlim=(58, 122))
    ax[0].text(0.03, 0.05, "mean of 10 seeds (same initial 60 points per seed)", transform=ax[0].transAxes, fontsize=5.8)
    ax[0].legend(loc="upper right"); ax[0].grid(alpha=0.25, lw=0.4)
    fin = d[d.n_points == d.n_points.max()].pivot_table(index="seed", columns="policy", values="mean_mae_norm")
    rows = [("Sobol − Random", fin.sobol - fin.random, PC["sobol"]), ("Uncertainty − Random", fin.uncertainty - fin.random, PC["uncertainty"]),
            ("LLM − Random", fin.llm - fin.random, PC["llm"]), ("LLM − Uncertainty", fin.llm - fin.uncertainty, PC["llm"])]
    rng = np.random.default_rng(3); summ = {}
    for i, (lab, dd, c) in enumerate(rows):
        dd = dd.values; bs = rng.choice(dd, (10000, len(dd))).mean(1); lo, hi = np.percentile(bs, [2.5, 97.5])
        y = len(rows) - 1 - i
        ax[1].errorbar(1e3 * dd.mean(), y, xerr=[[1e3 * (dd.mean() - lo)], [1e3 * (hi - dd.mean())]], fmt="s" if i == 3 else "o",
                       ms=3, color=c, mfc="white" if i == 3 else c, capsize=2, lw=0.9)
        ax[1].text(4.6, y, f"{1e3 * dd.mean():+.1f} [{1e3 * lo:+.1f}, {1e3 * hi:+.1f}]  {int((dd < 0).sum())}/10", fontsize=5.8, va="center")
        summ[lab] = (round(1e3 * dd.mean(), 2), round(1e3 * lo, 2), round(1e3 * hi, 2), int((dd < 0).sum()))
    ax[1].axvline(0, color="k", lw=0.5)
    ax[1].set_yticks(range(len(rows))); ax[1].set_yticklabels([r[0] for r in rows][::-1], fontsize=6.5)
    ax[1].set(xlabel="final-round difference in mean MAE / range (×10$^{-3}$)", xlim=(-5, 10.5))
    ax[1].grid(alpha=0.25, lw=0.4, axis="x")
    for a, s in zip(ax, "ab"):
        label(a, f"({s})", -0.15 if s == "a" else -0.42, 1.0)
    fig.tight_layout(pad=0.3, h_pad=0.8)
    save(fig, "fig4_policies")
    L = [json.loads(x) for x in open(R / "al_live/nominal/llm_calls.jsonl")]
    NOTES["fig4"] = dict(final={p: (round(fin[p].mean(), 4), round(fin[p].std(), 4)) for p in fin.columns}, diffs=summ,
                         llm_calls=len(L), accepted=sum(r["validator_status"] == "accepted" for r in L),
                         tokens=(sum(r["input_tokens"] for r in L), sum(r["output_tokens"] for r in L)))


# ------------------------------------------------------------------ Table 1 sensitivities
def table1():
    sa = pd.read_csv(R / "stage_a_v11/stage_a_deltas.csv")
    dv = J(R / "stage_a_v11/stage_a_summary.json")["dvth_T"]
    feats = [("ΔV_th (mV)", "vth_V", 1e3), ("SS (%)", "ss_mV_dec", 100), ("g_m,max (%)", "gm_max_S_per_cm", 100),
             ("I_on (%)", "ion_A_per_cm", 100), ("R_on,sp (%)", "ron_mohm_cm2", 100), ("I_D @ V_DS=2 V (%)", "id_vds_req_A_per_cm", 100)]
    varsx = [("wjfet", "W_JFET"), ("npwell", "N_pw"), ("qit", "Q_it,eff"), ("mu", "s_μ (nuisance)")]
    fmt = lambda v: "0.0" if abs(v) < 0.05 else f"{v:+.1f}"
    rows = []
    for name, col, sc in feats:
        row = {"feature (+20% change)": name}
        for v, vn in varsx:
            a = sa[(sa["var"] == v) & (sa.level == "+20pct")].set_index("T")[col]
            row[vn] = f"{fmt(sc * a[300])} / {fmt(sc * a[423])}"
        rows.append(row)
    row = {"feature (+20% change)": "Δ[V_th(423 K) − V_th(300 K)] (mV)"}
    for v, vn in varsx:
        row[vn] = fmt(1e3 * (dv[f"A_{v}_+20pct"] - dv["A_base"]))
    rows.append(row)
    T = pd.DataFrame(rows); T.to_csv(TAB / "table1_sensitivity.csv", index=False)
    md = ["| " + " | ".join(T.columns) + " |", "|" + "---|" * len(T.columns)] + ["| " + " | ".join(map(str, r)) + " |" for r in T.values]
    (TAB / "table1_sensitivity.md").write_text("\n".join(md) + "\n\n값: 300 K / 423 K. Q_it,eff +20% = 음전하 1.0→1.2×10¹² cm⁻². 기준 소자 V_th = 3.765 V(300 K), 3.530 V(423 K).\n")
    NOTES["table1"] = T.to_dict("records")


if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); table1()
    json.dump(NOTES, open(OUT / "figure_notes.json", "w"), indent=1, ensure_ascii=False, default=float)
    print(json.dumps(NOTES, indent=1, ensure_ascii=False, default=float)[:3500])
