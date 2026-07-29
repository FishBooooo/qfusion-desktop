# QFusion SQLite migrations

Migrations are invoked programmatically through `qfusion.storage.upgrade_database`.
The Alembic environment deliberately contains no database URL and refuses to create an
engine from Shell or user configuration.

Production startup may only upgrade the caller-selected QFusion SQLite database. Downgrade
commands exist in revision files for reversibility testing, but are not exposed by the
application. Tests create their database under the Runner's repository-local `.tmp/`.
