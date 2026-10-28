"""Esquemas de la entidad principal: usuarios (perfiles profesionales)."""

from datetime import datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from .comunes import Entrada, Fecha, IdObjeto, Modalidad, Moneda, Seniority, Texto, Ubicacion

# Mismo patrón que el validador $jsonSchema de la colección.
Email = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, max_length=254,
                                         pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
# Las skills se normalizan en minúscula para que se puedan comparar con las de las ofertas.
Skill = Annotated[str, StringConstraints(strip_whitespace=True, to_lower=True, min_length=1, max_length=40)]


class Experiencia(Entrada):
    empresaId: IdObjeto | None = Field(None, description="Empresa registrada en la plataforma")
    empresaNombre: Texto | None = Field(None, description="Obligatorio si no se indica empresaId")
    puesto: Texto
    desde: Fecha
    hasta: Fecha | None = Field(None, description="null si es el trabajo actual")
    actual: bool | None = Field(None, description="Se calcula a partir de 'hasta'; si se envía, debe coincidir")
    descripcion: Texto | None = None

    @model_validator(mode="after")
    def validar_coherencia(self):
        if self.empresaId is None and self.empresaNombre is None:
            raise ValueError("Indicar empresaId (empresa registrada) o empresaNombre")
        if self.hasta is not None and self.hasta < self.desde:
            raise ValueError("'hasta' no puede ser anterior a 'desde'")
        if self.actual is not None and self.actual != (self.hasta is None):
            raise ValueError("'actual' es true sólo cuando 'hasta' es null")
        return self


class Educacion(Entrada):
    institucion: Texto
    titulo: Texto
    desde: Fecha
    hasta: Fecha | None = None
    estado: Literal["en_curso", "finalizado", "abandonado"]

    @model_validator(mode="after")
    def validar_fechas(self):
        if self.hasta is not None and self.hasta < self.desde:
            raise ValueError("'hasta' no puede ser anterior a 'desde'")
        return self


class Idioma(Entrada):
    idioma: Texto
    nivel: Literal["A1", "A2", "B1", "B2", "C1", "C2"]


class Certificacion(Entrada):
    nombre: Texto
    emisor: Texto
    fecha: Fecha


class SalarioPretendido(Entrada):
    monto: int = Field(ge=0)
    moneda: Moneda
    periodo: Literal["mensual", "anual"] = "mensual"


class Preferencias(Entrada):
    disponible: bool | None = None
    modalidades: list[Modalidad] | None = None
    salarioPretendido: SalarioPretendido | None = None


class Contacto(Entrada):
    telefono: Texto | None = None
    github: Texto | None = None


def _sin_repetidos(skills: list[str] | None) -> list[str] | None:
    return None if skills is None else list(dict.fromkeys(skills))


class UsuarioCrear(Entrada):
    nombre: Texto
    apellido: Texto
    email: Email
    titular: Texto | None = None
    seniority: Seniority
    ubicacion: Ubicacion
    skills: list[Skill] = Field(default_factory=list, max_length=50)
    experiencia: list[Experiencia] = Field(default_factory=list, max_length=30)
    educacion: list[Educacion] = Field(default_factory=list, max_length=20)
    idiomas: list[Idioma] | None = None
    certificaciones: list[Certificacion] | None = None
    preferencias: Preferencias | None = None
    contacto: Contacto | None = None

    _skills_sin_repetidos = field_validator("skills")(_sin_repetidos)


class UsuarioActualizar(Entrada):
    """Actualización parcial (PATCH): sólo se modifican los campos enviados.

    Enviar null en un campo opcional lo elimina del perfil; en un campo obligatorio es un error.
    Los arreglos (skills, experiencia, ...) se reemplazan completos.
    """
    nombre: Texto | None = None
    apellido: Texto | None = None
    email: Email | None = None
    titular: Texto | None = None
    seniority: Seniority | None = None
    ubicacion: Ubicacion | None = None
    skills: list[Skill] | None = Field(None, max_length=50)
    experiencia: list[Experiencia] | None = Field(None, max_length=30)
    educacion: list[Educacion] | None = Field(None, max_length=20)
    idiomas: list[Idioma] | None = None
    certificaciones: list[Certificacion] | None = None
    preferencias: Preferencias | None = None
    contacto: Contacto | None = None

    _skills_sin_repetidos = field_validator("skills")(_sin_repetidos)


class UsuarioRespuesta(UsuarioCrear):
    model_config = ConfigDict(extra="ignore")

    id: str
    creadoEn: datetime
    actualizadoEn: datetime


class UsuarioResumen(BaseModel):
    """Versión reducida para los listados: sin experiencia, educación ni datos de contacto."""
    id: str
    nombre: str
    apellido: str
    titular: str | None = None
    seniority: Seniority
    ubicacion: Ubicacion
    skills: list[str]
