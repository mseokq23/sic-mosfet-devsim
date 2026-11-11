"""The results page (site/, GitHub Pages) is built from the committed result files by scripts/make_site.py:
its data files match a rebuild and every file it links exists.
No DEVSIM, no API calls; the two fitted parts (surrogate.js, estimates.js) are checked by their stored diagnostics."""
import html
import json
import math
import re
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def load(name):
    text = (SITE / "data" / f"{name}.js").read_text(encoding="utf-8")
    head = f"window.SITE=window.SITE||{{}};window.SITE.{name}="
    assert text.startswith(head)
    return json.loads(text[len(head):].rstrip().rstrip(";"))


def same(a, b, path="$"):
    """Equal up to float formatting (values are rounded before they are written)."""
    if isinstance(a, dict):
        assert isinstance(b, dict) and a.keys() == b.keys(), path
        for k in a:
            same(a[k], b[k], f"{path}.{k}")
    elif isinstance(a, list):
        assert isinstance(b, list) and len(a) == len(b), path
        for i, (x, y) in enumerate(zip(a, b)):
            same(x, y, f"{path}[{i}]")
    elif isinstance(a, float) or isinstance(b, float):
        assert a is not None and b is not None and math.isclose(a, b, rel_tol=1e-9, abs_tol=1e-12), (path, a, b)
    else:
        assert a == b, (path, a, b)


@pytest.fixture(scope="module")
def ms():
    sys.path.insert(0, str(ROOT / "scripts"))
    import make_site
    return make_site


def normal(obj):
    return json.loads(json.dumps(obj, ensure_ascii=False, allow_nan=False))


def test_core_matches_rebuild(ms):
    core = load("core")
    for name in ("design", "stage_a", "features", "rq1", "selection"):
        same(core[name], normal(getattr(ms, name)()), name)
    assert core["meta"]["repo"] == ms.REPO and not core["meta"]["dirty"]


def test_iv_and_llm_match_rebuild(ms):
    same(load("iv"), normal(ms.iv()), "iv")
    llm = load("llm")
    same(llm, normal(ms.llm()), "llm")
    assert llm["dist_check_max_abs"] <= 1e-4          # reconstructed training sets reproduce the logged distances


def test_code_excerpts_match_sources(ms):
    items = load("code")["items"]
    rebuilt = normal(ms.code())["items"]
    assert [{k: v for k, v in it.items() if k != "url"} for it in items] == \
           [{k: v for k, v in it.items() if k != "url"} for it in rebuilt]
    for it in items:                                    # the highlighted HTML is the exact source text
        src = (ROOT / it["file"]).read_text(encoding="utf-8").splitlines()[it["start"] - 1:it["end"]]
        assert html.unescape(re.sub(r"<[^>]+>", "", it["html"])) == textwrap.dedent("\n".join(src))
        assert it["url"].endswith(f"/{it['file']}#L{it['start']}-L{it['end']}")


def test_fitted_parts_diagnostics():
    sur = load("surrogate")
    assert len(sur["train_u"]) == sur["n_train"] and sur["n_test"] > 100
    for key, m in sur["models"].items():
        assert len(m["alpha"]) == sur["n_train"] and len(m["comp"]) == len(m["ymu"]) == len(m["alpha"][0]), key
    for T in ("300", "423"):                            # held-out test devices
        assert sur["validation"][T]["vth_mV_median"] < 10
    est = load("estimates")
    assert len(est["ids"]) == len(est["truth"]) == 128 and est["draws"] == 5
    assert max(est["check_max_abs_diff"].values()) < 1e-6   # draw 0 reproduces the committed per-device errors
    for key, rows in est["est"].items():
        assert len(rows) == 128 and all(len(r) == 3 for r in rows), key


def test_linked_files_exist():
    page = (SITE / "index.html").read_text(encoding="utf-8")
    repo_paths = [p for attr in re.findall(r'data-(?:src|code)="([^"]+)"', page) for p in attr.split()]
    assert repo_paths
    for p in repo_paths:
        assert (ROOT / p).exists(), p
    for p in re.findall(r'(?:src|href)="((?:assets|data)/[^"]+)"', page):
        assert (SITE / p).exists(), p
    app = (SITE / "assets" / "app.js").read_text(encoding="utf-8")
    for name in re.findall(r'need\("(\w+)"\)', app):
        assert (SITE / "data" / f"{name}.js").exists(), name
    for el in set(re.findall(r'\$\("([\w-]+)"\)', app)):
        assert f'id="{el}"' in page, el
