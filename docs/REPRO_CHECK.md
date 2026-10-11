# 재현 점검 기록 (2026-10-11)

원고 V4.9의 코드(커밋 `366f6e3`, 결과 커밋 `90134a2`)를 논문 실행과 **다른 CPU**에서 처음부터 설치해 README의 재현 명령을 모두 실행하고,
다시 만든 파일을 커밋된 파일과 비교한 기록이다. 새 결과 파일은 커밋하지 않았다(비교 후 폐기).

## 환경

| 항목 | 값 |
|---|---|
| CPU | Intel(R) Xeon(R) Processor @ 2.10GHz, 2코어(논문 실행: AMD EPYC 7763, GitHub Codespaces / GitHub-hosted runner) |
| OS | Linux 6.18, glibc 2.39 |
| Python | 3.12.3, `pip install -r requirements.txt && pip install -e .` (DEVSIM 2.11.0, MKL 2026.1.0, NumPy 2.5.3, scikit-learn 1.9.1) |
| 스레드 | `MKL_NUM_THREADS=1`, `OMP_NUM_THREADS=1`, `PYTHONHASHSEED=0` |
| 비교 방법 | git worktree에서 실행한 뒤 `git status`와 숫자 비교(`scripts/compare_outputs.py`와 같은 방법) |

## 설치 점검

| 명령 | 결과 | 시간 |
|---|---|---|
| `pytest -q` | 52개 통과 | 25 s |
| `python scripts/gate0_check.py` | `official diode_1d x2: PASS (identical)` | 1.4 s |

## L1 · 저장된 원자료에서 다시 계산

| 명령 | 시간 | 커밋된 파일과의 차이 |
|---|---|---|
| `audit_results.py` | 16 s | 대리모델 통계의 끝자리(절대 차이 ≤ 2×10<sup>−10</sup>) |
| `stage_a_report.py`, `identifiability.py` | 8 s | CRB 끝자리(상대 차이 ≤ 6×10<sup>−14</sup>) |
| `ridge_rq1.py` | 2 s | 없음 |
| `repeat_control.py` | 123 s | 숫자 끝자리(절대 차이 ≤ 7×10<sup>−9</sup>), 메타데이터(코드 커밋, CPU, Python). `v47_repeat_control.md`는 머리말의 코드 커밋 한 줄만 다름 |
| `robustness.py` | 90 s | 끝자리(절대 차이 ≤ 2×10<sup>−7</sup>); `robustness.md` 동일 |
| `robustness_mixed.py` | 103 s | `robustness_mixed.md` 동일, `table2_robustness.csv` 끝자리(상대 차이 ≤ 1.1×10<sup>−7</sup>) |
| `v48_extra_stats.py` | 64 s | 끝자리(절대 차이 ≤ 5×10<sup>−7</sup>); `v48_extra_stats.md` 동일 |
| `rq3_ablation.py` | 65 s | 숫자 동일, 코드 커밋·생성 시각만 다름 |
| `make_paper_figures.py`, `make_v47_figures.py`, `make_fig3_robust.py`, `make_slide_figures.py` | 79 s | 그림 파일은 바이트가 다름(글꼴 환경). 표 1 머리말이 `μ_ch` → `s_μ`(논문 표기)로 바뀜 → 이번 갱신에서 반영 |

결론: GP·Ridge 기반 수치(RQ1, 반복 측정 통제, 강건성, 사후 비교)는 Markdown 요약표와 논문에 인용한 모든 수치가 같다.

## L1 · 능동학습 재실행

| 명령 | 시간 | 결과 |
|---|---|---|
| `run_al.py --noise none/nominal/high` | 각 270–290 s | 무작위·Sobol 곡선 동일. 불확실도·dry-run LLM 곡선은 모든 시드에서 라운드 1부터 다름 |
| `summarize_results.py` | 16 s | `rq2.md` nominal: 불확실도 최종 0.1238 → 0.1242, 무작위 대비 −0.0025 [−0.0039, −0.0009] → −0.0021 [−0.0041, +0.0003], 도달 점 수 106 → 106 |
| `al_ninit.py --n-init 30 90` | 205 s | 초기 30·90점은 커밋된 값과 같음(Sobol 24.4%·8.7%, 불확실도 20.2%·14.7%). 초기 60점은 다시 만든 `results/al/nominal`을 읽어 불확실도 절감 11.9%(커밋 12.0%) |

