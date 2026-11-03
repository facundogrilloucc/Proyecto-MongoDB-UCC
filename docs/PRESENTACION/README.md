# Material para la presentación

| Archivo | Qué es |
| :--- | :--- |
| [`Presentacion_Plataforma_Empleos.pptx`](Presentacion_Plataforma_Empleos.pptx) | Presentación de 29 diapositivas, con notas del orador en cada una |
| [`Informe_Base_de_Datos_Aplicada_Plataforma_Empleos.docx`](Informe_Base_de_Datos_Aplicada_Plataforma_Empleos.docx) | Informe técnico en Word con formato académico de la UCC: carátula, índice, tablas, código y los gráficos del análisis |
| [`demo/demo_en_vivo.sh`](demo/demo_en_vivo.sh) | Demo guiada para ejecutar en vivo mientras se presenta |
| [`guia_demo.md`](guia_demo.md) | Explicación de todo el proyecto a través de la demo: qué aparece y qué decir en cada paso. Sirve si piden mostrar solamente la demo |

## Presentación

Estructura:

| Sección | Diapositivas | Contenido |
| :--- | :--- | :--- |
| Introducción | 1–2 | Portada y el proyecto en números |
| Problema y diseño | 3–6 | Por qué una base documental, modelo de 4 colecciones, decisiones de modelado y un documento de ejemplo |
| Implementación | 7–8 | Docker Compose, validación y datos de prueba |
| Consultas e índices | 9–12 | Las 13 consultas, el *matching*, los 8 índices y el análisis con `explain()` |
| API y consistencia | 13–16 | Arquitectura en capas, el caso "aceptar candidato", la transacción y las pruebas |
| Análisis de datos | 17–23 | Método en JupyterLab, los 4 gráficos con sus hallazgos, resumen de indicadores y recomendación |
| Cierre | 24–27 | Reproducibilidad, demo en vivo, conclusiones y preguntas |
| Anexo | 28–29 | Endpoints de la API y comparación con un modelo relacional |

- **Notas del orador:** cada diapositiva trae lo que hay que decir. En PowerPoint se ven en **Vista → Página de notas** o debajo de la diapositiva en modo edición; al presentar con **Vista del moderador**, aparecen solo en la pantalla de quien presenta.
- **Duración:** las diapositivas 1 a 27 dan para unos 15 a 20 minutos. El anexo queda para responder preguntas.
- **Reparto sugerido** entre los integrantes: está en [`../defensa.md`](../defensa.md), sección 2.

## Informe

Si el índice aparece vacío o desactualizado al abrir el archivo en Word, hacer clic derecho sobre él y elegir **Actualizar campos**.

## Demo en vivo

Necesita Docker Desktop abierto y el archivo `.env` creado (ver [`../instrucciones.md`](../instrucciones.md)).

En Mac (Terminal) o en Windows (Git Bash), desde la carpeta del proyecto:

```bash
docs/PRESENTACION/demo/demo_en_vivo.sh
```

El script avanza de a un paso y espera un **Enter** entre cada uno, para poder explicar mientras se ve el resultado:

| Paso | Qué muestra |
| :--- | :--- |
| Preparación | Deja la base en su estado original y levanta la API |
| 1. Modelo documental | Un perfil completo con sus arreglos embebidos y una postulación con su historial |
| 2. Validación | El validador de MongoDB rechaza una oferta con más vacantes disponibles que el total |
| 3. Consulta sobre arreglos | `$all` + `$elemMatch` (consulta 5) |
| 4. Índices | `explain()` de la búsqueda principal con y sin índice: 3 documentos examinados contra 60 |
| 5. Aceptar candidato | Por la API: el primero se acepta y la oferta se cierra; el segundo recibe 409 y su postulación no cambia |
| 6. Tests | Falla simulada a mitad de la transacción y 5 aceptaciones simultáneas |
| 7. Navegador | Abre Swagger y el notebook en JupyterLab |
| Fin | Ofrece volver la base a su estado original |

La demo modifica datos. Al terminar ofrece restaurarlos; si se omite, después se puede ejecutar `bin/reset_db.sh`.

Para ensayarla de corrido, sin pausas y sin abrir el navegador:

```bash
DEMO_SIN_PAUSAS=1 docs/PRESENTACION/demo/demo_en_vivo.sh
```
