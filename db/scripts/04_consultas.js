// 04_consultas.js
// Consultas del dominio (sección 5.3 de la consigna).
// Uso: bin/mongosh.sh /scripts/04_consultas.js
//
// Cada consulta indica qué pregunta responde y qué tipo de consulta cubre.
// Los resultados se imprimen en una línea por documento para poder guardarlos
// como evidencia (docs/evidencia/04_consultas.txt).

// Fecha de referencia de los datos de prueba (la misma que usa seed/generar_datos.py).
const HOY = new Date("2026-10-27T12:00:00Z");
const DIA = 24 * 60 * 60 * 1000;
const SENIORITIES = ["junior", "semi-senior", "senior", "lead"];

function titulo(n, pregunta, tipo) {
  print(`\n${"=".repeat(100)}\nConsulta ${n} — ${pregunta}\nTipo: ${tipo}\n${"-".repeat(100)}`);
}
function mostrar(resultados) {
  const lista = Array.isArray(resultados) ? resultados : resultados.toArray();
  lista.forEach(doc => print(JSON.stringify(doc, (clave, valor) =>
    typeof valor === "string" && /^\d{4}-\d{2}-\d{2}T/.test(valor) ? valor.slice(0, 10) : valor)));
  print(`(${lista.length} resultado${lista.length === 1 ? "" : "s"})`);
}

// ------------------------------------------------------------------------------------------
titulo(1, "¿Qué ofertas abiertas para semi-senior pagan al menos $1.700.000 de mínimo?",
  "filtro con operadores de comparación ($gte) + ordenamiento");
mostrar(db.ofertas.find(
  { estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS", "salario.min": { $gte: 1_700_000 } },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, salario: 1 }
).sort({ "salario.min": -1 }));

// ------------------------------------------------------------------------------------------
titulo(2, "¿Qué postulaciones activas de los últimos 30 días tienen una coincidencia de skills alta (>= 75 %)?",
  "filtro con operadores de comparación ($gte, $nin) sobre números y fechas");
mostrar(db.postulaciones.find(
  {
    coincidenciaSkills: { $gte: 0.75 },
    fechaPostulacion: { $gte: new Date(HOY - 30 * DIA) },
    estado: { $nin: ["rechazada", "retirada"] }
  },
  { _id: 0, usuarioId: 1, ofertaId: 1, estado: 1, coincidenciaSkills: 1, fechaPostulacion: 1 }
).sort({ coincidenciaSkills: -1, fechaPostulacion: -1 }));

// ------------------------------------------------------------------------------------------
titulo(3, "¿A qué ofertas abiertas (no junior) puede aplicar alguien que vive en la provincia de Córdoba?",
  "operadores lógicos ($and implícito, $or, $ne, $in): remotas, o híbridas/presenciales en Córdoba");
mostrar(db.ofertas.find(
  {
    estado: "abierta",
    seniority: { $ne: "junior" },
    $or: [
      { modalidad: "remoto" },
      { modalidad: { $in: ["hibrido", "presencial"] }, "ubicacion.provincia": "Córdoba" }
    ]
  },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, ciudad: "$ubicacion.ciudad" }
).sort({ modalidad: 1, titulo: 1 }));

// ------------------------------------------------------------------------------------------
titulo(4, "¿Qué candidatos de Córdoba están disponibles, aceptan trabajo remoto y pretenden hasta $2.000.000?",
  "consulta sobre atributos anidados (ubicacion.*, preferencias.*, preferencias.salarioPretendido.*)");
mostrar(db.usuarios.find(
  {
    "ubicacion.provincia": "Córdoba",
    "preferencias.disponible": true,
    "preferencias.modalidades": "remoto",
    "preferencias.salarioPretendido.moneda": "ARS",
    "preferencias.salarioPretendido.monto": { $lte: 2_000_000 }
  },
  { _id: 0, nombre: 1, apellido: 1, seniority: 1, pretende: "$preferencias.salarioPretendido.monto" }
).sort({ "preferencias.salarioPretendido.monto": 1 }));

// ------------------------------------------------------------------------------------------
titulo(5, "¿Quiénes saben Python y SQL y trabajan hoy en una empresa registrada en la plataforma?",
  "consulta sobre arreglos: $all sobre skills y $elemMatch sobre el arreglo de experiencia (en el filtro y en la proyección)");
// La proyección posicional "experiencia.$" no sirve acá: el filtro toca dos arreglos
// (skills y experiencia) y MongoDB no puede saber a cuál se refiere el "$".
// La proyección con $elemMatch devuelve sólo el trabajo actual en una empresa registrada.
const trabajoActualRegistrado = { actual: true, empresaId: { $ne: null } };
mostrar(db.usuarios.find(
  { skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: trabajoActualRegistrado } },
  { _id: 0, nombre: 1, apellido: 1, skills: 1, experiencia: { $elemMatch: trabajoActualRegistrado } }
));

// ------------------------------------------------------------------------------------------
titulo(6, "¿Cuáles son las 10 ofertas abiertas mejor pagas en pesos?",
  "proyección (con campos calculados), ordenamiento y límite");
