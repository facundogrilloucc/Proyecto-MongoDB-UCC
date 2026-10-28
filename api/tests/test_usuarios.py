"""Tests del CRUD de usuarios (entidad principal)."""

import pytest
from bson import ObjectId

from .conftest import verificar_consistencia


def usuario_valido(**cambios) -> dict:
    return {
        "nombre": "Ana",
        "apellido": "Paz",
        "email": "Ana.Paz@Example.com",
        "seniority": "semi-senior",
        "ubicacion": {"ciudad": "Córdoba", "provincia": "Córdoba", "pais": "Argentina"},
        "skills": ["Python", "MongoDB", "python", " Docker "],
        "experiencia": [{"empresaNombre": "Freelance", "puesto": "Desarrolladora", "desde": "2022-01-01",
                         "hasta": "2023-06-30"}],
        "educacion": [{"institucion": "UCC", "titulo": "Ingeniería en Sistemas", "desde": "2020-03-01",
                       "estado": "en_curso"}],
        **cambios,
    }


# --------------------------------------------------------------------------- crear

def test_crear_usuario_normaliza_y_completa_campos_derivados(api, fabrica):
    empresa = fabrica.empresa("Nubia Software")
    datos = usuario_valido(experiencia=[{"empresaId": str(empresa["_id"]), "empresaNombre": "Otro nombre",
                                         "puesto": "Backend Developer", "desde": "2024-03-01"}])

    respuesta = api.post("/usuarios", json=datos)

    assert respuesta.status_code == 201
    usuario = respuesta.json()
    assert ObjectId.is_valid(usuario["id"])
    assert usuario["email"] == "ana.paz@example.com"
    assert usuario["skills"] == ["python", "mongodb", "docker"]  # minúscula y sin repetidos
    trabajo = usuario["experiencia"][0]
    assert trabajo["empresaNombre"] == "Nubia Software"  # se toma de la colección empresas
    assert trabajo["hasta"] is None and trabajo["actual"] is True
    assert api.get(f"/usuarios/{usuario['id']}").json() == usuario


def test_crear_usuario_con_email_repetido_devuelve_409(api):
    assert api.post("/usuarios", json=usuario_valido()).status_code == 201

    respuesta = api.post("/usuarios", json=usuario_valido(nombre="Otra", email="ANA.PAZ@example.com"))

    assert respuesta.status_code == 409
    assert respuesta.json()["error"] == "conflicto"


@pytest.mark.parametrize("cambios", [
    {"email": "sin-arroba"},
    {"seniority": "experto"},
    {"nombre": ""},
    {"edad": 30},  # campo desconocido
    {"ubicacion": {"ciudad": "Córdoba"}},  # falta el país
    {"experiencia": [{"puesto": "Dev", "desde": "2022-01-01"}]},  # sin empresaId ni empresaNombre
    {"experiencia": [{"empresaNombre": "X", "puesto": "Dev", "desde": "2023-01-01", "hasta": "2022-01-01"}]},
    {"experiencia": [{"empresaNombre": "X", "puesto": "Dev", "desde": "2022-01-01", "actual": False}]},
    {"skills": [f"skill{i}" for i in range(51)]},
], ids=["email", "seniority", "nombre_vacio", "campo_desconocido", "sin_pais", "experiencia_sin_empresa",
        "fechas_invertidas", "actual_incoherente", "demasiadas_skills"])
def test_crear_usuario_con_datos_invalidos_devuelve_422(api, db, cambios):
    respuesta = api.post("/usuarios", json=usuario_valido(**cambios))

    assert respuesta.status_code == 422
    assert respuesta.json()["error"] == "datos_invalidos"
    assert respuesta.json()["errores"]  # indica qué campo falló
    assert db.usuarios.count_documents({}) == 0


def test_crear_usuario_con_empresa_inexistente_devuelve_422(api):
    datos = usuario_valido(experiencia=[{"empresaId": str(ObjectId()), "puesto": "Dev", "desde": "2022-01-01"}])

    respuesta = api.post("/usuarios", json=datos)

    assert respuesta.status_code == 422
    assert "no existe" in respuesta.json()["detalle"]


# --------------------------------------------------------------------------- obtener y listar

def test_obtener_usuario_inexistente_devuelve_404(api):
    respuesta = api.get(f"/usuarios/{ObjectId()}")

    assert respuesta.status_code == 404
    assert respuesta.json()["error"] == "no_encontrado"


def test_obtener_usuario_con_id_mal_formado_devuelve_422(api):
    assert api.get("/usuarios/no-es-un-id").status_code == 422


