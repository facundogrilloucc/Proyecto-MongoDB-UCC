"""Esquemas de postulaciones."""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

from .comunes import Entrada, EstadoPostulacion, IdObjeto, Moneda, Texto


class PretensionSalarial(Entrada):
    monto: int = Field(ge=0)
    moneda: Moneda


class PostulacionCrear(Entrada):
    usuarioId: IdObjeto
    cartaPresentacion: Texto | None = None
    pretensionSalarial: PretensionSalarial | None = None


class CambioDeEstado(Entrada):
    # "enviada" no figura: es el estado inicial y no se puede volver a él.
    estado: Literal["en_revision", "entrevista", "aceptada", "rechazada", "retirada"]
    nota: Texto | None = None


class EntradaHistorial(BaseModel):
    estado: EstadoPostulacion
    fecha: datetime
    nota: str | None = None


class PostulacionRespuesta(BaseModel):
    id: str
    usuarioId: str
    ofertaId: str
    empresaId: str
    estado: EstadoPostulacion
    coincidenciaSkills: float | None = None
    cartaPresentacion: str | None = None
    pretensionSalarial: PretensionSalarial | None = None
    historialEstados: list[EntradaHistorial]
    fechaPostulacion: datetime
    actualizadoEn: datetime
