"""Write docs/PRETEST.md (numbers for G3/Stage A/extraction read from results JSON/CSV) and docs/PARAMETERS.md."""
import json, sys
from pathlib import Path
import pandas as pd
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT / "src"))
from sicsim.params import parameter_table
from sicsim.config import load_config, material_from
P = ROOT / "results" / "pretest"
g3 = json.load(open(P / "gate3_summary.json"))
sa = pd.read_csv(P / "stage_a" / "stage_a_deltas.csv")
sas = json.load(open(P / "stage_a" / "stage_a_summary.json"))
ra = json.load(open(P / "vth_refine" / "runs" / "R_base_T300.json"))["features"]
rb = json.load(open(P / "vth_refine" / "runs" / "R_qit_+20pct_T300.json"))["features"]
cox = 3.9 * 8.8541878128e-14 / 50e-7; theo = 1.602176634e-19 * 0.2e12 / cox
m, t = g3["mesh"], g3["temperature_300_to_423"]
L = []; w = L.append
w("# 사전 테스트 결과 (pre-test)\n")
w("> 이 문서는 동결 전(v0.3) 사전 테스트 기록이다. v1.0에서 채널 이동도 온도지수=1, 채널 이동도 교란 변수 추가로 동결됨(docs/ROADMAP.md).\n")
w("실행: 2026-10-02, 샌드박스(Python 3.12.3, 1 CPU, 3 GB), devsim 2.11.0 + mkl 2026.1.0(PARDISO). "
  "원자료: `results/pretest/` (run별 JSON에 곡선·수치 이력 포함). 이 문서는 `scripts/make_pretest_report.py`로 생성.\n")
w("## 요약\n")
w("| 단계 | 내용 | 결과 | 판정 |\n|---|---|---|---|")
w("| G0 | 설치·공식 예제 | `pip install devsim` 단독은 import 실패(BLAS/LAPACK 없음) → mkl 추가로 해결. 공식 diode_1d 0.36 s, 2회 비트 동일 | 통과 |")
w("| G1 | 1D PN 다이오드 | Vbi = 해석해(300 K 2.8817/2.9547 V, 423 K 2.7162/2.7734 V; 불완전이온화 on/off), "
  "Al 1e18 이온화율 6.0%→20.9%(300→423 K) 해석해 일치, 공핍폭 오차 1.3%, 이상계수 ~2→~1.1 | 통과 |")
w("| G2 | 1D MOSCAP | Vfb 오차 ≤5 mV, ΔVfb(Qeff ±1e12) ∓2.318~2.322 V vs 이론 ∓2.320 V, Vth 오차 0~28 mV(공핍근사 대비) | 통과 |")
w(f"| G3 | 2D half-cell MOSFET | medium 메시 채택(사전 허용오차 전부 통과), 배정밀도=128-bit 특징, 비트 단위 재현, 온도 방향 타당 | 통과 |")
w(f"| Stage A | ±20% OAT × 300/423 K | {sas['n_converged']}/{sas['n_runs']} 수렴, 사전 예상 부호 "
  f"{sum(c['pass_'] for c in sas['checks'])}/{len(sas['checks'])} 일치 | 조건부: 보정 추출로 재실행 필요 |\n")
w("## G3: 2D MOSFET (기준 소자, 300 K, 배정밀도, 단극성 DD)\n")
w("| 메시 | 노드 | 시간(s) | Vth(V) | SS(mV/dec) | gm,max(mS/cm) | Ion(mA/cm) | Ron,sp(mΩ·cm²) | ID@2V(A/cm) |\n|---|---|---|---|---|---|---|---|---|")
for lv in ("coarse", "medium", "fine"):
    r = m[lv]
    w(f"| {lv} | {r['nodes']} | {r['runtime_s']:.0f} | {r['vth_V']:.4f} | {r['ss_mV_dec']:.2f} | {1e3*r['gm_max_S_per_cm']:.3f} | "
      f"{1e3*r['ion_A_per_cm']:.2f} | {r['ron_mohm_cm2']:.3f} | {r['id_vds_req_A_per_cm']:.4f} |")
