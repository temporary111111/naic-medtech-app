[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$Requirements = Join-Path $DesktopDir "requirements-build.txt"

$PythonCandidates = @(
    (Join-Path $ProjectRoot "env\Scripts\python.exe"),
    (Join-Path $ProjectRoot ".venv\Scripts\python.exe"),
    "py -3.11",
    "python"
)
$PythonCommand = ""
foreach ($candidate in $PythonCandidates) {
    try {
        if ($candidate -like "*\python.exe" -and -not (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            continue
        }
        if ($candidate -eq "py -3.11") {
            & py -3.11 --version *> $null
        } else {
            & $candidate --version *> $null
        }
        if ($LASTEXITCODE -eq 0) {
            $PythonCommand = $candidate
            break
        }
    } catch {
        continue
    }
}

if (-not $PythonCommand) {
    throw "No working Python interpreter was found. Create env with Python 3.11 first."
}

Write-Host "Installing desktop build tools into the project virtual environment..."
if ($PythonCommand -eq "py -3.11") {
    & py -3.11 -m pip install --use-feature=truststore -r $Requirements
} else {
    & $PythonCommand -m pip install --use-feature=truststore -r $Requirements
}
if ($LASTEXITCODE -ne 0) {
    throw "Desktop build-tool installation failed."
}

Write-Host "PyInstaller is ready."
Write-Host "Inno Setup 6 is still required for the final Setup.exe wrapper. The packaged app can be validated first with:"
Write-Host "  .\tools\desktop\build-installer.ps1 -SkipInstaller"