mostrar(db.ofertas.find(
  { estado: "abierta", "salario.moneda": "ARS" },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, salarioMax: "$salario.max" }
).sort({ "salario.max": -1, _id: 1 }).limit(10));

// ------------------------------------------------------------------------------------------
titulo(7, "¿Cómo es el embudo de selección de cada empresa y cuál es su tasa de aceptación?",
  "aggregate(): $group con conteos condicionales, $lookup a empresas, cálculo de tasas y $sort");
mostrar(db.postulaciones.aggregate([
  {
    $group: {
      _id: "$empresaId",
      postulaciones: { $sum: 1 },
      entrevistas: { $sum: { $cond: [{ $in: ["entrevista", "$historialEstados.estado"] }, 1, 0] } },
      aceptadas: { $sum: { $cond: [{ $eq: ["$estado", "aceptada"] }, 1, 0] } },
      retiradas: { $sum: { $cond: [{ $eq: ["$estado", "retirada"] }, 1, 0] } }
    }
  },
  { $lookup: { from: "empresas", localField: "_id", foreignField: "_id", as: "empresa" } },
  {
    $project: {
      _id: 0,
      empresa: { $first: "$empresa.nombre" },
      postulaciones: 1, entrevistas: 1, aceptadas: 1, retiradas: 1,
      // Se excluyen las retiradas: la empresa no llegó a decidir sobre ellas.
      tasaAceptacion: {
        $round: [{ $divide: ["$aceptadas", { $max: [1, { $subtract: ["$postulaciones", "$retiradas"] }] }] }, 3]
      }
    }
  },
  { $sort: { tasaAceptacion: -1, postulaciones: -1 } }
]));

// ------------------------------------------------------------------------------------------
titulo(8, "¿Qué skills piden las empresas más de lo que las ofrecen los candidatos (y al revés)?",
  "aggregate(): $unwind, $group, $unionWith entre ofertas y usuarios, y $facet");
const totalOfertas = db.ofertas.countDocuments();
const totalUsuarios = db.usuarios.countDocuments();
mostrar(db.ofertas.aggregate([
  // La demanda incluye las skills requeridas y las deseables (algunas, como git, sólo aparecen como deseables).
  { $project: { skill: { $setUnion: ["$skillsRequeridas", { $ifNull: ["$skillsDeseables", []] }] } } },
  { $unwind: "$skill" },
  { $group: { _id: "$skill", ofertas: { $sum: 1 } } },
  {
    $unionWith: {
      coll: "usuarios",
      pipeline: [{ $unwind: "$skills" }, { $group: { _id: "$skills", usuarios: { $sum: 1 } } }]
    }
  },
  // Junta los conteos de las dos colecciones para cada skill ($sum ignora el campo ausente).
  { $group: { _id: "$_id", ofertas: { $sum: "$ofertas" }, usuarios: { $sum: "$usuarios" } } },
  {
    $set: {
      pctOfertas: { $round: [{ $multiply: [100, { $divide: ["$ofertas", totalOfertas] }] }, 1] },
      pctUsuarios: { $round: [{ $multiply: [100, { $divide: ["$usuarios", totalUsuarios] }] }, 1] }
    }
  },
  { $set: { brecha: { $round: [{ $subtract: ["$pctOfertas", "$pctUsuarios"] }, 1] } } },
  {
    $facet: {
      masDemandadasQueOfrecidas: [{ $sort: { brecha: -1 } }, { $limit: 6 }],
      masOfrecidasQueDemandadas: [{ $sort: { brecha: 1 } }, { $limit: 4 }]
    }
  }
]));

// ------------------------------------------------------------------------------------------
titulo(9, "¿Cuánto se paga según el seniority y la moneda?",
  "agrupamiento con cálculos estadísticos ($avg, $min, $max, $stdDevPop, $sum)");
mostrar(db.ofertas.aggregate([
  { $match: { salario: { $exists: true } } },
  { $set: { salarioMedio: { $avg: ["$salario.min", "$salario.max"] } } },
  {
    $group: {
      _id: { seniority: "$seniority", moneda: "$salario.moneda" },
      ofertas: { $sum: 1 },
      promedio: { $avg: "$salarioMedio" },
      minimo: { $min: "$salario.min" },
      maximo: { $max: "$salario.max" },
      desvio: { $stdDevPop: "$salarioMedio" }
    }
  },
  {
    $project: {
      _id: 0, moneda: "$_id.moneda", seniority: "$_id.seniority", ofertas: 1, minimo: 1, maximo: 1,
      promedio: { $round: ["$promedio", 0] }, desvio: { $round: ["$desvio", 0] },
      orden: { $indexOfArray: [SENIORITIES, "$_id.seniority"] }
    }
  },
  { $sort: { moneda: 1, orden: 1 } },
  { $unset: "orden" }
]));

// ------------------------------------------------------------------------------------------
// Consulta de complejidad elegida por el equipo: matching de candidatos.
const oferta = db.ofertas.find({ estado: "abierta", "skillsRequeridas.3": { $exists: true } })
  .sort({ fechaPublicacion: -1 }).limit(1).next();
