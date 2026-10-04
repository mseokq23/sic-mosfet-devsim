// Build the Korean draft in the IEIE conference layout (A4, title block single column, body double column).
const fs = require("fs");
const {
  Document, Packer, Paragraph, TextRun, ImageRun, Table, TableRow, TableCell, AlignmentType,
  WidthType, BorderStyle, SectionType, TabStopType, Tab,
} = require("docx");

const VERSION = process.argv[2] || "proc"; // "proc" (proceedings, author block) | "review" (anonymous)
const LATIN = "Times New Roman", KOR = "바탕";
const FONT = { ascii: LATIN, hAnsi: LATIN, cs: LATIN, eastAsia: KOR };
const COLW = 4620; // twips, one column (A4, 20 mm margins, 7 mm gap)

// mini markup: _{sub}  ^{sup}  **bold**
function runs(text, o = {}) {
  const out = []; const re = /(_\{[^}]*\}|\^\{[^}]*\}|\*\*[^*]+\*\*)/g; let last = 0, m;
  const base = { font: FONT, ...o };
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) out.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    const t = m[0];
    if (t.startsWith("_{")) out.push(new TextRun({ text: t.slice(2, -1), subScript: true, ...base }));
    else if (t.startsWith("^{")) out.push(new TextRun({ text: t.slice(2, -1), superScript: true, ...base }));
    else out.push(new TextRun({ text: t.slice(2, -2), ...base, bold: true }));
    last = m.index + t.length;
  }
  if (last < text.length) out.push(new TextRun({ text: text.slice(last), ...base }));
  return out;
}
const SP = { line: 250, before: 0, after: 0 };
const body = (t) => new Paragraph({ children: runs(t, { size: 18 }), alignment: AlignmentType.JUSTIFIED, indent: { firstLine: 180 }, spacing: SP });
const h1 = (t) => new Paragraph({ keepNext: true, children: runs(t, { size: 19, bold: true }), alignment: AlignmentType.CENTER, spacing: { before: 150, after: 70, line: 250 } });
const h2 = (t) => new Paragraph({ keepNext: true, children: runs(t, { size: 18, bold: true }), spacing: { before: 70, after: 30, line: 250 } });
const center = (t, size, extra = {}) => new Paragraph({ children: runs(t, { size, ...extra }), alignment: AlignmentType.CENTER, spacing: { line: 240, before: 0, after: 0 } });

function pngSize(p) { const b = fs.readFileSync(p); return [b.readUInt32BE(16), b.readUInt32BE(20)]; }
function figure(file, widthPx, caption) {
  const [w, h] = pngSize(file);
  return [
    new Paragraph({ keepNext: true, alignment: AlignmentType.CENTER, spacing: { before: 90, after: 30 },
      children: [new ImageRun({ type: "png", data: fs.readFileSync(file), transformation: { width: widthPx, height: Math.round(widthPx * h / w) } })] }),
    new Paragraph({ alignment: AlignmentType.JUSTIFIED, spacing: { after: 90, line: 220 }, children: runs(caption, { size: 15 }) }),
  ];
}
function equation(t, num) {
  return new Paragraph({ tabStops: [{ type: TabStopType.CENTER, position: COLW / 2 }, { type: TabStopType.RIGHT, position: COLW }],
    spacing: { before: 50, after: 50, line: 250 }, children: [new TextRun({ children: [new Tab()] }), ...runs(t, { size: 18 }), new TextRun({ children: [new Tab()] }), ...runs(`(${num})`, { size: 18 })] });
}

