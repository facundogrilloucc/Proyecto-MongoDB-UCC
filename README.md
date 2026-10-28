# Plataforma de empleos estilo LinkedIn — MongoDB

Trabajo práctico integrador de **Base de Datos Aplicada** (UCC).

**Integrantes:** Facundo Grillo, María Emilia Lasa, Gonzalo Marín

Base de datos documental para una plataforma de empleos: perfiles profesionales, empresas, ofertas laborales y postulaciones.

## Documentación

**¿Primera vez?** Seguí la guía paso a paso para Mac y Windows: [docs/instrucciones.md](docs/instrucciones.md).

| Entrega | Documento |
| :--- | :--- |
| 1 — Propuesta y diseño | [docs/entrega-1-diseno.md](docs/entrega-1-diseno.md) |
| 2 — Implementación, consultas e índices | [docs/entrega-2.md](docs/entrega-2.md) |
| 3 — API, repositorios y consistencia | [docs/entrega-3.md](docs/entrega-3.md) |
| 4 — Análisis de datos | [analisis/analisis.ipynb](analisis/analisis.ipynb) |
| **Informe técnico final** | [docs/informe-final.md](docs/informe-final.md) |
| Guía para la defensa | [docs/defensa.md](docs/defensa.md) |

## Requisitos

- Docker Desktop (o Docker Engine con Docker Compose v2).
- No hace falta instalar MongoDB, `mongosh` ni Python localmente: todo corre en contenedores.

## Puesta en marcha

```bash
cp .env.example .env
```

Editar `.env` y definir una contraseña (sin caracteres especiales). Después:

```bash
bin/reset_db.sh
```

Ese script:

1. Levanta MongoDB 8.0 como replica set de un nodo (`docker compose up -d --wait mongo`).
2. Borra la base y crea las colecciones con sus validaciones (`db/scripts/01_colecciones.js`).
3. Carga los datos de prueba (`docker compose run --rm seed`).
4. Crea los índices (`db/scripts/02_indices.js`).
5. Verifica cantidades, integridad y reglas de negocio (`db/scripts/03_verificacion.js`).

Se puede ejecutar todas las veces que haga falta: siempre deja la base en el mismo estado, porque los datos se generan con una semilla fija.

## API

Con la base ya cargada:

```bash
docker compose up -d --build --wait api
```

- Documentación interactiva (Swagger): <http://localhost:8000/docs>
- Tests de integración (43): `docker compose run --rm api pytest`
- Recorrido de demostración de todos los endpoints: `docker compose exec api python scripts/demo.py`. Modifica datos; después conviene volver al estado original con `bin/reset_db.sh`.

La API está hecha con FastAPI y PyMongo, en tres capas: `routers` (HTTP), `services` (reglas de negocio y transacciones) y `repositories` (acceso a MongoDB). El detalle está en [docs/entrega-3.md](docs/entrega-3.md).

## Análisis de datos

Notebook de Jupyter con PyMongo, Pandas y Matplotlib: [analisis/analisis.ipynb](analisis/analisis.ipynb). En GitHub se ve con los gráficos ya generados.

Para abrirlo en JupyterLab, con la base ya cargada:

```bash
docker compose up -d analisis
```

y entrar a <http://localhost:8888>.

Para volver a ejecutarlo completo sin abrir el navegador (regenera también los gráficos de `analisis/figuras/`):

```bash
docker compose run --rm analisis jupyter nbconvert --to notebook --execute --inplace analisis.ipynb
```

## Scripts de la base

| Script | Qué hace |
| :--- | :--- |
| `db/scripts/01_colecciones.js` | Crea las colecciones con validación `$jsonSchema` |
| `seed/generar_datos.py` | Genera y carga ~450 documentos reproducibles |
| `db/scripts/02_indices.js` | Crea los índices |
| `db/scripts/03_verificacion.js` | Verifica la carga y prueba las validaciones |
| `db/scripts/04_consultas.js` | Las 13 consultas del dominio |
| `db/scripts/05_explain.js` | Análisis de índices con `explain("executionStats")` |
| `db/scripts/06_consistencia_inicial.js` | Pruebas de consistencia (índice único, operaciones atómicas, transacción) |

Cualquier script se ejecuta con:

```bash
bin/mongosh.sh /scripts/04_consultas.js
```

Para abrir una consola `mongosh` interactiva sobre la base:

```bash
bin/mongosh.sh
```

Para conectarse desde una herramienta externa (MongoDB Compass, por ejemplo), usar `directConnection=true`, porque el replica set se anuncia con el nombre interno `mongo`:

```
mongodb://<usuario>:<contraseña>@localhost:27017/?authSource=admin&directConnection=true
```

## Detener el entorno

Detener los contenedores (MongoDB, la API y Jupyter) y conservar los datos:

```bash
docker compose down
```

Detener los contenedores y borrar también el volumen de datos:

```bash
docker compose down -v
```

## Estructura

```
.
├── docker-compose.yml       # MongoDB (replica set), API, carga de datos y JupyterLab
├── api/                     # API REST (FastAPI): app/, tests/ y scripts/demo.py
├── analisis/                # notebook de análisis y gráficos generados
├── .env.example             # variables de configuración, sin credenciales reales
├── bin/                     # reset_db.sh y mongosh.sh
├── db/scripts/              # scripts de mongosh (colecciones, índices, consultas...)
├── seed/                    # generador de datos de prueba (Python + Faker)
└── docs/                    # documentación de cada entrega y evidencia de ejecución
```
