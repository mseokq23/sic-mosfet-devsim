// Manuscript V4.9 builder (V4.8 + reviewer feedback: retrospective pool-based wording, CI of the temperature-specific gain in the
// abstract, mixed-physics wording, LLM contribution limits, novelty paragraph, title 'TCAD Sample Selection'; see docs/V49_CHANGES.md).
//   NODE_PATH=<global node_modules> node build_v49.js proc    -> 5-page proceedings version (IEIE conference layout, author block)
//   NODE_PATH=<global node_modules> node build_v49.js review  -> 4-page written-review version (IEIE journal layout, anonymous)
// Numbers: docs/V47_RESULTS.md, results/summary/v47_*.md, results/summary/v48_extra_stats.md (scripts/v48_extra_stats.py).
// Figures: scripts/make_v47_figures.py (fig3_rq1_v47, fig3_rq1_robust_v47, fig4_policies_v47); OUT=<file> sets the output path.
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, BorderStyle, SectionType, TabStopType, Tab,
} = require("docx");

const MODE = process.argv[2] || "proc";
const REVIEW = MODE === "review";
const FIGDIR = process.env.FIGDIR || (fs.existsSync(path.join(__dirname, "../figures")) ? path.join(__dirname, "../figures") : __dirname);
const LATIN = "Times New Roman", KOR = "바탕";
const FONT = { ascii: LATIN, hAnsi: LATIN, cs: LATIN, eastAsia: KOR };
const COLW = 4620;                       // one column (A4, 20 mm side margins, 7 mm gap), twips
const FULLW = 11906 - 2 * 1134;          // text width of the single-column header, twips

// ------------------------------------------------------------------ citations (numbered by first appearance)
const ORDER = [];
function cite(text) {
  return text.replace(/\[\[([a-z0-9_,\s]+)\]\]/g, (m, ks) => {
    const ns = ks.split(",").map((k) => {
      k = k.trim();
      if (!REFDB[k]) throw new Error("unknown ref " + k);
      if (!ORDER.includes(k)) ORDER.push(k);
      return ORDER.indexOf(k) + 1;
    });
    const s = compress(ns);
    return REVIEW ? `^{[${s}]}` : `[${s}]`;
  });
}
function compress(ns) {
  ns = [...new Set(ns)].sort((a, b) => a - b);
  const out = []; let i = 0;
  while (i < ns.length) {
    let j = i;
    while (j + 1 < ns.length && ns[j + 1] === ns[j] + 1) j++;
    out.push(j - i >= 2 ? `${ns[i]}–${ns[j]}` : ns.slice(i, j + 1).join(","));
    i = j + 1;
  }
  return out.join(",");
}

// ------------------------------------------------------------------ mini markup: _{sub} ^{sup} **bold** ~~italic~~
function runs(text, o = {}) {
  text = cite(text);
  const out = []; const re = /(_\{[^}]*\}|\^\{[^}]*\}|\*\*[^*]+\*\*|~~[^~]+~~)/g; let last = 0, m;
  const base = { font: FONT, ...o };
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("_{")) out.push(new TextRun({ text: t.slice(2, -1), subScript: true, ...base }));
    else if (t.startsWith("^{")) out.push(new TextRun({ text: t.slice(2, -1), superScript: true, ...base }));
    else if (t.startsWith("**")) out.push(new TextRun({ text: t.slice(2, -2), ...base, bold: true }));
    else out.push(new TextRun({ text: t.slice(2, -2), ...base, italics: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const SP = { line: 250, before: 0, after: 0 };
const body = (t) => new Paragraph({ children: runs(t, { size: 18 }), alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 180 }, spacing: SP });
const h1 = (t) => new Paragraph({ keepNext: true, children: runs(t, { size: 19, bold: true }), alignment: AlignmentType.CENTER, spacing: { before: REVIEW ? 110 : 140, after: 50, line: 250 } });
const h2 = (t) => new Paragraph({ keepNext: true, children: runs(t, { size: 18, bold: true }), spacing: { before: 60, after: 25, line: 250 } });
const center = (t, size, extra = {}) => new Paragraph({ children: runs(t, { size, ...extra }), alignment: AlignmentType.CENTER, spacing: { line: 240, before: 0, after: 0 } });

function pngSize(p) { const b = fs.readFileSync(p); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function figure(file, widthPx, capKR, capEN) {
  const p = path.join(FIGDIR, file);
  const [w, h] = pngSize(p);
  const out = [new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 80, after: 25 },
    children: [new ImageRun({ type: "png", data: fs.readFileSync(p), transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] })];
  out.push(new Paragraph({ keepNext: !!capEN, alignment: AlignmentType.JUSTIFIED, spacing: { after: capEN ? 0 : 80, line: 210 }, children: runs(capKR, { size: 15 }) }));
  if (capEN) out.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 80, line: 210 }, children: runs(capEN, { size: 15 }) }));
  return out;
}
function equation(t, num) {
  return new Paragraph({ tabStops: [{ type: TabStopType.CENTER, position: COLW / 2 }, { type: TabStopType.RIGHT, position: COLW }],
    spacing: { before: 40, after: 40, line: 250 }, children: [new TextRun({ children: [new Tab()] }), ...runs(t, { size: 18 }), new TextRun({ children: [new Tab()] }), ...runs(`(${num})`, { size: 18 })] });
}
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const LINE = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: "000000" });
function cell(t, w, opts = {}) {
  return new TableCell({ width: { size: w, type: WidthType.DXA }, margins: { top: 20, bottom: 20, left: 35, right: 35 },
    borders: { top: opts.top || NONE, bottom: opts.bottom || NONE, left: NONE, right: NONE },
    children: [new Paragraph({ keepNext: !!opts.keepNext, keepLines: true, alignment: opts.left ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { line: 210 }, children: runs(t, { size: 13, bold: !!opts.bold }) })] });
}
function table(widths, rows) {
  return new Table({
    width: { size: widths.reduce((a, b) => a + b), type: WidthType.DXA }, columnWidths: widths,
    borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: rows.map((r, i) => new TableRow({ cantSplit: true, children: r.map((t, j) => cell(t, widths[j], {
      left: j === 0, bold: i === 0, top: i === 0 ? LINE(8) : undefined, keepNext: true,
      bottom: i === 0 ? LINE(4) : (i === rows.length - 1 ? LINE(8) : undefined) })) })),
  });
}
const capT = (t) => new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 80, after: 0, line: 210 }, children: runs(t, { size: 15 }) });
const note = (t) => new Paragraph({ spacing: { before: 15, after: 80, line: 200 }, children: runs(t, { size: 13 }) });

// ------------------------------------------------------------------ references (~~italic~~ = journal/book name)
const REFDB = {
  baliga: "B. J. Baliga, ~~Fundamentals of Power Semiconductor Devices~~, 2nd ed., Springer, 2019.",
  kimoto: "T. Kimoto and J. A. Cooper, ~~Fundamentals of Silicon Carbide Technology~~, Wiley-IEEE Press, 2014.",
  boiko: "D. A. Boiko, R. MacKnight, B. Kline, and G. Gomes, “Autonomous chemical research with large language models,” ~~Nature~~, vol. 624, pp. 570–578, Dec. 2023.",
  muting: "J. Müting, P. Natzke, A. Tsibizov, and U. Grossner, “Influence of process variations on the electrical performance of SiC power MOSFETs,” ~~IEEE Trans. Electron Devices~~, vol. 68, no. 1, pp. 230–235, Jan. 2021.",
  ha: "J. Ha, G. Lee, and J. Kim, “Machine learning approach for characteristics prediction of 4H-silicon carbide NMOSFET by process conditions,” in ~~Proc. IEEE Region 10 Symp. (TENSYMP)~~, 2021, doi: 10.1109/TENSYMP52854.2021.9550872.",
  ha2022: REVIEW
    ? "J. Ha et al., “Deep learning approach for characteristics prediction of nanowire FETs by process condition,” ~~J. Inst. Electron. Inf. Eng.~~, vol. 59, no. 12, pp. 29–37, Dec. 2022."
    : "하종현, 이경엽, 서민기, 방민지, 김태형, 김정식, “심층신경망을 이용한 Nanowire FETs의 공정 조건 특성 예측,” ~~전자공학회논문지~~, 제59권, 제12호, 29–37쪽, 2022년 12월.",
  agentic: "G. Fan, T. Ma, X. Sun, X. Wang, K. L. Low, and L. Shao, “AgenticTCAD: A LLM-based multi-agent framework for automated TCAD code generation and device optimization,” in ~~Proc. Design, Automation and Test in Europe Conf. (DATE)~~, 2026, doi: 10.23919/DATE69613.2026.11539536.",
  devsim: "J. E. Sanchez, “DEVSIM: A TCAD semiconductor device simulator,” ~~J. Open Source Softw.~~, vol. 7, no. 70, p. 3898, 2022.",
  sg: "D. L. Scharfetter and H. K. Gummel, “Large-signal analysis of a silicon Read diode oscillator,” ~~IEEE Trans. Electron Devices~~, vol. 16, no. 1, pp. 64–77, Jan. 1969.",
  ikeda: "M. Ikeda, H. Matsunami, and T. Tanaka, “Site effect on the impurity levels in 4H, 6H, and 15R SiC,” ~~Phys. Rev. B~~, vol. 22, no. 6, pp. 2842–2854, Sep. 1980.",
  roschke: "M. Roschke and F. Schwierz, “Electron mobility models for 4H, 6H, and 3C SiC,” ~~IEEE Trans. Electron Devices~~, vol. 48, no. 7, pp. 1442–1447, Jul. 2001.",
  burin: "J. Burin, P. Gaggl, S. Waid, A. Gsponer, and T. Bergauer, “TCAD parameters for 4H-SiC: A review,” arXiv:2410.06798v8, Dec. 2025.",
  cree: "Cree, Inc., ~~C2M0080120D Silicon Carbide Power MOSFET Data Sheet~~, Rev. D, Sep. 2019.",
  das: "S. Das, Y. Zheng, A. Ahyi, M. A. Kuroda, and S. Dhar, “Study of carrier mobilities in 4H-SiC MOSFETs using Hall analysis,” ~~Materials~~, vol. 15, no. 19, Art. no. 6736, 2022.",
  yu: "S. Yu, M. H. White, and A. K. Agarwal, “Experimental determination of interface trap density and fixed positive oxide charge in commercial 4H-SiC power MOSFETs,” ~~IEEE Access~~, vol. 9, pp. 149118–149124, 2021.",
  keysight: "Keysight Technologies, ~~B1505A Power Device Analyzer/Curve Tracer~~, Data Sheet 5990-3853EN, Feb. 2025.",
  gp: "C. E. Rasmussen and C. K. I. Williams, ~~Gaussian Processes for Machine Learning~~, MIT Press, 2006.",
  settles: "B. Settles, “Active learning literature survey,” Comput. Sci. Tech. Rep. 1648, Univ. of Wisconsin–Madison, 2009.",
  sobol: "I. M. Sobol’, “On the distribution of points in a cube and the approximate evaluation of integrals,” ~~USSR Comput. Math. Math. Phys.~~, vol. 7, no. 4, pp. 86–112, 1967.",
  anthropic: "Anthropic, “Structured outputs,” Claude Platform Documentation, https://platform.claude.com/docs/en/build-with-claude/structured-outputs (accessed Oct. 2026).",
  repo: "M. Lee, “sic-mosfet-devsim: simulation code, configurations and results of this study,” GitHub repository, https://github.com/mseokq23/sic-mosfet-devsim (results: commit 90134a2), 2026.",
  stark: "R. Stark, A. Tsibizov, S. Race, T. Ziemann, I. Kovacevic-Badstuebner, and U. Grossner, “Temperature dependence of the channel and drift resistance of SiC power MOSFETs extracted from I-V and C-V measurements,” ~~Mater. Sci. Forum~~, vol. 1092, pp. 165–170, Jun. 2023.",
  mehta: "K. Mehta, S. S. Raju, M. Xiao, B. Wang, Y. Zhang, and H. Y. Wong, “Improvement of TCAD augmented machine learning using autoencoder for semiconductor variation identification and inverse design,” ~~IEEE Access~~, vol. 8, pp. 143519–143529, 2020.",
  ong: "E. K. J. Ong, L. M. L. Nguyen, M. Eng, Y. Zhang, and H. Y. Wong, “Ga_{2}O_{3} TCAD mobility parameter calibration using simulation augmented machine learning with physics-informed neural network,” ~~IEEE Trans. Electron Devices~~, vol. 73, no. 2, pp. 775–781, Feb. 2026.",
  gupta: "R. Gupta, J. Hartford, and B. Liu, “LLMs for Bayesian optimization in scientific domains: Are we there yet?,” in ~~Findings Assoc. Comput. Linguist.: EMNLP 2025~~, pp. 15482–15510, 2025.",
};

