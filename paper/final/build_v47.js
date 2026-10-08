// Manuscript V4.7 builder (V4.6 + repeated-measurement control S1x2 + RQ3 ablation; results: docs/V47_RESULTS.md).
//   NODE_PATH=<global node_modules> node build_v47.js proc    -> 5-page proceedings version (IEIE conference layout, author block)
//   NODE_PATH=<global node_modules> node build_v47.js review  -> 4-page written-review version (IEIE journal layout, anonymous)
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
  ha: "J. Ha, G. Lee, and J. Kim, “Machine learning approach for characteristics prediction of 4H-silicon carbide NMOSFET by process conditions,” in ~~Proc. IEEE Region 10 Symp. (TENSYMP)~~, 2021.",
  ha2022: REVIEW
    ? "J. Ha et al., “Deep learning approach for characteristics prediction of nanowire FETs by process condition,” ~~J. Inst. Electron. Inf. Eng.~~, vol. 59, no. 12, pp. 29–37, Dec. 2022."
    : "하종현, 이경엽, 서민기, 방민지, 김태형, 김정식, “심층신경망을 이용한 Nanowire FETs의 공정 조건 특성 예측,” ~~전자공학회논문지~~, 제59권, 제12호, 29–37쪽, 2022년 12월.",
  agentic: "G. Fan, T. Ma, X. Sun, X. Wang, K. L. Low, and L. Shao, “AgenticTCAD: A LLM-based multi-agent framework for automated TCAD code generation and device optimization,” in ~~Proc. Design, Automation and Test in Europe Conf. (DATE)~~, 2026.",
  devsim: "J. E. Sanchez, “DEVSIM: A TCAD semiconductor device simulator,” ~~J. Open Source Softw.~~, vol. 7, no. 70, p. 3898, 2022.",
  sg: "D. L. Scharfetter and H. K. Gummel, “Large-signal analysis of a silicon Read diode oscillator,” ~~IEEE Trans. Electron Devices~~, vol. 16, no. 1, pp. 64–77, Jan. 1969.",
  ikeda: "M. Ikeda, H. Matsunami, and T. Tanaka, “Site effect on the impurity levels in 4H, 6H, and 15R SiC,” ~~Phys. Rev. B~~, vol. 22, no. 6, pp. 2842–2854, Sep. 1980.",
  roschke: "M. Roschke and F. Schwierz, “Electron mobility models for 4H, 6H, and 3C SiC,” ~~IEEE Trans. Electron Devices~~, vol. 48, no. 7, pp. 1442–1447, Jul. 2001.",
  burin: "J. Burin, P. Gaggl, S. Waid, A. Gsponer, and T. Bergauer, “TCAD parameters for 4H-SiC: A review,” arXiv:2410.06798, 2025.",
  cree: "Cree, Inc., ~~C2M0080120D Silicon Carbide Power MOSFET Data Sheet~~, Rev. D, 2019.",
  yu: "S. Yu, M. H. White, and A. K. Agarwal, “Experimental determination of interface trap density and fixed positive oxide charge in commercial 4H-SiC power MOSFETs,” ~~IEEE Access~~, vol. 9, pp. 149118–149124, 2021.",
  keysight: "Keysight Technologies, ~~B1505A Power Device Analyzer/Curve Tracer Data Sheet~~.",
  gp: "C. E. Rasmussen and C. K. I. Williams, ~~Gaussian Processes for Machine Learning~~, MIT Press, 2006.",
  settles: "B. Settles, “Active learning literature survey,” Comput. Sci. Tech. Rep. 1648, Univ. of Wisconsin–Madison, 2009.",
  sobol: "I. M. Sobol’, “On the distribution of points in a cube and the approximate evaluation of integrals,” ~~USSR Comput. Math. Math. Phys.~~, vol. 7, no. 4, pp. 86–112, 1967.",
  anthropic: "Anthropic, “Structured outputs,” Claude Platform Documentation, https://platform.claude.com/docs/en/build-with-claude/structured-outputs (accessed Oct. 2026).",
  repo: "M. Lee, “sic-mosfet-devsim: simulation code, configurations and results of this study,” GitHub repository, https://github.com/mseokq23/sic-mosfet-devsim, 2026.",
  tsibizov: "A. Tsibizov, R. Stark, and U. Grossner, “Temperature dependence of on-state inter-terminal capacitances (C_{gd} and C_{gs}) of SiC MOSFETs and frequency limitations of their measurements,” arXiv:2107.10408, 2021.",
  mehta: "K. Mehta, S. S. Raju, M. Xiao, B. Wang, Y. Zhang, and H. Y. Wong, “Improvement of TCAD augmented machine learning using autoencoder for semiconductor variation identification and inverse design,” ~~IEEE Access~~, vol. 8, pp. 143519–143529, 2020.",
  ong: "E. K. J. Ong, L. M. L. Nguyen, M. Eng, Y. Zhang, and H. Y. Wong, “Ga_{2}O_{3} TCAD mobility parameter calibration using simulation augmented machine learning with physics-informed neural network,” ~~IEEE Trans. Electron Devices~~, vol. 73, no. 2, pp. 775–781, Feb. 2026.",
  gupta: "R. Gupta, J. Hartford, and B. Liu, “LLMs for Bayesian optimization in scientific domains: Are we there yet?,” in ~~Findings Assoc. Comput. Linguist.: EMNLP 2025~~, pp. 15482–15510, 2025.",
};

const titleKR = "DEVSIM 기반 4H-SiC 평판형 MOSFET 공정 결과 파라미터의 다중 온도 역추정과 LLM 보조 실험 선택 평가";
const titleEN = "Multi-Temperature Inverse Estimation of Process-Outcome Parameters and Evaluation of LLM-Assisted Experiment Selection for 4H-SiC Planar MOSFETs Using DEVSIM";
const ABS_EN = "This paper uses the open-source TCAD tool DEVSIM to estimate three latent process-outcome parameters of a 4H-SiC planar MOSFET (JFET width, P-well doping and effective interface charge) from DC characteristics simulated at 300 K and 423 K, with channel mobility varied as an unestimated nuisance parameter. With measurement noise on the features, adding the 423 K features lowered the normalized error of a Gaussian-process inverse model from 0.112 to 0.072. Measuring the 300 K features twice gave 0.086, so under independent noise about two thirds of the gain came from the second measurement; the gain specific to temperature was concentrated in the JFET width (0.079 to 0.050) and was not detected for the other two parameters. With correlated noise between the two measurements, the repeat gain vanished but the 423 K gain remained. When the 423 K data were re-simulated with channel-mobility temperature exponents of 0 and −1, models trained on the same exponent kept a 35% and 32% reduction, whereas a model trained with the nominal exponent gave errors of 0.54 and 0.93. Uncertainty sampling needed 12–20% fewer simulations than random sampling, similar to a Sobol sequence. An LLM-assisted selector followed the numbers it was shown, but its final error was indistinguishable from that of uncertainty sampling whether its input was intact, anonymized or shuffled.";
const ABS_EN_REVIEW = "This paper uses DEVSIM to estimate three latent process-outcome parameters of a 4H-SiC planar MOSFET (JFET width, P-well doping and effective interface charge) from DC characteristics simulated at 300 K and 423 K. With measurement noise on the features, adding the 423 K features lowered the normalized error of a Gaussian-process inverse model from 0.112 to 0.072. Measuring the 300 K features twice gave 0.086, so about two thirds of the gain came from the extra measurement; the temperature-specific gain was concentrated in the JFET width. With correlated noise, the repeat gain vanished but the 423 K gain remained. A model trained with the nominal channel-mobility temperature exponent gave errors of 0.54 and 0.93 on data re-simulated with exponents of 0 and −1. Uncertainty sampling needed 12–20% fewer simulations than random sampling, similar to a Sobol sequence. An LLM-assisted selector followed the numbers it was shown, but its final error was indistinguishable from that of uncertainty sampling with intact, anonymized or shuffled input.";
const ABS_KR = "DEVSIM으로 4H-SiC 평판형 MOSFET의 300 K·423 K DC 특성을 계산하고, 이 특성으로 JFET 폭, P-well 도핑, 유효 계면전하를 역추정하였다. 특징에 측정 잡음을 넣었을 때 423 K 특징을 함께 쓰면 가우시안 과정 역추정의 정규화 오차가 0.112에서 0.072로 줄었다. 300 K 특징을 두 번 측정한 통제는 0.086이어서 독립 잡음에서는 이득의 약 2/3가 측정 횟수에서 나왔고, 온도 고유 이득은 JFET 폭(0.079→0.050)에 집중되었다. 두 측정의 잡음이 상관되면 반복 측정의 이득은 사라졌으나 423 K의 이득은 남았다. 그러나 423 K 데이터를 채널 이동도 온도지수 0, −1로 다시 계산하면 기준 지수(+1)로 학습한 모델의 오차가 0.537, 0.928로 커졌다. 불확실도 선택은 무작위보다 시뮬레이션을 12~20% 줄였으나 Sobol 순서와 비슷하였고, LLM 보조 선택은 제공된 수치를 따랐지만 정보를 지우거나 섞어도 최종 오차는 불확실도 선택과 구분되지 않았다.";

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
const T2 = REVIEW ? [
  ["423 K physics of test data", "Matched training", "S2−S1 (95% CI)", "Nominal training", "Randomized training^{†}"],
  ["Baseline (γ = +1, r = 0)", "0.072", "[−0.049, −0.031]", "—", "0.082"],
  ["γ = 0", "0.073", "[−0.048, −0.030]", "**0.537**", "0.083"],
  ["γ = −1", "0.076", "[−0.045, −0.026]", "**0.928**", "0.088"],
  ["r = 0.1", "0.057", "[−0.065, −0.046]", "0.084", "0.079"],
  ["r = 0.3", "0.033", "[−0.091, −0.068]", "**0.132**", "0.080"],
  ["Series R^{*}", "—", "—", "**0.261**", "—"],
] : [
  ["시험 데이터의 423 K 물리", "같은 물리로 학습", "S2−S1 (95% CI)", "기준 물리로 학습", "가정 무작위화 학습^{†}"],
  ["기준(γ = +1, r = 0)", "0.072", "[−0.049, −0.031]", "—", "0.082"],
  ["γ = 0", "0.073", "[−0.048, −0.030]", "**0.537**", "0.083"],
  ["γ = −1", "0.076", "[−0.045, −0.026]", "**0.928**", "0.088"],
  ["r = 0.1", "0.057", "[−0.065, −0.046]", "0.084", "0.079"],
  ["r = 0.3", "0.033", "[−0.091, −0.068]", "**0.132**", "0.080"],
  ["기생 직렬저항^{*}", "—", "—", "**0.261**", "—"],
];
const T1W = [1300, 830, 830, 830, 830];
const T2W = [1260, 680, 1100, 800, 780];

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


