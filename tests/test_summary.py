import json
import pandas as pd
from sicsim.summary import rq3_section


def _tree(tmp_path, mode):
    rows = [dict(policy=p, seed=s, n_points=n, mean_mae_norm=0.13 - 0.001 * (p == "llm") - 0.0001 * n / 10)
            for p in ("random", "uncertainty", "sobol", "llm") for s in range(3) for n in (60, 70)]
    for d in ("al/nominal", "al_live/nominal"):
        (tmp_path / d).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_csv(tmp_path / d / "al_curves.csv", index=False)
    rec = dict(mode=mode, model_id="claude-sonnet-5-5" if mode == "live" else "dry-run", validator_status="accepted",
               reject_reason=None, candidate_ids=[f"C{i}" for i in range(20)], selected_ids=["C0", "C5"],
               reason_codes=["DIVERSITY"], input_tokens=100, output_tokens=20, latency_s=1.0)
    (tmp_path / "al_live/nominal/llm_calls.jsonl").write_text(json.dumps(rec) + "\n")


def test_rq3_live_comparison(tmp_path):
    _tree(tmp_path, "live")
    text = "\n".join(rq3_section(tmp_path))
    assert "vs uncertainty" in text and "평균 3.5" in text and "LLM 우세 3/3" in text


def test_rq3_flags_dry_run(tmp_path):
    _tree(tmp_path, "dry-run")
    assert "dry-run" in "\n".join(rq3_section(tmp_path))
