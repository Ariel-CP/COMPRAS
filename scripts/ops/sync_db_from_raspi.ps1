# Script para sincronizar BD desde Raspberry
# Uso: .\scripts\ops\sync_db_from_raspi.ps1

$pythonExe = "$PSScriptRoot\..\..\\.venv\\Scripts\\python.exe"
$scriptPath = "$PSScriptRoot\sync_db_from_raspi.py"

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "  SINCRONIZAR BD LOCAL DESDE RASPBERRY (compras-dev)          " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan

# Verificar que Python existe
if (-not (Test-Path $pythonExe)) {
    Write-Host "✗ Error: No se encontró Python en .venv" -ForegroundColor Red
    Write-Host "  Ejecuta primero: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Ejecutar script Python
Write-Host ""
& $pythonExe $scriptPath

$exitCode = $LASTEXITCODE
if ($exitCode -eq 0) {
    Write-Host ""
    Write-Host "Sincronización exitosa" -ForegroundColor Green
} else {
    Write-Host ""
    Write-Host "Error durante sincronización (código: $exitCode)" -ForegroundColor Red
}

exit $exitCode
