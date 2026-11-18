# Ejecutar como administrador. Solo permite TCP 8000 desde la subred local.
#Requires -RunAsAdministrator
$ErrorActionPreference = 'Stop'
$ruleName = 'Compras-API-LAN-8000'
$existing = Get-NetFirewallRule -Name $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    $existing | Remove-NetFirewallRule
}
New-NetFirewallRule -Name $ruleName -DisplayName 'Compras API - red local TCP 8000' `
    -Direction Inbound -Action Allow -Enabled True -Protocol TCP -LocalPort 8000 `
    -RemoteAddress LocalSubnet -Profile Any -EdgeTraversalPolicy Block | Out-Null
Get-NetFirewallRule -Name $ruleName | Select-Object Name, Enabled, Direction, Action
Get-NetFirewallRule -Name $ruleName | Get-NetFirewallAddressFilter |
    Select-Object RemoteAddress
