#!/usr/bin/env bash
# Demo guiada para la presentación.
# Cada paso muestra el comando, lo ejecuta y espera un Enter antes de seguir,
# para poder explicar mientras se ve el resultado.
#
# Uso (Mac: Terminal · Windows: Git Bash), desde cualquier carpeta:
#   docs/PRESENTACION/demo/demo_en_vivo.sh
# Para correrla de corrido, sin pausas:
#   DEMO_SIN_PAUSAS=1 docs/PRESENTACION/demo/demo_en_vivo.sh
set -uo pipefail
cd "$(dirname "$0")/../../.."
export MSYS_NO_PATHCONV=1  # Git Bash: no convertir rutas como /scripts/...

API_PORT=$(grep -E '^API_PORT=' .env 2>/dev/null | cut -d= -f2)
JUPYTER_PORT=$(grep -E '^JUPYTER_PORT=' .env 2>/dev/null | cut -d= -f2)
API="http://localhost:${API_PORT:-8000}"
JUPYTER="http://localhost:${JUPYTER_PORT:-8888}"
OFERTA="6aacc5503c4722f3c1b4fd44"  # Desarrollador/a Mobile Sr · Brújula Fintech: 1 vacante, 9 postulantes activos
RESPUESTA=$(mktemp)
trap 'rm -f "$RESPUESTA"' EXIT

AZUL=$'\e[1;34m'; VERDE=$'\e[1;32m'; AMARILLO=$'\e[1;33m'; GRIS=$'\e[0;90m'; NORMAL=$'\e[0m'

paso() { printf '\n%s══════════════════════════════════════════════════════════════════════%s\n' "$AZUL" "$NORMAL"
         printf '%s %s%s\n' "$AZUL" "$1" "$NORMAL"
         [ $# -gt 1 ] && printf '%s %s%s\n' "$GRIS" "$2" "$NORMAL"
         printf '%s══════════════════════════════════════════════════════════════════════%s\n' "$AZUL" "$NORMAL"; }
comando() { printf '%s$ %s%s\n' "$AMARILLO" "$1" "$NORMAL"; }
nota() { printf '%s→ %s%s\n' "$VERDE" "$1" "$NORMAL"; }
pausa() { [ -n "${DEMO_SIN_PAUSAS:-}" ] && return; read -rp $'\n'"${GRIS}[Enter para seguir]${NORMAL} " _; }
mongo() { bin/mongosh.sh --eval "$1"; }
# Formatea JSON con el Python del contenedor de la API (no hace falta Python en la computadora).
py() { docker compose exec -T api python -c "import sys, json; d = json.load(sys.stdin); $1"; }
pedir() {  # pedir MÉTODO RUTA [CUERPO] -> deja la respuesta en $RESPUESTA y el código en $CODIGO
  if [ $# -gt 2 ]; then
    CODIGO=$(curl -s -o "$RESPUESTA" -w '%{http_code}' -X "$1" "$API$2" -H 'Content-Type: application/json' -d "$3")
  else
    CODIGO=$(curl -s -o "$RESPUESTA" -w '%{http_code}' -X "$1" "$API$2")
  fi
}
abrir() { case "$(uname -s)" in
            Darwin) open "$1" ;;
            MINGW*|MSYS*|CYGWIN*) start "" "$1" ;;
            *) xdg-open "$1" >/dev/null 2>&1 || true ;;
          esac; }

# ------------------------------------------------------------------ preparación
paso "Preparación" "Base en su estado original y API levantada (tarda unos segundos)"
if [ ! -f .env ]; then echo "Falta el archivo .env: ver docs/instrucciones.md, sección 3.1"; exit 1; fi
if ! docker info >/dev/null 2>&1; then echo "Docker Desktop no está abierto"; exit 1; fi
comando "bin/reset_db.sh"
bin/reset_db.sh 2>&1 | grep -E "^==>|Verificación" || { echo "Falló la carga de la base"; exit 1; }
comando "docker compose up -d --build --wait api"
docker compose up -d --build --wait api >/dev/null 2>&1 || { echo "No se pudo levantar la API"; exit 1; }
pedir GET /salud; nota "API en $API → $(cat "$RESPUESTA")"
pausa