const titleKR = "DEVSIM 기반 4H-SiC 평판형 MOSFET 공정 결과 파라미터의 다중 온도 역추정과 LLM 보조 TCAD 표본 선택 평가";
const titleEN = "Multi-Temperature Inverse Estimation of Process-Outcome Parameters and Evaluation of LLM-Assisted TCAD Sample Selection for 4H-SiC Planar MOSFETs Using DEVSIM";
const ABS_EN = "Using DC characteristics of a 4H-SiC planar MOSFET simulated with DEVSIM at 300 K and 423 K, we estimate three latent process-outcome parameters (JFET width, P-well doping and effective interface charge) with a Gaussian-process model under assumed measurement noise. Adding the 423 K features lowered the normalized error from 0.112 to 0.072, but measuring the 300 K features twice already gave 0.086, so about two thirds of the gain came from the extra measurement. The temperature-specific remainder (−0.014 vs. the repeated measurement, 95% CI −0.024 to −0.006) was concentrated in the JFET width and persisted under correlated measurement noise and at an equal simulation budget. It was clear only when the high-temperature physics was known: a wrong channel-mobility temperature exponent raised the error to 0.54 and 0.93, above the no-information level of 0.25, and training that covered all five physics assumptions avoided this failure but showed no statistically established gain over the repeated measurement. In a retrospective pool-based evaluation, uncertainty sampling needed 12–20% fewer simulations than random sampling, but a Sobol sequence performed comparably. An LLM-assisted selector passed structured-output validation in 238 of 240 calls and followed the numbers it was given, as shuffled inputs redirected its choices; with 10 seeds, however, it showed no advantage over uncertainty sampling.";
const ABS_EN_REVIEW = "From DC characteristics of a 4H-SiC planar MOSFET simulated with DEVSIM at 300 K and 423 K, we estimate the JFET width, P-well doping and effective interface charge with a Gaussian-process model under assumed measurement noise. Adding the 423 K features lowered the normalized error from 0.112 to 0.072, but measuring the 300 K features twice gave 0.086, so about two thirds of the gain came from the extra measurement. The temperature-specific remainder (−0.014 vs. the repeated measurement, 95% CI −0.024 to −0.006) was concentrated in the JFET width and persisted under correlated measurement noise and at an equal simulation budget. It was clear only when the high-temperature physics was known: a wrong channel-mobility temperature exponent raised the error to 0.54 and 0.93, and training that covered all five physics assumptions avoided this failure but showed no statistically established gain over the repeated measurement. In a retrospective pool-based evaluation, uncertainty sampling needed 12–20% fewer simulations than random sampling, comparable to a Sobol sequence. An LLM-assisted selector followed the numbers it was shown, but with 10 seeds it showed no advantage over uncertainty sampling.";
const ABS_KR = "DEVSIM으로 계산한 4H-SiC 평판형 MOSFET의 300 K·423 K DC 특성에서 JFET 폭, P-well 도핑, 유효 계면전하를 가우시안 과정으로 역추정하였다. 측정 잡음을 넣었을 때 423 K 특징을 더하면 정규화 오차가 0.112에서 0.072로 줄었다. 그러나 300 K를 두 번 측정해도 0.086이어서, 이득의 약 2/3는 측정 횟수에서 나왔다. 나머지 온도 고유 이득(반복 측정 대비 −0.014, 95% CI −0.024~−0.006)은 JFET 폭에 집중되었고, 측정 간 잡음 상관과 같은 시뮬레이션 예산에서도 유지되었다. 다만 이 이득은 고온 물리를 알 때만 뚜렷하였다. 채널 이동도 온도지수를 틀리게 가정하면 오차가 0.54, 0.93으로 커졌고, 다섯 가정을 모두 포함해 학습하면 이 실패는 피했지만 반복 측정보다 낫다는 통계적 근거는 없었다. 회고적 풀 평가에서 불확실도 선택은 무작위보다 시뮬레이션을 12~20% 줄였으나 Sobol 순서도 비슷하였다. LLM 보조 선택은 제공된 수치를 따랐지만, 시드 10개에서 불확실도 선택보다 나은 결과는 확인되지 않았다.";

// ------------------------------------------------------------------ tables
const T1_KR = [
  ["특징 (+20%)", "W_{JFET}", "N_{pw}", "Q_{it,eff}", "s_{μ}(교란)"],
  ["**기준값(범위)**", "2.4 µm (±20%)", "1×10^{17} (±20%)", "−1.0×10^{12} (−1.5~−0.5)", "1 (0.8~1.2)"],
  ["ΔV_{th} (mV)", "0/0", "+485/+474", "+464/+464", "−13/−13"],
  ["SS (%)", "0/0", "+3.4/+3.8", "0/0", "−0.2/−0.1"],
  ["g_{m,max} (%)", "+0.6/+1.2", "−4.7/−5.1", "−1.2/−0.6", "+16.2/+11.8"],
  ["I_{on} (%)", "+3.1/+4.5", "−3.0/−1.7", "−1.3/−0.6", "+7.8/+3.6"],
  ["R_{on,sp} (%)", "−3.1/−4.3", "+3.1/+1.7", "+1.3/+0.7", "−7.3/−3.5"],
  ["I_{D}(2 V) (%)", "+3.3/+4.7", "−3.4/−1.9", "−1.4/−0.7", "+8.3/+3.8"],
  ["ΔV_{th,T} (mV)*", "0.0", "−10.9", "0.0", "−0.4"],
];
const T1_EN = T1_KR.map((r, i) => (i === 0 ? ["Feature (+20%)", "W_{JFET}", "N_{pw}", "Q_{it,eff}", "s_{μ} (nuisance)"]
  : i === 1 ? ["**Nominal (range)**", "2.4 µm (±20%)", "1×10^{17} (±20%)", "−1.0×10^{12} (−1.5 to −0.5)", "1 (0.8–1.2)"] : r));
// S2 mean MAE_norm per 423 K scenario; parentheses: change from S1x2 (0.086), * = paired-bootstrap 95% CI of S2 - S1x2
// excludes 0 (results/summary/v48_extra_stats.md, part 1). Clipped nominal-training values are given in the text.
const T2_ROWS = [
  ["0.072 (−17%)^{*}", "—", "0.082 (−5%)"],
  ["0.073 (−15%)^{*}", "**0.537**", "0.083 (−3%)"],
  ["0.076 (−12%)^{*}", "**0.928**", "0.088 (+1%)"],
  ["0.057 (−34%)^{*}", "0.084", "0.079 (−8%)"],
  ["0.033 (−62%)^{*}", "**0.132**", "0.080 (−7%)"],
  ["—", "0.261", "—"],
];
const T2 = REVIEW
  ? [["423 K physics of test data", "Matched training", "Nominal training", "Randomized training^{†}"],
     ...["Baseline (γ = +1, r = 0)", "γ = 0", "γ = −1", "r = 0.1", "r = 0.3", "Series R^{‡}"].map((h, i) => [h, ...T2_ROWS[i]])]
  : [["시험 데이터의 423 K 물리", "같은 물리로 학습", "기준 물리로 학습", "가정 무작위화 학습^{†}"],
     ...["기준(γ = +1, r = 0)", "γ = 0", "γ = −1", "r = 0.1", "r = 0.3", "기생 직렬저항^{‡}"].map((h, i) => [h, ...T2_ROWS[i]])];
const T1W = [1300, 830, 830, 830, 830];
const T2W = [1380, 1080, 1000, 1160];
// LLM ablation (results/summary/v47_rq3_ablation.md; seed-level CIs: v48_extra_stats.md, part 3); Δ in units of 1e-3
const T3_ROWS = [
  ["0.1250", "+1.2 [−0.8, +3.6]", "0.63/0.63", "—"],
  ["0.1236", "−0.2 [−1.7, +1.3]", "0.62/0.62", "47/47 (31)"],
  ["0.1242", "+0.4 [−1.6, +3.1]", "0.55/0.55", "49/49 (34)"],
  ["0.1257", "+1.9 [−0.7, +4.8]", "0.49/0.64", "51/36 (30)"],
  ["0.1259", "+2.1 [−0.3, +5.0]", "—", "—"],
  ["0.1238", "—", "—", "—"],
];
const T3 = REVIEW
  ? [["Condition", "Final MAE_{norm}", "Δ vs. uncertainty (×10^{−3})", "Top-10 overlap (true/shown)", "Widened worst variable (shown/true)"],
     ...["A0 (1st run)", "A original", "B anonymized", "C shuffled", "D top-20 random", "Uncertainty"].map((h, i) => [h, ...T3_ROWS[i]])]
  : [["조건", "최종 MAE_{norm}", "불확실도 대비 Δ (×10^{−3})", "상위 10 겹침 (실제/표시)", "최악 변수 방향 확대 (표시/실제)"],
     ...["A0 (1차 실행)", "A 원래 형식", "B 익명화", "C 정보 섞기", "D 상위 20 무작위", "불확실도"].map((h, i) => [h, ...T3_ROWS[i]])];
const T3W = [1080, 640, 1000, 880, 1020];

// ------------------------------------------------------------------ header
const head = [];
if (REVIEW) {
  const tb = [
    new Paragraph({ spacing: { after: 60 }, children: runs("투고용 논문", { size: 16 }) }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60, line: 300 }, children: runs(titleKR, { size: 30, bold: true }) }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120, line: 250 }, children: runs(`(${titleEN})`, { size: 20 }) }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 30 }, children: runs("요  약", { size: 18, bold: true }) }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 300, right: 300, firstLine: 180 }, spacing: { line: 235, after: 80 }, children: runs(ABS_KR, { size: 17 }) }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 30 }, children: runs("Abstract", { size: 18, bold: true }) }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 300, right: 300, firstLine: 180 }, spacing: { line: 225, after: 80 }, children: runs(ABS_EN_REVIEW, { size: 16 }) }),
    new Paragraph({ indent: { left: 300, right: 300 }, spacing: { after: 60 }, children: runs("**Keywords :** 4H-SiC MOSFET, DEVSIM, Inverse estimation, Repeated measurement, Model mismatch, Active learning, LLM", { size: 16 }) }),
  ];
  head.push(new Table({
    width: { size: FULLW, type: WidthType.DXA }, columnWidths: [FULLW],
    borders: { top: LINE(12), bottom: LINE(12), left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
    rows: [new TableRow({ children: [new TableCell({ width: { size: FULLW, type: WidthType.DXA }, margins: { top: 60, bottom: 60, left: 60, right: 60 },
      borders: { top: LINE(12), bottom: LINE(12), left: NONE, right: NONE }, children: tb })] })],
  }));
  head.push(...figure("fig1_structure_flow.png", 430,
    "그림 1. (a) 4H-SiC 평판형 MOSFET half-cell 단면(half-pitch 3.5 µm·채널 길이 0.5 µm 고정, 드리프트층 축약 표시)과 추정 파라미터, (b) 다중 온도 시뮬레이션–특징 추출–역추정 및 표본 선택 흐름",
    "Fig. 1. (a) Half-cell cross-section of the 4H-SiC planar MOSFET (half-pitch 3.5 µm, channel length 0.5 µm, drift layer abbreviated) and estimated parameters, (b) workflow of multi-temperature simulation, feature extraction, inverse estimation and sample selection."));
} else {
  head.push(
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 110, line: 300 }, children: runs(titleKR, { size: 30, bold: true }) }),
    center("이민석", 20), center("광운대학교 전자공학과", 17), center("e-mail : minseok1270@gmail.com", 17),
    new Paragraph({ spacing: { after: 90 }, children: [] }),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 50, line: 260 }, children: runs(titleEN, { size: 22, bold: true }) }),
    center("Minseok Lee", 17), center("Department of Electronic Engineering, Kwangwoon University", 17),
    new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 150, after: 50 }, children: runs("Abstract", { size: 18, bold: true }) }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 400, right: 400, firstLine: 200 }, spacing: { line: 240, after: 60 }, children: runs(ABS_EN, { size: 17 }) }),
    ...figure("fig1_structure_flow.png", 570, "그림 1. (a) 4H-SiC 평판형 MOSFET half-cell 단면(half-pitch 3.5 µm·채널 길이 0.5 µm 고정, 드리프트층 축약 표시)과 추정 파라미터, (b) 다중 온도 시뮬레이션–특징 추출–역추정 및 표본 선택 흐름."),
  );
}

