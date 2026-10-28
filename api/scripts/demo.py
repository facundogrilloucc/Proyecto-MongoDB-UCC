"""Recorrido de demostración de la API sobre los datos de prueba del proyecto.

Hace peticiones HTTP reales a la API en ejecución e imprime cada petición y su respuesta.
Modifica la base (crea un usuario, una postulación y acepta candidatos), así que al
terminar conviene volver al estado original con bin/reset_db.sh.

Uso: docker compose exec api python scripts/demo.py
"""

import json
import os

import httpx

API = os.environ.get("API_URL", "http://localhost:8000")
cliente = httpx.Client(base_url=API, timeout=10)


def paso(titulo: str) -> None:
    print(f"\n{'=' * 100}\n{titulo}\n{'-' * 100}")


def pedir(metodo: str, ruta: str, *, max_lineas: int = 18, **kwargs) -> httpx.Response:
    respuesta = cliente.request(metodo, ruta, **kwargs)
    print(f"{metodo} {ruta}" + (f"?{httpx.QueryParams(kwargs['params'])}" if kwargs.get("params") else ""))
    if "json" in kwargs:
        print("  cuerpo: " + json.dumps(kwargs["json"], ensure_ascii=False))
    print(f"  -> {respuesta.status_code}")
    if respuesta.content:
        lineas = json.dumps(respuesta.json(), ensure_ascii=False, indent=2).splitlines()
        for linea in lineas[:max_lineas]:
            print("     " + linea)
        if len(lineas) > max_lineas:
            print(f"     ... ({len(lineas) - max_lineas} líneas más)")
    return respuesta


paso("1. La API y la base están funcionando")
pedir("GET", "/salud")

paso("2. Listar usuarios con filtros: seniors que saben python y sql (resumen paginado)")
pedir("GET", "/usuarios", params={"skill": ["python", "sql"], "seniority": "senior", "limite": 2})

paso("3. Crear un usuario (las skills se normalizan y 'actual' se deriva de 'hasta')")
nuevo = {
    "nombre": "Lucía", "apellido": "Fernández", "email": "Lucia.Fernandez@demo.example",
    "titular": "Backend Developer", "seniority": "semi-senior",
    "ubicacion": {"ciudad": "Córdoba", "provincia": "Córdoba", "pais": "Argentina"},
    "skills": ["Python", "MongoDB", "SQL", "python", "Docker"],
    "experiencia": [{"empresaNombre": "Freelance", "puesto": "Desarrolladora Backend", "desde": "2023-03-01"}],
    "educacion": [{"institucion": "Universidad Católica de Córdoba", "titulo": "Ingeniería en Sistemas",
                   "desde": "2019-03-01", "estado": "en_curso"}],
}
usuario = pedir("POST", "/usuarios", json=nuevo, max_lineas=40).json()

paso("4. Crear otro usuario con el mismo email (distinto uso de mayúsculas) -> 409")
pedir("POST", "/usuarios", json={**nuevo, "email": "LUCIA.FERNANDEZ@demo.example"})

paso("5. Crear un usuario con datos inválidos -> 422 con el detalle de cada error")
pedir("POST", "/usuarios", json={**nuevo, "email": "sin-arroba", "seniority": "experta"}, max_lineas=30)

paso("6. Obtener el usuario creado")
pedir("GET", f"/usuarios/{usuario['id']}", max_lineas=8)

paso("7. Actualizar parcialmente: reemplazar las skills, agregar preferencias y quitar el titular con null")
pedir("PATCH", f"/usuarios/{usuario['id']}",
      json={"skills": ["python", "mongodb", "sql", "docker", "aws"], "preferencias": {"disponible": True}},
      max_lineas=12)
pedir("PATCH", f"/usuarios/{usuario['id']}", json={"titular": None}, max_lineas=6)

paso("8. Errores de identificador: inexistente -> 404, mal formado -> 422")
pedir("GET", "/usuarios/6710a1f0c1a2b3c4d5e6f999")
pedir("GET", "/usuarios/no-es-un-id")

ACTIVOS = ("enviada", "en_revision", "entrevista")


def postulante_activo(oferta_id: str) -> dict | None:
    postulantes = cliente.get(f"/ofertas/{oferta_id}/postulaciones", params={"limite": 100}).json()["resultados"]
    return next((p for p in postulantes if p["estado"] in ACTIVOS), None)


paso("9. Buscar una oferta abierta con una sola vacante disponible y algún postulante activo")
ofertas = cliente.get("/ofertas", params={"estado": "abierta", "limite": 100}).json()["resultados"]
oferta = next(o for o in ofertas if o["vacantes"]["disponibles"] == 1 and postulante_activo(o["id"]))
otro = postulante_activo(oferta["id"])
pedir("GET", f"/ofertas/{oferta['id']}", max_lineas=40)

paso("10. Postularse a la oferta (la coincidencia de skills se calcula al postularse) y repetir -> 409")
postulacion = pedir("POST", f"/ofertas/{oferta['id']}/postulaciones",
                    json={"usuarioId": usuario["id"], "cartaPresentacion": "Me interesa el puesto."}).json()
pedir("POST", f"/ofertas/{oferta['id']}/postulaciones", json={"usuarioId": usuario["id"]})

paso("11. Transición no permitida: de 'enviada' directo a 'aceptada' -> 409")
pedir("PATCH", f"/postulaciones/{postulacion['id']}/estado", json={"estado": "aceptada"})

paso("12. Avanzar el proceso: en_revision -> entrevista -> aceptada (transacción)")
pedir("PATCH", f"/postulaciones/{postulacion['id']}/estado", json={"estado": "en_revision"}, max_lineas=0)
pedir("PATCH", f"/postulaciones/{postulacion['id']}/estado",
      json={"estado": "entrevista", "nota": "Entrevista técnica"}, max_lineas=0)
pedir("PATCH", f"/postulaciones/{postulacion['id']}/estado",
      json={"estado": "aceptada", "nota": "Oferta aceptada"}, max_lineas=40)

paso("13. La oferta descontó la vacante y, como era la última, quedó cerrada")
final = pedir("GET", f"/ofertas/{oferta['id']}", max_lineas=0).json()
print(f"     estado: {final['estado']} | vacantes: {final['vacantes']} | fechaCierre: {final['fechaCierre']}")

paso("14. Otro candidato de la misma oferta llega a entrevista e intenta ser aceptado -> 409 sin vacantes")
siguiente = {"enviada": "en_revision", "en_revision": "entrevista"}
while otro["estado"] in siguiente:
    otro = cliente.patch(f"/postulaciones/{otro['id']}/estado", json={"estado": siguiente[otro["estado"]]}).json()
print(f"(postulación {otro['id']} en estado '{otro['estado']}')")
pedir("PATCH", f"/postulaciones/{otro['id']}/estado", json={"estado": "aceptada"})
despues = pedir("GET", f"/postulaciones/{otro['id']}", max_lineas=0).json()
print(f"     -> sigue en '{despues['estado']}': la transacción se abortó y el paso 1 se deshizo")

paso("15. Eliminar un usuario con una contratación registrada -> 409")
pedir("DELETE", f"/usuarios/{usuario['id']}")

paso("16. Eliminar un usuario sin contrataciones -> 204, y después ya no existe")
temporal = cliente.post("/usuarios", json={**nuevo, "email": "temporal@demo.example"}).json()
pedir("DELETE", f"/usuarios/{temporal['id']}")
pedir("GET", f"/usuarios/{temporal['id']}")
