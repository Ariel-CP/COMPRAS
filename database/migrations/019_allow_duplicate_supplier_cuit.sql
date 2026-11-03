-- CUIT no identifica de forma única los códigos de proveedor del ERP.
-- Mantener la búsqueda indexada, permitiendo CUIT compartidos.
ALTER TABLE `proveedor`
  DROP INDEX `cuit`;