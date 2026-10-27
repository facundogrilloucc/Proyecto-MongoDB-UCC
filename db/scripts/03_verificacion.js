// 03_verificacion.js
// Verifica la cantidad de documentos, la consistencia básica entre colecciones
// y que las reglas de validación rechacen documentos inválidos.
// Uso: bin/mongosh.sh /scripts/03_verificacion.js

let errores = 0;
function chequear(descripcion, cantidadConProblemas) {
  const ok = cantidadConProblemas === 0;
  if (!ok) errores++;
  print(`${ok ? "OK   " : "FALLA"} ${descripcion}${ok ? "" : ` (${cantidadConProblemas} con problemas)`}`);
}
const contar = (coleccion, pipeline) =>
  db[coleccion].aggregate([...pipeline, { $count: "n" }]).toArray()[0]?.n ?? 0;

// 1. Cantidades -------------------------------------------------------------
print("== Cantidad de documentos");
let total = 0;
for (const nombre of ["empresas", "usuarios", "ofertas", "postulaciones"]) {
  const n = db[nombre].countDocuments();
  total += n;
  print(`   ${nombre.padEnd(14)} ${n}`);
}
print(`   ${"total".padEnd(14)} ${total}`);

// 2. Integridad referencial -------------------------------------------------
print("\n== Integridad referencial");
chequear("Toda oferta referencia a una empresa existente", contar("ofertas", [
  { $lookup: { from: "empresas", localField: "empresa.empresaId", foreignField: "_id", as: "e" } },
  { $match: { e: { $size: 0 } } }
]));
chequear("El nombre de empresa desnormalizado en la oferta coincide con el original", contar("ofertas", [
  { $lookup: { from: "empresas", localField: "empresa.empresaId", foreignField: "_id", as: "e" } },
  { $match: { $expr: { $ne: ["$empresa.nombre", { $first: "$e.nombre" }] } } }
]));
chequear("Toda postulación referencia a un usuario existente", contar("postulaciones", [
  { $lookup: { from: "usuarios", localField: "usuarioId", foreignField: "_id", as: "u" } },
  { $match: { u: { $size: 0 } } }
]));
chequear("Toda postulación referencia a una oferta existente y de la misma empresa", contar("postulaciones", [
  { $lookup: { from: "ofertas", localField: "ofertaId", foreignField: "_id", as: "o" } },
  { $match: { $expr: { $ne: ["$empresaId", { $first: "$o.empresa.empresaId" }] } } }
]));

// 3. Reglas de negocio ------------------------------------------------------
print("\n== Reglas de negocio");
chequear("vacantes.disponibles = total - postulaciones aceptadas", contar("ofertas", [
  { $lookup: { from: "postulaciones", localField: "_id", foreignField: "ofertaId", as: "p" } },
  { $match: { $expr: { $ne: ["$vacantes.disponibles", { $subtract: ["$vacantes.total",
      { $size: { $filter: { input: "$p", cond: { $eq: ["$$this.estado", "aceptada"] } } } }] }] } } }
]));
chequear("cantidadPostulaciones = postulaciones no retiradas", contar("ofertas", [
  { $lookup: { from: "postulaciones", localField: "_id", foreignField: "ofertaId", as: "p" } },
  { $match: { $expr: { $ne: ["$cantidadPostulaciones",
      { $size: { $filter: { input: "$p", cond: { $ne: ["$$this.estado", "retirada"] } } } }] } } }
]));
chequear("Ninguna oferta abierta o pausada se quedó sin vacantes",
  db.ofertas.countDocuments({ estado: { $ne: "cerrada" }, "vacantes.disponibles": 0 }));
chequear("Las ofertas cerradas tienen fecha de cierre y las demás no",
  db.ofertas.countDocuments({ $or: [{ estado: "cerrada", fechaCierre: null },
                                    { estado: { $ne: "cerrada" }, fechaCierre: { $ne: null } }] }));
chequear("El estado de la postulación coincide con el último paso de su historial", contar("postulaciones", [
  { $match: { $expr: { $ne: ["$estado", { $last: "$historialEstados.estado" }] } } }
]));
chequear("Nadie se postuló antes de que se publicara la oferta", contar("postulaciones", [
  { $lookup: { from: "ofertas", localField: "ofertaId", foreignField: "_id", as: "o" } },
  { $match: { $expr: { $lt: ["$fechaPostulacion", { $first: "$o.fechaPublicacion" }] } } }
]));

