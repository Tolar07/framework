"""
SPORT PARITY — football features are inherited by basketball (Architect 2026-11-05: "all the
things that have been done for football should apply to basketball ... so we don't miss any
settings on football and basketball does not have it ... more like an inheritance thing").

config/sport_parity.json lists EVERY framework module (engine, monitor, data, scripts, output,
pipeline, verification, clv, run_*.py) with what basketball has of it:
  covers   the module handles basketball itself (it must mention NBA / basketball / NCAA)
  twin     basketball has its own module doing the job ("basketball": existing path(s))
  todo     basketball still needs it ("priority": 1-3, "note": what to build)
  shared   sport-agnostic plumbing
  n/a      football-only by nature ("note" says why and what basketball uses instead)
A new module that isn't listed fails this test: its author must decide what basketball gets.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = json.loads((ROOT / "config" / "sport_parity.json").read_text(encoding="utf-8"))
SCOPE = ["engine", "monitor", "data", "scripts", "output", "pipeline", "verification", "clv"]
STATUSES = {"covers", "twin", "todo", "shared", "n/a"}


def scope_files() -> set[str]:
    out = {p.relative_to(ROOT).as_posix() for d in SCOPE for p in (ROOT / d).glob("*.py")
           if p.name != "__init__.py"}
    return out | {p.name for p in ROOT.glob("run_*.py")}


def test_every_module_is_listed():
    mods = REG["modules"]
    missing = sorted(scope_files() - set(mods))
    assert not missing, ("not in config/sport_parity.json — say what basketball gets "
                         f"(covers / twin / todo / shared / n/a): {missing}")
    stale = sorted(set(mods) - scope_files())
    assert not stale, f"listed in config/sport_parity.json but gone: {stale}"


def test_every_entry_is_complete():
    for f, e in REG["modules"].items():
        st = e.get("status")
        assert st in STATUSES, (f, st)
        assert e.get("note"), f"{f}: say why"
        if st == "twin":
            paths = (e.get("basketball") or "").split()
            assert paths, f"{f}: twin needs its basketball module"
            for p in paths:
                assert (ROOT / p).exists(), f"{f}: twin {p} does not exist"
        if st == "todo":
            assert e.get("priority") in (1, 2, 3), f"{f}: todo needs priority 1-3"
        if st == "covers":
            txt = (ROOT / f).read_text(encoding="utf-8", errors="ignore")
            assert re.search(r"nba|basketball|ncaa", txt, re.I), f"{f}: says it covers basketball but never mentions it"
    for g in REG.get("basketball_gaps") or []:
        assert g.get("feature") and g.get("priority") in (1, 2, 3)
        for p in (g.get("nba_has") or "").split():
            assert (ROOT / p).exists(), f"basketball gap names a missing NBA module: {p}"


def main() -> None:
    test_every_module_is_listed()
    test_every_entry_is_complete()
    todo = [e for e in REG["modules"].values() if e["status"] == "todo"]
    print(f"sport_parity_test OK — {len(REG['modules'])} modules; basketball still to inherit: "
          f"{len(todo)} (priority 1: {sum(e['priority'] == 1 for e in todo)}), "
          f"{len(REG.get('basketball_gaps') or [])} world-basketball gaps")


if __name__ == "__main__":
    main()