# ------------------------------------------------------------------ 1. modelo
paso "1. Modelo documental" "Un perfil completo es un solo documento, con sus arreglos embebidos"
comando "db.usuarios.findOne({ certificaciones: { \$exists: true }, \"experiencia.1\": { \$exists: true } })"
mongo 'printjson(db.usuarios.findOne({ certificaciones: { $exists: true }, "experiencia.1": { $exists: true } }, { creadoEn: 0, actualizadoEn: 0 }))'
pausa
comando "db.postulaciones.findOne({ estado: \"aceptada\" })   // historial de estados embebido"
mongo 'printjson(db.postulaciones.findOne({ estado: "aceptada" }, { cartaPresentacion: 0 }))'
nota "usuarioId y ofertaId son referencias; historialEstados está embebido"
pausa

# ------------------------------------------------------------------ 2. validación
paso "2. Validación en la base" "El validador \$jsonSchema rechaza un documento inválido"
comando "db.ofertas.insertOne({ ..., vacantes: { total: 1, disponibles: 3 } })"
mongo '
const e = db.empresas.findOne();
try {
  db.ofertas.insertOne({ empresa: { empresaId: e._id, nombre: e.nombre }, titulo: "Demo", descripcion: "Demo",
    seniority: "junior", modalidad: "remoto", skillsRequeridas: ["python"], vacantes: { total: 1, disponibles: 3 },
    estado: "abierta", cantidadPostulaciones: 0, fechaPublicacion: new Date(), creadoEn: new Date(), actualizadoEn: new Date() });
  print("Se insertó (no debería)");
} catch (err) { print(`Rechazado por el validador: código ${err.code} (${err.message})`); }'
nota "Regla entre campos: vacantes.disponibles no puede superar a vacantes.total"
pausa

# ------------------------------------------------------------------ 3. consulta
paso "3. Consulta sobre arreglos" "Quién sabe Python y SQL y trabaja hoy en una empresa registrada (consulta 5)"
comando 'db.usuarios.find({ skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: { actual: true, empresaId: { $ne: null } } } })'
mongo '
const actual = { actual: true, empresaId: { $ne: null } };
db.usuarios.find({ skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: actual } },
                 { _id: 0, nombre: 1, apellido: 1, skills: 1, experiencia: { $elemMatch: actual } })
  .limit(3).forEach(u => print(`${u.nombre} ${u.apellido} | ${u.skills.join(", ")} | trabaja en ${u.experiencia[0].empresaNombre}`));
print(`... ${db.usuarios.countDocuments({ skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: actual } })} usuarios en total`);'
nota "\$all: el arreglo contiene ambas skills · \$elemMatch: un mismo trabajo cumple las dos condiciones"
pausa

