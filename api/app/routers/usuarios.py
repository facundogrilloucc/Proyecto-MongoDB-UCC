from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response, status

from ..schemas.comunes import EstadoPostulacion, Pagina, Seniority
from ..schemas.postulaciones import PostulacionRespuesta
from ..schemas.usuarios import UsuarioActualizar, UsuarioCrear, UsuarioRespuesta, UsuarioResumen
from ..services.postulaciones import PostulacionesServicio
from ..services.usuarios import UsuariosServicio
from .dependencias import Desplazamiento, Limite, postulaciones_servicio, usuarios_servicio

router = APIRouter(prefix="/usuarios", tags=["usuarios"])

ERRORES = {404: {"description": "El usuario no existe"}, 422: {"description": "Datos inválidos"}}


@router.post("", status_code=status.HTTP_201_CREATED, response_model=UsuarioRespuesta,
             response_model_exclude_unset=True, summary="Crear un usuario",
             responses={409: {"description": "El email ya está registrado"}, 422: ERRORES[422]})
def crear(datos: UsuarioCrear, servicio: UsuariosServicio = Depends(usuarios_servicio)):
    return servicio.crear(datos)


@router.get("", response_model=Pagina[UsuarioResumen], response_model_exclude_unset=True,
            summary="Listar usuarios con filtros")
def listar(skill: Annotated[list[str], Query(description="Repetible: el usuario debe tener todas")] = [],
           seniority: Seniority | None = None,
           provincia: str | None = None,
           ciudad: str | None = None,
           disponible: bool | None = None,
           limite: Limite = 20,
           desplazamiento: Desplazamiento = 0,
           servicio: UsuariosServicio = Depends(usuarios_servicio)):
    return servicio.listar(skills=skill, seniority=seniority, provincia=provincia, ciudad=ciudad,
                           disponible=disponible, limite=limite, desplazamiento=desplazamiento)


@router.get("/{id}", response_model=UsuarioRespuesta, response_model_exclude_unset=True,
            summary="Obtener un usuario por id", responses=ERRORES)
def obtener(id: str, servicio: UsuariosServicio = Depends(usuarios_servicio)):
    return servicio.obtener(id)


@router.patch("/{id}", response_model=UsuarioRespuesta, response_model_exclude_unset=True,
              summary="Actualizar parcialmente un usuario",
              responses={**ERRORES, 409: {"description": "El email ya está registrado"}})
def actualizar(id: str, datos: UsuarioActualizar, servicio: UsuariosServicio = Depends(usuarios_servicio)):
    return servicio.actualizar(id, datos)


@router.delete("/{id}", status_code=status.HTTP_204_NO_CONTENT, summary="Eliminar un usuario y sus postulaciones",
               responses={**ERRORES, 409: {"description": "El usuario tiene contrataciones registradas"}})
def eliminar(id: str, servicio: UsuariosServicio = Depends(usuarios_servicio)):
    servicio.eliminar(id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{id}/postulaciones", response_model=Pagina[PostulacionRespuesta], response_model_exclude_unset=True,
            summary="Postulaciones de un usuario", responses=ERRORES)
def postulaciones(id: str,
                  estado: EstadoPostulacion | None = None,
                  limite: Limite = 20,
                  desplazamiento: Desplazamiento = 0,
                  servicio: PostulacionesServicio = Depends(postulaciones_servicio)):
    return servicio.listar_de_usuario(id, estado, limite, desplazamiento)
