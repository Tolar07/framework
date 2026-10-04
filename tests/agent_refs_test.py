"""Every file an OLP XDV agent, skill, CLAUDE.md or MAP.md names must exist.

Agents and skills are how sessions find their way around the framework; a
reference to a moved or parked file sends a session to code that isn't
there. This fails the moment one goes stale.
"""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = sorted((ROOT / ".claude" / "agents").glob("olp-xdv-*.md")) + [
    ROOT / ".claude" / "skills" / "olp-xdv" / "SKILL.md",
    ROOT / "CLAUDE.md",
    ROOT / "MAP.md",
]
# Any path with a directory part and a code/doc extension, inline or in a code
# block, e.g. engine/slate.py or tests/staking_test.py. URLs are skipped.
PATH_RE = re.compile(r"(?<![\w/.:-])([A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)+\.(?:py|md|yml|json))\b")
# Patterns that name a file family, not one file.
TEMPLATED = ("<", "*")


def refs(doc: Path) -> list[str]:
    return [m for m in PATH_RE.findall(doc.read_text(encoding="utf-8"))
            if not any(t in m for t in TEMPLATED)]


def test_every_referenced_path_exists():
    missing = []
    for doc in DOCS:
        for ref in refs(doc):
            if not (ROOT / ref).exists():
                missing.append(f"{doc.relative_to(ROOT)} -> {ref}")
    assert not missing, "stale references:\n  " + "\n  ".join(missing)


def test_no_agent_points_into_legacy_as_live_code():
    for doc in DOCS:
        for ref in refs(doc):
            if ref.startswith("legacy/"):
                text = doc.read_text(encoding="utf-8")
                assert "parked" in text, f"{doc.name} names {ref} without saying it is parked"


def test_ten_stage_agents_present():
    names = {d.stem for d in DOCS}
    for i in range(1, 11):
        assert any(n.startswith(f"olp-xdv-{i:02d}-") for n in names), f"stage agent {i:02d} missing"


if __name__ == "__main__":
    for name, fn in sorted(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"{name}: OK")
    print("agent_refs_test: OK")
