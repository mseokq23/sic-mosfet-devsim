"""Slide-sized charts for the oral presentation, drawn from the committed results.
  python scripts/make_slide_figures.py  -> paper/slides/*.png"""
import json, sys
from pathlib import Path
import numpy as np, pandas as pd
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch
from PIL import Image
ROOT = Path(__file__).resolve().parents[1]; R = ROOT / "results"; OUT = ROOT / "paper/slides"; OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "Noto Sans CJK KR", "mathtext.fontset": "dejavusans", "font.size": 15, "axes.labelsize": 15,
                     "axes.titlesize": 17, "xtick.labelsize": 14, "ytick.labelsize": 14, "legend.fontsize": 13, "axes.linewidth": 0.9,
                     "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False, "axes.unicode_minus": True})
M = lambda t: t.replace("-", "\u2212")   # typographic minus in labels
INK, GRAY, BLUE, ORANGE, RED, GREEN, LIGHT = "#1f2d3d", "#a7b0ba", "#2f5597", "#d9822b", "#c0392b", "#2e8b57", "#d5dbe1"
V = {"W": "$W_{JFET}$", "N": "$N_{pw}$", "Q": "$Q_{it,eff}$", "M": r"$s_\mu$"}
J = lambda p: json.load(open(p))
def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=200, bbox_inches="tight", facecolor="white"); plt.close(fig); print("->", name)
T1 = pd.read_csv(ROOT / "paper/tables/table1_sensitivity.csv").set_index("feature (+20% change)")
def cell(row, col, k=0): return float(str(T1.loc[row, col]).split("/")[k].replace("+", "").strip())
cols = ["W_JFET", "N_pw", "Q_it,eff", [c for c in T1.columns if c.startswith(("μ", "s_"))][0]]

# 1. problem: confusion pairs at 300 K -------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.3))
dv = [cell("ΔV_th (mV)", c) for c in cols]; ion = [cell("I_on (%)", c) for c in cols]
lab = [V["W"], V["N"], V["Q"], V["M"]]
for a, vals, colors, title, unit, fmt in ((ax[0], dv, [GRAY, ORANGE, ORANGE, GRAY], "문턱전압 변화  ΔV$_{th}$ (300 K)", "mV", "{:+.0f} mV"),
                                         (ax[1], ion, [BLUE, GRAY, GRAY, BLUE], "온 전류 변화  ΔI$_{on}$ (300 K)", "%", "{:+.1f}%")):
    y = np.arange(4)[::-1]
    a.barh(y, vals, color=colors, height=0.62)
    a.set_yticks(y); a.set_yticklabels(lab, fontsize=17); a.axvline(0, color=INK, lw=0.9)
    a.set_title(title, loc="left", fontweight="bold", color=INK); a.set_xlabel(f"각 변수 +20% 변화 시 ({unit})")
    span = max(vals) - min(min(vals), 0)
    for yy, v in zip(y, vals):
        txt = ("0 mV" if "mV" in fmt else "0%") if abs(v) < 0.05 else M(fmt.format(v))
        a.text(v + (0.02 * span if v >= 0 else -0.02 * span), yy, txt, va="center", ha="left" if v >= 0 else "right", fontsize=15, color=INK)
    a.set_xlim(min(min(vals), 0) - 0.32 * span, max(vals) + 0.30 * span)
ax[0].text(0.98, 0.05, "거의 같은 이동", transform=ax[0].transAxes, ha="right", fontsize=15, color=ORANGE, fontweight="bold")
ax[1].text(0.98, 0.93, "둘 다 전류 증가", transform=ax[1].transAxes, ha="right", fontsize=15, color=BLUE, fontweight="bold")
fig.tight_layout(w_pad=3); save(fig, "s_confusion")

# 2. idea: 423 K separates the pairs --------------------------------------------------------------
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.5), gridspec_kw=dict(width_ratios=[1, 1.15]))
for c, color, name in ((cols[0], BLUE, V["W"]), (cols[3], ORANGE, V["M"])):
    a300, a423 = cell("I_on (%)", c, 0), cell("I_on (%)", c, 1)
    ax[0].plot([0, 1], [a300, a423], "-o", color=color, lw=3, ms=10)
    ax[0].text(-0.06, a300, M(f"{a300:+.1f}%"), ha="right", va="center", fontsize=16, color=color)
    ax[0].text(1.06, a423, f"{a423:+.1f}%  {name}", ha="left", va="center", fontsize=16, color=color, fontweight="bold")
