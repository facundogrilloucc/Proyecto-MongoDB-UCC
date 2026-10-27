# Entrega parcial 2 — Base poblada, consultas e índices

**Proyecto:** Plataforma de empleos estilo LinkedIn
**Integrantes:** Facundo Grillo, María Emilia Lasa, Gonzalo Marín
**Motor:** MongoDB 8.0 (replica set de un nodo en Docker Compose)

Esta entrega implementa el diseño de la [Entrega 1](entrega-1-diseno.md). Incluye:

- Creación de las colecciones con reglas de validación.
- Carga reproducible de datos de prueba.
- 13 consultas del dominio.
- Índices con su análisis de `explain()`.
- Primeras pruebas de consistencia.

Toda la salida que se muestra acá se obtuvo ejecutando los scripts. Los archivos completos están en [`docs/evidencia/`](evidencia/).

---

## 1. Cómo reproducir todo

```bash
cp .env.example .env      # definir una contraseña
bin/reset_db.sh           # crea, carga, indexa y verifica
bin/mongosh.sh /scripts/04_consultas.js
bin/mongosh.sh /scripts/05_explain.js
bin/mongosh.sh /scripts/06_consistencia_inicial.js
```

| Archivo | Contenido |
| :--- | :--- |
| [`docker-compose.yml`](../docker-compose.yml) | MongoDB 8.0 como replica set `rs0`, con autenticación y volumen persistente, más un servicio `seed` con Python para la carga |
| [`db/scripts/01_colecciones.js`](../db/scripts/01_colecciones.js) | Borra la base y crea las 4 colecciones con validación |
| [`seed/generar_datos.py`](../seed/generar_datos.py) | Genera y carga los datos de prueba |
| [`db/scripts/02_indices.js`](../db/scripts/02_indices.js) | Crea los índices |
| [`db/scripts/03_verificacion.js`](../db/scripts/03_verificacion.js) | Verifica cantidades, integridad, reglas de negocio y validaciones |
| [`db/scripts/04_consultas.js`](../db/scripts/04_consultas.js) | Consultas del dominio |
| [`db/scripts/05_explain.js`](../db/scripts/05_explain.js) | Análisis de índices |
| [`db/scripts/06_consistencia_inicial.js`](../db/scripts/06_consistencia_inicial.js) | Pruebas de consistencia |

**Reproducibilidad:** el generador usa una semilla fija (`42`) y una fecha de referencia fija (27/10/2026), así que cada ejecución produce exactamente los mismos documentos, incluidos los `_id`. Lo comprobamos así: después de un `reset_db.sh` completo, la salida de `04_consultas.js` fue idéntica byte a byte a la anterior.

**Por qué un replica set:** las transacciones multidocumento que se usarán en la Entrega 3 no funcionan en una instancia independiente. Por eso el contenedor arranca `mongod --replSet rs0`, y el *healthcheck* inicializa el replica set la primera vez.

---

## 2. Colecciones y validación de esquema

Cada colección se crea con un `validator` (`validationLevel: strict`, `validationAction: error`). Las reglas combinan:

- **`$jsonSchema`**: campos obligatorios, tipos BSON, valores permitidos (`seniority`, `modalidad`, `estado`, niveles de idioma), formato del email, skills sin repetir (`uniqueItems`) y límites de tamaño de los arreglos embebidos (`maxItems`). Este último límite es la garantía de que experiencia y skills, que decidimos embeber, no crezcan sin control.
- **Expresiones de consulta** para reglas entre campos que `$jsonSchema` no puede expresar (solo en `ofertas`):

```js
{ $expr: { $lte: ["$vacantes.disponibles", "$vacantes.total"] } },
{ $or: [{ salario: { $exists: false } }, { $expr: { $lte: ["$salario.min", "$salario.max"] } }] },
{ $or: [{ modalidad: "remoto" }, { ubicacion: { $exists: true } }] }
```

`03_verificacion.js` intenta insertar 7 documentos inválidos y comprueba que todos se rechacen:

```
== Validación de esquema (se espera que cada inserción falle)
OK    usuarios: email con formato inválido -> rechazado (código 121)
OK    usuarios: seniority fuera de los valores permitidos -> rechazado (código 121)
OK    usuarios: skills repetidas -> rechazado (código 121)
OK    ofertas: más vacantes disponibles que el total -> rechazado (código 121)
OK    ofertas: salario mínimo mayor al máximo -> rechazado (código 121)
OK    ofertas: oferta presencial sin ubicación -> rechazado (código 121)
OK    postulaciones: historial de estados vacío -> rechazado (código 121)
```

