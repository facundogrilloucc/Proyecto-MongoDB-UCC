# Guía para la defensa

La consigna pide que **cada integrante** pueda:

1. explicar el modelo documental;
2. ejecutar una consulta;
3. justificar un índice;
4. describir el funcionamiento del repositorio.

Esta guía tiene una propuesta de presentación con demo, una ficha para cada uno de esos cuatro puntos y las preguntas más probables con sus respuestas. **Todos deberían leer la guía completa**, no solo la parte que presentan.

---

## 1. Antes de la defensa

**El día anterior:**

- [ ] `git pull` en la computadora con la que se va a presentar.
- [ ] Docker Desktop abierto y funcionando.
- [ ] `bin/reset_db.sh` → tiene que terminar en `Verificación completa: sin errores.`
- [ ] `docker compose up -d --build --wait api` → abrir <http://localhost:8000/docs>.
- [ ] `docker compose run --rm api pytest -q` → `43 passed`.
- [ ] `docker compose up -d analisis` → abrir <http://localhost:8888> y el notebook `analisis.ipynb`.
- [ ] Compass conectado a la base (URI en [instrucciones.md](instrucciones.md), sección 4).
- [ ] Ensayar la demo de corrido: `DEMO_SIN_PAUSAS=1 docs/PRESENTACION/demo/demo_en_vivo.sh`.

**15 minutos antes:**

- [ ] `bin/reset_db.sh`, para empezar con los datos originales.
- [ ] Abrir en pestañas: Swagger, Jupyter, Compass, el repositorio en GitHub y una terminal en la carpeta del proyecto.
- [ ] Aumentar el tamaño de letra de la terminal.

---

## 2. Presentación propuesta (≈ 15 minutos)

El reparto es una sugerencia; acomódenlo como prefieran.

| Bloque | Tiempo | Quién | Contenido | Qué mostrar |
| :--- | :--- | :--- | :--- | :--- |
| 1. Problema y modelo | 3 min | Integrante A | Dominio, por qué MongoDB, las 4 colecciones, qué se embebe y qué se referencia | Diagrama del [informe](informe-final.md), sección 3; un usuario completo en Compass |
| 2. Consultas e índices | 3 min | Integrante B | Una consulta de arreglos, una agregación, el *matching*; índice ESR con `explain` | Consultas 5, 8 y 10 en mongosh o Compass; salida de `05_explain.js` |
| 3. API y consistencia | 4 min | Integrante C | Capas, CRUD, el caso "aceptar candidato" con su transacción y los tests | Pasos 5 y 6 de la demo (sección 3) |
| 4. Análisis y conclusiones | 3 min | Integrante A o B | 2 o 3 gráficos y la recomendación | Notebook en Jupyter |
| 5. Reproducibilidad | 1 min | Integrante C | Docker Compose, `reset_db.sh`, prueba desde entorno limpio | `docker compose ps` |

---

## 3. Demo en vivo

La demo está automatizada en [`PRESENTACION/demo/demo_en_vivo.sh`](PRESENTACION/demo/demo_en_vivo.sh). Avanza de a un paso, espera un Enter entre cada uno y empieza dejando la base en su estado original.

```bash
docs/PRESENTACION/demo/demo_en_vivo.sh
```

El guion está en **[`PRESENTACION/guia_demo.md`](PRESENTACION/guia_demo.md)**. Para cada paso indica qué aparece en pantalla, qué decir, qué requisito de la consigna demuestra y qué suelen preguntar.

| Situación | Cómo usar la guía |
| :--- | :--- |
| **El profesor pide solamente la demo** | Seguir la guía completa, empezando por la sección 0 ("El proyecto en un minuto"). Cubre todos los requisitos de la consigna en unos 12 minutos |
| **Presentación completa con demo** | Usar los pasos de la demo dentro de cada bloque de la sección 2: el paso 1 en el bloque 1; los pasos 3 y 4 en el bloque 2; los pasos 5 y 6 en el bloque 3; y Jupyter (paso 7) en el bloque 4 |
| **Piden algo que la demo no muestra** | Tabla "Si piden ver más", al final de la guía |

