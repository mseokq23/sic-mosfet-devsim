"""README figures from the committed result files (no DEVSIM, no model fitting, no API calls).
  python scripts/make_readme_figures.py                    -> docs/figures/*.png, docs/figures/sources.json (~10 s)
  python scripts/make_readme_figures.py --only iv_baseline iv_population --out /tmp/fig
  python scripts/make_readme_figures.py --full-color       # 24-bit PNGs (default: 256-color palette, ~2.5x smaller)
sources.json lists the files each figure read (path, size, SHA-256). Labels are in English so that the DejaVu fonts
bundled with matplotlib are enough and the PNGs come out the same on any machine with the pinned matplotlib."""
from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from matplotlib.patches import Patch  # noqa: E402
from matplotlib.ticker import NullFormatter  # noqa: E402
from PIL import Image  # noqa: E402  (installed with matplotlib)

ROOT = Path(__file__).resolve().parents[1]
RES, SUM = ROOT / "results", ROOT / "results" / "summary"
VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]
VARIANTS = ["gamma0", "gamma_m1", "qitT10", "qitT30"]
DPI = 150
USED: dict[str, set] = {}                       # figure -> source files (relative paths)
CUR = [""]
FULL_COLOR = [False]

# ---------------------------------------------------------------------------------------------------- style
plt.rcParams.update({
    "font.family": "DejaVu Sans", "mathtext.fontset": "dejavusans", "font.size": 9.5, "axes.titlesize": 10,
    "axes.titlelocation": "left", "axes.labelsize": 9.5, "xtick.labelsize": 8.5, "ytick.labelsize": 8.5,
    "legend.fontsize": 8.5, "legend.frameon": False, "axes.spines.top": False, "axes.spines.right": False,
    "axes.edgecolor": "#555555", "axes.linewidth": 0.8, "axes.grid": True, "grid.color": "#e8e8e8",
    "grid.linewidth": 0.6, "lines.linewidth": 1.4, "figure.facecolor": "white", "savefig.facecolor": "white",
    "svg.hashsalt": "sicsim", "axes.axisbelow": True,
})
C_T = {300: "#1f6fbf", 423: "#e0602b"}                         # temperature
C_LVL = {"-20pct": "#762a83", "-10pct": "#af8dc3", "base": "#1a1a1a", "+10pct": "#7fbf7b", "+20pct": "#1b7837"}
C_SET = {"S1": "#a3abaf", "S1x2": "#56b4e9", "S1x2cat": "#8fb8d8", "S2": "#0b4f8a", "S3": "#009e73"}
C_VAR = {"nominal": "#1a1a1a", "gamma0": "#0072b2", "gamma_m1": "#56b4e9", "qitT10": "#e69f00", "qitT30": "#d55e00"}
C_POL = {"random": "#7f7f7f", "sobol": "#009e73", "uncertainty": "#0072b2", "top20_random": "#cc79a7",
         "A0": "#d55e00", "A": "#e69f00", "B": "#56b4e9", "C": "#1a1a1a"}
LBL_SET = {"S1": "S1  (300 K)", "S1x2": "S1×2  (300 K, two noisy repeats)", "S1x2cat": "S1×2cat",
           "S2": "S2  (300 K + 423 K)", "S3": "S3  (S2 + 423−300 K differences)"}
LBL_VAR = {"nominal": r"frozen physics ($\gamma$ = +1)", "gamma0": r"$\gamma$ = 0", "gamma_m1": r"$\gamma$ = −1",
           "qitT10": r"$|Q_\mathrm{it}|$ −10 % at 423 K", "qitT30": r"$|Q_\mathrm{it}|$ −30 % at 423 K"}
LBL_PAR = {"wjfet_scale": r"$W_\mathrm{JFET}$ scale", "npwell_scale": r"$N_\mathrm{pw}$ scale",
           "qit_eff_cm2": r"$|Q_\mathrm{it,eff}|$ ($10^{12}$ cm$^{-2}$)", "mu_channel_scale": r"$s_\mu$ (channel mobility scale)"}
