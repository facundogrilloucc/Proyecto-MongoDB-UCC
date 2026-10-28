from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database

# Campos que se devuelven en los listados (el perfil completo sólo se lee de a uno).
CAMPOS_RESUMEN = {"nombre": 1, "apellido": 1, "titular": 1, "seniority": 1, "ubicacion": 1, "skills": 1}


class UsuariosRepositorio:
    def __init__(self, db: Database):
        self.coleccion = db.usuarios

    def crear(self, documento: dict, sesion: ClientSession | None = None) -> ObjectId:
        return self.coleccion.insert_one(documento, session=sesion).inserted_id

    def obtener(self, id: ObjectId, sesion: ClientSession | None = None) -> dict | None:
        return self.coleccion.find_one({"_id": id}, session=sesion)

    def listar(self, *, skills: list[str], seniority: str | None, provincia: str | None, ciudad: str | None,
               disponible: bool | None, limite: int, desplazamiento: int) -> tuple[int, list[dict]]:
        filtro: dict[str, Any] = {}
        if skills:
            filtro["skills"] = {"$all": skills}  # usa el índice multikey ix_skills
        if seniority:
            filtro["seniority"] = seniority
        if provincia:
            filtro["ubicacion.provincia"] = provincia
        if ciudad:
            filtro["ubicacion.ciudad"] = ciudad
        if disponible is not None:
            filtro["preferencias.disponible"] = disponible

        total = self.coleccion.count_documents(filtro)
        cursor = (self.coleccion.find(filtro, CAMPOS_RESUMEN)
                  .sort([("apellido", 1), ("nombre", 1), ("_id", 1)])
                  .skip(desplazamiento).limit(limite))
        return total, list(cursor)

    def actualizar(self, id: ObjectId, asignar: dict, quitar: list[str]) -> dict | None:
        cambios: dict[str, Any] = {"$set": asignar}
        if quitar:
            cambios["$unset"] = {campo: "" for campo in quitar}
        return self.coleccion.find_one_and_update({"_id": id}, cambios, return_document=ReturnDocument.AFTER)

    def eliminar(self, id: ObjectId, sesion: ClientSession | None = None) -> bool:
        return self.coleccion.delete_one({"_id": id}, session=sesion).deleted_count == 1
