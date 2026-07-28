$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

if (-not $IsWindows) {
    throw "This script must run on a Windows host or Windows CI runner."
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "install_tools_windows.ps1")
. (Join-Path $scriptDirectory "qfusion_env.ps1")

uv sync --locked --all-extras
uv run --locked python scripts/check_pnpm_isolation.py
uv run --locked python scripts/export_openapi.py
pnpm install --frozen-lockfile
pnpm generate:client
pnpm --dir apps/desktop tauri icon src-tauri/app-icon.svg --output src-tauri/icons

cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml --all --check
cargo clippy --locked --manifest-path apps/desktop/src-tauri/Cargo.toml --all-targets -- -D warnings
cargo test --locked --manifest-path apps/desktop/src-tauri/Cargo.toml

uv run --locked ruff check services/backend scripts
uv run --locked mypy
uv run --locked python -m pytest
pnpm --dir apps/desktop lint
pnpm --dir apps/desktop typecheck
pnpm --dir apps/desktop test

uv run --locked python scripts/build_backend.py
pnpm --dir apps/desktop tauri build --bundles nsis

Write-Host "Windows M0 artifacts were built. Sidecar embedding is intentionally deferred."
