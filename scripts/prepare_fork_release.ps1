[CmdletBinding()]
param(
    [Parameter(Mandatory)]
    [string] $TargetPath,
    [Parameter()]
    [string] $BaseRevision = "v9.3.7",
    [Parameter()]
    [string] $BranchName = "zhcn-v9",
    [Parameter()]
    [string] $CommitMessage = "Add Simplified Chinese support for D4LF V9",
    [Parameter()]
    [string] $AuthorName,
    [Parameter()]
    [string] $AuthorEmail
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
    throw "The fork release target must be outside the private development worktree."
}

$dirty = git status --porcelain
if ($LASTEXITCODE -ne 0) {
    throw "Unable to inspect the source worktree."
}
if ($dirty) {
    throw "Commit or stash all source changes before preparing a fork release."
}

if (-not $AuthorName) {
    $AuthorName = (git config --get user.name).Trim()
}
if (-not $AuthorEmail) {
    $AuthorEmail = (git config --get user.email).Trim()
}
if (-not $AuthorName) {
    throw "A public Git author name is required."
}
if ($AuthorEmail -notmatch "@users\.noreply\.github\.com$") {
    throw "The public Git author email must be a GitHub noreply address."
}
Invoke-Checked -Command "git" -Arguments @("check-ref-format", "--branch", $BranchName)

$baseCommit = (git rev-parse "$BaseRevision^{commit}").Trim()
if ($LASTEXITCODE -ne 0 -or -not $baseCommit) {
    throw "Unable to resolve the upstream base revision $BaseRevision."
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
        throw "The fork release target already exists and is not empty."
    }
} else {
    $null = New-Item -ItemType Directory -Path $targetRoot
}

$temporaryId = [guid]::NewGuid().ToString("N")
$temporaryRef = "refs/d4lf-release-export/$temporaryId"
$archivePath = Join-Path ([IO.Path]::GetTempPath()) "d4lf-fork-tree-$temporaryId.zip"
$bundlePath = Join-Path ([IO.Path]::GetTempPath()) "d4lf-fork-base-$temporaryId.bundle"
$oldAuthorDate = $env:GIT_AUTHOR_DATE
$oldCommitterDate = $env:GIT_COMMITTER_DATE

try {
    Invoke-Checked -Command "git" -Arguments @("update-ref", $temporaryRef, $baseCommit)
    Invoke-Checked -Command "git" -Arguments @("bundle", "create", $bundlePath, $temporaryRef)
    Invoke-Checked -Command "git" -Arguments @("archive", "--format=zip", "--output=$archivePath", "HEAD")

    Invoke-Checked -Command "git" -Arguments @("init", $targetRoot)
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "config", "--local", "core.logAllRefUpdates", "false")
    Invoke-Checked -Command "git" -Arguments @(
        "-C",
        $targetRoot,
        "fetch",
        "--no-tags",
        $bundlePath,
        "${temporaryRef}:refs/heads/$BranchName"
    )
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "checkout", $BranchName)
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "rm", "-r", "--ignore-unmatch", ".")
    Expand-Archive -LiteralPath $archivePath -DestinationPath $targetRoot

    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "config", "--local", "user.name", $AuthorName)
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "config", "--local", "user.email", $AuthorEmail)
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "config", "--local", "user.useConfigOnly", "true")
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "config", "--local", "commit.gpgSign", "false")

    $releaseDate = [DateTimeOffset]::UtcNow.ToString("yyyy-MM-ddTHH:mm:ssZ")
    $env:GIT_AUTHOR_DATE = $releaseDate
    $env:GIT_COMMITTER_DATE = $releaseDate
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "add", "--force", "--all")
    Invoke-Checked -Command "git" -Arguments @("-C", $targetRoot, "commit", "-m", $CommitMessage)
    Remove-TransientGitMetadata -RepositoryRoot $targetRoot

    $targetStatus = git -C $targetRoot status --porcelain --untracked-files=all
    if ($LASTEXITCODE -ne 0 -or $targetStatus) {
        throw "The prepared fork worktree does not exactly match the committed archive."
    }
    $ignoredFiles = git -C $targetRoot ls-files --others --ignored --exclude-standard
    if ($LASTEXITCODE -ne 0 -or $ignoredFiles) {
        throw "The prepared fork contains archive files that were not committed."
    }

    Push-Location $targetRoot
    try {
        $releaseScanArguments = @(
            "run",
            "--no-project",
            "--python",
            "3.14",
            "python",
            "-B",
            "-m",
            "src.tools.public_safety",
            "--fork-release",
            "--fork-base",
            $baseCommit,
            "--expected-branch",
            $BranchName,
            "--expected-author-name",
            $AuthorName,
            "--expected-author-email",
            $AuthorEmail
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
    git update-ref -d $temporaryRef 2>$null
    if (Test-Path -LiteralPath $archivePath -PathType Leaf) {
        Remove-Item -LiteralPath $archivePath -Force
    }
    if (Test-Path -LiteralPath $bundlePath -PathType Leaf) {
        Remove-Item -LiteralPath $bundlePath -Force
    }
}

Write-Host "Fork release prepared at $targetRoot"
Write-Host "Branch: $BranchName"
Write-Host "Base: $baseCommit"
Write-Host "Author: $AuthorName <$AuthorEmail>"
Write-Host "No Git remote was added."
