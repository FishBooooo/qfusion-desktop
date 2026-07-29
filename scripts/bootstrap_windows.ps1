$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "install_tools_windows.ps1")
. (Join-Path $scriptDirectory "qfusion_env.ps1")

uv sync --locked --all-extras
uv run --locked python scripts/check_pnpm_isolation.py
uv run --locked python scripts/export_openapi.py
pnpm install --frozen-lockfile
pnpm generate:client

Write-Host "QFusion Windows workspace setup completed."
