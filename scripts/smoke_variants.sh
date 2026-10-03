#!/usr/bin/env bash
# Local check before dispatching robustness-batch: one 423 K run (test point T0000) per variant, in parallel (~2 min on 4 cores).
set -euo pipefail
cd "$(dirname "$0")/.."
export MKL_NUM_THREADS=1 OMP_NUM_THREADS=1
for v in gamma_m1 gamma0 qitT10 qitT30; do
  rm -rf "/tmp/smoke_$v"
  python -m sicsim.runner configs/design_test.csv --out "/tmp/smoke_$v" --temps 423 \
         --config "configs/variants/$v.yaml" --shard 0/128 > "/tmp/smoke_$v.log" 2>&1 &
done
wait
python - <<'PY'
import json
b = json.load(open("results/test/runs/T0000_T423.json"))["features"]
print(f"{'variant':10s} conv  Vth(V)  dVth(mV)  Ron(mOhm.cm2)  dRon(%)  hash")
print(f"{'baseline':10s} True  {b['vth_V']:.4f}     —      {b['ron_mohm_cm2']:.4f}       —")
for v in ("gamma_m1", "gamma0", "qitT10", "qitT30"):
    r = json.load(open(f"/tmp/smoke_{v}/runs/T0000_T423.json")); f = r.get("features") or {}
    if not r.get("converged"):
        print(f"{v:10s} FAIL  {r.get('error_code')}"); continue
    print(f"{v:10s} True  {f['vth_V']:.4f}  {1e3*(f['vth_V']-b['vth_V']):+8.1f}   {f['ron_mohm_cm2']:.4f}    {100*(f['ron_mohm_cm2']/b['ron_mohm_cm2']-1):+6.1f}   {r['physics_hash']}")
print("expected: qitT30 dVth = -489 mV, qitT10 = -163 mV (= q*dQ/Cox); gamma variants: Ron up, Vth slightly up")
PY