**Alternativa manual:** si el script no se puede ejecutar, se pueden hacer los mismos pasos a mano:

- El modelo y la validación, en Compass (colecciones `usuarios` y `postulaciones`, y la pestaña **Validation** de `ofertas`).
- La consulta y el `explain`, en mongosh. Los comandos están en las secciones 4.2 y 4.3 de esta guía.
- El caso "aceptar candidato", en Swagger, con la oferta `6aacc5503c4722f3c1b4fd44`: llevar dos postulaciones activas hasta `entrevista` y aceptarlas. La primera recibe 200 y la segunda, 409.

---

## 4. Fichas: lo que cada integrante tiene que poder explicar

### 4.1. Explicar el modelo documental

> Tenemos cuatro colecciones. **`usuarios`** es la entidad principal y embebe la experiencia, la educación y las skills, porque son pocos elementos, se leen siempre junto con el perfil y no existen sin el usuario: un perfil completo es una sola lectura. **`postulaciones`** es una colección aparte porque es una relación muchos a muchos que crece sin límite: si la embebiéramos en la oferta, una oferta popular crecería indefinidamente y cada cambio de estado reescribiría un documento enorme. Cada postulación embebe su historial de estados. **`ofertas`** referencia a la empresa por id, pero guarda también su nombre (referencia extendida) para listar ofertas sin `$lookup`. **`empresas`** es una colección independiente, porque muchas ofertas la comparten.

Si preguntan por los costos:

- Renombrar una empresa exige actualizar sus ofertas.
- Los contadores desnormalizados (`cantidadPostulaciones`) hay que mantenerlos: la API lo hace dentro de transacciones.

### 4.2. Ejecutar una consulta

Tener preparada **una** consulta y saber explicar cada operador. Se recomienda la consulta 5, que es también el paso 3 de la demo. Para ejecutarla a mano: abrir `bin/mongosh.sh` en Mac, o la consola de Compass en Windows (`use empleos`), y pegar:

```js
db.usuarios.find(
  { skills: { $all: ["python", "sql"] }, experiencia: { $elemMatch: { actual: true, empresaId: { $ne: null } } } },
  { _id: 0, nombre: 1, apellido: 1, skills: 1, experiencia: { $elemMatch: { actual: true, empresaId: { $ne: null } } } }
)
```

- **`$all`:** el arreglo `skills` tiene que contener **todos** los valores indicados, en cualquier orden.
- **`$elemMatch`:** **un mismo elemento** de `experiencia` tiene que cumplir las dos condiciones a la vez. Sin `$elemMatch`, un trabajo podría cumplir `actual: true` y otro distinto `empresaId != null`.
- **La proyección con `$elemMatch`** devuelve solo el trabajo que cumple, no toda la trayectoria. Probamos primero con la proyección posicional `experiencia.$` y falló, porque el filtro toca dos arreglos y el `$` es ambiguo.

Como alternativa, una agregación: la consulta 9 (salarios). Explicar `$match` → `$group` con `$avg`, `$min`, `$max` y `$stdDevPop` → `$project`. Se agrupa también por moneda, porque no se pueden promediar pesos con dólares.

### 4.3. Justificar un índice

**`ix_busqueda_ofertas`** = `{ estado: 1, seniority: 1, "salario.moneda": 1, "salario.min": 1 }`

- Sirve a la búsqueda más frecuente de la plataforma (consulta 1).
- Sigue la regla **ESR**: primero los campos que se comparan por **igualdad** (estado, seniority, moneda) y al final el de **rango** (`salario.min >= …`). Así el índice acota exactamente el tramo de claves que interesa.
- En `explain`: 3 claves examinadas, 3 documentos examinados y 3 devueltos. Sin índice examina las 60 ofertas y además ordena en memoria (`SORT`). Con el índice no hay `SORT`, porque las claves ya vienen ordenadas por `salario.min`.
- Costo: ocupa espacio (en `ofertas` los índices pesan más que los datos) y cada escritura lo actualiza. Lo aceptamos porque las ofertas se leen mucho más de lo que se escriben.
- Con 450 documentos todo tarda 0 ms, así que el beneficio se mide comparando documentos examinados contra devueltos, no por el tiempo.