**Qué queda fuera del validador:** la existencia de los documentos referenciados (por ejemplo, que `usuarioId` apunte a un usuario real). MongoDB no tiene claves foráneas, así que esto lo controla la capa de servicios de la API (Entrega 3) y lo verifica el script de verificación (sección 3.3).

---

## 3. Carga de datos

### 3.1. Generador

[`seed/generar_datos.py`](../seed/generar_datos.py) usa Faker (`es_AR`) para nombres y apellidos. Los valores del dominio salen de catálogos propios:

- Seis familias de puestos (backend, frontend, data, devops, mobile, QA), cada una con sus skills.
- Ciudades argentinas con distinto peso.
- Empresas ficticias.
- Bandas salariales por seniority en ARS y USD.

Puntos a destacar del generador:

- **Skills normalizadas** en minúscula y con un nombre canónico, para que las comparaciones entre usuarios y ofertas funcionen.
- **Demanda y oferta de skills desbalanceadas a propósito:** cada skill tiene un peso para perfiles y otro para ofertas. Por ejemplo, `kubernetes` y `typescript` son más pedidas que ofrecidas. Así el análisis de la Entrega 4 tiene algo que descubrir.
- **Coherencia entre colecciones:**
  - Los usuarios se postulan sobre todo a ofertas de su área.
  - Las aceptadas son las de mayor coincidencia de skills.
  - `vacantes.disponibles` y `cantidadPostulaciones` se calculan a partir de las postulaciones.
  - Las fechas respetan la cronología (no hay postulaciones anteriores a la publicación).
- **`_id` determinísticos:** los primeros 4 bytes del `ObjectId` son la fecha real de creación del documento y los 8 restantes salen de la semilla.

### 3.2. Volumen

| Colección | Documentos |
| :--- | ---: |
| `empresas` | 20 |
| `usuarios` | 120 |
| `ofertas` | 60 |
| `postulaciones` | 250 |
| **Total** | **450** |

### 3.3. Verificación de la carga

Salida de `03_verificacion.js` (completa en [`evidencia/01_reset_y_verificacion.txt`](evidencia/01_reset_y_verificacion.txt)):

```
== Integridad referencial
OK    Toda oferta referencia a una empresa existente
OK    El nombre de empresa desnormalizado en la oferta coincide con el original
OK    Toda postulación referencia a un usuario existente
OK    Toda postulación referencia a una oferta existente y de la misma empresa

== Reglas de negocio
OK    vacantes.disponibles = total - postulaciones aceptadas
OK    cantidadPostulaciones = postulaciones no retiradas
OK    Ninguna oferta abierta o pausada se quedó sin vacantes
OK    Las ofertas cerradas tienen fecha de cierre y las demás no
OK    El estado de la postulación coincide con el último paso de su historial
OK    Nadie se postuló antes de que se publicara la oferta
```

Los controles de integridad son agregaciones con `$lookup` que buscan documentos huérfanos o desnormalizaciones desincronizadas. Los mismos controles servirán para detectar inconsistencias si en algún momento una operación falla a mitad de camino.

### 3.4. Casos límite incluidos

| Caso | Cantidad |
| :--- | ---: |
| Usuarios sin experiencia laboral | 16 |
| Usuarios sin skills (perfil recién creado) | 2 |
| Usuarios sin preferencias | 20 |
| Usuarios fuera de Argentina (sin provincia) | 3 |
| Usuarios con más de un trabajo actual | 3 |
| Experiencias en empresas no registradas (`empresaId: null`) | 129 |
| Empresas sin ofertas publicadas | 3 |
| Ofertas sin salario publicado | 18 |
| Ofertas remotas sin ubicación | 10 |
| Ofertas cerradas sin vacantes disponibles | 10 |
| Ofertas pausadas | 4 |
| Ofertas sin postulaciones activas | 3 |

Postulaciones por estado: enviada 58, en revisión 44, entrevista 23, aceptada 25, rechazada 73, retirada 27.

---

## 4. Consultas

Las consultas están en [`db/scripts/04_consultas.js`](../db/scripts/04_consultas.js) y la salida completa en [`evidencia/04_consultas.txt`](evidencia/04_consultas.txt).

### 4.1. Cobertura de la consigna

| Requisito de la consigna | Consultas |
| :--- | :--- |
| Dos consultas con filtros y operadores de comparación | 1, 2 |
| Una consulta con operadores lógicos | 3 |
| Una consulta sobre atributos anidados | 4 |
| Una consulta sobre arreglos | 5 |
| Proyección, ordenamiento y límite | 6 |
| Dos consultas con `aggregate()` | 7, 8 (además 10, 11 y 12) |
| Agrupamiento con cálculos estadísticos | 9 |
| Consulta adicional de complejidad elegida | 10 (matching de candidatos) |
| Extras | 11 (evolución mensual), 12 (coherencia del seniority), 13 (búsqueda de texto) |

