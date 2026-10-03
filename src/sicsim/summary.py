"""Result summaries that need unit tests (RQ3 live-LLM section)."""
import json
from pathlib import Path

import numpy as np
import pandas as pd


def rq3_section(R):
    T = ["# RQ3: LLM 보조 선택 (results/al_live)\n"]
    rng = np.random.default_rng(1)
    for logp in sorted((R / "al_live").glob("*/llm_calls.jsonl")):
        nzn = logp.parent.name
        Lg = [json.loads(x) for x in open(logp)]
        modes = sorted({r.get("mode", "dry-run" if r["model_id"] == "dry-run" else "live") for r in Lg})
        T.append(f"\n## {nzn}: 호출 {len(Lg)}회, 모드 {modes}, 모델 {sorted({r['model_id'] for r in Lg})}")
        if modes != ["live"]:
            T.append("**실제 LLM 결과가 아님(dry-run) → RQ3 근거로 사용하지 말 것.**"); continue
        acc = [r for r in Lg if r["validator_status"] == "accepted"]
        ranks = [r["candidate_ids"].index(i) + 1 for r in acc for i in r["selected_ids"]]   # candidates listed by uncertainty
        rc = pd.Series([c for r in acc for c in (r.get("reason_codes") or [])]).value_counts()
        rej = pd.Series([(r["reject_reason"] or "")[:30] for r in Lg if r["validator_status"] != "accepted"]).value_counts()
        T += [f"- 검증 통과 {len(acc)}/{len(Lg)} (거절 → 사전 규칙대로 uncertainty로 대체), 거절 사유: {rej.to_dict() or '없음'}",
              f"- 선택 ID의 불확실도 순위(1=가장 불확실, 후보 {len(Lg[0]['candidate_ids'])}개): 평균 {np.mean(ranks):.1f}, 상위 10위 내 비율 {np.mean(np.array(ranks) <= 10):.2f}",
              f"- 사유 코드: {rc.to_dict()}",
              f"- 토큰 입력/출력 합계 {sum(r['input_tokens'] for r in Lg)}/{sum(r['output_tokens'] for r in Lg)}, 평균 지연 {np.mean([r['latency_s'] for r in Lg]):.1f} s"]
        live = pd.read_csv(logp.parent / "al_curves.csv"); live = live[live.policy == "llm"]
        base = pd.read_csv(R / "al" / nzn / "al_curves.csv")
        last = live.n_points.max()
        f = lambda d, p: d[(d.policy == p) & (d.n_points == last)].set_index("seed").mean_mae_norm
        L_ = f(live, "llm")
        T.append(f"- 최종 mae_norm: LLM {L_.mean():.4f} ± {L_.std():.4f}")
        for ref in ("random", "uncertainty", "sobol"):
            dd = (L_ - f(base, ref)).dropna().values
            bs = [rng.choice(dd, len(dd)).mean() for _ in range(5000)]; lo, hi = np.percentile(bs, [2.5, 97.5])
            T.append(f"  - vs {ref}: Δ {dd.mean():+.4f} [95% CI {lo:+.4f}, {hi:+.4f}], LLM 우세 {int((dd < 0).sum())}/{len(dd)}")
    return T