def test_listar_usuarios_filtra_y_pagina(api, fabrica):
    fabrica.usuario(skills=["python", "sql"], seniority="senior", preferencias={"disponible": True})
    fabrica.usuario(skills=["python", "sql", "docker"], seniority="junior")
    fabrica.usuario(skills=["java"], seniority="senior", ubicacion={"ciudad": "Rosario", "provincia": "Santa Fe",
                                                                   "pais": "Argentina"})

    def ids(parametros):
        return [u["apellido"] for u in api.get("/usuarios", params=parametros).json()["resultados"]]

    assert ids({"skill": ["python", "SQL"]}) == ["Prueba 001", "Prueba 002"]
    assert ids({"seniority": "senior"}) == ["Prueba 001", "Prueba 003"]
    assert ids({"provincia": "Santa Fe"}) == ["Prueba 003"]
    assert ids({"disponible": "true"}) == ["Prueba 001"]

    pagina = api.get("/usuarios", params={"limite": 2, "desplazamiento": 2}).json()
    assert pagina["total"] == 3 and len(pagina["resultados"]) == 1
    assert "experiencia" not in pagina["resultados"][0]  # los listados devuelven el resumen


# --------------------------------------------------------------------------- actualizar

def test_actualizar_modifica_solo_los_campos_enviados(api):
    creado = api.post("/usuarios", json=usuario_valido()).json()

    respuesta = api.patch(f"/usuarios/{creado['id']}", json={"titular": "Backend Dev", "skills": ["Go", "go"]})

    assert respuesta.status_code == 200
    usuario = respuesta.json()
    assert usuario["titular"] == "Backend Dev"
    assert usuario["skills"] == ["go"]
    assert usuario["experiencia"] == creado["experiencia"]
    assert usuario["creadoEn"] == creado["creadoEn"]
    assert usuario["actualizadoEn"] >= creado["actualizadoEn"]


def test_actualizar_con_null_elimina_un_campo_opcional(api):
    creado = api.post("/usuarios", json=usuario_valido(titular="Dev")).json()

    usuario = api.patch(f"/usuarios/{creado['id']}", json={"titular": None}).json()

    assert "titular" not in usuario


@pytest.mark.parametrize("cuerpo", [{"email": None}, {}, {"seniority": "experto"}],
                         ids=["null_en_obligatorio", "sin_campos", "valor_invalido"])
def test_actualizar_con_datos_invalidos_devuelve_422(api, cuerpo):
    creado = api.post("/usuarios", json=usuario_valido()).json()

    assert api.patch(f"/usuarios/{creado['id']}", json=cuerpo).status_code == 422


def test_actualizar_usuario_inexistente_devuelve_404(api):
    assert api.patch(f"/usuarios/{ObjectId()}", json={"titular": "X"}).status_code == 404


def test_actualizar_con_email_de_otro_usuario_devuelve_409(api, fabrica):
    otro = fabrica.usuario()
    creado = api.post("/usuarios", json=usuario_valido()).json()

    respuesta = api.patch(f"/usuarios/{creado['id']}", json={"email": otro["email"]})

    assert respuesta.status_code == 409


# --------------------------------------------------------------------------- eliminar

def test_eliminar_usuario_borra_sus_postulaciones_y_ajusta_las_ofertas(api, db, fabrica):
    usuario, otro = fabrica.usuario(), fabrica.usuario()
    oferta_a, oferta_b = fabrica.oferta(), fabrica.oferta()
    fabrica.postulacion(usuario, oferta_a, "entrevista")
    fabrica.postulacion(usuario, oferta_b, "retirada")  # ya no cuenta en cantidadPostulaciones
    fabrica.postulacion(otro, oferta_a, "enviada")

    respuesta = api.delete(f"/usuarios/{usuario['_id']}")

    assert respuesta.status_code == 204
    assert api.get(f"/usuarios/{usuario['_id']}").status_code == 404
    assert db.postulaciones.count_documents({"usuarioId": usuario["_id"]}) == 0
    assert db.postulaciones.count_documents({"usuarioId": otro["_id"]}) == 1
    assert db.ofertas.find_one({"_id": oferta_a["_id"]})["cantidadPostulaciones"] == 1
    assert db.ofertas.find_one({"_id": oferta_b["_id"]})["cantidadPostulaciones"] == 0
    verificar_consistencia(db)


def test_eliminar_usuario_con_contratacion_devuelve_409_y_no_borra_nada(api, db, fabrica):
    usuario = fabrica.usuario()
    fabrica.postulacion(usuario, fabrica.oferta(vacantes=2), "aceptada")
    fabrica.postulacion(usuario, fabrica.oferta(), "enviada")

    respuesta = api.delete(f"/usuarios/{usuario['_id']}")

    assert respuesta.status_code == 409
    assert db.usuarios.count_documents({"_id": usuario["_id"]}) == 1
    assert db.postulaciones.count_documents({"usuarioId": usuario["_id"]}) == 2
    verificar_consistencia(db)


def test_eliminar_usuario_inexistente_devuelve_404(api):
    assert api.delete(f"/usuarios/{ObjectId()}").status_code == 404