### 4.2. Detalle

#### Consulta 1 — Ofertas abiertas semi-senior que pagan al menos $1.700.000 de mínimo

**Objetivo:** que un candidato semi-senior encuentre las ofertas mejor pagas para su nivel. Es la búsqueda principal de la plataforma.

```js
db.ofertas.find(
  { estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS", "salario.min": { $gte: 1_700_000 } },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, salario: 1 }
).sort({ "salario.min": -1 })
```

**Resultado esperado:** solo ofertas abiertas, semi-senior y en pesos, con `salario.min >= 1.700.000`, ordenadas de mayor a menor mínimo. Las ofertas sin salario publicado no aparecen.
**Resultado obtenido:** 3 ofertas (Pampa Pagos y Cauce Seguros con mínimo de $1.930.000, y Cauce Seguros con $1.700.000, que está justo en el borde e incluido por `$gte`).

#### Consulta 2 — Postulaciones activas recientes con alta coincidencia de skills

**Objetivo:** que un reclutador vea los candidatos más prometedores de las últimas 4 semanas que siguen en carrera.

```js
db.postulaciones.find(
  { coincidenciaSkills: { $gte: 0.75 },
    fechaPostulacion: { $gte: new Date(HOY - 30 * DIA) },
    estado: { $nin: ["rechazada", "retirada"] } },
  { _id: 0, usuarioId: 1, ofertaId: 1, estado: 1, coincidenciaSkills: 1, fechaPostulacion: 1 }
).sort({ coincidenciaSkills: -1, fechaPostulacion: -1 })
```

**Resultado esperado:** postulaciones con coincidencia de al menos 0,75 y fecha posterior al 27/09/2026, en cualquier estado salvo rechazada o retirada.
**Resultado obtenido:** 16 postulaciones: 9 con coincidencia 1,0, una con 0,8 y 6 con 0,75.

#### Consulta 3 — Ofertas a las que puede aplicar alguien que vive en Córdoba

**Objetivo:** filtrar por modalidad y ubicación al mismo tiempo. Una persona de Córdoba puede tomar cualquier oferta remota, pero las híbridas o presenciales solo si son en Córdoba.

```js
db.ofertas.find(
  { estado: "abierta",
    seniority: { $ne: "junior" },
    $or: [
      { modalidad: "remoto" },
      { modalidad: { $in: ["hibrido", "presencial"] }, "ubicacion.provincia": "Córdoba" }
    ] },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, ciudad: "$ubicacion.ciudad" }
).sort({ modalidad: 1, titulo: 1 })
```

**Resultado esperado:** ofertas abiertas no junior que sean remotas (de cualquier lugar, con o sin ubicación) o que sean híbridas o presenciales en la provincia de Córdoba.
**Resultado obtenido:** 15 ofertas: 13 remotas (algunas sin ciudad, otras de CABA o La Plata), una híbrida y una presencial en Córdoba.

#### Consulta 4 — Candidatos de Córdoba disponibles para trabajo remoto que pretenden hasta $2.000.000

**Objetivo:** búsqueda de candidatos por un reclutador con presupuesto limitado. Se filtra por campos de tres niveles de anidamiento.

```js
db.usuarios.find(
  { "ubicacion.provincia": "Córdoba",
    "preferencias.disponible": true,
    "preferencias.modalidades": "remoto",
    "preferencias.salarioPretendido.moneda": "ARS",
    "preferencias.salarioPretendido.monto": { $lte: 2_000_000 } },
  { _id: 0, nombre: 1, apellido: 1, seniority: 1, pretende: "$preferencias.salarioPretendido.monto" }
).sort({ "preferencias.salarioPretendido.monto": 1 })
```

**Resultado esperado:** usuarios que cumplan todas las condiciones anidadas. Quedan fuera los usuarios sin `preferencias`, porque el campo no existe.
**Resultado obtenido:** 6 candidatos (5 junior y 1 semi-senior), con pretensiones de entre $1.120.000 y $1.500.000.

#### Consulta 5 — Quiénes saben Python y SQL y trabajan hoy en una empresa registrada

**Objetivo:** consulta sobre dos arreglos distintos del mismo documento: las skills (arreglo de strings) y la experiencia (arreglo de subdocumentos).

```js
const trabajoActualRegistrado = { actual: true, empresaId: { $ne: null } };
db.usuarios.find(
  { skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: trabajoActualRegistrado } },
  { _id: 0, nombre: 1, apellido: 1, skills: 1, experiencia: { $elemMatch: trabajoActualRegistrado } }
)
```

