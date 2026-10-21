"""Check every number reported in the paper against the committed configuration and result files.
  python scripts/check_paper_numbers.py                  # prints the table, writes paper/numbers.csv
  python scripts/check_paper_numbers.py --out /tmp/n.csv # write the table elsewhere
Each check recomputes a value from configs/ or results/ (no DEVSIM, no model fitting; a few seconds), formats it the way
the paper prints it and compares the strings. Exit code 1 if any check fails. Values are written with ASCII '-' for
minus, '~' for ranges and '/' between the 300 K and 423 K values, as in the paper."""
from __future__ import annotations

import csv
import inspect
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.alsim import diverse_top, run_policy
from sicsim.analysis import feature_set, make_model, wide_table
from sicsim.config import _Loader, load_config

R, S = ROOT / "results", ROOT / "results" / "summary"
J = lambda p: json.load(open(p, encoding="utf-8"))
Y = lambda p: yaml.load(open(p, encoding="utf-8"), Loader=_Loader)
VARS = ["wjfet_scale", "npwell_scale", "qit_eff_cm2"]
f2, f3, f4 = (lambda v: f"{v:.2f}"), (lambda v: f"{v:.3f}"), (lambda v: f"{v:.4f}")
sgn1 = lambda v: "0.0" if abs(v) < 0.05 else f"{v:+.1f}"
yes = lambda b: "yes" if b else "no"
ROWS: list[dict] = []


def check(section, item, paper, value, source):
    ROWS.append(dict(section=section, item=item, paper=paper, repo=value, ok=paper == value, source=source))


