[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$Archive
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$DataDir = Join-Path $ProjectRoot "data\runtime"
$env:PYTHONPATH = Join-Path $ProjectRoot "app"

python (Join-Path $DesktopDir "launcher.py") --data-dir $DataDir --verify-backup $Archive
if ($LASTEXITCODE -ne 0) {
    throw "Backup verification failed."
}
