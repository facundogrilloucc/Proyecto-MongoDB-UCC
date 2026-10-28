"""Capa de acceso a datos: el único lugar de la API que usa PyMongo sobre las colecciones.

Todos los métodos que escriben aceptan una sesión opcional para poder participar de
una transacción iniciada por la capa de servicios.
"""
