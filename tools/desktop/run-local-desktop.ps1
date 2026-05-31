[CmdletBinding()]
param(
    [int]$Port = 8114
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$DataDir = Join-Path $ProjectRoot "data\runtime"
$env:PYTHONPATH = Join-Path $ProjectRoot "app"

python (Join-Path $DesktopDir "launcher.py") --data-dir $DataDir --port $Port
if ($LASTEXITCODE -ne 0) {
    throw "Local desktop launcher failed."
}
