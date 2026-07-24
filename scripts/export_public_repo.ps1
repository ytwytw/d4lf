[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $TargetPath
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

function Invoke-Checked {
    param(
        [Parameter(Mandatory)]
        [string] $Command,
        [Parameter()]
        [string[]] $Arguments = @()
    )

    & $Command @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Command failed with exit code $LASTEXITCODE"
    }
}

function Remove-TransientGitMetadata {
    param(
        [Parameter(Mandatory)]
        [string] $RepositoryRoot
    )

    $resolvedRoot = [IO.Path]::GetFullPath($RepositoryRoot)
    $expectedGitDirectory = [IO.Path]::GetFullPath((Join-Path $resolvedRoot ".git"))
    $gitDirectory = (git -C $resolvedRoot rev-parse --absolute-git-dir).Trim()
    if ($LASTEXITCODE -ne 0 -or -not $gitDirectory) {
        throw "Unable to resolve the prepared repository Git directory."
    }
    $gitDirectory = [IO.Path]::GetFullPath($gitDirectory)
    if (-not $gitDirectory.Equals($expectedGitDirectory, [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to clean Git metadata outside the prepared repository."
    }

    Invoke-Checked -Command "git" -Arguments @("-C", $resolvedRoot, "reflog", "expire", "--expire=now", "--all")
    foreach ($name in @("FETCH_HEAD", "ORIG_HEAD", "MERGE_HEAD", "CHERRY_PICK_HEAD", "REBASE_HEAD")) {
        $metadataPath = Join-Path $gitDirectory $name
        if (Test-Path -LiteralPath $metadataPath) {
            Remove-Item -LiteralPath $metadataPath -Force
        }
    }
    foreach ($relativePath in @("logs", "refs/original")) {
        $metadataPath = Join-Path $gitDirectory $relativePath
        if (Test-Path -LiteralPath $metadataPath) {
            Remove-Item -LiteralPath $metadataPath -Recurse -Force
        }
    }
}

$sourceRoot = (git rev-parse --show-toplevel).Trim()
if ($LASTEXITCODE -ne 0 -or -not $sourceRoot) {
    throw "Run this script from a Git worktree."
}
$sourceRoot = [IO.Path]::GetFullPath($sourceRoot)
$targetRoot = [IO.Path]::GetFullPath($TargetPath)
$sourcePrefix = $sourceRoot.TrimEnd([IO.Path]::DirectorySeparatorChar) + [IO.Path]::DirectorySeparatorChar
if ($targetRoot.Equals($sourceRoot, [StringComparison]::OrdinalIgnoreCase) -or
    $targetRoot.StartsWith($sourcePrefix, [StringComparison]::OrdinalIgnoreCase)) {
    throw "The public export target must be outside the private development worktree."
}

$dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect the source worktree."
}
if ($dirty) {
    throw "Commit or stash all source changes before creating a public export."
}

$denylist = Join-Path $sourceRoot ".public-safety.local"
$sourceScanArguments = @(
    "run",
    "python",
    "-B",
    "-m",
    "src.tools.public_safety",
    "--tree",
    "HEAD",
    "--require-third-party-redistribution"
)
if (Test-Path -LiteralPath $denylist -PathType Leaf) {
    $sourceScanArguments += @("--denylist", $denylist)
}
Invoke-Checked -Command "uv" -Arguments $sourceScanArguments

if (Test-Path -LiteralPath $targetRoot) {
    if (Get-ChildItem -LiteralPath $targetRoot -Force | Select-Object -First 1) {
        throw "The public export target already exists and is not empty."
    }
} else {
    $null = New-Item -ItemType Directory -Path $targetRoot
}

$archivePath = Join-Path ([IO.Path]::GetTempPath()) ("d4lf-public-" + [guid]::NewGuid().ToString("N") + ".zip")
$oldAuthorDate = $env:GIT_AUTHOR_DATE
$oldCommitterDate = $env:GIT_COMMITTER_DATE

try {
    Invoke-Checked -Command "git" -Arguments @("archive", "--format=zip", "--output=$archivePath", "HEAD")
    Expand-Archive -LiteralPath $archivePath -DestinationPath $targetRoot

    $pathScanArguments = @("run", "python", "-B", "-m", "src.tools.public_safety", "--path", $targetRoot)
    if (Test-Path -LiteralPath $denylist -PathType Leaf) {
        $pathScanArguments += @("--denylist", $denylist)
    }
    Invoke-Checked -Command "uv" -Arguments $pathScanArguments

    Push-Location $targetRoot
    try {
        Invoke-Checked -Command "git" -Arguments @("init", "-b", "main")
        Invoke-Checked -Command "git" -Arguments @("config", "--local", "core.logAllRefUpdates", "false")
        Invoke-Checked -Command "git" -Arguments @("config", "--local", "user.name", "D4LF Public Release")
        Invoke-Checked -Command "git" -Arguments @("config", "--local", "user.email", "public-release@invalid")
        Invoke-Checked -Command "git" -Arguments @("config", "--local", "user.useConfigOnly", "true")
        Invoke-Checked -Command "git" -Arguments @("config", "--local", "commit.gpgSign", "false")

        $env:GIT_AUTHOR_DATE = "2000-01-01T00:00:00Z"
        $env:GIT_COMMITTER_DATE = "2000-01-01T00:00:00Z"
        Invoke-Checked -Command "git" -Arguments @("add", "--all")
        Invoke-Checked -Command "git" -Arguments @("commit", "-m", "Initial public release")
        Remove-TransientGitMetadata -RepositoryRoot $targetRoot

        $releaseScanArguments = @(
            "run",
            "--no-project",
            "--python",
            "3.14",
            "python",
            "-B",
            "-m",
            "src.tools.public_safety",
            "--public-release",
            "--require-third-party-redistribution"
        )
        if (Test-Path -LiteralPath $denylist -PathType Leaf) {
            $releaseScanArguments += @("--denylist", $denylist)
        }
        Invoke-Checked -Command "uv" -Arguments $releaseScanArguments
    } finally {
        Pop-Location
    }
} finally {
    if ($null -eq $oldAuthorDate) {
        Remove-Item Env:GIT_AUTHOR_DATE -ErrorAction SilentlyContinue
    } else {
        $env:GIT_AUTHOR_DATE = $oldAuthorDate
    }
    if ($null -eq $oldCommitterDate) {
        Remove-Item Env:GIT_COMMITTER_DATE -ErrorAction SilentlyContinue
    } else {
        $env:GIT_COMMITTER_DATE = $oldCommitterDate
    }
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
        Remove-Item -LiteralPath $archivePath -Force
    }
}

Write-Host "Public export created at $targetRoot"
Write-Host "It has one neutral root commit and no Git remote."
