from bson import ObjectId
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..database import en_transaccion
from ..errores import Conflicto, NoEncontrado
from ..repositories.ofertas import OfertasRepositorio
from ..repositories.postulaciones import PostulacionesRepositorio
from ..repositories.usuarios import UsuariosRepositorio
from ..schemas.postulaciones import CambioDeEstado, PostulacionCrear
from ..utils import a_json, a_object_id, ahora

# Transiciones permitidas: estado actual -> estados a los que puede pasar.
# aceptada, rechazada y retirada son finales.
TRANSICIONES = {
    "enviada": {"en_revision", "rechazada", "retirada"},
    "en_revision": {"entrevista", "rechazada", "retirada"},
    "entrevista": {"aceptada", "rechazada", "retirada"},
}


def estados_de_origen(destino: str) -> list[str]:
    return [origen for origen, destinos in TRANSICIONES.items() if destino in destinos]


class PostulacionesServicio:
    def __init__(self, db: Database):
        self.db = db
        self.postulaciones = PostulacionesRepositorio(db)
        self.ofertas = OfertasRepositorio(db)
        self.usuarios = UsuariosRepositorio(db)

    # ------------------------------------------------------------------ lectura

    def obtener(self, id: str) -> dict:
        postulacion = self.postulaciones.obtener(a_object_id(id))
        if postulacion is None:
            raise NoEncontrado(f"No existe la postulación {id}")
        return a_json(postulacion)

    def listar_de_oferta(self, oferta_id: str, estado: str | None, limite: int, desplazamiento: int) -> dict:
        id = a_object_id(oferta_id)
        if self.ofertas.obtener(id) is None:
            raise NoEncontrado(f"No existe la oferta {oferta_id}")
        total, resultados = self.postulaciones.listar(oferta_id=id, estado=estado, limite=limite,
                                                      desplazamiento=desplazamiento)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "resultados": a_json(resultados)}

    def listar_de_usuario(self, usuario_id: str, estado: str | None, limite: int, desplazamiento: int) -> dict:
        id = a_object_id(usuario_id)
        if self.usuarios.obtener(id) is None:
            raise NoEncontrado(f"No existe el usuario {usuario_id}")
        total, resultados = self.postulaciones.listar(usuario_id=id, estado=estado, limite=limite,
                                                      desplazamiento=desplazamiento)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "resultados": a_json(resultados)}

    # ------------------------------------------------------------------ postularse

    def postularse(self, oferta_id: str, datos: PostulacionCrear) -> dict:
        """Crea la postulación y suma 1 al contador de la oferta, en una transacción."""
        id_oferta, id_usuario = a_object_id(oferta_id), a_object_id(datos.usuarioId)

        def operacion(sesion: ClientSession) -> dict:
            usuario = self.usuarios.obtener(id_usuario, sesion)
            if usuario is None:
                raise NoEncontrado(f"No existe el usuario {datos.usuarioId}")
            oferta = self.ofertas.obtener(id_oferta, sesion)
            if oferta is None:
                raise NoEncontrado(f"No existe la oferta {oferta_id}")
            if oferta["estado"] != "abierta":
                raise Conflicto(f"La oferta está {oferta['estado']} y no recibe postulaciones")

            requeridas = set(oferta["skillsRequeridas"])
            fecha = ahora()
            documento = {
                "usuarioId": id_usuario,
                "ofertaId": id_oferta,
                "empresaId": oferta["empresa"]["empresaId"],
                "estado": "enviada",
                "coincidenciaSkills": round(len(requeridas & set(usuario["skills"])) / len(requeridas), 2),
                "historialEstados": [{"estado": "enviada", "fecha": fecha}],
                "fechaPostulacion": fecha,
                "actualizadoEn": fecha,
            }
            documento.update(datos.model_dump(exclude_none=True, exclude={"usuarioId"}))
            try:
                documento["_id"] = self.postulaciones.crear(documento, sesion)
            except DuplicateKeyError:
                raise Conflicto("El usuario ya se postuló a esta oferta")  # índice único ux_usuario_oferta
            # Condicionado a que la oferta siga abierta: si otra petición la cerró entre la
            # lectura y esta escritura, se aborta todo y la postulación tampoco queda creada.
            if not self.ofertas.incrementar_postulaciones(id_oferta, 1, sesion, solo_si_abierta=True):
                raise Conflicto("La oferta dejó de recibir postulaciones")
            return documento

        return a_json(en_transaccion(self.db, operacion))

    # ------------------------------------------------------------------ cambios de estado

    def cambiar_estado(self, id: str, cambio: CambioDeEstado) -> dict:
        postulacion_id = a_object_id(id)
        if cambio.estado == "aceptada":
            return a_json(self._aceptar(postulacion_id, cambio.nota))
        if cambio.estado == "retirada":
            return a_json(self._retirar(postulacion_id, cambio.nota))

        # en_revision, entrevista y rechazada sólo modifican la postulación:
        # alcanza con una operación atómica sobre un documento, sin transacción.
        postulacion = self.postulaciones.cambiar_estado(
            postulacion_id, desde=estados_de_origen(cambio.estado), hacia=cambio.estado, nota=cambio.nota,
            fecha=ahora())
        if postulacion is None:
            self._explicar_rechazo(postulacion_id, cambio.estado)
        return a_json(postulacion)

    def _aceptar(self, postulacion_id: ObjectId, nota: str | None) -> dict:
        """Acepta al candidato: caso de consistencia principal del proyecto.

        Tres escrituras en dos colecciones que deben aplicarse todas o ninguna:
          1. la postulación pasa a "aceptada" (y se agrega al historial);
          2. la oferta descuenta una vacante, sólo si está abierta y le queda alguna;
          3. si era la última vacante, la oferta se cierra.
        Si cualquier paso falla, la transacción se aborta y la postulación vuelve a su
        estado anterior. Si dos reclutadores aceptan a la vez la última vacante, una de
        las transacciones choca con la otra, MongoDB la reintenta, el paso 2 ya no
        encuentra vacantes y esa aceptación se rechaza.
        """
        def operacion(sesion: ClientSession) -> dict:
            fecha = ahora()
            postulacion = self.postulaciones.cambiar_estado(
                postulacion_id, desde=estados_de_origen("aceptada"), hacia="aceptada", nota=nota, fecha=fecha,
                sesion=sesion)
            if postulacion is None:
                self._explicar_rechazo(postulacion_id, "aceptada", sesion)

            oferta = self.ofertas.descontar_vacante(postulacion["ofertaId"], fecha, sesion)
            if oferta is None:
                raise Conflicto("La oferta no está abierta o ya no tiene vacantes disponibles")
            if oferta["vacantes"]["disponibles"] == 0:
                self.ofertas.cerrar(oferta["_id"], fecha, sesion)
            return postulacion

        return en_transaccion(self.db, operacion)

    def _retirar(self, postulacion_id: ObjectId, nota: str | None) -> dict:
        """El candidato retira su postulación: cambia el estado y resta 1 al contador de la oferta."""
        def operacion(sesion: ClientSession) -> dict:
            postulacion = self.postulaciones.cambiar_estado(
                postulacion_id, desde=estados_de_origen("retirada"), hacia="retirada", nota=nota, fecha=ahora(),
                sesion=sesion)
            if postulacion is None:
                self._explicar_rechazo(postulacion_id, "retirada", sesion)
            self.ofertas.incrementar_postulaciones(postulacion["ofertaId"], -1, sesion)
            return postulacion

        return en_transaccion(self.db, operacion)

    def _explicar_rechazo(self, postulacion_id: ObjectId, destino: str, sesion: ClientSession | None = None):
        """Se llama cuando un cambio de estado no modificó nada: distingue 404 de transición inválida."""
        actual = self.postulaciones.obtener(postulacion_id, sesion)
        if actual is None:
            raise NoEncontrado(f"No existe la postulación {postulacion_id}")
        raise Conflicto(f"Una postulación en estado '{actual['estado']}' no puede pasar a '{destino}'")