// ------------------------------------------------------------------ body (V4.7: + repeated-measurement control S1x2, + RQ3 ablation)
const B = [];
const ORD_DEFAULT = REVIEW ? { F2: "post", F3: "post", T2: "pre", F4: "post" } : { F2: "post", F3: "post", T2: "post", F4: "mid" };  // placement chosen by a layout search (ORD_F2/F3/T2/F4=pre|post, F4 also mid)
const PRE = (k) => (process.env["ORD_" + k] || ORD_DEFAULT[k]) === "pre";
const R_ = (review, proc) => (REVIEW ? review : proc);
const S = REVIEW
  ? { c1: "Ⅰ. 서  론", c2: "Ⅱ. 시뮬레이션 모델 및 검증", s21: "1. 소자 구조와 물리 모델", s22: "2. 추정 파라미터와 특징", s23: "3. 모델 검증",
      c3: "Ⅲ. 실험 설계 및 역추정", s31: "1. 민감도 분석", s32: "2. 데이터, 잡음 모델과 역추정", s33: "3. 강건성 시험", s34: "4. 적응형 표본 선택",
      c4: "Ⅳ. 결과 및 고찰", s41: "1. 다중 온도 특징의 효과(RQ1)", s42: "2. 고온 물리 가정에 대한 강건성(RQ1)", s43: "3. 적응형 선택의 효과(RQ2)", s44: "4. LLM 보조 선택(RQ3)",
      c5: "Ⅴ. 결  론", refs: "REFERENCES" }
  : { c1: "Ⅰ. 서론", c2: "Ⅱ. 시뮬레이션 모델 및 검증", s21: "2.1 소자 구조와 물리 모델", s22: "2.2 추정 파라미터와 특징", s23: "2.3 모델 검증",
      c3: "Ⅲ. 실험 설계 및 역추정", s31: "3.1 민감도 분석", s32: "3.2 데이터, 잡음 모델과 역추정", s33: "3.3 강건성 시험", s34: "3.4 적응형 표본 선택", s35: "3.5 계산 환경과 재현성",
      c4: "Ⅳ. 결과 및 고찰", s41: "4.1 다중 온도 특징의 효과(RQ1)", s42: "4.2 고온 물리 가정에 대한 강건성(RQ1)", s43: "4.3 적응형 선택의 효과(RQ2)", s44: "4.4 LLM 보조 선택(RQ3)",
      c5: "Ⅴ. 결론", refs: "참고문헌" };

// ---------- I. introduction
B.push(h1(S.c1));
if (REVIEW) {
  B.push(body("4H-SiC MOSFET은 고전압·고온 전력 변환에 널리 쓰이지만[[baliga,kimoto]], JFET 폭, P-well 도핑, SiO_{2}/SiC 계면전하 같은 공정 결과의 편차는 문턱전압(V_{th})과 온저항(R_{on,sp})을 함께 바꾼다. P-well 도핑 증가와 음의 계면전하 증가는 모두 V_{th}를 높이고 JFET 폭 증가와 채널 이동도 증가는 모두 전류를 늘리므로, 측정 특성만으로 원인을 역추정하기 어렵다. 온도는 이 혼동을 푸는 데 오래 쓰여 온 정보로, 고온의 V_{th} 감소는 측정 소자에서 계면 트랩 밀도의 지표로 쓰이고[[yu]] 채널 저항은 JFET·드리프트 저항보다 온도 의존성이 약하다[[tsibizov]]. 한편 TCAD는 계산 비용이 커서 효율적인 실험 설계가 필요하고, 대규모 언어 모델(LLM)을 실험 계획에 쓰려는 시도도 있다[[boiko]]."),
    body("Müting 등은 상용 1.2 kV SiC MOSFET에 보정한 TCAD로 공정 편차의 영향을 평가했고[[muting]], TCAD 데이터로 공정 조건에서 특성을 예측하거나[[ha]] 전기적 특성으로부터 소자·공정 파라미터를 역추정한 기계학습[[ha2022,mehta]], 여러 온도의 측정으로 TCAD 이동도를 보정한 연구[[ong]], LLM 에이전트로 TCAD 코드를 생성하는 연구[[agentic]]도 보고되었다. 그러나 TCAD로 학습한 역추정은 학습에 없는 물리에 취약하고[[mehta]], 다중 온도 특징의 이득이 같은 소자를 한 번 더 측정한 효과와 어떻게 다른지, 고온 물리 가정이 틀리면 어떻게 되는지를 같은 조건에서 비교한 연구는 찾지 못했다. LLM 기반 실험 선택이 수치적 방법보다 낫지 않다는 보고도 있다[[gupta]]."),
    body("해석에는 공개형 TCAD인 DEVSIM[[devsim]]을 사용하였고, 다음 세 가지를 확인하였다. RQ1은 423 K 특성을 더했을 때 역추정 오차가 얼마나 줄고, 그 이득 가운데 반복 측정으로 설명되지 않는 부분은 무엇이며, 423 K 물리 가정에 따라 어떻게 달라지는지, RQ2는 적응형 표본 선택이 무작위·Sobol 표본보다 시뮬레이션 수를 줄이는지, RQ3는 LLM 보조 선택이 수치적 불확실도 선택보다 나은지와 LLM이 제공 정보를 쓰는지이다. RQ3에는 두 정책의 차이가 없다는 귀무가설을 두었고, 주 분석과 강건성·통제·절제 시험의 예상 결과는 해당 분석이나 시뮬레이션 전에 저장소 문서에 기록하였다. 직렬저항 시험은 탐색적 분석이고 가정 무작위화 학습은 사후 분석이다. 항복과 장기 신뢰성은 다루지 않았다."));
} else {
  B.push(body("4H-SiC MOSFET은 넓은 밴드갭과 높은 임계전계 덕분에 고전압·고온 전력 변환에 널리 쓰인다[[baliga,kimoto]]. 그러나 JFET 폭, P-well 도핑, SiO_{2}/SiC 계면전하 같은 공정 결과의 편차는 문턱전압(V_{th})과 온저항(R_{on,sp})을 함께 바꾸고, 서로 다른 원인이 같은 전기적 변화를 만들기 때문에 측정 특성만으로 원인을 역추정하기 어렵다. P-well 도핑 증가와 음의 계면전하 증가는 모두 V_{th}를 높이고, JFET 폭 증가와 채널 이동도 증가는 모두 전류를 늘린다."),
    body("온도는 이러한 혼동을 푸는 데 오래 쓰여 온 정보이다. 고온의 V_{th} 감소는 측정 소자에서 계면 트랩 밀도의 지표로 쓰이고[[yu]], 채널 저항은 JFET·드리프트 저항보다 온도 의존성이 약하다[[tsibizov]]. 드리프트층의 벌크 이동도는 온도가 오르면 감소하는 반면 채널 이동도의 온도 의존성은 계면 상태에 따라 달라지기 때문이다[[kimoto]]. 한편 TCAD는 계산 비용이 커서 다변수·다중 온도 실험을 효율적으로 설계할 방법이 필요하며, 대규모 언어 모델(LLM)을 실험 계획에 활용하려는 시도도 있다[[boiko]]."),
    body("Müting 등은 상용 1.2 kV SiC MOSFET에 보정한 TCAD로 공정 단계별 편차의 영향을 평가하여 에피 도핑과 계면 트랩 밀도가 소자 간 편차에 가장 중요함을 보였다[[muting]]. TCAD 데이터로 공정 조건에서 4H-SiC MOSFET 특성을 예측하거나[[ha]] 전기적 특성으로부터 소자·공정 파라미터를 역으로 예측한 기계학습[[ha2022,mehta]], 여러 온도의 측정 곡선으로 TCAD 이동도 파라미터를 보정한 연구[[ong]], LLM 에이전트가 TCAD 코드를 생성해 소자를 최적화하는 연구[[agentic]]도 보고되었다. 그러나 TCAD로 학습한 역추정은 학습에 없는 물리에 취약하며[[mehta]], 다중 온도 특징의 이득이 같은 소자를 한 번 더 측정한 효과와 어떻게 다른지, 고온 물리 가정이 틀렸을 때 어떻게 되는지를 같은 조건에서 비교한 연구는 찾지 못했다. LLM 기반 실험 선택은 수치적 방법보다 낫지 않다는 보고도 있어[[gupta]], 본 논문은 LLM을 다음에 계산할 시뮬레이션 후보를 고르는 데만 쓰고 그 출력을 결정론적 검증기로 거른 뒤 수치적 선택 규칙 및 절제 조건과 비교하였다."),
    body("해석에는 공개형 TCAD인 DEVSIM[[devsim]]을 사용해 4H-SiC 평판형 MOSFET의 2차원 DC 해석 흐름을 만들었고, 이를 이용해 세 가지를 확인하였다. RQ1은 300 K 특성에 423 K 특성을 더했을 때 역추정 오차가 얼마나 줄고, 그 이득 가운데 반복 측정으로 설명되지 않는 부분은 무엇이며, 423 K 물리 가정에 따라 어떻게 달라지는지이다. RQ2는 적응형 표본 선택이 무작위나 Sobol 표본보다 필요한 시뮬레이션 수를 줄이는지, RQ3는 LLM 보조 선택이 수치적 불확실도 선택보다 나은지와 LLM이 제공 정보를 실제로 쓰는지이다. 이를 통해 다중 온도 특징의 이득을 반복 측정 이득과 온도 고유 이득으로 나누어 고온 물리 가정 불일치의 위험과 함께 정량화하고, 검증기로 제한한 LLM 표본 선택을 절제 실험으로 평가한다. RQ3에는 두 정책의 차이가 없다는 귀무가설을 두었고, 주 분석과 강건성·통제·절제 시험의 예상 결과는 해당 분석이나 시뮬레이션 전에 저장소 문서에 기록하였다(3.5절). 직렬저항 시험은 탐색적 분석이고 가정 무작위화 학습은 사후 분석이다. 항복과 장기 신뢰성은 다루지 않았다."));
}

