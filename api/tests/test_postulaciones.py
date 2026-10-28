"""Tests de postulaciones y del caso de consistencia "aceptar candidato"."""

import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from bson import ObjectId

from app.errores import Conflicto
from app.repositories.ofertas import OfertasRepositorio
from app.schemas.postulaciones import CambioDeEstado
from app.services.postulaciones import PostulacionesServicio

from .conftest import verificar_consistencia


def cambiar_estado(api, postulacion, estado):
    return api.patch(f"/postulaciones/{postulacion['_id']}/estado", json={"estado": estado})


# --------------------------------------------------------------------------- postularse

def test_postularse_crea_la_postulacion_y_suma_al_contador(api, db, fabrica):
    usuario = fabrica.usuario(skills=["python", "mongodb", "react"])
    oferta = fabrica.oferta(skills=("python", "mongodb", "sql"))

    respuesta = api.post(f"/ofertas/{oferta['_id']}/postulaciones",
                         json={"usuarioId": str(usuario["_id"]), "cartaPresentacion": "Me interesa"})

    assert respuesta.status_code == 201
    postulacion = respuesta.json()
    assert postulacion["estado"] == "enviada"
    assert postulacion["coincidenciaSkills"] == 0.67  # 2 de las 3 skills requeridas
    assert postulacion["empresaId"] == str(oferta["empresa"]["empresaId"])
    assert [h["estado"] for h in postulacion["historialEstados"]] == ["enviada"]
    assert db.ofertas.find_one({"_id": oferta["_id"]})["cantidadPostulaciones"] == 1
    verificar_consistencia(db)


def test_postularse_dos_veces_devuelve_409_y_no_cambia_el_contador(api, db, fabrica):
    usuario, oferta = fabrica.usuario(), fabrica.oferta()
    cuerpo = {"usuarioId": str(usuario["_id"])}
    assert api.post(f"/ofertas/{oferta['_id']}/postulaciones", json=cuerpo).status_code == 201

    respuesta = api.post(f"/ofertas/{oferta['_id']}/postulaciones", json=cuerpo)

    assert respuesta.status_code == 409
    assert db.postulaciones.count_documents({}) == 1
    assert db.ofertas.find_one({"_id": oferta["_id"]})["cantidadPostulaciones"] == 1


@pytest.mark.parametrize("estado", ["pausada", "cerrada"])
def test_postularse_a_una_oferta_no_abierta_devuelve_409(api, db, fabrica, estado):
    usuario, oferta = fabrica.usuario(), fabrica.oferta(estado=estado)

    respuesta = api.post(f"/ofertas/{oferta['_id']}/postulaciones", json={"usuarioId": str(usuario["_id"])})

    assert respuesta.status_code == 409
    assert db.postulaciones.count_documents({}) == 0


def test_postularse_con_usuario_u_oferta_inexistente_devuelve_404(api, fabrica):
    usuario, oferta = fabrica.usuario(), fabrica.oferta()

    sin_usuario = api.post(f"/ofertas/{oferta['_id']}/postulaciones", json={"usuarioId": str(ObjectId())})
    sin_oferta = api.post(f"/ofertas/{ObjectId()}/postulaciones", json={"usuarioId": str(usuario["_id"])})

    assert sin_usuario.status_code == 404
    assert sin_oferta.status_code == 404


# --------------------------------------------------------------------------- transiciones de estado

def test_transiciones_validas_actualizan_estado_e_historial(api, fabrica):
    postulacion = fabrica.postulacion(fabrica.usuario(), fabrica.oferta(), "enviada")

    assert cambiar_estado(api, postulacion, "en_revision").status_code == 200
    respuesta = api.patch(f"/postulaciones/{postulacion['_id']}/estado",
                          json={"estado": "entrevista", "nota": "Entrevista técnica el lunes"})

    assert respuesta.status_code == 200
    cuerpo = respuesta.json()
    assert cuerpo["estado"] == "entrevista"
    assert [h["estado"] for h in cuerpo["historialEstados"]] == ["enviada", "en_revision", "entrevista"]
    assert cuerpo["historialEstados"][-1]["nota"] == "Entrevista técnica el lunes"


@pytest.mark.parametrize("actual, destino", [
    ("enviada", "aceptada"),      # no se puede saltear la entrevista
    ("rechazada", "entrevista"),  # los estados finales no cambian
    ("retirada", "en_revision"),
    ("aceptada", "rechazada"),
])
def test_transicion_no_permitida_devuelve_409_sin_modificar(api, db, fabrica, actual, destino):
    postulacion = fabrica.postulacion(fabrica.usuario(), fabrica.oferta(vacantes=2), actual)

    respuesta = cambiar_estado(api, postulacion, destino)

    assert respuesta.status_code == 409
    assert db.postulaciones.find_one({"_id": postulacion["_id"]}) == postulacion
    verificar_consistencia(db)


def test_cambiar_estado_de_postulacion_inexistente_devuelve_404(api):
    respuesta = api.patch(f"/postulaciones/{ObjectId()}/estado", json={"estado": "en_revision"})

    assert respuesta.status_code == 404


def test_retirar_resta_la_postulacion_del_contador(api, db, fabrica):
    oferta = fabrica.oferta()
    postulacion = fabrica.postulacion(fabrica.usuario(), oferta, "en_revision")

    assert cambiar_estado(api, postulacion, "retirada").status_code == 200

    assert db.ofertas.find_one({"_id": oferta["_id"]})["cantidadPostulaciones"] == 0
    verificar_consistencia(db)


# --------------------------------------------------------------------------- aceptar candidato (transacción)

