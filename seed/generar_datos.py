"""Genera y carga los datos de prueba de la plataforma de empleos.

Los datos son reproducibles: con la misma semilla se generan exactamente los
mismos documentos, incluidos los _id. El script vacía las cuatro colecciones y
las vuelve a cargar, así que puede ejecutarse varias veces.

Uso:
    docker compose run --rm seed            (dentro de Docker Compose)
    MONGO_URI=... MONGO_DB=... python generar_datos.py
"""

import os
import random
import unicodedata
from datetime import datetime, timedelta, timezone

from bson import ObjectId
from faker import Faker
from pymongo import MongoClient

SEMILLA = 42
# Fecha de referencia fija (en lugar de "ahora") para que los datos no cambien
# según el día en que se ejecute el script.
HOY = datetime(2026, 10, 27, 12, 0)

N_EMPRESAS = 20
N_USUARIOS = 120
N_OFERTAS = 60
N_POSTULACIONES = 250

rnd = random.Random(SEMILLA)
fake = Faker("es_AR")
Faker.seed(SEMILLA)

# --------------------------------------------------------------------------- catálogos

SENIORITIES = ["junior", "semi-senior", "senior", "lead"]
SUFIJO_SENIORITY = {"junior": "Jr", "semi-senior": "Ssr", "senior": "Sr", "lead": "Lead"}

# Cada skill tiene dos pesos: (frecuencia en perfiles, frecuencia en ofertas).
# Están desbalanceados a propósito para que el análisis pueda detectar skills
# muy pedidas por las empresas y poco presentes en los candidatos (y al revés).
FAMILIAS = {
    "backend": {
        "titulos": ["Backend Developer", "Desarrollador/a Backend"],
        "skills": {"python": (5, 4), "java": (4, 4), "node.js": (4, 3), "go": (1, 3),
                   "sql": (5, 4), "mongodb": (3, 3), "postgresql": (3, 4), "docker": (3, 5),
                   "kubernetes": (1, 3), "aws": (2, 4), "fastapi": (2, 2), "spring": (2, 3),
                   "django": (2, 1), "redis": (1, 2)},
    },
    "frontend": {
        "titulos": ["Frontend Developer", "Desarrollador/a Frontend"],
        "skills": {"javascript": (5, 4), "typescript": (2, 5), "react": (4, 5), "angular": (3, 2),
                   "vue": (2, 1), "html": (5, 2), "css": (5, 2), "next.js": (1, 3)},
    },
    "data": {
        "titulos": ["Data Analyst", "Data Engineer", "Analista de Datos"],
        "skills": {"python": (5, 5), "sql": (5, 5), "pandas": (4, 3), "power bi": (4, 2),
                   "excel": (5, 1), "spark": (1, 3), "machine learning": (2, 3),
                   "airflow": (1, 3), "tableau": (2, 1)},
    },
    "devops": {
        "titulos": ["DevOps Engineer", "SRE", "Cloud Engineer"],
        "skills": {"docker": (5, 5), "kubernetes": (2, 5), "aws": (3, 5), "azure": (2, 2),
                   "terraform": (1, 4), "linux": (5, 3), "ci/cd": (3, 4), "gcp": (1, 2)},
    },
    "mobile": {
        "titulos": ["Mobile Developer", "Desarrollador/a Mobile"],
        "skills": {"kotlin": (3, 4), "swift": (2, 3), "flutter": (3, 3),
                   "react native": (3, 3), "java": (3, 1)},
    },
    "qa": {
        "titulos": ["QA Analyst", "QA Automation Engineer"],
        "skills": {"selenium": (3, 3), "cypress": (2, 4), "testing manual": (5, 2),
                   "postman": (4, 3), "jmeter": (1, 2), "sql": (3, 2)},
    },
}
TRANSVERSALES = {"git": (8, 3), "scrum": (5, 2), "jira": (4, 1)}
PESO_FAMILIA_USUARIOS = {"backend": 30, "frontend": 25, "data": 20, "devops": 8, "mobile": 7, "qa": 10}
PESO_FAMILIA_OFERTAS = {"backend": 28, "frontend": 18, "data": 17, "devops": 20, "mobile": 10, "qa": 7}