**Resultado esperado:** usuarios que tengan ambas skills y al menos una experiencia actual en una empresa registrada. `$elemMatch` es necesario: sin él, la condición `actual: true` podría cumplirla un elemento y `empresaId != null` otro distinto. En la proyección, `$elemMatch` devuelve solo ese trabajo y no toda la trayectoria.
**Resultado obtenido:** 10 usuarios, cada uno con su trabajo actual (por ejemplo, Victoria Diaz en Algarrobo Agrotech).

> **Problema encontrado:** la primera versión usaba la proyección posicional `"experiencia.$"` y MongoDB devolvió `positional operator '.$' element mismatch`. El filtro toca dos arreglos (`skills` y `experiencia`), así que el `$` posicional es ambiguo. Lo resolvimos con una proyección `$elemMatch`.

#### Consulta 6 — Las 10 ofertas abiertas mejor pagas en pesos

**Objetivo:** ranking de salarios para la portada del sitio. Usa una proyección con campos renombrados, ordenamiento y límite.

```js
db.ofertas.find(
  { estado: "abierta", "salario.moneda": "ARS" },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, salarioMax: "$salario.max" }
).sort({ "salario.max": -1, _id: 1 }).limit(10)
```

**Resultado esperado:** 10 documentos ordenados por `salarioMax` descendente. `_id` desempata ofertas con el mismo salario, para que el resultado sea siempre igual.
**Resultado obtenido:** desde *Frontend Developer Lead* en Pampa Pagos ($4.410.000) hasta *QA Automation Engineer Ssr* en Cauce Seguros ($2.750.000).

#### Consulta 7 — Embudo de selección y tasa de aceptación por empresa

**Objetivo:** comparar cómo selecciona cada empresa: cuántas postulaciones recibe, cuántas llegan a entrevista y cuántas terminan en contratación.

```js
db.postulaciones.aggregate([
  { $group: {
      _id: "$empresaId",
      postulaciones: { $sum: 1 },
      entrevistas: { $sum: { $cond: [{ $in: ["entrevista", "$historialEstados.estado"] }, 1, 0] } },
      aceptadas:   { $sum: { $cond: [{ $eq: ["$estado", "aceptada"] }, 1, 0] } },
      retiradas:   { $sum: { $cond: [{ $eq: ["$estado", "retirada"] }, 1, 0] } } } },
  { $lookup: { from: "empresas", localField: "_id", foreignField: "_id", as: "empresa" } },
  { $project: {
      _id: 0, empresa: { $first: "$empresa.nombre" },
      postulaciones: 1, entrevistas: 1, aceptadas: 1, retiradas: 1,
      tasaAceptacion: { $round: [{ $divide: ["$aceptadas",
        { $max: [1, { $subtract: ["$postulaciones", "$retiradas"] }] }] }, 3] } } },
  { $sort: { tasaAceptacion: -1, postulaciones: -1 } }
])
```

**Detalle:** "entrevistas" cuenta las postulaciones que pasaron por esa etapa en algún momento, mirando el historial embebido y no solo el estado actual. Para la tasa se excluyen las retiradas, porque la empresa no llegó a decidir sobre ellas, y `$max: [1, …]` evita dividir por cero.
**Resultado obtenido:** 17 empresas, una por cada empresa que recibió postulaciones. Brújula Fintech recibe el mayor volumen (46 postulaciones) pero acepta solo 1 (tasa 0,025). Lumen Analytics acepta 2 de 4 decididas (0,5).

#### Consulta 8 — Skills más demandadas que ofrecidas, y al revés

**Objetivo:** detectar faltantes de talento. Compara el porcentaje de ofertas que piden cada skill con el porcentaje de usuarios que la tienen. Es la base del análisis de la Entrega 4.

```js
db.ofertas.aggregate([
  { $project: { skill: { $setUnion: ["$skillsRequeridas", { $ifNull: ["$skillsDeseables", []] }] } } },
  { $unwind: "$skill" },
  { $group: { _id: "$skill", ofertas: { $sum: 1 } } },
  { $unionWith: { coll: "usuarios",
      pipeline: [{ $unwind: "$skills" }, { $group: { _id: "$skills", usuarios: { $sum: 1 } } }] } },
  { $group: { _id: "$_id", ofertas: { $sum: "$ofertas" }, usuarios: { $sum: "$usuarios" } } },
  { $set: {
      pctOfertas:  { $round: [{ $multiply: [100, { $divide: ["$ofertas",  totalOfertas] }] }, 1] },
      pctUsuarios: { $round: [{ $multiply: [100, { $divide: ["$usuarios", totalUsuarios] }] }, 1] } } },
  { $set: { brecha: { $round: [{ $subtract: ["$pctOfertas", "$pctUsuarios"] }, 1] } } },
  { $facet: {
      masDemandadasQueOfrecidas: [{ $sort: { brecha: -1 } }, { $limit: 6 }],
      masOfrecidasQueDemandadas: [{ $sort: { brecha: 1 } }, { $limit: 4 }] } }
])
```