// ---------- II. model
B.push(h1(S.c2), h2(S.s21));
B.push(body(R_("그림 1(a)의 half-cell은 1.2 kV급 설계를 참고한 평판형 구조로, 게이트 산화막 50 nm, P-well 1×10^{17} cm^{−3}, JFET 영역 2×10^{16} cm^{−3}, 드리프트층 10 µm·1×10^{16} cm^{−3}이다. Poisson 방정식과 전자 연속방정식을 Scharfetter–Gummel 이산화[[sg]]로 풀고, 불완전 이온화(N 66 meV, Al 191 meV)[[ikeda]], 도핑·온도 의존 이동도[[roschke]], SRH 재결합을 포함하였으며 물성값은 문헌 고찰[[burin]]을 따랐다. 채널 이동도는 벌크와 표면 성분을 결합한 식 (1), (2)로 두었다.",
  "그림 1(a)의 half-cell은 1.2 kV급 설계를 참고한 평판형 구조로, 게이트 산화막 50 nm, P-well 1×10^{17} cm^{−3}, JFET 영역 2×10^{16} cm^{−3}, 드리프트층 10 µm·1×10^{16} cm^{−3}, half-pitch 3.5 µm, 채널 길이 0.5 µm이다. Poisson 방정식과 전자 연속방정식을 Scharfetter–Gummel 이산화[[sg]]로 풀고, 불완전 이온화(N 66 meV, Al 191 meV)[[ikeda]], 도핑·온도 의존 전자 이동도[[roschke]], SRH 재결합을 포함하였으며 물성값은 문헌 고찰[[burin]]을 따랐다. 채널의 전자 이동도는 벌크 성분과 표면 성분을 Matthiessen 규칙으로 결합하여 식 (1), (2)로 두었다.")));
B.push(equation("μ_{n}^{−1} = μ_{bulk}^{−1}(N, T) + e^{−y/λ} μ_{surf}^{−1}(T)", 1));
B.push(equation("μ_{surf}(T) = 20 s_{μ}(T/300 K)^{γ} cm^{2}/V·s, γ ∈ {+1, 0, −1}", 2));
B.push(body(R_("여기서 y는 계면으로부터의 거리, λ = 3 nm, s_{μ}(0.8~1.2)는 추정하지 않는 채널 이동도 배율(교란 변수)이다. 식 (2)의 계수 20 cm^{2}/V·s와 λ = 3 nm는 가정값이다. 기준 모델은 γ = +1이며 γ = 0, −1은 강건성 시험에만 쓴다. 계면은 면전하 σ = q[Q_{f} + Q_{it,eff}(T)](가정값 Q_{f} = 1×10^{12} cm^{−2}, 고정)로 두었고, 기준 모델에서 Q_{it,eff}는 온도와 무관하다. 강건성 시험에서는 그 크기가 고온에서 줄어드는 경우를 식 (3)으로 검토한다.",
  "여기서 y는 계면으로부터의 거리, λ = 3 nm, s_{μ}는 0.8~1.2의 채널 이동도 배율(교란 변수)이다. 식 (2)의 계수 20 cm^{2}/V·s와 λ = 3 nm는 가정값이다. 기준 모델은 γ = +1(300–423 K에서 증가)이며, γ = 0, −1은 4.2절의 강건성 시험에만 쓴다. 계면에는 가정값인 고정전하 Q_{f} = 1×10^{12} cm^{−2}와 유효 계면전하 Q_{it,eff}를 면전하 σ = q[Q_{f} + Q_{it,eff}(T)]로 두었다. 기준 모델에서 Q_{it,eff}는 온도와 무관하며, 강건성 시험에서는 그 크기가 고온에서 줄어드는 경우를 식 (3)으로 검토한다.")));
B.push(equation("Q_{it,eff}(T) = Q_{it,eff}(300)·[1 − r(T − 300)/123]", 3));
B.push(body(R_("T의 단위는 K이고 r ∈ {0, 0.1, 0.3}이다. Q_{it,eff}는 음수이므로 식 (3)은 그 절댓값을 줄이며, 모든 설계점에 같은 r을 적용한다. 추정 대상은 300 K에서 정의한 Q_{it,eff}이고 r은 역추정 모델에 주지 않는다. 정공은 소스/바디와 평형으로 두는 단극성 근사를 썼다. 423 K에서도 접합 생성전류(2×10^{−16} A/cm^{2} 이하)는 특징 추출의 최소 전류(약 3×10^{−7} A/cm^{2})보다 9자릿수 이상 작고, V_{DS} ≤ 5 V에서 충돌 이온화는 무시된다.",
  "T의 단위는 K이고 r ∈ {0, 0.1, 0.3}이다. Q_{it,eff}는 음수이므로 식 (3)은 그 절댓값을 줄인다. Q_{f}는 온도와 무관하게 고정하고 모든 DOE 점에 같은 r을 적용하며, 추정 대상은 300 K에서 정의한 Q_{it,eff}이고 r은 역추정 모델에 입력하지 않는다. 정공은 소스/바디와 평형으로 두는 단극성 근사를 사용하였다. 423 K에서도 접합 생성전류(2×10^{−16} A/cm^{2} 이하)는 특징 추출의 최소 전류(약 3×10^{−7} A/cm^{2})보다 9자릿수 이상 작고, 바디 다이오드는 역바이어스이며 V_{DS} ≤ 5 V에서 충돌 이온화는 무시된다.")));