const compatibles = SENIORITIES.filter(s =>
  Math.abs(SENIORITIES.indexOf(s) - SENIORITIES.indexOf(oferta.seniority)) <= 1);

titulo(10, `¿Qué candidatos que todavía no se postularon encajan mejor con la oferta "${oferta.titulo}" de ${oferta.empresa.nombre}?`,
  "consulta adicional (matching): $setIntersection, cálculo de coincidencia, $lookup con pipeline y ranking");
print(`Skills requeridas: ${oferta.skillsRequeridas.join(", ")} | deseables: ${(oferta.skillsDeseables ?? []).join(", ") || "-"}`);
mostrar(db.usuarios.aggregate([
  // Prefiltro que aprovecha el índice multikey sobre skills.
  { $match: { skills: { $in: oferta.skillsRequeridas }, seniority: { $in: compatibles } } },
  {
    $set: {
      coincidentes: { $setIntersection: ["$skills", oferta.skillsRequeridas] },
      deseables: { $size: { $setIntersection: ["$skills", oferta.skillsDeseables ?? []] } }
    }
  },
  { $set: { coincidencia: { $round: [{ $divide: [{ $size: "$coincidentes" }, oferta.skillsRequeridas.length] }, 2] } } },
  { $match: { coincidencia: { $gte: 0.6 } } },
  // Descarta a quienes ya se postularon a esta oferta.
  {
    $lookup: {
      from: "postulaciones", localField: "_id", foreignField: "usuarioId",
      pipeline: [{ $match: { ofertaId: oferta._id } }],
      as: "yaPostulado"
    }
  },
  { $match: { yaPostulado: { $size: 0 } } },
  { $sort: { coincidencia: -1, deseables: -1, "preferencias.disponible": -1, apellido: 1 } },
  { $limit: 10 },
  {
    $project: {
      _id: 0, candidato: { $concat: ["$nombre", " ", "$apellido"] }, seniority: 1,
      coincidencia: 1, coincidentes: 1, deseables: 1, disponible: "$preferencias.disponible"
    }
  }
]));

// ------------------------------------------------------------------------------------------
titulo(11, "¿Cómo evolucionaron las postulaciones mes a mes?",
  "aggregate(): agrupamiento temporal con $dateTrunc y métricas por período");
mostrar(db.postulaciones.aggregate([
  {
    $group: {
      _id: { $dateTrunc: { date: "$fechaPostulacion", unit: "month" } },
      postulaciones: { $sum: 1 },
      aceptadas: { $sum: { $cond: [{ $eq: ["$estado", "aceptada"] }, 1, 0] } },
      coincidenciaPromedio: { $avg: "$coincidenciaSkills" }
    }
  },
  { $sort: { _id: 1 } },
  {
    $project: {
      _id: 0, mes: { $dateToString: { date: "$_id", format: "%Y-%m" } },
      postulaciones: 1, aceptadas: 1, coincidenciaPromedio: { $round: ["$coincidenciaPromedio", 2] }
    }
  }
]));

// ------------------------------------------------------------------------------------------
titulo(12, "¿Los años de experiencia declarados son coherentes con el seniority de cada perfil?",
  "aggregate(): $map + $dateDiff sobre el arreglo embebido de experiencia y estadísticas por grupo");
mostrar(db.usuarios.aggregate([
  {
    $set: {
      aniosExperiencia: {
        $divide: [{
          $sum: {
            $map: {
              input: "$experiencia",
              in: { $dateDiff: { startDate: "$$this.desde", endDate: { $ifNull: ["$$this.hasta", HOY] }, unit: "month" } }
            }
          }
        }, 12]
      }
    }
  },
  {
    $group: {
      _id: "$seniority",
      usuarios: { $sum: 1 },
      promedio: { $avg: "$aniosExperiencia" },
      minimo: { $min: "$aniosExperiencia" },
      maximo: { $max: "$aniosExperiencia" },
      sinExperiencia: { $sum: { $cond: [{ $eq: [{ $size: "$experiencia" }, 0] }, 1, 0] } }
    }
  },
  {
    $project: {
      _id: 0, seniority: "$_id", usuarios: 1, sinExperiencia: 1,
      promedio: { $round: ["$promedio", 1] }, minimo: { $round: ["$minimo", 1] }, maximo: { $round: ["$maximo", 1] },
      orden: { $indexOfArray: [SENIORITIES, "$_id"] }
    }
  },
  { $sort: { orden: 1 } },
  { $unset: "orden" }
]));

// ------------------------------------------------------------------------------------------
titulo(13, "¿Qué ofertas mencionan \"python\" y \"remoto\" en el título o la descripción?",
  "extensión: búsqueda de texto con índice text (idioma español) y ordenamiento por relevancia");
mostrar(db.ofertas.find(
  { $text: { $search: "python remoto" } },
  { _id: 0, titulo: 1, empresa: "$empresa.nombre", modalidad: 1, relevancia: { $meta: "textScore" } }
// _id desempata ofertas con la misma relevancia, para que el resultado sea siempre el mismo.
).sort({ relevancia: { $meta: "textScore" }, _id: 1 }).limit(8));