// ------------------------------------------------------------------ body (V4.8: review fixes, S1x2 comparisons, readability)
const B = [];
const ORD_DEFAULT = REVIEW ? { F2: "pre", F3: "pre", T2: "post", F4: "late", T3: "post" } : { F2: "post", F3: "post", T2: "post", F4: "pre", T3: "pre" };
const PRE = (k) => (process.env["ORD_" + k] || ORD_DEFAULT[k]) === "pre";
const R_ = (review, proc) => (REVIEW ? review : proc);
const S = REVIEW
  ? { c1: "Ⅰ. 서  론", c2: "Ⅱ. 시뮬레이션 모델 및 검증", s21: "1. 소자 구조와 물리 모델", s22: "2. 추정 파라미터와 특징", s23: "3. 모델 검증",
      c3: "Ⅲ. 실험 설계", s31: "1. 민감도 분석", s32: "2. 데이터, 잡음 모델과 반복 측정 통제", s33: "3. 고온 물리 강건성 시험", s34: "4. 적응형 표본 선택과 LLM 절제",
      c4: "Ⅳ. 결과 및 고찰", s41: "1. 다중 온도 특징의 효과(RQ1)", s42: "2. 고온 물리 가정에 대한 의존성(RQ1)", s43: "3. 적응형 선택의 효과(RQ2)", s44: "4. LLM 보조 선택(RQ3)",
      c5: "Ⅴ. 결  론", refs: "REFERENCES" }
  : { c1: "Ⅰ. 서론", c2: "Ⅱ. 시뮬레이션 모델 및 검증", s21: "2.1 소자 구조와 물리 모델", s22: "2.2 추정 파라미터와 특징", s23: "2.3 모델 검증",
      c3: "Ⅲ. 실험 설계", s31: "3.1 민감도 분석", s32: "3.2 데이터, 잡음 모델과 반복 측정 통제", s33: "3.3 고온 물리 강건성 시험", s34: "3.4 적응형 표본 선택과 LLM 절제", s35: "3.5 계산 환경, 재현성과 사전 예측",
      c4: "Ⅳ. 결과 및 고찰", s41: "4.1 다중 온도 특징의 효과(RQ1)", s42: "4.2 고온 물리 가정에 대한 의존성(RQ1)", s43: "4.3 적응형 선택의 효과(RQ2)", s44: "4.4 LLM 보조 선택(RQ3)",
      c5: "Ⅴ. 결론", refs: "참고문헌" };

// ---------- I. introduction
B.push(h1(S.c1));
if (REVIEW) {
  B.push(body("4H-SiC MOSFET은 고전압·고온 전력 변환에 널리 쓰인다[[baliga,kimoto]]. 그러나 JFET 폭, P-well 도핑, 계면전하 같은 공정 결과의 편차는 문턱전압(V_{th})과 비온저항(R_{on,sp})을 함께 바꾼다. P-well 도핑과 음의 계면전하가 늘면 모두 V_{th}가 높아지고, JFET 폭과 채널 이동도가 늘면 모두 전류가 커진다. 따라서 측정 특성만으로는 원인을 구분하기 어렵다. 온도 의존성은 이런 원인을 구분하는 데 쓰여 왔다. 측정 소자에서는 계면 트랩 밀도가 클수록 25→150 °C의 V_{th} 감소가 컸고[[yu]], 채널 저항은 드리프트 저항보다 온도 의존성이 약했다[[stark]]. 채널 이동도는 쿨롱 산란이 지배하면 고온에서 증가하고 포논 산란이 지배하면 감소한다[[das]]."),
    body("TCAD에 기반한 공정 편차 평가[[muting]], 공정 조건에서 특성을 예측하거나[[ha]] 특성에서 소자 파라미터를 역추정한 기계학습[[ha2022,mehta]], 여러 온도의 측정으로 TCAD 이동도를 보정한 연구[[ong]]가 보고되었다. 그러나 TCAD로 학습한 모델은 학습에 없는 변수에 취약하다[[mehta]]. 또 다중 온도 특징의 이득이 같은 소자를 한 번 더 측정한 효과와 어떻게 다른지, 고온 물리를 모르거나 틀리게 가정하면 어떻게 되는지를 같은 조건에서 비교한 연구는 찾지 못했다. 한편 TCAD는 계산 비용이 커서 효율적인 실험 설계가 필요하다. 대규모 언어 모델(LLM)을 실험 계획[[boiko]]이나 TCAD 코드 생성[[agentic]]에 쓰려는 시도가 있지만, LLM 기반 실험 선택이 수치적 방법보다 낫지 않다는 보고도 있다[[gupta]]."),
    body("본 논문은 공개형 TCAD인 DEVSIM[[devsim]]으로 300 K·423 K 특성을 계산하고 세 가지를 묻는다. RQ1은 423 K 특징의 이득 가운데 반복 측정으로 설명되지 않는 부분과 그 고온 물리 의존성이다. RQ2는 미리 계산한 후보 풀에서 회고적으로 평가한 적응형 표본 선택이 시뮬레이션을 얼마나 줄이는지, RQ3는 LLM 보조 선택이 수치적 불확실도 선택보다 나은지와 제공 정보를 쓰는지이다. 주 분석과 통제·절제 시험의 예상 결과는 분석 전에 저장소 문서에 기록하였다. S1×2의 시나리오별·같은 예산 비교, 가정 무작위화 학습, 범위 제한 예측, 초기 표본 수 민감도, RQ3의 실행 간 비교와 최소 검출 차이는 사후 분석이다."),
    body("본 논문의 새로움은 새 알고리즘이 아니라 이득의 출처를 가르는 비교 설계에 있다. 기여는 ① 300 K 반복 측정 통제로 반복 이득과 온도 고유 이득을 나누고, ② 온도 고유 이득이 고온 물리를 알 때만 뚜렷함을 보이며, ③ LLM 선택을 정보 익명화·섞기 절제로 평가한 것이다. 방법 요소(TCAD, 가우시안 과정, 능동학습, 구조화 출력)는 기존 기법을 따랐다."));
} else {
  B.push(body("4H-SiC MOSFET은 넓은 밴드갭과 높은 임계전계 덕분에 고전압·고온 전력 변환에 널리 쓰인다[[baliga,kimoto]]. 그러나 JFET 폭, P-well 도핑, SiO_{2}/SiC 계면전하 같은 공정 결과의 편차는 문턱전압(V_{th})과 비온저항(R_{on,sp})을 함께 바꾼다. P-well 도핑과 음의 계면전하가 늘면 모두 V_{th}가 높아지고, JFET 폭과 채널 이동도가 늘면 모두 전류가 커진다. 서로 다른 원인이 같은 전기적 변화를 만들기 때문에 측정 특성만으로 원인을 역추정하기 어렵다."),
    body("온도 의존성은 이런 원인을 구분하는 데 쓰여 왔다. 측정 소자에서는 계면 트랩 밀도가 클수록 25→150 °C의 V_{th} 감소가 컸고[[yu]], 채널 저항은 드리프트 저항보다 온도 의존성이 약했다[[stark]]. 드리프트층의 벌크 이동도는 고온에서 감소하지만[[roschke]], 채널 이동도는 쿨롱 산란이 지배하면 증가하고 포논 산란이 지배하면 감소한다[[das]]. 따라서 고온 특성은 300 K 특성과 다른 조합의 정보를 줄 수 있지만, 그 내용은 고온 물리에 따라 달라진다."),
    body("Müting 등은 상용 1.2 kV SiC MOSFET에 보정한 TCAD로 공정 편차를 평가해 에피 도핑과 계면 트랩 밀도가 소자 간 편차에 가장 중요함을 보였다[[muting]]. TCAD 데이터로 공정 조건에서 특성을 예측하거나[[ha]] 전기적 특성에서 소자 파라미터를 역추정한 기계학습[[ha2022,mehta]], 여러 온도의 측정 곡선으로 TCAD 이동도를 보정한 연구[[ong]]도 있다. 그러나 TCAD로 학습한 모델은 학습에 없는 변수에 취약하다[[mehta]]. 또 다중 온도 특징의 이득이 같은 소자를 한 번 더 측정한 효과와 어떻게 다른지, 고온 물리를 모르거나 틀리게 가정하면 어떻게 되는지를 같은 조건에서 비교한 연구는 찾지 못했다."),
    body("한편 TCAD는 계산 비용이 커서 효율적인 실험 설계가 필요하다. 대규모 언어 모델(LLM)을 실험 계획[[boiko]]이나 TCAD 코드 생성[[agentic]]에 쓰려는 시도가 있지만, LLM 기반 실험 선택이 수치적 방법보다 낫지 않다는 보고도 있다[[gupta]]. 따라서 LLM이 제공 정보를 실제로 쓰는지 따로 확인할 필요가 있다."),
    body("본 논문은 공개형 TCAD인 DEVSIM[[devsim]]으로 4H-SiC 평판형 MOSFET의 300 K·423 K DC 특성을 계산하고 세 가지를 묻는다. RQ1은 423 K 특징이 역추정 오차를 얼마나 줄이는지, 그 가운데 반복 측정으로 설명되지 않는 부분은 무엇이며 고온 물리 가정에 어떻게 의존하는지이다. RQ2는 미리 계산한 후보 풀에서 회고적으로 평가한 적응형 표본 선택이 필요한 시뮬레이션 수를 줄이는지, RQ3는 검증기로 제한한 LLM 보조 선택이 수치적 불확실도 선택보다 나은지와 제공 정보를 쓰는지이다. 주 분석과 통제·절제 시험의 예상 결과는 분석 전에 저장소 문서에 기록하였다(3.5절)."),
    body("본 논문의 새로움은 새 알고리즘이 아니라 이득의 출처를 가르는 비교 설계에 있으며, 기여는 세 가지이다. ① 300 K 반복 측정 통제로 다중 온도 이득을 반복 이득과 온도 고유 이득으로 나눈다. ② 온도 고유 이득은 고온 물리를 알 때만 뚜렷하고, 측정 간 잡음 상관이 클수록 상대적으로 커짐을 보인다. ③ LLM 선택을 정보 익명화·섞기 절제로 평가해 최종 오차와 선택 행동을 함께 보고한다. 방법 요소(TCAD, 가우시안 과정, 능동학습, 구조화 출력)는 기존 기법을 따랐다."));
}

