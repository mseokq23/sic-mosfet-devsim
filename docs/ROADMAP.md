# 실험 로드맵 (마감 2026-10-19, 심사용 익명 4쪽)

| 단계 | 기간 | 내용 | 산출물 |
|---|---|---|---|
| 1 | 10/2~3 | Codespaces 환경(postCreate: mkl+devsim 설치, Gate 0, environment.txt) | environment.txt, CI 통과 |
| 2 | ~10/5 | G1 PN·G2 MOSCAP·G3 MOSFET 재실행(사전 테스트 재현), G4 문헌 정성 비교 | results/gates, 그림 2 초안 |
| 3 | ~10/6 | 파라미터·프로토콜 동결: Qf, μ_surf·온도지수, χ/φm, Qit_eff 범위, 메시(medium), 추출 규칙 → `version` 태그 | configs 동결 커밋 |
| 4 | ~10/7 | Stage A(기준점+±10/20%, 2온도, 26 run) → 방향·효과크기 확인 | stage_a_summary.json, 그림 |
| 5 | ~10/11 | Sobol 풀 512점 + 독립 테스트 128점 × 2온도(약 1,280 run) 사전 계산 | results/pool, results/test |
| 6 | ~10/13 | RQ1(S1/S2/S3) + RQ2·RQ3(정책 4종 × 시드 10, 초기 60 + 10×6) | rq1_feature_sets.json, al_curves.csv, llm_calls.jsonl |
| 7 | ~10/17 | 그림 4개+표 1, 원고 / 10/18~19 검토·제출 | 논문 |

## 명령
```bash
# 4 Stage A
python -c "from sicsim.design import stage_a; stage_a().to_csv('configs/design_stage_a.csv', index=False)"
python -m sicsim.runner configs/design_stage_a.csv --out results/stage_a --jobs 4
python scripts/stage_a_report.py results/stage_a
# 5 후보 풀 + 테스트셋 (Codespaces 병렬, 또는 Actions > doe-batch 로 샤딩)
python -c "from sicsim.design import sobol_pool, random_set; sobol_pool(512, seed=2026).to_csv('configs/design_pool.csv', index=False); random_set(128, seed=12345).to_csv('configs/design_test.csv', index=False)"
python -m sicsim.runner configs/design_pool.csv --out results/pool --jobs 4 --budget-s 20000   # 재실행하면 이어서
python -m sicsim.runner configs/design_test.csv --out results/test --jobs 4
# 6 RQ1~3 (LLM 실제 호출은 --llm-live + ANTHROPIC_API_KEY)
python scripts/run_al.py --pool results/pool --test results/test --seeds 10
```

## 계산량(사전 테스트 실측 기반)
medium 메시 1 run(1 공정점 × 1 온도) ≈ 80 s/코어. 풀+테스트 1,280 run ≈ 28 코어·시간
(4코어 Codespace ≈ 7 h). 러너는 run별 JSON을 즉시 저장하므로 중단돼도 같은 명령으로 재개된다.

## 동결 전 결정 사항
- 단극성 근사(정공 평형)를 방법 절에 명시(초안의 '전자·정공 연속방정식' 문장 수정).
- Ioff는 배정밀도 수치 바닥(~1e-12 A/cm) 아래(물리값 ~1e-29 A/cm) → DOE 특징에서 제외.
- Qit_eff 범위(현재 가정 −1.5e12~−0.5e12 cm⁻²), Qf(+1e12), μ_surf(20 cm²/Vs, 온도지수 0)는 문헌·민감도로 확정.
- LLM 정책 모델 ID 1개로 고정, 요청마다 model/prompt hash/input hash/응답/토큰 기록(llm_calls.jsonl).

## 사전 테스트 이후 변경(baseline-v0.3)
- Vth·SS는 목표 전류에서 게이트 전압을 다시 푸는 보정 추출 사용(격자 보간 오차 2~7 mV 제거).
- `configs/design_stage_a.csv`(13점), `design_pool.csv`(Sobol 512점, seed 2026), `design_test.csv`(128점, seed 12345)는 미리 생성되어 있음.
- 첫 작업: Codespace 생성 → `pytest -q` → Stage A 재실행(`--jobs 4`, 26 run, 약 10분) → `python scripts/stage_a_report.py results/stage_a`.