Para mostrarlo a mano (es el paso 4 de la demo):

```js
db.ofertas.find({ estado: "abierta", seniority: "semi-senior", "salario.moneda": "ARS", "salario.min": { $gte: 1700000 } })
  .explain("executionStats").executionStats
```

`totalDocsExamined` da 3, igual a `nReturned`. Agregando `.hint({ $natural: 1 })` antes de `.explain(...)`, para que no use el índice, examina 60.

Otro buen ejemplo: **`ux_usuario_oferta`** (único). Garantiza en la base que nadie se postule dos veces, incluso si llegan dos peticiones al mismo tiempo, y su prefijo `usuarioId` resuelve "mis postulaciones" sin otro índice.

### 4.4. Describir el funcionamiento del repositorio

Seguir el recorrido de una petición, por ejemplo `POST /usuarios`:

1. **Router** ([`routers/usuarios.py`](../api/app/routers/usuarios.py)): FastAPI valida el cuerpo con el modelo Pydantic `UsuarioCrear`. Si algo no cumple, responde 422 sin llegar a la base.
2. **Servicio** ([`services/usuarios.py`](../api/app/services/usuarios.py)): aplica las reglas de negocio:
   - verifica que las empresas referenciadas existan;
   - copia su nombre;
   - deriva `actual` de `hasta`;
   - completa las fechas.
3. **Repositorio** ([`repositories/usuarios.py`](../api/app/repositories/usuarios.py)): el único lugar que habla con MongoDB. `crear()` hace el `insert_one`. Si el email ya existe, el índice único lanza `DuplicateKeyError` y el servicio lo traduce a 409.

Puntos clave:

- **Cada capa tiene una responsabilidad.** El router no conoce MongoDB, y el servicio no conoce HTTP ni las colecciones.
- **Los métodos de escritura del repositorio reciben una `sesion` opcional.** Así, el servicio puede agrupar varias operaciones de distintos repositorios en una transacción (`en_transaccion` en [`database.py`](../api/app/database.py)).
- **Las consultas viven en el repositorio.** Por ejemplo, `descontar_vacante()` tiene el filtro `vacantes.disponibles > 0` y el `$inc` en la misma operación atómica.

---

## 5. Preguntas probables

**¿Por qué MongoDB y no una base relacional?**
Los perfiles son heterogéneos (muchos campos opcionales y listas de largo variable) y se leen completos. En MongoDB, un perfil es un documento y una lectura; en SQL serían 6 tablas y *joins*. Ver la comparación en la sección 9 del informe.

**¿Por qué no embebieron las postulaciones dentro de la oferta?**
Crecen sin límite: el límite de un documento es 16 MB y cada cambio de estado reescribiría la oferta entera. Además, se consultan desde el usuario ("mis postulaciones") y desde la oferta ("postulantes"). Con una colección propia y dos índices, las dos consultas son eficientes.

**¿Qué pasa si una empresa cambia de nombre?**
Hay que hacer un `updateMany` sobre `ofertas` para actualizar `empresa.nombre`. Es el costo de la referencia extendida; lo aceptamos porque renombrar es muy raro y listar ofertas es constante. `03_verificacion.js` controla que el nombre desnormalizado coincida.

**¿Qué pasa si se cae la API en la mitad de "aceptar candidato"?**
Nada queda a medias: las tres escrituras están en una transacción, y si no llega el *commit*, MongoDB las descarta. Lo probamos forzando un error después de dos escrituras (`test_falla_a_mitad_de_la_transaccion_no_deja_cambios_parciales`).

