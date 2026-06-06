[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Archive,
    [switch]$IncludeConfig
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$DataDir = Join-Path $ProjectRoot "data\runtime"
$env:PYTHONPATH = Join-Path $ProjectRoot "app"

$arguments = @((Join-Path $DesktopDir "launcher.py"), "--data-dir", $DataDir, "--restore-backup", $Archive)
if ($IncludeConfig) {
    $arguments += "--include-config"
}

python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Backup restore failed."
}
