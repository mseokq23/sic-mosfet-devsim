"""Batch runner with process isolation, parallel workers and resume.

  python -m sicsim.runner designs/stage_a.csv --out results/stage_a --jobs 4 --temps 300 423
  (--shard i/N runs only every N-th run, for GitHub Actions matrix jobs)

Outputs in --out:  runs/<run_id>.json (full record incl. curves),  runs.csv (flat table:
draft log columns + all features),  failures are logged with converged=False (never dropped).
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import json
import os
import subprocess
import sys
import threading
from pathlib import Path

import pandas as pd

from .config import ROOT
from .schema import Experiment, RUN_COLUMNS

_lock = threading.Lock()


def _commit():
    try:
        return subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                              text=True).stdout.strip() or None
    except Exception:
        return None


def expand(design: pd.DataFrame, temps, policy="manual", round_=0, seed=0) -> list[dict]:
    jobs = []
    for _, r in design.iterrows():
        for T in temps:
            e = Experiment(run_id=f"{r['candidate_id']}_T{int(T)}", candidate_id=r["candidate_id"],
                           process_group_id=r.get("process_group_id", r["candidate_id"]), policy=policy,
                           round=round_, temperature_K=float(T), wjfet_scale=float(r["wjfet_scale"]),
                           npwell_scale=float(r["npwell_scale"]), qit_eff_cm2=float(r["qit_eff_cm2"]),
                           mu_channel_scale=float(r.get("mu_channel_scale", 1.0)), seed=seed)
            jobs.append(e.model_dump())
    return jobs


def flatten(res: dict) -> dict:
    row = {k: res.get(k) for k in RUN_COLUMNS}
    for k, v in (res.get("features") or {}).items():      # features fill/override log columns
        if row.get(k) is None:
            row[k] = v
    row.update(error_code=res.get("error_code"), n_nodes=res.get("n_nodes"), n_solves=res.get("n_solves"),
               mesh_scale=res.get("mesh_scale"), extended=res.get("extended"), holes=res.get("holes"),
               config_version=res.get("config_version"))
    return row


def run_one(job: dict, out: Path, extra: dict, commit) -> dict:
    rdir = out / "runs"
    rdir.mkdir(parents=True, exist_ok=True)
    res_p, job_p = rdir / f"{job['run_id']}.json", rdir / f"{job['run_id']}.job.json"
    if not res_p.exists():
        json.dump({**job, **extra}, open(job_p, "w"))
        env = {**os.environ, "PYTHONPATH": str(ROOT / "src"), "MKL_NUM_THREADS": "1",
               "OMP_NUM_THREADS": "1"}
        p = subprocess.run([sys.executable, "-m", "sicsim.worker", str(job_p), str(res_p)], env=env,
                           capture_output=True, text=True)
        if p.returncode != 0 or not res_p.exists():      # crash -> logged as failed run
            json.dump({**job, "converged": False, "error_code": f"WORKER_CRASH: {p.stderr[-300:]}"},
                      open(res_p, "w"))
        job_p.unlink(missing_ok=True)
        res = json.load(open(res_p))
        res.update(code_commit=commit, created_at=dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"))
        json.dump(res, open(res_p, "w"))
    return json.load(open(res_p))


def run_batch(jobs: list[dict], out, n_workers=1, extra=None, verbose=True, budget_s=None) -> pd.DataFrame:
    """Run jobs (resume-safe). budget_s: stop LAUNCHING new runs after this many seconds
    (lets a batch be split into chunks that fit a time limit; just call again to resume)."""
    import time as _t
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    extra, commit = extra or {}, _commit()
    rows, t0, pending = [], _t.time(), list(jobs)
    todo = [j for j in pending if not (out / "runs" / f"{j['run_id']}.json").exists()]
    done = [j for j in pending if j not in todo]
    for j in done:
        rows.append(flatten(json.load(open(out / "runs" / f"{j['run_id']}.json"))))
    with cf.ThreadPoolExecutor(max_workers=n_workers) as ex:
        inflight = set()
        while todo or inflight:
            while todo and len(inflight) < n_workers and (budget_s is None or _t.time() - t0 < budget_s):
                inflight.add(ex.submit(run_one, todo.pop(0), out, extra, commit))
            if not inflight:
                break
            fin, inflight = cf.wait(inflight, return_when=cf.FIRST_COMPLETED)
            for f in fin:
                res = f.result()
                with _lock:
                    rows.append(flatten(res))
                    if verbose:
                        print(f"[{len(rows)}/{len(jobs)}] {res['run_id']} conv={res.get('converged')} "
                              f"t={res.get('runtime_s', 0):.0f}s vth={(res.get('features') or {}).get('vth_V')}",
                              flush=True)
    if todo and verbose:
        print(f"budget reached: {len(todo)} runs left (re-run the same command to resume)")
    df = pd.DataFrame(rows).sort_values("run_id") if rows else pd.DataFrame(columns=RUN_COLUMNS)
    df.to_csv(out / "runs.csv", index=False)
    return df


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("design")
    ap.add_argument("--out", required=True)
    ap.add_argument("--jobs", type=int, default=1)
    ap.add_argument("--temps", type=float, nargs="+", default=[300, 423])
    ap.add_argument("--mesh-scale", type=float, default=None)
    ap.add_argument("--extended", action="store_true")
    ap.add_argument("--policy", default="manual")
    ap.add_argument("--round", type=int, default=0)
    ap.add_argument("--shard", default=None, help="i/N")
    ap.add_argument("--budget-s", type=float, default=None, help="stop launching new runs after N s")
    a = ap.parse_args(argv)
    jobs = expand(pd.read_csv(a.design), a.temps, a.policy, a.round)
    if a.shard:
        i, n = map(int, a.shard.split("/"))
        jobs = jobs[i::n]
    extra = {}
    if a.mesh_scale is not None:
        extra["mesh_scale"] = a.mesh_scale
    if a.extended:
        extra["extended"] = True
    run_batch(jobs, a.out, a.jobs, extra, budget_s=a.budget_s)


if __name__ == "__main__":
    main()
