$ErrorActionPreference = 'Stop'
$repoPath = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$runnerPath = Join-Path $PSScriptRoot 'ejecutar_sistema.ps1'
$userName = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument (
    '-NoProfile -NonInteractive -WindowStyle Hidden -ExecutionPolicy Bypass -File "' + $runnerPath + '"'
) -WorkingDirectory $repoPath
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $userName
$principal = New-ScheduledTaskPrincipal -UserId $userName -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
    -StartWhenAvailable -ExecutionTimeLimit ([TimeSpan]::Zero) -MultipleInstances IgnoreNew `
    -RestartCount 999 -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName 'Compras API' -Action $action -Trigger $trigger `
    -Principal $principal -Settings $settings -Description (
        'Sistema Compras: API en puerto 8000 con supervisor y arranque al iniciar sesion.'
    ) -Force | Out-Null
Start-ScheduledTask -TaskName 'Compras API'
Write-Output 'Tarea Compras API instalada e iniciada.'