// ---------- II. model
B.push(h1(S.c2), h2(S.s21));
B.push(body(R_("그림 1(a)의 half-cell은 1.2 kV급 설계를 참고한 평판형 구조로, 게이트 산화막 50 nm, P-well 1×10^{17} cm^{−3}, JFET 영역 2×10^{16} cm^{−3}, 드리프트층 10 µm·1×10^{16} cm^{−3}이다. Poisson 방정식과 전자 연속방정식을 Scharfetter–Gummel 이산화[[sg]]로 풀고, 불완전 이온화(N 66 meV, Al 191 meV)[[ikeda]], 도핑·온도 의존 이동도[[roschke]], SRH 재결합을 포함하였다. 물성값은 문헌 고찰[[burin]]을 따랐고, 채널 이동도는 벌크와 표면 성분을 결합한 식 (1), (2)로 두었다.",
  "그림 1(a)의 half-cell은 1.2 kV급 설계를 참고한 평판형 구조로, 게이트 산화막 50 nm, P-well 1×10^{17} cm^{−3}, JFET 영역 2×10^{16} cm^{−3}, 드리프트층 10 µm·1×10^{16} cm^{−3}, half-pitch 3.5 µm, 채널 길이 0.5 µm이다. Poisson 방정식과 전자 연속방정식을 Scharfetter–Gummel 이산화[[sg]]로 풀고, 불완전 이온화(N 66 meV, Al 191 meV)[[ikeda]], 도핑·온도 의존 전자 이동도[[roschke]], SRH 재결합을 포함하였다. 물성값은 문헌 고찰[[burin]]을 따랐다. 채널의 전자 이동도는 벌크 성분과 표면 성분을 Matthiessen 규칙으로 결합한 식 (1), (2)로 두었다.")));
B.push(equation("μ_{n}^{−1} = μ_{bulk}^{−1}(N, T) + e^{−y/λ} μ_{surf}^{−1}(T)", 1));
B.push(equation("μ_{surf}(T) = 20 s_{μ}(T/300 K)^{γ} cm^{2}/(V·s), γ ∈ {+1, 0, −1}", 2));
B.push(body(R_("y는 계면으로부터의 거리, λ = 3 nm, s_{μ}(0.8~1.2)는 추정하지 않는 채널 이동도 배율(교란 변수)이며, 계수 20 cm^{2}/(V·s)와 λ는 가정값이다. 기준 모델은 쿨롱 산란이 지배해 채널 이동도가 고온에서 증가하는 경우(γ = +1)이고, γ = 0, −1은 강건성 시험에만 쓴다. 계면은 면전하 σ = q[Q_{f} + Q_{it,eff}(T)](Q_{f} = 1×10^{12} cm^{−2}, 가정값)로 두었고, 기준 모델에서 Q_{it,eff}는 온도와 무관하다. 그 크기가 고온에서 줄어드는 경우는 식 (3)으로 시험한다.",
  "y는 계면으로부터의 거리, λ = 3 nm, s_{μ}는 0.8~1.2의 채널 이동도 배율(추정하지 않는 교란 변수)이며, 계수 20 cm^{2}/(V·s)와 λ는 가정값이다. 기준 모델은 쿨롱 산란이 지배해 채널 이동도가 300–423 K에서 증가하는 경우(γ = +1)이다. 그러나 n채널 소자의 Hall 이동도는 상온 이상에서 포논 산란으로 감소할 수 있으므로[[das]], γ = 0, −1도 시험한다(4.2절). 계면에는 고정전하 Q_{f} = 1×10^{12} cm^{−2}(가정값)와 유효 계면전하 Q_{it,eff}를 면전하 σ = q[Q_{f} + Q_{it,eff}(T)]로 두었다. 기준 모델에서 Q_{it,eff}는 온도와 무관하며, 그 크기가 고온에서 줄어드는 경우는 식 (3)으로 시험한다.")));
B.push(equation("Q_{it,eff}(T) = Q_{it,eff}(300)·[1 − r(T − 300)/123]", 3));
B.push(body(R_("T의 단위는 K이고 r ∈ {0, 0.1, 0.3}이다. Q_{it,eff}는 음수이므로 식 (3)은 그 절댓값을 줄인다. 모든 설계점에 같은 r을 적용하고 r은 역추정 모델에 주지 않는다. Q_{it,eff}는 정적 등가전하이므로 SS를 바꾸지 않는다. 정공은 소스/바디와 평형으로 두는 단극성 근사를 썼다. 423 K에서도 접합 생성전류(2×10^{−16} A/cm^{2} 이하)는 특징 추출의 최소 전류(약 3×10^{−7} A/cm^{2})보다 9자릿수 이상 작다.",
  "T의 단위는 K이고 r ∈ {0, 0.1, 0.3}이다. Q_{it,eff}는 음수이므로 식 (3)은 그 절댓값을 줄인다. 모든 설계점에 같은 r을 적용하며, 추정 대상은 300 K의 Q_{it,eff}이고 r은 역추정 모델에 입력하지 않는다. Q_{it,eff}는 계면 트랩의 정적 등가전하이므로 SS를 바꾸지 않는다. 정공은 소스/바디와 평형으로 두는 단극성 근사를 썼다. 423 K에서도 접합 생성전류(2×10^{−16} A/cm^{2} 이하)는 특징 추출의 최소 전류(약 3×10^{−7} A/cm^{2})보다 9자릿수 이상 작고, V_{DS} ≤ 5 V이므로 충돌 이온화는 넣지 않았다.")));
B.push(h2(S.s22));
B.push(body(R_("추정 대상은 공정 결과를 나타내는 잠재 파라미터 θ = (W_{JFET}, N_{pw}, Q_{it,eff})이며, 기준값과 범위는 표 1에 정리하였다. 소자 간 편차에 중요한 에피 도핑[[muting]]은 고정하였다. W_{JFET} 편차는 마스크 피치를 고정한 채 자기정렬 경계가 이동하는 것으로 정의하였다. 고온은 상용 소자 데이터시트의 고온 특성 온도인 423 K(150 °C)[[cree]]로 두었다. 각 온도에서 V_{DS} = 0.1 V 전달 특성과 V_{GS} = 18 V 출력 특성을 계산하였다. 특징 벡터 x_{T}는 6개 스칼라(V_{th}(1×10^{−4} A/cm 정전류), SS, log g_{m,max}, log I_{on}, log R_{on,sp}, log I_{D}(V_{DS} = 2 V))와 11개 전달곡선 표본 log I_{D}(V_{GS} = 4~20 V)이다. 전류는 2차원 단면의 단위 폭당 값(A/cm)이다. 특징 집합은 S1 = x_{300}(17차원), S2 = [x_{300}, x_{423}](34차원), S3 = [S2, x_{423} − x_{300}](51차원)이다.",
  "추정 대상은 공정 결과를 나타내는 잠재 파라미터 θ = (W_{JFET}, N_{pw}, Q_{it,eff})이다. 채널 이동도 배율 s_{μ}는 모든 설계에서 변하지만 추정하지 않는다. 기준값과 범위는 표 1에 정리하였다. 소자 간 편차에 중요한 에피 도핑[[muting]]은 고정하였다. W_{JFET} 편차는 마스크 피치를 고정한 채 자기정렬된 P-well/n^{+} 경계가 이동하는 것으로 정의해 채널 길이와 면적 정규화를 유지하였다. 고온은 상용 소자 데이터시트의 고온 특성 온도인 423 K(150 °C)[[cree]]로 두었다. 각 온도 T에서 V_{DS} = 0.1 V 전달 특성과 V_{GS} = 18 V 출력 특성을 계산하고, 특징 벡터 x_{T}를 6개 스칼라와 11개 전달곡선 표본으로 만들었다. 스칼라는 V_{th}(1×10^{−4} A/cm 정전류), SS(10^{−10}~10^{−6} A/cm), log g_{m,max}, log I_{on}(V_{GS} = 18 V), log R_{on,sp}(V_{DS} ≤ 0.5 V 기울기), log I_{D}(V_{DS} = 2 V)이다. 표본은 V_{GS} = 4, 5, 6, 7, 8, 10, …, 20 V의 log I_{D}이다. 전류는 2차원 단면의 단위 폭당 값(A/cm)이다. 특징 집합은 S1 = x_{300}(17차원), S2 = [x_{300}, x_{423}](34차원), S3 = [S2, x_{423} − x_{300}](51차원)이다.")));
B.push(h2(S.s23));
const F2 = () => figure("fig2_validation.png", REVIEW ? 220 : 280, R_("그림 2. 시뮬레이션 검증: (a) 전달 특성(V_{DS} = 0.1 V, 점: V_{th}), (b) 출력 특성(V_{GS} = 18 V), (c) fine 메시 대비 드레인 전류 차이(300 K), (d) Q_{it,eff}에 따른 V_{th} 이동과 해석해. J_{D}: 단위 폭 전류를 셀 폭(3.5 µm)으로 나눈 값",
  "그림 2. 시뮬레이션 검증: (a) 전달 특성(V_{DS} = 0.1 V, 점: V_{th}, I_{cc}: V_{th} 정전류 기준), (b) 출력 특성(V_{GS} = 18 V), (c) fine 메시 대비 드레인 전류 차이(300 K), (d) Q_{it,eff}에 따른 V_{th} 이동과 해석해. J_{D}는 단위 폭 전류를 셀 폭(3.5 µm)으로 나눈 값이다."),
  REVIEW ? "Fig. 2. Model verification: (a) transfer characteristics (V_{DS} = 0.1 V), (b) output characteristics (V_{GS} = 18 V), (c) drain-current difference from the fine mesh (300 K), (d) V_{th} shift versus Q_{it,eff} with the analytic line. J_{D}: current per unit width divided by the cell width (3.5 µm)." : null);
const P23 = body(R_("1차원 PN 다이오드의 내장전위·불완전 이온화율과 MOS 커패시터의 평탄대 전압은 해석해와 5 mV 이내로 일치하였다. 그림 2에서 300 K→423 K에 V_{th}는 3.765→3.530 V, SS는 112.5→155.7 mV/dec, R_{on,sp}는 2.00→2.87 mΩ·cm^{2}로 변하였다. 사용한 메시(1.1만 노드)는 fine 메시 대비 V_{th} 0.07 mV, R_{on,sp} 0.9% 이내였고, Q_{it,eff}에 따른 V_{th} 이동은 −qΔQ_{it}/C_{ox}와 1 mV 이내로 일치하였다. 상용 1.2 kV 소자[[cree]]의 25→150 °C 변화(V_{th} 2.9→2.4 V, R_{DS(on)} 80→144 mΩ)와 방향은 같지만 본 모델의 변화폭(0.23 V, 44%)은 더 작다. 측정 소자에서 나타나는 고온 계면 트랩 전자 방출[[yu]]은 기준 모델에 넣지 않았다.",
  "1차원 PN 다이오드의 내장전위·불완전 이온화율과 MOS 커패시터의 평탄대 전압은 해석해와 5 mV 이내로 일치하였다. 그림 2에서 300 K→423 K에 V_{th}는 3.765→3.530 V, SS는 112.5→155.7 mV/dec, R_{on,sp}는 2.00→2.87 mΩ·cm^{2}로 변하였다. 사용한 메시(1.1만 노드)는 fine 메시 대비 V_{th} 0.07 mV, R_{on,sp} 0.9% 이내였고, Q_{it,eff}에 따른 V_{th} 이동은 −qΔQ_{it}/C_{ox}와 1 mV 이내로 일치하였다. 상용 1.2 kV 소자[[cree]]의 25→150 °C 변화(V_{th} 2.9→2.4 V, R_{DS(on)} 80→144 mΩ)와 방향은 같지만 본 모델의 변화폭(0.23 V, 44%)은 더 작다. 데이터시트 값은 패키지를 포함한 다른 조건의 측정이므로 정량 비교에는 한계가 있다. 측정 소자에서는 고온에서 계면 트랩의 전자가 방출되어 V_{th}가 더 낮아지는데[[yu]], 기준 모델은 이를 넣지 않았다. 이 효과(r)와 이동도 지수(γ)를 바꾼 계산은 4.2절에 정리하였다."));
if (PRE("F2")) B.push(...F2(), P23); else B.push(P23, ...F2());

