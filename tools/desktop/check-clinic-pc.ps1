[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

function Find-EdgeExecutable {
    $candidates = @()
    foreach ($root in @(${env:ProgramFiles(x86)}, $env:ProgramFiles, $env:LOCALAPPDATA)) {
        if ($root) {
            $candidates += Join-Path $root "Microsoft\Edge\Application\msedge.exe"
        }
    }
    foreach ($candidate in $candidates) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) {
            return $candidate
        }
    }
    $edge = Get-Command "msedge.exe" -ErrorAction SilentlyContinue
    return if ($edge) { $edge.Source } else { $null }
}

$os = Get-CimInstance Win32_OperatingSystem
$systemDrive = Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='$($env:SystemDrive)'"
$edgePath = Find-EdgeExecutable
$is64BitOs = [Environment]::Is64BitOperatingSystem
$architecture = if ($is64BitOs) { "x64" } else { "x86" }
$windowsMajorVersion = [Environment]::OSVersion.Version.Major
$windowsBuild = [Environment]::OSVersion.Version.Build
$isSupportedWindows = $windowsMajorVersion -ge 10
$freeDiskGb = if ($systemDrive) { [Math]::Round($systemDrive.FreeSpace / 1GB, 1) } else { 0 }
$hasEnoughDisk = $freeDiskGb -ge 2
$edgeAvailable = [bool]$edgePath
$status = if ($isSupportedWindows -and $hasEnoughDisk -and $edgeAvailable) { "Compatible" } else { "Needs attention" }

[PSCustomObject]@{
    Product                = "NDHI Laboratory Records"
    Computer               = $env:COMPUTERNAME
    OS                     = $os.Caption
    OSVersion              = $os.Version
    WindowsBuild           = $windowsBuild
    Architecture           = $architecture
    RecommendedInstaller   = $architecture
    PowerShell             = $PSVersionTable.PSVersion.ToString()
    Edge                   = if ($edgeAvailable) { "Installed" } else { "Not found (browser fallback only)" }
    EdgePath               = $edgePath
    SystemDriveFreeGB      = $freeDiskGb
    Status                 = $status
} | Format-List

if (-not $isSupportedWindows) {
    Write-Warning "Windows 10 or newer is required."
}
if (-not $edgeAvailable) {
    Write-Warning "Microsoft Edge was not found. The launcher can fall back to the default browser, but the dedicated app window should be repaired before clinic deployment."
}
if (-not $hasEnoughDisk) {
    Write-Warning "At least 2 GB free disk space is required before installation."
}
if ($os.Caption -match "Windows 10") {
    Write-Warning "Windows 10 compatibility is possible, but the clinic PC should be upgraded because Microsoft support ended on 2025-10-14."
}

exit $(if ($status -eq "Compatible") { 0 } else { 2 })
