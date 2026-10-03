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
`docker compose up --build` arranca API y DB; la API espera el healthcheck de DB.
En este paso el backend todavía no guarda análisis ni necesita la base de datos
al arrancar fuera de Docker. El repositorio de análisis está disponible; conectarlo a `/analyze` será el siguiente paso.

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
No usar una base de producción para pruebas.

Para verificar el repositorio desde la imagen de desarrollo, usando su configuración
sin imprimir la conexión:

```sh
docker compose run --rm api sh -c 'TEST_DATABASE_URL="$DATABASE_URL" python -m pytest -q backend/test/test_postgres_repository.py'
```

La batería comprueba también que no hay diferencias entre el modelo SQLAlchemy y
la migración aplicada, y que Alembic puede generar la siguiente revisión.
