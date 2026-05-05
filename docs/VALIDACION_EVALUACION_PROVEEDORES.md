# Guía de Validación: Sistema de Evaluación de Proveedores

## Estado Actual
✅ Fases 1-5 COMPLETADAS
- BD: 5 tablas de recepción creadas
- API: 5 endpoints funcionales
- Servicios: Importación, normalización, cálculo de métricas

## Testing Rápido (sin datos reales de Access)

### Opción 1: Cargar datos de prueba directamente en BD

```sql
-- 1. Insertar data de prueba en recepcion_staging
INSERT INTO recepcion_staging (
  fila_hash, proveedor_codigo, proveedor_nombre, producto_codigo,
  producto_nombre, cantidad_solicitada, cantidad_recibida, 
  lote_numero, fecha_recepcion_original, calidad_ok, estado_procesamiento
) VALUES (
  SHA2('TEST-001', 256), 'PROV001', 'Proveedor Test', 'PROD001',
  'Producto Test', 100, 100, 'LOTE-2026-001', '2026-04-20', 1, 'PENDIENTE'
);

-- 2. Normalizar
POST /recepcion/normalizar-staging

-- 3. Calcular métricas
POST /recepcion/calcular-metricas?anno=2026&mes=04

-- 4. Consultar ranking
GET /recepcion/ranking?anno=2026&mes=04
```

### Opción 2: Usar archivo Access real

```bash
# Terminal
POST /recepcion/import-access?ruta_archivo=R:\\COMPARTIR-Calidad-ID\\...\\Control.accdb

# Luego normalizar y calcular
POST /recepcion/normalizar-staging
POST /recepcion/calcular-metricas?anno=2026&mes=04
GET /recepcion/ranking?anno=2026&mes=04
```

## Flujo Completo de Validación

### 1. Iniciar API
```bash
cd h:\COMPRAS
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

### 2. Abrir en navegador
```
http://localhost:8000/docs
```

### 3. Probar endpoints en orden:

#### 3a. POST `/recepcion/import-access`
- **Query params:**
  - `ruta_archivo`: Ruta completa al .accdb
  - Ejemplo: `R:\COMPARTIR-Calidad-ID\CALIDAD\...Control.accdb`
- **Response esperado:**
  ```json
  {
    "exitoso": true,
    "total_filas": N,
    "nuevas_insertadas": N,
    "duplicadas": 0,
    "errores": 0,
    "timestamp": "2026-04-28T..."
  }
  ```

#### 3b. POST `/recepcion/normalizar-staging`
- **Sin parámetros**
- **Response esperado:**
  ```json
  {
    "exitoso": true,
    "total_procesadas": N,
    "exitosas": N,
    "rechazadas": 0,
    "timestamp": "2026-04-28T..."
  }
  ```

#### 3c. POST `/recepcion/calcular-metricas`
- **Query params:**
  - `anno`: 2026
  - `mes`: 4 (o mes actual)
- **Response esperado:**
  ```json
  {
    "exitoso": true,
    "total_proveedores": N,
    "calculadas": N,
    "errores": 0,
    "timestamp": "2026-04-28T..."
  }
  ```

#### 3d. GET `/recepcion/ranking`
- **Query params:**
  - `anno`: 2026
  - `mes`: 4
- **Response esperado:**
  ```json
  [
    {
      "proveedor_id": 1,
      "proveedor_nombre": "Nombre Proveedor",
      "puntaje_general": 8.5,
      "puntaje_calidad": 9.0,
      "puntaje_cumplimiento": 8.0,
      "puntaje_respuesta_nc": 8.5,
      "en_riesgo": 0,
      "razon_riesgo": null,
      "anno": 2026,
      "mes": 4
    }
  ]
  ```

#### 3e. GET `/recepcion/evaluar/{proveedor_id}`
- **Path param:**
  - `proveedor_id`: 1 (o ID real de proveedor)
- **Query params:**
  - `anno`: 2026 (opcional)
  - `mes`: 4 (opcional)
- **Response esperado:** Array de métricas históricas

## Validaciones Críticas

### ✅ Idempotencia
Importar 2 veces el mismo archivo Access → debe dar duplicadas=N, nuevas_insertadas=0

### ✅ Trazabilidad
Verificar en BD que staging crudo se conserva (auditoría)

### ✅ Integridad referencial
Validar que solo se procesan filas con proveedor/producto válidos

### ✅ Recalcular sin reimportar
Cambiar peso en parametro_sistema → recalcular métricas → scores deben variar

## Archivos Clave

| Archivo | Tipo | Descripción |
|---------|------|-------------|
| `database/migrations/010_*` | SQL | Tablas staging, parámetros |
| `database/migrations/011_*` | SQL | Tablas canónicas, métricas |
| `app/services/recepcion_access_import_service.py` | Python | Lectura Access |
| `app/services/recepcion_normalization_service.py` | Python | Normalización |
| `app/services/recepcion_metrics_service.py` | Python | Cálculo KPIs |
| `app/api/recepcion_api.py` | Python | Endpoints |
| `app/schemas/recepcion.py` | Python | Modelos Pydantic |
| `app/api/router.py` | Python | Integración |
| `requirements.txt` | Deps | pyodbc agregado |

## Errores Esperados y Soluciones

### "File not found" en import-access
- Verificar ruta absoluta correcta
- Usar formato UNC si es red: `\\servidor\compartir\archivo.accdb`

### "Unknown proveedor" en normalización
- Proveedor no existe en tabla `proveedor`
- Importar maestro de proveedores primero

### "foreign key constraint failed"
- BD no tiene integridad referencial habilitada
- Verificar estructura en verificar_tablas.py

## Próximas Fases

**Fase 6 (v2):** UI con ranking y drill-down por proveedor
**Fase 7 (v2):** Automatización y gobernanza de datos