// ---------------------------------------------------------------- Table 1 (sensitivity)
const NONE = { style: BorderStyle.NONE, size: 0, color: "FFFFFF" };
const LINE = (sz) => ({ style: BorderStyle.SINGLE, size: sz, color: "000000" });
const tWidths = [1300, 830, 830, 830, 830];
function cell(t, w, opts = {}) {
  return new TableCell({ width: { size: w, type: WidthType.DXA }, margins: { top: 25, bottom: 25, left: 40, right: 40 },
    borders: { top: opts.top || NONE, bottom: opts.bottom || NONE, left: NONE, right: NONE },
    children: [new Paragraph({ alignment: opts.left ? AlignmentType.LEFT : AlignmentType.CENTER, spacing: { line: 220 }, children: runs(t, { size: 13, bold: !!opts.bold }) })] });
}
const T1 = [
  ["특징 (+20%)", "W_{JFET}", "N_{pw}", "Q_{it,eff}", "μ_{ch}"],
  ["ΔV_{th} (mV)", "0/0", "+485/+474", "+464/+464", "−13/−13"],
  ["SS (%)", "0/0", "+3.4/+3.8", "0/0", "−0.2/−0.1"],
  ["g_{m,max} (%)", "+0.6/+1.2", "−4.7/−5.1", "−1.2/−0.6", "+16.2/+11.8"],
  ["I_{on} (%)", "+3.1/+4.5", "−3.0/−1.7", "−1.3/−0.6", "+7.8/+3.6"],
  ["R_{on,sp} (%)", "−3.1/−4.3", "+3.1/+1.7", "+1.3/+0.7", "−7.3/−3.5"],
  ["I_{D}(2 V) (%)", "+3.3/+4.7", "−3.4/−1.9", "−1.4/−0.7", "+8.3/+3.8"],
  ["ΔV_{th,T} (mV)*", "0.0", "−10.9", "0.0", "−0.4"],
];
const table1 = new Table({
  width: { size: tWidths.reduce((a, b) => a + b), type: WidthType.DXA }, columnWidths: tWidths,
  borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
  rows: T1.map((r, i) => new TableRow({ children: r.map((t, j) => cell(t, tWidths[j], {
    left: j === 0, bold: i === 0, top: i === 0 ? LINE(8) : undefined,
    bottom: i === 0 ? LINE(4) : (i === T1.length - 1 ? LINE(8) : undefined) })) })),
});

// ---------------------------------------------------------------- Table 2 (robustness, from paper/tables/table2_robustness.csv)
const t2Widths = [1500, 1000, 1000, 1120];
const T2 = [
  ["423 K 물리", "같은 물리 학습", "기준 물리 학습", "가정 혼합 학습†"],
  ["기준(γ = +1, 정적 Q_{it})", "0.072", "—", "0.082"],
  ["γ = 0", "0.073", "0.537", "0.083"],
  ["γ = −1", "0.076", "0.928", "0.088"],
  ["Q_{it} 크기 −10%", "0.057", "0.084", "0.079"],
  ["Q_{it} 크기 −30%", "0.033", "0.132", "0.080"],
  ["기생 직렬저항*", "—", "0.261", "—"],
];
const table2 = new Table({
  width: { size: t2Widths.reduce((a, b) => a + b), type: WidthType.DXA }, columnWidths: t2Widths,
  borders: { top: NONE, bottom: NONE, left: NONE, right: NONE, insideHorizontal: NONE, insideVertical: NONE },
  rows: T2.map((r, i) => new TableRow({ children: r.map((t, j) => cell(t, t2Widths[j], {
    left: j === 0, bold: i === 0, top: i === 0 ? LINE(8) : undefined,
    bottom: i === 0 ? LINE(4) : (i === T2.length - 1 ? LINE(8) : undefined) })) })),
});

// ---------------------------------------------------------------- content
const titleKR = "DEVSIM 기반 4H-SiC 평판형 MOSFET 공정 결과 파라미터의 다중 온도 역추정과 LLM 보조 적응형 실험 선택";
const titleEN = "Multi-Temperature Inverse Estimation of Process-Outcome Parameters and LLM-Assisted Adaptive Experiment Selection for 4H-SiC Planar MOSFETs Using DEVSIM";
const abstract = "We present a reproducible open-source TCAD workflow based on DEVSIM that estimates three latent process-outcome parameters of a 4H-SiC planar MOSFET—JFET width, P-well doping, and effective interface charge—from DC characteristics simulated at 300 K and 423 K, with channel mobility treated as an unmodeled nuisance. The two-dimensional half-cell drift–diffusion model was verified against analytic limits and mesh refinement. Under a measurement-noise model, adding 423 K features reduced the normalized estimation error of a Gaussian-process inverse model by 36% on average and by 53% for the JFET width, and a linear ridge model showed the same gain. When training and test data shared the same physics, the gain persisted for channel-mobility temperature exponents of +1, 0, and −1 (32–36%) and grew when the interface charge decreased with temperature. A model trained with a mismatched mobility exponent failed, whereas training over a mixture of the assumed physics retained a 22–29% gain. In pool-based active learning, uncertainty sampling saved 12–20% of the simulations relative to random sampling, comparable to a fixed Sobol design. An LLM-assisted selector produced valid structured selections in 59 of 60 calls but did not outperform uncertainty sampling.";

