-- Migration: solicitado previo para LAF (anticipacion y balanceo quincenal)

CREATE TABLE IF NOT EXISTS asistente_oc_laf_solicitado (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  anio SMALLINT NOT NULL,
  mes TINYINT NOT NULL,
  producto_id BIGINT UNSIGNED NOT NULL,
  proveedor_nombre VARCHAR(160) NOT NULL,
  cantidad_total DECIMAL(18,6) NOT NULL DEFAULT 0,
  cantidad_q1 DECIMAL(18,6) NOT NULL DEFAULT 0,
  cantidad_q2 DECIMAL(18,6) NOT NULL DEFAULT 0,
  fecha_pedido DATE NULL,
  fecha_entrega_estimada DATE NULL,
  estado ENUM('PENDIENTE','PARCIAL','RECIBIDO','CANCELADO') NOT NULL DEFAULT 'PENDIENTE',
  observaciones VARCHAR(255) NULL,
  fecha_creacion TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
  fecha_actualizacion TIMESTAMP NULL DEFAULT NULL ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  KEY idx_asis_oc_laf_periodo (anio, mes),
  KEY idx_asis_oc_laf_producto (producto_id),
  CONSTRAINT fk_asis_oc_laf_producto FOREIGN KEY (producto_id)
    REFERENCES producto(id) ON DELETE RESTRICT
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
