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
al arrancar fuera de Docker. Las migraciones y el repositorio se añaden a continuación.

Para detener servicios conservando datos: `docker compose stop`.
No usar `down -v` sobre una base con datos que deban conservarse.

## Despliegue previsto

PostgreSQL gestionado mediante DATABASE_URL, conexión TLS y usuario con permisos
mínimos. No exponer el puerto DB públicamente. Las migraciones se ejecutarán como
paso de release. Backup/restauración y autorización se verificarán antes de publicar
historiales multiusuario. El volumen Docker local no sustituye las copias de seguridad.
