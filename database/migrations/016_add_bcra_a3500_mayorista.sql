-- Migracion: agregar serie BCRA A3500 mayorista
-- Fecha: 2026-09-09
-- No elimina ni modifica registros minoristas ni historicos USD_MAY/VENTA.

ALTER TABLE `tipo_cambio_hist`
  MODIFY COLUMN `tipo` enum('COMPRA','VENTA','PROMEDIO','MAYORISTA') NOT NULL DEFAULT 'PROMEDIO',
  MODIFY COLUMN `origen` enum('ERP_FLEXXUS','MANUAL','OTRO','BCRA_A3500') NOT NULL DEFAULT 'MANUAL';