B.push(h2(S.s22));
B.push(body(R_("추정 대상은 공정 결과를 나타내는 잠재 파라미터 θ = (W_{JFET}, N_{pw}, Q_{it,eff})이며, 기준값과 범위는 표 1에 함께 정리하였다. 소자 간 편차에 중요한 에피 도핑[[muting]]은 고정하였다. W_{JFET} 편차는 마스크 피치를 고정한 채 자기정렬 경계가 이동하는 것으로 정의하였다. 각 온도에서 V_{DS} = 0.1 V 전달 특성과 V_{GS} = 18 V 출력 특성을 계산하고, 특징 벡터 x_{T}를 6개 스칼라(V_{th}(1×10^{−4} A/cm 정전류), SS(10^{−10}~10^{−6} A/cm), log g_{m,max}, log I_{on}, log R_{on,sp}, log I_{D}(V_{DS} = 2 V))와 11개 전달곡선 표본 log I_{D}(V_{GS} = 4~20 V)로 구성하였다. 전류는 2차원 단면의 단위 폭당 값(A/cm)이다. 특징 집합은 S1 = x_{300}(17차원), S2 = [x_{300}, x_{423}](34차원), S3 = [S2, x_{423} − x_{300}](51차원)이다.",
  "추정 대상은 공정 결과를 나타내는 잠재 파라미터 θ = (W_{JFET}, N_{pw}, Q_{it,eff})이고, 채널 이동도 배율 s_{μ}는 모든 설계에서 변하지만 추정하지 않는다. 각 변수의 기준값과 범위는 표 1에 함께 정리하였다. 소자 간 편차에 중요한 에피 도핑[[muting]]은 고정하였다. W_{JFET} 편차는 마스크 피치를 고정한 채 자기정렬된 P-well/n^{+} 경계가 이동하는 것으로 정의하여 채널 길이와 면적 정규화를 유지하였다. 각 온도 T에서 V_{DS} = 0.1 V 전달 특성과 V_{GS} = 18 V 출력 특성을 계산하고, 특징 벡터 x_{T}를 6개 스칼라와 11개 전달곡선 표본으로 구성하였다. 전류는 2차원 단면의 단위 폭당 값(A/cm)이다. 스칼라는 V_{th}(1×10^{−4} A/cm 정전류), SS(10^{−10}~10^{−6} A/cm 구간), log g_{m,max}, log I_{on}(V_{GS} = 18 V), log R_{on,sp}(V_{DS} ≤ 0.5 V 기울기), log I_{D}(V_{DS} = 2 V)이고, 표본은 V_{GS} = 4, 5, 6, 7, 8, 10, 12, …, 20 V에서의 log I_{D}이다. 특징 집합은 S1 = x_{300}(17차원), S2 = [x_{300}, x_{423}](34차원), S3 = [S2, x_{423} − x_{300}](51차원)이다. V_{th}와 SS는 목표 전류에서 바이어스를 다시 풀어 격자 보간 오차를 제거하였다.")));
B.push(h2(S.s23));
const F2 = () => figure("fig2_validation.png", REVIEW ? 220 : 280, R_("그림 2. 시뮬레이션 검증: (a) 전달 특성(V_{DS} = 0.1 V, 점: V_{th}), (b) 출력 특성(V_{GS} = 18 V), (c) fine 메시 대비 드레인 전류 차이(300 K), (d) Q_{it,eff}에 따른 V_{th} 이동과 해석해",
  "그림 2. 시뮬레이션 검증: (a) 전달 특성(V_{DS} = 0.1 V, 점: V_{th}), (b) 출력 특성(V_{GS} = 18 V), (c) fine 메시 대비 드레인 전류 차이(300 K), (d) Q_{it,eff}에 따른 V_{th} 이동과 해석해."),
  REVIEW ? "Fig. 2. Model verification: (a) transfer characteristics (V_{DS} = 0.1 V), (b) output characteristics (V_{GS} = 18 V), (c) drain-current difference from the fine mesh (300 K), (d) V_{th} shift versus Q_{it,eff} with the analytic line." : null);
const P23 = body(R_("1차원 PN 다이오드의 내장전위·불완전 이온화율과 MOS 커패시터의 평탄대 전압은 해석해와 5 mV 이내로 일치하였다. 그림 2에서 300 K→423 K에 V_{th}는 3.765→3.530 V, SS는 112.5→155.7 mV/dec, R_{on,sp}는 2.00→2.87 mΩ·cm^{2}로 변하였다. 사용한 메시(1.1만 노드)는 fine 메시 대비 V_{th} 0.07 mV, R_{on,sp} 0.9% 이내였고, Q_{it,eff}에 따른 V_{th} 이동은 −qΔQ_{it}/C_{ox}와 1 mV 이내로 일치하였다. 상용 1.2 kV 소자[[cree]]의 25→150 °C 변화(V_{th} 2.9→2.4 V, R_{DS(on)} 80→144 mΩ)와 방향은 같지만 본 모델의 변화폭(0.23 V, 44%)은 더 작다. 측정 소자에서 나타나는 고온 계면 트랩 전자 방출[[yu]]은 넣지 않았으며, 이 가정을 바꾼 계산은 4장 2절에 있다.",
  "1차원 PN 다이오드의 내장전위·불완전 이온화율과 MOS 커패시터의 평탄대 전압을 해석해와 비교해 5 mV 이내로 일치함을 확인하였다. 그림 2의 MOSFET에서 300 K→423 K에 V_{th}는 3.765→3.530 V, SS는 112.5→155.7 mV/dec, R_{on,sp}는 2.00→2.87 mΩ·cm^{2}로 변하였다. 사용한 메시(1.1만 노드)는 fine 메시 대비 V_{th} 0.07 mV, R_{on,sp} 0.9% 이내였고, Q_{it,eff}에 따른 V_{th} 이동은 −qΔQ_{it}/C_{ox}와 1 mV 이내로 일치하였다. 상용 1.2 kV 평판형 소자[[cree]]의 25→150 °C 변화(V_{th} 2.9→2.4 V, R_{DS(on)} 80→144 mΩ)와 방향은 같지만 본 모델의 변화폭(0.23 V, 44%)은 더 작다. 측정 소자에서는 고온에서 계면 트랩의 전자가 방출되어 V_{th}가 더 낮아지는데[[yu]] 본 모델은 이 효과를 넣지 않았고, γ = +1이면 고온에서 R_{on,sp} 증가폭도 작아진다. 두 가정을 바꾼 계산은 4.2절에 정리하였다."));
if (PRE("F2")) B.push(...F2(), P23); else B.push(P23, ...F2());

