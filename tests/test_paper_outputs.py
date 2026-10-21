"""The paper figures, tables and numbers can be rebuilt from the committed result files (no DEVSIM, a few seconds)."""
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]


def test_paper_numbers_match_results(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_paper_numbers.py"), "--out", str(tmp_path / "n.csv")],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stdout[-3000:] + r.stderr[-2000:]
    assert " 0 mismatches" in r.stdout
    assert (tmp_path / "n.csv").read_text(encoding="utf-8") == (ROOT / "paper" / "numbers.csv").read_text(encoding="utf-8")


def test_paper_figures_and_tables_rebuild(tmp_path):
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_paper_figures.py"), "--out", str(tmp_path)],
                       capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    for name in ("fig1_structure_flow", "fig2_validation", "fig3_rq1"):
        new = np.asarray(Image.open(tmp_path / "figures" / f"{name}.png").convert("RGB"), dtype=int)
        old = np.asarray(Image.open(ROOT / "paper" / "figures" / f"{name}.png").convert("RGB"), dtype=int)
        assert new.shape == old.shape, name
        assert (np.abs(new - old).max(axis=2) > 0).mean() < 0.005, name      # identical with the pinned packages
    for name in ("table1_sensitivity", "table2_physics", "table3_policies"):
        for ext in ("md", "csv"):
            assert (tmp_path / "tables" / f"{name}.{ext}").read_text(encoding="utf-8") == \
                (ROOT / "paper" / "tables" / f"{name}.{ext}").read_text(encoding="utf-8"), f"{name}.{ext}"