**Detalle:** `$unionWith` junta en un mismo pipeline los conteos de dos colecciones, y el segundo `$group` los combina por skill. `$facet` devuelve los dos rankings en una sola pasada.

**Resultado obtenido:**

| Más demandadas que ofrecidas | % ofertas | % usuarios | Brecha |
| :--- | ---: | ---: | ---: |
| aws | 31,7 | 14,2 | +17,5 |
| next.js | 15,0 | 0,8 | +14,2 |
| typescript | 16,7 | 5,8 | +10,9 |
| postgresql | 28,3 | 17,5 | +10,8 |

| Más ofrecidas que demandadas | % ofertas | % usuarios | Brecha |
| :--- | ---: | ---: | ---: |
| git | 23,3 | 71,7 | −48,4 |
| scrum | 18,3 | 48,3 | −30,0 |
| jira | 15,0 | 34,2 | −19,2 |
| node.js | 5,0 | 19,2 | −14,2 |

> **Ajuste:** en la primera versión la demanda contaba solo `skillsRequeridas`, y `git`, `scrum` y `jira` aparecían con 0 % de demanda porque las empresas los piden únicamente como deseables. Para no distorsionar la brecha, contamos como demanda la unión de requeridas y deseables.

#### Consulta 9 — Salario según seniority y moneda (estadísticas)

**Objetivo:** dar referencias salariales a candidatos y empresas.

```js
db.ofertas.aggregate([
  { $match: { salario: { $exists: true } } },
  { $set: { salarioMedio: { $avg: ["$salario.min", "$salario.max"] } } },
  { $group: {
      _id: { seniority: "$seniority", moneda: "$salario.moneda" },
      ofertas: { $sum: 1 }, promedio: { $avg: "$salarioMedio" },
      minimo: { $min: "$salario.min" }, maximo: { $max: "$salario.max" },
      desvio: { $stdDevPop: "$salarioMedio" } } },
  // ...redondeo y orden por moneda y nivel de seniority ($indexOfArray)
])
```

**Detalle:** se agrupa por moneda además de seniority, porque promediar pesos con dólares no tiene sentido. El orden usa `$indexOfArray` sobre `["junior", "semi-senior", "senior", "lead"]` y no el orden alfabético.

**Resultado obtenido:**

| Moneda | Seniority | Ofertas | Promedio | Mínimo | Máximo | Desvío |
| :--- | :--- | ---: | ---: | ---: | ---: | ---: |
| ARS | junior | 10 | 1.296.500 | 910.000 | 1.800.000 | 138.005 |
| ARS | semi-senior | 11 | 1.968.182 | 1.460.000 | 2.750.000 | 213.459 |
| ARS | senior | 8 | 3.090.000 | 2.460.000 | 3.980.000 | 254.608 |
| ARS | lead | 7 | 4.197.857 | 3.230.000 | 6.110.000 | 428.660 |
| USD | semi-senior | 3 | 2.567 | 2.000 | 3.300 | 330 |
| USD | senior | 2 | 4.400 | 3.400 | 5.800 | 600 |
| USD | lead | 1 | 6.200 | 5.600 | 6.800 | 0 |

No hay ofertas junior en USD. Las 18 ofertas sin salario no participan.

#### Consulta 10 (complejidad elegida) — Matching de candidatos para una oferta

**Objetivo:** recomendar a un reclutador los mejores candidatos que todavía no se postularon a su oferta. La consulta toma la oferta abierta más reciente con 4 o más skills requeridas.

```js
db.usuarios.aggregate([
  { $match: { skills: { $in: oferta.skillsRequeridas }, seniority: { $in: compatibles } } },
  { $set: { coincidentes: { $setIntersection: ["$skills", oferta.skillsRequeridas] },
            deseables: { $size: { $setIntersection: ["$skills", oferta.skillsDeseables ?? []] } } } },
  { $set: { coincidencia: { $round: [{ $divide: [{ $size: "$coincidentes" }, oferta.skillsRequeridas.length] }, 2] } } },
  { $match: { coincidencia: { $gte: 0.6 } } },
  { $lookup: { from: "postulaciones", localField: "_id", foreignField: "usuarioId",
               pipeline: [{ $match: { ofertaId: oferta._id } }], as: "yaPostulado" } },
  { $match: { yaPostulado: { $size: 0 } } },
  { $sort: { coincidencia: -1, deseables: -1, "preferencias.disponible": -1, apellido: 1 } },
  { $limit: 10 },
  { $project: { _id: 0, candidato: { $concat: ["$nombre", " ", "$apellido"] }, seniority: 1,
                coincidencia: 1, coincidentes: 1, deseables: 1, disponible: "$preferencias.disponible" } }
])
```

