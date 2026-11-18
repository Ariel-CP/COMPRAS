-- Certificados de proveedor por material/lote. Access permanece en solo lectura.
CREATE TABLE IF NOT EXISTS `recepcion_certificado_calidad` (
  `recepcion_linea_id` INT NOT NULL PRIMARY KEY,
  `recibido` TINYINT(1) NOT NULL DEFAULT 0,
  `usuario_id` BIGINT UNSIGNED NOT NULL,
  `fecha_actualizacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  CONSTRAINT `fk_certificado_linea` FOREIGN KEY (`recepcion_linea_id`)
    REFERENCES `recepcion_linea` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_certificado_usuario` FOREIGN KEY (`usuario_id`)
    REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS `recepcion_certificado_documento` (
  `id` BIGINT NOT NULL AUTO_INCREMENT PRIMARY KEY,
  `recepcion_linea_id` INT NOT NULL,
  `nombre` VARCHAR(255) NOT NULL,
  `tipo_mime` VARCHAR(100) NOT NULL,
  `tamano` INT UNSIGNED NOT NULL,
  `sha256` CHAR(64) NOT NULL,
  `contenido` MEDIUMBLOB NOT NULL,
  `usuario_id` BIGINT UNSIGNED NOT NULL,
  `fecha_creacion` TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  UNIQUE KEY `uk_certificado_documento_hash` (`recepcion_linea_id`, `sha256`),
  CONSTRAINT `fk_certificado_documento_linea` FOREIGN KEY (`recepcion_linea_id`)
    REFERENCES `recepcion_linea` (`id`) ON DELETE CASCADE,
  CONSTRAINT `fk_certificado_documento_usuario` FOREIGN KEY (`usuario_id`)
    REFERENCES `usuario` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
