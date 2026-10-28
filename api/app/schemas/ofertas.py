"""Esquemas de empresas y ofertas (sólo lectura en esta entrega)."""

from datetime import datetime

from pydantic import BaseModel

from .comunes import EstadoOferta, Modalidad, Moneda, Seniority, Ubicacion


class EmpresaRespuesta(BaseModel):
    id: str
    nombre: str
    industria: str
    tamanio: str
    ubicacion: Ubicacion
    sitioWeb: str | None = None
    descripcion: str | None = None


class EmpresaReferencia(BaseModel):
    empresaId: str
    nombre: str


class Salario(BaseModel):
    min: int
    max: int
    moneda: Moneda
    periodo: str


class Vacantes(BaseModel):
    total: int
    disponibles: int


class OfertaRespuesta(BaseModel):
    id: str
    empresa: EmpresaReferencia
    titulo: str
    descripcion: str
    seniority: Seniority
    modalidad: Modalidad
    ubicacion: Ubicacion | None = None
    skillsRequeridas: list[str]
    skillsDeseables: list[str] | None = None
    salario: Salario | None = None
    vacantes: Vacantes
    estado: EstadoOferta
    cantidadPostulaciones: int
    fechaPublicacion: datetime
    fechaCierre: datetime | None = None
