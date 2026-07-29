# QFusion SQLite migrations

Migrations are invoked programmatically through `qfusion.storage.upgrade_database`.
The Alembic environment deliberately contains no database URL and refuses to create an
engine from Shell or user configuration.

Production startup may only upgrade the caller-selected QFusion SQLite database. Downgrade
commands exist in revision files for reversibility testing, but are not exposed by the
application. Tests create their database under the Runner's repository-local `.tmp/`.

The Nuitka build copies the exact `env.py`, revision files, and template into a
`qfusion_migrations/` directory beside the standalone executable. The build manifest records
each asset's SHA-256 and the single Alembic head. Windows smoke testing first asks the compiled
executable to load and verify that packaged revision graph before it starts an owned Loopback
health-check process.
