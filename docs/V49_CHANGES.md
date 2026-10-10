# V4.9 원고: 검토 의견 반영

V4.8(커밋 `3d58cee`)에 대한 외부 검토 의견을 모두 반영한 판이다. 새 계산은 없고, 수치는 V4.8과 같은 결과 파일
(`results/summary/v47_*.md`, `v48_extra_stats.md`, `v47_rq3_ablation.json`)에서 가져왔다. 기존 본문은 줄이지 않았다.

| 항목 | 위치 |
|---|---|
| 원고 빌더 | `paper/final/build_v49.js` (`proc`/`review`) |
| 원고 | `paper/final/proceedings_v49_5p.docx`, `paper/final/review_v49_4p.docx` |
| V4.8 빌더 | `paper/final/build_v48.js` (재현용으로 그대로 둠) |

## 반영 내용

| 검토 의견 | 반영 | 근거 |
|---|---|---|
| 혼합학습 초록 문장("gave no better mean error")이 0.079~0.088 대 0.086과 어긋남 | 영문 초록: "avoided this failure but showed no statistically established gain over the repeated measurement". 국문 초록·본문·결론: "이 실패는 피했지만 반복 측정보다 낫다는 통계적 근거는 없었다", 본문은 "통계적으로 검증되지 않았다" | `v48_extra_stats.md` 1절(mixed, CI 모두 0 포함) |
| 혼합학습이 "불일치를 완화했다"는 제안 표현 | 쓰지 않음. 시험한 다섯 물리가 모두 학습 가정에 포함되었으므로 "포함해 학습하면 실패를 피했다"로 쓰고, 가정 밖의 물리는 시험하지 않았음을 4.2절에 명시 | `scripts/robustness_mixed.py` |
| RQ2를 회고적 풀 평가로 일관 표기 | 초록, 서론 RQ2, 3.4절(“512개 후보의 특성을 미리 계산해 두고 정책이 고른 점만 학습에 사용”), 4.3절, 그림 4 캡션, 결론, 한계·향후 과제(온라인 방식) | `src/sicsim/alsim.py` |
| 능동학습 이득은 후보 다양성으로 설명 | 4.3절: Sobol도 무작위 대비 0.0023을 줄여 불확실도와 같았으므로 절감의 상당 부분은 후보 다양성으로 설명될 수 있고 알고리즘적 우수성은 주장하기 어렵다. 결론에도 반영 | `v47_rq3_ablation.md` 보조 비교 |
| LLM 기여 범위 한정 | 구조화 출력·검증 작동(240회 중 238회 통과), 입력 교란 시 선택 변화, 수치 정책보다 나은 선택이라는 근거 없음, 사유 코드의 설명력 미입증을 결론에 명시 | `v47_rq3_ablation.json` |
| 사유 코드의 물리적 설명력 | 4.4절: 거의 모든 호출에서 여섯 범주 중 같은 다섯 범주가 함께 선택됨(A: 네 범주 60/60회, 한 범주 58/60회) | `v47_rq3_ablation.json` `behaviour.*.reason_codes` |
| 초록에 S2 대 S1×2 차이와 CI | 국문·영문 초록에 “반복 측정 대비 −0.014, 95% CI −0.024~−0.006”, 결론에도 같은 값 | `v47_repeat_control.md` S2−S1x2 |
| 서론 끝 신규성 문단 | 기여 문단을 따로 두고 “새로움은 새 알고리즘이 아니라 이득의 출처를 가르는 비교 설계에 있다”와 “방법 요소는 기존 기법을 따랐다”를 추가(‘최초’ 표현 없음) | — |
| 제목 | “LLM 보조 실험 선택 평가” → “LLM 보조 TCAD 표본 선택 평가”, “LLM-Assisted Experiment Selection” → “LLM-Assisted TCAD Sample Selection” (README 제목도 같이 변경) | 선택 대상은 DEVSIM 설계점 |

## 쪽수

검토 의견을 모두 넣고 기존 본문을 줄이지 않았으므로 V4.8보다 길어졌다(측정용 대체 글꼴 기준 심사용 약 14줄, 프로시딩 약 26줄 증가).
같은 측정에서 심사용은 5쪽째로 약 8줄, 프로시딩은 6쪽째로 약 16줄 넘친다. 이 측정은 Word보다 길게 나오는 경향이 있었으나(V4.7 심사용에서 특히 큼)
제출 전 Word(Windows)에서 쪽수를 반드시 확인해야 한다. 그림·표 위치 기본값: 심사용 F2·F3 = pre, F4 = late, 나머지 post /
프로시딩 F4·T3 = pre, 나머지 post(측정상 가장 짧은 배치).