CIUDADES = [  # (ciudad, provincia, país, peso)
    ("Córdoba", "Córdoba", "Argentina", 35),
    ("Ciudad Autónoma de Buenos Aires", "Buenos Aires", "Argentina", 30),
    ("Rosario", "Santa Fe", "Argentina", 10),
    ("Mendoza", "Mendoza", "Argentina", 8),
    ("La Plata", "Buenos Aires", "Argentina", 5),
    ("Villa María", "Córdoba", "Argentina", 4),
    ("San Miguel de Tucumán", "Tucumán", "Argentina", 4),
    ("Neuquén", "Neuquén", "Argentina", 4),
]

EMPRESAS = [
    ("Nubia Software", "Tecnología"), ("Andes Data Labs", "Tecnología"),
    ("Quebracho Sistemas", "Consultoría"), ("Pampa Pagos", "Fintech"),
    ("Cumbre Salud Digital", "Salud"), ("Lumen Analytics", "Tecnología"),
    ("Ruta 9 Logística", "Logística"), ("Algarrobo Agrotech", "Agrotech"),
    ("Mercadito Online", "E-commerce"), ("Aula Viva", "Educación"),
    ("Cóndor Cloud", "Tecnología"), ("Brújula Fintech", "Fintech"),
    ("Sierra Consulting", "Consultoría"), ("Tilo Retail", "Retail"),
    ("Faro Telecom", "Telecomunicaciones"), ("Puna Studio", "Tecnología"),
    ("Cauce Seguros", "Fintech"), ("Molle Tech", "Tecnología"),
    ("Trigo Digital", "Agrotech"), ("Ceibo Labs", "Tecnología"),
]
TAMANIOS = (["1-10", "11-50", "51-200", "201-1000", "1000+"], [10, 30, 35, 18, 7])

EMPRESAS_NO_REGISTRADAS = ["Estudio Contable Pérez", "Municipalidad de Córdoba", "Kiosco Digital SRL",
                           "Consultora Delta", "Startup Patagonia", "Banco del Interior"]

UNIVERSIDADES = ["Universidad Católica de Córdoba", "Universidad Nacional de Córdoba",
                 "Universidad Tecnológica Nacional - FRC", "Universidad de Buenos Aires",
                 "Universidad Nacional de La Plata", "Universidad Siglo 21",
                 "Instituto Tecnológico de Buenos Aires", "Universidad Nacional de Rosario"]
TITULOS = ["Ingeniería en Sistemas de Información", "Licenciatura en Ciencias de la Computación",
           "Ingeniería Informática", "Analista de Sistemas", "Tecnicatura en Programación",
           "Licenciatura en Ciencia de Datos"]

CERTIFICACIONES = {
    "backend": [("MongoDB Associate Developer", "MongoDB"), ("Oracle Certified Java Programmer", "Oracle")],
    "frontend": [("Meta Front-End Developer", "Meta")],
    "data": [("Google Data Analytics", "Google"), ("Microsoft Power BI Data Analyst", "Microsoft")],
    "devops": [("AWS Certified Cloud Practitioner", "Amazon Web Services"),
               ("Certified Kubernetes Administrator", "CNCF")],
    "mobile": [("Associate Android Developer", "Google")],
    "qa": [("ISTQB Foundation Level", "ISTQB")],
}

# Rangos de salario mensual (mínimo de la banda) por seniority y moneda.
SALARIOS = {
    "ARS": {"junior": (900_000, 1_300_000), "semi-senior": (1_400_000, 2_000_000),
            "senior": (2_200_000, 3_200_000), "lead": (3_200_000, 4_300_000)},
    "USD": {"junior": (1_000, 1_600), "semi-senior": (1_800, 2_800),
            "senior": (3_000, 4_500), "lead": (4_500, 6_500)},
}

DESCRIPCIONES_PUESTO = [
    "Desarrollo y mantenimiento de funcionalidades del producto principal.",
    "Participación en un equipo ágil con despliegues frecuentes.",
    "Migración de sistemas legados a una arquitectura moderna.",
    "Trabajo con clientes internos para relevar requerimientos.",
]


# --------------------------------------------------------------------------- utilidades

def nuevo_id(fecha):
    """ObjectId determinístico: timestamp real del documento + 8 bytes de la semilla."""
    segundos = int(fecha.replace(tzinfo=timezone.utc).timestamp())
    return ObjectId(segundos.to_bytes(4, "big") + rnd.getrandbits(64).to_bytes(8, "big"))


