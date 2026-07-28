$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "This script must run on a Windows host or Windows CI runner."
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "install_tools_windows.ps1")
. (Join-Path $scriptDirectory "qfusion_env.ps1")

uv sync --locked --all-extras
uv run python scripts/check_pnpm_isolation.py
uv run python scripts/export_openapi.py
pnpm install --frozen-lockfile
pnpm generate:client

uv run ruff check services/backend scripts
uv run mypy
uv run pytest
pnpm --dir apps/desktop lint
pnpm --dir apps/desktop typecheck
pnpm --dir apps/desktop test

uv run python scripts/build_backend.py
pnpm --dir apps/desktop tauri build --bundles nsis

Write-Host "Windows M0 artifacts were built. Sidecar embedding is intentionally deferred."
