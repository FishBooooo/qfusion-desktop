$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

if (-not $IsWindows) {
    throw "This script must run on a Windows host or Windows CI runner."
}

function Invoke-QFusionNativeCommand {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$FilePath,
        [Parameter(Mandatory = $true)][string[]]$Arguments
    )

    & $FilePath @Arguments
    $exitCode = $LASTEXITCODE
    if ($exitCode -ne 0) {
        throw "QFusion native command '$Name' failed with exit code $exitCode."
    }
}

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
& (Join-Path $scriptDirectory "install_tools_windows.ps1")
. (Join-Path $scriptDirectory "qfusion_env.ps1")

Invoke-QFusionNativeCommand "uv sync" "uv" @("sync", "--locked", "--all-extras")
Invoke-QFusionNativeCommand "pnpm isolation check" "uv" @("run", "--locked", "python", "scripts/check_pnpm_isolation.py")
Invoke-QFusionNativeCommand "OpenAPI export" "uv" @("run", "--locked", "python", "scripts/export_openapi.py")
Invoke-QFusionNativeCommand "pnpm install" "pnpm" @("install", "--frozen-lockfile")
Invoke-QFusionNativeCommand "generated client" "pnpm" @("generate:client")
Invoke-QFusionNativeCommand "Tauri icon generation" "pnpm" @("--dir", "apps/desktop", "tauri", "icon", "src-tauri/app-icon.svg", "--output", "src-tauri/icons")

Invoke-QFusionNativeCommand "cargo fmt" "cargo" @("fmt", "--manifest-path", "apps/desktop/src-tauri/Cargo.toml", "--all", "--check")
Invoke-QFusionNativeCommand "cargo clippy" "cargo" @("clippy", "--locked", "--manifest-path", "apps/desktop/src-tauri/Cargo.toml", "--all-targets", "--", "-D", "warnings")
Invoke-QFusionNativeCommand "cargo test" "cargo" @("test", "--locked", "--manifest-path", "apps/desktop/src-tauri/Cargo.toml")

Invoke-QFusionNativeCommand "Ruff" "uv" @("run", "--locked", "ruff", "check", "services/backend", "scripts")
Invoke-QFusionNativeCommand "mypy" "uv" @("run", "--locked", "mypy")
Invoke-QFusionNativeCommand "pytest" "uv" @("run", "--locked", "python", "-m", "pytest")
Invoke-QFusionNativeCommand "frontend lint" "pnpm" @("--dir", "apps/desktop", "lint")
Invoke-QFusionNativeCommand "frontend typecheck" "pnpm" @("--dir", "apps/desktop", "typecheck")
Invoke-QFusionNativeCommand "frontend tests" "pnpm" @("--dir", "apps/desktop", "test")

Invoke-QFusionNativeCommand "Nuitka backend build" "uv" @("run", "--locked", "python", "scripts/build_backend.py")
Invoke-QFusionNativeCommand "standalone backend smoke" "uv" @("run", "--locked", "python", "scripts/smoke_backend_standalone.py")
Invoke-QFusionNativeCommand "Tauri NSIS build" "pnpm" @("--dir", "apps/desktop", "tauri", "build", "--bundles", "nsis")

Write-Host "Windows M0 artifacts were built and the standalone backend health smoke passed."