def fecha_entre(desde, hasta):
    return desde + timedelta(seconds=rnd.randint(0, int((hasta - desde).total_seconds())))


def muestra_ponderada(pesos, k):
    """Elige k claves distintas de un diccionario {clave: peso}."""
    disponibles = dict(pesos)
    elegidas = []
    for _ in range(min(k, len(disponibles))):
        clave = rnd.choices(list(disponibles), weights=list(disponibles.values()))[0]
        elegidas.append(clave)
        del disponibles[clave]
    return elegidas


def slug(texto):
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return "".join(c for c in sin_tildes.lower() if c.isalnum())


def elegir_ubicacion():
    ciudad, provincia, pais, _ = rnd.choices(CIUDADES, weights=[c[3] for c in CIUDADES])[0]
    return {"ciudad": ciudad, "provincia": provincia, "pais": pais}


def redondear(monto, moneda):
    paso = 10_000 if moneda == "ARS" else 100
    return int(round(monto / paso) * paso)


def pesos_skills(familia, columna):
    """columna 0 = peso en perfiles, 1 = peso en ofertas."""
    return {s: p[columna] for s, p in FAMILIAS[familia]["skills"].items()}


# --------------------------------------------------------------------------- empresas

def generar_empresas():
    empresas = []
    for nombre, industria in EMPRESAS[:N_EMPRESAS]:
        creado = fecha_entre(datetime(2023, 1, 1), datetime(2025, 6, 1))
        empresa = {
            "_id": nuevo_id(creado),
            "nombre": nombre,
            "industria": industria,
            "tamanio": rnd.choices(*TAMANIOS)[0],
            "ubicacion": elegir_ubicacion(),
            "creadoEn": creado,
            "actualizadoEn": fecha_entre(creado, HOY),
        }
        if rnd.random() < 0.7:
            empresa["sitioWeb"] = f"https://{slug(nombre)}.example.com"
        if rnd.random() < 0.6:
            empresa["descripcion"] = f"{nombre} es una empresa del rubro {industria.lower()} con base en {empresa['ubicacion']['ciudad']}."
        empresas.append(empresa)
    return empresas


# --------------------------------------------------------------------------- usuarios

def generar_experiencia(familia, seniority, empresas):
    anios = {"junior": (0, 2), "semi-senior": (2, 4), "senior": (5, 9), "lead": (8, 14)}[seniority]
    cantidad = {"junior": (0, 1), "semi-senior": (1, 3), "senior": (2, 5), "lead": (3, 6)}[seniority]
    n = rnd.randint(*cantidad)
    if n == 0:
        return []

    inicio = HOY - timedelta(days=int(rnd.uniform(*anios) * 365) + 120)
    tramo = (HOY - inicio) / n
    titulo = rnd.choice(FAMILIAS[familia]["titulos"])
    trabaja_actualmente = rnd.random() < 0.8
    experiencia = []
    for i in range(n):
        desde = inicio + tramo * i
        ultimo = i == n - 1
        hasta = None if (ultimo and trabaja_actualmente) else desde + tramo - timedelta(days=rnd.randint(1, 45))
        # El nivel del puesto crece con la trayectoria.
        nivel = SENIORITIES[min(SENIORITIES.index(seniority), round(i * SENIORITIES.index(seniority) / max(n - 1, 1)))]
        trabajo = {"puesto": f"{titulo} {SUFIJO_SENIORITY[nivel]}", "desde": desde.replace(microsecond=0),
                   "hasta": hasta.replace(microsecond=0) if hasta else None, "actual": hasta is None}
        sorteo = rnd.random()
        if sorteo < 0.55:
            empresa = rnd.choice(empresas)
            trabajo = {"empresaId": empresa["_id"], "empresaNombre": empresa["nombre"], **trabajo}
        elif sorteo < 0.65:
            trabajo = {"empresaId": None, "empresaNombre": "Freelance", **trabajo}
        else:
            trabajo = {"empresaId": None, "empresaNombre": rnd.choice(EMPRESAS_NO_REGISTRADAS), **trabajo}
        if rnd.random() < 0.5:
            trabajo["descripcion"] = rnd.choice(DESCRIPCIONES_PUESTO)
        experiencia.append(trabajo)
    return experiencia


