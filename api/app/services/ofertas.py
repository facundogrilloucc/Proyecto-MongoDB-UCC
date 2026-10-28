from pymongo.database import Database

from ..errores import DatosInvalidos, NoEncontrado
from ..repositories.empresas import EmpresasRepositorio
from ..repositories.ofertas import OfertasRepositorio
from ..utils import a_json, a_object_id


class OfertasServicio:
    """Consultas de ofertas y empresas (en esta entrega son de sólo lectura)."""

    def __init__(self, db: Database):
        self.ofertas = OfertasRepositorio(db)
        self.empresas = EmpresasRepositorio(db)

    def obtener_oferta(self, id: str) -> dict:
        oferta = self.ofertas.obtener(a_object_id(id))
        if oferta is None:
            raise NoEncontrado(f"No existe la oferta {id}")
        return a_json(oferta)

    def listar_ofertas(self, *, estado: str | None, seniority: str | None, modalidad: str | None, skills: list[str],
                       moneda: str | None, salario_minimo: int | None, limite: int, desplazamiento: int) -> dict:
        if salario_minimo is not None and moneda is None:
            # Comparar montos en pesos y en dólares no tiene sentido.
            raise DatosInvalidos("Para filtrar por salario mínimo hay que indicar la moneda")
        total, ofertas = self.ofertas.listar(
            estado=estado, seniority=seniority, modalidad=modalidad, skills=[s.strip().lower() for s in skills],
            moneda=moneda, salario_minimo=salario_minimo, limite=limite, desplazamiento=desplazamiento)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "resultados": a_json(ofertas)}

    def obtener_empresa(self, id: str) -> dict:
        empresa = self.empresas.obtener(a_object_id(id))
        if empresa is None:
            raise NoEncontrado(f"No existe la empresa {id}")
        return a_json(empresa)

    def listar_empresas(self, *, industria: str | None, limite: int, desplazamiento: int) -> dict:
        total, empresas = self.empresas.listar(industria=industria, limite=limite, desplazamiento=desplazamiento)
        return {"total": total, "limite": limite, "desplazamiento": desplazamiento, "resultados": a_json(empresas)}