- v4.7 실행(Codespaces, AMD EPYC 7763)에서는 불확실도 곡선이 논문 실행과 완전히 같았다(`v47_rq3_ablation.md`의 환경 점검, 최대 차이 0). 따라서 RQ2·RQ3의 곡선은 실행 CPU 종류에 의존한다.
- 초기 30·90점 결과가 Intel에서 그대로 재현되고 초기 60점 기준은 AMD 실행이므로, `al_ninit_summary.csv`는 서로 다른 CPU에서 계산한 곡선을 함께 쓴 것으로 보인다.
- 출력 형식 차이: 현재 `summarize_results.py`는 `rq2.md` 머리말을 "dry-run"으로 쓰고, 현재 `al_ninit.py`는 `ci_lo`·`ci_hi` 열과 `al_ninit_curves.csv`를 쓴다(커밋된 파일은 `ci` 문자열 열과 `al_ninit_curves_n30_n90.csv`).

## RQ3 · A0 재생

`run_al.py --policies llm --replay-log results/al_live/nominal/llm_calls.jsonl` (156 s): payload 해시 일치 0/60, 저장 응답 50/60이 후보 목록 밖이라 대체 규칙 적용, 최종 0.1240(A0 0.1250). 재생은 후보 목록이 같아야 하므로 같은 CPU 종류에서만 A0를 재현한다.

## L2 · 소자 검증과 run 재계산

| 대상 | 시간 | 결과 |
|---|---|---|
| Gate 1 (`gate1_pn_diode.py`) | 11 s | 실행 시간·환경 정보만 다름 |
| Gate 2 (`gate2_moscap.py`) | 9 s | 반복 횟수·실행 시간과 1.6×10<sup>−15</sup> V 차이 |
| `rerun_check.py` T0000 300·423 K | 60 s | 해시 일치, 특징 ≤ 6×10<sup>−16</sup>, 전달곡선 ≤ 2.7×10<sup>−13</sup>, 출력곡선 0 |
| `rerun_check.py` T0001 423 K | 53 s | 해시 일치, 특징 ≤ 2×10<sup>−16</sup>, 곡선 0 |
| `rerun_check.py` γ = 0 변형 T0002 423 K | 50 s | 해시 일치, 특징 0, 전달곡선 ≤ 1.9×10<sup>−12</sup> |

### Gate 3를 동결 설정(v1.1)으로 다시 계산

커밋된 `results/pretest/gate3/*.json`은 사전 시험 단계(설정 이름 `baseline-v0.2-pretest`)에 저장되었다. 그 뒤(v0.3) V<sub>th</sub>·SS 추출을
0.25 V 격자 보간에서 목표 전류의 게이트 전압을 다시 푸는 보정 추출로 바꿨으므로, 기록의 V<sub>th</sub>는 보간 방식 값이다.
같은 300 K medium·fine 사례를 v1.1-frozen으로 다시 계산했다(medium 52 s, fine 120 s).

- **I–V 곡선은 두 사례 모두 기록과 비트 단위로 같다**(전달·출력 곡선 상대 차이 0). g<sub>m,max</sub>, I<sub>on</sub>, R<sub>on,sp</sub>도 같다.
- 다시 계산한 결과의 `vth_interp_V`(보간 방식)는 기록의 V<sub>th</sub>와 같고, `vth_V`(보정 추출)는 논문 2.3절 값이다.

| V<sub>th</sub> 추출 | 기준 소자 V<sub>th</sub> (medium) | ΔV<sub>th</sub> (medium − fine) | SS | g<sub>m,max</sub> | I<sub>on</sub> | R<sub>on,sp</sub> |
|---|---|---|---|---|---|---|
| 격자 보간 (커밋된 기록) | 3.7718 V | 0.073 mV | +0.10% | −2.66% | −0.85% | +0.87% |
| 보정 추출 (동결 설정, 논문) | 3.7646 V | 0.028 mV | +0.11% | −2.66% | −0.85% | +0.87% |

메시 비교의 결론(허용오차 안, 논문 2.3절의 "V<sub>th</sub> 0.07 mV, R<sub>on,sp</sub> 0.9% 이내")은 어느 추출 방식에서도 성립한다.

## 원고와 리포트

| 대상 | 결과 |
|---|---|
| `paper/final/build_v49.js proc`, `review` (docx 9.7.1) | 각 2 s, 본문 텍스트(pandoc 추출)가 커밋된 `proceedings_v49_5p.docx`, `review_v49_4p.docx`와 같음 |
| `scripts/make_report.py` | 2 s, 1.0 MB. 브라우저(Chromium)에서 그래프 13개, 스크립트 오류 없음, 폭 390·768·1280 px에서 가로 스크롤 없음. `--embed-plotly`(plotly 6.9.0, plotly.js 3.7.0)도 같음 |
