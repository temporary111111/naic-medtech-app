[CmdletBinding()]
param(
    [ValidateSet("x64", "x86")]
    [string]$Architecture = "x64",
    [string]$Version = "",
    [string]$PythonCommand = "",
    [switch]$SkipInstaller,
    [switch]$SkipSmokeTest
)

$ErrorActionPreference = "Stop"
$DesktopDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ProjectRoot = (Resolve-Path (Join-Path $DesktopDir "..\..")).Path
$BuildRoot = Join-Path $ProjectRoot "dist\desktop"
$PackageDist = Join-Path $BuildRoot "package"
$WorkDir = Join-Path $BuildRoot "work"
$InstallerOutput = Join-Path $BuildRoot "installer"
$SpecPath = Join-Path $DesktopDir "package.spec"
$InstallerScript = Join-Path $DesktopDir "installer.iss"
$IconFile = Join-Path $DesktopDir "assets\ndhi-labrecords.ico"
$VersionPath = Join-Path $DesktopDir "VERSION"

if (-not $PythonCommand) {
    $VenvPython = Join-Path $ProjectRoot ".venv\Scripts\python.exe"
    $PythonCommand = if (Test-Path -LiteralPath $VenvPython -PathType Leaf) { $VenvPython } else { "python" }
}

if (-not $Version) {
    $Version = (Get-Content -LiteralPath $VersionPath -Raw).Trim()
}
if (-not (Test-Path -LiteralPath $IconFile -PathType Leaf)) {
    throw "Desktop icon file is missing: $IconFile"
}
if ($Version -notmatch "^[0-9]+\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$") {
    throw "Version '$Version' must use a SemVer-like format such as 0.1.0-dev."
}

function Invoke-Python {
    param([Parameter(ValueFromRemainingArguments = $true)][string[]]$Arguments)
    & $PythonCommand @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "Python command failed: $PythonCommand $($Arguments -join ' ')"
    }
}