**Detalle:**

1. El primer `$match` aprovecha el índice multikey `ix_skills` para descartar enseguida a quienes no tienen ninguna skill pedida, y acepta seniorities a un nivel de distancia del de la oferta.
2. `$setIntersection` calcula qué skills coinciden.
3. El `$lookup` con `localField` y `pipeline` excluye a quienes ya se postularon, apoyándose en el índice único `ux_usuario_oferta`.

**Resultado obtenido:** para *Desarrollador/a Backend Ssr* de Puna Studio (requiere mongodb, sql, postgresql, spring y aws), 9 candidatos. Simon Guzman cumple el 100 %; tres candidatos, el 80 %; y cinco, el 60 %.

#### Consulta 11 — Evolución mensual de las postulaciones

```js
db.postulaciones.aggregate([
  { $group: { _id: { $dateTrunc: { date: "$fechaPostulacion", unit: "month" } },
              postulaciones: { $sum: 1 },
              aceptadas: { $sum: { $cond: [{ $eq: ["$estado", "aceptada"] }, 1, 0] } },
              coincidenciaPromedio: { $avg: "$coincidenciaSkills" } } },
  { $sort: { _id: 1 } },
  { $project: { _id: 0, mes: { $dateToString: { date: "$_id", format: "%Y-%m" } },
                postulaciones: 1, aceptadas: 1, coincidenciaPromedio: { $round: ["$coincidenciaPromedio", 2] } } }
])
```

**Resultado obtenido:** las postulaciones crecen de 5 en abril a 129 en octubre de 2026, porque la mayoría de las ofertas son recientes. Las aceptaciones de los últimos meses son bajas porque esos procesos todavía están en curso.

#### Consulta 12 — ¿Los años de experiencia son coherentes con el seniority?

**Objetivo:** control de calidad de los perfiles. Calcula los años trabajados a partir del arreglo embebido de experiencia.

```js
db.usuarios.aggregate([
  { $set: { aniosExperiencia: { $divide: [{ $sum: { $map: {
      input: "$experiencia",
      in: { $dateDiff: { startDate: "$$this.desde", endDate: { $ifNull: ["$$this.hasta", HOY] }, unit: "month" } }
  } } }, 12] } } },
  { $group: { _id: "$seniority", usuarios: { $sum: 1 }, promedio: { $avg: "$aniosExperiencia" },
              minimo: { $min: "$aniosExperiencia" }, maximo: { $max: "$aniosExperiencia" },
              sinExperiencia: { $sum: { $cond: [{ $eq: [{ $size: "$experiencia" }, 0] }, 1, 0] } } } },
  // ...redondeo y orden por nivel
])
```

**Resultado obtenido:**

| Seniority | Usuarios | Años promedio | Mínimo | Máximo | Sin experiencia |
| :--- | ---: | ---: | ---: | ---: | ---: |
| junior | 32 | 0,7 | 0 | 2,2 | 16 |
| semi-senior | 48 | 3,2 | 2,2 | 4,2 | 0 |
| senior | 29 | 7,1 | 5,1 | 9,2 | 0 |
| lead | 11 | 11,2 | 8,4 | 13,8 | 0 |

Los rangos son crecientes y casi no se superponen, así que el seniority declarado es coherente. Hay una limitación: los trabajos simultáneos (los 3 usuarios con un freelance en paralelo) suman meses dos veces.

#### Consulta 13 (extensión) — Búsqueda de texto

```js
db.ofertas.find(
  { $text: { $search: "python remoto" } },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, relevancia: { $meta: "textScore" } }
).sort({ relevancia: { $meta: "textScore" }, _id: 1 }).limit(8)
```

**Resultado obtenido:** las 4 ofertas con mayor relevancia (≈1,05) mencionan las dos palabras. Las siguientes (≈0,53) mencionan solo una. El índice de texto usa el idioma español, así que aplica *stemming* y descarta palabras vacías.

---

## 5. Índices

### 5.1. Índices creados

