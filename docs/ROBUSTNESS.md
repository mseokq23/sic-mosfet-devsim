# 강건성 실험 실행 안내 (v1.3)

1. 패치 적용·검사: `unzip -o sicsim_patch_v1.3_robustness.zip && pytest -q` (39 passed)
2. 로컬 스모크(약 2분, 4코어 병렬): `bash scripts/smoke_variants.sh`
   - 기대값: qitT30 ΔV_th = −489 mV, qitT10 = −163 mV(= qΔQ/C_ox), γ 변형은 R_on 증가·V_th 소폭 증가, 모두 conv True
3. 사전 예측 확인 후 커밋·푸시: `docs/PREDICTIONS_ROBUSTNESS.md`가 결과보다 먼저 커밋되어야 한다.
4. GitHub → Actions → robustness-batch → Run workflow (기본값 그대로) 또는 `gh workflow run robustness-batch.yml`
   - 80 jobs(4 변형 × 풀 16 + 테스트 4 샤드), job당 32 run. 동시 실행 한도(Free 20, Pro 40)를 넘는 job은 자동 대기.
   - 완료 시 merge job이 `results/pool_<v>/`, `results/test_<v>/`, `results/summary/robustness.{json,md}`를 커밋한다.
5. `git pull` 후 `results/summary/robustness.md` 확인(로컬 재계산: `python scripts/robustness.py`, 약 2분).