d = g3["medium_vs_fine"]
w(f"\nmedium−fine: ΔVth {1e3*d['vth_V']:.2f} mV, SS {100*d['ss_mV_dec']:.2f}%, gm {100*d['gm_max_S_per_cm']:.2f}%, "
  f"Ion {100*d['ion_A_per_cm']:.2f}%, Ron {100*d['ron_mohm_cm2']:.2f}% → 허용오차(20 mV/5%/3%/2%/2%, "
  f"`configs/sweep_protocol.yaml`, 실행 전 등록) 모두 통과. coarse는 gm {100*g3['coarse_vs_fine']['gm_max_S_per_cm']:.1f}%로 탈락, "
  f"출력곡선도 {m['coarse']['output_truncated_at_V']:.2f} V에서 중단.\n")
pr = g3["precision_dp_vs_xp"]
w(f"- 정밀도: 배정밀도 vs 128-bit 특징 차이 Vth {abs(pr['vth_V']):.1e} V, SS {100*abs(pr['ss_mV_dec']):.3f}%. "
  f"수치 전류 바닥(|ID+IS|) {g3['kcl_floor']['double']:.1e} vs {g3['kcl_floor']['extended']:.1e} A/cm. 128-bit는 약 3배 느림 → 배정밀도 채택, "
  "SS 창을 1e-10~1e-6 A/cm(바닥의 77배 이상)로 설정.")
w(f"- 재현성: 같은 조건 2회 실행 곡선 비트 단위 동일 = {g3['repeatability_bitwise_identical']}.")
w("- 300 K → 423 K: " + ", ".join(f"{k} {v['T300']:.4g} → {v['T423']:.4g}" for k, v in t.items()) + "\n")
w("![G3](../results/pretest/fig_gate3_mosfet.png)\n")
w("## Stage A: 단일 변수 ±20% (보간 추출 기준)\n")
w("| T(K) | 변수 | ΔVth(V) | SS | gm,max | Ion | Ron,sp | ID@2V |\n|---|---|---|---|---|---|---|---|")
for _, r in sa[sa.level == "+20pct"].iterrows():
    w(f"| {r['T']} | {r['var']} +20% | {r['vth_V']:+.4f} | {100*r['ss_mV_dec']:+.2f}% | {100*r['gm_max_S_per_cm']:+.2f}% | "
      f"{100*r['ion_A_per_cm']:+.2f}% | {100*r['ron_mohm_cm2']:+.2f}% | {100*r['id_vds_req_A_per_cm']:+.2f}% |")
w("\n(qit +20% = 더 큰 음의 유효 계면전하, −1.2e12 cm⁻²)\n")
w("- 사전 예상과 다른 항목: Wjfet↑에서 Ron,sp가 증가. Ron,sp는 half-cell 폭으로 정규화하므로 JFET를 넓히면 셀 피치가 커지고, "
  "이 설계(μ_surf=20 cm²/Vs)에서는 채널 저항이 지배적이라 면적 정규화 저항이 커진다. 깊이당 전류(ID@2V)는 예상대로 증가. → 논문에 정규화 기준 명시.")
w("- 온도 대비 ΔVth(423−300 K): " + ", ".join(f"{k} {v:+.4f}" for k, v in sas["dvth_T"].items()) +
  " V. 점 사이 차이(수 mV)가 비단조적 → 아래 보간 오차가 원인으로 확인됨.\n")
w("![Stage A](../results/pretest/fig_stage_a.png)\n")
w("## 추출 보정: 바이어스 재해석(secant)으로 Vth·SS 결정\n")
w(f"0.25 V 격자 보간 대신 목표 전류(1e-10, 1e-6, 1e-4 A/cm)에서 게이트 전압을 할선법으로 다시 풀어 결정(run당 해 약 11회 추가, 시간 +10%). "
  f"검증: Qit_eff +20%의 Vth 이동 = {rb['vth_V']-ra['vth_V']:.5f} V (보간 {rb['vth_interp_V']-ra['vth_interp_V']:.5f} V), "
  f"해석해 qΔQ/Cox = {theo:.5f} V. 기준 소자 Vth {ra['vth_V']:.4f} V(보간 {ra['vth_interp_V']:.4f} V). "
  "→ `baseline-v0.3`부터 적용, Stage A·풀 계산은 이 버전으로 수행.\n")
