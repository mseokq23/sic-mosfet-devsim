"""The README figures can be rebuilt from the committed result files (no DEVSIM, a few seconds)."""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_readme_figures_build(tmp_path):
    names = ["iv_baseline", "estimation_errors"]
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "make_readme_figures.py"), "--out", str(tmp_path),
                        "--only", *names], capture_output=True, text=True, timeout=600)
    assert r.returncode == 0, r.stderr[-2000:]
    for n in names:
        assert (tmp_path / f"{n}.png").stat().st_size > 10_000


def test_readme_links_existing_figures():
    """Every image the README shows exists in docs/figures and every figure there is shown."""
    import re
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    shown = set(re.findall(r"docs/figures/([\w-]+\.png)", readme))
    on_disk = {p.name for p in (ROOT / "docs" / "figures").glob("*.png")}
    assert shown and shown == on_disk