def generar_educacion(seniority):
    educacion = []
    desde = HOY - timedelta(days=365 * {"junior": rnd.randint(1, 5), "semi-senior": rnd.randint(4, 8),
                                         "senior": rnd.randint(8, 14), "lead": rnd.randint(12, 20)}[seniority])
    estado = rnd.choices(["en_curso", "finalizado", "abandonado"],
                         weights=[60, 30, 10] if seniority == "junior" else [10, 80, 10])[0]
    educacion.append({
        "institucion": rnd.choice(UNIVERSIDADES),
        "titulo": rnd.choice(TITULOS),
        "desde": desde.replace(hour=0, minute=0, second=0, microsecond=0),
        "hasta": None if estado == "en_curso" else (desde + timedelta(days=365 * rnd.randint(3, 6))).replace(
            hour=0, minute=0, second=0, microsecond=0),
        "estado": estado,
    })
    if rnd.random() < 0.2:
        inicio = fecha_entre(desde, HOY - timedelta(days=200)).replace(hour=0, minute=0, second=0, microsecond=0)
        educacion.append({"institucion": rnd.choice(UNIVERSIDADES), "titulo": "Diplomatura en Desarrollo de Software",
                          "desde": inicio, "hasta": inicio + timedelta(days=180), "estado": "finalizado"})
    return educacion


def generar_usuarios(empresas):
    usuarios = []
    for i in range(N_USUARIOS):
        familia = rnd.choices(list(PESO_FAMILIA_USUARIOS), weights=list(PESO_FAMILIA_USUARIOS.values()))[0]
        seniority = rnd.choices(SENIORITIES, weights=[30, 35, 25, 10])[0]
        nombre, apellido = fake.first_name(), fake.last_name()
        creado = fecha_entre(datetime(2024, 1, 1), HOY - timedelta(days=30)).replace(microsecond=0)

        cantidad_skills = rnd.randint(*{"junior": (3, 5), "semi-senior": (4, 7), "senior": (5, 9), "lead": (6, 10)}[seniority])
        skills = muestra_ponderada(pesos_skills(familia, 0), cantidad_skills - 1)
        if rnd.random() < 0.15:  # perfil "full stack" o mixto
            otra = rnd.choice([f for f in FAMILIAS if f != familia])
            skills += [s for s in muestra_ponderada(pesos_skills(otra, 0), 2) if s not in skills]
        skills += [s for s in muestra_ponderada({k: v[0] for k, v in TRANSVERSALES.items()}, rnd.randint(1, 2))
                   if s not in skills]

        experiencia = generar_experiencia(familia, seniority, empresas)
        titulo = rnd.choice(FAMILIAS[familia]["titulos"])

        usuario = {
            "_id": nuevo_id(creado),
            "nombre": nombre,
            "apellido": apellido,
            "email": f"{slug(nombre)}.{slug(apellido)}{i}@{rnd.choice(['example.com', 'example.org', 'correo.example'])}",
            "seniority": seniority,
            "ubicacion": elegir_ubicacion(),
            "skills": skills,
            "experiencia": experiencia,
            "educacion": generar_educacion(seniority),
            "creadoEn": creado,
            "actualizadoEn": fecha_entre(creado, HOY).replace(microsecond=0),
        }
        if rnd.random() < 0.85:
            usuario["titular"] = f"{titulo} {SUFIJO_SENIORITY[seniority]} | " + " · ".join(skills[:3])
        if rnd.random() < 0.8:
            usuario["idiomas"] = [{"idioma": "inglés", "nivel": rnd.choices(["A2", "B1", "B2", "C1", "C2"],
                                                                            weights=[10, 25, 35, 20, 10])[0]}]
            if rnd.random() < 0.12:
                usuario["idiomas"].append({"idioma": "portugués", "nivel": rnd.choice(["A2", "B1", "B2"])})
        if rnd.random() < 0.25:
            nombre_cert, emisor = rnd.choice(CERTIFICACIONES[familia])
            usuario["certificaciones"] = [{"nombre": nombre_cert, "emisor": emisor,
                                           "fecha": fecha_entre(datetime(2022, 1, 1), HOY).replace(microsecond=0)}]
        if rnd.random() < 0.8:
            sin_trabajo = not any(e["actual"] for e in experiencia)
            preferencias = {"disponible": sin_trabajo or rnd.random() < 0.4,
                            "modalidades": rnd.sample(["remoto", "hibrido", "presencial"], rnd.randint(1, 3))}
            if rnd.random() < 0.7:
                moneda = "USD" if rnd.random() < 0.15 else "ARS"
                minimo, maximo = SALARIOS[moneda][seniority]
                preferencias["salarioPretendido"] = {"monto": redondear(rnd.uniform(minimo, maximo * 1.2), moneda),
                                                     "moneda": moneda, "periodo": "mensual"}
            usuario["preferencias"] = preferencias
        if rnd.random() < 0.6:
            usuario["contacto"] = {"telefono": f"+54 9 {rnd.choice(['351', '11', '341', '261'])} {rnd.randint(400, 799)}-{rnd.randint(1000, 9999)}"}
            if rnd.random() < 0.5:
                usuario["contacto"]["github"] = f"https://github.com/{slug(nombre)}{slug(apellido)}"
        usuario["_familia"] = familia  # auxiliar: se elimina antes de insertar
        usuarios.append(usuario)

    # Casos límite
    recien_creados = usuarios[-2:]  # perfiles recién creados, todavía vacíos
    for u in recien_creados:
        u.update(skills=[], experiencia=[], seniority="junior")
        u.pop("titular", None)
        u.pop("certificaciones", None)
    for u in usuarios[:3]:  # tres usuarios que viven fuera de Argentina, sin provincia
        u["ubicacion"] = {"ciudad": "Montevideo", "pais": "Uruguay"}
    for u in [u for u in usuarios if u["experiencia"] and u["seniority"] != "junior"][:3]:
        # trabajos simultáneos: además de su empleo, un proyecto freelance actual
        u["experiencia"].append({"empresaId": None, "empresaNombre": "Freelance",
                                 "puesto": "Consultor/a independiente",
                                 "desde": (HOY - timedelta(days=200)).replace(microsecond=0),
                                 "hasta": None, "actual": True})
    return usuarios