def main(out=ROOT / "paper" / "numbers.csv"):
    cfg, bnd, nz = load_config(), Y(ROOT / "configs/parameter_bounds.yaml"), Y(ROOT / "configs/noise_model.yaml")
    g, dop, mat = cfg["mosfet"]["geometry"], cfg["mosfet"]["doping"], cfg["material"]
    rc, ph, ab = J(S / "repeat_control.json"), J(S / "posthoc_stats.json"), J(S / "rq3_ablation.json")
    case = lambda lv, rho, m: next(c for c in rc["cases"] if c["level"] == lv and abs(c["rho"] - rho) < 1e-9 and c["model"] == m)
    base = case("nominal", 0.0, "gp"); st = base["sets"]

    # ------------------------------------------------------------ II. model and device (configs)
    src = "configs/baseline.yaml"
    check("II", "gate oxide (nm)", "50", f"{1e3 * g['tox_um']:.0f}", src)
    check("II", "P-well doping (cm^-3)", "1e17", f"{dop['N_pw']:.0e}".replace("e+", "e"), src)
    check("II", "JFET doping (cm^-3)", "2e16", f"{dop['N_jfet']:.0e}".replace("e+", "e"), src)
    check("II", "drift layer (um, cm^-3)", "10, 1e16", f"{g['t_drift_um']:g}, {dop['N_drift']:.0e}".replace("e+", "e"), src)
    check("II", "half-pitch (um)", "3.5", f"{g['x_pw_um'] + g['wjfet_um'] / 2:g}", src)
    check("II", "channel length (um)", "0.5", f"{g['x_pw_um'] - g['x_ns1_um']:g}", src)
    check("II", "surface-mobility depth lambda (nm)", "3", f"{1e3 * mat['surf_lambda_um']:g}", src)
    check("II", "mu_surf at 300 K (cm^2/Vs)", "20", f"{mat['mu_surf300']:g}", src)
    check("II", "gamma: baseline, variants", "+1; 0, -1", f"{mat['mu_surf_gamma']:+g}; " + ", ".join(
        f"{Y(ROOT / f'configs/variants/{v}.yaml')['material']['mu_surf_gamma']:g}" for v in ("gamma0", "gamma_m1")),
          "configs/baseline.yaml, configs/variants/gamma*.yaml")
    check("II", "Q_f (cm^-2)", "1e12", f"{cfg['interface']['qf_cm2']:.0e}".replace("e+", "e"), src)
    check("II", "r (Q_it,eff reduction at 423 K)", "0, 0.1, 0.3", "0, " + ", ".join(
        f"{Y(ROOT / f'configs/variants/{v}.yaml')['interface']['qit_T_reduction_423']:g}" for v in ("qitT10", "qitT30")),
          "configs/variants/qitT*.yaml")
    check("II", "max V_DS (V)", "5", f"{max(s[0] for s in cfg['bias']['vds_segments']):g}", src)
    check("II", "bias: transfer V_DS, output V_GS (V)", "0.1, 18", f"{cfg['bias']['vds_lin']:g}, {cfg['bias']['vgs_on']:g}", src)
    check("II", "transfer samples V_GS (V)", "4,5,6,7,8,10,12,14,16,18,20", ",".join(f"{v:g}" for v in cfg["extract"]["feature_vgs"]), src)
    v_ = bnd["variables"]
    check("II", "ranges W_JFET, N_pw", "+-20%, +-20%", ", ".join(f"+-{100 * (v_[k]['high'] - 1):.0f}%" for k in ("wjfet_scale", "npwell_scale")),
          "configs/parameter_bounds.yaml")
    check("II", "range Q_it,eff (1e12 cm^-2)", "-1.0 (-1.5~-0.5)", f"{v_['qit_eff_cm2']['nominal'] / 1e12:.1f} "
          f"({v_['qit_eff_cm2']['low'] / 1e12:.1f}~{v_['qit_eff_cm2']['high'] / 1e12:.1f})", "configs/parameter_bounds.yaml")
    nu = bnd["nuisance"]["mu_channel_scale"]
    check("II", "range s_mu", "0.8~1.2", f"{nu['low']:g}~{nu['high']:g}", "configs/parameter_bounds.yaml")
    pool_w = wide_table(pd.read_csv(R / "pool/runs.csv"))
    check("II", "features per temperature", "17", str(feature_set(pool_w, "S1").shape[1]), "results/pool/runs.csv")

    # ------------------------------------------------------------ II. validation
    g1, g2, g3 = (J(R / f"validation/{n}.json") for n in ("gate1_pn_diode", "gate2_moscap", "gate3_summary"))
    dev = max([abs(c["vbi_sim"] - c["vbi_ana"]) for c in g1["cases"]] + [abs(c["vfb_sim"] - c["vfb_ana"]) for c in g2["cases"]])
    check("II", "PN diode V_bi, MOS capacitor V_fb vs analytic (mV)", "< 5", "< 5" if 1e3 * dev < 5 else f"{1e3 * dev:.2f}",
          "results/validation/gate1_pn_diode.json, gate2_moscap.json")
    b3, b4 = (J(R / f"stage_a/runs/A_base_T{T}.json")["features"] for T in (300, 423))
    check("II", "V_th 300->423 K (V)", "3.765->3.530", f"{b3['vth_V']:.3f}->{b4['vth_V']:.3f}", "results/stage_a/runs/A_base_T*.json")
    check("II", "SS 300->423 K (mV/dec)", "112.5->155.7", f"{b3['ss_mV_dec']:.1f}->{b4['ss_mV_dec']:.1f}", "results/stage_a/runs/A_base_T*.json")
    check("II", "R_on,sp 300->423 K (mOhm cm^2)", "2.00->2.87", f"{b3['ron_mohm_cm2']:.2f}->{b4['ron_mohm_cm2']:.2f}", "results/stage_a/runs/A_base_T*.json")
    m = g3["mesh"]
    check("II", "mesh nodes standard, fine", "1.1e4, 2.36e4", f"{m['medium']['nodes'] / 1e4:.1f}e4, {m['fine']['nodes'] / 1e4:.2f}e4",
          "results/validation/gate3_summary.json")
    check("II", "standard vs fine mesh: V_th (mV), R_on,sp (%)", "0.07, 0.9", f"{1e3 * abs(g3['medium_vs_fine']['vth_V']):.2f}, "
          f"{100 * abs(g3['medium_vs_fine']['ron_mohm_cm2']):.1f}", "results/validation/gate3_summary.json")
    runs = {p.stem: J(p) for p in (R / "stage_a/runs").glob("A_*.json")}
    slope = 1.602176634e-19 * g["tox_um"] * 1e-4 / (3.9 * 8.8541878128e-14) * 1e12
    qd = max(abs(runs[f"A_qit_{lv}_T{T}"]["features"]["vth_V"] - runs[f"A_base_T{T}"]["features"]["vth_V"]
                 + slope * (runs[f"A_qit_{lv}_T{T}"]["qit_eff_cm2"] - runs[f"A_base_T{T}"]["qit_eff_cm2"]) / 1e12)
             for T in (300, 423) for lv in ("-20pct", "-10pct", "+10pct", "+20pct"))
    check("II", "V_th shift vs -q dQ_it/C_ox (mV)", "< 1", "< 1" if 1e3 * qd < 1 else f"{1e3 * qd:.2f}", "results/stage_a/runs/A_qit_*.json")

    # ------------------------------------------------------------ III. Table 1 (Stage A, +20 %)
    sa = pd.read_csv(R / "stage_a/stage_a_deltas.csv"); dv = J(R / "stage_a/stage_a_summary.json")["dvth_T"]
    d = lambda var, col: sa[(sa["var"] == var) & (sa.level == "+20pct")].set_index("T")[col]
    pair = lambda var, col, sc, fmt: f"{fmt(sc * d(var, col)[300])}/{fmt(sc * d(var, col)[423])}"
    i0 = lambda v: "0" if abs(v) < 0.5 else f"{v:+.0f}"
    s1d = lambda v: "0" if abs(v) < 0.05 else f"{v:+.1f}"
    src = "results/stage_a/stage_a_deltas.csv"
    for var, paper in (("wjfet", "0/0"), ("npwell", "+485/+474"), ("qit", "+464/+464"), ("mu", "-13/-13")):
        check("Table 1", f"dV_th (mV), {var}", paper, pair(var, "vth_V", 1e3, i0), src)
    for var, paper in (("wjfet", "0/0"), ("npwell", "+3.4/+3.8"), ("qit", "0/0"), ("mu", "-0.2/-0.1")):
        check("Table 1", f"SS (%), {var}", paper, pair(var, "ss_mV_dec", 100, s1d), src)
    for var, paper in (("wjfet", "+3.1/+4.5"), ("npwell", "-3.0/-1.7"), ("qit", "-1.3/-0.6"), ("mu", "+7.8/+3.6")):
        check("Table 1", f"I_on (%), {var}", paper, pair(var, "ion_A_per_cm", 100, s1d), src)
    for var, paper in (("wjfet", "0.0"), ("npwell", "-10.9"), ("qit", "0.0"), ("mu", "-0.4")):
        check("Table 1", f"d[V_th(423)-V_th(300)] (mV), {var}", paper, sgn1(1e3 * (dv[f"A_{var}_+20pct"] - dv["A_base"])),
              "results/stage_a/stage_a_summary.json")
    ion = lambda var, T: d(var, "ion_A_per_cm")[T]
    check("III", "I_on sensitivity ratio W_JFET/s_mu, 300->423 K", "0.40->1.26",
          f"{ion('wjfet', 300) / ion('mu', 300):.2f}->{ion('wjfet', 423) / ion('mu', 423):.2f}", src)

    # ------------------------------------------------------------ III. design, noise, models, policies
    test_w = wide_table(pd.read_csv(R / "test/runs.csv"))
    nrun = lambda p: int(pd.read_csv(p).converged.astype(str).str.lower().eq("true").sum())
    check("III", "pool / test devices", "512 / 128", f"{len(pool_w)} / {len(test_w)}", "results/pool, results/test")
    check("III", "DEVSIM runs, baseline physics (all converged)", "1280", str(nrun(R / "pool/runs.csv") + nrun(R / "test/runs.csv")),
          "results/{pool,test}/runs.csv")
    check("III", "DEVSIM runs, 423 K physics variants (all converged)", "2560", str(sum(
        nrun(R / f"{s}_{v}/runs.csv") for s in ("pool", "test") for v in ("gamma0", "gamma_m1", "qitT10", "qitT30"))),
          "results/{pool,test}_<variant>/runs.csv")
    rel = nz["relative"]
    check("III", "noise: V_th (mV); SS, g_m, transfer (%); currents, R (%)", "10; 2, 2, 2; 1, 1, 1",
          f"{1e3 * nz['absolute']['vth_V']:g}; {100 * rel['ss_mV_dec']:g}, {100 * rel['gm_max_S_per_cm']:g}, {100 * nz['logid_samples']:g}; "
          f"{100 * rel['ion_A_per_cm']:g}, {100 * rel['ron_mohm_cm2']:g}, {100 * rel['id_vds_req_A_per_cm']:g}", "configs/noise_model.yaml")
    check("III", "2x noise level", "2", f"{nz['levels']['high'] / nz['levels']['nominal']:g}", "configs/noise_model.yaml")
    gp = make_model("gp")[-1]
    check("III", "GP kernel", "Constant*RBF+White", "Constant*RBF+White" if repr(gp.kernel).startswith("1**2 * RBF") and "WhiteKernel" in repr(gp.kernel)
          else repr(gp.kernel), "src/sicsim/analysis.py")
    check("III", "RF trees", "300", str(make_model("rf").n_estimators), "src/sicsim/analysis.py")
    check("III", "Ridge with cross-validated alpha", "RidgeCV", type(make_model("ridge")[-1]).__name__, "src/sicsim/analysis.py")
    lo = np.array([v_[k]["low"] for k in VARS]); hi_ = np.array([v_[k]["high"] for k in VARS])
    mid = np.abs(test_w[VARS].values - (lo + hi_) / 2) / (hi_ - lo)
    check("III", "MAE_norm of the range-midpoint guess", "0.25", f2(mid.mean()), "results/test/runs.csv")
    check("III", "extra noise realisations (secondary)", "4", str(len(rc["replicates"])), "results/summary/repeat_control.json")
    check("III", "noise correlation rho", "0, 0.5, 0.9", ", ".join(f"{r:g}" for r in rc["meta"]["rhos"]), "results/summary/repeat_control.json")
    rob = J(S / "robustness.json")
    check("III", "series resistance (mOhm cm^2)", "0.1~0.3", "~".join(f"{x:g}" for x in rob["rho_range_mohm_cm2"]), "results/summary/robustness.json")
    metas = {k: J(R / p / "meta.json") for k, p in (("A0", "al_live/nominal"), ("A", "al_ablation/named/nominal"),
                                                    ("B", "al_ablation/anon/nominal"), ("C", "al_ablation/shuffled/nominal"),
                                                    ("numeric", "al_ablation/numeric/nominal"))}
    mm = metas["numeric"]
    check("III", "selection: initial points, batch x rounds, seeds", "60, 10x6, 10", f"{mm['n_init']}, {mm['batch']}x{mm['rounds']}, {mm['seeds']}",
          "results/al_ablation/numeric/nominal/meta.json")
    tf = inspect.signature(diverse_top).parameters["top_factor"].default
    check("III", "uncertainty policy: candidates scanned (top_factor x batch)", "30", str(tf * mm["batch"]), "src/sicsim/alsim.py")
    check("III", "LLM: candidates shown", "20", str(inspect.signature(run_policy).parameters["top_n"].default), "src/sicsim/alsim.py")
    check("III", "LLM model (A0, A, B, C)", "claude-sonnet-5-5", ",".join(sorted({metas[k]["llm_model"] for k in ("A0", "A", "B", "C")})),
          "results/al_*/**/meta.json")
    check("III", "equivalence margin", "0.0025", f4(ab["meta"]["sesoi"]), "results/summary/rq3_ablation.json")

    # ------------------------------------------------------------ IV.1 RQ1 (GP, nominal noise, rho = 0)
    src = "results/summary/repeat_control.json"
    check("IV.1", "MAE_norm S1, S1x2, S2", "0.112, 0.086, 0.072", ", ".join(f3(st[k]["mean"]) for k in ("S1", "S1x2", "S2")), src)
    c = base["contrasts"]["S2-S1x2"]["mean"]
    check("IV.1", "S2-S1x2 [95% CI]", "-0.014 [-0.024, -0.006]", f"{f3(c['delta'])} [{f3(c['ci'][0])}, {f3(c['ci'][1])}]", src)
    check("IV.1", "W_JFET S1x2->S2", "0.079->0.050", f"{f3(st['S1x2']['wjfet_scale'])}->{f3(st['S2']['wjfet_scale'])}", src)
    share = lambda s: (s["S1"]["mean"] - s["S1x2"]["mean"]) / (s["S1"]["mean"] - s["S2"]["mean"])
    frac = lambda x: "2/3" if 0.6 < x < 0.72 else ("1/2" if 0.4 < x < 0.6 else f"{x:.2f}")
    check("IV.1", "share of the 423 K gain explained by averaging", "2/3", frac(share(st)), src)
    check("IV.1", "same, 2x noise", "1/2", frac(share(case("high", 0.0, "gp")["sets"])), src)
    ns = []
    for lv, mdl, con in (("nominal", "gp", "S2-S1x2"), ("nominal", "gp", "S2-S1x2cat"), ("high", "gp", "S2-S1x2"), ("nominal", "ridge", "S2-S1x2")):
        cc = case(lv, 0.0, mdl)["contrasts"][con]
        ns.append(all(cc[v]["ci"][0] < 0 < cc[v]["ci"][1] for v in VARS[1:]) and cc["wjfet_scale"]["ci"][1] < 0)
    check("IV.1", "W_JFET significant, N_pw/Q_it,eff not (34-dim, 2x noise, Ridge)", "yes", yes(all(ns)), src)
    reps = rc["replicates"]
    rng = lambda k: f"{f3(min([r['sets'][k]['mean'] for r in reps] + [st[k]['mean']]))}~{f3(max([r['sets'][k]['mean'] for r in reps] + [st[k]['mean']]))}"
    check("IV.1", "other noise realisations: S1x2, S2", "0.086~0.092, 0.069~0.078", f"{rng('S1x2')}, {rng('S2')}", src)
    same = all(r["contrasts"]["S2-S1x2"]["wjfet_scale"]["ci"][1] < 0 and all(
        r["contrasts"]["S2-S1x2"][v]["ci"][0] < 0 < r["contrasts"]["S2-S1x2"][v]["ci"][1] for v in VARS[1:]) for r in reps)
    check("IV.1", "other noise realisations: same pattern", "yes", yes(same), src)
    eb = ph["part2"]["120"]
    check("IV.1", "equal budget 120 runs: S2 (60 pts), S1, S1x2 (120 pts)", "0.085, 0.127, 0.096",
          ", ".join(f3(eb[k]["mean"]) for k in ("S2", "S1", "S1x2")), "results/summary/posthoc_stats.json")
    check("IV.1", "N_pw: V_th temperature shift per +20% (mV)", "-10.9", sgn1(1e3 * (dv["A_npwell_+20pct"] - dv["A_base"])),
          "results/stage_a/stage_a_summary.json")
    check("IV.1", "noise of V_th(423)-V_th(300) (mV)", "14", f"{1e3 * np.sqrt(2) * nz['absolute']['vth_V']:.0f}", "configs/noise_model.yaml")
    nf = J(R / "al/none/rq1_feature_sets.json")["S1_gp"]["mean_mae_norm"]
    check("IV.1", "noise-free S1 (GP) below 0.001", "yes", yes(nf < 0.001), "results/al/none/rq1_feature_sets.json")
    crb = rc["crb"]["S2_over_S1"]["0.0"]
    check("IV.1", "local CRB ratio S2/S1: W_JFET, N_pw, Q_it,eff", "0.38, 0.59, 0.58", ", ".join(f2(crb[v]) for v in VARS), src)
    r9 = case("nominal", 0.9, "gp")["sets"]
    check("IV.1", "rho = 0.9: S1x2, S2, S3", "0.110, 0.075, 0.064", ", ".join(f3(r9[k]["mean"]) for k in ("S1x2", "S2", "S3")), src)
    check("Fig. 3", "W_JFET S2 vs S1x2 (%)", "-36", f"{100 * (base['contrasts']['S2-S1x2']['wjfet_scale']['ratio'] - 1):.0f}", src)

    # ------------------------------------------------------------ IV.2 / Table 2 (423 K physics)
    sc, ref = ph["part1"]["scenarios"], ph["part1"]["reference"]["S1x2"]["mean"]
    cell = lambda rec: f"{f3(rec['mean'])} ({100 * (rec['mean'] / ref - 1):+.0f}%)" + ("*" if rec["vs_S1x2"]["mean"]["ci"][1] < 0 else "")
    src = "results/summary/posthoc_stats.json"
    t2 = {"base": ("0.072 (-17%)*", None, "0.082 (-5%)"), "gamma0": ("0.073 (-15%)*", "0.537", "0.083 (-3%)"),
          "gamma_m1": ("0.076 (-12%)*", "0.928", "0.088 (+1%)"), "qitT10": ("0.057 (-34%)*", "0.084", "0.079 (-8%)"),
          "qitT30": ("0.033 (-62%)*", "0.132", "0.080 (-7%)")}
    for k, (o, mis, mix) in t2.items():
        check("Table 2", f"{k}: oracle", o, cell(sc[k]["matched"]), src)
        if mis:
            check("Table 2", f"{k}: mismatch", mis, f3(sc[k]["nominal"]["mean"]), src)
        check("Table 2", f"{k}: mixture", mix, cell(sc[k]["mixed"]), src)
    sr = rc["series_r"]["sets"]
    check("Table 2", "series resistance: S1, S1x2, S2", "0.378, 0.405, 0.261", ", ".join(f3(sr[k]["mean"]) for k in ("S1", "S1x2", "S2")),
          "results/summary/repeat_control.json")
    check("Abstract", "mismatch gamma = 0, -1", "0.54, 0.93", f"{f2(sc['gamma0']['nominal']['mean'])}, {f2(sc['gamma_m1']['nominal']['mean'])}", src)
    mx = [sc[k]["mixed"]["mean"] for k in t2]
    check("IV.2", "mixture range; none below S1x2", "0.079~0.088; yes", f"{f3(min(mx))}~{f3(max(mx))}; " + yes(
        all(sc[k]["mixed"]["vs_S1x2"]["mean"]["ci"][1] > 0 for k in t2)), src)
    t423 = pd.read_csv(R / "test/runs.csv"); t423 = t423[t423.temperature_K == 423].set_index("candidate_id")
    shift = {}
    for v in ("gamma0", "gamma_m1"):
        tv = pd.read_csv(R / f"test_{v}/runs.csv").set_index("candidate_id").loc[t423.index]
        shift[v] = (np.median(1e3 * (tv.vth_V - t423.vth_V)), np.median(100 * (1 - tv.gm_max_S_per_cm / t423.gm_max_S_per_cm)))
    check("IV.2", "423 K, gamma = 0, -1: g_m,max decrease (%)", "20, 38", f"{shift['gamma0'][1]:.0f}, {shift['gamma_m1'][1]:.0f}",
          "results/test/runs.csv, results/test_gamma*/runs.csv (median of 128)")
    check("IV.2", "423 K, gamma = 0, -1: V_th shift (mV)", "+27, +56", f"{shift['gamma0'][0]:+.0f}, {shift['gamma_m1'][0]:+.0f}",
          "results/test/runs.csv, results/test_gamma*/runs.csv (median of 128)")

    # ------------------------------------------------------------ IV.3 / Table 3 (selection, S2, RF, nominal, 10 seeds)
    fin, beh, p3 = ab["final"], ab["behaviour"], ph["part3"]
    src = "results/summary/rq3_ablation.json"
    for k, paper in (("random", "0.1263"), ("sobol", "0.1240"), ("U", "0.1238"), ("A0", "0.1250"), ("A", "0.1236"),
                     ("B", "0.1242"), ("C", "0.1257"), ("D", "0.1259")):
        check("Table 3", f"final MAE_norm, {k}", paper, f4(fin[k]["mean"]), src)
    k3 = lambda x: f"{1e3 * x:+.1f}"
    flip = lambda c: f"{k3(-c['delta'])} [{k3(-c['boot95'][1])}, {k3(-c['boot95'][0])}]"
    keep = lambda c: f"{k3(c['delta'])} [{k3(c['boot95'][0])}, {k3(c['boot95'][1])}]"
    check("Table 3", "random vs uncertainty (x1e-3)", "+2.5 [+0.9, +3.9]", flip(p3["final:U-random"]), "results/summary/posthoc_stats.json")
    check("Table 3", "Sobol vs uncertainty (x1e-3)", "+0.2 [-0.9, +1.3]", flip(p3["final:U-sobol"]), "results/summary/posthoc_stats.json")
    for k, paper in (("A0", "+1.2 [-0.8, +3.6]"), ("A", "-0.2 [-1.7, +1.3]"), ("B", "+0.4 [-1.6, +3.1]"), ("C", "+1.9 [-0.7, +4.8]"),
                     ("D", "+2.1 [-0.3, +5.0]")):
        check("Table 3", f"{k} vs uncertainty (x1e-3)", paper, keep(p3[f"final:{k}-U"]), "results/summary/posthoc_stats.json")
    for k, paper in (("A0", "0.63/0.63"), ("A", "0.62/0.62"), ("B", "0.55/0.55"), ("C", "0.49/0.64")):
        check("Table 3", f"top-10 overlap actual/displayed, {k}", paper, f"{beh[k]['overlap_true']:.2f}/{beh[k]['overlap_shown']:.2f}", src)
    u = p3["final:U-random"]
    check("IV.3", "uncertainty - random [95% CI]", "-0.0025 [-0.0039, -0.0009]", f"{f4(u['delta'])} [{f4(u['boot95'][0])}, {f4(u['boot95'][1])}]",
          "results/summary/posthoc_stats.json")
    sv = {(int(r.n_init), r.policy): r.saving_pct for r in pd.read_csv(S / "al_ninit_summary.csv").itertuples()}
    check("IV.3", "samples saved vs random: n_init 60; 30, 90 (%)", "12; 20, 15",
          f"{sv[(60, 'uncertainty')]:.0f}; {sv[(30, 'uncertainty')]:.0f}, {sv[(90, 'uncertainty')]:.0f}", "results/summary/al_ninit_summary.csv")
    usob = p3["final:U-sobol"]["boot95"]
    check("IV.3", "uncertainty vs Sobol: CI includes 0", "yes", yes(usob[0] < 0 < usob[1]), "results/summary/posthoc_stats.json")
    rq2 = (S / "rq2.md").read_text(encoding="utf-8"); hi_sec = rq2[rq2.index("noise = high"):]
    cis = [tuple(map(float, re.findall(r"[-+]\d*\.\d+", m)[1:3])) for m in re.findall(r"\| (?:sobol|uncertainty) \|[^|]+\|([^|]+)\|", hi_sec)]
    check("IV.3", "2x noise: uncertainty and Sobol vs random CIs include 0", "yes", yes(len(cis) == 2 and all(a < 0 < b for a, b in cis)),
          "results/summary/rq2.md")
    best_rf = min(fin[k]["mean"] for k in fin)
    check("IV.3", "GP on 60 random points < every RF policy at 120", "0.085; yes", f"{f3(eb['S2']['mean'])}; {yes(eb['S2']['mean'] < best_rf)}",
          "results/summary/posthoc_stats.json, rq3_ablation.json")
    check("IV.3", "LLM calls validated", "238/240", f"{sum(beh[k]['accepted'] for k in ('A0', 'A', 'B', 'C'))}/"
          f"{sum(beh[k]['calls'] for k in ('A0', 'A', 'B', 'C'))}", src)
    eq = {k: p3[f"final:{k}-U"]["equivalent_boot90"] for k in ("A0", "A", "B", "C", "D")}
    check("IV.3", "within +-0.0025 of uncertainty: only A", "yes", yes(eq["A"] and not any(eq[k] for k in ("A0", "B", "C", "D"))),
          "results/summary/posthoc_stats.json")
    mde = [p3[f"final:{k}-U"]["mde80"] for k in ("A", "B", "C", "D", "A0")]
    check("IV.3", "minimum detectable difference", "0.0025~0.0047", f"{f4(min(mde))}~{f4(max(mde))}", "results/summary/posthoc_stats.json")
    check("IV.3", "C: overlap with displayed / actual top-10 (%)", "64, 49", f"{100 * beh['C']['overlap_shown']:.0f}, {100 * beh['C']['overlap_true']:.0f}", src)
    check("IV.3", "C: widened toward the displayed worst target", "51/59", f"{beh['C']['widen_displayed']}/{beh['C']['n_stats']}", src)
    check("IV.3", "B, A: widened toward the worst target (of 60)", "49, 47", f"{beh['B']['widen_displayed']}, {beh['A']['widen_displayed']}", src)

    # ------------------------------------------------------------ report
    out = Path(out); out.parent.mkdir(parents=True, exist_ok=True)
    with open(out, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["section", "item", "paper", "repo", "ok", "source"])
        w.writeheader(); w.writerows({k: r[k] for k in w.fieldnames} for r in ROWS)
    bad = [r for r in ROWS if not r["ok"]]
    for r in ROWS:
        tag = "ok " if r["ok"] else "XX "
        print(f"{tag}{r['section']:8s} {r['item'][:58]:58s} paper={r['paper']:30s} repo={r['repo']}")
    print(f"\n{len(ROWS)} checks, {len(bad)} mismatches -> {out.relative_to(ROOT) if out.is_relative_to(ROOT) else out}")
    return 1 if bad else 0


if __name__ == "__main__":
    a = sys.argv[1:]
    sys.exit(main(a[a.index("--out") + 1]) if "--out" in a else main())