// ---------- III. design
B.push(h1(S.c3), h2(S.s31));
B.push(body("표 1은 각 변수를 +20% 바꿨을 때의 특징 변화이다. N_{pw}와 Q_{it,eff}는 V_{th}를 각각 +485, +464 mV로 거의 같게 바꾸지만, 본 모델에서 SS(+3.4%)와 V_{th} 온도 이동(−10.9 mV)은 N_{pw}에만 반응한다. W_{JFET}와 s_{μ}는 300 K에서 모두 I_{on}을 높이지만, 채택한 이동도 모델에서는 423 K에서 드리프트 이동도가 감소하고 채널 이동도가 증가하므로 W_{JFET}의 민감도는 커지고(+3.1→+4.5%) s_{μ}의 민감도는 작아진다(+7.8→+3.6%). 따라서 본 모델에서 N_{pw}와 Q_{it,eff}는 SS와 V_{th} 온도 이동으로, W_{JFET}와 s_{μ}는 두 온도에서의 I_{on} 민감도 차이로 구분할 수 있다."));
if (REVIEW) { B.push(capT("표 1. 파라미터 기준값·범위와 +20% 변화에 따른 특징 변화(300 K/423 K)"), capT("Table 1. Nominal values, ranges and feature changes for a +20% change of each parameter (300 K/423 K)."), table(T1W, T1_EN), note("Units: N_{pw} in cm^{−3}, Q_{it,eff} in cm^{−2} (at 300 K). +20%: 1.2 times the nominal (Q_{it,eff}: −1.0 → −1.2×10^{12} cm^{−2}). *ΔV_{th,T}: change of V_{th}(423 K) − V_{th}(300 K) from the baseline.")); }
else { B.push(capT("표 1. 파라미터 기준값·범위와 +20% 변화에 따른 특징 변화(300 K/423 K)"), table(T1W, T1_KR), note("N_{pw} 단위 cm^{−3}, Q_{it,eff} 단위 cm^{−2}(300 K 값). +20%: 기준값의 1.2배(Q_{it,eff}는 −1.0 → −1.2×10^{12} cm^{−2}). *ΔV_{th,T}: V_{th}(423 K)−V_{th}(300 K)의 기준 대비 변화. 기준 V_{th}: 3.765 V(300 K), 3.530 V(423 K).")); }
B.push(h2(S.s32));
if (REVIEW) {
  B.push(body("4차원(θ, s_{μ}) Sobol 후보 512점(풀)과 독립 무작위 시험점 128점을 두 온도에서 계산(1,280회)하였다. 측정 잡음은 특징 단계에서 독립 정규잡음으로 더하였다. 표준편차는 가정값으로 V_{th} 10 mV, SS·g_{m,max} 2%, I_{on}·R_{on,sp}·I_{D}(2 V) 1%, 전달곡선 표본 2%이며, 전류 1%는 측정기 정확도(0.1~0.2%)[[keysight]]에 반복 측정 변동과 자기발열의 재현 오차를 더한 값이다. 표본 전류는 잡음 후 1×10^{−11} A/cm 하한에서 절단하였고, 특징 간 잡음 상관은 무시하였으며 풀과 시험 집합에는 서로 다른 잡음 실현을 썼다. ‘2배 잡음’은 모든 표준편차를 두 배로 한 경우이다. 역추정 모델(가우시안 과정(GP)[[gp]], 랜덤 포레스트(RF), 선형 Ridge)은 표준화한 특징에서 θ를 예측하며, 성능은 각 변수의 절대오차를 DOE 범위로 나눠 평균한 MAE_{norm}과, 시험점별 오차 차이의 짝지은 부트스트랩(5,000회) 95% CI로 평가하였다. 국소 식별성은 Stage A 자코비안(6개 스칼라, 4개 변수)과 가정한 잡음의 Cramér–Rao 하한으로 점검하였다. 423 K 특징의 이득에 섞인 반복 측정 효과를 분리하기 위해, 300 K 특징에 독립 잡음을 한 번 더 실현해 두 측정을 평균한 통제 집합 S1×2를 학습·시험 데이터에 만들고, 두 측정 사이의 잡음 상관 ρ ∈ {0, 0.5, 0.9}도 바꾸어 보았다."));
} else {
  B.push(body("4차원(θ, s_{μ}) Sobol 후보 512점(풀)과 독립 무작위 시험점 128점을 두 온도에서 계산(1,280회)하였다. 측정 잡음은 원시 곡선이 아니라 추출된 특징에 직접, 서로 독립인 정규분포로 더하였다. V_{th}에는 표준편차 σ_{k}의 가산 잡음을, 나머지 특징에는 상대 표준편차 σ_{k}의 곱셈 잡음을 주었다."),
    body("σ_{k}는 가정값으로 V_{th} 10 mV, SS·g_{m,max} 2%, I_{on}·R_{on,sp}·I_{D}(2 V) 1%, 전달곡선 표본 2%로 두었으며, 로그로 쓰는 특징에는 log(1 + σ_{k}ε)를 더하였다. 표본 전류는 잡음 후 1×10^{−11} A/cm 하한에서 절단하였다. 전류 1%는 측정기 정확도(0.1~0.2%)[[keysight]]에 반복 측정 변동과 자기발열에 의한 재현 오차를 더한 비구조적 잡음이며, 바이어스에 상관된 직렬저항은 3.3절에서 구조적 불일치로 따로 다룬다. 특징 간 잡음 상관은 무시하였고, 풀과 시험 집합에는 서로 다른 잡음 실현(고정 시드)을 사용하였다. ‘2배 잡음’은 모든 σ_{k}를 두 배로 한 경우이다. 역추정 모델은 가우시안 과정(GP, 상수×RBF+백색잡음 커널)[[gp]], 랜덤 포레스트(RF, 300그루), 선형 Ridge 회귀이며, 입력은 표준화하고 출력 θ는 DOE 범위로 [0, 1] 정규화하였다. 성능은 각 변수의 절대오차를 DOE 범위로 나눈 뒤 세 변수에 대해 평균한 MAE_{norm}(시험점 N = 128)으로 평가하고, 두 특징 집합의 비교에는 시험점별 오차 차이 e_{i}^{S2} − e_{i}^{S1}의 짝지은 부트스트랩(5,000회) 95% CI를 사용하였다. 국소 식별성은 Stage A(기준점과 각 변수 ±10%·±20%, 17점×2온도)의 6개 스칼라 특징으로 만든 피셔 정보 J^{T}Σ^{−1}J(J: 4개 변수(θ, s_{μ})에 대한 중앙차분 자코비안, Σ: 가정한 잡음의 대각 공분산)의 Cramér–Rao 하한으로 점검하였다."),
    body("423 K 특징의 이득에는 같은 소자를 한 번 더 측정한 효과도 섞여 있다. 이를 분리하기 위해 300 K 특징에 서로 독립인 잡음을 한 번 더 실현해 두 측정을 평균한 통제 집합 S1×2(17차원)를 학습·시험 데이터 모두에 만들고 같은 방식으로 평가하였다. 두 측정 사이의 잡음 상관 ρ ∈ {0, 0.5, 0.9}(S2는 300/423 K, S1×2는 두 300 K 측정)도 바꾸어 보았으며, ρ = 0의 S1·S2는 위와 같은 잡음 실현이다."));
}
B.push(h2(S.s33));
if (REVIEW) {
  B.push(body("고온 물리 가정의 영향을 보기 위해 423 K 특성만 다시 계산하였다(300 K 물리는 동일). 변형은 식 (2)의 γ = 0, −1과 식 (3)의 r = 0.1, 0.3이며, 각각 풀·시험점 640점을 재계산하였다(2,560회, 모두 수렴). 평가는 ① 같은 물리로 학습·평가(해당 가정에서 다중 온도 정보의 유용성), ② 기준 물리로 학습하고 변형 물리로 평가(모델 불일치에 대한 취약성), ③ 사후 분석인 가정 무작위화 학습으로 나눈다. ③은 총 512개 풀 점 각각의 423 K 데이터를 다섯 가정(기준과 네 변형) 중 하나에서 균등 무작위로 가져와 학습하되 가정의 종류는 입력하지 않으므로, 기준 학습과 총 공정점 수와 실행 예산이 같다. 모든 시나리오는 같은 128개 시험점을 쓴다. 또한 학습에 없는 기생 직렬저항을 시험 데이터에만 적용하였다. 소자별 면적 정규화 저항 ρ_{s} ~ U(0.1, 0.3) mΩ·cm^{2}(두 온도에 동일)를 드레인 측 집중저항 R_{s} = ρ_{s}/W(W: half-cell 폭)로 두고, 저장된 곡선을 1차 근사로 변환한 뒤 특징을 다시 계산하였다. 선형 영역의 전류 특징에는 I_{D}/(1 + I_{D}R_{s}/V_{DS})를, I_{D}(2 V)에는 출력곡선에서 I_{D} = f(2 V − I_{D}R_{s})의 해를 쓰고 R_{on,sp}에는 ρ_{s}를 더하였으며 V_{th}·SS는 그대로 두었다."));
} else {
  B.push(body("고온 물리 가정의 영향을 보기 위해 423 K 특성만 다시 계산하였다(300 K 물리는 동일). 변형은 식 (2)의 γ = 0, −1과 식 (3)의 r = 0.1, 0.3이며, 각각 풀·시험점 640점을 재계산하였다(2,560회, 모두 수렴). 평가는 ① 같은 물리로 학습·평가: 해당 가정에서 다중 온도 정보가 원리적으로 유용한지, ② 기준 물리로 학습하고 변형 물리로 평가: 모델 불일치에 대한 취약성, ③ 가정 무작위화 학습(사후 분석): 총 512개 풀 점 각각의 423 K 데이터를 다섯 가정(기준, γ = 0, −1, r = 0.1, 0.3) 중 하나에서 균등 무작위로 가져와(각 116/90/95/105/106점) 학습하되, 가정의 종류는 모델에 입력하지 않는다. 따라서 ③은 기준 학습과 총 공정점 수·DEVSIM 실행 예산이 같고, 모든 시나리오는 같은 128개 시험점에서 평가한다. 또한 학습에 없는 기생 직렬저항을 시험 데이터에만 적용하였다. 소자별 면적 정규화 저항 ρ_{s} ~ U(0.1, 0.3) mΩ·cm^{2}(두 온도에 동일)를 드레인 측 집중저항 R_{s} = ρ_{s}/W(W = 3.5 µm, 단위 폭당)로 두고, 저장된 곡선을 1차 근사로 변환한 뒤 특징을 다시 계산하였다."),
    body("선형 영역(V_{DS} = 0.1 V)의 I_{on}, 전달곡선 표본, g_{m,max}(변환된 곡선에서 재추출)에는 I_{D}/(1 + I_{D}R_{s}/V_{DS})를 적용하고, I_{D}(2 V)는 출력곡선 f에서 I_{D} = f(2 V − I_{D}R_{s})를 이분법으로 풀어 구했으며, R_{on,sp}에는 ρ_{s}를 더하였다. V_{th}·SS 영역의 전류(≤ 10^{−4} A/cm)에서는 I_{D}R_{s}가 0.1 mV 미만이므로 두 특징은 그대로 두었다. 이는 재시뮬레이션이 아닌 1차 근사이다."));
}
B.push(h2(S.s34));
if (REVIEW) {
  B.push(body("풀 기반 회고적 능동학습[[settles]]으로 모든 정책에 같은 초기 무작위 60점과 예산(10점×6회)을 주고, S2 특징과 RF 역추정 모델로 시드 10개를 반복하였다. 무작위와 Sobol 순서[[sobol]]는 학습 모델을 쓰지 않는 기준선이고, 불확실도 정책과 LLM 보조 정책은 현재까지의 학습 데이터로 후보를 고른다. 불확실도 정책은 정규화된 설계 변수 p에서 S2 특징을 예측하는 순방향 RF의 트리 간 표준편차를 특징 평균한 u(p)를 구하고, u 상위 30개 후보에서 u(p)·d(p)(d: 학습점과 이미 고른 점까지의 최소 거리)가 최대인 점을 10회 순차 선택한다. LLM 보조 정책은 u 상위 20개 후보의 설계값·u·d와 학습 데이터 교차검증 오차를 Claude(claude-sonnet-5-5)에 주고, 선택 ID와 사유 코드를 JSON 스키마 구조화 출력[[anthropic]]으로 받는다. 응답은 결정론적 검증 함수가 후보 포함 여부, 중복, 개수(10개), 근거 길이(400자 이하)를 확인해 하나라도 어기면 그 라운드는 불확실도 정책의 선택을 쓴다. LLM이 제공 정보를 쓰는지 보기 위해 같은 환경에서 원래 형식(A), 변수명과 물리 설명을 지운 익명화(B), 후보의 (u, d)와 변수별 오차를 섞어 틀리게 보여 준 조건(C), LLM 없이 상위 20개 중 무작위로 고르는 기준선(D)을 다시 실행하였다. 코드와 실행 기록은 버전과 함께 저장하였으며 심사 후 공개한다."));
} else {
  B.push(body("풀 기반 회고적 능동학습[[settles]]으로 모든 정책에 같은 초기 무작위 60점과 예산(10점×6회)을 주고, S2 특징과 RF 역추정 모델로 시드 10개를 반복하였다. 비교한 정책은 네 가지이다. 무작위와 Sobol 순서[[sobol]]는 학습 모델을 쓰지 않는 기준선이고, 불확실도 정책과 LLM 보조 정책은 현재까지의 학습 데이터에서 만든 정보로 후보를 고른다. 불확실도 정책은 정규화된 설계 변수 p(4차원)에서 표준화된 S2 특징을 예측하는 순방향 RF(200그루)의 트리 간 표준편차를 특징에 대해 평균한 u(p)를 구하고, u 상위 30개 후보에서 u(p)와 거리 d(p)의 곱이 최대인 점을 10회 순차 선택해 배치를 고른다. d(p)는 학습점과 이미 고른 점까지의 최소 유클리드 거리이며, 의사코드와 구현은 저장소[[repo]]에 공개하였다."),
    body("LLM 보조 정책은 u 상위 20개 후보의 정규화된 설계값·u·d와, 학습 데이터의 교차검증으로 얻은 변수별 오차 및 가장 오차가 큰 변수를 Claude(claude-sonnet-5-5)에 제공하고, 후보 목록 안의 선택 ID와 6개 범주의 사유 코드를 JSON 스키마 구조화 출력[[anthropic]]으로 받는다. 응답은 결정론적 검증 함수가 선택 ID의 후보 목록 포함 여부, 중복, 개수(10개), 근거 길이(400자 이하)를 확인하며, 하나라도 어기면 그 라운드의 배치는 불확실도 정책의 선택으로 채운다. LLM이 제공 정보를 쓰는지 보기 위해 같은 환경에서 다음 조건을 다시 실행하였다. A는 원래 형식, B는 변수명을 x1–x4로 바꾸고 소자·물리 설명을 뺀 익명화, C는 라운드마다 20개 후보의 (u, d) 쌍을 무작위로 섞고 변수별 오차를 순환 이동해 가장 오차가 큰 변수를 항상 틀리게 보여 준 조건이며, D는 LLM 없이 상위 20개 중 10개를 무작위로 고른다."));
}
if (!REVIEW) { B.push(h2(S.s35), body("모든 run은 버전을 고정한 환경(DEVSIM 2.11)에서 별도 프로세스로 실행하고 설정·물리·메시 해시와 수렴 이력을 기록하였으며, GitHub Actions 병렬 작업으로 계산하였다(run당 중앙값 45 s). 결과 감사에서 설계와 run의 1:1 대응, 저장 곡선으로부터의 특징 재추출 일치, 다른 머신에서의 재계산 일치(상대 차이 10^{−13} 이하)를 확인하였다. 예측은 저장소[[repo]]의 docs/PREDICTIONS*.md에 풀·시험 결과 분석 전(커밋 f542405), 변형 시뮬레이션 전(ae73669), 반복 측정 통제와 RQ3 절제의 실행 전(cb3534b, 기존 결과를 본 뒤 설계)에 적어 두었다. 절제 조건은 모두 이전 실행의 불확실도 곡선이 그대로 재현되는 같은 환경에서 실행하였다.")); }

