"""Figure 3 with a third panel for the physics-mismatch (robustness) results.
  python scripts/make_fig3_robust.py   -> paper/figures/fig3_rq1.(png|pdf), fig3_rq1_robust.(png|pdf)
Panels (a) and (b) are computed exactly as in make_paper_figures.fig3(); panel (c) reads
results/summary/robustness.json and robustness_mixed.json (nominal noise, GP)."""
import inspect, json, sys
from pathlib import Path
import numpy as np
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "scripts"))
import make_paper_figures as M


def panel_c(ax):
    rb = json.load(open(M.R / "summary/robustness.json"))["levels"]["nominal"]
    mx = json.load(open(M.R / "summary/robustness_mixed.json"))["levels"]["nominal"]
    keys = [("base", "baseline (in-model)", None), ("gamma0", "gamma0 in-model", "gamma0 out-of-model"),
            ("gamma_m1", "gamma_m1 in-model", "gamma_m1 out-of-model"), ("qitT10", "qitT10 in-model", "qitT10 out-of-model"),
            ("qitT30", "qitT30 in-model", "qitT30 out-of-model")]
    labels = ["Baseline", r"$\gamma$ = 0", r"$\gamma$ = $-$1", "$r$ = 0.1", "$r$ = 0.3"]
    s1 = rb["baseline (in-model)"]["S1"]["mean"]
    x = np.arange(len(keys)); wd = 0.26

    def bar(xx, v, color, hatch=None):
        ax.bar(xx, v, wd, color=color, edgecolor="k", lw=0.3, hatch=hatch)
        ax.text(xx, v * 1.07, f"{v:.3f}", ha="center", va="bottom", fontsize=4.8, rotation=90)

    for i, (k, kin, kout) in enumerate(keys):
        bar(x[i] - wd, rb[kin]["S2"]["mean"], "#2f5597")
        if kout:
            bar(x[i], rb[kout]["S2"]["mean"], "#c0392b")
        bar(x[i] + wd, mx[f"all-mixed -> {k}"]["S2"]["mean"], "#2ca02c")
    xs = len(keys) + 0.15                                   # parasitic series resistance, test data only
    sr = rb["series-R out-of-model"]
    bar(xs - wd / 2, sr["S1"]["mean"], "#c9c9c9", "////")
    bar(xs + wd / 2, sr["S2"]["mean"], "#c0392b", "////")
    ax.axhline(s1, color="k", lw=0.6, ls="--")
    ax.set_yscale("log"); ax.set_ylim(0.02, 9.0)
    ax.set_xticks(list(x) + [xs]); ax.set_xticklabels(labels + ["Series $R$"], fontsize=6)
    ax.set_ylabel("mean MAE / range (log)"); ax.set_xlabel("423 K physics of the test data")
    ax.legend(handles=[Patch(fc="#2f5597", ec="k", lw=0.3, label="S2, matched training"),
                       Patch(fc="#c0392b", ec="k", lw=0.3, label="S2, nominal training (mismatch)"),
                       Patch(fc="#2ca02c", ec="k", lw=0.3, label="S2, mixed physics (post hoc)"),
                       Patch(fc="#c9c9c9", ec="k", lw=0.3, hatch="////", label="S1, with series $R$"),
                       Line2D([0], [0], color="k", lw=0.6, ls="--", label=f"S1 (300 K only) = {s1:.3f}")],
              loc="upper left", ncol=2, fontsize=5.3, columnspacing=0.9, handlelength=1.5)
    ax.grid(alpha=0.25, lw=0.4, axis="y", which="both")


def fig3_robust():
    src = inspect.getsource(M.fig3)
    src = src.replace('fig, ax = plt.subplots(2, 1, figsize=(C1, 3.5), gridspec_kw=dict(height_ratios=[1.25, 1]))',
                      'fig, ax = plt.subplots(3, 1, figsize=(C1, 4.85), gridspec_kw=dict(height_ratios=[1.15, 0.85, 1.4]))')
    src = src.replace('for a, s in zip(ax, "ab"):', 'panel_c(ax[2])\n    for a, s in zip(ax, "abc"):')
    src = src.replace('label(a, f"({s})", -0.15, 1.0)', 'label(a, f"({s})", -0.2, 1.0)')
    src = src.replace('save(fig, "fig3_rq1")', 'save(fig, "fig3_rq1_robust")').replace("def fig3():", "def _fig3_robust():")
    assert "panel_c(ax[2])" in src and "fig3_rq1_robust" in src
    ns = dict(M.__dict__); ns["panel_c"] = panel_c
    exec(compile(src, "fig3_robust", "exec"), ns)
    ns["_fig3_robust"]()


if __name__ == "__main__":
    M.fig3()            # two-panel version (review manuscript)
    fig3_robust()       # three-panel version (proceedings manuscript)
    print("-> paper/figures/fig3_rq1.png, fig3_rq1_robust.png")