function Remove-SafeBuildDirectory {
    param([string]$Path)
    if (-not (Test-Path -LiteralPath $Path)) {
        return
    }
    $resolvedBuildRoot = [IO.Path]::GetFullPath($BuildRoot).TrimEnd("\")
    $resolvedTarget = [IO.Path]::GetFullPath($Path).TrimEnd("\")
    if (-not $resolvedTarget.StartsWith($resolvedBuildRoot + "\", [StringComparison]::OrdinalIgnoreCase)) {
        throw "Refusing to remove path outside the desktop build directory: $resolvedTarget"
    }
    foreach ($attempt in 1..8) {
        try {
            Remove-Item -LiteralPath $resolvedTarget -Recurse -Force -ErrorAction Stop
            return
        } catch {
            if ($attempt -eq 8) {
                throw
            }
            Start-Sleep -Milliseconds 750
        }
    }
}

function Find-Iscc {
    $command = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    $candidates = @()
    foreach ($root in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, (Join-Path $env:LOCALAPPDATA "Programs"))) {
        if ($root) {
            $candidates += Join-Path $root "Inno Setup 6\ISCC.exe"
        }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    return $null
}

function Test-HealthEndpoint {
    param([int]$Port)
    $request = [System.Net.HttpWebRequest]::Create("http://127.0.0.1:$Port/api/health")
    $request.Method = "GET"
    $request.Timeout = 1500
    $request.ReadWriteTimeout = 1500
    try {
        $response = $request.GetResponse()
        try {
            if ([int]$response.StatusCode -ne 200) {
                return $false
            }
            $reader = [IO.StreamReader]::new($response.GetResponseStream())
            try {
                $payload = $reader.ReadToEnd() | ConvertFrom-Json
                return $payload.status -eq "ok" -and $payload.product_id -eq "ndhi-labrecords"
            } finally {
                $reader.Dispose()
            }
        } finally {
            $response.Dispose()
        }
    } catch {
        return $false
    }
}

Write-Host "Checking Python and PyInstaller..."
Invoke-Python -Arguments @("-c", "import struct, sys; print(sys.version); print('x64' if struct.calcsize('P') == 8 else 'x86')")
$PythonArchitecture = (& $PythonCommand -c "import struct; print('x64' if struct.calcsize('P') == 8 else 'x86')").Trim()
if ($PythonArchitecture -ne $Architecture) {
    throw "Requested $Architecture build, but $PythonCommand is $PythonArchitecture. Use a matching Python interpreter."
}
& $PythonCommand -c "import PyInstaller; print('PyInstaller', PyInstaller.__version__)"
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller is not installed for $PythonCommand. Install tools\desktop\requirements-build.txt in the build environment before generating a package."
}

New-Item -ItemType Directory -Force -Path $BuildRoot | Out-Null
Remove-SafeBuildDirectory -Path $PackageDist
Remove-SafeBuildDirectory -Path $WorkDir
New-Item -ItemType Directory -Force -Path $PackageDist, $WorkDir, $InstallerOutput | Out-Null

Write-Host "Packaging NDHI Laboratory Records $Version ($Architecture)..."
Invoke-Python -Arguments @(
    "-m", "PyInstaller",
    "--noconfirm",
    "--clean",
    "--distpath", $PackageDist,
    "--workpath", $WorkDir,
    $SpecPath
)

$PackagedExe = Join-Path $PackageDist "NDHI-LabRecords\NDHI-LabRecords.exe"
if (-not (Test-Path -LiteralPath $PackagedExe -PathType Leaf)) {
    throw "Packaged executable was not created: $PackagedExe"
}

if (-not $SkipSmokeTest) {
    Write-Host "Running packaged local-server and verified-backup smoke test..."
    $SmokeRoot = Join-Path $BuildRoot ("smoke-" + [Guid]::NewGuid().ToString("N"))
    New-Item -ItemType Directory -Force -Path $SmokeRoot | Out-Null
    $SmokePort = 18114
    $Server = Start-Process -FilePath $PackagedExe -ArgumentList @("--serve", "--data-dir", $SmokeRoot, "--port", $SmokePort) -PassThru -WindowStyle Hidden
    try {
        $healthy = $false
        foreach ($attempt in 1..120) {
            if (Test-HealthEndpoint -Port $SmokePort) {
                $healthy = $true
                break
            }
            Start-Sleep -Milliseconds 750
        }
        if (-not $healthy) {
            throw "Packaged server did not become healthy."
        }
        $BackupProcess = Start-Process -FilePath $PackagedExe -ArgumentList @("--backup-now", "--data-dir", $SmokeRoot, "--reason", "build-smoke") -Wait -PassThru -WindowStyle Hidden
        if ($BackupProcess.ExitCode -ne 0) {
            throw "Packaged verified-backup smoke test failed."
        }
    } finally {
        if (-not $Server.HasExited) {
            Stop-Process -Id $Server.Id -Force
        }
        Wait-Process -Id $Server.Id -Timeout 10 -ErrorAction SilentlyContinue
        Remove-SafeBuildDirectory -Path $SmokeRoot
    }
}

if ($SkipInstaller) {
    Write-Host "Packaged app ready: $PackagedExe"
    exit 0
}

$Iscc = Find-Iscc
if (-not $Iscc) {
    throw "Inno Setup 6 compiler (ISCC.exe) was not found. Install Inno Setup 6, or rerun with -SkipInstaller to validate the packaged app first."
}

Write-Host "Compiling Windows installer..."
& $Iscc `
    "/DAppVersion=$Version" `
    "/DArchitecture=$Architecture" `
    "/DSourceDir=$(Split-Path -Parent $PackagedExe)" `
    "/DOutputDir=$InstallerOutput" `
    "/DIconFile=$IconFile" `
    $InstallerScript
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup compilation failed."
}

$InstallerPath = Join-Path $InstallerOutput "NDHI-LabRecords-Setup-$Version-$Architecture.exe"
if (-not (Test-Path -LiteralPath $InstallerPath -PathType Leaf)) {
    throw "Installer was not created: $InstallerPath"
}

Write-Host "Installer ready: $InstallerPath"