def test_aceptar_descuenta_una_vacante_y_la_oferta_sigue_abierta(api, db, fabrica):
    oferta = fabrica.oferta(vacantes=2)
    postulacion = fabrica.postulacion(fabrica.usuario(), oferta, "entrevista")

    respuesta = cambiar_estado(api, postulacion, "aceptada")

    assert respuesta.status_code == 200
    assert respuesta.json()["estado"] == "aceptada"
    actualizada = db.ofertas.find_one({"_id": oferta["_id"]})
    assert actualizada["vacantes"]["disponibles"] == 1
    assert actualizada["estado"] == "abierta"
    verificar_consistencia(db)


def test_aceptar_la_ultima_vacante_cierra_la_oferta(api, db, fabrica):
    oferta = fabrica.oferta(vacantes=1)
    postulacion = fabrica.postulacion(fabrica.usuario(), oferta, "entrevista")

    assert cambiar_estado(api, postulacion, "aceptada").status_code == 200

    cerrada = db.ofertas.find_one({"_id": oferta["_id"]})
    assert cerrada["vacantes"]["disponibles"] == 0
    assert cerrada["estado"] == "cerrada"
    assert cerrada["fechaCierre"] is not None
    verificar_consistencia(db)


def test_aceptar_sin_vacantes_devuelve_409_y_deshace_el_cambio_de_la_postulacion(api, db, fabrica):
    """El paso 1 (postulación -> aceptada) se ejecuta, pero el paso 2 falla porque la oferta
    ya no tiene vacantes: la transacción se aborta y la postulación vuelve a 'entrevista'."""
    oferta = fabrica.oferta(vacantes=1)
    fabrica.postulacion(fabrica.usuario(), oferta, "aceptada")
    db.ofertas.update_one({"_id": oferta["_id"]}, {"$set": {"estado": "cerrada", "fechaCierre": oferta["creadoEn"]}})
    pendiente = fabrica.postulacion(fabrica.usuario(), oferta, "entrevista")

    respuesta = cambiar_estado(api, pendiente, "aceptada")

    assert respuesta.status_code == 409
    assert "vacantes" in respuesta.json()["detalle"]
    assert db.postulaciones.find_one({"_id": pendiente["_id"]}) == pendiente  # ni estado ni historial cambiaron
    verificar_consistencia(db)


def test_falla_a_mitad_de_la_transaccion_no_deja_cambios_parciales(db, fabrica, monkeypatch):
    """Se simula una caída después de las dos primeras escrituras (postulación aceptada y
    vacante descontada) y antes de cerrar la oferta. Sin transacción, la base quedaría con
    la vacante descontada y la oferta abierta sin vacantes."""
    oferta = fabrica.oferta(vacantes=1)
    postulacion = fabrica.postulacion(fabrica.usuario(), oferta, "entrevista")
    oferta_antes = db.ofertas.find_one({"_id": oferta["_id"]})

    def falla_simulada(*args, **kwargs):
        raise RuntimeError("Falla simulada al cerrar la oferta")

    monkeypatch.setattr(OfertasRepositorio, "cerrar", falla_simulada)
    with pytest.raises(RuntimeError, match="Falla simulada"):
        PostulacionesServicio(db).cambiar_estado(str(postulacion["_id"]), CambioDeEstado(estado="aceptada"))

    assert db.postulaciones.find_one({"_id": postulacion["_id"]}) == postulacion
    assert db.ofertas.find_one({"_id": oferta["_id"]}) == oferta_antes
    verificar_consistencia(db)


def test_aceptaciones_simultaneas_no_superan_las_vacantes(db, fabrica):
    """Cinco reclutadores aceptan a la vez a cinco candidatos distintos para una sola vacante.

    Todas las transacciones modifican el mismo documento de la oferta: MongoDB detecta el
    conflicto de escritura, aborta las perdedoras y with_transaction las reintenta. En el
    reintento ya no hay vacantes, así que exactamente una aceptación tiene éxito.
    """
    oferta = fabrica.oferta(vacantes=1)
    postulaciones = [fabrica.postulacion(fabrica.usuario(), oferta, "entrevista") for _ in range(5)]
    largada = threading.Barrier(len(postulaciones))

    def aceptar(postulacion):
        largada.wait()  # todas arrancan al mismo tiempo
        try:
            PostulacionesServicio(db).cambiar_estado(str(postulacion["_id"]), CambioDeEstado(estado="aceptada"))
            return "aceptada"
        except Conflicto:
            return "rechazada por falta de vacantes"

    with ThreadPoolExecutor(max_workers=len(postulaciones)) as hilos:
        resultados = list(hilos.map(aceptar, postulaciones))

    assert resultados.count("aceptada") == 1
    assert resultados.count("rechazada por falta de vacantes") == 4
    assert db.postulaciones.count_documents({"ofertaId": oferta["_id"], "estado": "aceptada"}) == 1
    final = db.ofertas.find_one({"_id": oferta["_id"]})
    assert final["vacantes"]["disponibles"] == 0 and final["estado"] == "cerrada"
    verificar_consistencia(db)


# --------------------------------------------------------------------------- listados

def test_listar_postulantes_de_una_oferta_ordena_por_coincidencia(api, db, fabrica):
    oferta = fabrica.oferta(vacantes=3)
    baja = fabrica.postulacion(fabrica.usuario(), oferta, "enviada")
    alta = fabrica.postulacion(fabrica.usuario(), oferta, "enviada")
    db.postulaciones.update_one({"_id": baja["_id"]}, {"$set": {"coincidenciaSkills": 0.33}})

    pagina = api.get(f"/ofertas/{oferta['_id']}/postulaciones").json()

    assert pagina["total"] == 2
    assert [p["id"] for p in pagina["resultados"]] == [str(alta["_id"]), str(baja["_id"])]
    assert api.get(f"/ofertas/{ObjectId()}/postulaciones").status_code == 404
