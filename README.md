# DEVSIM 기반 4H-SiC 평판형 MOSFET 다중 온도 역추정

> **Reproducibility artifact for an undergraduate research paper**  
> *Multi-Temperature Inverse Estimation of Process-Outcome Parameters in 4H-SiC Planar MOSFETs under Physics-Model Mismatch*

[![CI](https://github.com/mseokq23/sic-mosfet-devsim/actions/workflows/ci.yml/badge.svg)](https://github.com/mseokq23/sic-mosfet-devsim/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![DEVSIM](https://img.shields.io/badge/DEVSIM-2.11.0-blue.svg)](environment.txt)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](environment.txt)

이 저장소는 **DEVSIM 기반 4H-SiC 평판형 MOSFET의 다중 온도 공정 결과 파라미터 역추정**, **적응형 TCAD 표본선택**, **LLM 보조 후보 재순위화**, **물리모델 불일치 강건성 시험**을 재현하기 위한 코드·설정·원자료·분석 결과를 제공합니다.

> [!IMPORTANT]
> 이 저장소는 시뮬레이션 기반 **모델 내부 식별성 및 지정된 model mismatch**를 검증합니다. 실제 제작 소자의 정량적 공정 역추정이나 실측 보정 완료 모델을 주장하지 않습니다.

## Artifact 상태

| 항목 | 값 |
|---|---|
| 저장소 상태 | 논문 제출용 재현성 artifact |
| 기준 소자·물리 설정 | [`v1.1-frozen`](https://github.com/mseokq23/sic-mosfet-devsim/releases/tag/v1.1-frozen) |
| 현재 기준 브랜치 | `main` |
| 권장 인용 단위 | 최종 paper release 및 해당 commit SHA |
| Nominal dataset | 512 pool + 128 independent test points, 각 300/423 K |
| Robustness dataset | 4개 변형 × (512 pool + 128 test), 423 K 재계산 |
| 라이선스 | MIT |

논문 제출 시에는 변경 가능한 `main` URL보다 **최종 GitHub Release 또는 commit SHA**를 사용하십시오. 현재 개발 이력에는 `v1.0-frozen`, `v1.1-frozen` 태그가 있으며, 논문 V3 전체를 고정하는 별도 paper release를 생성할 예정입니다.

## 연구 질문

- **RQ1 — 다중 온도 식별성:** 300 K와 423 K 특징을 결합하면 300 K 단독 특징보다 잠재 공정 결과 파라미터 역추정 오차가 감소하는가?
- **RQ2 — 적응형 표본선택:** 동일 TCAD 실행예산에서 불확실도·다양성 기반 표본선택은 무작위 또는 Sobol 선택보다 효율적인가?
- **RQ3 — LLM 보조 선택:** 구조화 출력과 결정론적 검증기로 제한된 LLM 재순위화가 수치 정책보다 추가적인 정확도 이득을 제공하는가?
- **Robustness — 모델 불일치:** 채널 이동도 온도지수, 계면전하 온도의존성 및 기생 직렬저항이 다중 온도 역추정에 미치는 영향은 무엇인가?

## 핵심 결과

1. 동일 물리 조건에서 300/423 K 특징은 300 K 단독 특징보다 평균 정규화 MAE를 약 **36%** 낮췄습니다.
2. 채널 이동도 온도지수 \(\gamma\in\{+1,0,-1\}\)의 matched-physics 조건에서 다중 온도 이득은 유지됐습니다.
3. Nominal physics로 학습한 다중 온도 모델은 고온 물리가 달라진 out-of-model 시험에서 큰 오차를 보여, 추가 정보와 model-form risk를 함께 평가해야 함을 확인했습니다.
4. 실행 후 수행한 탐색적 혼합물리 학습은 검토한 시나리오에서 약 **22–29%**의 다중 온도 이득을 유지했습니다.
5. LLM 후보 재순위화는 수치적 불확실도·다양성 정책 대비 유의한 정확도 향상을 보이지 않았습니다. 따라서 LLM은 성능 우위 기법이 아니라 **구조화되고 검증 가능한 보조 선택 인터페이스**로 해석합니다.

정확한 수치, 신뢰구간 및 조건은 아래 결과 문서를 기준으로 확인하십시오.

- [RQ1: feature-set comparison](results/summary/rq1.md)
- [RQ1: equal-budget comparison](results/summary/rq1_equal_budget.md)
- [RQ2: adaptive selection](results/summary/rq2.md)
- [RQ3: LLM-assisted selection](results/summary/rq3.md)
- [Robustness results and prediction audit](docs/ROBUSTNESS_RESULTS.md)
- [Nominal pool/test audit](docs/AUDIT.md)

## 범위와 한계

| 구분 | 포함 |
|---|---|
| 소자 | 1.2 kV급 문헌 구조를 참고한 2D planar MOSFET half-cell |
| 온도 | 300 K, 423 K |
| 추정 대상 | `Wjfet`, `Npwell`, `Qit_eff` |
| 교란변수 | `mu_channel_scale` |
| 수송·물리 | Poisson, 전자 연속방정식, Scharfetter–Gummel, SRH, 도핑·온도 의존 이동도, 불완전 이온화, 정적 유효 계면전하, 유효 채널 이동도 |
| 강건성 시험 | 채널 이동도 온도지수, 423 K 계면전하 변화, 기생 직렬저항, 혼합물리 학습 |
| 제외 | 충돌 이온화, self-heating, 산화막 열화, Fermi–Dirac 통계, 전계 의존 이동도, 동적 계면 트랩 |
| 검증 범위 | 동일 TCAD 모델 내 역식별성과 지정된 물리·기생성분 불일치 |
| 미검증 | 항복전압 정량 검증, 실측 기반 parameter calibration, 실제 공정조건과 유효 파라미터의 일대일 대응 |

`1.2 kV급`은 참고 구조의 등급을 의미하며, 본 연구에서 충돌 이온화를 사용해 항복전압을 검증했다는 의미가 아닙니다.

## 논문–Artifact 대응표

| 논문 분석 | 입력 자료 | 분석·실행 코드 | 결과·증거 |
|---|---|---|---|
| PN/MOSCAP/MOSFET 검증 | `results/pretest/`, `results/stage_a_v11/` | `scripts/gate1_pn_diode.py`, `gate2_moscap.py`, `gate3_mosfet.py`, `gate3_report.py` | `docs/PRETEST.md`, `results/gates/` |
| Stage A·국소 식별성 | `configs/design_stage_a.csv`, `results/stage_a_v11/` | `scripts/stage_a_report.py`, `scripts/identifiability.py` | Stage A report 및 CRB 출력 |
| RQ1 S1/S2/S3 | `results/pool/`, `results/test/` | `scripts/run_al.py`, `scripts/summarize_results.py` | `results/summary/rq1.md` |
| 동일 계산예산 비교 | 동일 pool/test | `scripts/summarize_results.py` | `results/summary/rq1_equal_budget.md` |
| Ridge 기준선 | 동일 pool/test | `scripts/ridge_rq1.py` | `results/summary/`의 Ridge 결과 |
| RQ2 능동학습 | `results/al/` | `scripts/run_al.py`, `scripts/al_ninit.py` | `results/summary/rq2.md` |
| RQ3 실제 LLM | `results/al_live/nominal/` | `scripts/llm_check.py`, `scripts/run_al.py` | `rq3.md`, `llm_calls.jsonl`, `meta.json` |
| 물리 강건성 | `results/pool_gamma*`, `pool_qitT*`, 대응 test | `scripts/robustness.py` | `docs/ROBUSTNESS_RESULTS.md`, `results/summary/robustness.md` |
| 혼합물리 학습 | 기존 nominal/variant pool·test | `scripts/robustness_mixed.py` | `results/summary/`의 mixed-physics 결과 |
| 결과 감사 | nominal pool/test 및 설계 CSV | `scripts/audit_results.py` | `docs/AUDIT.md`, `results/pool/audit.json` |
| 논문 그림 | 위 결과 | `scripts/make_paper_figures.py` | `paper/figures/` |

## 빠른 검증

아래 단계는 저장된 결과와 분석 파이프라인을 점검하기 위한 절차입니다. 전체 DOE를 다시 계산하지 않습니다.

### GitHub Codespaces

1. **Code → Codespaces → Create codespace**를 선택합니다. 4-core 환경을 권장합니다.
2. `postCreate`가 의존성 설치, editable install, Gate 0 점검 및 환경 잠금을 수행합니다.
3. 다음 명령을 실행합니다.

```bash
pytest -q
python scripts/gate0_check.py
```

CI도 push와 pull request에서 위 두 검사를 수행합니다. CI 배지는 **단위시험과 Gate 0**의 상태이며, 전체 TCAD DOE 자동 재현을 의미하지 않습니다.

### 로컬 Linux

```bash
git clone https://github.com/mseokq23/sic-mosfet-devsim.git
cd sic-mosfet-devsim

python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
pip install -e .

pytest -q
python scripts/gate0_check.py
```

DEVSIM import에는 MKL이 필요합니다. 정확한 검증 환경과 설치 패키지는 [`environment.txt`](environment.txt)를 확인하십시오.

## 결과 재분석

저장된 nominal pool/test에서 논문 결과 요약을 다시 생성합니다.

```bash
python scripts/audit_results.py \
  results/pool configs/design_pool.csv \
  results/test configs/design_test.csv

python scripts/summarize_results.py
python scripts/robustness.py
python scripts/robustness_mixed.py
```

예상 결과는 다음 위치에 생성되거나 갱신됩니다.

- `results/pool/audit.json`
- `results/summary/rq1.md`
- `results/summary/rq1_equal_budget.md`
- `results/summary/rq2.md`
- `results/summary/rq3.md`
- `results/summary/robustness.md`

> [!NOTE]
> 재분석 명령은 제출용 release에서 검증된 명령을 기준으로 사용하십시오. 분석 스크립트가 기존 summary를 갱신할 수 있으므로, 원본 보존이 필요하면 별도 branch 또는 깨끗한 clone에서 실행하십시오.

## 부분 TCAD 재현

전체 DOE 전에 최소 소자 물리와 추출 파이프라인을 검증합니다.

```bash
python scripts/gate1_pn_diode.py
python scripts/gate2_moscap.py
python scripts/gate3_mosfet.py
python scripts/gate3_report.py
```

| Gate | 목적 |
|---|---|
| Gate 0 | Python·DEVSIM·수치환경 확인 |
| Gate 1 | 4H-SiC PN diode 물리 확인 |
| Gate 2 | MOS capacitor 전위·전하 검증 |
| Gate 3 | Planar MOSFET 전달·출력 특성과 특징 추출 확인 |

사전 테스트 결과와 판정 기준은 [`docs/PRETEST.md`](docs/PRETEST.md)를 확인하십시오.

## 전체 TCAD 재현

전체 재현은 nominal DOE와 강건성 변형 계산을 포함합니다.

### Nominal DOE

```bash
python -m sicsim.runner configs/design_pool.csv \
  --out results/pool --jobs 4 --budget-s 20000

python -m sicsim.runner configs/design_test.csv \
  --out results/test --jobs 4
```

- Pool: 512 공정점 × 2온도 = 1,024 runs
- Independent test: 128 공정점 × 2온도 = 256 runs
- 총 nominal 계산: 1,280 runs
- Runner는 run별 JSON을 즉시 저장하므로 같은 명령으로 중단 지점부터 재개할 수 있습니다.

GitHub Actions의 DOE workflow를 사용하면 design CSV를 shard로 나눠 계산할 수 있습니다. 상세 명령과 예상 계산량은 [`docs/ROADMAP.md`](docs/ROADMAP.md)를 확인하십시오.

### Robustness DOE

강건성 workflow는 다음 네 변형의 423 K 결과를 재계산합니다.

- `gamma0`: \(\mu_{\mathrm{surf}}\) 온도지수 0
- `gamma_m1`: \(\mu_{\mathrm{surf}}\) 온도지수 −1
- `qitT10`: 423 K에서 \(|Q_{\mathrm{it,eff}}|\) 10% 감소
- `qitT30`: 423 K에서 \(|Q_{\mathrm{it,eff}}|\) 30% 감소

GitHub에서 **Actions → robustness-batch → Run workflow**를 사용합니다. Workflow는 변형·pool/test별 shard를 실행하고, 결과를 병합한 후 분석 결과를 commit합니다.

- 변형 계산: 4 × (512 pool + 128 test) = 2,560 runs at 423 K
- 300 K nominal 결과는 물리가 같으므로 재사용
- 논문에 사용된 실행: GitHub Actions run `37164222148`

## Artifact 무결성

### Nominal dataset

- 512 pool points × 2 temperatures = 1,024 runs
- 128 independent test points × 2 temperatures = 256 runs
- 설계–run 누락, 중복 및 파라미터 불일치: 0
- 모든 nominal runs 수렴
- 저장 특징과 원시 곡선 재추출 결과 일치
- 다른 머신에서 선택한 runs를 독립 재계산해 부동소수점 허용오차 내 일치 확인

자세한 수치 정밀도 하한과 재현성 점검은 [`docs/AUDIT.md`](docs/AUDIT.md)를 확인하십시오.

### Robustness dataset

- 4 variants × (512 pool + 128 test) = 2,560 runs
- 수렴: 2,560 / 2,560
- 재시도: 0
- 출력곡선 조기 종료: 0
- 각 변형의 물리 hash와 실행 commit 기록

자세한 결과와 실행 전 예측의 대응은 [`docs/ROBUSTNESS_RESULTS.md`](docs/ROBUSTNESS_RESULTS.md)를 확인하십시오.

> 수렴성과 독립 재계산 일치는 계산 일관성의 증거이며, 제작 소자에 대한 실험 검증을 의미하지 않습니다.

## 분석 계획과 탐색적 분석

| 분석 | 분류 | 기록 |
|---|---|---|
| Nominal RQ1–RQ3 | 동결 설정과 분석 규칙에 따른 주 분석 | `docs/ROADMAP.md`, `docs/AUDIT.md` |
| 이동도 지수·계면전하 변형 | 실행 전 commit된 분석 계획 | `docs/PREDICTIONS_ROBUSTNESS.md` |
| 기생 직렬저항 | 탐색적 분석 | 실행 전 계획 문서에서 사전 예측이 아님을 명시 |
| 혼합물리 학습 | 결과 확인 후 수행한 사후 분석 | `docs/ROBUSTNESS_RESULTS.md`에서 post-hoc으로 명시 |

Git commit은 분석 계획과 결과의 시간 순서를 보여주지만, OSF 등 독립기관의 정식 사전등록과 동일한 의미로 사용하지 않습니다. 본 저장소에서는 **“실행 전 commit된 분석 계획”**으로 표현합니다.

## LLM 보조 표본선택

LLM은 DEVSIM을 직접 제어하지 않습니다. 수치 정책이 사전 선별한 후보를 구조화된 정보에 따라 재순위화하며, 출력은 Pydantic 기반 결정론적 검증기를 통과해야만 사용됩니다.

논문에 사용된 live-API 기록은 [`results/al_live/nominal/`](results/al_live/nominal/)에 있습니다.

- `llm_calls.jsonl`: 후보 입력 요약, 구조화 응답, 검증 결과, 선택 ID 및 호출 메타데이터
- `meta.json`: 실행 모드와 모델 설정
- `al_curves.csv`: 정책별 학습곡선
- `rq1_feature_sets.json`: 동일 실행에서 사용한 특징집합 결과

외부 호스팅 LLM은 서비스 업데이트와 비결정성 때문에 동일 응답을 bitwise 재현하지 못할 수 있습니다. 따라서 논문 결과의 canonical record는 commit된 JSONL 로그입니다. API key 값은 기록하지 않으며, key가 없거나 호출이 실패한 경우 live 실행을 dry-run으로 조용히 대체하지 않고 중단합니다.

Live 호출 전 점검:

```bash
python scripts/llm_check.py
```

Live 정책 실행:

```bash
python scripts/run_al.py \
  --pool results/pool \
  --test results/test \
  --seeds 10 \
  --noise nominal \
  --policies llm \
  --llm-live \
  --out results/al_live
```

LLM 실호출에는 별도의 API key와 비용이 필요합니다. 논문의 성능 결과는 과거 dry-run이 아니라 `results/al_live/nominal/`의 live 기록만 사용합니다.

## Provenance

논문 artifact의 핵심 실행 순서는 다음과 같습니다.

| 단계 | 식별자 | 의미 |
|---|---|---|
| 기준 설정 동결 | tag `v1.1-frozen` | fixed-pitch JFET 정의와 nominal 물리·DOE 동결 |
| Nominal pool/test 감사 | `docs/AUDIT.md` | 설계 대응, 수렴, 특징 재추출, 독립 재계산 확인 |
| 실제 LLM 결과 | `results/al_live/nominal/` | live API 호출·검증·정책 결과 기록 |
| 강건성 실행 전 계획 | commit `ae736696632ceddd81432e08c63ad82715734515` | 변형 설정·예측·판정 규칙을 결과 실행 전에 기록 |
| 강건성 결과 | Actions run `37164222148` | 2,560 variant runs 및 자동 분석 |
| 강건성 결과 commit | `c83ea195e9216c65ddd0507d6e759fbff0fd32d9` | Actions bot이 결과와 run ID를 저장 |

정확한 chronology는 Git history와 다음 문서에서 확인할 수 있습니다.

- [`docs/PREDICTIONS_ROBUSTNESS.md`](docs/PREDICTIONS_ROBUSTNESS.md)
- [`docs/ROBUSTNESS_RESULTS.md`](docs/ROBUSTNESS_RESULTS.md)
- [`docs/AUDIT.md`](docs/AUDIT.md)
- [`docs/ROADMAP.md`](docs/ROADMAP.md)

## 저장소 구조

```text
configs/
  baseline.yaml              # nominal 소자·물리·바이어스 설정
  parameter_bounds.yaml      # DOE 파라미터 범위
  noise_model.yaml           # 분석 잡음 모델
  variants/                  # 강건성 물리 변형

src/sicsim/
  params.py, physics.py      # 파라미터와 DEVSIM 물리모델
  devices.py                 # 1D diode/MOSCAP, 2D MOSFET half-cell
  solver.py, simulate.py     # 램프·재시도·단일 run
  extract.py                 # 전기적 특징 추출
  runner.py, worker.py       # 병렬·재개·shard 실행
  design.py                  # Stage A, Sobol pool, test design
  analysis.py, alsim.py      # 역추정·정책 비교
  schema.py, llm.py          # 구조화 출력·검증·LLM 기록

scripts/                     # 검증, DOE, 분석, 그림 생성 entry points
results/                     # commit된 원자료, 감사 결과 및 요약
paper/                       # 논문 초안, 캡션 및 그림
docs/                        # 분석 계획, 감사, 강건성 결과, 로드맵
tests/                       # 단위·파이프라인 테스트
```

기존 코드·결과 디렉터리 구조는 논문 artifact와 개발 이력을 보존하기 위해 유지합니다.

## 알려진 수치 한계

- 300 K \(V_{\mathrm{th}}\): 할선 반복의 수치 오차가 최대 약 3 mV이며 nominal 측정 잡음 가정보다 작습니다.
- \(g_{m,\max}\): 0.25 V 게이트 바이어스 격자로 인한 약 1.2–1.4%의 분해능 한계가 있습니다.
- 300 K 고문턱 소자의 \(V_{\mathrm{GS}}=4\,\mathrm{V}\) 전류 일부는 수치 바닥 아래이므로 잡음 모델에서 \(10^{-11}\,\mathrm{A/cm}\)로 절단합니다.
- `noise=none`은 분석 잡음을 추가하지 않는다는 뜻이며, 수치해석·격자·추출 오차까지 0이라는 뜻은 아닙니다.

자세한 감사 결과는 [`docs/AUDIT.md`](docs/AUDIT.md)를 확인하십시오.

## 환경과 계산량

검증 환경:

- Ubuntu GitHub-hosted runner 및 GitHub Codespaces
- Python 3.12
- DEVSIM 2.11.0
- 배정밀도
- medium mesh
- `MKL_NUM_THREADS=1`, `OMP_NUM_THREADS=1` 권장

패키지 잠금과 실제 설치 환경은 다음 파일에 있습니다.

- [`requirements.txt`](requirements.txt)
- [`requirements-optional.txt`](requirements-optional.txt)
- [`environment.txt`](environment.txt)
- [`pyproject.toml`](pyproject.toml)

계산시간은 실행 환경에 따라 달라집니다. 전체 nominal DOE와 robustness DOE는 quick verification보다 훨씬 많은 계산자원이 필요하므로, 논문 결과 확인만을 위해 전체 TCAD를 다시 실행할 필요는 없습니다.

## 논문 그림 재생성

```bash
python scripts/make_paper_figures.py
```

생성 결과는 [`paper/figures/`](paper/figures/)에 저장됩니다. 그림에 사용된 정확한 숫자는 `results/summary/`와 `paper/figure_notes.json`을 함께 확인하십시오.

## 인용

최종 논문과 artifact release가 확정되면 아래 정보를 갱신합니다.

```bibtex
@software{sic_mosfet_devsim_2026,
  author  = {Lee, Minseok},
  title   = {Reproducibility Artifact for Multi-Temperature Inverse Estimation of 4H-SiC Planar MOSFET Parameters},
  year    = {2026},
  url     = {https://github.com/mseokq23/sic-mosfet-devsim},
  version = {paper-v3.0}
}
```

논문 제출 후 가능한 경우 GitHub Release를 Zenodo에 보존하여 DOI를 추가합니다.

## 라이선스

코드는 [MIT License](LICENSE)를 따릅니다. 외부 소프트웨어와 데이터의 라이선스는 각 프로젝트의 조건을 따릅니다.