LBL_TGT = {"wjfet_scale": r"$W_\mathrm{JFET}$", "npwell_scale": r"$N_\mathrm{pw}$", "qit_eff_cm2": r"$Q_\mathrm{it,eff}$",
           "mean": "mean"}
X_VGS, X_VDS = r"$V_\mathrm{GS}$ (V)", r"$V_\mathrm{DS}$ (V)"
Y_ID = r"$I_\mathrm{D}$ (A/cm)"
ICC = 1.0e-4                                    # constant-current V_th criterion, configs/baseline.yaml (A/cm)


# ---------------------------------------------------------------------------------------------------- io
def src(rel: str) -> Path:
    USED.setdefault(CUR[0], set()).add(rel)
    return ROOT / rel


def run(rel: str) -> dict:
    return json.load(open(src(rel), encoding="utf-8"))


def csv(rel: str, **kw) -> pd.DataFrame:
    return pd.read_csv(src(rel), **kw)


def jload(rel: str) -> dict:
    return json.load(open(src(rel), encoding="utf-8"))


def runs_table(name: str) -> pd.DataFrame:
    d = csv(f"results/{name}/runs.csv")
    return d[d["converged"].astype(str).str.lower() == "true"].copy()


def transfer(d):
    t = d["curves"]["transfer"]
    vg, i = np.asarray(t["vgs"], float), np.asarray(t["id"], float)
    floor = d["features"].get("kcl_floor_A_per_cm") or 0.0
    return vg, np.where(i > floor, i, np.nan)              # points under the solver current floor are not drawn


def output(d):
    o = d["curves"]["output"]
    return np.asarray(o["vds"], float), np.asarray(o["id"], float)


