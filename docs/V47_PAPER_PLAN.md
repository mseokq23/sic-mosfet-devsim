# 원고 V4.7 수정 계획 (결과 반영 전 작성)

기준 원고: V4.6a(프로시딩 5쪽, 심사용 익명 4쪽). 결과 파일이 나오면 아래 순서로 반영한다. 숫자 자리는 `[ ]`로 표시했다.
원고 빌드: `paper/final/build_final.js`를 복사한 `build_v47.js`(proc/review 두 모드).

## 1. 결과와 무관하게 바꿀 것
- **제목**: "…다중 온도 역추정과 LLM 보조 실험 선택 **평가**" / "…and an Evaluation of LLM-Assisted Experiment Selection…".
  LLM이 개선을 낸다는 인상 대신 검증했다는 의미가 되도록 한다.
- **서론 2문단**: "온도는 추가 정보가 될 수 있다"를 기존 기법으로 먼저 인정한다. 고온 Vth 감소로 계면 트랩·산화막 전하를 구분한
  측정 연구[yu]와, 채널 저항과 드리프트 저항의 온도 의존성을 분리한 연구[stark]를 인용한다.
- **서론 3문단**: TCAD 데이터로 학습한 역추정과 학습에 없는 물리(hidden variable)에 대한 취약성[wong2020; mehta2020],
  다중 온도 측정을 쓴 TCAD-ML 보정[nguyen2026]을 추가하고, 이들이 다중 온도 이득을 반복 측정과 분리하거나
  고온 물리 불일치에서 평가하지 않았다는 점으로 차별화한다. LLM 쪽은 LLM 기반 실험 선택이 고전적 방법보다 낫지 않다는
  벤치마크[gupta2025]를 추가한다.
- **기여 문장**: ① 반복 측정을 통제한 온도 고유 이득, ② 고온 물리 불일치 시 역전(5~8배), ③ LLM 선택의 절제 평가 순서로 쓴다.
- **2.3절 또는 한계**: 기준 모델에 고온 트랩 방출이 없다는 점은 이미 적혀 있으므로 유지한다. 채널 이동도 온도지수의
  부호가 계면 상태에 따라 실제로 달라진다는 근거[das2022]를 γ = 0, −1 시험의 동기로 한 문장 추가한다.
- **3.5절·결론**: 능동학습 곡선이 CPU에 따라 라운드 1부터 조금 달라진다는 점과, v4.7 비교는 한 환경에서 만들었다는 점을 한 문장.
- **심사용 익명본**: 참고문헌의 저장소 URL과 3.5절 커밋 해시를 "익명 저장소(심사 후 공개)"로 바꾼다. 프로시딩본은 그대로.
- **지면 확보 후보**: 2.2절 배정밀도/128비트 문장, 3.3절 직렬저항 변환의 이분법 설명, 4.4절 사유 코드·토큰 통계, 2.3절 데이터시트
  비교 일부.

## 2. 결과에 따라 바꿀 것

### 3.2절(방법) 추가 — 반복 측정 통제
> 423 K 특징의 이득에는 같은 소자를 한 번 더 측정한 효과도 섞여 있으므로, 300 K 특징을 독립 잡음으로 두 번 실현해 평균한
> 통제 집합 S1×2를 같은 방식으로 학습·평가하였다(학습·시험 모두). 두 측정 사이의 잡음 상관 ρ ∈ {0, 0.5, 0.9}도 비교하였다.

### 4.1절(RQ1) 수정
- 그림 3(a)에 S1×2 막대를 추가한다(S1, S1×2, S2, 변수별).
- 문장 틀(C1·C2 성립 시): "300 K를 두 번 측정한 S1×2의 오차는 [ ]로 S1보다 [ ]% 작았다. S2는 S1×2보다 W_JFET에서 [ ]
  (95% CI [ , ]) 작았으나 N_pw·Q_it,eff에서는 차이가 없었다([ ], [ ]). 즉 온도 고유 이득은 300 K에서 채널 이동도와 공선인
  W_JFET에 집중된다." 국소 하한 비(0.38 대 반복 0.71)를 같은 문단에 둔다.
