"""Punto de entrada de la API."""

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import DuplicateKeyError, PyMongoError, ServerSelectionTimeoutError, WriteError

from . import database
from .errores import ErrorDeDominio
from .routers import ofertas, postulaciones, usuarios


@asynccontextmanager
async def ciclo_de_vida(app: FastAPI):
    database.conectar()
    yield
    database.desconectar()


app = FastAPI(
    title="API Plataforma de Empleos",
    version="1.0.0",
    description="Trabajo práctico integrador de Base de Datos Aplicada (UCC). "
                "CRUD de usuarios (entidad principal), búsqueda de ofertas y gestión de postulaciones.",
    lifespan=ciclo_de_vida,
)
app.include_router(usuarios.router)
app.include_router(ofertas.router)
app.include_router(postulaciones.router)


def _error(estado_http: int, codigo: str, detalle: str, **extra) -> JSONResponse:
    return JSONResponse(status_code=estado_http, content={"error": codigo, "detalle": detalle, **extra})


@app.exception_handler(ErrorDeDominio)
def manejar_error_de_dominio(request: Request, error: ErrorDeDominio):
    return _error(error.estado_http, error.codigo, error.detalle)


@app.exception_handler(RequestValidationError)
def manejar_validacion(request: Request, error: RequestValidationError):
    """Errores de los esquemas de Pydantic, con el mismo formato que el resto de los errores."""
    errores = [{"campo": ".".join(str(parte) for parte in e["loc"]), "mensaje": e["msg"]} for e in error.errors()]
    return _error(422, "datos_invalidos", "La petición tiene datos inválidos", errores=errores)


# Redes de seguridad: errores de MongoDB que no debería producir la lógica de la API,
# pero que se traducen a una respuesta clara en lugar de un error 500 genérico.
@app.exception_handler(DuplicateKeyError)
def manejar_clave_duplicada(request: Request, error: DuplicateKeyError):
    return _error(409, "conflicto", "Ya existe un documento con esos datos únicos")


@app.exception_handler(WriteError)
def manejar_error_de_escritura(request: Request, error: WriteError):
    if error.code == 121:  # DocumentValidationFailure: lo rechazó el validador $jsonSchema
        return _error(422, "datos_invalidos", "El documento no cumple las reglas de validación de la colección")
    return _error(500, "error_base_de_datos", "Error al escribir en la base de datos")


@app.exception_handler(ServerSelectionTimeoutError)
def manejar_base_no_disponible(request: Request, error: ServerSelectionTimeoutError):
    return _error(503, "base_no_disponible", "No se pudo conectar con MongoDB")


@app.exception_handler(PyMongoError)
def manejar_error_de_mongo(request: Request, error: PyMongoError):
    return _error(500, "error_base_de_datos", "Error inesperado de la base de datos")


@app.get("/salud", tags=["sistema"], summary="Verificar que la API y la base estén funcionando")
def salud():
    database.obtener_db().command("ping")
    return {"estado": "ok"}
