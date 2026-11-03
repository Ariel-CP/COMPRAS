-- Ampliar el correo de proveedor para listas ERP con múltiples destinatarios.
-- Cambio compatible: solo aumenta capacidad, no modifica filas existentes.
ALTER TABLE `proveedor`
  MODIFY COLUMN `email` VARCHAR(512) NULL;