// ---------- IV. results
B.push(h1(S.c4), h2(S.s41));
const F3 = () => figure(REVIEW ? "fig3_rq1_v47.png" : "fig3_rq1_robust_v47.png", REVIEW ? 220 : 285,
  R_("그림 3. 역추정 오차(시험 128점, GP): (a) 변수별 S1, S1×2, S2(기본 잡음, 오차 막대: 부트스트랩 95% CI, 괄호: S1×2 대비 S2의 유의한 감소), (b) 두 측정의 잡음 상관 ρ에 따른 평균 오차",
     "그림 3. 역추정 오차(시험 128점, GP): (a) 변수별 S1, S1×2, S2(기본 잡음, 오차 막대: 부트스트랩 95% CI, 괄호: S1×2 대비 S2의 유의한 감소, 점선: 무정보 추정), (b) 두 측정의 잡음 상관 ρ에 따른 평균 오차, (c) 시험 시나리오별 S2 평균 오차(로그축, 점선: S1, 일점쇄선: S1×2, 오른쪽: 직렬저항)."),
  REVIEW ? "Fig. 3. Inverse-estimation error (128 test points, GP): (a) S1, S1×2 and S2 per parameter (nominal noise; error bars: bootstrap 95% CI; bracket: significant reduction of S2 from S1×2), (b) mean error versus the noise correlation ρ of the two measurements." : null);
const P41 = body(R_("그림 3(a)에서 기본 잡음의 GP MAE_{norm}은 S1 0.112, S2 0.072였으나(S2−S1 95% CI [−0.049, −0.031]), 300 K를 두 번 측정한 S1×2도 0.086이어서 독립 잡음에서는 이득의 약 2/3가 측정 횟수에서 나왔다. S1×2 대비 S2의 온도 고유 이득은 평균 −0.0145(CI [−0.0237, −0.0060])로 W_{JFET}에 집중되었고(0.079→0.050, CI [−0.040, −0.017]), N_{pw}와 Q_{it,eff}는 CI가 0을 포함하였다. Cramér–Rao 하한의 S2/S1 비도 W_{JFET}가 0.38로 N_{pw}·Q_{it,eff}(0.59, 0.58)보다 작았다. 34차원 통제, 2배 잡음, 선형 Ridge, 다른 잡음 실현 4개에서도 결론은 같았다. 그림 3(b)처럼 두 측정의 잡음이 상관되면(ρ = 0.9) 반복 이득은 사라졌으나(S1×2 0.110) S2는 0.075를 유지했고 온도차를 더한 S3는 0.064였다. 잡음이 없으면 S1의 오차도 0.001 미만이었다.",
  "그림 3(a)와 같이 기본 잡음에서 GP의 MAE_{norm}은 S1 0.112, S2 0.072로 S2가 36% 작았다(S2−S1 95% CI [−0.049, −0.031]). 그러나 300 K를 두 번 측정한 S1×2도 0.086으로 S1보다 23% 작아(S1×2/S1 비 0.73, 0.79, 0.80, 독립 2회 측정의 이론값 0.71), 독립 잡음에서는 이득의 약 2/3가 측정 횟수에서 나왔다. S2는 S1×2보다 평균 0.0145(95% CI [−0.0237, −0.0060]) 작았고, 이 온도 고유 이득은 표 1에서 s_{μ}와 반대로 423 K 민감도가 커졌던 W_{JFET}에 집중되었다(0.079→0.050, CI [−0.040, −0.017]). N_{pw}(0.124→0.113)와 Q_{it,eff}(0.057→0.052)는 CI가 0을 포함하였고, Cramér–Rao 하한의 S2/S1 비도 W_{JFET}가 0.38로 N_{pw}·Q_{it,eff}(0.59, 0.58)보다 작았다. 두 측정을 나란히 넣은 34차원 통제(0.091), 2배 잡음, 선형 Ridge(S1 0.117, S1×2 0.088, S2 0.073), 다른 잡음 실현 4개에서도 W_{JFET}의 추가 이득만 유의하였다. 그림 3(b)처럼 두 측정의 잡음이 상관되면 반복 측정의 이득은 사라졌으나(ρ = 0.5, 0.9에서 S1×2 0.101, 0.110) S2는 0.077, 0.075를 유지했고, ρ = 0.9에서는 온도차 특징을 더한 S3가 0.064로 더 작았다. 같은 DEVSIM 실행 수에서도 120회의 S2(60점)가 0.085로 480회의 S1(0.113)보다 작았다. 잡음이 없으면 S1의 오차도 0.001 미만이었다."));
