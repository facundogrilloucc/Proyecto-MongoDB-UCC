from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database


class PostulacionesRepositorio:
    def __init__(self, db: Database):
        self.coleccion = db.postulaciones

    def crear(self, documento: dict, sesion: ClientSession | None = None) -> ObjectId:
        return self.coleccion.insert_one(documento, session=sesion).inserted_id

    def obtener(self, id: ObjectId, sesion: ClientSession | None = None) -> dict | None:
        return self.coleccion.find_one({"_id": id}, session=sesion)

    def listar(self, *, oferta_id: ObjectId | None = None, usuario_id: ObjectId | None = None,
               estado: str | None = None, limite: int, desplazamiento: int) -> tuple[int, list[dict]]:
        filtro: dict[str, Any] = {}
        orden: list[tuple[str, int]] = [("fechaPostulacion", -1), ("_id", 1)]
        if oferta_id:
            filtro["ofertaId"] = oferta_id  # índice ix_oferta_estado
            orden = [("coincidenciaSkills", -1)] + orden  # los mejores candidatos primero
        if usuario_id:
            filtro["usuarioId"] = usuario_id  # prefijo del índice ux_usuario_oferta
        if estado:
            filtro["estado"] = estado

        total = self.coleccion.count_documents(filtro)
        cursor = self.coleccion.find(filtro).sort(orden).skip(desplazamiento).limit(limite)
        return total, list(cursor)

    def cambiar_estado(self, id: ObjectId, *, desde: list[str], hacia: str, nota: str | None, fecha: datetime,
                       sesion: ClientSession | None = None) -> dict | None:
        """Cambia el estado y agrega la entrada al historial en una sola operación atómica.

        Sólo modifica la postulación si su estado actual está en `desde`; así una transición
        inválida (o una carrera con otra petición que ya la cambió) no modifica nada.
        Devuelve la postulación actualizada, o None si no se modificó.
        """
        entrada: dict[str, Any] = {"estado": hacia, "fecha": fecha}
        if nota:
            entrada["nota"] = nota
        return self.coleccion.find_one_and_update(
            {"_id": id, "estado": {"$in": desde}},
            {"$set": {"estado": hacia, "actualizadoEn": fecha}, "$push": {"historialEstados": entrada}},
            return_document=ReturnDocument.AFTER,
            session=sesion,
        )

    def de_usuario(self, usuario_id: ObjectId, sesion: ClientSession | None = None) -> list[dict]:
        return list(self.coleccion.find({"usuarioId": usuario_id}, {"ofertaId": 1, "estado": 1}, session=sesion))

    def eliminar_de_usuario(self, usuario_id: ObjectId, sesion: ClientSession | None = None) -> int:
        return self.coleccion.delete_many({"usuarioId": usuario_id}, session=sesion).deleted_count
