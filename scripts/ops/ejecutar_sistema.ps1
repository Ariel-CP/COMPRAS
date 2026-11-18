$ErrorActionPreference = 'Stop'
$repoPath = Split-Path (Split-Path $PSScriptRoot -Parent) -Parent
$pythonPath = Join-Path $repoPath '.venv\Scripts\python.exe'
$logPath = Join-Path $repoPath 'outputs\runtime'
New-Item -ItemType Directory -Path $logPath -Force | Out-Null
Set-Location -LiteralPath $repoPath

# Una sola instancia del supervisor por usuario de Windows.
$mutex = New-Object System.Threading.Mutex($false, 'Local\ComprasApiSupervisor')
if (-not $mutex.WaitOne(0)) { exit 0 }
try {
    while ($true) {
        $listener = Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue
        if ($listener) {
            Start-Sleep -Seconds 15
            continue
        }
        $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
        $apiProcess = Start-Process -FilePath $pythonPath -ArgumentList @(
            '-m', 'uvicorn', 'app.main:app', '--host', '0.0.0.0', '--port', '8000'
        ) -WorkingDirectory $repoPath -WindowStyle Hidden -PassThru -RedirectStandardOutput (
            Join-Path $logPath "api-$stamp.out.log"
        ) -RedirectStandardError (Join-Path $logPath "api-$stamp.err.log")
        $apiProcess.WaitForExit()
        Start-Sleep -Seconds 10
    }
} finally {
    $mutex.ReleaseMutex()
    $mutex.Dispose()
}