const head = [
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 120, line: 300 }, children: runs(titleKR, { size: 30, bold: true }) }),
];
if (VERSION === "proc") {
  head.push(center("○○○^{*}, ○○○^{*}, ○○○^{**}", 20),
    center("^{*}○○대학교 ○○공학과, ^{**}○○대학교 ○○공학과", 17),
    center("e-mail: ○○○@○○○.ac.kr", 17));
}
head.push(new Paragraph({ spacing: { after: 100 }, children: [] }),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60, line: 260 }, children: runs(titleEN, { size: 22, bold: true }) }));
if (VERSION === "proc") {
  head.push(center("○○○^{*}, ○○○^{*}, and ○○○^{**}", 17), center("^{*}Department of ○○, ○○ University", 17));
}
head.push(
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 160, after: 50 }, children: runs("Abstract", { size: 18, bold: true }) }),
  new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 400, right: 400, firstLine: 200 }, spacing: { line: 240, after: 60 }, children: runs(abstract, { size: 17 }) }),
  ...figure(require("path").join(__dirname, "../figures/fig1_structure_flow.png"), 575, "그림 1. (a) 4H-SiC 평판형 MOSFET half-cell 단면(half-pitch 3.5 µm·채널 길이 0.5 µm 고정, 드리프트층 축약 표시)과 추정 파라미터, (b) 다중 온도 시뮬레이션–특징 추출–역추정 및 실험 선택 흐름."),
);