ax[0].set_xlim(-0.45, 1.75); ax[0].set_ylim(2, 9); ax[0].set_xticks([0, 1]); ax[0].set_xticklabels(["300 K", "423 K"], fontsize=16)
ax[0].set_ylabel("ΔI$_{on}$ (%)  (+20% 변화)"); ax[0].set_title("온 전류 민감도의 온도 변화", loc="left", fontweight="bold", color=INK)
ss = [cell("SS (%)", cols[1]), cell("SS (%)", cols[2])]
dt = [cell("Δ[V_th(423 K) − V_th(300 K)] (mV)", cols[1]), cell("Δ[V_th(423 K) − V_th(300 K)] (mV)", cols[2])]
x = np.arange(2); w = 0.36
b1 = ax[1].bar(x - w / 2, ss, w, color=[ORANGE, GRAY], label="SS 변화 (%)")
ax2 = ax[1].twinx(); ax2.spines["right"].set_visible(True)
b2 = ax2.bar(x + w / 2, dt, w, color=[ORANGE, GRAY], hatch="//", edgecolor="white", label="ΔV$_{th}$ 온도 이동 변화 (mV)")
ax[1].set_xticks(x); ax[1].set_xticklabels([V["N"], V["Q"]], fontsize=17); ax[1].set_ylim(-4.5, 4.5); ax2.set_ylim(-13, 13)
ax[1].axhline(0, color=INK, lw=0.9); ax[1].set_ylabel("SS 변화 (%)"); ax2.set_ylabel("V$_{th}$ 온도 이동 변화 (mV)")
for xx, v in zip(x - w / 2, ss): ax[1].text(xx, v + (0.25 if v >= 0 else -0.6), "0%" if abs(v) < 0.05 else M(f"{v:+.1f}%"), ha="center", fontsize=15, color=INK)
for xx, v in zip(x + w / 2, dt): ax2.text(xx, v + (0.8 if v >= 0 else -2.0), "0 mV" if abs(v) < 0.05 else M(f"{v:+.1f} mV"), ha="center", fontsize=15, color=INK)
ax[1].set_title(f"{V['N']}만 남기는 신호", loc="left", fontweight="bold", color=INK)
ax[1].legend(handles=[Patch(fc=ORANGE, label="SS 변화"), Patch(fc=ORANGE, hatch="//", ec="white", label="V$_{th}$ 온도 이동 변화")], loc="upper right", fontsize=13)
fig.tight_layout(w_pad=3); save(fig, "s_temperature")

# 3. RQ1 --------------------------------------------------------------------------------------------
rb = J(R / "summary/robustness.json")["levels"]; b = rb["nominal"]["baseline (in-model)"]
eb = J(ROOT / "paper/figure_notes.json")["fig3"]["equal_budget"]
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.6), gridspec_kw=dict(width_ratios=[1.1, 1]))
keys = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]; x = np.arange(3); w = 0.36
s1 = [b["S1"][k] for k in keys]; s2 = [b["S2"][k] for k in keys]
ax[0].bar(x - w / 2, s1, w, color=GRAY, label="300 K만 (S1)"); ax[0].bar(x + w / 2, s2, w, color=BLUE, label="300 + 423 K (S2)")
for xx, a1, a2 in zip(x, s1, s2):
    ax[0].text(xx - w / 2, a1 + 0.003, f"{a1:.3f}", ha="center", fontsize=13, color=INK)
    ax[0].text(xx + w / 2, a2 + 0.003, f"{a2:.3f}", ha="center", fontsize=13, color=BLUE, fontweight="bold")
    ax[0].text(xx, max(a1, a2) + 0.022, M(f"{100 * (a2 - a1) / a1:+.0f}%"), ha="center", fontsize=16, color=BLUE, fontweight="bold")
ax[0].set_xticks(x); ax[0].set_xticklabels([V["W"], V["N"], V["Q"]], fontsize=17); ax[0].set_ylim(0, 0.21)
ax[0].set_ylabel("정규화 MAE (낮을수록 좋음)"); ax[0].legend(loc="upper right", ncol=1); ax[0].set_title("변수별 역추정 오차 (기본 잡음, GP)", loc="left", fontweight="bold", color=INK)
for S, color, mk, lab in (("S1", GRAY, "o", "S1: n점"), ("S2", BLUE, "s", "S2: n/2점")):
    bb = np.array(eb[S]); ax[1].errorbar(bb[:, 0], bb[:, 1], yerr=bb[:, 2], color=color, marker=mk, ms=9, lw=3, capsize=4, label=lab)
