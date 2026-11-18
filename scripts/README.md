# Scripts del proyecto

Esta carpeta esta separada por uso para evitar confusiones:

- `scripts/ops`: scripts operativos o de administracion (seed, sync, deploy, migracion).
- `scripts/dev`: scripts de debug, inspeccion y pruebas manuales locales.

## Regla de uso

1. Si un script se ejecuta en entornos productivos o de mantenimiento controlado, va a `ops`.
2. Si es para diagnostico local, pruebas puntuales o exploracion, va a `dev`.
3. Evitar referenciar rutas absolutas en scripts nuevos.

## Inicio permanente en Windows

Ejecutar `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ops/configurar_inicio_windows.ps1`
desde la cuenta habitual de Windows del proyecto. Instala e inicia la tarea `Compras API`,
sin pedir ni guardar contraseñas. Al iniciar sesión arranca el supervisor
`scripts/ops/ejecutar_sistema.ps1`, que ejecuta uvicorn sin reload y vuelve a iniciarlo
si termina. La tarea no tiene límite de duración y Windows reintenta si falla el supervisor.
Usa el puerto 8000; si está ocupado, espera sin detener otros procesos.

Acceso local: `http://localhost:8000`. Logs por arranque: `outputs/runtime/api-*.log`.
Ver estado con `Get-ScheduledTask -TaskName 'Compras API'` y salud en `/health`.
Reejecutar el instalador actualiza la misma tarea. Requiere el equipo encendido,
sin suspensión y la sesión del usuario abierta; no arranca antes del inicio de sesión.
No reemplaza la configuración de firewall para acceso desde otras computadoras.

### Acceso desde la red local

Ejecutar `scripts/ops/habilitar_red_local.ps1` en PowerShell como administrador.
La regla `Compras-API-LAN-8000` permite TCP 8000 entrante únicamente desde
`LocalSubnet`, sin cambiar el perfil de red ni desactivar el firewall.
Desde otra PC usar `http://<IP-del-servidor>:8000` (IP verificada el 18/11/2026:
`192.168.2.70`). El servidor ya escucha en `0.0.0.0`. Para diagnosticar desde
el cliente: `Test-NetConnection 192.168.2.70 -Port 8000`.
La IP puede cambiar si DHCP no tiene reserva; reservarla en el router/servidor
DHCP corresponde al administrador de la red. Para retirar el permiso:
`Remove-NetFirewallRule -Name Compras-API-LAN-8000` como administrador.

## Nota

Si tenias comandos guardados con rutas anteriores (por ejemplo `scripts/seed_admin.py`), actualizalos a la nueva ubicacion (`scripts/ops/seed_admin.py` o `scripts/dev/...`).
