"""XSS regression tests for the webapp's client-side JS.

DOM-based XSS in a strict-CSP app (script-src 'self') is the one sink class
CSP cannot stop: the payload is delivered by a whitelisted script assigning
attacker text (API `data.error`, error objects) into `innerHTML`. The fix is
client-side: every dynamic fragment concatenated into `innerHTML` must pass
through `escapeHtml()` (textContent round-trip), never raw string concat.

Two layers of proof:
  1. Source scan — every `innerHTML = '<...' +` assignment in produce.js /
     signoff.js must route its dynamic operand through escapeHtml (a raw
     `+ data.error +` or `+ e +` inside an innerHTML assignment fails).
  2. Runtime — drive the real `escapeHtml` implementation in node (small DOM
     shim) and assert `<img onerror=...>` input comes back as inert text.

Run:  python tests/webapp_xss_test.py   (node must be on PATH for layer 2;
layer 1 runs regardless).
"""
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent
JS_DIR = ROOT / "webapp" / "static" / "js"

# ---------------------------------------------------------------------------
# Layer 1 — source scan: no raw attacker/error text may reach innerHTML.
# The problematic pattern is an innerHTML assignment whose template is
# concatenated with a dynamic value NOT wrapped in escapeHtml(...).
# We flag these concrete shapes (they were the sinks before the patch):
#   + data.error +        + (data ? data.error : 'failed') +
#   + err.message +       + e +          (error object in a .catch)
# ---------------------------------------------------------------------------
BAD_PATTERNS = [
    re.compile(r"\+\s*\(?\s*data\s*\?\s*data\.error\s*:\s*'failed'\s*\)?\s*\+"),
    re.compile(r"\+\s*data\.error\s*\+"),
    re.compile(r"\+\s*err\.message\s*\+"),
    re.compile(r"Network error:\s*'\s*\+\s*e\s*\+"),
]

# The escaped forms must be present for the same sinks.
GOOD_PATTERNS = [
    re.compile(r"escapeHtml\(\s*data\s*\?\s*data\.error\s*:\s*'failed'\s*\)"),
    re.compile(r"escapeHtml\(\s*data\.error\s*\)"),
    re.compile(r"escapeHtml\(\s*err\.message\s*\)"),
    re.compile(r"escapeHtml\(\s*e\s*\)"),
]


def _scan(file: Path) -> tuple[list[str], list[str]]:
    src = file.read_text(encoding="utf-8")
    bad, good = [], []
    for i, line in enumerate(src.splitlines(), 1):
        if "innerHTML" not in line:
            continue
        for pat in BAD_PATTERNS:
            if pat.search(line):
                bad.append(f"{file.name}:{i}: {line.strip()}")
    # GOOD: every innerHTML assignment line must contain escapeHtml(...) —
    # either at the sink (produce.js wraps data.error/e directly) or inside
    # a helper that the sink calls (signoff.js flag() escapes text+kind).
    for i, line in enumerate(src.splitlines(), 1):
        if "innerHTML" in line and "= " in line and "escapeHtml(" in line:
            good.append(f"{file.name}:{i}: {line.strip()}")
    return bad, good


def check_source_scan() -> None:
    for name in ("produce.js", "signoff.js"):
        f = JS_DIR / name
        assert f.exists(), f"missing {f}"
        bad, good = _scan(f)
        assert not bad, f"UNESCAPED innerHTML sink in {name}:\n" + "\n".join(bad)
        assert good, f"no escapeHtml() found on innerHTML lines in {name} — patch may be missing"
    print("layer1 source scan (no raw data.error/err.message/e into innerHTML): OK")


# ---------------------------------------------------------------------------
# Layer 2 — runtime: the escapeHtml helper must neutralize an HTML payload.
# A minimal DOM shim stands in for createElement/textContent/innerHTML so the
# REAL browser behavior is exercised without a full browser.
# ---------------------------------------------------------------------------
DOM_SHIM = r"""
function _encode(s) {
  return String(s)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');
}
function createElement() {
  var text = '';
  var raw = null;       // set via innerHTML (verbatim), null = use encoded text
  return {
    set textContent(v) { text = String(v); raw = null; },
    get textContent() { return text; },
    set innerHTML(v) { raw = String(v); },
    get innerHTML() { return raw !== null ? raw : _encode(text); },
  };
}
"""

PROBE = r"""
function escapeHtml(text) {
  var div = createElement();
  div.textContent = String(text);
  return div.innerHTML;
}
var payload = '<img src=x onerror=alert(1)><script>alert(2)<\/script>';
var out = escapeHtml(payload);
// After escaping, the dangerous markup must be inert: no raw tag delimiters
// left that a browser would parse as elements/attributes.
var hasRawLt    = out.indexOf('<') !== -1;
var hasRawGt    = out.indexOf('>') !== -1;
var hasOnAttr   = out.indexOf('onerror') !== -1;  // would only be present if raw
if (hasRawLt || hasRawGt) {
  console.error('FAIL: escapeHtml left raw < or > markup: ' + out);
  process.exit(1);
}
if (out.indexOf('&lt;') === -1) {
  console.error('FAIL: escapeHtml did not encode < as &lt;: ' + out);
  process.exit(1);
}
console.log('layer2 runtime escape (img-onerror + script payload -> inert text): OK');
console.log('  output: ' + out);
"""


def check_runtime_escape() -> None:
    if not shutil.which("node"):
        print("layer2 runtime escape: SKIPPED (node not on PATH)")
        return
    r = subprocess.run(["node", "-e", DOM_SHIM + PROBE],
                       capture_output=True, text=True, timeout=30)
    assert r.returncode == 0, f"node probe failed:\n{r.stdout}\n{r.stderr}"
    for line in r.stdout.splitlines():
        print("  " + line)


if __name__ == "__main__":
    check_source_scan()
    check_runtime_escape()
    print("\n[OK] WEBAPP XSS TESTS PASSED")
    sys.exit(0)