w("## 수치·모델 결정 사항 (사전 테스트에서 확정)\n")
for s in [
    "단극성 DD: 정공 연속방정식은 n+ 영역 정공 농도(~1e-35 cm⁻³) 때문에 수렴 불가 → 정공은 접지된 소스/바디와 평형(φp=0). "
    "충돌이온화·바디다이오드 도통이 없는 n채널 동작 범위에서 유효. 초안 방법 절 문장 수정 필요.",
    "수렴 기준: DEVSIM 상대오차 = |Δx|/(|x|+1e-10). 1e-9는 배정밀도 바닥 아래 → relative_error 1e-6.",
    "2D 메셔: 외곽 경계에는 contact가 생성되지 않음 → 얇은 더미 영역(gas_*)을 두어 경계를 내부화(공식 예제 방식).",
    "MOSCAP 반전: SiC는 소수캐리어 공급이 없어(deep depletion) 전체 DD로 DC 반전이 풀리지 않음 → MOSCAP은 평형 Poisson으로 검증.",
    "출력곡선: VDS ≥ 2 V에 도달한 뒤의 수렴 실패만 허용(ID@2V 특징 유지), 그 전 실패는 run 실패로 기록.",
    "Ioff: 물리값 ~1e-29 A/cm로 배정밀도 바닥 아래 → DOE 특징에서 제외(값은 기록하되 ioff_below_floor 플래그).",
    "실행 시간: medium·배정밀도 1 run ≈ 80~90 s/코어 → 풀 512 + 테스트 128점 × 2온도 ≈ 30 코어·시간.",
]:
    w(f"- {s}")
w("\n## 위험 요소와 동결 전 확인\n")
for s in [
    "RQ1: Npwell과 Qit_eff는 Vth에서 섞이지만 SS·gm,max로 300 K만으로도 상당 부분 구분 → 423 K 추가 이득이 작을 수 있음. "
    "고온 정보는 주로 Wjfet(드리프트/JFET 저항 비중↑)에 기여하며 채널 이동도 온도지수(현재 0) 가정에 민감 → 문헌으로 확정 후 동결, '제한적 개선'도 해석 가능한 틀 준비.",
    "파라미터: Qf(+1e12), μ_surf(20 cm²/Vs, 온도지수 0), χ/φm(3.7/4.1 eV), Qit_eff 범위(−1.5e12~−0.5e12 cm⁻²)는 가정값.",
    "devcontainer·CI·DOE 워크플로는 실제 GitHub/Codespaces에서 아직 미실행 → 첫 Codespace 생성 시 Gate 0·pytest 통과부터 확인.",
]:
    w(f"- {s}")
(ROOT / "docs" / "PRETEST.md").write_text("\n".join(L) + "\n")
rows = parameter_table(material_from(load_config()))
cols = list(rows[0].keys())
pt = ["# 4H-SiC 모델 파라미터 (configs/baseline.yaml 적용값, " + str(load_config().get("version")) + ")\n", "| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)]
pt += ["| " + " | ".join(str(r.get(c, "")) for c in cols) + " |" for r in rows]
pt.append("\n출처는 TCAD Parameters for 4H-SiC: A Review(arXiv:2410.06798)에 정리된 원문헌. 리뷰는 단일 권장 세트를 제시하지 않으므로 핵심 값은 민감도로 보고한다.")
(ROOT / "docs" / "PARAMETERS.md").write_text("\n".join(pt) + "\n")
print("wrote docs/PRETEST.md, docs/PARAMETERS.md", len(L), "lines;", len(rows), "parameters")
