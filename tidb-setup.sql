-- ============================================
-- SongQueue - Setup TiDB Cloud
-- Copiar todo y ejecutar en TiDB Cloud → SQL Editor
-- ============================================

-- 1. Verificar permisos del usuario actual
SHOW GRANTS FOR CURRENT_USER();

-- 2. Crear usuario dedicado (si no existe)
CREATE USER IF NOT EXISTS 'songqueue'@'%' IDENTIFIED BY 'SongQueue2026!';

-- 3. Dar permisos completos solo en la BD songqueue
GRANT ALL PRIVILEGES ON songqueue.* TO 'songqueue'@'%';

-- 4. Aplicar cambios
FLUSH PRIVILEGES;

-- 5. Verificar que el usuario tiene permisos
SHOW GRANTS FOR 'songqueue'@'%';
