#!/usr/bin/env bash
# Reinicializa la base desde cero: borra la base, crea las colecciones con sus
# validaciones, carga los datos de prueba, crea los índices y verifica la carga.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "Falta el archivo .env (copiar .env.example a .env)" >&2
  exit 1
fi

echo "==> Levantando MongoDB"
docker compose up -d --wait mongo

echo "==> Creando colecciones y validaciones"
bin/mongosh.sh /scripts/01_colecciones.js

echo "==> Cargando datos de prueba"
docker compose run --rm seed

echo "==> Creando índices"
bin/mongosh.sh /scripts/02_indices.js

echo "==> Verificando la carga"
bin/mongosh.sh /scripts/03_verificacion.js
