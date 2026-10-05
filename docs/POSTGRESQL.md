# PostgreSQL en desarrollo

La base de datos usa la [imagen oficial PostgreSQL](https://hub.docker.com/_/postgres),
serie 17. Se conserva el volumen `postgres_data` en reinicios. PostgreSQL 17 monta
sus datos en `/var/lib/postgresql/data`. El puerto local por defecto es 5433 para
no interferir con instalaciones en 5432. API y DB se publican solo en localhost
mientras la aplicación sea una demo sin autorización multiusuario.

Desde la raíz del repositorio:

```sh
cp .env.example .env
docker compose up -d --wait db
docker compose exec -T db sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -c "SELECT 1"'
```

No sobrescribir un `.env` existente. Las credenciales de ejemplo son exclusivamente
locales; elegir credenciales distintas antes de despliegue. Si ya existe un volumen,
cambiar POSTGRES_PASSWORD no cambia automáticamente la contraseña de esa instancia.
No eliminar el volumen para arreglar credenciales: preservar los datos y rotarlas.

`docker compose config --quiet` valida la configuración sin imprimir credenciales.
`docker compose up --build` arranca API y DB; la API espera el healthcheck de DB, aplica las
migraciones y crea el usuario demo (`DEMO_USER_EMAIL`, `DEMO_USER_PASSWORD`) si no existe.
Antes del primer análisis hay que aplicar las migraciones descritas abajo.
Cada respuesta correcta de `/analyze` guarda un registro y devuelve `analysis_id`.
Sin conexión o sin tablas migradas devuelve 503; no comunica un guardado exitoso.
`/health` comprueba que la API está viva, no la disponibilidad de PostgreSQL.

Para detener servicios conservando datos: `docker compose stop`.
No usar `down -v` sobre una base con datos que deban conservarse.

## Despliegue previsto

PostgreSQL gestionado mediante DATABASE_URL, conexión TLS y usuario con permisos
mínimos. No exponer el puerto DB públicamente. Las migraciones se ejecutarán como
paso de release. Backup/restauración y autorización se verificarán antes de publicar
historiales multiusuario. El volumen Docker local no sustituye las copias de seguridad.

## Migraciones y repositorio

Después de arrancar DB, construir la API y migrar explícitamente:

```sh
docker compose build api
docker compose run --rm api python -m alembic upgrade head
docker compose up -d --wait api
```

La migración `0001_analyses` crea `analyses`. Cada ejecución tiene un UUID propio,
hash SHA-256 del archivo, resultado estructurado, configuración, características,
versiones de algoritmo y características, y fecha UTC. No se guardan archivos ni audio.
La escritura es transaccional; reutilizar un UUID provoca rollback. La migración
puede repetirse sin duplicar tablas. Todavía no existe un endpoint público de historial.

Las pruebas de integración requieren `TEST_DATABASE_URL` con una conexión PostgreSQL
local (preferiblemente dedicada a pruebas) y permisos para crear esquemas. Ejecutar
`.venv/bin/python -m pytest -q`. Cada prueba crea y elimina exclusivamente su esquema
`test_scoremaster_<uuid>`; sin esa variable las pruebas PostgreSQL se omiten.
No usar una base de producción para pruebas. En local puede crearse una base
dedicada en el contenedor y apuntar ambas variables a ella:

```sh
docker compose exec db sh -c 'createdb -U "$POSTGRES_USER" scoremaster_test'
```

El CI de GitHub Actions ejecuta estas pruebas en cada pull request con un servicio
PostgreSQL 17 temporal.

Para verificar el repositorio desde la imagen de desarrollo, usando su configuración
sin imprimir la conexión:

```sh
docker compose run --rm api sh -c 'TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q backend/test/test_postgres_repository.py'
```

La batería comprueba también que no hay diferencias entre el modelo SQLAlchemy y
la migración aplicada, y que Alembic puede generar la siguiente revisión.

## Guardado desde la API

Cada ejecución correcta guarda el resultado completo previo, la plantilla usada y
los minutos solicitados. Guarda también las dimensiones agregadas legacy y el
resumen de tempo, identificados por `legacy-v1` y `legacy-features-v1`; todavía no
son características locales del nuevo algoritmo. Analizar dos veces el mismo archivo
crea dos IDs distintos. El hash corresponde a los bytes subidos (incluida la copia
temporal con instrumentos corregidos cuando la interfaz la envía). La respuesta
añade `analysis_id` sin modificar los campos musicales anteriores.

Desde la fase A2 cada análisis pertenece a su usuario y a una obra (`works`). La obra
guarda el archivo MusicXML original, el título, el compositor y el nombre del archivo,
**privados de su propietario** (decisión de la autora, 2026-10-04): permiten reabrir el
visor, el audio y replanificar sin volver a subirlo. Subir otra vez el mismo archivo
actualiza la misma obra. Borrar la obra (o la cuenta) borra su archivo y sus análisis
en cascada. `bands` guarda la plantilla del usuario (músicos por instrumento). El audio
no se guarda.

La migración `0004_work_preparation` añade `works.preparation_status` (`review`, `preparing`,
`ready`, `archived`; por defecto `review`), fijado por el director con `PATCH /works/{id}` e
independiente de la dificultad analizada. `GET /works/priorities` devuelve los pasajes críticos
del último análisis de cada obra en preparación, con `origin: "analysis"` para distinguirlos de
las futuras notas del director. Volver a analizar una obra conserva su estado.

Para arrancar con Python fuera de Docker, configurar `DATABASE_URL` en el entorno
del proceso usando la conexión local de `.env.example` (por ejemplo en el entorno
del IDE); Uvicorn no carga `.env` automáticamente. Después:

```sh
npm --prefix frontend ci
npm --prefix frontend run build
.venv/bin/python -m uvicorn backend.app.main:app --host 127.0.0.1 --port 8006
```

El pool se reutiliza y se cierra al apagar la API. El análisis sigue ejecutándose en un hilo de trabajo.

La integración prueba respuestas frente al algoritmo legacy, registros e IDs,
subidas rechazadas, errores sin credenciales expuestas y lectura tras reabrir
conexiones. Para comprobar el volumen: analizar una partitura sintética, conservar
su `analysis_id`, ejecutar `docker compose restart db api` y leer el registro mediante
el repositorio después de que DB esté saludable. No se publica historial ni endpoint
de lectura hasta incorporar autorización por registro.
