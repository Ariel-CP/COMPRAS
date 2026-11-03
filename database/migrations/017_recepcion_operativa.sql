-- Datos operativos del formulario Control de Recepción.
-- Access permanece como fuente histórica de solo lectura.

ALTER TABLE `recepcion_cabecera`
  ADD COLUMN `orden_compra` VARCHAR(50) NULL AFTER `proveedor_id`,
  ADD COLUMN `remito` VARCHAR(100) NULL AFTER `orden_compra`,
  ADD COLUMN `fecha_control` DATE NULL AFTER `fecha_entrega_esperada`,
  ADD COLUMN `terminacion_superficial` DECIMAL(5,2) NULL,
  ADD COLUMN `control_dimensional` DECIMAL(5,2) NULL,
  ADD COLUMN `embalaje` DECIMAL(5,2) NULL;

ALTER TABLE `recepcion_linea`
  ADD COLUMN `numero_plano` VARCHAR(50) NULL AFTER `producto_id`,
  ADD COLUMN `designacion` VARCHAR(255) NULL AFTER `numero_plano`,
  ADD COLUMN `cantidad_lote` DECIMAL(15,4) NULL AFTER `cantidad_recibida`,
  ADD COLUMN `nivel_inspeccion` VARCHAR(30) NULL,
  ADD COLUMN `tamano_muestra` INT NULL,
  ADD COLUMN `porcentaje_muestreo` DECIMAL(6,3) NULL,
  ADD COLUMN `material_utilizado` VARCHAR(255) NULL;

ALTER TABLE `recepcion_inspeccion`
  ADD COLUMN `desviacion` TEXT NULL AFTER `valor_medido`;