// ---------- III. design
B.push(h1(S.c3), h2(S.s31));
B.push(body(R_("표 1은 각 변수를 +20% 바꿨을 때의 특징 변화이다. N_{pw}와 Q_{it,eff}는 V_{th}를 +485, +464 mV로 거의 같게 바꾸지만, SS(+3.4%)와 V_{th} 온도 이동(−10.9 mV)은 N_{pw}에만 반응한다. W_{JFET}와 s_{μ}는 300 K에서 모두 I_{on}을 높인다. 그러나 423 K에서는 드리프트 이동도가 감소하고 채널 이동도가 증가하므로, 두 변수의 I_{on} 민감도 비(W_{JFET}/s_{μ})가 0.40에서 1.26으로 바뀐다.",
  "표 1은 각 변수를 +20% 바꿨을 때의 특징 변화이다. N_{pw}와 Q_{it,eff}는 V_{th}를 +485, +464 mV로 거의 같게 바꾸지만, SS(+3.4%)와 V_{th} 온도 이동(−10.9 mV)은 N_{pw}에만 반응한다. W_{JFET}와 s_{μ}는 300 K에서 모두 I_{on}을 높인다. 그러나 423 K에서는 드리프트 이동도가 감소하고 채널 이동도가 증가하므로 W_{JFET}의 민감도는 커지고(+3.1→+4.5%) s_{μ}의 민감도는 작아진다(+7.8→+3.6%). 두 변수의 I_{on} 민감도 비(W_{JFET}/s_{μ})는 0.40에서 1.26으로 바뀌어, 두 온도는 서로 다른 조합의 정보를 준다.")));
if (REVIEW) { B.push(capT("표 1. 파라미터 기준값·범위와 +20% 변화에 따른 특징 변화(300 K/423 K)"), capT("Table 1. Nominal values, ranges and feature changes for a +20% change of each parameter (300 K/423 K)."), table(T1W, T1_EN), note("Units: N_{pw} in cm^{−3}, Q_{it,eff} in cm^{−2} (at 300 K). +20%: 1.2 times the nominal (Q_{it,eff}: −1.0 → −1.2×10^{12} cm^{−2}). *ΔV_{th,T}: change of V_{th}(423 K) − V_{th}(300 K) from the baseline.")); }
else { B.push(capT("표 1. 파라미터 기준값·범위와 +20% 변화에 따른 특징 변화(300 K/423 K)"), table(T1W, T1_KR), note("N_{pw} 단위 cm^{−3}, Q_{it,eff} 단위 cm^{−2}(300 K 값). +20%: 기준값의 1.2배(Q_{it,eff}는 −1.0 → −1.2×10^{12} cm^{−2}). *ΔV_{th,T}: V_{th}(423 K)−V_{th}(300 K)의 기준 대비 변화.")); }
B.push(h2(S.s32));
if (REVIEW) {
  B.push(body("4차원(θ, s_{μ}) Sobol 후보 512점(풀)과 독립 무작위 시험점 128점을 두 온도에서 계산(1,280회)하였다. 측정 잡음은 추출된 특징에 독립 정규잡음으로 더하였다. 표준편차(가정값)는 V_{th} 10 mV, SS·g_{m,max} 2%, I_{on}·R_{on,sp}·I_{D}(2 V) 1%, 전달곡선 표본 2%이다. 전류 1%는 측정기 정확도(판독값의 0.03~0.4%)[[keysight]]에 반복 측정 변동과 자기발열의 재현 오차를 더해 정하였다. ‘2배 잡음’은 모든 표준편차를 두 배로 한 경우이다. 역추정 모델(가우시안 과정(GP)[[gp]], 랜덤 포레스트(RF), 선형 Ridge)은 특징에서 θ를 예측한다. 성능은 각 변수의 절대오차를 DOE 범위로 나눠 평균한 MAE_{norm}(무정보 추정 0.25)과, 시험점별 오차 차이의 짝지은 부트스트랩(5,000회) 95% CI로 평가하였다. 국소 식별성은 기준점 주변 자코비안(6개 스칼라)과 가정한 잡음의 Cramér–Rao 하한으로 점검하였다."),
    body("423 K 특징의 이득에는 같은 소자를 한 번 더 측정한 효과가 섞여 있다. 이를 분리하기 위해 300 K 특징에 독립 잡음을 한 번 더 실현해 두 측정을 평균한 통제 집합 S1×2를 학습·시험 데이터에 만들었다. 두 측정 사이의 잡음 상관 ρ ∈ {0, 0.5, 0.9}도 바꾸었다(S2는 300/423 K, S1×2는 두 300 K 측정). 상관된 잡음은 접촉 저항처럼 두 측정에 함께 들어가는 오차를 나타낸다."));
} else {
  B.push(body("4차원(θ, s_{μ}) Sobol 후보 512점(풀)과 독립 무작위 시험점 128점을 두 온도에서 계산(1,280회)하였다. 측정 잡음은 추출된 특징에 서로 독립인 정규분포로 더하였다. V_{th}에는 가산 잡음(10 mV)을, 나머지에는 상대 잡음(SS·g_{m,max} 2%, I_{on}·R_{on,sp}·I_{D}(2 V) 1%, 전달곡선 표본 2%)을 주었다. 이 표준편차는 가정값이다. 전류 1%는 측정기 정확도(고분해능 ADC, 전류 범위에 따라 판독값의 0.03~0.4%)[[keysight]]에 반복 측정 변동과 자기발열의 재현 오차를 고려해 정하였다. 표본 전류는 잡음 후 1×10^{−11} A/cm 하한에서 절단하였고, 풀과 시험 집합에는 서로 다른 잡음 실현을 썼다. ‘2배 잡음’은 모든 표준편차를 두 배로 한 경우이다."),
    body("역추정 모델은 가우시안 과정(GP, 상수×RBF+백색잡음 커널)[[gp]], 랜덤 포레스트(RF, 300그루), 선형 Ridge 회귀이다. GP·Ridge의 입력은 표준화하고, 출력은 DOE 범위로 [0, 1] 정규화하였다. 성능은 각 변수의 절대오차를 DOE 범위로 나눠 세 변수에 대해 평균한 MAE_{norm}으로 평가하였다. 범위 중앙값을 답하는 무정보 추정의 MAE_{norm}은 0.25이다. 두 특징 집합의 비교에는 시험점별 오차 차이의 짝지은 부트스트랩(5,000회) 95% CI를 썼다. 국소 식별성은 기준점 주변의 중앙차분 자코비안(6개 스칼라, 4개 변수)과 가정한 잡음으로 계산한 Cramér–Rao 하한으로 점검하였다."),
    body("423 K 특징의 이득에는 같은 소자를 한 번 더 측정한 효과가 섞여 있다. 이를 분리하기 위해 300 K 특징에 독립 잡음을 한 번 더 실현해 두 측정을 평균한 통제 집합 S1×2(17차원)를 학습·시험 데이터에 만들었다. 두 측정 사이의 잡음 상관 ρ ∈ {0, 0.5, 0.9}도 바꾸었다(S2는 300/423 K, S1×2는 두 300 K 측정). 두 번째 측정의 표준정규 잡음은 z_{2} = ρz_{1} + (1 − ρ^{2})^{1/2}z′(z′는 독립)로 만들었다. 상관된 잡음은 접촉 저항이나 고정 장치처럼 두 측정에 함께 들어가는 오차를 나타낸다."));
}
B.push(h2(S.s33));
if (REVIEW) {
  B.push(body("423 K 특성만 다시 계산하여(300 K 물리는 동일) 식 (2)의 γ = 0, −1과 식 (3)의 r = 0.1, 0.3을 시험하였다(풀·시험점 640점씩, 2,560회, 모두 수렴). 평가는 세 가지이다. ① 같은 물리로 학습·평가하여 해당 가정에서 423 K 정보가 유용한지 본다. ② 기준 물리로 학습하고 변형 물리로 평가하여 고온 물리를 틀리게 가정한 경우를 본다. ③ 512개 풀 점의 423 K 데이터를 다섯 가정 중 하나에서 무작위로 가져와 학습하여 고온 물리를 모르는 경우를 본다(가정 무작위화 학습, 사후 분석). 가정의 종류는 입력하지 않았고, 모든 경우를 같은 128개 시험점에서 S1, S1×2와 비교하였다. 또 탐색적으로 소자별 직렬저항(면적 정규화 0.1–0.3 mΩ·cm^{2}, 두 온도에 동일)을 시험 데이터에만 넣고, 저장된 곡선을 1차 근사로 변환해 특징을 다시 계산하였다(V_{th}·SS는 그대로)."));
} else {
  B.push(body("고온 물리 가정의 영향을 보기 위해 423 K 특성만 다시 계산하였다(300 K 물리는 동일). 변형은 식 (2)의 γ = 0, −1과 식 (3)의 r = 0.1, 0.3이며, 각각 풀·시험점 640점을 재계산하였다(2,560회, 모두 수렴). 평가는 세 가지이다. ① 같은 물리로 학습·평가하면 해당 가정에서 423 K 정보가 유용한지 본다. ② 기준 물리로 학습하고 변형 물리로 평가하면 고온 물리를 틀리게 가정한 경우를 본다. ③ 512개 풀 점의 423 K 데이터를 다섯 가정(기준과 네 변형) 중 하나에서 무작위로 가져와 학습하면 고온 물리를 모르는 경우를 본다(가정 무작위화 학습, 사후 분석). 가정의 종류는 모델에 입력하지 않았고, 모든 경우를 같은 128개 시험점에서 S1, S1×2와 비교하였다."),
    body("또 학습에 없는 기생 직렬저항을 시험 데이터에만 넣었다(탐색적 분석). 소자별 면적 정규화 저항 R_{s,sp} ~ U(0.1, 0.3) mΩ·cm^{2}(두 온도에 동일)를 드레인 측 집중저항 R_{s} = R_{s,sp}/W_{c}(W_{c} = 3.5 µm)로 두고, 저장된 곡선을 1차 근사로 변환해 특징을 다시 계산하였다. 전류 특징과 g_{m,max}는 R_{s}의 전압 강하를 반영해 다시 구하고(선형 영역 I_{D}/(1 + I_{D}R_{s}/V_{DS})), R_{on,sp}에는 R_{s,sp}를 더하였다. 전류가 작은 V_{th}·SS는 그대로 두었다(I_{D}R_{s} < 0.1 mV)."));
}
B.push(h2(S.s34));
if (REVIEW) {
  B.push(body("풀 기반 회고적 능동학습[[settles]](512개 후보의 특성을 미리 계산해 두고 정책이 고른 점만 학습에 사용)으로 모든 정책에 같은 초기 무작위 60점과 예산(10점×6회)을 주고, S2 특징과 RF 역추정 모델로 시드 10개를 반복하였다. 무작위와 Sobol 순서[[sobol]]는 학습 모델을 쓰지 않는 기준선이다. 불확실도 정책은 S2 특징을 예측하는 순방향 RF의 트리 간 표준편차 u(p)를 구하고, u 상위 30개 후보에서 u(p)와 d(p)(학습점과 이미 고른 점까지의 최소 거리)의 곱이 최대인 점을 10회 순차 선택한다. LLM 보조 정책은 u 상위 20개 후보의 설계값·u·d와 학습 데이터의 교차검증 오차를 Claude(claude-sonnet-5-5, 기본 샘플링 온도)에 주고, 선택 ID와 배치 단위 사유 코드를 JSON 스키마 구조화 출력[[anthropic]]으로 받는다. 프롬프트는 불확실도만으로 고르지 말고 거리와 가장 오차가 큰 변수를 함께 고려하라고 지시한다. 결정론적 검증 함수가 후보 포함, 중복, 개수, 근거 길이(400자 이하)를 확인해 하나라도 어기면 그 라운드는 불확실도 정책의 선택을 쓴다."),
    body("LLM이 제공 정보를 쓰는지 보기 위해 같은 환경에서 원래 형식(A), 변수명과 물리 설명을 지운 익명화(B, 사유 코드 목록은 동일), 후보의 (u, d)와 변수별 오차를 섞어 틀리게 보여 준 조건(C), LLM 없이 상위 20개 중 무작위로 고르는 기준선(D)을 다시 실행하였다. B는 물리 지식, C는 제공 수치, D는 상위 20개 안에서의 선택 자체의 역할을 본다. LLM과 D는 상위 20개, 불확실도 정책은 상위 30개에서 고르므로 후보 집합이 다르다. 코드와 실행 기록은 버전과 함께 저장하였으며 심사 후 공개한다."));
} else {
  B.push(body("풀 기반 회고적 능동학습[[settles]](512개 후보의 특성을 미리 계산해 두고 정책이 고른 점만 학습에 사용)으로 모든 정책에 같은 초기 무작위 60점과 예산(10점×6회)을 주고, S2 특징과 RF 역추정 모델로 시드 10개를 반복하였다. RF는 재학습이 빠르고 조정할 하이퍼파라미터가 적다. 무작위와 Sobol 순서[[sobol]]는 학습 모델을 쓰지 않는 기준선이다. 불확실도 정책은 정규화된 설계 변수 p(4차원)에서 S2 특징을 예측하는 순방향 RF(200그루)의 트리 간 표준편차를 평균한 u(p)를 구한다. 그리고 u 상위 30개 후보에서 u(p)와 거리 d(p)의 곱이 최대인 점을 10회 순차 선택한다. d(p)는 학습점과 이미 고른 점까지의 최소 거리이다."),
    body("LLM 보조 정책은 u 상위 20개 후보의 설계값·u·d, 그리고 학습 데이터의 5겹 교차검증으로 얻은 변수별 오차와 가장 오차가 큰 변수를 Claude(claude-sonnet-5-5, 기본 샘플링 온도)에 제공한다. 응답으로 후보 ID 10개와 배치 단위의 사유 코드를 JSON 스키마 구조화 출력[[anthropic]]으로 받는다. 시스템 프롬프트는 불확실도만으로 고르지 말고 거리, 설계값의 분산, 가장 오차가 큰 변수를 함께 고려하라고 지시한다. 결정론적 검증 함수가 ID의 후보 포함 여부, 중복, 개수, 근거 길이(400자 이하)를 확인하고, 하나라도 어기면 그 라운드는 불확실도 정책의 선택을 쓴다."),
    body("LLM이 제공 정보를 쓰는지 보기 위해 같은 환경에서 네 조건을 다시 실행하였다. A는 원래 형식, B는 변수명을 x1–x4로 바꾸고 소자·물리 설명을 뺀 익명화이다(사유 코드 목록은 동일). C는 라운드마다 20개 후보의 (u, d) 쌍을 섞고 변수별 오차를 순환 이동해, 가장 오차가 큰 변수를 항상 틀리게 보여 준다. D는 LLM 없이 상위 20개 중 10개를 무작위로 고른다. B는 물리 지식, C는 제공 수치, D는 상위 20개 안에서 고르는 것 자체의 역할을 본다. LLM과 D는 상위 20개에서, 불확실도 정책은 상위 30개에서 고르므로 후보 집합이 다르다."));
}
if (!REVIEW) { B.push(h2(S.s35),
  body("모든 run은 버전을 고정한 환경(DEVSIM 2.11)에서 별도 프로세스로 실행하고, 설정·물리·메시 해시와 수렴 이력을 기록하였다(GitHub Actions, run당 중앙값 약 46 s). 설계와 run의 1:1 대응, 저장 곡선에서의 특징 재추출, 다른 머신에서의 재계산(상대 차이 10^{−13} 이하)을 확인하였다. 절제 조건은 모두 이전 불확실도 곡선이 그대로 재현되는 같은 환경에서 실행하였다."),
  body("예측은 저장소[[repo]]의 docs/PREDICTIONS*.md에 풀·시험 결과 분석 전(커밋 f542405), 변형 시뮬레이션 전(ae73669), 반복 측정 통제와 RQ3 절제의 실행 전(cb3534b, 기존 결과를 본 뒤 설계)에 적었다. 변화 방향과 통제·절제 예측은 대부분 맞았지만, 오차 크기 예측과 강건성 예측 일부(4.2절의 γ = 0 등)는 빗나갔다. γ = +1과 s_{μ}는 사전 시험(γ = 0)에서 고온 이득이 이 가정에 민감함을 본 뒤 풀 계산 전에 정하였다. 가정 무작위화 학습, 범위 제한 예측, 시나리오별·같은 예산의 S1×2 비교, 잡음 상관의 변수별 해석, 초기 표본 수 민감도, A0의 동등성 판정과 실행 간 선택 겹침, 최소 검출 차이는 사후 분석이다.")); }

