[CmdletBinding()]
param(
    [Parameter(ValueFromRemainingArguments)]
    [string[]] $InputPaths = @()
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"
$requiredVersion = [version] "1.25.0"

$module = Get-Module -ListAvailable -Name PSScriptAnalyzer |
    Where-Object Version -EQ $requiredVersion |
    Select-Object -First 1

if ($null -eq $module) {
    [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
    $provider = Get-PackageProvider -Name NuGet -ListAvailable -ErrorAction SilentlyContinue |
        Sort-Object Version -Descending |
        Select-Object -First 1
    if ($null -eq $provider -or $provider.Version -lt [version] "2.8.5.201") {
        $null = Install-PackageProvider `
            -Name NuGet `
            -MinimumVersion "2.8.5.201" `
            -Scope CurrentUser `
            -Force `
            -Confirm:$false
    }
    Install-Module `
        -Name PSScriptAnalyzer `
        -RequiredVersion $requiredVersion `
        -Scope CurrentUser `
        -Repository PSGallery `
        -Force `
        -AllowClobber `
        -Confirm:$false
    $module = Get-Module -ListAvailable -Name PSScriptAnalyzer |
        Where-Object Version -EQ $requiredVersion |
        Select-Object -First 1
}

Import-Module $module.Path -Force

$findings = @(
    foreach ($inputPath in $InputPaths) {
        if (Test-Path -LiteralPath $inputPath -PathType Leaf) {
            Invoke-ScriptAnalyzer -Path $inputPath -Severity Error
        }
    }
)

if ($findings.Count -gt 0) {
    $findings |
        Select-Object RuleName, Severity, ScriptName, Line, Message |
        Format-Table -AutoSize |
        Out-String |
        Write-Output
    exit 1
}