ax[1].set_xscale("log", base=2); ax[1].set_xticks([60, 120, 240, 480]); ax[1].set_xticklabels(["60", "120", "240", "480"])
ax[1].set_xlabel("DEVSIM 실행 수 (학습)"); ax[1].set_ylabel("평균 정규화 MAE"); ax[1].legend(loc="center right")
ax[1].set_title("같은 계산량에서 비교", loc="left", fontweight="bold", color=INK)
s2_120 = eb["S2"][1][1]; s1_480 = eb["S1"][3][1]
ax[1].annotate(f"120회: {s2_120:.3f}", (120, s2_120), xytext=(150, 0.093), fontsize=14, color=BLUE, arrowprops=dict(arrowstyle="-", color=BLUE))
ax[1].annotate(f"480회: {s1_480:.3f}", (480, s1_480), xytext=(250, 0.124), fontsize=14, color="#59636e", arrowprops=dict(arrowstyle="-", color="#59636e"))
fig.tight_layout(w_pad=3); save(fig, "s_rq1")

# 4. robustness ---------------------------------------------------------------------------------------
mx = J(R / "summary/robustness_mixed.json")["levels"]["nominal"]; N = rb["nominal"]
sc = [("base", "baseline (in-model)", None), ("gamma0", "gamma0 in-model", "gamma0 out-of-model"), ("gamma_m1", "gamma_m1 in-model", "gamma_m1 out-of-model"),
      ("qitT10", "qitT10 in-model", "qitT10 out-of-model"), ("qitT30", "qitT30 in-model", "qitT30 out-of-model")]
labels = ["기준\n(γ = +1, r = 0)", "γ = 0", "γ = −1", "r = 0.1", "r = 0.3"]
fig, ax = plt.subplots(figsize=(13.5, 5.0)); x = np.arange(5); w = 0.26
def bar(xx, v, c, h=None):
    ax.bar(xx, v, w, color=c, hatch=h, edgecolor="white" if h else c, lw=0)
    ax.text(xx, v * 1.07, f"{v:.3f}", ha="center", va="bottom", fontsize=12.5, rotation=90, color=INK)
for i, (k, kin, kout) in enumerate(sc):
    bar(x[i] - w, N[kin]["S2"]["mean"], BLUE)
    if kout: bar(x[i], N[kout]["S2"]["mean"], RED)
    bar(x[i] + w, mx[f"all-mixed -> {k}"]["S2"]["mean"], GREEN)
xs = 5.25; sr = N["series-R out-of-model"]
bar(xs - w / 2, sr["S1"]["mean"], GRAY, "//"); bar(xs + w / 2, sr["S2"]["mean"], RED, "//")
s1v = b["S1"]["mean"]; ax.axhline(s1v, color=INK, lw=1.4, ls="--")
ax.set_yscale("log"); ax.set_ylim(0.02, 9); ax.set_xticks(list(x) + [xs]); ax.set_xticklabels(labels + ["기생 직렬저항\n(시험만)"], fontsize=14)
ax.set_ylabel("S2 평균 정규화 MAE (로그)"); ax.set_xlabel("시험 데이터의 423 K 물리")
ax.legend(handles=[Patch(fc=BLUE, label="같은 물리로 학습"), Patch(fc=RED, label="기준 물리로 학습 (불일치)"), Patch(fc=GREEN, label="가정 무작위화 학습 (사후)"),
                   Patch(fc=GRAY, hatch="//", ec="white", label="S1 (직렬저항 시험)"), Line2D([0], [0], color=INK, lw=1.4, ls="--", label=f"S1 = {s1v:.3f} (300 K만)")],
          loc="upper left", ncol=3, fontsize=13, columnspacing=1.2)
ax.grid(alpha=0.25, axis="y", which="both"); fig.tight_layout(); save(fig, "s_robust")

