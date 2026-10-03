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

## v0.4 — Stage A(Codespaces) 결과 반영
- Stage A 26 run 전부 수렴. 보정 추출로 Qit_eff ±20%의 Vth 이동 ±0.464 V(해석해 qΔQ/Cox와 1 mV 이내).
  ΔVth(423−300 K)는 Npwell −20%→+20%에서 −0.196→−0.217 V로 단조, Qit_eff·Wjfet는 1 mV 이내로 불변.
- 측정 잡음 모델 `configs/noise_model.yaml` 사전 등록: 시뮬레이션 특징에는 잡음이 없어 RQ1이 자명해지므로
  분석 단계에서 잡음을 더해 평가한다(`run_al.py --noise none|low|nominal|high`, 절제 분석).
- 국소 식별성(CRB) `scripts/identifiability.py`: nominal 잡음에서 S2/S1 = Wjfet 0.58, Npwell 0.65, Qit_eff 0.65
  (423 K가 단순 반복 측정이면 0.71). Npwell–Qit_eff 추정 상관 −0.998 → 두 변수 분리가 핵심 난제.
- (선택) 채널 이동도 `mu_channel_scale`을 비추정 교란 변수로 풀에 포함: Stage A 확장 8 run 후 식별성 재계산.
- 모델 가정 민감도: μ_surf 온도지수 0 vs 1 (`configs/variant_musurf_gamma1.yaml`, 300 K는 동일하므로 423 K만 계산).
- 계산 자원: 4코어 Codespace에서 `--jobs 4`는 run당 약 190 s(처리량 약 48 s/run) → 풀+테스트 1,280 run ≈ 17 h
  ≈ 70 core-hours(Free 플랜 월 120 core-hours). 공개 저장소의 GitHub Actions 표준 러너는 무료 → `doe-batch`(16 shards) 권장.
- 기준 소자 구조를 바꾸면(예: 2.4 kV급) G3 메시 확인 → Stage A → 식별성 분석을 다시 수행한 뒤 풀 계산.

```bash
unzip -o sicsim_patch_v0.4.zip && pytest -q
python scripts/identifiability.py results/stage_a                       # ±10% 중앙차분, nominal 잡음
# (선택) 교란 변수 μch
python -m sicsim.runner configs/design_stage_a_mu.csv --out results/stage_a --jobs 4
python scripts/identifiability.py results/stage_a
# (선택) μ_surf 온도지수 민감도 (423 K만)
python -m sicsim.runner configs/design_stage_a.csv --out results/stage_a_g1 --jobs 4 --temps 423 --config configs/variant_musurf_gamma1.yaml
cp results/stage_a/runs/*_T300.json results/stage_a_g1/runs/ && python scripts/merge_runs.py results/stage_a_g1
python scripts/identifiability.py results/stage_a_g1
# 풀/테스트: GitHub → Actions → doe-batch → Run workflow (design_pool.csv, 16 shards), 끝나면
gh run download <run-id> -D artifacts && mkdir -p results/pool/runs && cp artifacts/runs-*/*.json results/pool/runs/ && python scripts/merge_runs.py results/pool
```


## v1.0 동결 (2026-10-02) — v1.1로 대체됨(Wjfet 정의 외 동일)
결정: ① 기준 소자 1.2 kV급 유지 ② 잡음 모델 nominal 유지(Ion·Ron 1%: B1505A/B1500A SMU 정확도 0.1~0.2%에
접촉 저항 변동·발열 재현 오차가 더해진 값; 원고에는 구체적 측정 불확실도 문헌 인용 필요, Vth·SS·gm 근거도 보완)
③ 채널 이동도 `mu_channel_scale`(0.8~1.2)를 교란 변수로 모든 설계에 포함(시뮬레이터 입력, 추정 대상 아님)
④ 채널 이동도 온도지수 `mu_surf_gamma` = 1 ⑤ 나머지 가정(Qf, Qit_eff 범위 등) 유지.
파일: `baseline.yaml`(v1.0-frozen) · `parameter_bounds.yaml`(bounds-v1.0) · `noise_model.yaml`(noise-v1.0) ·
`design_stage_a.csv`(17점) · `design_pool.csv`(Sobol 512, 4차원) · `design_test.csv`(128, 4차원) ·
`variant_musurf_gamma0.yaml`(한계 분석용, 300 K는 v1.0과 동일).

