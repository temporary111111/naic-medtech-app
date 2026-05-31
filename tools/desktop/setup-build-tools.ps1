[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
$Requirements = Join-Path $DesktopDir "requirements-build.txt"

if (-not (Test-Path -LiteralPath $VenvPython -PathType Leaf)) {
    throw "Project virtual environment not found: $VenvPython"
}

Write-Host "Installing desktop build tools into the project virtual environment..."
& $VenvPython -m pip install --use-feature=truststore -r $Requirements
if ($LASTEXITCODE -ne 0) {
    throw "Desktop build-tool installation failed."
}

Write-Host "PyInstaller is ready."
Write-Host "Inno Setup 6 is still required for the final Setup.exe wrapper. The packaged app can be validated first with:"
Write-Host "  .\tools\desktop\build-installer.ps1 -SkipInstaller"
