"""Every darts study the nightly multisport workflow runs must also have its report in the save (commit) list,
or the result is regenerated each night and thrown away (framework#341)."""
import re
from pathlib import Path

WF = (Path(__file__).resolve().parent.parent / ".github" / "workflows" / "multisport.yml").read_text(encoding="utf-8")


def test_every_run_darts_study_is_saved():
    ran = set(re.findall(r"python backtest/(darts_\w+_study|darts_study)\.py", WF))
    saved = set(re.findall(r"backtest/(DARTS_\w+\.md)", WF))
    assert ran, "no darts studies found in the workflow"
    missing = [m for m in ran if f"{m.upper()}.md" not in saved]
    assert not missing, f"run but never saved: {missing}"