**¿Y si dos reclutadores aceptan al mismo tiempo la última vacante?**
Las dos transacciones modifican el mismo documento de la oferta. MongoDB detecta el conflicto de escritura y aborta una. `with_transaction` la reintenta, y en el reintento el `$inc` condicional (`disponibles > 0`) ya no encuentra vacante, así que responde 409. Lo probamos con 5 hilos simultáneos: exactamente 1 aceptación.

**¿Por qué no usaron una transacción para todo?**
Las transacciones tienen costo: necesitan un replica set, agregan latencia y pueden reintentarse. Cuando la operación toca un solo documento (por ejemplo, pasar una postulación a `entrevista`), una operación atómica condicional ya garantiza la consistencia. Usamos transacciones solo cuando se modifican documentos de dos colecciones.

**¿Por qué MongoDB corre como replica set si es un solo nodo?**
Porque las transacciones multidocumento no funcionan en una instancia independiente. Un replica set de un nodo es la forma más simple de tenerlas en desarrollo.

**¿Qué es un índice multikey?**
Un índice sobre un campo que es un arreglo: MongoDB crea una entrada por cada elemento. Así, `{ skills: 1 }` encuentra a los usuarios que tienen "python" en su lista. Una limitación: un índice compuesto no puede tener dos campos que sean arreglos en el mismo documento.

**¿Por qué los tiempos de `explain` dan 0 ms?**
Con 450 documentos todo entra en memoria y un recorrido completo es instantáneo. Por eso evaluamos la proporción entre documentos examinados y devueltos, que con datos reales crecería linealmente sin índice.

**¿Cómo evitan postulaciones duplicadas si llegan dos peticiones simultáneas?**
Con el índice único `{usuarioId, ofertaId}`: aunque la API no detecte el duplicado, la base rechaza la segunda inserción (E11000) y la API responde 409.

**¿Qué valida Pydantic y qué valida MongoDB?**

- **Pydantic:** la petición (tipos, obligatorios, formato, campos desconocidos y coherencia interna, por ejemplo `hasta >= desde`).
- **Los servicios:** lo que requiere consultar la base (que la empresa exista, que la transición sea válida).
- **El validador `$jsonSchema`:** es la red de seguridad. Si un error de programación dejara pasar un documento inválido, la base lo rechaza.

**¿Por qué no se puede borrar un usuario que fue contratado?**
Su postulación aceptada ya descontó una vacante: borrarla dejaría la oferta inconsistente y perderíamos un dato histórico. Respondemos 409. A un usuario sin contrataciones sí se lo borra, junto con sus postulaciones, en una transacción.

**¿Para qué guardan `cantidadPostulaciones` si se puede contar?**
Para mostrar la popularidad en los listados sin un `count` por oferta. El costo es mantenerlo: se actualiza dentro de las transacciones de postularse, retirar y eliminar usuario, y la verificación confirma que no se desincroniza.

**¿Los datos son reales?**
No: son 450 documentos sintéticos generados con semilla fija, siempre iguales. Algunas relaciones las induce el generador; en el análisis lo señalamos en cada conclusión. El código de análisis funcionaría igual con datos reales.

**¿Qué pasa con las postulaciones activas cuando una oferta se cierra?**
Quedan como están, y el reclutador las rechaza. Rechazarlas automáticamente agregaría más escrituras a la transacción de aceptar; es una mejora posible.

**¿`$lookup` no es un *join*? ¿No contradice usar una base documental?**
Sí, es un *join*. Lo usamos en consultas analíticas o poco frecuentes (embudo por empresa, verificación de integridad). En las consultas frecuentes lo evitamos con el diseño: embebiendo o con la referencia extendida.

---

## 6. Si algo falla durante la demo

| Problema | Solución rápida |
| :--- | :--- |
| Swagger no carga | `docker compose up -d --build --wait api` |
| Datos alterados por una prueba anterior | `bin/reset_db.sh` |
| Compass no conecta | Revisar que la URI tenga `directConnection=true` y la contraseña del `.env` |
| No hay tiempo para la demo manual | `docker compose exec api python scripts/demo.py` y recorrer la salida |
| Falla todo lo demás | Mostrar la evidencia ya generada en `docs/evidencia/` |
