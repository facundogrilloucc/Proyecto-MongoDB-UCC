// 01_colecciones.js
// Borra la base del proyecto y crea las colecciones con sus reglas de validación.
// Uso: bin/mongosh.sh /scripts/01_colecciones.js
//
// Las reglas combinan $jsonSchema (campos obligatorios, tipos y valores permitidos)
// con condiciones de consulta para reglas entre campos que $jsonSchema no puede
// expresar (por ejemplo, salario.min <= salario.max).

db.dropDatabase();
print(`Base "${db.getName()}" eliminada`);

const fecha = { bsonType: "date" };
const fechaONull = { bsonType: ["date", "null"] };
const texto = { bsonType: "string", minLength: 1 };
const entero = { bsonType: ["int", "long"] };
const SENIORITIES = ["junior", "semi-senior", "senior", "lead"];
const MODALIDADES = ["remoto", "hibrido", "presencial"];
const MONEDAS = ["ARS", "USD"];

const ubicacion = {
  bsonType: "object",
  required: ["ciudad", "pais"],
  properties: {
    ciudad: texto,
    provincia: texto,
    pais: texto
  }
};

const listaDeSkills = {
  bsonType: "array",
  uniqueItems: true,
  maxItems: 50,
  items: { bsonType: "string", minLength: 1 }
};

// ---------------------------------------------------------------- usuarios
db.createCollection("usuarios", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["nombre", "apellido", "email", "seniority", "ubicacion",
                 "skills", "experiencia", "educacion", "creadoEn", "actualizadoEn"],
      properties: {
        nombre: texto,
        apellido: texto,
        email: { bsonType: "string", pattern: "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$" },
        titular: texto,
        seniority: { enum: SENIORITIES },
        ubicacion: ubicacion,
        skills: listaDeSkills,
        experiencia: {
          bsonType: "array",
          maxItems: 30,
          items: {
            bsonType: "object",
            required: ["empresaNombre", "puesto", "desde", "hasta", "actual"],
            properties: {
              empresaId: { bsonType: ["objectId", "null"] },
              empresaNombre: texto,
              puesto: texto,
              desde: fecha,
              hasta: fechaONull,
              actual: { bsonType: "bool" },
              descripcion: texto
            }
          }
        },
        educacion: {
          bsonType: "array",
          maxItems: 20,
          items: {
            bsonType: "object",
            required: ["institucion", "titulo", "desde", "estado"],
            properties: {
              institucion: texto,
              titulo: texto,
              desde: fecha,
              hasta: fechaONull,
              estado: { enum: ["en_curso", "finalizado", "abandonado"] }
            }
          }
        },
        idiomas: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["idioma", "nivel"],
            properties: {
              idioma: texto,
              nivel: { enum: ["A1", "A2", "B1", "B2", "C1", "C2"] }
            }
          }
        },
        certificaciones: {
          bsonType: "array",
          items: {
            bsonType: "object",
            required: ["nombre", "emisor", "fecha"],
            properties: { nombre: texto, emisor: texto, fecha: fecha }
          }
        },
        preferencias: {
          bsonType: "object",
          properties: {
            disponible: { bsonType: "bool" },
            modalidades: { bsonType: "array", items: { enum: MODALIDADES } },
            salarioPretendido: {
              bsonType: "object",
              required: ["monto", "moneda", "periodo"],
              properties: {
                monto: { bsonType: ["int", "long"], minimum: 0 },
                moneda: { enum: MONEDAS },
                periodo: { enum: ["mensual", "anual"] }
              }
            }
          }
        },
        contacto: {
          bsonType: "object",
          properties: { telefono: texto, github: texto }
        },
        creadoEn: fecha,
        actualizadoEn: fecha
      }
    }
  }
});

// ---------------------------------------------------------------- empresas
db.createCollection("empresas", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["nombre", "industria", "tamanio", "ubicacion", "creadoEn", "actualizadoEn"],
      properties: {
        nombre: texto,
        industria: texto,
        tamanio: { enum: ["1-10", "11-50", "51-200", "201-1000", "1000+"] },
        ubicacion: ubicacion,
        sitioWeb: { bsonType: "string", pattern: "^https?://" },
        descripcion: texto,
        creadoEn: fecha,
        actualizadoEn: fecha
      }
    }
  }
});