| Colección | Índice | Campos | Justificación |
| :--- | :--- | :--- | :--- |
| `usuarios` | `ux_email` (único) | `email` | Impide cuentas duplicadas; búsqueda por email en el alta o login |
| `usuarios` | `ix_skills` (multikey) | `skills` | Búsqueda de candidatos por skill (consultas 5 y 10) |
| `empresas` | `ux_nombre` (único) | `nombre` | Unicidad del nombre comercial |
| `ofertas` | `ix_busqueda_ofertas` | `estado, seniority, salario.moneda, salario.min` | Búsqueda principal de ofertas (consulta 1) |
| `ofertas` | `ix_skills_requeridas` (multikey) | `skillsRequeridas` | Ofertas que piden una skill |
| `ofertas` | `tx_ofertas` (texto, español) | `titulo` (peso 3), `descripcion` (peso 1) | Búsqueda libre (consulta 13) |
| `postulaciones` | `ux_usuario_oferta` (único) | `usuarioId, ofertaId` | Una sola postulación por usuario y oferta; su prefijo resuelve "mis postulaciones" |
| `postulaciones` | `ix_oferta_estado` | `ofertaId, estado` | Postulantes de una oferta, filtrados por estado |

**Orden de los campos en `ix_busqueda_ofertas`:** sigue la regla **ESR** (*Equality, Sort, Range*). Primero van los campos que se comparan por igualdad (`estado`, `seniority`, `salario.moneda`) y al final el de rango (`salario.min`). Así el índice acota exactamente el tramo de claves que interesa.

**Cambio respecto de la Entrega 1:** el diseño preveía `{estado, modalidad, seniority, salario.min}`. Al escribir las consultas vimos que la búsqueda por salario siempre necesita fijar la moneda (comparar `min` entre pesos y dólares no tiene sentido) y que la modalidad se filtra con `$or` (consulta 3), lo que no aprovecha bien un índice compuesto. Por eso reemplazamos `modalidad` por `salario.moneda`.

### 5.2. Análisis con `explain("executionStats")`

[`05_explain.js`](../db/scripts/05_explain.js) ejecuta cada consulta dos veces: con el plan elegido por MongoDB y forzando un recorrido completo con `hint({ $natural: 1 })`. Salida completa en [`evidencia/05_explain.txt`](evidencia/05_explain.txt).

| # | Consulta | Plan con índice | Devueltos | Claves exam. | Docs exam. | Docs exam. sin índice |
| :--- | :--- | :--- | ---: | ---: | ---: | ---: |
| 1 | Ofertas semi-senior ARS ≥ 1,7 M (consulta 1) | `FETCH ← IXSCAN[ix_busqueda_ofertas]` | 3 | 3 | 3 | 60 |
| 2 | Usuarios con python y sql (consulta 5) | `FETCH ← IXSCAN[ix_skills]` | 28 | 44 | 44 | 120 |
| 3 | Postulantes activos de la oferta más popular | `FETCH ← IXSCAN[ix_oferta_estado]` | 21 | 22 | 21 | 250 |
| 4 | Postulaciones de un usuario por fecha | `SORT ← FETCH ← IXSCAN[ux_usuario_oferta]` | 6 | 6 | 6 | 250 |
| 5 | Top 10 mejor pagas en ARS (consulta 6) | `SORT ← FETCH ← IXSCAN[ix_busqueda_ofertas]` | 10 | 26 | 19 | 60 |
| 6 | Usuario por email | `EXPRESS_IXSCAN[ux_email]` | 1 | 1 | 1 | 120 |

**Interpretación:**

- **Explain 1 (caso ideal):** se examinaron exactamente tantas claves y documentos como resultados (3/3/3). Además, el plan no tiene etapa `SORT`: como los tres campos de igualdad están fijos, las claves ya vienen ordenadas por `salario.min`, y MongoDB recorre el índice en sentido inverso para el orden descendente. Sin índice, examina las 60 ofertas y ordena en memoria.
- **Explain 2 (multikey con `$all`):** MongoDB usa el índice para **uno** de los valores (las 44 personas con `python`) y verifica `sql` al leer cada documento. Por eso examina 44 documentos para devolver 28. Sigue siendo mucho mejor que leer los 120.
- **Explain 3:** el `$in` sobre tres estados genera tres rangos dentro del índice. La clave de más (22 contra 21) corresponde al salto entre rangos. Sin índice, se leen las 250 postulaciones para devolver 21.
- **Explain 4 (prefijo de un índice compuesto):** no hizo falta un índice propio sobre `usuarioId`, porque el índice único `{usuarioId, ofertaId}` lo cubre como prefijo. El índice no incluye `fechaPostulacion`, así que el orden se hace en memoria (`SORT`). Con 5 o 10 postulaciones por usuario ese costo es despreciable, y no justifica mantener otro índice en cada escritura.
- **Explain 5 (el índice ayuda a medias):** el índice resuelve `estado = "abierta"`, pero `salario.moneda` no está a continuación (entre medio está `seniority`). Por eso examina 26 claves para leer 19 documentos y ordena en memoria. Un índice `{estado: 1, "salario.moneda": 1, "salario.max": -1}` eliminaría el `SORT`, pero con 60 ofertas no compensa el costo de mantenerlo. Lo dejamos anotado como mejora para un volumen real.
- **Explain 6:** MongoDB 8 usa `EXPRESS_IXSCAN`, un camino rápido para igualdades sobre índices únicos que ni siquiera pasa por el planificador.

