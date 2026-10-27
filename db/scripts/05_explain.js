// 05_explain.js
// Analiza con explain("executionStats") el uso de los índices en consultas relevantes.
// Para cada caso compara el plan elegido con un recorrido completo de la colección
// (hint({ $natural: 1 }) obliga a MongoDB a no usar índices).
// Uso: bin/mongosh.sh /scripts/05_explain.js

function etapas(plan) {
  if (!plan) return [];
  const propia = plan.stage + (plan.indexName ? `[${plan.indexName}]` : "");
  const hijas = [plan.inputStage, ...(plan.inputStages ?? [])].flatMap(etapas);
  return [propia, ...hijas];
}

function resumen(etiqueta, explicacion) {
  const plan = explicacion.queryPlanner.winningPlan;
  const s = explicacion.executionStats;
  print(`  ${etiqueta.padEnd(16)} plan: ${etapas(plan.queryPlan ?? plan).join(" <- ")}`);
  print(`  ${"".padEnd(16)} devueltos: ${s.nReturned} | claves examinadas: ${s.totalKeysExamined}` +
        ` | documentos examinados: ${s.totalDocsExamined} | tiempo: ${s.executionTimeMillis} ms`);
}

function comparar(n, descripcion, cursorConIndice, cursorSinIndice) {
  print(`\n${"=".repeat(100)}\nExplain ${n} — ${descripcion}\n${"-".repeat(100)}`);
  resumen("con índice", cursorConIndice.explain("executionStats"));
  if (cursorSinIndice) resumen("sin índice", cursorSinIndice.explain("executionStats"));
}

// 1. Búsqueda principal de ofertas (consulta 1) -> ix_busqueda_ofertas
const filtroOfertas = { estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS",
                        "salario.min": { $gte: 1_700_000 } };
comparar(1, "Ofertas abiertas semi-senior en ARS con salario mínimo >= 1.700.000 (consulta 1)",
  db.ofertas.find(filtroOfertas).sort({ "salario.min": -1 }),
  db.ofertas.find(filtroOfertas).sort({ "salario.min": -1 }).hint({ $natural: 1 }));

// 2. Candidatos por skills (consulta 5) -> ix_skills (multikey)
comparar(2, "Usuarios con python y sql (consulta 5)",
  db.usuarios.find({ skills: { $all: ["python", "sql"] } }),
  db.usuarios.find({ skills: { $all: ["python", "sql"] } }).hint({ $natural: 1 }));

// 3. Postulantes de una oferta por estado -> ix_oferta_estado
const ofertaPopular = db.ofertas.find().sort({ cantidadPostulaciones: -1 }).limit(1).next();
const filtroPostulantes = { ofertaId: ofertaPopular._id, estado: { $in: ["enviada", "en_revision", "entrevista"] } };
comparar(3, `Postulantes activos de la oferta con más postulaciones (${ofertaPopular.cantidadPostulaciones})`,
  db.postulaciones.find(filtroPostulantes),
  db.postulaciones.find(filtroPostulantes).hint({ $natural: 1 }));

// 4. Postulaciones de un usuario -> prefijo de ux_usuario_oferta
const usuario = db.postulaciones.aggregate([{ $sortByCount: "$usuarioId" }, { $limit: 1 }]).next();
comparar(4, `Postulaciones de un usuario ordenadas por fecha (${usuario.count} postulaciones)`,
  db.postulaciones.find({ usuarioId: usuario._id }).sort({ fechaPostulacion: -1 }),
  db.postulaciones.find({ usuarioId: usuario._id }).sort({ fechaPostulacion: -1 }).hint({ $natural: 1 }));

// 5. Top 10 mejor pagas (consulta 6): el índice resuelve el filtro, pero no el orden.
comparar(5, "Top 10 ofertas abiertas mejor pagas en ARS (consulta 6)",
  db.ofertas.find({ estado: "abierta", "salario.moneda": "ARS" }).sort({ "salario.max": -1 }).limit(10),
  db.ofertas.find({ estado: "abierta", "salario.moneda": "ARS" }).sort({ "salario.max": -1 }).limit(10)
    .hint({ $natural: 1 }));

// 6. Unicidad del email -> ux_email
const email = db.usuarios.findOne().email;
comparar(6, "Buscar un usuario por email (login / alta)",
  db.usuarios.find({ email }),
  db.usuarios.find({ email }).hint({ $natural: 1 }));

// Costo de almacenamiento de los índices --------------------------------------------------
print(`\n${"=".repeat(100)}\nTamaño de colecciones e índices (bytes)\n${"-".repeat(100)}`);
for (const nombre of ["usuarios", "empresas", "ofertas", "postulaciones"]) {
  const st = db[nombre].aggregate([{ $collStats: { storageStats: {} } }]).next().storageStats;
  print(`  ${nombre.padEnd(14)} datos: ${String(st.size).padStart(7)} | índices: ${String(st.totalIndexSize).padStart(7)} | ` +
        Object.entries(st.indexSizes).map(([k, v]) => `${k}=${v}`).join(", "));
}