- C1 실패 시: "S2의 이득은 같은 횟수의 반복 측정과 통계적으로 구분되지 않았다"로 RQ1 주장을 낮추고, 서론·초록·결론을 같이 고친다.
- ρ 결과는 한 문장(예: "두 측정의 잡음이 상관된 경우(ρ = 0.9) 반복 이득은 [ ]로 줄었으나 S2의 W_JFET 이득은 [ ]였다").

### 4.2절·표 2(강건성) 수정
- 표 2 아래 또는 본문에 "S1×2 = [ ] (423 K 물리와 무관)" 기준선을 둔다. 메시지: 고온 물리가 불확실하면 300 K 반복 측정이
  얻는 이득([ ]%)은 위험 없이 확보되고, 423 K의 추가 이득은 물리가 맞을 때만 남는다.
- 직렬저항 행에 S1×2 값을 추가한다(C9).

### 4.4절(RQ3) 재작성
- 3.4절에 조건 B(익명화)·C(정보 섞기)·D(상위 20 내 무작위)를 한 문단으로 정의한다.
- 그림 4(b)를 같은 환경의 A·B·C·D와 불확실도의 짝지은 차이로 바꾼다.
- 문장 틀(Q1·Q3·Q4 성립 시): "세 LLM 조건과 D의 최종 오차는 불확실도 정책과 구분되지 않았다([ ]). 정보를 섞은 C에서 LLM은
  표시된 불확실도 상위 10개 중 [ ]개를 골라 표시 숫자를 따랐고(실제 상위 10과의 겹침 [ ], 무작위 기대 0.50), 틀리게 표시한 최악
  변수 방향으로 배치를 넓혔다([ ]회, 무작위 기대 [ ]%). 즉 LLM은 제공 정보를 읽고 따르지만, 후보가 이미 불확실도 상위로 걸러진
  이 설정에서는 그 정보가 정확도 차이로 이어지지 않았다." 기존의 원인 추정 문장("…원인으로 보인다")은 삭제한다.

### 초록·결론
- 초록: 개선 수치 → 반복 측정 통제 결과 → 고온 물리 불일치의 역전 → LLM 절제 결과 순서. 각 1문장.
- 결론 첫 문장: "다중 온도 측정은 단일 온도에서 교란 변수와 공선인 파라미터에 대해 반복 측정 이상의 정보를 주지만, 그 이득은
  고온 물리가 맞을 때에만 유지된다."(C1·C2 성립 시)

## 3. 추가할 참고문헌 (서지 확인됨)
- [stark] R. Stark, A. Tsibizov, S. Race, T. Ziemann, I. Kovacevic-Badstuebner, U. Grossner, "Temperature dependence of the channel
  and drift resistance of SiC power MOSFETs extracted from I-V and C-V measurements," Mater. Sci. Forum, vol. 1092, pp. 165–170, 2023.
- [wong2020] H. Y. Wong et al., "TCAD-machine learning framework for device variation and operating temperature analysis with
  experimental demonstration," IEEE J. Electron Devices Soc., vol. 8, pp. 992–1000, 2020.
- [mehta2020] K. Mehta, S. S. Raju, M. Xiao, B. Wang, Y. Zhang, H. Y. Wong, "Improvement of TCAD augmented machine learning using
  autoencoder for semiconductor variation identification and inverse design," IEEE Access, vol. 8, pp. 143519–143529, 2020.
- [nguyen2026] L. M. L. Nguyen, E. Ong, M. Eng, Y. Zhang, H. Y. Wong, "Ga₂O₃ TCAD mobility parameter calibration using simulation
  augmented machine learning with physics-informed neural network," IEEE Trans. Electron Devices, vol. 73, no. 2, pp. 775–781, 2026.
- [das2022] S. Das, Y. Zheng, A. Ahyi, M. A. Kuroda, S. Dhar, "Study of carrier mobilities in 4H-SiC MOSFETs using Hall analysis,"
  Materials, vol. 15, no. 19, 6736, 2022.
- [gupta2025] R. Gupta, J. Hartford, B. Liu, "LLMs for Bayesian optimization in scientific domains: Are we there yet?," EMNLP 2025
  (arXiv:2509.21403). 수록 형식(본회의/Findings)과 쪽수는 제출 전 확인.
- 선택: [brynjarsdottir2014] J. Brynjarsdóttir, A. O'Hagan, "Learning about physical parameters: the importance of model
  discrepancy," Inverse Problems, vol. 30, no. 11, 114007, 2014.
