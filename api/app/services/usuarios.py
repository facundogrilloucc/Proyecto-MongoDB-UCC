from collections import Counter
from typing import Any

from bson import ObjectId
from pydantic import BaseModel
from pymongo.client_session import ClientSession
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..database import en_transaccion
from ..errores import Conflicto, DatosInvalidos, NoEncontrado
from ..repositories.empresas import EmpresasRepositorio
from ..repositories.ofertas import OfertasRepositorio
from ..repositories.postulaciones import PostulacionesRepositorio
from ..repositories.usuarios import UsuariosRepositorio
from ..schemas.usuarios import UsuarioActualizar, UsuarioCrear
from ..utils import a_json, a_object_id, ahora

CAMPOS_OBLIGATORIOS = {"nombre", "apellido", "email", "seniority", "ubicacion", "skills", "experiencia", "educacion"}


def _a_documento(valor: Any) -> Any:
    """Convierte modelos de Pydantic en diccionarios para MongoDB, sin los campos vacíos."""
    if isinstance(valor, BaseModel):
        return valor.model_dump(exclude_none=True)
    if isinstance(valor, list):
        return [_a_documento(v) for v in valor]
    return valor


class UsuariosServicio:
    def __init__(self, db: Database):
        self.db = db
        self.usuarios = UsuariosRepositorio(db)
        self.empresas = EmpresasRepositorio(db)
        self.ofertas = OfertasRepositorio(db)
        self.postulaciones = PostulacionesRepositorio(db)

    # ------------------------------------------------------------------ lectura

    def obtener(self, id: str) -> dict:
        usuario = self.usuarios.obtener(a_object_id(id))
        if usuario is None:
            raise NoEncontrado(f"No existe el usuario {id}")
        return a_json(usuario)

    def listar(self, *, skills: list[str], seniority: str | None, provincia: str | None, ciudad: str | None,
               disponible: bool | None, limite: int, desplazamiento: int) -> dict:
        total, usuarios = self.usuarios.listar(
            skills=[s.strip().lower() for s in skills], seniority=seniority, provincia=provincia, ciudad=ciudad,
            disponible=disponible, limite=limite, desplazamiento=desplazamiento)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "resultados": a_json(usuarios)}

    # ------------------------------------------------------------------ escritura

    def crear(self, datos: UsuarioCrear) -> dict:
        documento = datos.model_dump(exclude_none=True)
        documento["experiencia"] = self._preparar_experiencia(documento["experiencia"])
        for estudio in documento["educacion"]:
            estudio.setdefault("hasta", None)
        documento["creadoEn"] = documento["actualizadoEn"] = ahora()
        try:
            documento["_id"] = self.usuarios.crear(documento)
        except DuplicateKeyError:
            raise Conflicto(f"Ya existe un usuario con el email {datos.email}")
        return a_json(documento)

    def actualizar(self, id: str, datos: UsuarioActualizar) -> dict:
        enviados = datos.model_fields_set
        if not enviados:
            raise DatosInvalidos("No se envió ningún campo para actualizar")

        asignar, quitar = {}, []
        for campo in enviados:
            valor = getattr(datos, campo)
            if valor is None:
                if campo in CAMPOS_OBLIGATORIOS:
                    raise DatosInvalidos(f"'{campo}' es obligatorio y no puede ser null")
                quitar.append(campo)
            else:
                asignar[campo] = _a_documento(valor)
        if "experiencia" in asignar:
            asignar["experiencia"] = self._preparar_experiencia(asignar["experiencia"])
        for estudio in asignar.get("educacion", []):
            estudio.setdefault("hasta", None)
        asignar["actualizadoEn"] = ahora()

        try:
            usuario = self.usuarios.actualizar(a_object_id(id), asignar, quitar)
        except DuplicateKeyError:
            raise Conflicto(f"Ya existe un usuario con el email {datos.email}")
        if usuario is None:
            raise NoEncontrado(f"No existe el usuario {id}")
        return a_json(usuario)

    def eliminar(self, id: str) -> None:
        """Elimina el usuario y sus postulaciones, y descuenta esas postulaciones de cada oferta.

        Son escrituras en tres colecciones que tienen que aplicarse todas o ninguna:
        si se borrara el usuario y fallara el resto, quedarían postulaciones huérfanas
        y contadores de ofertas incorrectos. Por eso se hace en una transacción.
        """
        usuario_id = a_object_id(id)

        def operacion(sesion: ClientSession) -> None:
            if self.usuarios.obtener(usuario_id, sesion) is None:
                raise NoEncontrado(f"No existe el usuario {id}")
            postulaciones = self.postulaciones.de_usuario(usuario_id, sesion)
            if any(p["estado"] == "aceptada" for p in postulaciones):
                # Una contratación ya descontó una vacante: borrarla dejaría la oferta inconsistente.
                raise Conflicto("El usuario tiene contrataciones registradas y no puede eliminarse")
            activas = Counter(p["ofertaId"] for p in postulaciones if p["estado"] != "retirada")
            for oferta_id, cantidad in activas.items():
                self.ofertas.incrementar_postulaciones(oferta_id, -cantidad, sesion)
            self.postulaciones.eliminar_de_usuario(usuario_id, sesion)
            self.usuarios.eliminar(usuario_id, sesion)

        en_transaccion(self.db, operacion)

    # ------------------------------------------------------------------ auxiliares

    def _preparar_experiencia(self, experiencia: list[dict]) -> list[dict]:
        """Valida las empresas referenciadas y completa los campos derivados.

        - Si se indica empresaId, la empresa tiene que existir, y empresaNombre se toma
          de la colección empresas (desnormalización controlada: nunca lo decide el cliente).
        - `actual` se deriva de `hasta`.
        """
        ids = [ObjectId(e["empresaId"]) for e in experiencia if e.get("empresaId")]
        nombres = self.empresas.nombres(ids) if ids else {}
        resultado = []
        for trabajo in experiencia:
            empresa_id = ObjectId(trabajo["empresaId"]) if trabajo.get("empresaId") else None
            if empresa_id is not None and empresa_id not in nombres:
                raise DatosInvalidos(f"La empresa {empresa_id} no existe")
            preparado = {
                "empresaId": empresa_id,
                "empresaNombre": nombres[empresa_id] if empresa_id else trabajo["empresaNombre"],
                "puesto": trabajo["puesto"],
                "desde": trabajo["desde"],
                "hasta": trabajo.get("hasta"),
                "actual": trabajo.get("hasta") is None,
            }
            if trabajo.get("descripcion"):
                preparado["descripcion"] = trabajo["descripcion"]
            resultado.append(preparado)
        return resultado