# --------------------------------------------------------------------------- ofertas

def generar_ofertas(empresas):
    ofertas = []
    # La última empresa queda sin ofertas publicadas (caso límite).
    publicadoras = empresas[:-1]
    for _ in range(N_OFERTAS):
        empresa = rnd.choice(publicadoras)
        familia = rnd.choices(list(PESO_FAMILIA_OFERTAS), weights=list(PESO_FAMILIA_OFERTAS.values()))[0]
        seniority = rnd.choices(SENIORITIES, weights=[20, 35, 35, 10])[0]
        modalidad = rnd.choices(["remoto", "hibrido", "presencial"], weights=[40, 40, 20])[0]
        # Más ofertas recientes que antiguas (distribución triangular con moda en 20 días).
        publicada = (HOY - timedelta(days=int(rnd.triangular(1, 240, 20)), hours=rnd.randint(0, 12))).replace(microsecond=0)
        titulo = f"{rnd.choice(FAMILIAS[familia]['titulos'])} {SUFIJO_SENIORITY[seniority]}"

        requeridas = muestra_ponderada(pesos_skills(familia, 1), rnd.randint(3, 5))
        restantes = {s: p for s, p in pesos_skills(familia, 1).items() if s not in requeridas}
        restantes.update({k: v[1] for k, v in TRANSVERSALES.items()})
        deseables = muestra_ponderada(restantes, rnd.randint(0, 3))

        texto_modalidad = {"remoto": "trabajo 100% remoto", "hibrido": "modalidad híbrida",
                           "presencial": "trabajo presencial en oficina"}[modalidad]
        oferta = {
            "_id": nuevo_id(publicada),
            "empresa": {"empresaId": empresa["_id"], "nombre": empresa["nombre"]},
            "titulo": titulo,
            "descripcion": (f"En {empresa['nombre']} buscamos {titulo.lower()} para sumarse a nuestro equipo. "
                            f"Ofrecemos {texto_modalidad}. Buscamos experiencia en {', '.join(requeridas)}."),
            "seniority": seniority,
            "modalidad": modalidad,
            "skillsRequeridas": requeridas,
            "vacantes": {"total": rnd.choices([1, 2, 3, 5], weights=[60, 25, 10, 5])[0], "disponibles": 0},
            "estado": "abierta",
            "cantidadPostulaciones": 0,
            "fechaPublicacion": publicada,
            "fechaCierre": None,
            "creadoEn": publicada,
            "actualizadoEn": publicada,
        }
        # Las ofertas remotas a veces no indican ubicación (caso límite permitido por el esquema).
        if modalidad != "remoto" or rnd.random() < 0.5:
            oferta["ubicacion"] = dict(empresa["ubicacion"])
        if deseables:
            oferta["skillsDeseables"] = deseables
        if rnd.random() < 0.7:  # no todas las empresas publican el salario
            moneda = "USD" if modalidad == "remoto" and rnd.random() < 0.35 else "ARS"
            minimo = redondear(rnd.uniform(*SALARIOS[moneda][seniority]), moneda)
            oferta["salario"] = {"min": minimo, "max": redondear(minimo * rnd.uniform(1.15, 1.5), moneda),
                                 "moneda": moneda, "periodo": "mensual"}
        # Las ofertas viejas tienden a estar cerradas; el resto, abiertas o pausadas.
        dias = (HOY - publicada).days
        if dias > 120 or (dias > 45 and rnd.random() < 0.3):
            oferta["estado"] = "cerrada"
        elif rnd.random() < 0.15:
            oferta["estado"] = "pausada"
        oferta["_familia"] = familia
        ofertas.append(oferta)
    return ofertas


