[CmdletBinding()]
param(
    [int]$Port = 8114,
    [string]$RuleName = "NDHI Laboratory Records LAN",
    [string]$ProgramPath = "$env:ProgramFiles\NDHI\LabRecords\NDHI-LabRecords.exe"
)

$ErrorActionPreference = "Stop"

$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = [Security.Principal.WindowsPrincipal]::new($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    throw "Run this script as Administrator so Windows Firewall can be updated."
}

$existingRule = Get-NetFirewallRule -DisplayName $RuleName -ErrorAction SilentlyContinue
if ($existingRule) {
    Remove-NetFirewallRule -DisplayName $RuleName
}

$rule = @{
    DisplayName = $RuleName
    Direction = "Inbound"
    Action = "Allow"
    Protocol = "TCP"
    LocalPort = $Port
    Profile = "Private", "Domain", "Public"
    RemoteAddress = "LocalSubnet"
    Description = "Allows trusted clinic LAN devices to open NDHI Laboratory Records on TCP port $Port."
}
if (Test-Path -LiteralPath $ProgramPath -PathType Leaf) {
    $rule.Program = $ProgramPath
}

New-NetFirewallRule @rule | Out-Null

Write-Host "Created LAN firewall rule: $RuleName on TCP port $Port for Private/Domain/Public local subnet networks."