const B = [];
B.push(h1("Ⅰ. 서론"),
  body("4H-SiC MOSFET은 넓은 밴드갭과 높은 임계전계 덕분에 고전압·고온 전력 변환에 널리 쓰인다[1,2]. 그러나 JFET 폭, P-well 도핑, SiO_{2}/SiC 계면전하 같은 공정 결과의 편차는 문턱전압(V_{th})과 온저항(R_{on,sp})을 함께 바꾸고, 서로 다른 원인이 같은 전기적 변화를 만들기 때문에 측정 특성만으로 원인을 역추정하기 어렵다. P-well 도핑 증가와 음의 계면전하 증가는 모두 V_{th}를 높이고, JFET 폭 증가와 채널 이동도 증가는 모두 전류를 늘린다."),
  body("온도는 이러한 혼동을 풀 수 있는 추가 정보가 될 수 있다. 드리프트층의 벌크 이동도는 온도가 오르면 감소하는 반면 채널 이동도의 온도 의존성은 계면 상태에 따라 달라지며[2], 도핑에 의한 V_{th} 성분도 온도에 따라 변한다. 한편 TCAD는 계산 비용이 커서 다변수·다중 온도 실험을 효율적으로 설계할 방법이 필요하며, 대규모 언어 모델(LLM)을 실험 계획에 활용하려는 시도도 있다[3]."),
  body("Müting 등은 상용 1.2 kV SiC MOSFET에 보정한 TCAD로 공정 단계별 편차의 영향을 평가하여 에피 도핑과 계면 트랩 밀도가 소자 간 편차에 가장 중요함을 보였다[4]. TCAD 데이터로 공정 조건에서 4H-SiC MOSFET 특성을 예측하는 기계학습[5]과, LLM 에이전트가 TCAD 코드를 생성해 소자를 최적화하는 연구[6]도 보고되었다. 이들이 공정 조건에서 특성으로 가는 순방향 예측과 최적화를 다룬 반면, 본 연구는 다중 온도 특성으로부터 공정 결과 파라미터를 역추정하는 식별성 문제와, LLM을 검증기로 제한한 실험 선택기로 두고 정량적 기준선과 비교하는 데 초점을 둔다."),
  body("본 논문은 공개형 TCAD인 DEVSIM[7]으로 4H-SiC 평판형 MOSFET의 2차원 DC 해석 파이프라인을 구축하고 다음 질문에 답한다. (RQ1) 300 K 특성에 423 K 특성을 더하면 공정 결과 파라미터의 역추정이 개선되며, 그 이득은 고온 물리 가정에 얼마나 민감한가. (RQ2) 적응형 표본 선택이 무작위·Sobol 표본보다 필요한 시뮬레이션 수를 줄이는가. (RQ3) LLM 보조 선택이 수치적 불확실도 선택보다 우수한가. RQ3의 귀무가설과 강건성 시험의 예상 결과는 실행 전에 사전 등록하였다. 연구 범위는 고온 DC 특성과 공정편차이며, 항복과 장기 신뢰성은 다루지 않는다."),
  h1("Ⅱ. 시뮬레이션 모델 및 검증"),
  h2("2.1 소자 구조와 물리 모델"),
  body("그림 1(a)의 half-cell은 1.2 kV급 설계를 참고한 평판형 구조로, 게이트 산화막 50 nm, P-well 1×10^{17} cm^{−3}, JFET 영역 2×10^{16} cm^{−3}, 드리프트층 10 µm·1×10^{16} cm^{−3}이다. Poisson 방정식과 전자 연속방정식을 Scharfetter–Gummel 이산화[8]로 풀고, 불완전 이온화(N 66 meV, Al 191 meV)[9], 도핑·온도 의존 전자 이동도[10], SRH 재결합을 포함하였으며 물성값은 문헌 고찰[11]을 따랐다. 채널 이동도는 식 (1)로 표면 감쇠를 반영하며, 채택한 표면 이동도 모델에서는 μ_{surf} = 20(T/300 K) cm^{2}/V·s(λ = 3 nm)로 300–423 K에서 증가하도록 설정하였다. 계면 고정전하(Q_{f} = 1×10^{12} cm^{−2})와 유효 계면전하 Q_{it,eff}는 온도의존성을 부여하지 않은 정적 면전하로 두었다. 정공은 소스/바디와 평형으로 두는 단극성 근사를 사용하였다. 423 K에서도 접합 생성전류(2×10^{−16} A/cm^{2} 이하)는 특징 추출의 최소 전류(약 3×10^{−7} A/cm^{2})보다 9자릿수 이상 작고, 바디 다이오드는 역바이어스이며 V_{DS} ≤ 5 V에서 충돌 이온화는 무시된다."),
  equation("μ_{n}^{−1} = μ_{bulk}^{−1}(N, T) + e^{−y/λ} μ_{surf}^{−1}(T)", 1),
  h2("2.2 추정 파라미터와 특징"),
  body("추정 대상은 공정 결과를 나타내는 잠재 파라미터인 JFET 폭 W_{JFET}(±20%), P-well 도핑 N_{pw}(±20%), 유효 계면전하 Q_{it,eff}(−1.5~−0.5×10^{12} cm^{−2})이며, 채널 이동도 배율 μ_{ch}(±20%)는 추정하지 않는 교란 변수로 모든 설계에 포함하였다. 소자 간 편차에 중요한 에피 도핑[4]은 고정하였다. W_{JFET} 편차는 마스크 피치를 고정한 채 자기정렬된 P-well/n^{+} 경계가 이동하는 것으로 정의하여 채널 길이와 면적 정규화를 유지하였다. 300 K와 423 K에서 V_{DS} = 0.1 V 전달 특성과 V_{GS} = 18 V 출력 특성을 계산하고, V_{th}(1×10^{−4} A/cm 정전류), SS(10^{−10}~10^{−6} A/cm), g_{m,max}, I_{on}(V_{GS} = 18 V), R_{on,sp}(V_{DS} ≤ 0.5 V), I_{D}(V_{DS} = 2 V)와 11개 게이트 전압의 log I_{D}를 특징으로 추출하였다. V_{th}와 SS는 목표 전류에서 바이어스를 다시 풀어 격자 보간 오차를 제거하였다. 배정밀도 계산은 128비트 확장정밀도와 같은 특징값을 주어(V_{th} 차이 10^{−11} V 수준) 계산 시간이 1/3인 배정밀도를 사용하였다."),
  h2("2.3 모델 검증"),
  body("1차원 PN 다이오드의 내장전위·불완전 이온화율과 MOS 커패시터의 평탄대 전압은 해석해와 5 mV 이내로 일치하였다. 그림 2는 MOSFET 수준의 검증이다. 300 K→423 K에서 V_{th}는 3.765→3.530 V, SS는 112.5→155.7 mV/dec, R_{on,sp}는 2.00→2.87 mΩ·cm^{2}로 변하였다. 사용한 메시(1.1만 노드)는 2.4만 노드 대비 V_{th} 0.07 mV, R_{on,sp} 0.9% 이내였고, Q_{it,eff}에 따른 V_{th} 이동은 해석해 −qΔQ_{it}/C_{ox}와 1 mV 이내로 일치하였다. 온도에 따른 V_{th} 감소와 R_{on,sp} 증가의 방향은 상용 1.2 kV 평판형 소자의 데이터시트(25→150 °C에서 V_{th} 2.9→2.4 V, R_{DS(on)} 80→144 mΩ)[12]와 같지만 변화폭(0.24 V, 43%)은 작다. 측정 소자에서는 고온에서 계면 트랩의 전자가 방출되어 V_{th}가 더 낮아지고[13], 고온에서 증가하는 채널 이동도 가정은 R_{on,sp} 증가를 줄인다. 이 두 가정의 영향은 4.2절에서 검토한다. 이후 생성한 1,280회 실행은 모두 수렴하였고 다른 머신에서 재계산한 특징도 동일하였다."),
  ...figure(require("path").join(__dirname, "../figures/fig2_validation.png"), 284, "그림 2. 시뮬레이션 검증: (a) 전달 특성(V_{DS} = 0.1 V, 점: V_{th}), (b) 출력 특성(V_{GS} = 18 V), (c) fine 메시 대비 드레인 전류 차이(300 K), (d) Q_{it,eff}에 따른 V_{th} 이동과 해석해."),
  h1("Ⅲ. 실험 설계 및 역추정"),
  h2("3.1 민감도 분석"),
  body("표 1은 각 변수를 +20% 바꿨을 때의 특징 변화이다. N_{pw}와 Q_{it,eff}는 V_{th}를 각각 +485, +464 mV로 거의 같게 바꾸지만, 본 모델에서 SS(+3.4%)와 V_{th} 온도 이동(−10.9 mV)은 N_{pw}에만 반응한다. W_{JFET}와 μ_{ch}는 300 K에서 모두 I_{on}을 높이지만, 채택한 이동도 모델에서는 423 K에서 드리프트 이동도가 감소하고 채널 이동도가 증가하므로 W_{JFET}의 민감도는 커지고(+3.1→+4.5%) μ_{ch}의 민감도는 작아진다(+7.8→+3.6%). 즉 이 모델에서 고온 특성은 두 혼동 쌍을 분리하는 정보를 제공한다."),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 90, after: 40 }, children: runs("표 1. 각 변수 +20% 변화에 따른 특징 변화(300 K/423 K)", { size: 15 }) }),
  table1,
  new Paragraph({ spacing: { before: 20, after: 90, line: 210 }, children: runs("*ΔV_{th,T}: V_{th}(423 K)−V_{th}(300 K)의 기준 대비 변화. 기준 V_{th}: 3.765 V(300 K), 3.530 V(423 K).", { size: 13 }) }),
  h2("3.2 데이터 생성과 역추정"),
  body("4차원 Sobol 후보 512점과 독립 무작위 시험점 128점을 두 온도에서 계산(1,280회)하였다. 실측을 고려해 V_{th} 10 mV, SS·g_{m} 2%, 전류·저항 1%의 측정 잡음과 1×10^{−11} A/cm 전류 하한을 분석 단계에서 적용하였다. 전류 1%는 측정기 정확도(0.1~0.2%)[14]에 접촉저항 변동과 자기발열에 의한 재현 오차를 더한 값이다. 역추정 모델(가우시안 과정(GP)[15], 랜덤 포레스트(RF), extra trees, 선형 Ridge 회귀)은 300 K 특징(S1), 두 온도 특징(S2), S2에 온도 차분을 더한 특징(S3)으로 학습하고, DOE 범위로 정규화한 평균 절대오차(MAE)로 평가하였다."),
  h2("3.3 적응형 실험 선택"),
  body("풀 기반 회고적 능동학습[16]으로 모든 정책에 같은 초기 60점과 예산(10점×6회)을 주었다. 정책은 무작위, Sobol 순서[17], 불확실도(순방향 RF의 트리 간 분산과 거리 기반 다양성), LLM 보조 선택이다. LLM 보조 정책은 불확실도 상위 20개 후보의 정규화된 공정값·예측 불확실도·학습점 거리와 변수별 교차검증 오차를 Claude(claude-sonnet-5-5)에 제공하고, 후보 목록 안의 선택 ID와 6개 범주의 사유 코드를 JSON 스키마 구조화 출력[18]으로 받는다. 응답은 후보 목록·중복·배치 크기·근거 길이를 검사하는 검증기를 통과해야 하며, 거절 시 불확실도 정책으로 대체한다. S2 특징과 RF 역추정 모델로 시드 10개를 반복하고 짝지은 부트스트랩으로 비교하였다."),
  h2("3.4 강건성 시험과 재현성"),
  body("고온 물리 가정의 영향을 보기 위해 423 K 특성만 다시 계산하였다(300 K 물리는 동일). 변형은 채널 이동도 온도지수 0, −1과, 423 K에서 Q_{it,eff}의 크기가 10%·30% 줄어드는 경우(300 K에서 0, 온도에 선형)이며, 각각 풀·시험점 640점을 재계산하였다(2,560회, 모두 수렴). 같은 물리로 학습·평가하는 경우와 기준 물리로 학습하고 변형 물리로 평가하는 경우를 비교하였다. 모든 run은 버전을 고정한 환경(DEVSIM 2.11)에서 별도 프로세스로 실행하고 설정·물리·메시 해시와 수렴 이력을 기록하였으며, GitHub Actions 병렬 작업으로 계산하였다(run당 중앙값 45 s). 결과 감사에서 설계와 run의 1:1 대응, 저장 곡선으로부터의 특징 재추출 일치, 다른 머신에서의 재계산 일치(상대 차이 10^{−13} 이하)를 확인하였다."),
  h1("Ⅳ. 결과 및 고찰"),
  h2("4.1 다중 온도 특징의 효과(RQ1)"),
  body("그림 3(a)와 같이 기본 잡음 수준에서 GP의 평균 정규화 MAE는 S1 0.112에서 S2 0.072로 36% 감소하였다. W_{JFET}는 0.108→0.051(−53%), N_{pw}는 0.157→0.113(−28%), Q_{it,eff}는 0.071→0.052(−27%)로 표 1의 분석대로 W_{JFET}의 개선이 가장 컸으며, 잡음을 2배로 해도 W_{JFET} 오차는 46% 줄었다. 같은 DEVSIM 실행 수에서도 S2가 우세하여(그림 3(b)) 120회에서 S2(60점)는 0.084였고 S1은 480회에서도 0.113이었다. S3는 S2와 차이가 없었고(0.073), 선형 Ridge 회귀도 S1 0.117에서 S2 0.073으로 같은 개선을 보여 이득이 특정 모델이 아니라 특징의 정보에서 비롯됨을 확인하였다. 사전 등록한 국소 Cramér–Rao 하한은 개선 순서(W_{JFET} > N_{pw} ≈ Q_{it,eff})를 맞게 예측하였다. 잡음이 없으면 S1만으로도 오차가 거의 0이 되므로, 잡음 모델 없이 평가하면 다중 온도의 이점이 드러나지 않는다."),
  ...figure(require("path").join(__dirname, "../figures/fig3_rq1.png"), 284, "그림 3. 역추정 오차(테스트 128점, GP): (a) S1 대비 S2(기본·2배 잡음, 오차 막대: 부트스트랩 95% CI, 점선: 무정보 추정), (b) 동일 DEVSIM 실행 수 비교(S1 n점, S2 n/2점, 시드 5개)."),
  h2("4.2 고온 물리 가정에 대한 강건성"),
  body("표 2와 같이 학습과 평가가 같은 물리를 따르면 채널 이동도 온도지수를 0, −1로 바꿔도 S2의 이득은 35%, 32%로 유지되었고, 감소는 주로 W_{JFET}(개선 53→47→36%)에서 나타났다. 즉 이득의 근원은 채널과 드리프트 이동도의 온도 의존성이 서로 다르다는 점이며 부호가 반대일 필요는 없다. 고온에서 Q_{it,eff}가 줄면 V_{th} 온도 이동이 Q_{it,eff} 정보를 직접 담아 이득이 49%, 70%로 커졌다. 반면 기준 물리로 학습한 모델에서는 다른 이동도 지수의 423 K 특징(γ = −1에서 g_{m,max} −38%)이 학습 범위를 벗어나 S2 오차가 S1보다 크게 나빠졌고, Q_{it,eff} 30% 감소도 이득을 없앴다. 사전 예측 중 같은 물리에서의 이득 유지는 맞았으나, 지수 0에서도 S2가 우세하리라는 예측은 틀려 불일치의 영향을 과소평가하였다. 사후 분석으로 다섯 가정을 섞어 학습하면 모든 경우에 22–29%의 이득이 유지되었다(2배 잡음 13–21%). 학습에 없던 기생 직렬저항도 두 특징 집합의 오차를 모두 크게 키웠으므로, 다중 온도 역추정에는 고온 물리의 보정 또는 불확실한 가정을 포함한 학습과 직렬저항 보정이 전제되어야 한다."),
  new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 90, after: 40 }, children: runs("표 2. 423 K 물리 가정에 따른 S2의 평균 정규화 MAE(nominal 잡음, GP, S1 = 0.112)", { size: 15 }) }),
  table2,
  new Paragraph({ spacing: { before: 20, after: 90, line: 210 }, children: runs("†다섯 가정을 무작위로 섞은 풀로 학습(사후 분석). *소자별 0.1–0.3 mΩ·cm^{2}, 탐색적 분석(S1 = 0.378).", { size: 13 }) }),
  h2("4.3 적응형 선택의 효과(RQ2)"),
  body("그림 4에서 불확실도 정책은 무작위 대비 최종 오차를 0.0025(95% CI [−0.0039, −0.0009]) 줄였고, 무작위의 최종 정확도에 약 106점에서 도달하여 시뮬레이션을 약 12% 절감하였다. Sobol 순서도 비슷한 개선(−0.0023)을 보였고 2배 잡음에서는 유의한 차이가 없었다. 초기 무작위 표본이 30점이면 절감 효과는 약 20%(Sobol 24%)로 커졌으나 90점에서는 15%(9%)여서, 이득의 상당 부분은 공간 충전에서 오며 4차원의 매끄러운 문제에서는 공간 충전 설계가 강한 기준선이다."),
  h2("4.4 LLM 보조 선택(RQ3)"),
  body("LLM 응답 60회 중 59회가 검증을 통과하였고, 1회는 근거 길이 초과(421자 > 400자)로 거절되었으며 형식 오류나 목록 밖 ID는 없었다. LLM은 불확실도 상위 10개 중 평균 63%만 선택하고 나머지는 다양성을 위해 골랐으며(59회 중 56회 더 넓은 분포), 근거에서 언급한 오차가 큰 변수 축으로 선택 범위를 넓혔다(47/59회). 그러나 최종 오차는 불확실도 정책과 유의한 차이가 없었고(+0.0012, 95% CI [−0.0008, +0.0035]) 시드 간 편차가 더 컸으며, 사유 코드는 55/59회에서 모든 코드를 나열하여 설명력이 낮았다. 후보가 이미 불확실도 상위 20개로 제한되어 선택 여지가 좁고, 불확실도 정책도 다양성을 반영하며, 정책 간 차이(10^{−3} 수준)가 시드 간 변동과 비슷하기 때문으로 보인다. 따라서 귀무가설을 기각할 근거는 없으며, LLM은 검증기와 결합하여 구조화되고 검증 가능한 선택 인터페이스로 동작했으나 사유 코드의 설명력은 입증되지 않았다."),
  ...figure(require("path").join(__dirname, "../figures/fig4_policies.png"), 284, "그림 4. 실험 선택 정책 비교(S2, RF, 시드 10개): (a) 학습곡선(시드 평균), (b) 최종 라운드의 짝지은 차이(부트스트랩 95% CI, 오른쪽: 평균 [CI], 우세 시드 수)."),
  h1("Ⅴ. 결론"),
  body("DEVSIM 기반 4H-SiC 평판형 MOSFET DC 해석 파이프라인을 구축·검증하고, 423 K 특성이 JFET 폭–채널 이동도, P-well 도핑–계면전하의 혼동을 줄여 역추정 오차를 평균 36% 낮춤을 보였다. 이 이득은 선형 모델에서도 같았고, 학습과 평가가 같은 물리를 따르면 채널 이동도 온도지수(+1, 0, −1)와 계면전하의 온도 의존성을 바꿔도 유지되었다. 그러나 다른 이동도 지수로 학습한 모델은 실패했으므로, 실측 적용에는 고온 물리의 보정 또는 불확실한 가정을 포함한 학습(22–29% 이득)과 직렬저항 보정이 필요하다. 적응형 선택은 시뮬레이션을 12–20% 절감했으나 Sobol 설계와 비슷하였고, LLM 보조 선택은 98%의 유효 응답률로 구조화되고 검증 가능한 선택을 수행했으나 정확도 이득은 없었다. 본 결과는 시뮬레이션과 가정한 잡음 모델에 근거하며 단극성 근사와 단일 소자 구조로 한정된다. 300 K V_{th} 추출 정밀도(최대 3 mV)와 g_{m,max} 분해능(약 1.3%)은 가정한 측정 잡음보다 작다. 실측 검증과 항복 특성은 향후 과제이다."),
  h1("참고문헌"),
);
const REFS = [
  "B. J. Baliga, Fundamentals of Power Semiconductor Devices, 2nd ed., Springer, 2019.",
  "T. Kimoto and J. A. Cooper, Fundamentals of Silicon Carbide Technology, Wiley-IEEE Press, 2014.",
  "D. A. Boiko, R. MacKnight, B. Kline, and G. Gomes, “Autonomous chemical research with large language models,” Nature, vol. 624, pp. 570–578, 2023.",
  "J. Müting, P. Natzke, A. Tsibizov, and U. Grossner, “Influence of process variations on the electrical performance of SiC power MOSFETs,” IEEE Trans. Electron Devices, vol. 68, no. 1, pp. 230–235, 2021.",
  "J. Ha, G. Lee, and J. Kim, “Machine learning approach for characteristics prediction of 4H-silicon carbide NMOSFET by process conditions,” in Proc. IEEE Region 10 Symp. (TENSYMP), 2021.",
  "G. Fan, T. Ma, X. Sun, X. Wang, K. L. Low, and L. Shao, “AgenticTCAD: A LLM-based multi-agent framework for automated TCAD code generation and device optimization,” in Proc. Design, Automation & Test in Europe (DATE), 2026.",
  "J. E. Sanchez, “DEVSIM: A TCAD semiconductor device simulator,” Journal of Open Source Software, vol. 7, no. 70, p. 3898, 2022.",
  "D. L. Scharfetter and H. K. Gummel, “Large-signal analysis of a silicon Read diode oscillator,” IEEE Trans. Electron Devices, vol. 16, no. 1, pp. 64–77, 1969.",
  "M. Ikeda, H. Matsunami, and T. Tanaka, “Site effect on the impurity levels in 4H, 6H, and 15R SiC,” Phys. Rev. B, vol. 22, no. 6, p. 2842, 1980.",
  "M. Roschke and F. Schwierz, “Electron mobility models for 4H, 6H, and 3C SiC,” IEEE Trans. Electron Devices, vol. 48, no. 7, pp. 1442–1447, 2001.",
  "J. Burin, P. Gaggl, S. Waid, A. Gsponer, and T. Bergauer, “TCAD parameters for 4H-SiC: A review,” arXiv:2410.06798, 2025.",
  "Cree, Inc., C2M0080120D Silicon Carbide Power MOSFET Data Sheet, Rev. D, 2019.",
  "S. Yu, M. H. White, and A. K. Agarwal, “Experimental determination of interface trap density and fixed positive oxide charge in commercial 4H-SiC power MOSFETs,” IEEE Access, vol. 9, pp. 149118–149124, 2021.",
  "Keysight Technologies, B1505A Power Device Analyzer/Curve Tracer Data Sheet.",
  "C. E. Rasmussen and C. K. I. Williams, Gaussian Processes for Machine Learning, MIT Press, 2006.",
  "B. Settles, “Active learning literature survey,” Computer Sciences Tech. Rep. 1648, Univ. of Wisconsin–Madison, 2009.",
  "I. M. Sobol’, “On the distribution of points in a cube and the approximate evaluation of integrals,” USSR Comput. Math. Math. Phys., vol. 7, no. 4, pp. 86–112, 1967.",
  "Anthropic, “Structured outputs,” Claude Platform Documentation, https://platform.claude.com/docs/en/build-with-claude/structured-outputs.",
];
REFS.forEach((r, i) => B.push(new Paragraph({ alignment: AlignmentType.JUSTIFIED, indent: { left: 340, hanging: 340 }, spacing: { line: 220 },
  children: runs(`[${i + 1}] ${r}`, { size: 14 }) })));

const page = { size: { width: 11906, height: 16838 }, margin: { top: 1417, bottom: 1417, left: 1134, right: 1134 } };
const doc = new Document({
  styles: { default: { document: { run: { font: FONT, size: 18 } } } },
  sections: [
    { properties: { page, column: { count: 1 } }, children: head },
    { properties: { type: SectionType.CONTINUOUS, page, column: { count: 2, space: 397, equalWidth: true } }, children: B },
  ],
});
const out = VERSION === "proc" ? "draft_v3_proceedings.docx" : "draft_v3_review_anonymous.docx";
Packer.toBuffer(doc).then((buf) => { fs.writeFileSync(require("path").join(__dirname, out), buf); console.log("wrote", out); });
