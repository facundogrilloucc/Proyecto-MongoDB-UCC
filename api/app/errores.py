"""Errores de dominio. Cada uno sabe qué código HTTP le corresponde."""


class ErrorDeDominio(Exception):
    estado_http = 400
    codigo = "error"

    def __init__(self, detalle: str):
        super().__init__(detalle)
        self.detalle = detalle


class NoEncontrado(ErrorDeDominio):
    estado_http = 404
    codigo = "no_encontrado"


class Conflicto(ErrorDeDominio):
    """La operación es válida pero choca con el estado actual de los datos."""
    estado_http = 409
    codigo = "conflicto"


class DatosInvalidos(ErrorDeDominio):
    estado_http = 422
    codigo = "datos_invalidos"
