# RQ3: LLM 보조 선택 (results/al_live)


## nominal: 호출 60회, 모드 ['live'], 모델 ['claude-sonnet-5-5']
- 검증 통과 59/60 (거절 → 사전 규칙대로 uncertainty로 대체), 거절 사유: {'SCHEMA: short_rationale: Strin': 1}
- 선택 ID의 불확실도 순위(1=가장 불확실, 후보 20개): 평균 8.7, 상위 10위 내 비율 0.63
- 사유 코드: {'HIGH_UNCERTAINTY': 59, 'TARGET_CONFUSION_REGION': 59, 'BOUNDARY_COVERAGE': 59, 'DIVERSITY': 59, 'LOW_TRAIN_DENSITY': 55}
- 토큰 입력/출력 합계 179589/40056, 평균 지연 6.3 s
- 최종 mae_norm: LLM 0.1250 ± 0.0042
  - vs random: Δ -0.0013 [95% CI -0.0038, +0.0014], LLM 우세 8/10
  - vs uncertainty: Δ +0.0012 [95% CI -0.0008, +0.0035], LLM 우세 4/10
  - vs sobol: Δ +0.0010 [95% CI -0.0012, +0.0033], LLM 우세 4/10