def save(fig, out: Path, name: str):
    """PNG on white, reduced to a 256-color palette (about 2.5x smaller, no visible change at README size)."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=DPI)
    plt.close(fig)
    im = Image.open(buf).convert("RGB")
    if not FULL_COLOR[0]:
        im = im.quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    im.save(out / f"{name}.png", optimize=True)


def mean_ci(E, n=2000, seed=7):
    """Column means and 95 % CI over test devices (bootstrap seed 7, 2000 resamples; as scripts/make_v47_figures.py)."""
    E = np.asarray(E, float)
    bi = np.random.default_rng(seed).integers(0, len(E), (n, len(E)))
    lo, hi = np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0)
    return E.mean(0), lo, hi


def legend_top(fig, handles, ncol):
    fig.legend(handles=handles, loc="outside upper center", ncol=ncol, handlelength=2.2, columnspacing=1.6)


# ---------------------------------------------------------------------------------------------------- figures
def iv_baseline(out):
    """Design-center device (all scales 1, Q_it,eff = -1e12 cm^-2): transfer (log, linear) and output, 300/423 K."""
    fig, ax = plt.subplots(1, 3, figsize=(10, 3.25), constrained_layout=True)
    for T in (300, 423):
        d = run(f"results/stage_a_v11/runs/A_base_T{T}.json")
        vg, i = transfer(d)
        vds, io = output(d)
        f = d["features"]
        ax[0].semilogy(vg, i, color=C_T[T], label=f"{T} K")
        ax[0].plot(f["vth_V"], ICC, "o", ms=4.5, mfc="white", mec=C_T[T], mew=1.3, zorder=5)
        ax[0].annotate(f"$V_\\mathrm{{th}}$ = {f['vth_V']:.2f} V", (f["vth_V"], ICC),
                       xytext=(8, -14 if T == 300 else 6), textcoords="offset points", color=C_T[T], fontsize=7.5)
        ax[1].plot(vg, i * 1e3, color=C_T[T])
        ax[2].plot(vds, io, "-o", ms=2.8, color=C_T[T],
                   label=f"{T} K, $R_\\mathrm{{on,sp}}$ = {f['ron_mohm_cm2']:.2f} mΩ·cm²")
    ax[0].axhline(ICC, color="#9a9a9a", ls=":", lw=0.9)
    ax[0].text(19.6, ICC * 1.6, r"$I_\mathrm{D}$ = $10^{-4}$ A/cm", ha="right", fontsize=7.5, color="#6f6f6f")
    ax[0].set(xlim=(0, 20), ylim=(1e-12, 1e-1), xlabel=X_VGS, ylabel=Y_ID, title=r"(a) Transfer, $V_\mathrm{DS}$ = 0.1 V")
    ax[1].set(xlim=(0, 20), ylim=(0, None), xlabel=X_VGS, ylabel=r"$I_\mathrm{D}$ (mA/cm)",
              title=r"(b) Transfer, linear scale")
    ax[2].set(xlim=(0, 5.1), ylim=(0, None), xlabel=X_VDS, ylabel=Y_ID, title=r"(c) Output, $V_\mathrm{GS}$ = 18 V")
    ax[0].legend(loc="lower right")
    ax[2].legend(loc="upper left")
    save(fig, out, "iv_baseline")


def iv_one_at_a_time(out):
    """Stage A: one parameter at -20 %, -10 %, 0, +10 %, +20 % with the others at the design center."""
    par = [("wjfet", r"$W_\mathrm{JFET}$"), ("npwell", r"$N_\mathrm{pw}$"), ("qit", r"$|Q_\mathrm{it,eff}|$"),
           ("mu", r"$s_\mu$ (channel mobility)")]
    lvls = ["-20pct", "-10pct", "base", "+10pct", "+20pct"]
    fig, ax = plt.subplots(2, 4, figsize=(10, 5.0), sharex="row", sharey="row", constrained_layout=True)
    for j, (p, title) in enumerate(par):
        for lv in lvls:
            for T, ls in ((300, "-"), (423, "--")):
                name = "A_base" if lv == "base" else f"A_{p}_{lv}"
                d = run(f"results/stage_a_v11/runs/{name}_T{T}.json")
                vg, i = transfer(d)
                vds, io = output(d)
                kw = dict(color=C_LVL[lv], ls=ls, lw=1.25 if lv != "base" else 1.5)
                ax[0, j].semilogy(vg, i, **kw)
                ax[1, j].plot(vds, io, **kw)
        ax[0, j].set_title(f"({'abcd'[j]}) {title}")
        ax[1, j].set_title(f"({'efgh'[j]}) {title}")
        ax[0, j].set(xlim=(0, 10), ylim=(1e-12, 1e-1), xlabel=X_VGS)
        ax[1, j].set(xlim=(0, 5.1), ylim=(0, None), xlabel=X_VDS)
    ax[0, 0].set_ylabel(Y_ID + "\n" + r"transfer, $V_\mathrm{DS}$ = 0.1 V")
    ax[1, 0].set_ylabel(Y_ID + "\n" + r"output, $V_\mathrm{GS}$ = 18 V")
    h = [Line2D([], [], color=C_LVL[lv], lw=1.6, label=("0 (design center)" if lv == "base" else
                                                        lv.replace("pct", " %").replace("-", "−")))
         for lv in lvls]
    h += [Line2D([], [], color="#555", ls="-", label="300 K"), Line2D([], [], color="#555", ls="--", label="423 K")]
    legend_top(fig, h, 7)
    save(fig, out, "iv_one_at_a_time")


def iv_population(out):
    """All 128 test devices at 300 K and 423 K (frozen physics) with the design-center device on top."""
    design = csv("configs/design_test.csv")
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), constrained_layout=True)
    n = 0
    for cid in design["candidate_id"]:
        for T in (300, 423):
            p = f"results/test/runs/{cid}_T{T}.json"
            if not (ROOT / p).exists():
                continue
            d = json.load(open(ROOT / p, encoding="utf-8"))
            if not d.get("converged"):
                continue
            vg, i = transfer(d)
            vds, io = output(d)
            ax[0].semilogy(vg, i, color=C_T[T], alpha=0.16, lw=0.7)
            ax[1].plot(vds, io, color=C_T[T], alpha=0.16, lw=0.7)
            n += T == 300
    USED[CUR[0]].add("results/test/runs/*_T300.json, *_T423.json")
    for T, ls in ((300, "-"), (423, "--")):
        d = run(f"results/stage_a_v11/runs/A_base_T{T}.json")
        vg, i = transfer(d)
        vds, io = output(d)
        ax[0].semilogy(vg, i, color="#1a1a1a", ls=ls, lw=1.4)
        ax[1].plot(vds, io, color="#1a1a1a", ls=ls, lw=1.4)
    ax[0].set(xlim=(0, 20), ylim=(1e-12, 1e-1), xticks=range(0, 21, 5), xlabel=X_VGS, ylabel=Y_ID,
              title=rf"(a) Transfer, $V_\mathrm{{DS}}$ = 0.1 V, {n} test devices")
    ax[1].set(xlim=(0, 5.1), ylim=(0, None), xlabel=X_VDS, ylabel=Y_ID,
              title=rf"(b) Output, $V_\mathrm{{GS}}$ = 18 V, {n} test devices")
    h = [Line2D([], [], color=C_T[300], lw=1.6, label="300 K"), Line2D([], [], color=C_T[423], lw=1.6, label="423 K"),
         Line2D([], [], color="#1a1a1a", lw=1.4, label="design center, 300 K"),
         Line2D([], [], color="#1a1a1a", lw=1.4, ls="--", label="design center, 423 K")]
    legend_top(fig, h, 4)
    save(fig, out, "iv_population")


def features_vs_parameters(out):
    """Extracted DC features of the pool and test devices against the four design parameters, 300 K and 423 K."""
    d = pd.concat([runs_table("pool"), runs_table("test")], ignore_index=True)
    d["qit_abs"] = -d["qit_eff_cm2"] / 1e12
    d["gm_mS"] = d["gm_max_S_per_cm"] * 1e3
    feats = [("vth_V", r"$V_\mathrm{th}$ (V)"), ("ss_mV_dec", "SS (mV/dec)"),
             ("gm_mS", r"$g_\mathrm{m,max}$ (mS/cm)"), ("ron_mohm_cm2", r"$R_\mathrm{on,sp}$ (mΩ·cm²)")]
    pars = [("wjfet_scale", LBL_PAR["wjfet_scale"]), ("npwell_scale", LBL_PAR["npwell_scale"]),
            ("qit_abs", LBL_PAR["qit_eff_cm2"]), ("mu_channel_scale", LBL_PAR["mu_channel_scale"])]
    fig, ax = plt.subplots(4, 4, figsize=(10, 8.4), sharex="col", sharey="row", constrained_layout=True)
    ndev = d[d.temperature_K == 300]["candidate_id"].nunique()
    for r, (fc, fl) in enumerate(feats):
        for c, (pc, pl) in enumerate(pars):
            a = ax[r, c]
            for T in (300, 423):
                s = d[np.isclose(d.temperature_K, T)]
                a.scatter(s[pc], s[fc], s=3.2, color=C_T[T], alpha=0.42, lw=0, rasterized=False)
            if c == 0:
                a.set_ylabel(fl)
            if r == 3:
                a.set_xlabel(pl)
    h = [Line2D([], [], marker="o", ls="", ms=5, color=C_T[T], label=f"{T} K") for T in (300, 423)]
    legend_top(fig, h + [Line2D([], [], ls="", label=f"{ndev} devices (pool + test), frozen physics")], 3)
    save(fig, out, "features_vs_parameters")


def variants_423k(out):
    """423 K physics variants: I-V of the test device nearest the design center and the shift of every test device."""
    design = csv("configs/design_test.csv").set_index("candidate_id")
    z = pd.DataFrame({"w": design.wjfet_scale - 1, "n": design.npwell_scale - 1, "q": design.qit_eff_cm2 / 1e12 + 1,
                      "m": design.mu_channel_scale - 1})
    cid = z.pow(2).sum(axis=1).idxmin()
    fig, ax = plt.subplots(2, 2, figsize=(10, 6.6), constrained_layout=True)
    curves = {"nominal": f"results/test/runs/{cid}_T423.json"}
    curves.update({v: f"results/test_{v}/runs/{cid}_T423.json" for v in VARIANTS})
    d300 = run(f"results/test/runs/{cid}_T300.json")
    vg, i = transfer(d300)
    vds, io = output(d300)
    ax[0, 0].semilogy(vg, i, color="#b5b5b5", lw=1.2)
    ax[0, 1].plot(vds, io, color="#b5b5b5", lw=1.2)
    for v, rel in curves.items():
        d = run(rel)
        vg, i = transfer(d)
        vds, io = output(d)
        ls = "-" if v == "nominal" else ("--" if v.startswith("gamma") else "-.")
        ax[0, 0].semilogy(vg, i, color=C_VAR[v], ls=ls)
        ax[0, 1].plot(vds, io, color=C_VAR[v], ls=ls)
    p = design.loc[cid]
    tag = (f"{cid}: $W_\\mathrm{{JFET}}$ {p.wjfet_scale:.2f}, $N_\\mathrm{{pw}}$ {p.npwell_scale:.2f}, "
           f"$Q_\\mathrm{{it,eff}}$ {p.qit_eff_cm2 / 1e12:.2f}".replace("-", "−")
           + r"$\times10^{12}$ cm$^{-2}$, " + f"$s_\\mu$ {p.mu_channel_scale:.2f}")
    ax[0, 0].set(xlim=(0, 10), ylim=(1e-12, 1e-1), xlabel=X_VGS, ylabel=Y_ID,
                 title=r"(a) Transfer at 423 K, $V_\mathrm{DS}$ = 0.1 V")
    ax[0, 1].set(xlim=(0, 5.1), ylim=(0, None), xlabel=X_VDS, ylabel=Y_ID, title=r"(b) Output at 423 K, $V_\mathrm{GS}$ = 18 V")
    ax[0, 0].text(0.02, 0.97, tag, transform=ax[0, 0].transAxes, fontsize=7, va="top", color="#555")
    h = [Line2D([], [], color="#b5b5b5", lw=1.2, label="300 K (same for every variant)")]
    h += [Line2D([], [], color=C_VAR[v], ls="-" if v == "nominal" else ("--" if v.startswith("gamma") else "-."),
                 label=("423 K, " if v == "nominal" else "") + LBL_VAR[v]) for v in curves]
    ax[0, 1].legend(handles=h, loc="upper left", fontsize=7.5)
    base = runs_table("test")
    base = base[np.isclose(base.temperature_K, 423)].set_index("candidate_id")
    dv, dr = [], []
    for v in VARIANTS:
        j = runs_table(f"test_{v}").set_index("candidate_id").join(base, rsuffix="_b", how="inner")
        dv.append(((j.vth_V - j.vth_V_b) * 1e3).values)
        dr.append(((j.ron_mohm_cm2 / j.ron_mohm_cm2_b - 1) * 100).values)
    for a, data, yl, t in ((ax[1, 0], dv, r"$\Delta V_\mathrm{th}$ vs frozen physics (mV)", "(c)"),
                           (ax[1, 1], dr, r"$\Delta R_\mathrm{on,sp}$ vs frozen physics (%)", "(d)")):
        bp = a.boxplot(data, widths=0.5, patch_artist=True, showfliers=False, medianprops=dict(color="#1a1a1a"))
        for k, (patch, v) in enumerate(zip(bp["boxes"], VARIANTS)):
            patch.set(facecolor=C_VAR[v], alpha=0.35, edgecolor=C_VAR[v])
            x = k + 1 + np.random.default_rng(k).uniform(-0.17, 0.17, len(data[k]))
            a.scatter(x, data[k], s=5, color=C_VAR[v], alpha=0.65, lw=0)
        a.axhline(0, color="#9a9a9a", lw=0.8)
        a.set_xticks(range(1, len(VARIANTS) + 1), [LBL_VAR[v].replace(" at 423 K", "") for v in VARIANTS])
        a.set(ylabel=yl, title=f"{t} {len(data[0])} test devices at 423 K")
    save(fig, out, "variants_423k")


def estimation_errors(out):
    """GP inverse model on noisy features: normalized absolute error over the 128 test devices."""
    pts = csv("results/summary/v47_repeat_control_points.csv")
    budget = jload("results/summary/v48_extra_stats.json")["part2"]
    errc = [f"err_{v}" for v in VARS]

    def sel(rho=0.0, level="nominal", model="gp"):
        return pts[(pts.level == level) & np.isclose(pts.rho, rho) & (pts.model == model)]

    fig, ax = plt.subplots(1, 3, figsize=(10, 3.75), constrained_layout=True, gridspec_kw=dict(width_ratios=[1.45, 1, 1]))
    sets = ["S1", "S1x2", "S2"]
    x = np.arange(4)
    w = 0.26
    for k, s in enumerate(sets):
        E = sel()[lambda d: d.set == s].sort_values("candidate_id")[errc].values
        E = np.column_stack([E, E.mean(1)])
        m, lo, hi = mean_ci(E)
        ax[0].bar(x + (k - 1) * w, m, w * 0.92, color=C_SET[s])
        ax[0].errorbar(x + (k - 1) * w, m, yerr=[m - lo, hi - m], fmt="none", ecolor="#333", elinewidth=0.9, capsize=2)
    ax[0].set_xticks(x, [LBL_TGT[v] for v in VARS] + ["mean of 3"])
    ax[0].set(ylabel="normalized absolute error", title=r"(a) By parameter, $\rho$ = 0 (95 % CI)")
    rhos = [0.0, 0.5, 0.9]
    for s in ["S1", "S1x2", "S2", "S3"]:
        m_, lo_, hi_ = [], [], []
        for r in rhos:
            E = sel(r)[lambda d: d.set == s].sort_values("candidate_id")[errc].values.mean(1, keepdims=True)
            m, lo, hi = mean_ci(E)
            m_.append(m[0]); lo_.append(lo[0]); hi_.append(hi[0])
        ax[1].errorbar(rhos, m_, yerr=[np.subtract(m_, lo_), np.subtract(hi_, m_)], color=C_SET[s], marker="o", ms=4,
                       capsize=2)
    ax[1].set(xticks=rhos, xlabel=r"noise correlation $\rho$ (repeats / temperatures)",
              ylabel="mean normalized error", title=r"(b) Correlated noise (95 % CI)")
    bud = sorted(budget, key=int)
    for s in ["S1", "S1x2", "S2"]:
        m = [budget[b][s]["mean"] for b in bud]
        sd = [budget[b][s]["sd"] for b in bud]
        ax[2].errorbar([int(b) for b in bud], m, yerr=sd, color=C_SET[s], marker="o", ms=4, capsize=2)
    ax[2].set(xticks=[int(b) for b in bud], xlabel="DEVSIM runs used for training",
              ylabel="mean normalized error", title="(c) Equal budget (mean ± SD)")
    lo = min(a.get_ylim()[0] for a in ax[1:])
    hi = max(a.get_ylim()[1] for a in ax[1:])
    for a in ax[1:]:
        a.set_ylim(max(0, lo), hi)
    h = [Patch(color=C_SET[s], label=LBL_SET[s]) for s in ["S1", "S1x2", "S2", "S3"]]
    legend_top(fig, h, 4)
    save(fig, out, "estimation_errors")


def robustness_423k(out):
    """Mean normalized error when the 423 K data come from other physics assumptions; drain series resistance."""
    p1 = jload("results/summary/v48_extra_stats.json")["part1"]
    rc = jload("results/summary/v47_repeat_control.json")
    scen = ["base", "gamma0", "gamma_m1", "qitT10", "qitT30"]
    names = {"base": r"frozen ($\gamma$ = +1)", "gamma0": r"$\gamma$ = 0", "gamma_m1": r"$\gamma$ = −1",
             "qitT10": r"$|Q_\mathrm{it}|$ −10 %", "qitT30": r"$|Q_\mathrm{it}|$ −30 %"}
    train = [("matched", "trained on the same physics", "#0b4f8a"), ("mixed", "trained on mixed physics", "#56b4e9"),
             ("nominal", "trained on frozen physics", "#d55e00")]
    fig, ax = plt.subplots(1, 2, figsize=(10, 3.6), constrained_layout=True, gridspec_kw=dict(width_ratios=[1.7, 1]))
    x = np.arange(len(scen))
    w = 0.26
    for k, (key, lab, col) in enumerate(train):
        vals = [p1["scenarios"][s].get(key, {}).get("mean", np.nan) for s in scen]
        ax[0].bar(x + (k - 1) * w, vals, w * 0.92, color=col, label=lab)
    for s, ls in (("S1", ":"), ("S1x2", "--")):
        ax[0].axhline(p1["reference"][s]["mean"], color="#555", ls=ls, lw=1,
                      label=f"{s.replace('x2', '×2')} reference (300 K only)")
    ax[0].set_yscale("log")
    ax[0].set_ylim(0.02, 3)
    ticks = [0.02, 0.05, 0.1, 0.2, 0.5, 1]
    ax[0].set_yticks(ticks, [f"{t:g}" for t in ticks])
    ax[0].yaxis.set_minor_formatter(NullFormatter())
    ax[0].set_xticks(x, [names[s] for s in scen])
    ax[0].set(ylabel="mean normalized error (S2, GP)", title="(a) Physics assumed for the 423 K test data")
    ax[0].legend(fontsize=7.6, ncol=2, loc="upper left")
    nom = next(c for c in rc["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp")
    sets = ["S1", "S1x2", "S2"]
    xx = np.arange(len(sets))
    ax[1].bar(xx - 0.2, [nom["sets"][s]["mean"] for s in sets], 0.38, color="#a3abaf", label="test devices as simulated")
    ax[1].bar(xx + 0.2, [rc["series_r"]["sets"][s]["mean"] for s in sets], 0.38, color="#7b4fc9",
              label="test devices + drain series R\n(0.1–0.3 mΩ·cm², not in training)")
    ax[1].set_xticks(xx, [s.replace("x2", "×2") for s in sets])
    ax[1].set(ylabel="mean normalized error (GP)", title="(b) Drain series resistance")
    ax[1].legend(fontsize=7.2, loc="upper left")
    ax[1].set_ylim(0, max(rc["series_r"]["sets"][s]["mean"] for s in sets) * 1.45)
    save(fig, out, "robustness_423k")


POLICY_DIR = {"random": "results/al_v47/numeric/nominal", "sobol": "results/al_v47/numeric/nominal",
              "uncertainty": "results/al_v47/numeric/nominal", "top20_random": "results/al_v47/numeric/nominal",
              "A": "results/al_v47/named/nominal", "B": "results/al_v47/anon/nominal",
              "C": "results/al_v47/shuffled/nominal", "A0": "results/al_live/nominal"}
LBL_POL = {"random": "random", "sobol": "Sobol", "uncertainty": "uncertainty (forward RF)", "top20_random": "random among top-20 (D)",
           "A0": "LLM, first run (A0)", "A": "LLM, re-run (A)", "B": "LLM, anonymized (B)", "C": "LLM, shuffled info (C)"}


def selection_curves(out):
    """Pool-based selection from 60 to 120 devices (10 seeds): learning curves and final paired differences."""
    cur = {}
    for key, folder in POLICY_DIR.items():
        d = csv(f"{folder}/al_curves.csv")
        d = d[d.policy == ("llm" if key in ("A", "B", "C", "A0") else key)]
        g = d.groupby("n_points").mean_mae_norm
        cur[key] = (g.mean().index.values, g.mean().values, g.std(ddof=1).values, d.seed.nunique())
    ab = jload("results/summary/v47_rq3_ablation.json")
    p3 = jload("results/summary/v48_extra_stats.json")["part3"]
    fig = plt.figure(figsize=(10, 6.4), constrained_layout=True)
    gs = fig.add_gridspec(2, 2, height_ratios=[1.15, 1])
    a0, a1, a2 = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])

    def draw(a, keys, ref=()):
        for k in ref:
            n, m, _, _ = cur[k]
            a.plot(n, m, color=C_POL[k], ls=":", lw=1.2, label=f"{LBL_POL[k]}, reference")
        for k in keys:
            n, m, _, _ = cur[k]
            a.plot(n, m, color=C_POL[k], marker="o", ms=3.2, label=f"{LBL_POL[k]}")
        a.set(xlabel="devices simulated (300 K + 423 K each)", ylabel="mean normalized error (S2, RF)")
        a.legend(fontsize=7.8)

    draw(a0, ["random", "sobol", "uncertainty", "top20_random"])
    a0.set_title(f"(a) Selection policies, mean of {cur['random'][3]} seeds")
    draw(a1, ["A0", "A", "B", "C"], ref=("random", "uncertainty"))
    a1.set_title(f"(b) LLM-assisted selection, mean of {cur['A'][3]} seeds")
    lo = min(a.get_ylim()[0] for a in (a0, a1)); hi = max(a.get_ylim()[1] for a in (a0, a1))
    for a in (a0, a1):
        a.set_ylim(lo, hi)

    def row(label, rec, color):
        f = rec["final"] if "final" in rec else rec
        ci = f.get("ci") or f.get("boot95")
        return label, f["delta"] * 1e3, ci[0] * 1e3, ci[1] * 1e3, f["wins"], f.get("n", 10), color

    rows = [row("uncertainty − random", ab["secondary"]["U-random"], C_POL["uncertainty"]),
            row("Sobol − random", ab["secondary"]["sobol-random"], C_POL["sobol"]),
            row("top-20 random (D) − uncertainty", ab["compare"]["D-U"], C_POL["top20_random"]),
            row("LLM A0 − uncertainty", p3["final:A0-U"], C_POL["A0"]),
            row("LLM A − uncertainty", ab["compare"]["A-U"], C_POL["A"]),
            row("LLM B − uncertainty", ab["compare"]["B-U"], C_POL["B"]),
            row("LLM C − uncertainty", ab["compare"]["C-U"], C_POL["C"])]
    y = np.arange(len(rows))[::-1]
    xt = max(r[3] for r in rows) + 0.9                     # numbers in one column right of the intervals
    mn = lambda v: f"{v:+.1f}".replace("-", "−")
    for yy, (lab, d, lo_, hi_, wins, n, col) in zip(y, rows):
        a2.plot([lo_, hi_], [yy, yy], color=col, lw=2.4, solid_capstyle="butt")
        a2.plot(d, yy, "o", color=col, ms=6.5, mec="white", mew=0.8)
        a2.text(xt, yy, f"{mn(d)}  [{mn(lo_)}, {mn(hi_)}]   first lower in {wins}/{n} seeds", va="center",
                fontsize=8, color="#333")
    a2.axvline(0, color="#7a7a7a", lw=0.9)
    a2.set_yticks(y, [r[0] for r in rows])
    a2.set(xlabel=r"difference in final mean normalized error at 120 devices ($\times10^{-3}$), 95 % CI over seeds",
           title="(c) Paired differences at the final round (first − second)")
    a2.set_xlim(min(r[2] for r in rows) - 0.8, xt + 7.4)
    a2.set_xticks(np.arange(np.floor(min(r[2] for r in rows)), np.ceil(xt), 1.0))
    a2.grid(axis="y", visible=False)
    save(fig, out, "selection_curves")


FIGURES = {"iv_baseline": iv_baseline, "iv_one_at_a_time": iv_one_at_a_time, "iv_population": iv_population,
           "features_vs_parameters": features_vs_parameters, "variants_423k": variants_423k,
           "estimation_errors": estimation_errors, "robustness_423k": robustness_423k,
           "selection_curves": selection_curves}


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", default="docs/figures")
    ap.add_argument("--only", nargs="*", choices=list(FIGURES))
    ap.add_argument("--full-color", action="store_true", help="keep 24-bit PNGs instead of a 256-color palette")
    a = ap.parse_args()
    FULL_COLOR[0] = a.full_color
    out = (ROOT / a.out) if not Path(a.out).is_absolute() else Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for name in a.only or FIGURES:
        CUR[0] = name
        USED[name] = set()
        FIGURES[name](out)
        print(f"{name}.png  ({(out / f'{name}.png').stat().st_size / 1024:.0f} KB)")
    if not a.only:
        files = {}
        for name, rels in USED.items():
            items = []
            for rel in sorted(rels):
                p = ROOT / rel
                items.append(dict(path=rel, bytes=p.stat().st_size, sha256=sha(p)) if p.is_file() else dict(path=rel))
            files[name] = items
        (out / "sources.json").write_text(json.dumps(files, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
