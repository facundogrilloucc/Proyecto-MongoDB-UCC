// 06_consistencia_inicial.js
// Primeras pruebas de consistencia (la transacción completa de "aceptar candidato"
// se implementa en la API en la Entrega 3).
// Uso: bin/mongosh.sh /scripts/06_consistencia_inicial.js
//
// Todas las pruebas trabajan sobre documentos temporales marcados con
// MARCA, que se eliminan al final.

const MARCA = "__prueba_consistencia__";
let fallas = 0;
function resultado(ok, texto) {
  if (!ok) fallas++;
  print(`${ok ? "OK   " : "FALLA"} ${texto}`);
}
function seccion(texto) {
  print(`\n${"=".repeat(100)}\n${texto}\n${"-".repeat(100)}`);
}

const empresa = db.empresas.findOne();
const ahora = new Date();
function crearOfertaDePrueba(vacantes) {
  return db.ofertas.insertOne({
    empresa: { empresaId: empresa._id, nombre: empresa.nombre }, titulo: MARCA, descripcion: MARCA,
    seniority: "junior", modalidad: "remoto", skillsRequeridas: ["python"],
    vacantes: { total: vacantes, disponibles: vacantes }, estado: "abierta", cantidadPostulaciones: 0,
    fechaPublicacion: ahora, fechaCierre: null, creadoEn: ahora, actualizadoEn: ahora
  }).insertedId;
}

// ------------------------------------------------------------------------------------------
seccion("Prueba 1 — Un usuario no puede postularse dos veces a la misma oferta (índice único)");
const existente = db.postulaciones.findOne({}, { _id: 0, usuarioId: 1, ofertaId: 1, empresaId: 1 });
try {
  db.postulaciones.insertOne({
    ...existente, estado: "enviada", historialEstados: [{ estado: "enviada", fecha: ahora }],
    fechaPostulacion: ahora, actualizadoEn: ahora
  });
  resultado(false, "Se insertó una postulación duplicada");
} catch (e) {
  resultado(e.code === 11000, `Postulación duplicada rechazada por ux_usuario_oferta (código ${e.code}, E11000)`);
}

// ------------------------------------------------------------------------------------------
seccion("Prueba 2 — Descontar una vacante: lectura-y-escritura vs. operación atómica condicional");
// Escenario: una oferta con 1 vacante y dos reclutadores que aceptan candidatos al mismo tiempo.

// a) Enfoque ingenuo: cada reclutador lee el valor y después escribe "leído - 1".
let id = crearOfertaDePrueba(1);
const leidoA = db.ofertas.findOne({ _id: id }).vacantes.disponibles;  // reclutador A lee 1
const leidoB = db.ofertas.findOne({ _id: id }).vacantes.disponibles;  // reclutador B lee 1
let aceptadas = 0;
for (const leido of [leidoA, leidoB]) {
  if (leido > 0) {
    db.ofertas.updateOne({ _id: id }, { $set: { "vacantes.disponibles": leido - 1 } });
    aceptadas++;
  }
}
print(`  Ingenuo: ${aceptadas} candidatos aceptados con 1 sola vacante; ` +
      `disponibles quedó en ${db.ofertas.findOne({ _id: id }).vacantes.disponibles} (la segunda escritura pisó a la primera)`);
resultado(aceptadas === 2, "El enfoque de leer y después escribir permite aceptar más candidatos que vacantes");

// b) Operación atómica: la condición y el descuento van en la misma operación sobre un documento.
id = crearOfertaDePrueba(1);
const descontar = () => db.ofertas.updateOne(
  { _id: id, estado: "abierta", "vacantes.disponibles": { $gt: 0 } },
  { $inc: { "vacantes.disponibles": -1 }, $set: { actualizadoEn: new Date() } }
).modifiedCount;
const primera = descontar();
const segunda = descontar();
print(`  Atómico: primera aceptación modificó ${primera} documento, segunda modificó ${segunda}; ` +
      `disponibles = ${db.ofertas.findOne({ _id: id }).vacantes.disponibles}`);
