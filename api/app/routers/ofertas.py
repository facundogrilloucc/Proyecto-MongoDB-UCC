from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from ..schemas.comunes import EstadoOferta, EstadoPostulacion, Modalidad, Moneda, Pagina, Seniority
from ..schemas.ofertas import EmpresaRespuesta, OfertaRespuesta
from ..schemas.postulaciones import PostulacionCrear, PostulacionRespuesta
from ..services.ofertas import OfertasServicio
from ..services.postulaciones import PostulacionesServicio
from .dependencias import Desplazamiento, Limite, ofertas_servicio, postulaciones_servicio

router = APIRouter(tags=["ofertas y empresas"])


@router.get("/ofertas", response_model=Pagina[OfertaRespuesta], response_model_exclude_unset=True,
            summary="Buscar ofertas")
def listar_ofertas(estado: EstadoOferta | None = None,
                   seniority: Seniority | None = None,
                   modalidad: Modalidad | None = None,
                   skill: Annotated[list[str], Query(description="Repetible: la oferta debe pedirlas todas")] = [],
                   moneda: Moneda | None = None,
                   salarioMinimo: Annotated[int | None, Query(ge=0, description="Requiere moneda")] = None,
                   limite: Limite = 20,
                   desplazamiento: Desplazamiento = 0,
                   servicio: OfertasServicio = Depends(ofertas_servicio)):
    return servicio.listar_ofertas(estado=estado, seniority=seniority, modalidad=modalidad, skills=skill,
                                   moneda=moneda, salario_minimo=salarioMinimo, limite=limite,
                                   desplazamiento=desplazamiento)


@router.get("/ofertas/{id}", response_model=OfertaRespuesta, response_model_exclude_unset=True,
            summary="Obtener una oferta", responses={404: {"description": "La oferta no existe"}})
def obtener_oferta(id: str, servicio: OfertasServicio = Depends(ofertas_servicio)):
    return servicio.obtener_oferta(id)


@router.get("/ofertas/{id}/postulaciones", response_model=Pagina[PostulacionRespuesta],
            response_model_exclude_unset=True, summary="Postulantes de una oferta (mayor coincidencia primero)",
            responses={404: {"description": "La oferta no existe"}})
def postulantes(id: str,
                estado: EstadoPostulacion | None = None,
                limite: Limite = 20,
                desplazamiento: Desplazamiento = 0,
                servicio: PostulacionesServicio = Depends(postulaciones_servicio)):
    return servicio.listar_de_oferta(id, estado, limite, desplazamiento)


@router.post("/ofertas/{id}/postulaciones", status_code=status.HTTP_201_CREATED,
             response_model=PostulacionRespuesta, response_model_exclude_unset=True,
             summary="Postularse a una oferta",
             responses={404: {"description": "La oferta o el usuario no existen"},
                        409: {"description": "La oferta no está abierta o el usuario ya se postuló"}})
def postularse(id: str, datos: PostulacionCrear,
               servicio: PostulacionesServicio = Depends(postulaciones_servicio)):
    return servicio.postularse(id, datos)


@router.get("/empresas", response_model=Pagina[EmpresaRespuesta], response_model_exclude_unset=True,
            summary="Listar empresas")
def listar_empresas(industria: str | None = None,
                    limite: Limite = 20,
                    desplazamiento: Desplazamiento = 0,
                    servicio: OfertasServicio = Depends(ofertas_servicio)):
    return servicio.listar_empresas(industria=industria, limite=limite, desplazamiento=desplazamiento)


@router.get("/empresas/{id}", response_model=EmpresaRespuesta, response_model_exclude_unset=True,
            summary="Obtener una empresa", responses={404: {"description": "La empresa no existe"}})
def obtener_empresa(id: str, servicio: OfertasServicio = Depends(ofertas_servicio)):
    return servicio.obtener_empresa(id)