if (PRE("F3")) B.push(...F3(), P41); else B.push(P41, ...F3());
B.push(h2(S.s42));
const T2BLOCK = () => REVIEW
  ? [capT("표 2. 시험 시나리오별 S2의 평균 MAE_{norm}(기본 잡음, GP, S1 = 0.112, S1×2 = 0.086)"), capT("Table 2. Mean MAE_{norm} of S2 for each test scenario (nominal noise, GP, S1 = 0.112, S1×2 = 0.086)."), table(T2W, T2), note("Matched: same physics in training and test. Nominal: trained with γ = +1, r = 0. Bold: worse than S1. ^{†}Post hoc random mixture of five assumptions (label not an input). ^{*}0.1–0.3 mΩ·cm^{2} per device, test data only, exploratory (S1 = 0.378, S1×2 = 0.405). CI: paired bootstrap.")]
  : [capT("표 2. 시험 시나리오별 S2의 평균 MAE_{norm}(기본 잡음, GP, S1 = 0.112, S1×2 = 0.086)"), table(T2W, T2), note("같은 물리로 학습: 학습·시험 데이터가 같은 물리. 기준 물리로 학습: γ = +1, r = 0으로 학습. 굵은 값: S1보다 큰 오차. ^{†}512개 풀 점을 다섯 가정에 무작위 배정(사후 분석, 가정 종류는 입력하지 않음). ^{*}소자별 0.1–0.3 mΩ·cm^{2}, 시험 데이터에만 적용(탐색적, S1 = 0.378, S1×2 = 0.405). CI: 시험점 짝지은 부트스트랩.")];
const P42 = body(R_("표 2에서 423 K 데이터를 지수 0, −1로 다시 계산하고 같은 지수로 학습·평가하면 S2 오차는 0.073, 0.076으로 S1(0.112)보다 35%, 32% 작았고, S2−S1의 95% CI는 세 지수 모두 0 미만이었다. 지수가 +1, 0, −1로 바뀌는 동안 W_{JFET} 개선률은 53, 46, 36%로 줄었지만 N_{pw}·Q_{it,eff} 개선률은 27~31%에 머물렀다. W_{JFET} 개선이 준 것은 채널과 드리프트 이동도의 온도 의존성 차이가 줄었기 때문으로 해석된다. r = 0.1, 0.3에서 개선률이 49%, 70%로 커진 것은 식 (3)에 따라 423 K V_{th}가 Q_{it,eff}에 비례해 더 이동하기 때문이며, r = 0.3의 개선은 N_{pw}(78%)와 Q_{it,eff}(77%)에 집중되었다. 기준 물리로 학습한 모델에서는 γ = −1 데이터의 g_{m,max}가 38% 낮아 학습 범위를 벗어났고, S2 오차가 S1보다 컸다. 사전 예측에서는 γ = 0 데이터에도 기준 모델의 S2가 S1보다 나을 것으로 보았으나 실제 오차는 S1의 약 5배였다. 고온 물리와 무관한 S1×2(0.086)와 비교하면, 물리가 맞을 때 423 K의 추가 이득은 0.014였지만 지수가 틀리면 오차가 0.45~0.84 커졌다. 다섯 가정을 섞어 학습한 사후 분석에서는 S2가 다섯 시험 모두에서 S1보다 22~29% 작았다. 직렬저항을 시험 데이터에 넣으면 S1, S1×2, S2 오차가 0.378, 0.405, 0.261로 커져, 반복 측정은 계통 오차를 줄이지 못했고 보정 없이 정량 추정에 쓰기는 어렵다.",
  "표 2와 그림 3(c)에서 같은 물리로 학습·평가하면 S2는 γ = 0, −1에서 S1보다 35%, 32% 작았고 S2−S1의 95% CI는 세 지수 모두 0 미만이었다. 지수가 +1, 0, −1로 바뀌는 동안 W_{JFET} 개선률은 53%, 46%, 36%로 줄었지만 N_{pw}·Q_{it,eff} 개선률은 27~31%에 머물렀다. W_{JFET} 개선이 준 것은 채널과 드리프트 이동도의 온도 의존성 차이가 줄었기 때문으로 해석된다. r = 0.1, 0.3에서 개선률이 49%, 70%로 커진 것은 식 (3)에 따라 423 K V_{th}가 Q_{it,eff}에 비례해 더 이동해 Q_{it,eff}를 직접 반영하는 특징이 생겼기 때문이며, r = 0.3의 개선은 N_{pw}(78%)와 Q_{it,eff}(77%)에 집중되었다(W_{JFET} 55%). 반면 기준 물리로 학습한 모델은 γ = 0, −1과 r = 0.3에서 S1보다 오차가 컸다(γ = −1의 423 K g_{m,max}는 기준보다 38% 낮아 학습 범위 밖). 사전 예측 문서에서는 γ = 0 데이터에도 기준 모델의 S2가 S1보다 나을 것으로 보았으나 실제 오차는 S1의 약 5배였다. 고온 물리와 무관한 S1×2(0.086)와 비교하면, 물리가 맞을 때 423 K의 추가 이득은 0.014였지만 지수가 틀리면 오차가 0.45~0.84 커졌다. 사후 분석으로 다섯 가정을 섞어 학습하면 S2는 다섯 시험 모두에서 S1보다 22~29% 작았다(CI 모두 0 미만). 학습에 없던 직렬저항을 넣으면 S2(0.261)가 S1(0.378)보다 31% 작았고 S1×2는 0.405로 반복 측정이 계통 오차를 줄이지 못했지만, S2 오차도 직렬저항이 없을 때의 약 3.6배여서 보정 없이 정량 추정에 쓰기는 어렵다."));
if (PRE("T2")) B.push(...T2BLOCK(), P42); else B.push(P42, ...T2BLOCK());
B.push(h2(S.s43));
const F4 = () => figure("fig4_policies_v47.png", REVIEW ? 220 : 280,
  R_("그림 4. 표본 선택 정책 비교(S2, RF, 시드 10개, 같은 환경): (a) 학습곡선(시드 평균), (b) 최종 라운드의 짝지은 차이(부트스트랩 95% CI, 오른쪽: 평균 [CI], 왼쪽 항의 우세 시드 수)",
     "그림 4. 표본 선택 정책 비교(S2, RF, 시드 10개, 같은 환경): (a) 학습곡선(시드 평균), (b) 최종 라운드의 짝지은 차이(부트스트랩 95% CI, 오른쪽: 평균 [CI], 왼쪽 항의 우세 시드 수). LLM은 1차 실행(A0), 재실행(A), 익명화(B), 정보 섞기(C)."),
  REVIEW ? "Fig. 4. Comparison of sample-selection policies (S2, RF, 10 seeds, same environment): (a) learning curves (seed mean), (b) paired final-round differences (bootstrap 95% CI; right: mean [CI], seeds won by the left term)." : null);
