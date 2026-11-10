-- Registro append-only de inspecciones originales y reinspecciones.
-- Los valores del plan se registran como evidencia; esta migración no implementa reglas IRAM.

CREATE TABLE IF NOT EXISTS `recepcion_inspeccion_intento` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `recepcion_linea_id` INT NOT NULL,
  `numero_intento` SMALLINT UNSIGNED NOT NULL,
  `tipo_intento` ENUM('INICIAL', 'REINSPECCION') NOT NULL,
  `intento_anterior_id` BIGINT NULL,
  `nivel_inspeccion` VARCHAR(30) NULL,
  `tamano_muestra_planificado` INT NULL,
  `unidades_inspeccionadas` INT NOT NULL,
  `unidades_no_conformes` INT NOT NULL,
  `decision` ENUM('ACEPTADO', 'RECHAZADO', 'PENDIENTE') NOT NULL,
  `referencia_normativa` VARCHAR(100) NULL,
  `inspector_id` BIGINT UNSIGNED NULL,
  `fecha_inspeccion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_recepcion_intento_numero` (`recepcion_linea_id`, `numero_intento`),
  KEY `idx_recepcion_intento_anterior` (`intento_anterior_id`),
  KEY `idx_recepcion_intento_fecha` (`fecha_inspeccion`),
  CONSTRAINT `fk_recepcion_intento_linea`
    FOREIGN KEY (`recepcion_linea_id`) REFERENCES `recepcion_linea` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_recepcion_intento_anterior`
    FOREIGN KEY (`intento_anterior_id`) REFERENCES `recepcion_inspeccion_intento` (`id`),
  CONSTRAINT `fk_recepcion_intento_inspector`
    FOREIGN KEY (`inspector_id`) REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Historial inmutable de intentos de inspección por línea de recepción';

ALTER TABLE `recepcion_inspeccion`
  ADD COLUMN `intento_id` BIGINT NULL,
  ADD KEY `idx_recepcion_inspeccion_intento` (`intento_id`),
  ADD CONSTRAINT `fk_recepcion_inspeccion_intento`
    FOREIGN KEY (`intento_id`) REFERENCES `recepcion_inspeccion_intento` (`id`);