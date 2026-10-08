"""Manuscript V4.7 figures from the committed v4.7 results (no model fitting; reads result files only).
  python scripts/make_v47_figures.py
-> paper/figures/fig3_rq1_v47.(png|pdf)          (a) S1 / S1x2 / S2 per parameter, (b) noise-correlation sweep   [review]
   paper/figures/fig3_rq1_robust_v47.(png|pdf)   (a), (b) + (c) 423 K physics mismatch with the S1x2 reference      [proceedings]
   paper/figures/fig4_policies_v47.(png|pdf)     (a) learning curves (same session), (b) paired final differences
   paper/figures/v47_figure_notes.json           every number drawn, for checking the manuscript text
Sources: results/summary/v47_repeat_control_points.csv, v47_repeat_control.json, robustness.json, robustness_mixed.json,
results/al_v47/*, results/al_live/nominal (A0). Bootstrap: test points (seed 7, 2000) for Fig. 3, seeds (as in
scripts/rq3_ablation.py: seed 1, 5000) for Fig. 4, so the numbers equal results/summary/v47_rq3_ablation.json."""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import make_paper_figures as M                      # rcParams, sizes, helpers (label, save, TAG)
from rq3_ablation import boot, per_seed             # identical paired bootstrap to the v4.7 summary
plt = M.plt
R, S = ROOT / "results", ROOT / "results" / "summary"
VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]
C_S1, C_S1X2, C_S2 = "#c9c9c9", "#5e9ad6", "#2f5597"    # baseline gray, then a blue ramp (validated adjacent pairs)
NOTES = {}


def pts(level="nominal", rho=0.0, model="gp"):
    d = pd.read_csv(S / "v47_repeat_control_points.csv")
    return d[(d.level == level) & np.isclose(d.rho, rho) & (d.model == model)]


def mean_ci(E, n=2000, seed=7):
    """E: (n_points, k) per-point errors -> column means and 95% CI (test-point bootstrap, as in make_paper_figures.fig3)."""
    bi = np.random.default_rng(seed).integers(0, len(E), (n, len(E)))
    return E.mean(0), np.percentile(E[bi].mean(1), [2.5, 97.5], axis=0)