const P43 = body(R_("그림 4에서 불확실도 정책은 무작위 대비 최종 오차를 0.0025(95% CI [−0.0039, −0.0009]) 줄였고, 무작위의 최종 정확도에 약 106점에서 도달해 시뮬레이션을 약 12% 절감하였다. Sobol 순서도 −0.0023으로 비슷하였고, 2배 잡음에서는 두 정책 모두 무작위와 유의한 차이가 없었다. 초기 표본을 30점으로 줄이면 절감률은 약 20%(Sobol 24%)였다. Sobol 순서와 차이가 작아 절감의 상당 부분은 후보를 고르게 배치한 효과로 보인다.",
  "그림 4에서 불확실도 정책은 무작위 대비 최종 오차를 0.0025(95% CI [−0.0039, −0.0009]) 줄였고, 무작위의 최종 정확도에 약 106점에서 도달해 시뮬레이션을 약 12% 절감하였다. Sobol 순서도 −0.0023으로 비슷하였고, 2배 잡음에서는 두 정책 모두 무작위와 유의한 차이가 없었다. 초기 무작위 표본을 30점으로 줄이면 절감률은 약 20%(Sobol 24%)였다. Sobol 순서와 절감이 비슷하므로, 이 실험에서는 절감의 상당 부분이 후보를 공간에 고르게 배치한 효과로 보인다."));
const [P44a_rev, P44a_proc] = ["검증 통과는 1차 실행(A0) 59/60회, A·B·C 60/60, 60/60, 59/60회였다. 최종 오차는 A0 0.1250, A 0.1236, B 0.1242, C 0.1257, D 0.1259, 불확실도 0.1238로, 불확실도 대비 95% CI가 모두 0을 포함하여(그림 4(b)) 차이가 없다는 귀무가설을 기각할 수 없었고, 같은 조건의 두 실행(A0, A)도 0.0014 달랐다.",
  "LLM 응답은 1차 실행(A0) 60회 중 59회, 재실행한 A·B·C에서 60, 60, 59회가 검증을 통과하였다(거절은 모두 근거 400자 초과). 최종 오차는 A0 0.1250, A 0.1236, B 0.1242, C 0.1257, D 0.1259, 불확실도 0.1238이었고, 불확실도 대비 차이의 95% CI는 다섯 조건 모두 0을 포함하여(그림 4(b)) 차이가 없다는 귀무가설을 기각할 수 없었다. 같은 조건을 두 번 실행한 A0과 A도 0.0014(CI [+0.0001, +0.0027]) 달라, 조건 간 차이는 반복 실행 변동과 같은 크기였다."];
const [P44b_rev, P44b_proc] = ["그러나 선택 행동은 제공 정보를 따랐다. 정보를 섞은 C에서 LLM은 표시된 불확실도 상위 10개와 64%가 겹쳤으나 실제 상위 10개와는 49%로 무작위(50%)와 같았고, 틀리게 표시한 최악 변수 방향으로 59회 중 51회 범위를 넓혔다(실제 최악 변수 방향 36회, 무작위 기대 각 약 30회). 변수명과 물리 설명을 지운 B는 A와 비슷하게 행동하였다. 즉 LLM은 표시된 숫자를 읽고 따르지만, 후보가 이미 불확실도 상위 20개로 걸러진 설정에서는 그 정보가 정확도 차이로 이어지지 않았다. Gupta 등은 실험 결과를 섞어도 성능이 같은 것을 LLM이 피드백을 쓰지 않는 근거로 보았으나[[gupta]], 여기서는 최종 오차가 달라지지 않았는데도 선택은 정보를 따랐다.",
  "반면 선택 행동은 제공 정보를 따랐다. A에서 LLM은 불확실도 상위 10개 중 62%만 골라 60회 중 54회 더 넓은 배치를 택했고, 47회는 오차가 큰 변수 방향으로 범위를 넓혔다(같은 20개 중 무작위 선택의 기대 68%, 52%). 정보를 섞은 C에서는 표시된 상위 10개와 64%가 겹쳤지만 실제 상위 10개와는 49%로 무작위(50%)와 같았고, 틀리게 표시한 최악 변수 방향으로 59회 중 51회 범위를 넓혔다(실제 최악 변수 방향 36회, 무작위 기대 각 약 30회). 변수명과 물리 설명을 지운 B도 A와 비슷하게 행동하였다. 즉 LLM은 표시된 숫자를 읽고 따르지만, 후보가 이미 불확실도 상위 20개로 걸러진 이 설정에서는 그 정보가 정확도 차이로 이어지지 않았다. Gupta 등은 실험 결과를 섞어도 성능이 변하지 않는 것을 LLM이 피드백을 쓰지 않는 근거로 보았으나[[gupta]], 본 실험에서는 최종 오차가 달라지지 않았는데도 선택은 표시된 정보를 따랐으므로 성능만으로 정보 사용 여부를 판단하기는 어렵다."];
const F4MODE = process.env.ORD_F4 || ORD_DEFAULT.F4;   // pre | post | mid (mid: between the two RQ3 paragraphs)
const P44 = () => body(R_(P44a_rev + " " + P44b_rev, P44a_proc + " " + P44b_proc));
if (F4MODE === "pre") B.push(...F4(), P43, h2(S.s44), P44());
else if (F4MODE === "mid") B.push(P43, h2(S.s44), body(R_(P44a_rev, P44a_proc)), ...F4(), body(R_(P44b_rev, P44b_proc)));
else B.push(P43, ...F4(), h2(S.s44), P44());

// ---------- V. conclusion
B.push(h1(S.c5));
B.push(body(R_("423 K 특성을 더하면 GP 역추정 오차가 0.112에서 0.072로 줄었지만, 300 K를 두 번 측정해도 0.086이어서 독립 잡음에서는 이득의 약 2/3가 측정 횟수에서 나왔고, 온도 고유 이득은 W_{JFET}에 집중되었다. 반복 측정의 이득은 고온 물리와 무관하지만 잡음이 상관되면 사라지고, 온도 고유 이득은 잡음 상관에 강건하지만 지수 +1로 학습한 모델은 지수 0, −1 데이터에서 오차가 0.537, 0.928로 커졌다. 따라서 실측 소자에 적용하려면 측정한 온도 특성으로 고온 물리 가정의 범위를 먼저 정하고 직렬저항을 보정해야 한다. 적응형 선택은 시뮬레이션을 12~20% 줄였으나 Sobol 순서와 비슷하였고, LLM 선택의 최종 오차는 정보를 지우거나 섞어도 불확실도 선택과 구분되지 않았지만 선택 행동은 제공된 숫자를 따랐다.",
  "423 K 특성을 더하면 GP 역추정 오차가 0.112에서 0.072로 줄었지만, 300 K를 두 번 측정해도 0.086까지 줄어 독립 잡음에서는 이득의 약 2/3가 측정 횟수에서 나왔다. 반복 측정을 넘어서는 온도 고유 이득은 300 K에서 채널 이동도와 같은 방향으로 전류를 바꾸던 W_{JFET}에 집중되었다(0.079→0.050). 두 이득은 약점도 다르다. 반복 측정의 이득은 고온 물리와 무관하지만 두 측정의 잡음이 상관되면 사라지고 직렬저항 같은 계통 오차는 줄이지 못한다. 반대로 온도 고유 이득은 잡음 상관에도 유지되지만, 423 K 데이터를 채널 이동도 지수 0, −1로 다시 계산하면 지수 +1로 학습한 모델의 오차가 0.537, 0.928로 커졌다. 다섯 물리 가정을 섞어 학습해도(0.079~0.088) 실제 물리가 그 안에 있다는 보장은 없으므로, 실측 소자에는 측정한 V_{th}·R_{on,sp}의 온도 특성으로 이동도 지수와 계면전하 온도 의존성의 범위를 먼저 정하고 직렬저항을 따로 보정해야 한다. 적응형 선택은 무작위보다 시뮬레이션을 12~20% 줄였으나 Sobol 순서와 비슷하였고, LLM 보조 선택은 제공된 숫자를 따랐지만 정보를 지우거나 섞어도 최종 오차가 불확실도 선택과 구분되지 않았다. 즉 LLM의 정보 사용 여부는 최종 오차가 아니라 절제 조건에서의 선택 행동으로 확인되었다.")));
B.push(body(R_("모든 결과는 단극성 2차원 구조 하나와 가정한 잡음에서 얻은 것이며 실측 곡선으로는 검증하지 않았다. 300 K V_{th} 추출 정밀도(최대 3 mV)와 g_{m,max} 분해능(약 1.3%)은 가정한 잡음보다 작다. LLM 결과는 한 모델과 시드 10개에서 얻었다.",
  "모든 결과는 단극성 2차원 half-cell 한 구조와 가정한 측정 잡음에서 얻었고 실측 곡선으로는 검증하지 않았다. 300 K V_{th} 추출 정밀도(최대 3 mV)와 g_{m,max} 분해능(약 1.3%)은 가정한 잡음보다 작으며, 항복 특성은 다루지 않았다. LLM 결과는 한 모델(claude-sonnet-5-5)과 시드 10개에서 얻었다.")));

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
const out = process.env.OUT || (REVIEW ? "review_v47_4p.docx" : "proceedings_v47_5p.docx");
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(path.isAbsolute(out) ? out : path.join(__dirname, out), buf); console.log("wrote", out, "| refs:", ORDER.length); });
