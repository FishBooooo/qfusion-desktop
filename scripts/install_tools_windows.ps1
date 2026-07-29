$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$PSNativeCommandUseErrorActionPreference = $true

$scriptDirectory = Split-Path -Parent $MyInvocation.MyCommand.Path
. (Join-Path $scriptDirectory "qfusion_env.ps1")

if (-not $IsWindows) {
    throw "This script must run on a Windows x64 host or Windows CI runner."
}

$repositoryRoot = $env:QFUSION_REPOSITORY_ROOT
$versionFile = Join-Path $scriptDirectory "toolchain-versions.json"
$configuration = Get-Content -Raw -Path $versionFile | ConvertFrom-Json
$platform = "windows-x64"

function Stop-ByHostIsolation {
    param([Parameter(Mandatory = $true)][string]$Message)

    Write-Error "BLOCKED_BY_HOST_ISOLATION`n$Message"
}

function Get-CheckedDownload {
    param(
        [Parameter(Mandatory = $true)][string]$Url,
        [Parameter(Mandatory = $true)][string]$Sha256
    )

    $downloadDirectory = Join-Path $repositoryRoot ".cache/downloads"
    New-Item -ItemType Directory -Force -Path $downloadDirectory | Out-Null
    $destination = Join-Path $downloadDirectory ([IO.Path]::GetFileName($Url))

    if (Test-Path $destination -PathType Leaf) {
        $actualHash = (Get-FileHash -Algorithm SHA256 -Path $destination).Hash.ToLowerInvariant()
        if ($actualHash -ne $Sha256) {
            Stop-ByHostIsolation "Cached download checksum mismatch: $destination"
        }
        return $destination
    }

    $temporaryDownload = Join-Path $repositoryRoot ".tmp/$([guid]::NewGuid()).download"
    try {
        Invoke-WebRequest -NoProxy -Uri $Url -OutFile $temporaryDownload
        $actualHash = (Get-FileHash -Algorithm SHA256 -Path $temporaryDownload).Hash.ToLowerInvariant()
        if ($actualHash -ne $Sha256) {
            Stop-ByHostIsolation "Downloaded tool checksum mismatch: $Url"
        }
        Move-Item -Path $temporaryDownload -Destination $destination
    }
    finally {
        if (Test-Path $temporaryDownload -PathType Leaf) {
            Remove-Item -Force -Path $temporaryDownload
        }
    }
    return $destination
}

function New-QFusionTemporaryDirectory {
    $path = Join-Path $repositoryRoot ".tmp/$([guid]::NewGuid())"
    New-Item -ItemType Directory -Path $path | Out-Null
    return $path
}

function Remove-QFusionTemporaryDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $expectedPrefix = "$(Join-Path $repositoryRoot ".tmp")$([IO.Path]::DirectorySeparatorChar)"
    if (-not $Path.StartsWith($expectedPrefix, [StringComparison]::OrdinalIgnoreCase)) {
        Stop-ByHostIsolation "Refusing to clean an unexpected temporary path."
    }
    Remove-Item -Recurse -Force -Path $Path
}

$node = $configuration.tools.node
$nodeAsset = $node.assets.$platform
$nodeDirectory = Join-Path $repositoryRoot ".toolchains/node"
$nodeBinary = Join-Path $nodeDirectory "node.exe"
if (Test-Path $nodeBinary -PathType Leaf) {
    if ((& $nodeBinary --version) -ne "v$($node.version)") {
        Stop-ByHostIsolation "Existing project-local Node.js version does not match $($node.version)."
    }
}
elseif (Test-Path $nodeDirectory) {
    Stop-ByHostIsolation "Existing project-local Node.js directory is incomplete."
}
else {
    $nodeArchive = Get-CheckedDownload -Url $nodeAsset.url -Sha256 $nodeAsset.sha256
    $temporaryDirectory = New-QFusionTemporaryDirectory
    try {
        Expand-Archive -Path $nodeArchive -DestinationPath $temporaryDirectory
        $archiveRootName = [IO.Path]::GetFileNameWithoutExtension($nodeArchive)
        $archiveRoot = Join-Path $temporaryDirectory $archiveRootName
        if (-not (Test-Path (Join-Path $archiveRoot "node.exe") -PathType Leaf)) {
            Stop-ByHostIsolation "Node.js archive did not contain the expected binary."
        }
        Move-Item -Path $archiveRoot -Destination $nodeDirectory
    }
    finally {
        Remove-QFusionTemporaryDirectory -Path $temporaryDirectory
    }
}

$localBinDirectory = Join-Path $repositoryRoot ".toolchains/bin"

