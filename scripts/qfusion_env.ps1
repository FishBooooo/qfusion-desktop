$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
$repositoryRoot = (Resolve-Path (Join-Path $scriptDirectory "..")).Path

if (
    -not (Test-Path (Join-Path $repositoryRoot "PROJECT_TASKBOOK.md") -PathType Leaf) -or
    -not (Test-Path (Join-Path $repositoryRoot "pyproject.toml") -PathType Leaf)
) {
    throw "Refusing to run outside the QFusion repository."
}

$excludedEnvironmentPatterns = @(
    "ALL_PROXY",
    "AMENT_*",
    "CARGO_*",
    "CC",
    "CFLAGS",
    "CMAKE_PREFIX_PATH",
    "COLCON_*",
    "CONDA_*",
    "COREPACK_*",
    "CXX",
    "CXXFLAGS",
    "CUDA_*",
    "DOCKER_*",
    "DOTNET_*",
    "GIT_CONFIG_*",
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "JAVA_*",
    "KUBECONFIG",
    "LDFLAGS",
    "LD_LIBRARY_PATH",
    "NVIDIA_*",
    "NODE_OPTIONS",
    "NODE_PATH",
    "NO_PROXY",
    "NPM_*",
    "NUGET_*",
    "PIP_*",
    "PKG_CONFIG_*",
    "PLAYWRIGHT_*",
    "PNPM_*",
    "PODMAN_*",
    "PYTHONHOME",
    "PYTHONPATH",
    "PYTHONUSERBASE",
    "ROS_*",
    "RUSTDOCFLAGS",
    "RUSTFLAGS",
    "RUSTUP_*",
    "SCCACHE_*",
    "SSH_AUTH_SOCK",
    "UV_*",
    "VIRTUAL_ENV"
)

foreach ($environmentEntry in Get-ChildItem Env:) {
    foreach ($pattern in $excludedEnvironmentPatterns) {
        if ($environmentEntry.Name -like $pattern) {
            Remove-Item "Env:$($environmentEntry.Name)"
            break
        }
    }
}

$cacheDirectory = Join-Path $repositoryRoot ".cache"
$homeDirectory = Join-Path $cacheDirectory "home"
$temporaryDirectory = Join-Path $repositoryRoot ".tmp"
$toolchainDirectory = Join-Path $repositoryRoot ".toolchains"
$localBinDirectory = Join-Path $toolchainDirectory "bin"

$localDirectories = @(
    (Join-Path $cacheDirectory "corepack"),
    (Join-Path $cacheDirectory "coverage"),
    (Join-Path $cacheDirectory "dotnet"),
    (Join-Path $cacheDirectory "nuget"),
    (Join-Path $cacheDirectory "pip"),
    (Join-Path $cacheDirectory "playwright"),
    (Join-Path $cacheDirectory "pnpm/cache"),
    (Join-Path $cacheDirectory "pnpm/state"),
    (Join-Path $cacheDirectory "pnpm/store"),
    (Join-Path $cacheDirectory "uv"),
    (Join-Path $cacheDirectory "xdg/cache"),
    (Join-Path $cacheDirectory "xdg/config"),
    (Join-Path $cacheDirectory "xdg/data"),
    (Join-Path $cacheDirectory "xdg/state"),
    (Join-Path $homeDirectory "AppData/Local"),
    (Join-Path $homeDirectory "AppData/Roaming"),
    $localBinDirectory,
    $temporaryDirectory,
    (Join-Path $toolchainDirectory "cargo"),
    (Join-Path $toolchainDirectory "python"),
    (Join-Path $toolchainDirectory "rustup"),
    (Join-Path $toolchainDirectory "uv-tools")
)

foreach ($directory in $localDirectories) {
    New-Item -ItemType Directory -Force -Path $directory | Out-Null
}

$env:APPDATA = Join-Path $homeDirectory "AppData/Roaming"
$env:CARGO_HOME = Join-Path $toolchainDirectory "cargo"
$env:COREPACK_HOME = Join-Path $cacheDirectory "corepack"
$env:COVERAGE_FILE = Join-Path $cacheDirectory "coverage/.coverage"
$env:DOTNET_CLI_HOME = Join-Path $cacheDirectory "dotnet"
$env:GIT_CONFIG_GLOBAL = "NUL"
$env:GIT_CONFIG_NOSYSTEM = "1"
$env:HOME = $homeDirectory
$env:LOCALAPPDATA = Join-Path $homeDirectory "AppData/Local"
$env:NPM_CONFIG_CACHE = Join-Path $cacheDirectory "pnpm/cache"
$env:NPM_CONFIG_GLOBALCONFIG = "NUL"
$env:NPM_CONFIG_STATE_DIR = Join-Path $cacheDirectory "pnpm/state"
$env:NPM_CONFIG_STORE_DIR = Join-Path $cacheDirectory "pnpm/store"
$env:NPM_CONFIG_USERCONFIG = Join-Path $repositoryRoot ".npmrc"
$env:NUGET_PACKAGES = Join-Path $cacheDirectory "nuget"
$env:PIP_CACHE_DIR = Join-Path $cacheDirectory "pip"
$env:PIP_CONFIG_FILE = "NUL"
$env:PLAYWRIGHT_BROWSERS_PATH = Join-Path $cacheDirectory "playwright"
$env:PNPM_HOME = $localBinDirectory
$env:PYTHONUTF8 = "1"
$env:QFUSION_CACHE_DIR = $cacheDirectory
$env:QFUSION_ISOLATED = "1"
$env:QFUSION_REPOSITORY_ROOT = $repositoryRoot
$env:RUSTUP_AUTO_INSTALL = "0"
$env:RUSTUP_HOME = Join-Path $toolchainDirectory "rustup"
$env:RUSTUP_INIT_SKIP_PATH_CHECK = "yes"
$env:RUSTUP_NO_UPDATE_CHECK = "1"
$env:RUSTUP_TOOLCHAIN = "1.97.1-x86_64-pc-windows-msvc"
$env:TEMP = $temporaryDirectory
$env:TMP = $temporaryDirectory
$env:USERPROFILE = $homeDirectory
$env:UV_CACHE_DIR = Join-Path $cacheDirectory "uv"
$env:UV_NO_SYSTEM_CONFIG = "1"
$env:UV_PROJECT_ENVIRONMENT = Join-Path $repositoryRoot ".venv"
$env:UV_PYTHON_INSTALL_DIR = Join-Path $toolchainDirectory "python"
$env:UV_TOOL_BIN_DIR = $localBinDirectory
$env:UV_TOOL_DIR = Join-Path $toolchainDirectory "uv-tools"
$env:XDG_CACHE_HOME = Join-Path $cacheDirectory "xdg/cache"
$env:XDG_CONFIG_HOME = Join-Path $cacheDirectory "xdg/config"
$env:XDG_DATA_HOME = Join-Path $cacheDirectory "xdg/data"
$env:XDG_STATE_HOME = Join-Path $cacheDirectory "xdg/state"

$pathEntries = @(
    $localBinDirectory,
    (Join-Path $toolchainDirectory "node"),
    (Join-Path $toolchainDirectory "cargo/bin"),
    (Join-Path $repositoryRoot ".venv/Scripts"),
    (Join-Path $env:SystemRoot "System32"),
    $env:SystemRoot
)
$env:Path = $pathEntries -join [IO.Path]::PathSeparator
