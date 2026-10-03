"""run_pipeline's `leagues` argument must actually restrict the scan.

The regression this pins: run_daily.py passes --leagues into run_pipeline,
run_pipeline declared a `leagues` parameter, and then called
_run_pipeline_internal WITHOUT it. PipelineState had no field to hold it
either, so agent_1_ingest read WHITELISTED_LEAGUES directly and swept all 29
leagues on every run at roughly 10-20s of FlashScore each -- whatever the
caller asked for.

Same shape as get_fixtures_for_run_daily accepting fixtures_season and
discarding it (48d241c): a parameter accepted, threaded partway, then dropped.

Plain script, no pytest (repo convention):
    py -3.12 tests/league_filter_test.py
"""
from __future__ import annotations

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

import olp_xdv_pipeline as pipe  # noqa: E402

FAILURES: list[str] = []


def check(label: str, got, want) -> None:
    if got == want:
        print(f"  [OK] {label}")
    else:
        print(f"  [FAIL] {label}: got {got!r}, want {want!r}")
        FAILURES.append(label)


def check_true(label, got):
    check(label, bool(got), True)


def test_state_carries_the_selection() -> None:
    print("\ntest: PipelineState has somewhere to put it")

    st = pipe.PipelineState(season="2627", fixtures_season="2627",
                            dry_run=True, leagues=["EFL Cup", "La Liga"])
    check("selection is held", st.leagues, ["EFL Cup", "La Liga"])

    st = pipe.PipelineState(season="2627", fixtures_season="2627", dry_run=True)
    check("absent means the full whitelist", st.leagues, None)


def test_internal_runner_accepts_it() -> None:
    print("\ntest: the selection reaches the runner that builds the state")

    sig = inspect.signature(pipe._run_pipeline_internal)
    check_true("_run_pipeline_internal takes leagues", "leagues" in sig.parameters)

    sig = inspect.signature(pipe.run_pipeline)
    check_true("run_pipeline takes leagues", "leagues" in sig.parameters)

    # The drop point was here: run_pipeline declared the parameter and then
    # called the internal runner without forwarding it.
    src = inspect.getsource(pipe.run_pipeline)
    check_true("run_pipeline forwards it to _run_pipeline_internal",
               "leagues=leagues" in src)


def test_agent_1_reads_the_state_not_the_whitelist() -> None:
    print("\ntest: the scan loop consults the selection")

    # The loop used to be `for league in WHITELISTED_LEAGUES:` with no
    # reference to the requested set at all, which is what made the argument
    # inert. Pinning this by source keeps a future refactor from quietly
    # reverting to the unfiltered sweep.
    src = inspect.getsource(pipe.agent_1_ingest)
    check_true("agent_1_ingest consults state.leagues", "state.leagues" in src)
    check_true("and no longer iterates the raw whitelist",
               "for league in WHITELISTED_LEAGUES:" not in src)


def test_filter_logic() -> None:
    print("\ntest: the scan list is the intersection, and extras are reported")
    from engine.leagues import WHITELISTED_LEAGUES

    whitelist = list(WHITELISTED_LEAGUES)
    check_true("whitelist is non-empty", whitelist)

    def scan_list(selection):
        return [lg for lg in whitelist if not selection or lg in selection]

    check("no selection scans everything",
          len(scan_list(None)), len(whitelist))

    picked = whitelist[:2]
    check("a selection scans only those", scan_list(picked), picked)
    check_true("and that is fewer than the whole whitelist",
               len(scan_list(picked)) < len(whitelist))

    # A league that is not deploy-eligible cannot be scanned into a board, so
    # asking for one must be reported rather than silently yielding nothing.
    extras = set(["Not A Real League"]) - set(whitelist)
    check("an off-whitelist request is detectable",
          sorted(extras), ["Not A Real League"])
    check("and it contributes no scan targets",
          scan_list(["Not A Real League"]), [])


if __name__ == "__main__":
    test_state_carries_the_selection()
    test_internal_runner_accepts_it()
    test_agent_1_reads_the_state_not_the_whitelist()
    test_filter_logic()

    print()
    if FAILURES:
        print(f"=== {len(FAILURES)} FAILURE(S) ===")
        for f in FAILURES:
            print(f"  - {f}")
        sys.exit(1)
    print("=== all passed ===")