// ---------------------------------------------------------------- ofertas
db.createCollection("ofertas", {
  validator: {
    $and: [
      {
        $jsonSchema: {
          bsonType: "object",
          required: ["empresa", "titulo", "descripcion", "seniority", "modalidad",
                     "skillsRequeridas", "vacantes", "estado", "cantidadPostulaciones",
                     "fechaPublicacion", "creadoEn", "actualizadoEn"],
          properties: {
            empresa: {
              bsonType: "object",
              required: ["empresaId", "nombre"],
              properties: { empresaId: { bsonType: "objectId" }, nombre: texto }
            },
            titulo: texto,
            descripcion: texto,
            seniority: { enum: SENIORITIES },
            modalidad: { enum: MODALIDADES },
            ubicacion: ubicacion,
            skillsRequeridas: { ...listaDeSkills, minItems: 1 },
            skillsDeseables: listaDeSkills,
            salario: {
              bsonType: "object",
              required: ["min", "max", "moneda", "periodo"],
              properties: {
                min: { ...entero, minimum: 0 },
                max: { ...entero, minimum: 0 },
                moneda: { enum: MONEDAS },
                periodo: { enum: ["mensual", "anual"] }
              }
            },
            vacantes: {
              bsonType: "object",
              required: ["total", "disponibles"],
              properties: {
                total: { ...entero, minimum: 1 },
                disponibles: { ...entero, minimum: 0 }
              }
            },
            estado: { enum: ["abierta", "pausada", "cerrada"] },
            cantidadPostulaciones: { ...entero, minimum: 0 },
            fechaPublicacion: fecha,
            fechaCierre: fechaONull,
            creadoEn: fecha,
            actualizadoEn: fecha
          }
        }
      },
      // Nunca puede haber más vacantes disponibles que el total.
      { $expr: { $lte: ["$vacantes.disponibles", "$vacantes.total"] } },
      // Si se publica el salario, el mínimo no puede superar al máximo.
      { $or: [{ salario: { $exists: false } },
              { $expr: { $lte: ["$salario.min", "$salario.max"] } }] },
      // Las ofertas que no son remotas tienen que indicar una ubicación.
      { $or: [{ modalidad: "remoto" }, { ubicacion: { $exists: true } }] }
    ]
  }
});

// ---------------------------------------------------------------- postulaciones
const ESTADOS_POSTULACION = ["enviada", "en_revision", "entrevista", "aceptada", "rechazada", "retirada"];

db.createCollection("postulaciones", {
  validator: {
    $jsonSchema: {
      bsonType: "object",
      required: ["usuarioId", "ofertaId", "empresaId", "estado", "historialEstados",
                 "fechaPostulacion", "actualizadoEn"],
      properties: {
        usuarioId: { bsonType: "objectId" },
        ofertaId: { bsonType: "objectId" },
        empresaId: { bsonType: "objectId" },
        estado: { enum: ESTADOS_POSTULACION },
        coincidenciaSkills: { bsonType: ["double", "int"], minimum: 0, maximum: 1 },
        cartaPresentacion: texto,
        pretensionSalarial: {
          bsonType: "object",
          required: ["monto", "moneda"],
          properties: {
            monto: { ...entero, minimum: 0 },
            moneda: { enum: MONEDAS }
          }
        },
        historialEstados: {
          bsonType: "array",
          minItems: 1,
          items: {
            bsonType: "object",
            required: ["estado", "fecha"],
            properties: {
              estado: { enum: ESTADOS_POSTULACION },
              fecha: fecha,
              nota: texto
            }
          }
        },
        fechaPostulacion: fecha,
        actualizadoEn: fecha
      }
    }
  }
});

print("Colecciones creadas: " + db.getCollectionNames().sort().join(", "));
