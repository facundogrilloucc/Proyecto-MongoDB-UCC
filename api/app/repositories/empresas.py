from bson import ObjectId
from pymongo.database import Database


class EmpresasRepositorio:
    def __init__(self, db: Database):
        self.coleccion = db.empresas

    def obtener(self, id: ObjectId) -> dict | None:
        return self.coleccion.find_one({"_id": id})

    def listar(self, *, industria: str | None, limite: int, desplazamiento: int) -> tuple[int, list[dict]]:
        filtro = {"industria": industria} if industria else {}
        total = self.coleccion.count_documents(filtro)
        cursor = self.coleccion.find(filtro).sort("nombre", 1).skip(desplazamiento).limit(limite)
        return total, list(cursor)

    def nombres(self, ids: list[ObjectId]) -> dict[ObjectId, str]:
        """Devuelve {id: nombre} de las empresas que existen entre los ids pedidos."""
        cursor = self.coleccion.find({"_id": {"$in": ids}}, {"nombre": 1})
        return {empresa["_id"]: empresa["nombre"] for empresa in cursor}