# --------------------------------------------------------------------------- postulaciones

CAMINOS = {
    "enviada": ["enviada"],
    "en_revision": ["enviada", "en_revision"],
    "entrevista": ["enviada", "en_revision", "entrevista"],
    "aceptada": ["enviada", "en_revision", "entrevista", "aceptada"],
}
NOTAS = {"entrevista": ["Entrevista técnica agendada", "Entrevista con RR. HH."],
         "rechazada": ["El perfil no se ajusta a los requisitos", "Se avanzó con otro candidato"],
         "aceptada": ["Oferta aceptada por el candidato"]}


def camino_hasta(estado):
    if estado in CAMINOS:
        return CAMINOS[estado]
    if estado == "rechazada":
        return rnd.choice([["enviada", "rechazada"], ["enviada", "en_revision", "rechazada"],
                           ["enviada", "en_revision", "entrevista", "rechazada"]])
    return rnd.choice([["enviada", "retirada"], ["enviada", "en_revision", "retirada"]])


def generar_postulaciones(usuarios, ofertas):
    # Una oferta abierta queda sin postulaciones y otra concentra muchas (casos límite).
    abiertas = [o for o in ofertas if o["estado"] == "abierta"]
    sin_postulaciones, popular = abiertas[0], abiertas[1]
    candidatas = [o for o in ofertas if o is not sin_postulaciones]
    popularidad = [12 if o is popular else rnd.uniform(0.5, 2) for o in candidatas]

    postulaciones, pares = [], set()
    while len(postulaciones) < N_POSTULACIONES:
        oferta = rnd.choices(candidatas, weights=popularidad)[0]
        limite = min(HOY, oferta["fechaPublicacion"] + timedelta(days=45)) if oferta["estado"] == "cerrada" else HOY
        # Los usuarios se postulan sobre todo a ofertas de su área.
        pesos = [1 + 6 * len(set(u["skills"]) & set(oferta["skillsRequeridas"])) for u in usuarios]
        usuario = rnd.choices(usuarios, weights=pesos)[0]
        desde = max(oferta["fechaPublicacion"], usuario["creadoEn"])
        if (usuario["_id"], oferta["_id"]) in pares or desde >= limite:
            continue
        pares.add((usuario["_id"], oferta["_id"]))

        fecha = fecha_entre(desde, limite).replace(microsecond=0)
        coincidencia = len(set(usuario["skills"]) & set(oferta["skillsRequeridas"])) / len(oferta["skillsRequeridas"])
        postulacion = {
            "_id": nuevo_id(fecha),
            "usuarioId": usuario["_id"],
            "ofertaId": oferta["_id"],
            "empresaId": oferta["empresa"]["empresaId"],
            "estado": None,  # se define al repartir los estados por oferta
            "coincidenciaSkills": round(coincidencia, 2),
            "fechaPostulacion": fecha,
        }
        if rnd.random() < 0.4:
            postulacion["cartaPresentacion"] = (f"Hola, me interesa la posición de {oferta['titulo']}. "
                                                f"Tengo experiencia en {', '.join(usuario['skills'][:3]) or 'proyectos personales'}.")
        if rnd.random() < 0.5:
            moneda = oferta.get("salario", {}).get("moneda", "ARS")
            minimo, maximo = SALARIOS[moneda][oferta["seniority"]]
            postulacion["pretensionSalarial"] = {"monto": redondear(rnd.uniform(minimo, maximo * 1.3), moneda),
                                                 "moneda": moneda}
        postulaciones.append(postulacion)

    asignar_estados(postulaciones, ofertas)
    return postulaciones


