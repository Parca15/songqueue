#!/bin/sh
set -e

echo "Ejecutando migraciones..."
alembic upgrade head

echo "Iniciando aplicacion..."
exec "$@"
