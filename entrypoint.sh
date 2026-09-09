#!/bin/sh
set -e

echo "Ejecutando migraciones..."
if alembic upgrade head 2>&1; then
    echo "Migraciones completadas."
else
    echo "⚠ Migraciones fallaron (verifica permisos en la BD). La app iniciará de todas formas."
fi

echo "Iniciando aplicacion..."
exec "$@"