def panel_a(ax):
    d = pts()
    spec = [("S1", "S1: 300 K", C_S1, None), ("S1x2", "S1×2: 300 K twice", C_S1X2, None),
            ("S2", "S2: 300 + 423 K", C_S2, None)]
    x = np.arange(3); wd = 0.26; out = {}
    for i, (s, lab, c, h) in enumerate(spec):
        E = d[d.set == s].sort_values("candidate_id")[[f"err_{v}" for v in VARS]].values
        m, ci = mean_ci(E)
        ax.bar(x + (i - 1) * wd, m, wd * 0.92, color=c, hatch=h, edgecolor="k", lw=0.3, label=lab,
               yerr=[m - ci[0], ci[1] - m], error_kw=dict(lw=0.6, capsize=1.5))
        out[s] = dict(mean=[round(float(v), 4) for v in m], lo=[round(float(v), 4) for v in ci[0]], hi=[round(float(v), 4) for v in ci[1]])
    rc = json.load(open(S / "v47_repeat_control.json"))
    case = next(c for c in rc["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp")
    for j, v in enumerate(VARS):                        # temperature-specific gain: S2 vs S1x2, paired CI excludes 0?
        con = case["contrasts"]["S2-S1x2"][v]
        if con["ci"][1] < 0:
            top = out["S1x2"]["hi"][j] + 0.012
            ax.plot([x[j], x[j], x[j] + wd, x[j] + wd], [top - 0.004, top, top, top - 0.004], color="k", lw=0.5)
            ax.text(x[j] + wd / 2, top + 0.003, f"−{100 * (1 - con['ratio']):.0f}%", ha="center", va="bottom", fontsize=6)
    ax.axhline(0.25, color="k", lw=0.5, ls="--")
    ax.text(2.55, 0.244, "no information (uniform guess)", fontsize=6, ha="right", va="top")
    ax.set_xticks(x); ax.set_xticklabels([M.TAG[v] for v in VARS]); ax.set_ylabel("MAE / DOE range"); ax.set_ylim(0, 0.315)
    ax.legend(loc="upper center", ncol=3, fontsize=5.8, columnspacing=0.9, handlelength=1.4, borderaxespad=0.3)
    ax.grid(alpha=0.25, lw=0.4, axis="y")
    NOTES["fig3a"] = out


def panel_b(ax):
    rhos = [0.0, 0.5, 0.9]; out = {}
    spec = [("S1", "S1", "0.45", "o", (0, (3, 2)), "white", -0.024), ("S1x2", "S1×2", C_S1X2, "s", "-", C_S1X2, -0.008),
            ("S2", "S2", C_S2, "D", "-", C_S2, 0.008), ("S3", "S3 (S2 + differences)", C_S2, "^", (0, (1, 1.2)), "white", 0.024)]
    for s, lab, c, mk, ls, mf, dx in spec:
        m, lo, hi = [], [], []
        for r in rhos:
            E = pts(rho=r)
            E = E[E.set == s].sort_values("candidate_id")[[f"err_{v}" for v in VARS]].values.mean(1, keepdims=True)
            mm, ci = mean_ci(E)
            m.append(mm[0]); lo.append(ci[0][0]); hi.append(ci[1][0])
        m, lo, hi = map(np.array, (m, lo, hi))
        ax.errorbar(np.array(rhos) + dx, m, yerr=[m - lo, hi - m], color=c, marker=mk, ms=3.2, mfc=mf, mec=c, ls=ls, lw=0.9,
                    capsize=1.5, label=lab)
        out[s] = dict(rho=rhos, mean=[round(float(v), 4) for v in m], lo=[round(float(v), 4) for v in lo], hi=[round(float(v), 4) for v in hi])
    ax.set_xticks(rhos); ax.set_xlim(-0.08, 0.98); ax.set_ylim(0.055, 0.148)
    ax.set(xlabel=r"noise correlation between the two measurements, $\rho$", ylabel="mean MAE / range")
    ax.legend(loc="upper center", fontsize=5.8, ncol=4, handlelength=2.0, columnspacing=0.9, borderaxespad=0.3)
    ax.grid(alpha=0.25, lw=0.4, axis="y")
    NOTES["fig3b"] = out


def panel_c(ax):
    rb = json.load(open(S / "robustness.json"))["levels"]["nominal"]
    mx = json.load(open(S / "robustness_mixed.json"))["levels"]["nominal"]
    rc = json.load(open(S / "v47_repeat_control.json"))
    s1x2 = next(c for c in rc["cases"] if c["level"] == "nominal" and c["rho"] == 0 and c["model"] == "gp")["sets"]["S1x2"]["mean"]
    keys = [("base", "baseline (in-model)", None), ("gamma0", "gamma0 in-model", "gamma0 out-of-model"),
            ("gamma_m1", "gamma_m1 in-model", "gamma_m1 out-of-model"), ("qitT10", "qitT10 in-model", "qitT10 out-of-model"),
            ("qitT30", "qitT30 in-model", "qitT30 out-of-model")]
    labels = ["Baseline", r"$\gamma$ = 0", r"$\gamma$ = $-$1", "$r$ = 0.1", "$r$ = 0.3"]
    s1 = rb["baseline (in-model)"]["S1"]["mean"]
    x = np.arange(len(keys)); wd = 0.26

    def bar(xx, v, color, hatch=None, w=wd):
        ax.bar(xx, v, w, color=color, edgecolor="k", lw=0.3, hatch=hatch)
        ax.text(xx, v * 1.07, f"{v:.3f}", ha="center", va="bottom", fontsize=4.8, rotation=90)

    for i, (k, kin, kout) in enumerate(keys):
        bar(x[i] - wd, rb[kin]["S2"]["mean"], "#2f5597")
        if kout:
            bar(x[i], rb[kout]["S2"]["mean"], "#c0392b")
        bar(x[i] + wd, mx[f"all-mixed -> {k}"]["S2"]["mean"], "#2ca02c")
    xs = len(keys) + 0.3                                       # parasitic series resistance, test data only
    sr = rc["series_r"]["sets"]
    for xx, v, c, h in ((xs - wd, sr["S1"]["mean"], C_S1, "////"), (xs, sr["S1x2"]["mean"], C_S1X2, "////"),
                        (xs + wd, sr["S2"]["mean"], "#c0392b", "////")):
        bar(xx, v, c, h)
    ax.axhline(s1, color="k", lw=0.6, ls="--")
    ax.axhline(s1x2, color=C_S1X2, lw=0.8, ls=(0, (4, 1.5, 1, 1.5)))
    ax.set_yscale("log"); ax.set_ylim(0.02, 9.0)
    ax.set_xticks(list(x) + [xs]); ax.set_xticklabels(labels + ["Series $R$"], fontsize=6)
    ax.set_ylabel("mean MAE / range (log)"); ax.set_xlabel("423 K physics of the test data")
    ax.legend(handles=[Patch(fc="#2f5597", ec="k", lw=0.3, label="S2, matched training"),
                       Patch(fc="#c0392b", ec="k", lw=0.3, label="S2, nominal training (mismatch)"),
                       Patch(fc="#2ca02c", ec="k", lw=0.3, label="S2, mixed physics (post hoc)"),
                       Patch(fc="white", ec="k", lw=0.3, hatch="////", label="with series $R$ (S1, S1×2, S2)"),
                       Line2D([0], [0], color="k", lw=0.6, ls="--", label=f"S1 = {s1:.3f}"),
                       Line2D([0], [0], color=C_S1X2, lw=0.8, ls=(0, (4, 1.5, 1, 1.5)), label=f"S1×2 = {s1x2:.3f}")],
              loc="upper left", ncol=2, fontsize=5.2, columnspacing=0.9, handlelength=1.6)
    ax.grid(alpha=0.25, lw=0.4, axis="y", which="both")
    NOTES["fig3c"] = dict(S1=round(s1, 4), S1x2=round(s1x2, 4), series_r={k: round(v["mean"], 4) for k, v in sr.items()})


def fig3(three):
    if three:
        fig, ax = plt.subplots(3, 1, figsize=(M.C1, 4.95), gridspec_kw=dict(height_ratios=[1.2, 0.85, 1.4]))
    else:
        fig, ax = plt.subplots(2, 1, figsize=(M.C1, 3.45), gridspec_kw=dict(height_ratios=[1.25, 0.95]))
    panel_a(ax[0]); panel_b(ax[1])
    if three:
        panel_c(ax[2])
    for a, s in zip(ax, "abc"):
        M.label(a, f"({s})", -0.21, 1.035)
    fig.tight_layout(pad=0.3, h_pad=0.7)
    M.save(fig, "fig3_rq1_robust_v47" if three else "fig3_rq1_v47")


# ------------------------------------------------------------------ Fig. 4
PC = {"random": "#a6a6a6", "sobol": "#1f77b4", "uncertainty": "#2ca02c", "top20_random": "#9467bd", "llm": "#d62728"}
COND = {"U": (R / "al_v47/numeric/nominal", "uncertainty"), "random": (R / "al_v47/numeric/nominal", "random"),
        "sobol": (R / "al_v47/numeric/nominal", "sobol"), "D": (R / "al_v47/numeric/nominal", "top20_random"),
        "A": (R / "al_v47/named/nominal", "llm"), "B": (R / "al_v47/anon/nominal", "llm"),
        "C": (R / "al_v47/shuffled/nominal", "llm"), "A0": (R / "al_live/nominal", "llm")}


def fig4():
    data = {k: per_seed(*v) for k, v in COND.items()}
    fig = plt.figure(figsize=(M.C1, 3.85))
    ax = [fig.add_axes([0.16, 0.585, 0.82, 0.385]), fig.add_axes([0.385, 0.085, 0.595, 0.385])]
    lines = [("random", "Random", "o", "-"), ("sobol", "Sobol", "s", "-"), ("U", "Uncertainty", "D", "-"),
             ("D", "Top-20 random", "v", "-"), ("A", "LLM (Claude)", "o", "-")]
    for k, lab, mk, ls in lines:
        d = data[k][3]; pol = COND[k][1]
        m = d[d.policy == pol].groupby("n_points").mean_mae_norm.mean()
        ax[0].plot(m.index, m.values, marker=mk, ms=2.6, color=PC[pol], ls=ls, label=lab)
    ax[0].set(xlabel="process points (2 DEVSIM runs each)", ylabel="mean MAE / range (test)", xlim=(58, 122), ylim=(0.1215, 0.1495))
    ax[0].text(0.03, 0.04, "mean of 10 seeds (same initial 60 points per seed)", transform=ax[0].transAxes, fontsize=5.8)
    ax[0].legend(loc="upper right", fontsize=5.8, ncol=2, columnspacing=0.9, handlelength=1.8, borderaxespad=0.3)
    ax[0].grid(alpha=0.25, lw=0.4)
    rows = [("Uncertainty − Random", "U", "random", PC["uncertainty"], "D", None),
            ("Sobol − Random", "sobol", "random", PC["sobol"], "s", None),
            ("Top-20 random − Uncertainty", "D", "U", PC["top20_random"], "v", None),
            ("LLM, original run − Unc.", "A0", "U", PC["llm"], "o", "white"),
            ("LLM, repeat run − Unc.", "A", "U", PC["llm"], "o", None),
            ("LLM, anonymized − Unc.", "B", "U", PC["llm"], "^", None),
            ("LLM, shuffled info − Unc.", "C", "U", PC["llm"], "s", "white")]
    summ = {}
    for i, (lab, a, b, c, mk, mf) in enumerate(rows):
        fa, fb = data[a][0], data[b][0]
        assert list(fa.index) == list(fb.index)
        r = boot((fa - fb).values)
        y = len(rows) - 1 - i
        ax[1].errorbar(1e3 * r["delta"], y, xerr=[[1e3 * (r["delta"] - r["ci"][0])], [1e3 * (r["ci"][1] - r["delta"])]],
                       fmt=mk, ms=3, color=c, mfc=mf or c, mec=c, capsize=2, lw=0.9)
        ax[1].text(6.0, y, f"{1e3 * r['delta']:+.1f} [{1e3 * r['ci'][0]:+.1f}, {1e3 * r['ci'][1]:+.1f}]  {r['wins']}/10",
                   fontsize=5.6, va="center")
        summ[lab] = [round(1e3 * r["delta"], 2), round(1e3 * r["ci"][0], 2), round(1e3 * r["ci"][1], 2), r["wins"]]
    ax[1].axhline(4.5, color="0.6", lw=0.4, ls=":")
    ax[1].axvline(0, color="k", lw=0.5)
    ax[1].set_yticks(range(len(rows))); ax[1].set_yticklabels([r[0] for r in rows][::-1], fontsize=6.1)
    ax[1].set(xlabel="final-round difference in mean MAE / range (×10$^{-3}$)", xlim=(-5, 15.2))
    ax[1].set_xticks([-5, 0, 5])
    ax[1].grid(alpha=0.25, lw=0.4, axis="x")
    M.label(ax[0], "(a)", -0.15, 1.0); M.label(ax[1], "(b)", -0.62, 1.0)
    M.save(fig, "fig4_policies_v47")
    NOTES["fig4"] = dict(final={k: [round(float(v[0].mean()), 4), round(float(v[0].std()), 4)] for k, v in data.items()},
                         diffs_x1e3=summ)


if __name__ == "__main__":
    fig3(False); fig3(True); fig4()
    json.dump(NOTES, open(M.FIG / "v47_figure_notes.json", "w"), indent=1, ensure_ascii=False)
    print("-> paper/figures/fig3_rq1_v47, fig3_rq1_robust_v47, fig4_policies_v47 (.png, .pdf), v47_figure_notes.json")
