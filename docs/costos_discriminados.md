# Implementación de Costos Discriminados en MBOM

## Resumen
Sistema que discrimina costos de **Materiales** y **Procesos** en la estructura de MBOM.

## Cambios Realizados

### 1. Base de Datos
**Tabla `operacion`** - Nuevas columnas:
- `costo_hora` DECIMAL(18,6) - Costo por hora de la operación
- `moneda` ENUM('ARS','USD','USD_MAY','EUR') - Moneda del costo
- Índice en `centro_trabajo` para optimizar consultas

**Migración:** `database/migrations/001_add_costos_operacion.sql`

### 2. Backend

#### Servicios Creados
- **`app/services/operacion_service.py`**
  - CRUD completo de operaciones
  - Funciones: `listar_operaciones`, `crear_operacion`, `actualizar_operacion`, `eliminar_operacion`

- **`app/services/mbom_operacion_service.py`**
  - Gestión de ruta de operaciones por MBOM
  - Funciones: `listar_operaciones_mbom`, `agregar_operacion_mbom`, `eliminar_operacion_mbom`

- **`app/services/mbom_costos.py`** (Actualizado)
  - Nueva función `calcular_costos_completos()` que retorna estructura discriminada
  - `_calcular_costos_materiales()` - Cálculo de componentes (ya existía)
  - `_calcular_costos_procesos()` - **NUEVO** - Cálculo de operaciones

#### APIs Creadas
- **`app/api/operacion_api.py`**
  - `GET /api/operaciones/` - Listar operaciones
  - `POST /api/operaciones/` - Crear operación
  - `PUT /api/operaciones/{id}` - Actualizar operación
  - `DELETE /api/operaciones/{id}` - Eliminar operación

- **`app/api/mbom_api.py`** (Actualizado)
  - `GET /api/mbom/{mbom_id}/operaciones` - Ruta de operaciones del MBOM
  - `POST /api/mbom/{mbom_id}/operaciones` - Agregar operación a la ruta
  - `DELETE /api/mbom/operaciones/{id}` - Quitar operación
  - `GET /api/mbom/{id}/costos` - **ACTUALIZADO** para retornar estructura discriminada

### 3. Frontend

#### Estructura del Panel de Costos
**Tabs:**
- **Materiales**: Tabla de componentes con costos
- **Procesos**: Tabla de operaciones con tiempos y costos
- **Total**: Vista consolidada con desglose porcentual

#### Funciones JavaScript Actualizadas
- `cargarCostos()` - Carga discriminada de materiales y procesos
- `renderCostosMateriales()` - Renderiza tabla de materiales
- `renderCostosProcesos()` - Renderiza tabla de operaciones
- `renderCostosTotal()` - Renderiza vista consolidada
- `renderResumen()` - Actualiza línea de resumen
- `activarTabCostos()` - Cambia entre tabs

## Estructura de Datos

### Endpoint `/api/mbom/{id}/costos`

**Response:**
```json
{
  "materiales": {
    "componentes": [
      {
        "codigo": "40123",
        "nombre": "Material X",
        "cantidad": 10,
        "um_codigo": "KG",
        "costo_unitario": 5.50,
        "costo_total": 55.00,
        "moneda": "ARS"
      }
    ],
    "total": 155.00
  },
  "procesos": {
    "operaciones": [
      {
        "secuencia": 10,
        "codigo": "CORTE",
        "nombre": "Corte Manual",
        "tiempo_min": 15,
        "costo_hora": 2500,
        "subtotal": 625.00,
        "moneda": "ARS"
      }
    ],
    "total": 625.00
  },
  "total": 780.00,
  "desglose": {
    "materiales_pct": 19.9,
    "procesos_pct": 80.1
  }
}
```

## Próximos Pasos

### Fase Pendiente: UI de Gestión de Operaciones
1. Crear panel "Ruta de Operaciones" en `estructura.html`
2. Permitir agregar/quitar operaciones a la secuencia del MBOM
3. Vincular componentes a operaciones específicas (campo `operacion_secuencia` en `mbom_detalle`)

### Mejoras Sugeridas
- Importar operaciones desde Flexxus
- Historial de costos por operación (tabla `costo_operacion`)
- Cálculo de capacidad basado en tiempos estándar
- Reportes de eficiencia (tiempo real vs. estándar)

## Testing

### Verificar Migración
```sql
SELECT * FROM operacion LIMIT 5;
```

### Insertar Operación de Prueba
```sql
INSERT INTO operacion (codigo, nombre, centro_trabajo, tiempo_estandar_minutos, costo_hora, moneda)
VALUES ('CORTE01', 'Corte Manual', 'TALLER-A', 15, 2500, 'ARS');
```

### Probar Endpoint de Costos
```bash
curl http://localhost:8001/api/mbom/1/costos
```

## Archivos Modificados
- ✅ `database/migrations/001_add_costos_operacion.sql` (creado)
- ✅ `app/core/config.py` (credenciales BD actualizadas)
- ✅ `app/services/operacion_service.py` (creado)
- ✅ `app/services/mbom_operacion_service.py` (creado)
- ✅ `app/services/mbom_costos.py` (actualizado)
- ✅ `app/api/operacion_api.py` (creado)
- ✅ `app/api/mbom_api.py` (actualizado)
- ✅ `app/main.py` (router de operaciones registrado)
- ✅ `app/templates/mbom/estructura.html` (panel de costos con tabs)
