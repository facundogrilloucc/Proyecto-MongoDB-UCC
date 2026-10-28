"""Tipos y modelos compartidos por los esquemas de la API."""

from datetime import datetime, timezone
from typing import Annotated, Generic, Literal, TypeVar

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints

Seniority = Literal["junior", "semi-senior", "senior", "lead"]
Modalidad = Literal["remoto", "hibrido", "presencial"]
Moneda = Literal["ARS", "USD"]
EstadoOferta = Literal["abierta", "pausada", "cerrada"]
EstadoPostulacion = Literal["enviada", "en_revision", "entrevista", "aceptada", "rechazada", "retirada"]

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=2000)]
IdObjeto = Annotated[str, Field(pattern=r"^[0-9a-f]{24}$", examples=["6710a1f0c1a2b3c4d5e6f101"])]


def _a_utc(valor: datetime) -> datetime:
    # Las fechas sin zona horaria se interpretan como UTC, igual que en MongoDB.
    return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


Fecha = Annotated[datetime, AfterValidator(_a_utc)]


class Entrada(BaseModel):
    """Base de los modelos que recibe la API: rechaza campos desconocidos."""
    model_config = ConfigDict(extra="forbid")


class Ubicacion(Entrada):
    ciudad: Texto
    provincia: Texto | None = None
    pais: Texto


T = TypeVar("T")


class Pagina(BaseModel, Generic[T]):
    total: int
    limite: int
    desplazamiento: int
    resultados: list[T]