# ------------------------------------------------------------------ 4. explain
paso "4. Índices: explain(\"executionStats\")" "Búsqueda principal de ofertas con su índice compuesto (regla ESR) y sin índice"
comando 'db.ofertas.find({ estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS", "salario.min": { $gte: 1700000 } }).explain("executionStats")'
mongo '
const filtro = { estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS", "salario.min": { $gte: 1700000 } };
const etapas = p => p ? [p.stage + (p.indexName ? `[${p.indexName}]` : ""), ...etapas(p.inputStage)] : [];
for (const [nombre, cursor] of [["con índice", db.ofertas.find(filtro).sort({ "salario.min": -1 })],
                                ["sin índice", db.ofertas.find(filtro).sort({ "salario.min": -1 }).hint({ $natural: 1 })]]) {
  const x = cursor.explain("executionStats"), s = x.executionStats, plan = x.queryPlanner.winningPlan;
  print(`${nombre.padEnd(11)} ${etapas(plan.queryPlan ?? plan).join(" <- ").padEnd(42)} devueltos: ${s.nReturned} | documentos examinados: ${s.totalDocsExamined}`);
}'
nota "Con índice examina 3 documentos para devolver 3, y sin ordenar en memoria (no hay SORT)"
pausa

# ------------------------------------------------------------------ 5. API y consistencia
paso "5. Aceptar a un candidato (API + transacción)" "Oferta con 1 sola vacante: el primero se acepta, el segundo recibe 409"
comando "GET /ofertas/$OFERTA"
pedir GET "/ofertas/$OFERTA"
py 'print(d["titulo"], "·", d["empresa"]["nombre"]); print("estado:", d["estado"], "| vacantes:", d["vacantes"], "| postulaciones:", d["cantidadPostulaciones"])' < "$RESPUESTA"
comando "GET /ofertas/$OFERTA/postulaciones   (activas, mayor coincidencia primero)"
pedir GET "/ofertas/$OFERTA/postulaciones?limite=100"
ACTIVAS=$(py '[print(p["id"], p["estado"], p["coincidenciaSkills"]) for p in d["resultados"] if p["estado"] in ("enviada", "en_revision", "entrevista")]' < "$RESPUESTA" | tr -d '\r')
echo "$ACTIVAS" | head -3 | sed 's/^/  /'
PRIMERA=$(echo "$ACTIVAS" | sed -n 1p | cut -d' ' -f1)
SEGUNDA=$(echo "$ACTIVAS" | sed -n 2p | cut -d' ' -f1)
pausa

avanzar() {  # avanzar ID ESTADO: registra un cambio de estado y lo muestra
  pedir PATCH "/postulaciones/$1/estado" "{\"estado\": \"$2\"}"
  nota "PATCH /postulaciones/$1/estado {\"estado\": \"$2\"} → $CODIGO"
}
llevar_a_entrevista() {  # enviada -> en_revision -> entrevista, desde donde esté
  local estado
  estado=$(echo "$ACTIVAS" | grep "^$1" | cut -d' ' -f2)
  [ "$estado" = "enviada" ] && avanzar "$1" en_revision && estado=en_revision
  [ "$estado" = "en_revision" ] && avanzar "$1" entrevista
  return 0
}

echo "Primera postulación: hasta entrevista y después aceptada"
llevar_a_entrevista "$PRIMERA"
comando "PATCH /postulaciones/$PRIMERA/estado  {\"estado\": \"aceptada\"}"
pedir PATCH "/postulaciones/$PRIMERA/estado" '{"estado": "aceptada", "nota": "Demo en vivo"}'
nota "HTTP $CODIGO"
py 'print("estado:", d["estado"], "| historial:", " → ".join(h["estado"] for h in d["historialEstados"]))' < "$RESPUESTA"
comando "GET /ofertas/$OFERTA"
pedir GET "/ofertas/$OFERTA"
py 'print("estado:", d["estado"], "| vacantes:", d["vacantes"], "| fechaCierre:", d["fechaCierre"])' < "$RESPUESTA"
nota "La transacción descontó la vacante y, como era la última, cerró la oferta"
pausa

echo "Segunda postulación: hasta entrevista e intento de aceptarla"
llevar_a_entrevista "$SEGUNDA"
comando "PATCH /postulaciones/$SEGUNDA/estado  {\"estado\": \"aceptada\"}"
pedir PATCH "/postulaciones/$SEGUNDA/estado" '{"estado": "aceptada"}'
nota "HTTP $CODIGO"
py 'print(json.dumps(d, ensure_ascii=False))' < "$RESPUESTA"
pedir GET "/postulaciones/$SEGUNDA"
py 'print("la postulación sigue en:", d["estado"])' < "$RESPUESTA"
nota "El paso 1 (pasar a aceptada) se deshizo: la transacción se abortó por completo"
pausa

# ------------------------------------------------------------------ 6. tests
paso "6. Tests de consistencia" "Falla simulada a mitad de la transacción y 5 aceptaciones simultáneas"
comando 'docker compose run --rm api pytest -k "simultaneas or falla_a_mitad or sin_vacantes"'
docker compose run --rm api pytest -p no:warnings -k "simultaneas or falla_a_mitad or sin_vacantes" 2>&1 | grep -E "PASSED|FAILED|passed|failed"
pausa

# ------------------------------------------------------------------ 7. navegador
paso "7. Swagger y JupyterLab" "Se abren en el navegador para seguir la demo ahí"
comando "docker compose up -d --build --wait analisis"
docker compose up -d --build --wait analisis >/dev/null 2>&1 || echo "No se pudo levantar Jupyter"
nota "Swagger:    $API/docs"
nota "JupyterLab: $JUPYTER/lab/tree/analisis.ipynb"
if [ -z "${DEMO_SIN_PAUSAS:-}" ]; then
  abrir "$API/docs"
  abrir "$JUPYTER/lab/tree/analisis.ipynb"
fi
pausa

# ------------------------------------------------------------------ cierre
paso "Fin de la demo" "La demo modificó datos (aceptó un candidato y cerró una oferta)"
if [ -n "${DEMO_SIN_PAUSAS:-}" ]; then
  RESTAURAR=s
else
  read -rp "¿Volver la base a su estado original ahora? [S/n] " RESTAURAR
fi
case "${RESTAURAR:-s}" in
  [nN]*) nota "Para restaurarla más tarde: bin/reset_db.sh" ;;
  *) bin/reset_db.sh 2>&1 | grep "Verificación" ;;
esac