```bash
# 0) 이전 산출물 정리 (없으면 무시됨)
rm -f configs/design_stage_a_mu.csv configs/variant_musurf_gamma1.yaml
mkdir -p results/archive && { [ -d results/stage_a ] && mv results/stage_a results/archive/stage_a_v0.3 || true; }
# 1) 패치 적용 → 검증 → 동결 태그
unzip -o sicsim_patch_v1.0.zip && rm sicsim_patch_v1.0.zip && pytest -q
git add -A && git commit -m "freeze v1.0" && git tag v1.0-frozen && git push && git push --tags
# 2) Stage A v1.0: 17점 x 2온도 = 34 run (4코어 Codespace 약 30분)
python -m sicsim.runner configs/design_stage_a.csv --out results/stage_a_v1 --jobs 4
python scripts/stage_a_report.py results/stage_a_v1
python scripts/identifiability.py results/stage_a_v1
git add results && git commit -m "Stage A v1.0" && git push
# 3) 풀·테스트: GitHub > Actions > doe-batch > Run workflow 를 두 번 실행
#    (configs/design_pool.csv, results/pool, 16)  /  (configs/design_test.csv, results/test, 4)
#    merge 작업이 결과를 저장소에 커밋 -> Codespace에서:
git pull
# 4) RQ1~3 (잡음 수준별 결과는 results/al/<noise>/)
for nz in nominal high none; do python scripts/run_al.py --pool results/pool --test results/test --seeds 10 --noise $nz; done
# 5) (선택) 한계 분석: 온도지수 0, 423 K만 다시 계산
python -m sicsim.runner configs/design_stage_a.csv --out results/stage_a_g0 --jobs 4 --temps 423 --config configs/variant_musurf_gamma0.yaml
cp results/stage_a_v1/runs/*_T300.json results/stage_a_g0/runs/ && python scripts/merge_runs.py results/stage_a_g0
python scripts/identifiability.py results/stage_a_g0
```
RQ3 실제 LLM 호출: 저장소 Settings > Secrets and variables > Codespaces 에 `ANTHROPIC_API_KEY` 등록 후
`run_al.py ... --llm-live` (없으면 dry-run으로 동일 파이프라인만 검증).


## v1.1 동결 (2026-10-03) — 이 절이 현재 기준
- 변경: JFET 폭 공정편차를 **고정 피치**로 정의(`configs/baseline.yaml` → `geometry.wjfet_mode: fixed_pitch`).
  마스크 피치(half-cell 3.5 µm)는 고정, 자기정렬된 P-well/n+ 소스 경계가 −ΔW/2 이동, 채널 길이 0.5 µm 유지
  → Ron,sp 면적 정규화가 일정. (v1.0은 JFET 폭과 함께 셀 피치가 커져 Ron,sp에 비물리적 면적 효과가 섞였음)
- 검증(샌드박스): 기준점 전달곡선이 v1.0(Codespace 실행)과 비트 단위 동일 · Wjfet ±20% × 300/423 K 4 run 재시도 없이 수렴 ·
  Ron,sp가 Wjfet +20%에서 −3.1%(300 K)/−4.3%(423 K)로 감소(v1.0: +2.5%/−0.03%) · pytest 29개 통과.
- CRB 미리보기(v1.0 자코비안 + v1.1 Wjfet 열, nominal 잡음): Wjfet 300 K만 17.9% → 300+423 K 6.9% (비율 0.38, 단순 반복 0.71).
  Npwell 28.4 → 16.7%, Qit_eff 12.6 → 7.4%. v1.0의 피치 효과가 300 K Wjfet 식별성을 과대평가하고 있었음.

```bash
git pull
unzip -o sicsim_patch_v1.1.zip && rm sicsim_patch_v1.1.zip && pytest -q
git mv results/stage_a_v1 results/archive/stage_a_v1.0
git add -A && git commit -m "freeze v1.1: fixed-pitch JFET width" && git tag v1.1-frozen && git push && git push --tags
python -m sicsim.runner configs/design_stage_a.csv --out results/stage_a_v11 --jobs 4   # 34 run, 약 30분
python scripts/stage_a_report.py results/stage_a_v11
python scripts/identifiability.py results/stage_a_v11
git add results && git commit -m "Stage A v1.1" && git push
```
이후 풀·테스트(doe-batch), RQ1~3, 온도지수 0 한계 분석은 v1.0 절 3~5번과 같다(5번의 `results/stage_a_v1`은 `results/stage_a_v11`로).


### 분석 규칙 추가 (noise-v1.1, 풀 결과의 RQ 분석 전에 결정)
- 풀 감사: 1,280 run 전부 수렴, NaN 없음, 재시도 발생 10%(모두 수렴), 출력곡선 2~5 V 사이 조기 종료 7%(규칙상 허용, ID@2V 유효).
- 300 K의 `logid_vg4`(VGS 4 V 전류)가 고 Vth 소자에서 최소 8e-14 A/cm로 수치 바닥(최대 3.2e-12) 아래 → 잡음값.
- 규칙: 전달곡선 샘플은 `current_floor_A_per_cm`(1e-11 A/cm)에서 절단(잡음 추가 뒤, 모든 잡음 수준에 동일 적용).
- 결과 감사(docs/AUDIT.md): 무결성·재현성·해석해 일치 확인. 300 K Vth(≤3 mV)와 gm,max(약 1.3%)의 수치 정밀도 한계는 문서화하고 v1.1 데이터로 진행.
