param(
    [Parameter(Mandatory = $true)]
    [Alias("Host")]
    [string]$TargetHost,

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

$repoRoot = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
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
    "VERSION",
    "scripts/ops/install_raspberry.sh",
    "scripts/ops/update.sh"
)

if ($IncludeDatabase) {
    $items += "database"
}

Push-Location $repoRoot
try {
    tar -czf $archivePath @items
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo al generar el paquete de deploy con tar."
    }
}
finally {
    Pop-Location
}

$remote = "$User@$TargetHost"

Write-Host "Subiendo paquete a $remote ..."
scp $archivePath "$remote`:$RemotePath/compras-deploy.tar.gz"
if ($LASTEXITCODE -ne 0) {
    throw "Fallo la copia del paquete por SCP."
}

Write-Host "Desplegando archivos y reiniciando servicio ..."
$remoteDeployCmd = @'
set -e
mkdir -p __REMOTE_PATH__
tar -xzf __REMOTE_PATH__/compras-deploy.tar.gz -C __REMOTE_PATH__
chmod +x __REMOTE_PATH__/scripts/ops/install_raspberry.sh
sudo systemctl restart compras-api
sudo systemctl is-active compras-api
code='000'
for i in $(seq 1 20); do
  code=$(curl -s -o /dev/null -w '%{http_code}' http://127.0.0.1:8000/ui/login || true)
  if [ "$code" = "200" ]; then
    break
  fi
  sleep 1
done
echo "$code"
[ "$code" = "200" ]
'@
$remoteDeployCmd = $remoteDeployCmd.Replace("__REMOTE_PATH__", $RemotePath)
$remoteDeployCmd = $remoteDeployCmd.Replace("`r", "")
ssh $remote $remoteDeployCmd
if ($LASTEXITCODE -ne 0) {
    throw "Fallo el despliegue remoto por SSH."
}

if ($RunInstaller) {
    Write-Host "Ejecutando instalador remoto ..."
    ssh $remote "cd $RemotePath; chmod +x scripts/ops/install_raspberry.sh; ./scripts/ops/install_raspberry.sh"
    if ($LASTEXITCODE -ne 0) {
        throw "Fallo la ejecución remota del instalador."
    }
}

Write-Host "Deploy finalizado."
