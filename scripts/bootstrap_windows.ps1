$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "install_tools_windows.ps1")
. (Join-Path $scriptDirectory "qfusion_env.ps1")

uv sync --locked --all-extras
uv run python scripts/check_pnpm_isolation.py
uv run python scripts/export_openapi.py
pnpm install --frozen-lockfile
pnpm generate:client

Write-Host "QFusion Windows workspace setup completed."
