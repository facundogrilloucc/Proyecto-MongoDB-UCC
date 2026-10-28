from typing import Annotated

from fastapi import Depends, Query
from pymongo.database import Database

from ..database import obtener_db
from ..services.ofertas import OfertasServicio
from ..services.postulaciones import PostulacionesServicio
from ..services.usuarios import UsuariosServicio


def usuarios_servicio(db: Database = Depends(obtener_db)) -> UsuariosServicio:
    return UsuariosServicio(db)


def postulaciones_servicio(db: Database = Depends(obtener_db)) -> PostulacionesServicio:
    return PostulacionesServicio(db)


def ofertas_servicio(db: Database = Depends(obtener_db)) -> OfertasServicio:
    return OfertasServicio(db)


Limite = Annotated[int, Query(ge=1, le=100, description="Cantidad máxima de resultados")]
Desplazamiento = Annotated[int, Query(ge=0, description="Resultados a saltear (paginación)")]