// ---------- IV. results
B.push(h1(S.c4), h2(S.s41));
const F3 = () => figure(REVIEW ? "fig3_rq1_v47.png" : "fig3_rq1_robust_v47.png", REVIEW ? 220 : 285,
  R_("그림 3. 역추정 오차(시험 128점, GP): (a) 변수별 S1, S1×2, S2(기본 잡음, 오차 막대: 부트스트랩 95% CI, 괄호: S1×2 대비 S2의 유의한 감소, 점선: 무정보 추정), (b) 두 측정의 잡음 상관 ρ에 따른 평균 오차",
     "그림 3. 역추정 오차(시험 128점, GP): (a) 변수별 S1, S1×2, S2(기본 잡음, 오차 막대: 부트스트랩 95% CI, 괄호: S1×2 대비 S2의 유의한 감소, 점선: 무정보 추정), (b) 두 측정의 잡음 상관 ρ에 따른 평균 오차, (c) 시험 시나리오별 S2 평균 오차(로그축, 점선: S1, 일점쇄선: S1×2, 회색 점선: 무정보 추정, 오른쪽: 직렬저항)."),
  REVIEW ? "Fig. 3. Inverse-estimation error (128 test points, GP): (a) S1, S1×2 and S2 per parameter (nominal noise; error bars: bootstrap 95% CI; bracket: significant reduction of S2 from S1×2; dashed: no-information guess), (b) mean error versus the noise correlation ρ of the two measurements." : null);
const P41 = R_([
  body("423 K 특징의 이득 가운데 약 2/3는 측정 횟수에서 나왔다(그림 3(a)). GP의 MAE_{norm}은 S1 0.112, S1×2 0.086, S2 0.072였다. 반복 측정만으로 오차가 23% 줄어, S1→S2 감소(S2−S1 95% CI [−0.049, −0.031])의 약 2/3를 설명하였다(2배 잡음에서는 약 1/2). 나머지 온도 고유 이득(S2−S1×2 −0.014 [−0.024, −0.006])은 W_{JFET}에 집중되었다(0.079→0.050). N_{pw}·Q_{it,eff}에서는 이득이 검출되지 않았으나, CI는 Cramér–Rao 하한이 예상한 크기도 포함한다. 34차원 통제, 2배 잡음, Ridge, 다른 잡음 실현 4개에서도 결론은 같았다. 같은 DEVSIM 120회에서도 S2(60점)는 0.085로 S1(0.127)과 S1×2(0.096)보다 작았다."),
  body("W_{JFET}에 이득이 집중된 것은 표 1로 설명된다. 300 K에서 W_{JFET}와 s_{μ}는 I_{on}을 같은 방향으로 바꾸므로, 반복 측정은 잡음만 줄일 뿐 근사 공선성을 바꾸지 못한다. 423 K에서는 민감도 비가 바뀌어 새로운 정보가 생긴다. Cramér–Rao 하한의 S2/S1 비도 W_{JFET}(0.38)에서 가장 작았다."),
  body("측정 간 잡음이 상관되면 반복 측정의 이득이 줄었다(그림 3(b)). ρ = 0.5, 0.9에서 S1×2는 0.101, 0.110으로 반복 이득이 절반 이하로 줄거나 거의 사라졌지만, S2는 0.077, 0.075를 유지하였다. 사후에 변수별로 보면 GP의 S2는 W_{JFET}가 좋아졌으나(0.050→0.042) N_{pw}·Q_{it,eff}는 나빠졌다. 반면 온도차를 직접 넣은 S3나 선형 Ridge에서는 N_{pw}도 개선되었다(ρ = 0.9에서 0.105, 0.108)."),
], [
  body("423 K 특징의 이득 가운데 약 2/3는 측정 횟수에서 나왔다. 그림 3(a)에서 GP의 MAE_{norm}은 S1 0.112, S1×2 0.086, S2 0.072였다(S2−S1 95% CI [−0.049, −0.031]). 반복 측정만으로 오차가 23% 줄었고(변수별 비 0.73~0.80, 독립 2회 측정의 기대 0.71), 이는 S1→S2 감소의 약 2/3이다. 2배 잡음에서는 이 비율이 약 1/2이었다. 나머지 온도 고유 이득(S2−S1×2 −0.014 [−0.024, −0.006])은 W_{JFET}에 집중되었다(0.079→0.050, CI [−0.040, −0.017]). N_{pw}(0.124→0.113)와 Q_{it,eff}(0.057→0.052)에서는 이득이 검출되지 않았으나, CI는 Cramér–Rao 하한이 예상한 크기(약 −0.021, −0.010)도 포함한다. 두 측정을 나란히 넣은 34차원 통제(0.091), 2배 잡음, 선형 Ridge, 다른 잡음 실현 4개에서도 결론은 같았다."),
  body("온도 정보는 데이터를 늘리는 것보다 효율적이었다. 같은 DEVSIM 120회에서 S2(60점)는 0.085로, 120점을 쓴 S1(0.127)과 S1×2(0.096)보다 작았다. S1×2의 두 번째 측정은 잡음 실현이므로 시뮬레이션 비용이 S1과 같다. 실행 수를 480회로 늘려도 S1과 S1×2는 0.113, 0.087로 S2(60점)에 미치지 못했다. 잡음이 없으면 S1의 오차도 0.001 미만이었으므로, 오차를 정하는 것은 학습 데이터 양이 아니라 측정 잡음과 변수 간 근사 공선성이다. S2에 남은 평균 절대오차는 W_{JFET} 약 48 nm, N_{pw} 약 4.5×10^{15} cm^{−3}, Q_{it,eff} 약 5×10^{10} cm^{−2}이다."),
  body("W_{JFET}에 이득이 집중된 것은 표 1의 민감도로 설명된다. 300 K에서 W_{JFET}와 s_{μ}는 I_{on}을 같은 방향으로 바꾸므로, 반복 측정은 잡음을 줄일 뿐 둘의 근사 공선성을 바꾸지 못한다. 423 K에서는 민감도 비가 바뀌어 새로운 방향의 정보가 생긴다. Cramér–Rao 하한의 S2/S1 비도 W_{JFET}(0.38)에서 N_{pw}·Q_{it,eff}(0.59, 0.58)보다 작았다. 반면 N_{pw}를 Q_{it,eff}와 구분하는 V_{th} 온도 이동(+20%당 −10.9 mV)은 두 측정 차이의 잡음(14 mV)보다 작다."),
  body("측정 간 잡음이 상관되면 반복 측정의 이득이 줄었다(그림 3(b)). ρ = 0.5, 0.9에서 S1×2는 0.101, 0.110으로 반복 이득이 절반 이하로 줄거나 거의 사라졌지만, S2는 0.077, 0.075를 유지하였다. 사후에 변수별로 보면 GP의 S2는 W_{JFET}가 0.050→0.042로 좋아졌으나 N_{pw}·Q_{it,eff}는 0.113→0.126, 0.052→0.057로 나빠져, 이 두 변수에는 423 K 특징이 주로 반복 측정처럼 작용하였다. 반면 공통 잡음이 상쇄되는 온도차를 직접 넣은 S3(평균 0.064)나 선형 Ridge에서는 N_{pw}도 개선되었다(ρ = 0.9에서 0.105, 0.108). ρ = 0.9에서는 두 측정 차이의 잡음(4.5 mV)이 V_{th} 온도 이동(10.9 mV)보다 작아지므로, 정보는 데이터에 있으나 GP가 S2에서 이를 다 쓰지 못한 것으로 보인다."),
]);
if (PRE("F3")) B.push(...F3(), ...P41); else B.push(...P41, ...F3());
B.push(h2(S.s42));
const T2BLOCK = () => REVIEW
  ? [capT("표 2. 423 K 물리 시나리오별 S2의 평균 MAE_{norm}(기본 잡음, GP, S1 = 0.112, S1×2 = 0.086)"), capT("Table 2. Mean MAE_{norm} of S2 for each 423 K physics scenario (nominal noise, GP; S1 = 0.112, S1×2 = 0.086)."), table(T2W, T2), note("Parentheses: change from S1×2 (^{*}paired-bootstrap 95% CI of S2 − S1×2 excludes 0). Nominal training: γ = +1, r = 0. Bold: worse than S1. ^{†}Post hoc; 423 K data of the 512 pool points drawn at random from the five assumptions (label not an input). ^{‡}0.1–0.3 mΩ·cm^{2} per device, test data only, exploratory (S1 0.378, S1×2 0.405; all above the no-information level 0.25).")]
  : [capT("표 2. 423 K 물리 시나리오별 S2의 평균 MAE_{norm}(기본 잡음, GP, S1 = 0.112, S1×2 = 0.086)"), table(T2W, T2), note("괄호: S1×2 대비 변화. ^{*}S2 − S1×2의 시험점 짝지은 부트스트랩 95% CI가 0을 포함하지 않음. 기준 물리로 학습: γ = +1, r = 0으로 학습. 굵은 값: S1보다 큰 오차. ^{†}512개 풀 점의 423 K 데이터를 다섯 가정에서 무작위로 가져와 학습(사후 분석, 가정 종류는 입력하지 않음). ^{‡}소자별 0.1–0.3 mΩ·cm^{2}, 시험 데이터에만 적용(탐색적; S1 0.378, S1×2 0.405로 모두 무정보 추정 0.25보다 큼).")];
