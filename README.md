# sic-mosfet-devsim

DEVSIM 기반 4H-SiC 평판형(planar) MOSFET 다중 온도 공정편차 분석 및 LLM 보조 적응형 실험 자동화
(LLM-Assisted Adaptive Experiment Automation for Multi-Temperature Process-Variation Analysis of
4H-SiC Planar MOSFETs Using DEVSIM) — 학부 논문용 재현 가능한 실험 저장소.

## 빠른 시작 (GitHub Codespaces)
1. Code → Codespaces → *Create codespace* (4-core 권장). `postCreate`가 자동으로
   `requirements.txt` 설치(**mkl 포함 — DEVSIM은 mkl 없이 import 실패**) → `pip install -e .` →
   Gate 0 점검 → `environment.txt` 잠금을 수행합니다.
2. `pytest -q` (DEVSIM 없이 도는 검증기·추출기·파이프라인 테스트)
3. 물리 검증: `python scripts/gate1_pn_diode.py`, `gate2_moscap.py`, `gate3_mosfet.py` → `gate3_report.py`
4. 실험 단계와 명령은 `docs/ROADMAP.md`(현재 **v1.0 동결** 절), 사전 테스트 결과는 `docs/PRETEST.md`.

## 구조
```
configs/   baseline.yaml(물리·바이어스·추출 프로토콜) parameter_bounds.yaml sweep_protocol.yaml(사전 등록 허용오차)
src/sicsim params·physics(DEVSIM 모델) devices(1D 다이오드/MOSCAP, 2D half-cell) solver(램프·재시도)
           simulate(1회 실험) extract(특징) worker/runner(격리·병렬·재개·샤드) design(Stage A·Sobol 풀·테스트셋)
           schema(pydantic·검증기) llm(Claude 구조화 출력·dry-run·JSONL 로그) analysis(S1/S2/S3·역추정) alsim(정책 비교)
scripts/   gate0~3, stage_a_report, run_al, merge_runs, lock_env
results/pretest/  사전 테스트 원자료(JSON)·그림
```
동결 설정 v1.0: 1.2 kV급 half-cell, 추정 변수 Wjfet·Npwell·Qit_eff, 교란 변수 채널 이동도, 300/423 K.
물리 범위: Poisson, 전자 연속(단극성; 정공은 소스/바디와 평형), SG, SRH, 도핑·온도 의존 이동도,
불완전 이온화, 유효 계면전하(정적), 유효 채널 이동도. 제외: 충돌 이온화, self-heating, 산화막 열화,
Fermi-Dirac 통계, 전계 의존 이동도.  License: MIT.