$uv = $configuration.tools.uv
$uvAsset = $uv.assets.$platform
$uvBinary = Join-Path $localBinDirectory "uv.exe"
if (Test-Path $uvBinary -PathType Leaf) {
    $uvOutput = & $uvBinary --version
    if (-not $uvOutput.StartsWith("uv $($uv.version)")) {
        Stop-ByHostIsolation "Existing project-local uv version does not match $($uv.version)."
    }
}
else {
    $uvArchive = Get-CheckedDownload -Url $uvAsset.url -Sha256 $uvAsset.sha256
    $temporaryDirectory = New-QFusionTemporaryDirectory
    try {
        Expand-Archive -Path $uvArchive -DestinationPath $temporaryDirectory
        $uvSource = Get-ChildItem -Recurse -File -Path $temporaryDirectory -Filter "uv.exe" |
            Select-Object -First 1
        $uvxSource = Get-ChildItem -Recurse -File -Path $temporaryDirectory -Filter "uvx.exe" |
            Select-Object -First 1
        if ($null -eq $uvSource -or $null -eq $uvxSource) {
            Stop-ByHostIsolation "uv archive did not contain the expected binaries."
        }
        Copy-Item -Path $uvSource.FullName -Destination $uvBinary
        Copy-Item -Path $uvxSource.FullName -Destination (Join-Path $localBinDirectory "uvx.exe")
    }
    finally {
        Remove-QFusionTemporaryDirectory -Path $temporaryDirectory
    }
}

$just = $configuration.tools.just
$justAsset = $just.assets.$platform
$justBinary = Join-Path $localBinDirectory "just.exe"
if (Test-Path $justBinary -PathType Leaf) {
    if ((& $justBinary --version) -ne "just $($just.version)") {
        Stop-ByHostIsolation "Existing project-local just version does not match $($just.version)."
    }
}
else {
    $justArchive = Get-CheckedDownload -Url $justAsset.url -Sha256 $justAsset.sha256
    $temporaryDirectory = New-QFusionTemporaryDirectory
    try {
        Expand-Archive -Path $justArchive -DestinationPath $temporaryDirectory
        $justSource = Get-ChildItem -Recurse -File -Path $temporaryDirectory -Filter "just.exe" |
            Select-Object -First 1
        if ($null -eq $justSource) {
            Stop-ByHostIsolation "just archive did not contain the expected binary."
        }
        Copy-Item -Path $justSource.FullName -Destination $justBinary
    }
    finally {
        Remove-QFusionTemporaryDirectory -Path $temporaryDirectory
    }
}

$corepackBinary = Join-Path $nodeDirectory "corepack.cmd"
$pnpmBinary = Join-Path $localBinDirectory "pnpm.cmd"
if (-not (Test-Path $corepackBinary -PathType Leaf)) {
    Stop-ByHostIsolation "Pinned Node.js archive does not include Corepack."
}
if (Test-Path $pnpmBinary -PathType Leaf) {
    if ((& $pnpmBinary --version) -ne $configuration.tools.pnpm.version) {
        Stop-ByHostIsolation "Existing project-local pnpm version does not match $($configuration.tools.pnpm.version)."
    }
}
else {
    & $corepackBinary enable --install-directory $localBinDirectory pnpm
    if ((& $pnpmBinary --version) -ne $configuration.tools.pnpm.version) {
        Stop-ByHostIsolation "Corepack did not activate the pinned pnpm $($configuration.tools.pnpm.version)."
    }
}

$rustup = $configuration.tools.rustup
$rustupAsset = $rustup.assets.$platform
$rustupBinary = Join-Path $repositoryRoot ".toolchains/cargo/bin/rustup.exe"
if (Test-Path $rustupBinary -PathType Leaf) {
    $rustupOutput = (& $rustupBinary --version | Select-Object -First 1)
    if (-not $rustupOutput.StartsWith("rustup $($rustup.version) ")) {
        Stop-ByHostIsolation "Existing project-local rustup version does not match $($rustup.version)."
    }
}
else {
    $rustupInstaller = Get-CheckedDownload -Url $rustupAsset.url -Sha256 $rustupAsset.sha256
    & $rustupInstaller `
        --component clippy `
        --component rustfmt `
        --default-host $rustupAsset.host `
        --default-toolchain $configuration.tools.rust.version `
        --no-modify-path `
        --profile minimal `
        -y
}

$installedToolchains = & $rustupBinary toolchain list
$expectedToolchain = "$($configuration.tools.rust.version)-$($rustupAsset.host)"
if (-not ($installedToolchains | Select-String -SimpleMatch $expectedToolchain -Quiet)) {
    & $rustupBinary toolchain install $configuration.tools.rust.version `
        --component clippy `
        --component rustfmt `
        --profile minimal
}

$rustcBinary = Join-Path $repositoryRoot ".toolchains/cargo/bin/rustc.exe"
$rustcOutput = & $rustcBinary --version
if (-not $rustcOutput.StartsWith("rustc $($configuration.tools.rust.version) ")) {
    Stop-ByHostIsolation "Project-local Rust compiler does not match $($configuration.tools.rust.version)."
}

Write-Host (
    "QFusion project-local tools ready: node={0} pnpm={1} uv={2} rust={3} rustup={4} just={5}" -f
    $node.version,
    $configuration.tools.pnpm.version,
    $uv.version,
    $configuration.tools.rust.version,
    $rustup.version,
    $just.version
)
