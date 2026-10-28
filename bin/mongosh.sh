#!/usr/bin/env bash
# Ejecuta mongosh dentro del contenedor, autenticado y sobre la base del proyecto.
#   bin/mongosh.sh                         -> consola interactiva
#   bin/mongosh.sh /scripts/04_consultas.js -> ejecuta un script de db/scripts
set -euo pipefail
cd "$(dirname "$0")/.."

# En Git Bash (Windows), evita que "/scripts/..." se convierta en "C:/Program Files/Git/scripts/...".
export MSYS_NO_PATHCONV=1

tty_flag="-T"
if [ $# -eq 0 ] && [ -t 0 ]; then tty_flag=""; fi

docker compose exec $tty_flag mongo sh -c \
  'mongosh --quiet -u "$MONGO_INITDB_ROOT_USERNAME" -p "$MONGO_INITDB_ROOT_PASSWORD" --authenticationDatabase admin "$MONGO_DB" "$@"' \
  -- "$@"