def asignar_estados(postulaciones, ofertas):
    """Reparte estados de forma coherente con las vacantes y el estado de cada oferta."""
    por_oferta = {}
    for p in postulaciones:
        por_oferta.setdefault(p["ofertaId"], []).append(p)

    for oferta in ofertas:
        lista = sorted(por_oferta.get(oferta["_id"], []), key=lambda p: (p["coincidenciaSkills"], rnd.random()),
                       reverse=True)
        total = oferta["vacantes"]["total"]
        aptos = [p for p in lista if p["coincidenciaSkills"] >= 0.5]
        if oferta["estado"] == "cerrada":
            # Una oferta cerrada cubrió todas sus vacantes, salvo que no haya tenido candidatos aptos.
            aceptadas = min(total, len(aptos))
        else:
            aceptadas = rnd.randint(0, min(total - 1, len(aptos)))
        elegidas = aptos[:aceptadas]

        for p in lista:
            if p in elegidas:
                p["estado"] = "aceptada"
            elif oferta["estado"] == "cerrada":
                p["estado"] = rnd.choices(["rechazada", "retirada"], weights=[85, 15])[0]
            else:
                p["estado"] = rnd.choices(["enviada", "en_revision", "entrevista", "rechazada", "retirada"],
                                          weights=[30, 25, 15, 20, 10])[0]
            historial, fecha = [], p["fechaPostulacion"]
            for paso in camino_hasta(p["estado"]):
                if historial:
                    fecha = min(fecha + timedelta(days=rnd.randint(1, 7), hours=rnd.randint(0, 8)), HOY)
                entrada = {"estado": paso, "fecha": fecha}
                if paso in NOTAS and rnd.random() < 0.6:
                    entrada["nota"] = rnd.choice(NOTAS[paso])
                historial.append(entrada)
            p["historialEstados"] = historial
            p["actualizadoEn"] = historial[-1]["fecha"]

        oferta["vacantes"]["disponibles"] = total - aceptadas
        oferta["cantidadPostulaciones"] = sum(1 for p in lista if p["estado"] != "retirada")
        if oferta["estado"] == "cerrada":
            fechas_aceptacion = [p["actualizadoEn"] for p in elegidas]
            if aceptadas == total and fechas_aceptacion:
                oferta["fechaCierre"] = max(fechas_aceptacion)
            else:
                oferta["fechaCierre"] = min(HOY, oferta["fechaPublicacion"] + timedelta(days=60))
        if lista:
            oferta["actualizadoEn"] = max(oferta["fechaCierre"] or oferta["fechaPublicacion"],
                                          max(p["actualizadoEn"] for p in lista))


# --------------------------------------------------------------------------- carga

def main():
    uri = os.environ.get("MONGO_URI", "mongodb://localhost:27017/?directConnection=true")
    nombre_db = os.environ.get("MONGO_DB", "empleos")

    empresas = generar_empresas()
    usuarios = generar_usuarios(empresas)
    ofertas = generar_ofertas(empresas)
    postulaciones = generar_postulaciones(usuarios, ofertas)
    for documento in usuarios + ofertas:
        documento.pop("_familia")

    with MongoClient(uri) as cliente:
        db = cliente[nombre_db]
        for nombre, documentos in [("empresas", empresas), ("usuarios", usuarios),
                                   ("ofertas", ofertas), ("postulaciones", postulaciones)]:
            db[nombre].delete_many({})
            db[nombre].insert_many(documentos)
            print(f"{nombre:<14} {db[nombre].count_documents({}):>4} documentos")


if __name__ == "__main__":
    main()
