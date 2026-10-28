"""Configuración de los tests de integración.

Los tests corren contra un MongoDB real (el del Docker Compose), pero en una base
separada, `empleos_test`, para no tocar los datos de prueba del proyecto. Esa base se
crea copiando de `empleos` las colecciones con sus validadores y sus índices, así que
antes de correr los tests hay que haber ejecutado bin/reset_db.sh al menos una vez.
"""

import os
from datetime import datetime, timedelta, timezone

DB_ORIGEN = os.environ.get("MONGO_DB", "empleos")
DB_PRUEBAS = os.environ.get("MONGO_DB_PRUEBAS", "empleos_test")
os.environ["MONGO_DB"] = DB_PRUEBAS  # antes de importar la app: la API usa la base de pruebas

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pymongo import MongoClient  # noqa: E402
from pymongo.database import Database  # noqa: E402

from app.main import app  # noqa: E402

COLECCIONES = ["empresas", "usuarios", "ofertas", "postulaciones"]
AHORA = datetime.now(timezone.utc).replace(microsecond=0)


def _copiar_esquema(origen: Database, destino: Database) -> None:
    for info in origen.list_collections():
        nombre, opciones = info["name"], info.get("options", {})
        destino.create_collection(nombre, validator=opciones.get("validator", {}),
                                  validationLevel=opciones.get("validationLevel", "strict"),
                                  validationAction=opciones.get("validationAction", "error"))
        for indice in origen[nombre].list_indexes():
            if indice["name"] == "_id_":
                continue
            extras = {k: indice[k] for k in ("unique", "weights", "default_language") if k in indice}
            # Un índice de texto se describe por sus pesos, no por su clave interna (_fts).
            claves = ([(campo, "text") for campo in indice["weights"]] if "weights" in indice
                      else list(indice["key"].items()))
            destino[nombre].create_index(claves, name=indice["name"], **extras)


@pytest.fixture(scope="session")
def db():
    cliente = MongoClient(os.environ["MONGO_URI"], tz_aware=True)
    origen = cliente[DB_ORIGEN]
    if not set(COLECCIONES) <= set(origen.list_collection_names()):
        pytest.exit(f"La base '{DB_ORIGEN}' no tiene las colecciones: ejecutar bin/reset_db.sh", returncode=1)
    cliente.drop_database(DB_PRUEBAS)
    _copiar_esquema(origen, cliente[DB_PRUEBAS])
    yield cliente[DB_PRUEBAS]
    cliente.drop_database(DB_PRUEBAS)
    cliente.close()


@pytest.fixture(autouse=True)
def base_vacia(db):
    """Cada test empieza con las colecciones vacías (conservan validadores e índices)."""
    for nombre in COLECCIONES:
        db[nombre].delete_many({})


@pytest.fixture(scope="session")
def api(db):
    with TestClient(app) as cliente:
        yield cliente


# --------------------------------------------------------------------------- datos de prueba

class Fabrica:
    """Inserta documentos válidos directamente en la base, para preparar cada escenario."""

    def __init__(self, db: Database):
        self.db = db
        self.contador = 0

    def _siguiente(self) -> int:
        self.contador += 1
        return self.contador

    def empresa(self, nombre: str | None = None) -> dict:
        n = self._siguiente()
        documento = {"nombre": nombre or f"Empresa {n}", "industria": "Tecnología", "tamanio": "11-50",
                     "ubicacion": {"ciudad": "Córdoba", "provincia": "Córdoba", "pais": "Argentina"},
                     "creadoEn": AHORA, "actualizadoEn": AHORA}
        documento["_id"] = self.db.empresas.insert_one(documento).inserted_id
        return documento

    def usuario(self, **cambios) -> dict:
        n = self._siguiente()
        documento = {"nombre": "Usuario", "apellido": f"Prueba {n:03d}", "email": f"usuario{n}@example.com",
                     "seniority": "semi-senior",
                     "ubicacion": {"ciudad": "Córdoba", "provincia": "Córdoba", "pais": "Argentina"},
                     "skills": ["python", "mongodb", "docker"], "experiencia": [], "educacion": [],
                     "creadoEn": AHORA, "actualizadoEn": AHORA, **cambios}
        documento["_id"] = self.db.usuarios.insert_one(documento).inserted_id
        return documento

    def oferta(self, empresa: dict | None = None, *, vacantes: int = 1, estado: str = "abierta",
               skills: tuple[str, ...] = ("python", "mongodb", "sql")) -> dict:
        empresa = empresa or self.empresa()
        documento = {"empresa": {"empresaId": empresa["_id"], "nombre": empresa["nombre"]},
                     "titulo": "Backend Developer", "descripcion": "Oferta de prueba", "seniority": "semi-senior",
                     "modalidad": "remoto", "skillsRequeridas": list(skills),
                     "vacantes": {"total": vacantes, "disponibles": vacantes}, "estado": estado,
                     "cantidadPostulaciones": 0, "fechaPublicacion": AHORA - timedelta(days=10),
                     "fechaCierre": AHORA if estado == "cerrada" else None,
                     "creadoEn": AHORA, "actualizadoEn": AHORA}
        documento["_id"] = self.db.ofertas.insert_one(documento).inserted_id
        return documento

    def postulacion(self, usuario: dict, oferta: dict, estado: str = "entrevista") -> dict:
        """Crea una postulación ya avanzada hasta `estado` y mantiene coherentes los contadores de la oferta."""
        caminos = {"enviada": ["enviada"], "en_revision": ["enviada", "en_revision"],
                   "entrevista": ["enviada", "en_revision", "entrevista"],
                   "aceptada": ["enviada", "en_revision", "entrevista", "aceptada"],
                   "rechazada": ["enviada", "rechazada"], "retirada": ["enviada", "retirada"]}
        historial = [{"estado": e, "fecha": AHORA - timedelta(days=5 - i)} for i, e in enumerate(caminos[estado])]
        documento = {"usuarioId": usuario["_id"], "ofertaId": oferta["_id"],
                     "empresaId": oferta["empresa"]["empresaId"], "estado": estado, "coincidenciaSkills": 1.0,
                     "historialEstados": historial, "fechaPostulacion": historial[0]["fecha"],
                     "actualizadoEn": historial[-1]["fecha"]}
        documento["_id"] = self.db.postulaciones.insert_one(documento).inserted_id
        cambios = {}
        if estado != "retirada":
            cambios["cantidadPostulaciones"] = 1
        if estado == "aceptada":
            cambios["vacantes.disponibles"] = -1
        if cambios:
            self.db.ofertas.update_one({"_id": oferta["_id"]}, {"$inc": cambios})
        return documento


@pytest.fixture
def fabrica(db) -> Fabrica:
    return Fabrica(db)


def verificar_consistencia(db: Database) -> None:
    """Las mismas reglas que controla db/scripts/03_verificacion.js, para cada oferta."""
    for oferta in db.ofertas.find():
        postulaciones = list(db.postulaciones.find({"ofertaId": oferta["_id"]}))
        aceptadas = sum(p["estado"] == "aceptada" for p in postulaciones)
        no_retiradas = sum(p["estado"] != "retirada" for p in postulaciones)
        assert oferta["vacantes"]["disponibles"] == oferta["vacantes"]["total"] - aceptadas
        assert oferta["cantidadPostulaciones"] == no_retiradas
        if oferta["vacantes"]["disponibles"] == 0:
            assert oferta["estado"] == "cerrada"
