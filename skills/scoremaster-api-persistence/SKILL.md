---
name: scoremaster-api-persistence
description: Modificar API FastAPI, persistencia PostgreSQL, migraciones y configuración Docker de ScoreMasterAI; usar para contratos, uploads, repositorios y almacenamiento de análisis.
---

# API y persistencia

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md` y `backend/`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md` y `CONTRIBUTING.md`. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Inspecciona `backend/app/main.py`, `backend/app/config.py`, `backend/application/analysis_repository.py`, `backend/infrastructure/`, `migrations/` y `docker-compose.yml` según el alcance.

## Procedimiento

- Mantén contratos HTTP y orquestación en aplicación/API; SQLAlchemy y conexiones pertenecen a infraestructura. Reutiliza el puerto del repositorio sin introducir dependencias de base de datos en el dominio musical.
- Comprueba el estado real: disponer de migración y repositorio no implica que `/analyze` guarde resultados. Al conectar persistencia, define explícitamente errores y transacciones.
- Usa PostgreSQL. Persiste resultados estructurados, IDs, hash, configuración y versiones; no partituras originales ni bancos de audio.
- Conserva UUID por ejecución, fechas UTC y escritura transaccional. Versiona cambios de esquema con Alembic y verifica migración desde base vacía e idempotencia de upgrade.
- Revisa límites de upload y descompresión antes de procesar MusicXML/MXL, validación de parámetros y errores sin datos internos. Al añadir autenticación o historial, prueba acceso por propietario; la sesión demo del navegador no constituye control de acceso.
- Mantén API/DB en localhost mientras no exista autorización multiusuario. No publiques historial por el hecho de añadir un endpoint.
- No sobrescribas `.env` ni elimines volúmenes para solucionar credenciales. Usa `docker compose config --quiet` para verificar configuración sin imprimir secretos. Detener servicios no debe borrar datos.

## Verificación

Ejecuta pruebas de endpoints y repositorio afectadas. Las integraciones PostgreSQL requieren `TEST_DATABASE_URL` hacia una base dedicada (la de `docker compose up -d db`). Informa de pruebas omitidas: un skip no demuestra persistencia. Valida rollback ante conflictos y conservación tras reinicio cuando el cambio conecte el guardado. No ejecutes pruebas destructivas sobre datos de trabajo o producción.
