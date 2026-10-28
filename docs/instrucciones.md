# Instrucciones para levantar el proyecto

Esta guía explica cómo dejar la base de datos funcionando en tu computadora, en **Mac** o en **Windows**, desde cero.

Todo corre dentro de Docker. **No hace falta instalar MongoDB, `mongosh` ni Python.** Solo necesitás:

- **Git**, para descargar el repositorio.
- **Docker Desktop**, para ejecutar MongoDB.
- **MongoDB Compass** (opcional), para ver los datos con una interfaz gráfica.

Contenido:

1. [Instalación en Mac](#1-instalación-en-mac)
2. [Instalación en Windows](#2-instalación-en-windows)
3. [Cargar la base (igual en los dos sistemas)](#3-cargar-la-base)
4. [Conectarse con MongoDB Compass](#4-conectarse-con-mongodb-compass)
5. [Uso diario](#5-uso-diario)
6. [Problemas frecuentes](#6-problemas-frecuentes)

---

## 1. Instalación en Mac

### 1.1. Git

Abrí la app **Terminal** y escribí:

```bash
git --version
```

Si muestra una versión, ya está instalado. Si no, macOS va a ofrecer instalar las *Command Line Tools*: aceptá y esperá a que termine.

### 1.2. Docker Desktop

1. Descargalo de <https://www.docker.com/products/docker-desktop/>. Elegí **Apple Silicon** si tu Mac tiene chip M1, M2, M3 o M4, o **Intel** si es más vieja. Para saberlo, andá a  → *Acerca de esta Mac*.
2. Abrí el `.dmg` y arrastrá Docker a *Aplicaciones*.
3. Abrí Docker Desktop y aceptá los términos. No hace falta crear una cuenta: se puede omitir.
4. Esperá a que la ballena de la barra de menú deje de moverse.
5. Verificá en la Terminal:

```bash
docker compose version
```

### 1.3. Descargar el proyecto

Elegí una carpeta (por ejemplo, Documentos) y cloná el repositorio:

```bash
cd ~/Documents
```

```bash
git clone https://github.com/facundogrilloucc/Proyecto-MongoDB-UCC.git
```

```bash
cd Proyecto-MongoDB-UCC
```

Seguí en la [sección 3](#3-cargar-la-base).

---

## 2. Instalación en Windows

En Windows los scripts del proyecto (`bin/*.sh`) se ejecutan con **Git Bash**, una terminal que viene con Git. **No funcionan en PowerShell ni en CMD.**

### 2.1. Git (incluye Git Bash)

1. Descargalo de <https://git-scm.com/download/win> e instalalo.
2. Dejá las opciones por defecto, salvo una. En la pantalla *"Configuring the line ending conversions"*, elegí **"Checkout as-is, commit Unix-style line endings"**.

   Si ya tenías Git instalado, abrí Git Bash y ejecutá esto una vez:

   ```bash
   git config --global core.autocrlf input
   ```

   El repositorio ya fuerza el formato correcto en los scripts (archivo `.gitattributes`), pero esta configuración evita problemas con otros archivos.

### 2.2. WSL 2

Docker Desktop en Windows necesita WSL 2 (el subsistema de Linux de Windows).

1. Abrí **PowerShell como administrador**: clic derecho en el menú Inicio → *Terminal (Administrador)*.
2. Ejecutá:

   ```powershell
   wsl --install
   ```

3. **Reiniciá la computadora.**

Si dice que WSL ya está instalado, seguí adelante.

### 2.3. Docker Desktop

1. Descargalo de <https://www.docker.com/products/docker-desktop/> (versión *Windows – AMD64*; si tu equipo es ARM, la versión ARM64).
2. Durante la instalación, dejá marcada la opción **"Use WSL 2 instead of Hyper-V"**.
3. Abrí Docker Desktop, aceptá los términos y esperá a que abajo a la izquierda diga **"Engine running"**.
4. Abrí **Git Bash** (desde el menú Inicio) y verificá:

```bash
docker compose version
```

> Si al abrir Docker aparece un error de virtualización, hay que habilitarla en la BIOS de la computadora (suele llamarse *Intel VT-x*, *AMD-V* o *SVM Mode*).

### 2.4. Descargar el proyecto

En **Git Bash**:

```bash
cd ~/Documents
```

```bash
git clone https://github.com/facundogrilloucc/Proyecto-MongoDB-UCC.git
```

```bash
cd Proyecto-MongoDB-UCC
```

> **Importante:** cloná el proyecto en una carpeta local, como Documentos. **No uses OneDrive ni Google Drive**: Docker a veces no puede leer archivos de carpetas sincronizadas.

A partir de acá, **todos los comandos se ejecutan en Git Bash**, dentro de la carpeta del proyecto.

---

## 3. Cargar la base

Estos pasos son iguales en Mac (Terminal) y en Windows (Git Bash). Antes de empezar, **Docker Desktop tiene que estar abierto**.

### 3.1. Crear el archivo `.env`

El `.env` guarda el usuario y la contraseña de tu base local. No está en el repositorio, a propósito, así que cada uno crea el suyo a partir del ejemplo:

```bash
cp .env.example .env
```

Abrí `.env` con cualquier editor (VS Code, o el Bloc de notas en Windows) y cambiá `cambiar_esta_clave` por una contraseña inventada:

```
MONGO_ROOT_USER=admin
MONGO_ROOT_PASSWORD=mi_clave_local
MONGO_DB=empleos
MONGO_PORT=27017
```

- La contraseña **no puede tener** `@ : / ? #` ni espacios.
- No hace falta que sea la misma que la de tus compañeros: cada uno tiene su propia base.
- **Nunca subas el `.env` a GitHub.** Ya está excluido en `.gitignore`.

### 3.2. Crear y cargar la base

```bash
bin/reset_db.sh
```

Este script hace todo:

1. Levanta MongoDB.
2. Crea las colecciones con sus validaciones.
3. Carga los datos de prueba.
4. Crea los índices.
5. Verifica que todo esté bien.

**La primera vez tarda varios minutos**, porque descarga las imágenes de MongoDB y Python (unos 400 MB). Las siguientes veces tarda segundos.

Al final tiene que mostrar:

```
== Cantidad de documentos
   empresas       20
   usuarios       120
   ofertas        60
   postulaciones  250
   total          450
...
Verificación completa: sin errores.
```

Los datos se generan con una semilla fija, así que **todos tienen exactamente los mismos 450 documentos**.

### 3.3. Probar que funciona

Correr las consultas:

```bash
bin/mongosh.sh /scripts/04_consultas.js
```

Otros scripts disponibles:

```bash
bin/mongosh.sh /scripts/05_explain.js
```

```bash
bin/mongosh.sh /scripts/06_consistencia_inicial.js
```

---

## 4. Conectarse con MongoDB Compass

1. Descargá Compass de <https://www.mongodb.com/products/tools/compass> e instalalo.
2. Abrilo y hacé clic en **Add new connection**.
3. En el campo **URI**, pegá lo siguiente, reemplazando `USUARIO` y `CLAVE` por los valores de **tu** `.env`, **sin** los signos `< >`:

   ```
   mongodb://USUARIO:CLAVE@localhost:27017/?authSource=admin&directConnection=true
   ```

   Por ejemplo, con el `.env` de la sección 3.1 quedaría así:

   ```
   mongodb://admin:mi_clave_local@localhost:27017/?authSource=admin&directConnection=true
   ```

4. **No completes nada en "Advanced Connection Options"**: todo va en la URI.
5. Clic en **Save & Connect**. A la izquierda aparece la base `empleos` con sus cuatro colecciones.

Qué significa cada parte de la URI:

- **`authSource=admin`:** el usuario está creado en la base `admin`, no en `empleos`.
- **`directConnection=true`:** es obligatorio. MongoDB corre como *replica set* y se identifica con un nombre interno (`mongo`) que solo existe dentro de Docker. Con este parámetro, Compass se conecta directo a `localhost`.
- **Puerto:** si en tu `.env` cambiaste `MONGO_PORT`, usá ese número en lugar de `27017`.

### Consola de MongoDB

- **Mac:** podés abrir una consola interactiva con `bin/mongosh.sh` (sin argumentos).
- **Windows:** la consola interactiva no funciona bien desde Git Bash. Usá la de Compass: con la conexión abierta, hacé clic en **">_ Open MongoDB shell"** (arriba a la derecha) y escribí `use empleos`.

---

## 5. Uso diario

| Quiero... | Comando |
| :--- | :--- |
| Encender la base (los datos se conservan) | `docker compose up -d --wait mongo` |
| Apagar la base (los datos se conservan) | `docker compose down` |
| Volver la base al estado original | `bin/reset_db.sh` |
| Borrar todo, incluidos los datos | `docker compose down -v` |
| Ver si el contenedor está corriendo | `docker compose ps` |
| Ver los logs de MongoDB | `docker compose logs mongo` |

**Cuando un compañero sube cambios** (al generador de datos, las validaciones, los índices, etc.):

```bash
git pull
```

```bash
bin/reset_db.sh
```

Así tu base queda igual a la del repositorio.

Aunque no la uses, la base queda encendida hasta que la apagues o cierres Docker Desktop. Si cerrás Docker Desktop, la próxima vez abrilo y ejecutá `docker compose up -d --wait mongo`, o directamente `bin/reset_db.sh`.

---

## 6. Problemas frecuentes

| Síntoma | Causa | Solución |
| :--- | :--- | :--- |
| `Falta el archivo .env` | No creaste el `.env` | Paso 3.1: `cp .env.example .env` |
| `failed to connect to the docker API` / `Cannot connect to the Docker daemon` / `error during connect` | Docker Desktop no está abierto | Abrirlo y esperar a que diga *Engine running* |
| `port is already allocated` o `address already in use` | Otro programa, por ejemplo un MongoDB instalado, usa el puerto 27017 | En el `.env`, cambiar a `MONGO_PORT=27018` y usar ese puerto en Compass |
| `Permission denied` al ejecutar `bin/...` (Mac) | El script perdió el permiso de ejecución | `chmod +x bin/*.sh` |
| `bad interpreter` o `$'\r': command not found` (Windows) | Los scripts quedaron con fin de línea de Windows | Ver la nota debajo de la tabla |
| `bin/reset_db.sh` no se reconoce (Windows) | Lo estás ejecutando en PowerShell o CMD | Abrir **Git Bash** y ejecutarlo ahí |
| Compass: `Authentication failed` | Usuario o contraseña distintos de los del `.env`, quedaron los signos `< >`, o algo cargado en *Advanced Connection Options* | Borrar la conexión en Compass y crearla de nuevo, pegando solo la URI |
| Compass: `Authentication failed` **después de cambiar la contraseña** del `.env` | MongoDB crea el usuario una sola vez, la primera vez que arranca, y sigue usando la contraseña vieja | `docker compose down -v` y después `bin/reset_db.sh` |
| Compass: `connection timed out` o `getaddrinfo ENOTFOUND mongo` | El contenedor está apagado, o falta `directConnection=true` en la URI | `docker compose up -d --wait mongo` y revisar la URI |
| `dependency failed to start: container empleos-mongo is unhealthy` | MongoDB tardó más de lo normal en arrancar (frecuente la primera vez) | Volver a ejecutar `bin/reset_db.sh` |

**Si en Windows aparece `bad interpreter` o `$'\r': command not found`**, ejecutá en Git Bash, dentro del proyecto, los comandos de abajo. Ojo: **descartan los cambios que no hayas commiteado** (tu `.env` no se toca).

```bash
git config core.autocrlf input
```

```bash
git rm --cached -r -q .
```

```bash
git reset --hard
```

Si nada de esto lo resuelve, pasá por el grupo el mensaje de error completo y la salida de:

```bash
docker compose ps
```
