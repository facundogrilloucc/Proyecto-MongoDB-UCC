from datetime import datetime, timezone
from typing import Any

from bson import ObjectId

from .errores import DatosInvalidos


def ahora() -> datetime:
    # MongoDB guarda las fechas con precisión de milisegundos: se trunca para que lo que
    # devuelve la API al crear sea idéntico a lo que se lee después de la base.
    momento = datetime.now(timezone.utc)
    return momento.replace(microsecond=momento.microsecond // 1000 * 1000)


def a_object_id(valor: str) -> ObjectId:
    if not ObjectId.is_valid(valor):
        raise DatosInvalidos(f"'{valor}' no es un identificador válido")
    return ObjectId(valor)


def a_json(valor: Any) -> Any:
    """Convierte un documento de MongoDB al formato de la API: ObjectId -> str y _id -> id."""
    if isinstance(valor, ObjectId):
        return str(valor)
    if isinstance(valor, list):
        return [a_json(v) for v in valor]
    if isinstance(valor, dict):
        return {("id" if clave == "_id" else clave): a_json(v) for clave, v in valor.items()}
    return valor
