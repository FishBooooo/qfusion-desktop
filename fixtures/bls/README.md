# BLS fixtures

`public-data-v1-schema-fixture.json` is a fully synthetic payload shaped like the
credential-free BLS Public Data API v1 response. The series identifier, values,
periods, and footnotes are test-only and must never be presented as BLS facts.

The fixture exists to test schema validation, first-observed Point-in-Time
semantics, annual-row exclusion, revision identity, and deterministic parsing.
Tests must not call the live BLS API.
