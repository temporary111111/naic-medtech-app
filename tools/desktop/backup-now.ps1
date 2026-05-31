[CmdletBinding()]
param(
    [string]$Reason = "manual",
    [string]$Destination = ""
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$DataDir = Join-Path $ProjectRoot "data\runtime"
$env:PYTHONPATH = Join-Path $ProjectRoot "app"
$arguments = @((Join-Path $DesktopDir "launcher.py"), "--data-dir", $DataDir, "--backup-now", "--reason", $Reason)
if ($Destination) {
    $arguments += @("--destination", $Destination)
}

python @arguments
if ($LASTEXITCODE -ne 0) {
    throw "Verified backup creation failed."
}
