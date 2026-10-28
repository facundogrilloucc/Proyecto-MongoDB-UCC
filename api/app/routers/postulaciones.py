from fastapi import APIRouter, Depends

from ..schemas.postulaciones import CambioDeEstado, PostulacionRespuesta
from ..services.postulaciones import PostulacionesServicio
from .dependencias import postulaciones_servicio

router = APIRouter(prefix="/postulaciones", tags=["postulaciones"])


@router.get("/{id}", response_model=PostulacionRespuesta, response_model_exclude_unset=True,
            summary="Obtener una postulación", responses={404: {"description": "La postulación no existe"}})
def obtener(id: str, servicio: PostulacionesServicio = Depends(postulaciones_servicio)):
    return servicio.obtener(id)


@router.patch("/{id}/estado", response_model=PostulacionRespuesta, response_model_exclude_unset=True,
              summary="Cambiar el estado de una postulación",
              description=(
                  "Transiciones permitidas: enviada → en_revision → entrevista → aceptada. "
                  "Desde enviada, en_revision o entrevista también se puede pasar a rechazada o retirada.\n\n"
                  "Pasar a **aceptada** descuenta una vacante de la oferta (y la cierra si era la última) "
                  "dentro de una transacción. Pasar a **retirada** descuenta la postulación del contador de la oferta."
              ),
              responses={404: {"description": "La postulación no existe"},
                         409: {"description": "Transición no permitida o la oferta no tiene vacantes"}})
def cambiar_estado(id: str, cambio: CambioDeEstado,
                   servicio: PostulacionesServicio = Depends(postulaciones_servicio)):
    return servicio.cambiar_estado(id, cambio)