resultado(primera === 1 && segunda === 0, "Con $inc condicional la segunda aceptación se rechaza y no hay sobrecupo");

// c) El validador de la colección también impide un valor negativo aunque la aplicación se equivoque.
try {
  db.ofertas.updateOne({ _id: id }, { $inc: { "vacantes.disponibles": -1 } });
  resultado(false, "Se aceptó un valor negativo de vacantes");
} catch (e) {
  resultado(e.code === 121, `El validador rechaza vacantes.disponibles < 0 (código ${e.code}, DocumentValidationFailure)`);
}

// ------------------------------------------------------------------------------------------
seccion("Prueba 3 — Cambio de estado atómico con control de transiciones");
// Se actualiza el estado y se agrega la entrada al historial en un único updateOne.
// El filtro exige que el estado actual sea uno desde el que se puede pasar a "entrevista".
const rechazada = db.postulaciones.findOne({ estado: "rechazada" });
const pasarAEntrevista = (postulacion) => db.postulaciones.updateOne(
  { _id: postulacion._id, estado: { $in: ["enviada", "en_revision"] } },
  {
    $set: { estado: "entrevista", actualizadoEn: new Date() },
    $push: { historialEstados: { estado: "entrevista", fecha: new Date(), nota: MARCA } }
  }
).modifiedCount;
resultado(pasarAEntrevista(rechazada) === 0, "Una postulación rechazada no puede volver a 'entrevista'");

const enRevision = db.postulaciones.findOne({ estado: "en_revision" });
const largoAntes = enRevision.historialEstados.length;
resultado(pasarAEntrevista(enRevision) === 1, "Una postulación en revisión sí puede pasar a 'entrevista'");
const despues = db.postulaciones.findOne({ _id: enRevision._id });
resultado(despues.estado === "entrevista" && despues.historialEstados.length === largoAntes + 1,
  "El estado y el historial cambiaron juntos (una sola operación sobre un documento)");
// Se deshace el cambio para no alterar los datos de prueba.
db.postulaciones.replaceOne({ _id: enRevision._id }, enRevision);

// ------------------------------------------------------------------------------------------
seccion("Prueba 4 — El entorno admite transacciones multidocumento (replica set)");
id = crearOfertaDePrueba(1);
const sesion = db.getMongo().startSession();
const ofertasTx = sesion.getDatabase(db.getName()).ofertas;
const postulacionesTx = sesion.getDatabase(db.getName()).postulaciones;
sesion.startTransaction({ readConcern: { level: "snapshot" }, writeConcern: { w: "majority" } });
try {
  ofertasTx.updateOne({ _id: id }, { $inc: { "vacantes.disponibles": -1 } });
  postulacionesTx.insertOne({
    usuarioId: new ObjectId(), ofertaId: id, empresaId: empresa._id, estado: "aceptada",
    historialEstados: [{ estado: "aceptada", fecha: ahora, nota: MARCA }],
    fechaPostulacion: ahora, actualizadoEn: ahora
  });
  // Se simula una falla después de escribir en las dos colecciones.
  throw new Error("falla simulada antes del commit");
} catch (e) {
  sesion.abortTransaction();
  print(`  Transacción abortada: ${e.message}`);
} finally {
  sesion.endSession();
}
const ofertaTrasAbort = db.ofertas.findOne({ _id: id });
const postulacionesTrasAbort = db.postulaciones.countDocuments({ ofertaId: id });
resultado(ofertaTrasAbort.vacantes.disponibles === 1 && postulacionesTrasAbort === 0,
  "Tras el abort no quedó ningún cambio parcial: la vacante sigue disponible y no hay postulación");

// ------------------------------------------------------------------------------------------
const borradas = db.ofertas.deleteMany({ titulo: MARCA }).deletedCount;
print(`\nLimpieza: ${borradas} ofertas de prueba eliminadas.`);
print(fallas === 0 ? "Todas las pruebas pasaron." : `${fallas} prueba(s) fallaron.`);
