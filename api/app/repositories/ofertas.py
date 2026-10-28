from datetime import datetime
from typing import Any

from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.client_session import ClientSession
from pymongo.database import Database


class OfertasRepositorio:
    def __init__(self, db: Database):
        self.coleccion = db.ofertas

    def obtener(self, id: ObjectId, sesion: ClientSession | None = None) -> dict | None:
        return self.coleccion.find_one({"_id": id}, session=sesion)

    def listar(self, *, estado: str | None, seniority: str | None, modalidad: str | None, skills: list[str],
               moneda: str | None, salario_minimo: int | None, limite: int,
               desplazamiento: int) -> tuple[int, list[dict]]:
        filtro: dict[str, Any] = {}
        if estado:
            filtro["estado"] = estado
        if seniority:
            filtro["seniority"] = seniority
        if modalidad:
            filtro["modalidad"] = modalidad
        if skills:
            filtro["skillsRequeridas"] = {"$all": skills}
        if moneda:
            filtro["salario.moneda"] = moneda
        if salario_minimo is not None:
            filtro["salario.min"] = {"$gte": salario_minimo}

        total = self.coleccion.count_documents(filtro)
        cursor = (self.coleccion.find(filtro)
                  .sort([("fechaPublicacion", -1), ("_id", 1)])
                  .skip(desplazamiento).limit(limite))
        return total, list(cursor)

    def incrementar_postulaciones(self, id: ObjectId, cantidad: int, sesion: ClientSession | None = None,
                                  solo_si_abierta: bool = False) -> bool:
        filtro: dict[str, Any] = {"_id": id}
        if solo_si_abierta:
            filtro["estado"] = "abierta"
        resultado = self.coleccion.update_one(filtro, {"$inc": {"cantidadPostulaciones": cantidad}}, session=sesion)
        return resultado.modified_count == 1

    def descontar_vacante(self, id: ObjectId, fecha: datetime, sesion: ClientSession | None = None) -> dict | None:
        """Descuenta una vacante sólo si la oferta está abierta y le queda al menos una.

        La condición y el descuento van en la misma operación atómica, así que dos
        aceptaciones simultáneas nunca pueden dejar disponibles < 0. Devuelve la oferta
        ya actualizada, o None si no se pudo descontar.
        """
        return self.coleccion.find_one_and_update(
            {"_id": id, "estado": "abierta", "vacantes.disponibles": {"$gt": 0}},
            {"$inc": {"vacantes.disponibles": -1}, "$set": {"actualizadoEn": fecha}},
            return_document=ReturnDocument.AFTER,
            session=sesion,
        )

    def cerrar(self, id: ObjectId, fecha: datetime, sesion: ClientSession | None = None) -> None:
        self.coleccion.update_one(
            {"_id": id},
            {"$set": {"estado": "cerrada", "fechaCierre": fecha, "actualizadoEn": fecha}},
            session=sesion,
        )
