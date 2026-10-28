"""Conexión a MongoDB y ejecución de transacciones."""

import os
from typing import Callable, TypeVar

from pymongo import MongoClient, WriteConcern
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.read_concern import ReadConcern

T = TypeVar("T")

_cliente: MongoClient | None = None


def conectar() -> None:
    global _cliente
    _cliente = MongoClient(
        os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true"),
        tz_aware=True,  # las fechas se leen como datetime con zona horaria UTC
        serverSelectionTimeoutMS=5000,
    )


def desconectar() -> None:
    if _cliente is not None:
        _cliente.close()


def obtener_db() -> Database:
    """Dependencia de FastAPI: la base de datos del proyecto."""
    return _cliente[os.environ.get("MONGO_DB", "empleos")]


def en_transaccion(db: Database, operacion: Callable[[ClientSession], T]) -> T:
    """Ejecuta operacion(sesion) dentro de una transacción multidocumento.

    Si la operación lanza una excepción, la transacción se aborta y ninguna de sus
    escrituras queda aplicada. with_transaction además reintenta automáticamente ante
    errores transitorios, como un conflicto de escritura con otra transacción
    concurrente sobre el mismo documento; por eso la operación no debe tener efectos
    fuera de la base.
    """
    with db.client.start_session() as sesion:
        return sesion.with_transaction(
            operacion,
            read_concern=ReadConcern("snapshot"),
            write_concern=WriteConcern("majority"),
        )
