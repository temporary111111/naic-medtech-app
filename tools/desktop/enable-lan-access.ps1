[CmdletBinding()]
param(
    [int]$Port = 8114,
    [string]$RuleName = "NDHI Laboratory Records LAN"
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
    Enable-NetFirewallRule -DisplayName $RuleName | Out-Null
    Write-Host "LAN firewall rule is already present and enabled: $RuleName"
    return
}

New-NetFirewallRule `
    -DisplayName $RuleName `
    -Direction Inbound `
    -Action Allow `
    -Protocol TCP `
    -LocalPort $Port `
    -Profile Private,Domain `
    -Description "Allows trusted clinic LAN devices to open NDHI Laboratory Records on TCP port $Port." |
    Out-Null

Write-Host "Created LAN firewall rule: $RuleName on TCP port $Port for Private/Domain networks."