// 4. Casos límite presentes en los datos -------------------------------------
print("\n== Casos límite");
const casos = {
  "Usuarios sin experiencia laboral": db.usuarios.countDocuments({ experiencia: { $size: 0 } }),
  "Usuarios sin skills (perfil recién creado)": db.usuarios.countDocuments({ skills: { $size: 0 } }),
  "Usuarios sin preferencias": db.usuarios.countDocuments({ preferencias: { $exists: false } }),
  "Usuarios fuera de Argentina": db.usuarios.countDocuments({ "ubicacion.pais": { $ne: "Argentina" } }),
  "Usuarios con más de un trabajo actual": contar("usuarios", [
    { $match: { $expr: { $gt: [{ $size: { $filter: { input: "$experiencia", cond: "$$this.actual" } } }, 1] } } }]),
  "Experiencias en empresas no registradas": contar("usuarios", [
    { $unwind: "$experiencia" }, { $match: { "experiencia.empresaId": null } }]),
  "Empresas sin ofertas publicadas": contar("empresas", [
    { $lookup: { from: "ofertas", localField: "_id", foreignField: "empresa.empresaId", as: "o" } },
    { $match: { o: { $size: 0 } } }]),
  "Ofertas sin salario publicado": db.ofertas.countDocuments({ salario: { $exists: false } }),
  "Ofertas remotas sin ubicación": db.ofertas.countDocuments({ modalidad: "remoto", ubicacion: { $exists: false } }),
  "Ofertas cerradas sin vacantes disponibles": db.ofertas.countDocuments({ estado: "cerrada", "vacantes.disponibles": 0 }),
  "Ofertas pausadas": db.ofertas.countDocuments({ estado: "pausada" }),
  "Ofertas sin postulaciones": db.ofertas.countDocuments({ cantidadPostulaciones: 0 }),
};
for (const [descripcion, n] of Object.entries(casos)) print(`   ${descripcion.padEnd(46)} ${n}`);
print("   Postulaciones por estado: " + JSON.stringify(Object.fromEntries(
  db.postulaciones.aggregate([{ $group: { _id: "$estado", n: { $sum: 1 } } }, { $sort: { _id: 1 } }])
    .toArray().map(e => [e._id, e.n]))));

// 5. Las validaciones rechazan documentos inválidos --------------------------
print("\n== Validación de esquema (se espera que cada inserción falle)");
const empresa = db.empresas.findOne();
const ahora = new Date();
const invalidos = [
  ["usuarios", "email con formato inválido",
    { nombre: "Ana", apellido: "Paz", email: "ana-sin-arroba", seniority: "junior",
      ubicacion: { ciudad: "Córdoba", pais: "Argentina" }, skills: [], experiencia: [], educacion: [],
      creadoEn: ahora, actualizadoEn: ahora }],
  ["usuarios", "seniority fuera de los valores permitidos",
    { nombre: "Ana", apellido: "Paz", email: "ana@example.com", seniority: "experto",
      ubicacion: { ciudad: "Córdoba", pais: "Argentina" }, skills: [], experiencia: [], educacion: [],
      creadoEn: ahora, actualizadoEn: ahora }],
  ["usuarios", "skills repetidas",
    { nombre: "Ana", apellido: "Paz", email: "ana@example.com", seniority: "junior",
      ubicacion: { ciudad: "Córdoba", pais: "Argentina" }, skills: ["python", "python"], experiencia: [],
      educacion: [], creadoEn: ahora, actualizadoEn: ahora }],
  ["ofertas", "más vacantes disponibles que el total",
    { empresa: { empresaId: empresa._id, nombre: empresa.nombre }, titulo: "Test", descripcion: "Test",
      seniority: "junior", modalidad: "remoto", skillsRequeridas: ["python"],
      vacantes: { total: 1, disponibles: 3 }, estado: "abierta", cantidadPostulaciones: 0,
      fechaPublicacion: ahora, creadoEn: ahora, actualizadoEn: ahora }],
  ["ofertas", "salario mínimo mayor al máximo",
    { empresa: { empresaId: empresa._id, nombre: empresa.nombre }, titulo: "Test", descripcion: "Test",
      seniority: "junior", modalidad: "remoto", skillsRequeridas: ["python"],
      salario: { min: 2000000, max: 1000000, moneda: "ARS", periodo: "mensual" },
      vacantes: { total: 1, disponibles: 1 }, estado: "abierta", cantidadPostulaciones: 0,
      fechaPublicacion: ahora, creadoEn: ahora, actualizadoEn: ahora }],
  ["ofertas", "oferta presencial sin ubicación",
    { empresa: { empresaId: empresa._id, nombre: empresa.nombre }, titulo: "Test", descripcion: "Test",
      seniority: "junior", modalidad: "presencial", skillsRequeridas: ["python"],
      vacantes: { total: 1, disponibles: 1 }, estado: "abierta", cantidadPostulaciones: 0,
      fechaPublicacion: ahora, creadoEn: ahora, actualizadoEn: ahora }],
  ["postulaciones", "historial de estados vacío",
    { usuarioId: new ObjectId(), ofertaId: new ObjectId(), empresaId: empresa._id, estado: "enviada",
      historialEstados: [], fechaPostulacion: ahora, actualizadoEn: ahora }],
];
for (const [coleccion, descripcion, documento] of invalidos) {
  try {
    db[coleccion].insertOne(documento);
    errores++;
    print(`FALLA ${coleccion}: ${descripcion} -> se insertó y no debería`);
    db[coleccion].deleteOne({ _id: documento._id });
  } catch (e) {
    print(`OK    ${coleccion}: ${descripcion} -> rechazado (código ${e.code})`);
  }
}

print(errores === 0 ? "\nVerificación completa: sin errores." : `\nVerificación con ${errores} error(es).`);
