# SEC EDGAR fixtures

`submissions-schema-fixture.json` uses the documented SEC submissions column names and shape but
contains intentionally synthetic values. It is safe for CI and must never be treated as a filing,
investment fact, or proof that the live endpoint is reachable.

A captured official raw response is still required before the Adapter can be declared live-validated.
CI and unit tests must remain network-free; live capture belongs to a separately controlled public-network
Runner with a declared User-Agent.