# 5. RQ2 ---------------------------------------------------------------------------------------------
base, live = pd.read_csv(R / "al/nominal/al_curves.csv"), pd.read_csv(R / "al_live/nominal/al_curves.csv")
d = pd.concat([base[base.policy != "llm"], live[live.policy == "llm"]])
PC = {"random": "#8c96a0", "sobol": BLUE, "uncertainty": GREEN, "llm": ORANGE}
NAME = {"random": "무작위", "sobol": "Sobol 순서", "uncertainty": "불확실도", "llm": "LLM 보조"}
fig, ax = plt.subplots(1, 2, figsize=(13.5, 4.6), gridspec_kw=dict(width_ratios=[1.15, 1]))
for p in ("random", "sobol", "uncertainty", "llm"):
    m = d[d.policy == p].groupby("n_points").mean_mae_norm.mean()
    ax[0].plot(m.index, m.values, "-o", color=PC[p], lw=3 if p in ("uncertainty", "llm") else 2.2, ms=6, label=NAME[p])
ax[0].set_xlabel("학습 공정점 수 (점당 DEVSIM 2회)"); ax[0].set_ylabel("평균 정규화 MAE (시험)"); ax[0].legend(loc="upper right")
ax[0].set_title("학습 곡선 (시드 10개 평균)", loc="left", fontweight="bold", color=INK)
fin = d[d.n_points == d.n_points.max()].pivot_table(index="seed", columns="policy", values="mean_mae_norm")
rows = [("Sobol − 무작위", fin.sobol - fin.random, PC["sobol"]), ("불확실도 − 무작위", fin.uncertainty - fin.random, PC["uncertainty"]),
        ("LLM − 무작위", fin.llm - fin.random, PC["llm"]), ("LLM − 불확실도", fin.llm - fin.uncertainty, PC["llm"])]
rng = np.random.default_rng(3)
for i, (lab, dd, c) in enumerate(rows):
    dd = dd.values; bs = rng.choice(dd, (10000, len(dd))).mean(1); lo, hi = np.percentile(bs, [2.5, 97.5]); y = 3 - i
    ax[1].errorbar(1e3 * dd.mean(), y, xerr=[[1e3 * (dd.mean() - lo)], [1e3 * (hi - dd.mean())]], fmt="s" if i == 3 else "o", ms=10, color=c,
                   mfc="white" if i == 3 else c, capsize=5, lw=2.5)
    ax[1].text(6.2, y, M(f"{1e3 * dd.mean():+.1f} [{1e3 * lo:+.1f}, {1e3 * hi:+.1f}]"), va="center", fontsize=13.5, color=INK)
ax[1].axvline(0, color=INK, lw=1); ax[1].set_yticks(range(4)); ax[1].set_yticklabels([r[0] for r in rows][::-1], fontsize=14)
ax[1].set_xlim(-5, 15); ax[1].set_xlabel("최종 오차 차이 (×10$^{-3}$, 음수 = 개선)")
ax[1].set_title("최종 라운드 짝지은 차이 (95% CI)", loc="left", fontweight="bold", color=INK)
fig.tight_layout(w_pad=3); save(fig, "s_rq2")

# 6. RQ3: paired seeds, uncertainty vs LLM ---------------------------------------------------------------
fig, ax = plt.subplots(figsize=(6.2, 4.6))
u, l = fin.uncertainty.values, fin.llm.values
for a, c in zip(u, l): ax.plot([0, 1], [a, c], color=LIGHT, lw=2, zorder=1)
ax.scatter(np.zeros(10), u, s=90, color=GREEN, zorder=2); ax.scatter(np.ones(10), l, s=90, color=ORANGE, zorder=2)
ax.errorbar([-0.18], [u.mean()], yerr=[[0]], fmt="D", ms=11, color=GREEN); ax.errorbar([1.18], [l.mean()], yerr=[[0]], fmt="D", ms=11, color=ORANGE)
ax.text(-0.25, u.mean(), f"{u.mean():.4f}", ha="right", va="center", fontsize=15, color=GREEN, fontweight="bold")
ax.text(1.25, l.mean(), f"{l.mean():.4f}", ha="left", va="center", fontsize=15, color=ORANGE, fontweight="bold")
ax.set_xticks([0, 1]); ax.set_xticklabels(["불확실도", "LLM 보조"], fontsize=16); ax.set_xlim(-0.75, 1.75)
ax.set_ylabel("최종 평균 정규화 MAE"); ax.set_title("시드별 최종 오차 (10개)", loc="left", fontweight="bold", color=INK)
fig.tight_layout(); save(fig, "s_rq3")

# 7. device cross-section crop from Fig. 1(a) -------------------------------------------------------------
im = Image.open(ROOT / "paper/figures/fig1_structure_flow.png"); W, H = im.size
im.crop((0, 0, int(W * 0.338), H)).save(OUT / "s_device.png"); print("-> s_device")