const P42 = R_([
  body("온도 고유 이득은 고온 물리를 알 때만 뚜렷하게 남았다(표 2). 같은 물리로 학습·평가하면 다섯 시나리오 모두 S2가 S1과 S1×2보다 작았다. 그러나 S1×2 대비 감소는 기준 물리의 17%에서 γ = 0, −1의 15%, 12%로 줄었고, γ = −1에서는 세 변수에 고르게 나타났다. r = 0.1, 0.3에서는 423 K V_{th}가 Q_{it,eff}에 비례해 더 이동하므로 N_{pw}·Q_{it,eff}도 크게 개선되었다. 따라서 W_{JFET} 집중은 기준 물리의 결과이다. 데이터시트의 변화폭(V_{th} −0.5 V, R_{DS(on)} +80%)에는 기준 모델(−0.23 V, +44%)보다 r = 0.1(약 −0.47 V)과 γ = −1(약 +71%)이 더 가깝다."),
  body("고온 물리를 틀리게 가정하면 S2는 무너졌다. 기준 물리로 학습한 모델은 γ = 0, −1 데이터에서 0.537, 0.928(범위로 제한하면 0.388, 0.449)로 무정보 추정보다 나빴다. γ가 423 K V_{th}를 +27, +56 mV 옮기는데, 이는 N_{pw}의 온도 이동 신호(−10.9 mV)의 2.5~5배이다. 사전 예측에서는 γ = 0에서도 S2가 S1보다 나을 것으로 보았으나 빗나갔다."),
  body("고온 물리를 모르면 평균 오차에서 반복 측정 이상의 이득이 검출되지 않았다. 다섯 가정을 모두 포함해 학습한 S2(0.079~0.088)는 큰 실패를 피하고 S1보다 22~29% 작았지만, S1×2와의 차이는 통계적으로 검증되지 않았고(시험 물리는 모두 학습에 포함), W_{JFET}의 작은 이득(비 0.80~0.86)만 일부 시나리오에서 남았다. 학습에 없는 직렬저항을 시험 데이터에 넣으면(탐색적) S1, S1×2, S2가 모두 무정보 추정보다 나빴고(0.378, 0.405, 0.261), 특히 전류 특징에 의존하는 W_{JFET} 추정이 무너졌다."),
], [
  body("온도 고유 이득은 고온 물리를 알 때만 뚜렷하게 남았다(표 2, 그림 3(c)). 같은 물리로 학습·평가하면 다섯 시나리오 모두에서 S2가 S1과 S1×2보다 작았다(두 차이의 CI 모두 0 미만). 그러나 크기와 위치는 가정에 따라 달랐다. S1×2 대비 감소는 기준 물리의 17%에서 γ = 0, −1의 15%, 12%로 줄었고, γ = −1에서는 세 변수에 고르게 나타났다(비 0.87~0.89). r = 0.1, 0.3에서는 423 K V_{th}가 Q_{it,eff}에 비례해 더 이동하므로 N_{pw}·Q_{it,eff}도 크게 개선되었다(r = 0.1에서 비 0.67, 0.68). 따라서 W_{JFET} 집중은 기준 물리(γ = +1, r = 0)의 결과이다. 데이터시트의 변화폭(V_{th} −0.5 V, R_{DS(on)} +80%)에는 기준 모델(−0.23 V, +44%)보다 r = 0.1(약 −0.47 V)과 γ = −1(약 +71%)이 더 가깝다."),
  body("고온 물리를 틀리게 가정하면 S2는 무너졌다. 기준 물리로 학습한 모델의 오차는 γ = 0, −1 데이터에서 0.537, 0.928로 S1과 무정보 추정보다 컸고, 예측을 DOE 범위로 제한해도 0.388, 0.449였다. γ는 423 K V_{th}를 +27, +56 mV 옮기는데, 이는 N_{pw}의 온도 이동 신호(+20%당 −10.9 mV)의 2.5~5배이다. g_{m,max}도 20%, 38% 낮아져, 잡음 없는 값 기준으로 시험점의 57%, 100%가 학습 범위 밖에 놓였다. 사전 예측에서는 γ = 0 데이터에도 기준 모델의 S2가 S1보다 나을 것으로 보았으나 빗나갔다."),
  body("고온 물리를 모르면 평균 오차에서 반복 측정 이상의 이득이 검출되지 않았다. 다섯 가정을 모두 포함해 학습한 S2는 0.079~0.088로 큰 실패를 피하고 S1보다 22~29% 작았지만, S1×2(0.086)와의 차이는 다섯 시험 모두 통계적으로 검증되지 않았다(표 2). 시험한 물리는 모두 학습 가정에 포함되었으므로 가정 밖의 고온 물리는 시험하지 않았다. W_{JFET}의 작은 이득(비 0.80~0.86)도 기준과 r 변형에서만 남았다. 따라서 고온 물리를 모르고 측정 잡음이 독립이면, 300 K를 두 번 측정해도 비슷한 정확도를 얻는다."),
  body("직렬저항은 반복 측정으로도, 온도 정보로도 해결되지 않았다(탐색적 분석). 시험 데이터에 소자별 직렬저항을 넣으면 S1, S1×2, S2의 오차가 0.378, 0.405, 0.261로 모두 무정보 추정보다 컸다. 전류 특징에 의존하는 W_{JFET} 추정이 무너졌고(0.864, 0.997, 0.469), V_{th}·SS에 의존하는 N_{pw}·Q_{it,eff}는 반복 측정한 S1×2가 가장 작았다(0.151, 0.067). 실측에 적용하려면 직렬저항을 먼저 보정해야 한다."),
]);
if (PRE("T2")) B.push(...T2BLOCK(), ...P42); else B.push(...P42, ...T2BLOCK());
B.push(h2(S.s43));
const F4 = () => figure("fig4_policies_v47.png", REVIEW ? 220 : 280,
  R_("그림 4. 회고적 풀 평가의 표본 선택 정책 비교(S2, RF, 시드 10개, 같은 환경): (a) 학습곡선(시드 평균, LLM은 재실행 A), (b) 최종 라운드의 짝지은 차이(부트스트랩 95% CI, 오른쪽: 평균 [CI], 왼쪽 항의 우세 시드 수, Top-20 random = D)",
     "그림 4. 회고적 풀 평가의 표본 선택 정책 비교(S2, RF, 시드 10개, 같은 환경): (a) 학습곡선(시드 평균, LLM은 재실행 A), (b) 최종 라운드의 짝지은 차이(부트스트랩 95% CI, 오른쪽: 평균 [CI], 왼쪽 항의 우세 시드 수). LLM은 1차 실행(A0), 재실행(A), 익명화(B), 정보 섞기(C)이고, Top-20 random은 D이다."),
  REVIEW ? "Fig. 4. Retrospective pool-based comparison of sample-selection policies (S2, RF, 10 seeds, same environment): (a) learning curves (seed mean; LLM = rerun A), (b) paired final-round differences (bootstrap 95% CI; right: mean [CI], seeds won by the left term; Top-20 random = D)." : null);
const P43 = body(R_("회고적 풀 평가에서 적응형 선택의 이득은 작았고 Sobol 순서와 비슷하였다(그림 4). 불확실도 정책은 무작위 대비 최종 오차를 0.0025(95% CI [−0.0039, −0.0009]) 줄였고, 무작위의 최종 정확도에 약 106점에서 도달해 시뮬레이션을 약 12% 절감하였다. 초기 표본이 30점이면 절감률은 약 20%였다. Sobol 순서도 무작위 대비 0.0023을 줄여 최종 오차가 같았고(차이 −0.0002 [−0.0013, +0.0009]), 2배 잡음에서는 두 정책 모두 무작위와 차이가 없었다. 따라서 절감의 상당 부분은 후보 다양성으로 설명될 수 있다. 한편 GP는 무작위 60점만으로 0.085에 이르러 어떤 RF 정책(0.124~0.126)보다 정확했다. 이 문제에서는 표본 선택보다 역추정 모델의 선택이 오차에 더 큰 영향을 주었다.",
  "회고적 풀 평가에서 적응형 선택의 이득은 작았고 Sobol 순서와 비슷하였다(그림 4). 불확실도 정책은 무작위 대비 최종 오차를 0.0025(95% CI [−0.0039, −0.0009]) 줄였고, 무작위의 최종 정확도에 약 106점에서 도달해 시뮬레이션을 약 12% 절감하였다. 초기 표본을 30, 90점으로 바꾸면 절감률은 20%, 15%였고, Sobol 순서는 24%, 7%, 9%(초기 30, 60, 90점)였다. Sobol 순서도 무작위 대비 최종 오차를 0.0023 줄여 불확실도 정책과 같았고(차이 −0.0002 [−0.0013, +0.0009]), 2배 잡음에서는 두 정책 모두 무작위와 차이가 없었다. 따라서 절감의 상당 부분은 후보를 고르게 배치한 효과, 즉 후보 다양성으로 설명될 수 있으며 불확실도 정책의 알고리즘적 우수성을 주장하기는 어렵다. 한편 GP는 무작위 60점만으로 0.085에 이르러 어떤 RF 정책(0.124~0.126)보다 정확했다. 이 문제에서는 표본 선택보다 역추정 모델의 선택이 오차에 더 큰 영향을 주었다."));
const F4AT = process.env.ORD_F4 || ORD_DEFAULT.F4;   // pre | post | late (after the first RQ3 paragraph)
if (F4AT === "pre") B.push(...F4(), P43); else if (F4AT === "post") B.push(P43, ...F4()); else B.push(P43);
B.push(h2(S.s44));
const T3BLOCK = () => REVIEW
  ? [capT("표 3. LLM 절제 조건별 최종 오차와 선택 행동(시드 10개)"), capT("Table 3. Final error and selection behaviour of the LLM ablation conditions (10 seeds)."), table(T3W, T3), note("Δ: seed-paired difference from uncertainty sampling (bootstrap 95% CI). A0: first run of A. Overlap: share of the 10 picks within the uncertainty top 10 (random 0.50). Widened: calls whose batch spread along that variable exceeds the displayed top 10 (random expectation in parentheses; C: 59 calls). A, B: shown = true.")]
  : [capT("표 3. LLM 절제 조건별 최종 오차와 선택 행동(시드 10개)"), table(T3W, T3), note("Δ: 불확실도 정책과의 시드 짝지은 차이와 부트스트랩 95% CI. A0: A와 같은 조건의 1차 실행. 겹침: 선택 10개 중 불확실도 상위 10개의 비율(무작위 기대 0.50). 확대: 그 변수 방향의 표준편차가 표시된 상위 10개보다 큰 호출 수(괄호: 무작위 기대, C는 59회). A·B는 표시 = 실제.")];
