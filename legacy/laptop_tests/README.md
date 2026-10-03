# Retired laptop-line tests (2026-10-03)

These 66 test files came in with the laptop line (`elo-persistence`) in the
lineage merge (#47; see `docs/LINEAGE_MERGE_2026-10-03.md`). Each tests a
laptop version of a module that the merge did not keep (main's version won),
so none of them can pass against the unified code. Most fail on import
(`blend_toward_market`, `fetch_today`, `EloModel.to_payload`,
`booking.sportybet_cache` and similar).

They are kept for reference and do not run in CI. To revive a laptop feature,
port it into the live code as a normal PR and bring its test back into
`tests/` with it. Each file runs from the repo root as
`python legacy/laptop_tests/<name>.py`, but expect the same import failures
until its feature is ported.

The laptop tests that still pass against the unified code stayed in `tests/`.
