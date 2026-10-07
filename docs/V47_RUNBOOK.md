# v4.7 통제 실험 실행 절차 (Codespaces)

분석 계획과 사전 예측: [`PREDICTIONS_V47.md`](PREDICTIONS_V47.md). 논문 V4.6a 시점의 main은 태그 `v1.7-baseline`으로
고정되어 있으며, 이 브랜치(`exp/v4.7-controls`)는 main을 바꾸지 않는다. 새 DEVSIM 계산은 없다.

## 0. 준비 (1분)
```bash
git fetch origin --tags
git checkout exp/v4.7-controls && git pull
pip install -e .            # 새 모듈(sicsim.controls, sicsim.ablation) 반영
```
- `docs/PREDICTIONS_V47.md`를 읽고, 예측을 고치려면 **실행 전에** 고쳐서 커밋한다(실행 후에는 고치지 않는다).
- Codespaces secret `MSEOKQ_CLAUDE`가 이 저장소에 연결되어 있어야 한다(`llm` 단계에서만 필요).

## 1. 한 번에 실행 (약 45–60분)
```bash
bash scripts/v47_run_all.sh all
```
단계별로 나눠 실행해도 된다. **RQ3의 `numeric`과 `llm`은 같은 Codespace 세션에서 연달아 실행한다**(능동학습 곡선은 CPU에 따라
조금 달라지므로, 주 비교 조건은 한 환경에서 만든다).

| 단계 | 명령 | 내용 | API | 예상 시간 |
|---|---|---|---|---|
| check | `bash scripts/v47_run_all.sh check` | 브랜치, 계획·코드 커밋 상태, 단위 시험 | 없음 | 1분 |
| control | `bash scripts/v47_run_all.sh control` | RQ1 반복 측정 통제(S1x2, ρ 스윕, Ridge, 잡음 실현 5개, 직렬저항) | 없음 | 5분 |
| numeric | `bash scripts/v47_run_all.sh numeric` | RQ3 D(상위 20 내 무작위) + 불확실도·무작위·Sobol 재실행 | 없음 | 10분 |
| llm | `bash scripts/v47_run_all.sh llm` | RQ3 A(원본 형식)·B(익명화)·C(정보 섞기), 조건마다 60회 호출 | 180회 | 30–40분 |
| report | `bash scripts/v47_run_all.sh report` | 요약표 생성 | 없음 | 1분 |

- `control` 출력의 `reproduction:` 줄이 `EXACT` 또는 `CLOSE`여야 한다(논문의 S1 0.112275, S2 0.072011 재현 점검).
- `llm`은 시작 전에 `llm_check.py`로 호출 1회를 시험한다. 키가 없거나 호출이 계속 실패하면 dry-run으로 넘어가지 않고 멈춘다.
- 중간에 멈추면 같은 명령을 다시 실행한다. 끝난 조건은 건너뛰고, 끝나지 않은 시도는 `results/al_v47/_aborted/`로 옮긴 뒤 다시 실행한다.
- 토큰 사용량은 논문 실행(60회에 입력 약 18만, 출력 약 4만)의 약 3배이다.

## 2. 결과 커밋
```bash
git add results/al_v47 results/summary/v47_*
git commit -m "v4.7 control results"
git push
```

## 3. 산출물

| 파일 | 내용 |
|---|---|
| `results/summary/v47_repeat_control.{json,md}` | S1·S1x2·S1x2cat·S2·S3의 오차, S2−S1x2 등 짝지은 대비와 CI, ρ 스윕, CRB 비 |
| `results/summary/v47_repeat_control_points.csv` | 시험점별 오차(그림 재생성용) |
| `results/al_v47/{numeric,named,anon,shuffled}/nominal/` | 학습곡선(`al_curves.csv`), LLM 로그(`llm_calls.jsonl`, 표시한 payload 포함), `meta.json`(코드·계획 커밋, CPU) |
| `results/summary/v47_rq3_ablation.{json,md}` | 조건별 최종 오차, 짝지은 비교와 CI, 동등성, LLM 선택 행동 지표, 환경 점검 |

결과가 나오면 예측과의 대조를 `docs/V47_RESULTS.md`에 정리하고, 원고 수정은 [`V47_PAPER_PLAN.md`](V47_PAPER_PLAN.md)를 따른다.

## 4. 원본으로 돌아가기
```bash
git checkout main            # 또는: git checkout v1.7-baseline
```
이 브랜치의 결과와 코드는 main에 합치기 전까지 main의 결과·그림·원고에 영향을 주지 않는다.