const P44a = body(R_("LLM 보조 선택의 최종 오차는 어떤 조건에서도 불확실도 정책과 차이가 검출되지 않았다(표 3). LLM 응답은 240회 중 238회 검증을 통과했다(거절은 근거 400자 초과). 다만 이는 두 정책이 같다는 뜻이 아니다. 시드 10개로 검출 가능한 최소 차이(검정력 0.8)는 0.0025~0.0047로 RQ2 효과(0.0025)와 같거나 컸다. 사전에 정한 동등성 기준(90% CI가 ±0.0025 안)도 A만 만족하고 같은 조건의 1차 실행 A0은 만족하지 않았다. 같은 입력을 받은 첫 라운드에서도 두 실행의 선택은 10개 중 평균 8.3개만 겹쳤다.",
  "LLM 보조 선택의 최종 오차는 어떤 조건에서도 불확실도 정책과 차이가 검출되지 않았다(표 3). LLM 응답은 1차 실행(A0) 60회 중 59회, 재실행한 A·B·C에서 60, 60, 59회가 검증을 통과하였다(거절은 모두 근거 400자 초과). 호출 시간(평균 4.7~6.3 s)은 DEVSIM run(중앙값 약 46 s)보다 짧았다. 다만 이는 두 정책이 같다는 뜻이 아니다. 시드 10개로 검출 가능한 최소 차이(검정력 0.8)는 0.0025~0.0047로 RQ2 효과(0.0025)와 같거나 컸다. 사전에 정한 동등성 기준(90% CI가 ±0.0025 안)도 A는 만족했지만 같은 조건의 1차 실행 A0은 만족하지 않았다. 같은 입력을 받은 첫 라운드에서도 두 실행의 선택은 10개 중 평균 8.3개만 겹쳤고, A0과 A의 최종 오차 차이(0.0014)는 조건 간 차이와 같은 크기였다."));
const P44b = body(R_("반면 선택 행동은 제공 정보를 따랐다. 정보를 섞은 C의 선택은 표시된 상위 10개와 64% 겹쳤지만, 실제 상위 10개와는 49%로 무작위와 같았다. 또 틀리게 표시한 최악 변수 방향으로 넓힌 배치가 59회 중 51회였다(무작위 기대 약 30회). 변수명과 물리 설명을 지운 B도 A와 비슷하게 행동하여, 선택은 소자 지식보다 표시된 수치에 의존하였다. 이 행동의 일부는 프롬프트 지시를 따른 결과이다. 사유 코드는 거의 모든 호출에서 여섯 범주 중 같은 다섯 범주가 함께 선택되어, 그 물리적 설명력은 입증되지 않았다. 후보가 이미 불확실도 상위 20개로 걸러진 설정에서는 이 차이가 정확도로 거의 이어지지 않았다. C는 상위 20개 중 무작위인 D와 동등하였고, A가 D보다 작았던 차이(−0.0023)는 1차 실행 A0에서 재현되지 않았다. Gupta 등은 결과를 섞어도 성능이 변하지 않는 것을 LLM이 피드백을 쓰지 않는 근거로 보았다[[gupta]]. 설정은 다르지만 본 실험에서는 성능이 같아도 선택은 정보를 따랐으므로, 성능만으로 정보 사용 여부를 판단하기는 어렵다.",
  "반면 선택 행동은 제공된 정보를 따랐다(표 3). 정보를 섞은 C의 선택은 표시된 불확실도 상위 10개와 64% 겹쳤지만, 실제 상위 10개와는 49%로 무작위(50%)와 같았다. C는 틀리게 표시한 최악 변수 방향으로 범위를 넓힌 배치가 59회 중 51회였다(실제 최악 변수 방향 36회, 무작위 기대 약 30회). 변수명과 물리 설명을 지운 B도 A와 비슷하게 행동하여, 선택은 소자 지식보다 표시된 수치에 의존하였다. 이 행동의 일부는 프롬프트 지시를 따른 결과이다. 사유 코드는 거의 모든 호출에서 여섯 범주 중 같은 다섯 범주가 함께 선택되어, 그 물리적 설명력은 입증되지 않았다. 후보가 이미 불확실도 상위 20개로 걸러진 이 설정에서는 선택의 차이가 정확도로 거의 이어지지 않았다. 정보를 섞은 C는 상위 20개 중 무작위인 D와 동등하였다. A는 D보다 오차가 작았으나(−0.0023 [−0.0043, −0.0004]) 시드 수준 t 구간은 0을 포함하였고, 1차 실행 A0과 D의 차이는 검출되지 않았다. Gupta 등은 실험 결과를 섞어도 성능이 변하지 않는 것을 LLM이 피드백을 쓰지 않는 근거로 보았다[[gupta]]. 본 실험은 수치화된 획득 정보를 섞고 그 사용을 지시했다는 점에서 설정이 다르지만, 성능이 같아도 선택은 정보를 따를 수 있으므로 성능만으로 정보 사용 여부를 판단하기는 어렵다."));
const F4L = () => (F4AT === "late" ? F4() : []);
if (PRE("T3")) B.push(...T3BLOCK(), P44a, ...F4L(), P44b); else B.push(P44a, ...F4L(), ...T3BLOCK(), P44b);

// ---------- V. conclusion
B.push(h1(S.c5));
B.push(body(R_("결과는 세 가지로 요약된다. 첫째, 423 K 특징은 오차를 0.112에서 0.072로 줄였지만, 독립 잡음에서는 그 약 2/3를 300 K 반복 측정으로도 얻었다. 나머지 온도 고유 이득(−0.014 [−0.024, −0.006])은 기준 물리에서 W_{JFET}에 집중되었다. 둘째, 이 이득은 고온 물리를 알 때만 뚜렷하였다. 이동도 지수를 틀리게 가정하면 오차가 0.537, 0.928로 커졌고, 다섯 가정을 모두 포함해 학습하면 이 실패는 피했지만 반복 측정보다 낫다는 통계적 근거는 없었다. 따라서 실측에 적용하려면 고온 물리와 직렬저항을 별도 측정으로 먼저 보정해야 한다. 고온 물리를 모르고 측정 잡음이 독립이면 300 K 반복 측정이 값싼 대안이다. 셋째, 회고적 풀 평가에서 적응형 선택은 시뮬레이션을 12~20% 줄였으나 Sobol 순서와 비슷하여, 이득의 상당 부분은 후보 다양성으로 설명될 수 있다. LLM 보조 선택은 구조화 출력·검증 아래 작동하고(240회 중 238회 통과) 제공된 숫자를 따랐지만, 수치 정책보다 나은 선택이라는 근거는 없었고 사유 코드의 설명력도 입증되지 않았다. 따라서 LLM 선택은 최종 오차와 함께 절제 조건의 선택 행동으로 평가해야 한다.",
  "본 논문은 DEVSIM으로 계산한 4H-SiC MOSFET 특성에서 다중 온도 역추정의 이득을 반복 측정과 분리하고, 고온 물리 가정과 LLM 보조 선택을 함께 평가하였다. 결과는 세 가지로 요약된다. 첫째, 423 K 특징은 오차를 0.112에서 0.072로 줄였지만, 독립 잡음에서는 그 약 2/3를 300 K 반복 측정으로도 얻었다. 나머지 온도 고유 이득(−0.014 [−0.024, −0.006])은 기준 물리에서 W_{JFET}에 집중되었고, 같은 시뮬레이션 예산과 측정 간 잡음 상관에서도 유지되었다. 둘째, 이 이득은 고온 물리를 알 때만 뚜렷하였다. 이동도 지수를 틀리게 가정하면 오차가 0.537, 0.928로 커졌고, 다섯 가정을 모두 포함해 학습하면 이 실패는 피했지만 반복 측정보다 낫다는 통계적 근거는 없었다. 따라서 실측 소자에 적용하려면 고온 물리를 별도 측정으로 먼저 보정하고 직렬저항을 따로 보정해야 한다. 고온 물리를 모르고 측정 잡음이 독립이면 300 K 반복 측정이 값싼 대안이고, 고온 물리를 알고 측정 오차가 측정 간에 상관되면 고온 측정이 더 유리하다. 셋째, 회고적 풀 평가에서 적응형 선택은 무작위보다 시뮬레이션을 12~20% 줄였으나 Sobol 순서와 비슷하여, 이득의 상당 부분은 후보 다양성으로 설명될 수 있다. LLM 보조 선택은 구조화 출력·검증 아래 작동하고(240회 중 238회 통과) 입력을 섞으면 선택도 바뀌었지만, 시드 10개에서 수치 정책보다 나은 선택이라는 근거는 없었고 사유 코드의 설명력도 입증되지 않았다. 따라서 LLM 선택은 최종 오차만이 아니라 절제 조건에서의 선택 행동으로 함께 평가해야 한다.")));
B.push(body(R_("모든 결과는 단극성 2차원 구조 하나와 특징에 더한 정규 잡음 가정(주 분석은 독립 잡음)에서 얻었고 실측으로 검증하지 않았다. Q_{it,eff}를 정적 전하로 두어 SS로 N_{pw}와 Q_{it,eff}를 구분하는 결과는 이 모델에 한정되며, 에피 도핑은 고정하였다. 능동학습과 LLM 선택은 미리 계산한 후보 풀에서 회고적으로 평가하였고(RF 역추정), LLM 결과는 한 모델과 시드 10개로 얻었다.",
  "모든 결과는 단극성 2차원 half-cell 한 구조와 특징에 더한 정규 잡음 가정(주 분석은 독립 잡음)에서 얻었고 실측 곡선으로 검증하지 않았다. Q_{it,eff}를 정적 전하로 두어 SS가 Q_{it,eff}에 반응하지 않으므로, SS로 N_{pw}와 Q_{it,eff}를 구분하는 결과는 이 모델에 한정된다. 에피 도핑은 고정하였고 항복 특성은 다루지 않았다. 능동학습과 LLM 선택은 미리 계산한 후보 풀에서 회고적으로 평가하였고(RF 역추정), LLM 결과는 한 모델(claude-sonnet-5-5)과 시드 10개로 얻었다. 향후에는 실측 다중 온도 곡선으로 고온 물리를 보정한 뒤 역추정을 검증하고, 표본 선택은 DEVSIM을 실제로 돌리는 온라인 방식으로, LLM은 측정 온도·바이어스나 물리 가정처럼 수치 규칙이 없는 결정에서 평가할 계획이다.")));


// ----- references (only those cited, in citation order)
B.push(h1(S.refs));
for (const k of ORDER) {
  B.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 340, hanging: 340 }, spacing: { line: REVIEW ? 190 : 210 },
    children: runs(`[${ORDER.indexOf(k) + 1}] ${REFDB[k]}`, { size: 14 }) }));
}

// ------------------------------------------------------------------ document
const page = { size: { width: 11906, height: 16838 }, margin: { top: 1417, bottom: 1417, left: 1134, right: 1134 } };
const meta = REVIEW
  ? { creator: "Anonymous", lastModifiedBy: "Anonymous", title: titleKR, description: "Manuscript for written review (anonymized)" }
  : { creator: "이민석", lastModifiedBy: "이민석", title: titleKR, description: "Proceedings manuscript" };
const doc = new Document({
  ...meta,
  styles: { default: { document: { run: { font: FONT, size: 18 } } } },
  sections: [
    { properties: { page, column: { count: 1 } }, children: head },
    { properties: { type: SectionType.CONTINUOUS, page, column: { count: 2, space: 397, equalWidth: true } }, children: B },
  ],
});
const out = process.env.OUT || (REVIEW ? "review_v49_4p.docx" : "proceedings_v49_5p.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(path.isAbsolute(out) ? out : path.join(__dirname, out), buf); console.log("wrote", out, "| refs:", ORDER.length); });
