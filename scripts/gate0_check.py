"""Gate 0: DEVSIM import + solver info + official 1D diode example run twice (must be identical)."""
import os, subprocess, sys, tempfile, urllib.request
from pathlib import Path
import devsim
info = devsim.get_parameter(name="info")
print("devsim", info.get("version"), "| solver:", info.get("direct_solver"), "| extended:", info.get("extended_precision"))
base = "https://raw.githubusercontent.com/devsim/devsim/main/examples/diode/"
d = Path(tempfile.mkdtemp())
try:
    for f in ("diode_1d.py", "diode_common.py"):
        urllib.request.urlretrieve(base + f, d / f)
except Exception as e:
    print("SKIP official example (offline?):", e); sys.exit(0)
env = os.environ.copy()
env.update({"OMP_NUM_THREADS": "1", "MKL_NUM_THREADS": "1"})
outs = [subprocess.run([sys.executable, "diode_1d.py"], cwd=d, capture_output=True, text=True, env=env) for _ in range(2)]
ok = all(o.returncode == 0 for o in outs) and outs[0].stdout == outs[1].stdout
print("official diode_1d x2:", "PASS (identical)" if ok else "FAIL")
sys.exit(0 if ok else 1)
