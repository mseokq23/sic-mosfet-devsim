"""Compare regenerated outputs in this working tree with the committed versions (git HEAD).
  python scripts/compare_outputs.py                 # every modified or new file under results/, paper/, docs/figures/
  python scripts/compare_outputs.py results/summary # limit to some paths
For JSON/CSV the largest absolute and relative difference over all numbers is reported, plus fields whose text
changed (commit, CPU, timestamps); Markdown is compared line by line; figures are binary (fonts and library
versions change the bytes, so compare them by eye). Typical use: after scripts/reproduce_l1.sh or after running
the analysis scripts in place (then `git checkout -- results paper` restores the committed files)."""
from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip() or ".")


def git(*a):
    return subprocess.run(["git", *a], cwd=ROOT, capture_output=True, text=True).stdout


def head(path):
    return subprocess.run(["git", "show", f"HEAD:{path}"], cwd=ROOT, capture_output=True).stdout.decode("utf-8", "replace")


def walk(a, b, path, out):
    if isinstance(a, dict) and isinstance(b, dict):
        for k in sorted(set(a) | set(b), key=str):
            if k not in a or k not in b:
                out["text"].append(f"{path}.{k} (only in {'new' if k in b else 'committed'})")
            else:
                walk(a[k], b[k], f"{path}.{k}", out)
    elif isinstance(a, list) and isinstance(b, list):
        if len(a) != len(b):
            out["text"].append(f"{path} (length {len(a)} -> {len(b)})")
        for i, (x, y) in enumerate(zip(a, b)):
            walk(x, y, f"{path}[{i}]", out)
    elif isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
        if a != b:
            d = abs(a - b)
            out["n"] += 1
            out["abs"] = max(out["abs"], d)
            out["rel"] = max(out["rel"], d / max(abs(a), abs(b)))
    elif a != b:
        out["text"].append(path)


def compare(path):
    new = (ROOT / path).read_text(encoding="utf-8", errors="replace")
    old = head(path)
    out = dict(n=0, abs=0.0, rel=0.0, text=[])
    if path.endswith(".json"):
        walk(json.loads(old), json.loads(new), "", out)
    elif path.endswith(".jsonl"):
        A = [json.loads(x) for x in old.splitlines() if x.strip()]
        B = [json.loads(x) for x in new.splitlines() if x.strip()]
        walk(A, B, "", out)
    elif path.endswith(".csv"):
        A, B = pd.read_csv(io.StringIO(old)), pd.read_csv(io.StringIO(new))
        if list(A.columns) != list(B.columns) or len(A) != len(B):
            out["text"].append(f"columns/rows {list(A.columns)} x {len(A)} -> {list(B.columns)} x {len(B)}")
        else:
            for c in A.columns:
                if pd.api.types.is_numeric_dtype(A[c]) and pd.api.types.is_numeric_dtype(B[c]):
                    d = (A[c] - B[c]).abs()
                    if (d > 0).any():
                        den = pd.concat([A[c].abs(), B[c].abs()], axis=1).max(axis=1)
                        out["n"] += int((d > 0).sum())
                        out["abs"] = max(out["abs"], float(d.max()))
                        out["rel"] = max(out["rel"], float((d / den.where(den > 0)).max()))
                elif not A[c].astype(str).equals(B[c].astype(str)):
                    out["text"].append(f"column {c}")
    else:
        ol, nl = old.splitlines(), new.splitlines()
        changed = [i for i, (a, b) in enumerate(zip(ol, nl)) if a != b]
        if path.endswith(".html"):               # generated page: the embedded data block carries the build stamp
            out["text"] = [f"{len(changed)} line(s) differ (build stamp: branch, commit, time)"] if changed else []
        else:
            out["text"] = [f"line {i + 1}: {nl[i][:90]}" for i in changed]
        if len(ol) != len(nl):
            out["text"].append(f"line count {len(ol)} -> {len(nl)}")
    return out


def main():
    scope = sys.argv[1:] or ["results", "paper", "docs/figures"]
    status = git("status", "--porcelain", "--untracked-files=all", "--", *scope).splitlines()
    if not status:
        print("no regenerated file differs from the committed version")
        return
    print(f"{'file':58s} {'numbers changed':>15s} {'max |Δ|':>9s} {'max rel':>9s}  other differences")
    for line in status:
        code, path = line[:2], line[3:]
        if code.strip() == "??":
            print(f"{path:58s} {'new file (not in git)':>35s}")
            continue
        if path.endswith((".png", ".pdf", ".docx")):
            print(f"{path:58s} {'binary file changed':>35s}")
            continue
        try:
            r = compare(path)
        except Exception as e:                       # unreadable / deleted
            print(f"{path:58s} {'could not compare: ' + str(e)[:40]:>35s}")
            continue
        other = "; ".join(r["text"][:3]) + (f" (+{len(r['text']) - 3})" if len(r["text"]) > 3 else "")
        print(f"{path:58s} {r['n']:15d} {r['abs']:9.1e} {r['rel']:9.1e}  {other}")


if __name__ == "__main__":
    main()
