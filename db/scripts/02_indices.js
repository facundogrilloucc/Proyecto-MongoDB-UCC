// 02_indices.js
// Crea los índices del proyecto. Se ejecuta después de la carga de datos.
// Uso: bin/mongosh.sh /scripts/02_indices.js
//
// La justificación de cada índice y el análisis con explain() están en
// docs/entrega-2.md y en 05_explain.js.

// usuarios ------------------------------------------------------------------
// Unicidad del email: dos perfiles no pueden compartir la misma cuenta.
db.usuarios.createIndex({ email: 1 }, { unique: true, name: "ux_email" });
// Multikey: búsqueda de candidatos por skill (consultas 5 y 10).
db.usuarios.createIndex({ skills: 1 }, { name: "ix_skills" });

// empresas ------------------------------------------------------------------
db.empresas.createIndex({ nombre: 1 }, { unique: true, name: "ux_nombre" });

// ofertas -------------------------------------------------------------------
// Búsqueda principal de ofertas (consulta 1). Sigue la regla ESR:
// primero los campos de igualdad (estado, seniority, moneda) y al final el rango (salario.min).
db.ofertas.createIndex(
  { estado: 1, seniority: 1, "salario.moneda": 1, "salario.min": 1 },
  { name: "ix_busqueda_ofertas" }
);
// Multikey: ofertas que piden una skill determinada.
db.ofertas.createIndex({ skillsRequeridas: 1 }, { name: "ix_skills_requeridas" });
// Búsqueda de texto libre sobre título y descripción (extensión opcional).
db.ofertas.createIndex(
  { titulo: "text", descripcion: "text" },
  { name: "tx_ofertas", default_language: "spanish", weights: { titulo: 3, descripcion: 1 } }
);

// postulaciones -------------------------------------------------------------
// Evita que un usuario se postule dos veces a la misma oferta.
// Por ser usuarioId el prefijo, también resuelve "mis postulaciones".
db.postulaciones.createIndex({ usuarioId: 1, ofertaId: 1 }, { unique: true, name: "ux_usuario_oferta" });
// Postulantes de una oferta, filtrados por estado.
db.postulaciones.createIndex({ ofertaId: 1, estado: 1 }, { name: "ix_oferta_estado" });

for (const nombre of ["usuarios", "empresas", "ofertas", "postulaciones"]) {
  const indices = db[nombre].getIndexes().map(i => i.name);
  print(`${nombre.padEnd(14)} ${indices.join(", ")}`);
}
