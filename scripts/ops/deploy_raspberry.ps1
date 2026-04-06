param(
    [Parameter(Mandatory = $true)]
    [string]$Host,

    [string]$User = "acepeda",

    [string]$RemotePath = "~/COMPRAS",

    [switch]$IncludeDatabase,

    [switch]$RunInstaller
)

$ErrorActionPreference = "Stop"

function Require-Command {
    param([string]$Name)

    if (-not (Get-Command $Name -ErrorAction SilentlyContinue)) {
        throw "Falta comando requerido: $Name"
    }
}

Require-Command ssh
Require-Command scp
Require-Command tar

$repoRoot = Split-Path -Parent $PSScriptRoot
$stageDir = Join-Path $repoRoot ".deploy"
$archivePath = Join-Path $stageDir "compras-deploy.tar.gz"

if (Test-Path $stageDir) {
    Remove-Item -Recurse -Force $stageDir
}

New-Item -ItemType Directory -Path $stageDir | Out-Null

$items = @(
    "app",
    "requirements.txt",
    "requirements-dev.txt",
    "scripts/install_raspberry.sh"
)

if ($IncludeDatabase) {
    $items += "database"
}

Push-Location $repoRoot
try {
    tar -czf $archivePath @items
}
finally {
    Pop-Location
}

$remote = "$User@$Host"

Write-Host "Subiendo paquete a $remote ..."
scp $archivePath "$remote`:$RemotePath/compras-deploy.tar.gz"

Write-Host "Desplegando archivos y reiniciando servicio ..."
ssh $remote "set -e; mkdir -p $RemotePath; tar -xzf $RemotePath/compras-deploy.tar.gz -C $RemotePath; chmod +x $RemotePath/scripts/install_raspberry.sh; sudo systemctl restart compras-api; sudo systemctl is-active compras-api; curl -s -o /dev/null -w '%{http_code}`n' http://127.0.0.1:8000/ui/login"

if ($RunInstaller) {
    Write-Host "Ejecutando instalador remoto ..."
    ssh $remote "cd $RemotePath; chmod +x scripts/install_raspberry.sh; ./scripts/install_raspberry.sh"
}

Write-Host "Deploy finalizado."