**Sobre los tiempos:** todos los tiempos dan 0 ms. Con 450 documentos, todo entra en memoria y un recorrido completo es casi instantáneo, así que el tiempo no permite comparar. Lo que muestra el beneficio es la proporción entre documentos examinados y devueltos: con índice está cerca de 1:1; sin índice crece linealmente con el tamaño de la colección.

### 5.3. Costo de los índices

```
usuarios       datos:  146883 | índices:   45056 | _id_=4096, ux_email=20480, ix_skills=20480
empresas       datos:    6238 | índices:   24576 | _id_=4096, ux_nombre=20480
ofertas        datos:   45840 | índices:   77824 | _id_=4096, ix_busqueda_ofertas=20480, ix_skills_requeridas=20480, tx_ofertas=32768
postulaciones  datos:  103603 | índices:   49152 | _id_=4096, ux_usuario_oferta=24576, ix_oferta_estado=20480
```

- En `ofertas`, los índices ocupan **más que los datos** (78 KB contra 46 KB). Con tan pocos documentos, la mayor parte es el tamaño mínimo que reserva el motor de almacenamiento (WiredTiger) por cada índice, pero muestra que los índices no son gratis.
- El índice de texto es el más grande: guarda una entrada por cada palabra distinta de cada título y descripción.
- **Costo de escritura:** cada alta o modificación de una oferta actualiza 5 índices. Lo aceptamos porque las ofertas se leen mucho más de lo que se escriben (se publican una vez y se consultan miles de veces).
- En `postulaciones`, que es la colección con más escrituras (cambios de estado), mantuvimos solo los dos índices indispensables y no agregamos uno para ordenar por fecha (explain 4).

---

## 6. Primeras pruebas de consistencia

[`06_consistencia_inicial.js`](../db/scripts/06_consistencia_inicial.js) trabaja sobre documentos temporales que se eliminan al terminar. Al final, `03_verificacion.js` sigue dando todo OK. Salida completa en [`evidencia/06_consistencia_inicial.txt`](evidencia/06_consistencia_inicial.txt).

| Prueba | Mecanismo | Resultado |
| :--- | :--- | :--- |
| 1. Postularse dos veces a la misma oferta | Índice único `ux_usuario_oferta` | Rechazada con `E11000` |
| 2a. Dos reclutadores aceptan a la vez con 1 vacante, leyendo y después escribiendo | — (enfoque ingenuo) | **Se aceptan 2 candidatos con 1 vacante**: la segunda escritura pisa a la primera |
| 2b. Lo mismo con `updateOne({..., "vacantes.disponibles": {$gt: 0}}, {$inc: -1})` | Operación atómica condicional sobre un documento | La primera modifica 1 documento y la segunda 0: no hay sobrecupo |
| 2c. Forzar `vacantes.disponibles` negativo | Validador `$jsonSchema` (`minimum: 0`) | Rechazado con código 121 |
| 3. Pasar una postulación rechazada a "entrevista" | Filtro por estado de origen dentro del `updateOne` (`$set` + `$push`) | No se modifica. Desde "en revisión" sí, y estado e historial cambian juntos |
| 4. Transacción que escribe en `ofertas` y `postulaciones` y falla antes del commit | Transacción multidocumento + `abortTransaction()` | No queda ningún cambio parcial |

**Conclusiones para la Entrega 3:**

- Las operaciones que tocan **un solo documento** (descontar una vacante, cambiar el estado de una postulación) se resuelven con operaciones atómicas condicionales, sin transacción.
- **Aceptar un candidato** toca dos colecciones: la postulación pasa a aceptada y la oferta descuenta la vacante y eventualmente se cierra. La prueba 4 confirma que el entorno soporta transacciones y que un abort no deja cambios a medias. En la Entrega 3 esa operación se implementará como transacción en la API, usando dentro de ella el `$inc` condicional de la prueba 2b.

---

## 7. Pendiente para las próximas entregas

- **Entrega 3:**
  - API con CRUD de `usuarios`, con capa de repositorios.
  - Transacción "aceptar candidato".
  - Mantenimiento de las desnormalizaciones (`cantidadPostulaciones`, nombre de empresa) desde la capa de servicios.
- **Entrega 4:**
  - Notebook de análisis, partiendo de las consultas 7, 8, 9 y 11.
  - API como servicio dentro de Docker Compose.
