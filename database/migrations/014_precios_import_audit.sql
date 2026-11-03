-- Migracion 014: Auditoria de importacion y cambios de precios
-- Fecha: 2026-05-29

CREATE TABLE IF NOT EXISTS `precio_compra_import_lote` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `archivo_nombre` VARCHAR(255) DEFAULT NULL,
  `archivo_hash` CHAR(64) DEFAULT NULL,
  `formato` ENUM('CSV', 'XLSX') NOT NULL,
  `fecha_inicio` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `fecha_fin` TIMESTAMP NULL DEFAULT NULL,
  `usuario_id` BIGINT DEFAULT NULL,
  `total_registros` INT NOT NULL DEFAULT 0,
  `insertados` INT NOT NULL DEFAULT 0,
  `actualizados` INT NOT NULL DEFAULT 0,
  `rechazados` INT NOT NULL DEFAULT 0,
  `estado` ENUM('EXITOSA', 'PARCIAL', 'ERROR') NOT NULL DEFAULT 'ERROR',
  `mensaje_error` TEXT,
  KEY `idx_precio_lote_inicio` (`fecha_inicio`),
  KEY `idx_precio_lote_estado` (`estado`),
  KEY `idx_precio_lote_hash` (`archivo_hash`),
  KEY `idx_precio_lote_usuario` (`usuario_id`),
  CONSTRAINT `fk_precio_lote_usuario`
    FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Bitacora por lote de importacion de precios';

CREATE TABLE IF NOT EXISTS `precio_compra_hist_audit` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `precio_compra_hist_id` BIGINT NOT NULL,
  `import_lote_id` BIGINT DEFAULT NULL,
  `usuario_id` BIGINT DEFAULT NULL,
  `operacion` ENUM('INSERT', 'UPDATE') NOT NULL,
  `origen_cambio` ENUM('IMPORT', 'MANUAL') NOT NULL,
  `producto_id` BIGINT NOT NULL,
  `proveedor_codigo` VARCHAR(64) NOT NULL,
  `fecha_precio` DATE NOT NULL,
  `moneda` ENUM('ARS', 'USD', 'USD_MAY', 'EUR') NOT NULL,
  `valores_anteriores` LONGTEXT DEFAULT NULL,
  `valores_nuevos` LONGTEXT NOT NULL,
  `fecha_evento` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  KEY `idx_precio_audit_evento` (`fecha_evento`),
  KEY `idx_precio_audit_producto_fecha` (`producto_id`, `fecha_precio`),
  KEY `idx_precio_audit_lote` (`import_lote_id`),
  KEY `idx_precio_audit_usuario` (`usuario_id`),
  CONSTRAINT `fk_precio_audit_precio_hist`
    FOREIGN KEY (`precio_compra_hist_id`) REFERENCES `precio_compra_hist` (`id`)
    ON DELETE CASCADE,
  CONSTRAINT `fk_precio_audit_lote`
    FOREIGN KEY (`import_lote_id`) REFERENCES `precio_compra_import_lote` (`id`)
    ON DELETE SET NULL,
  CONSTRAINT `fk_precio_audit_usuario`
    FOREIGN KEY (`usuario_id`) REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
COMMENT='Auditoria de cambios por registro en precio_compra_hist';

ALTER TABLE `precio_compra_hist`
  ADD COLUMN IF NOT EXISTS `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS `fecha_actualizacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
    ON UPDATE CURRENT_TIMESTAMP;
