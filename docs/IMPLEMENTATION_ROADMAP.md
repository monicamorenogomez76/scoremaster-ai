# Plan aprobado y estado de implementación

## Decisiones que prevalecen

- PostgreSQL en desarrollo y producción; SQLAlchemy, Alembic y repositorios independientes del dominio.
- Grados visibles enteros 1–6 y rúbrica propia documentada, sin afirmar certificación oficial. Índice técnico interno 0–10; transformación explícita. Actualmente la aplicación sigue usando grados 1–5 e índice 0–5 hasta la entrega 13.
- Nivel objetivo por defecto intermedio, separado del grado editorial estimado.
- Separar Difficulty, Criticality y RehearsalPriority. Un análisis puede devolver cero críticos.
- Primera entrega: base musical fiable. Después revisión estructurada LLM y evaluación híbrida; sin chatbot, RAG ni agentes autónomos.
- Persistir resultados estructurados y feedback, no partituras originales ni bancos de audio.
- Evaluación local inicialmente; autenticación y autorización antes de publicar historial multiusuario.
- Un objetivo por PR, pruebas y documentación. Integración secuencial mediante squash.

## Baseline integrado

Las PR #11–#16 están integradas. La PR #5 se cerró porque su densidad rítmica y agrupación ya estaban incorporadas. Comprobaciones: 62 pruebas Python, 5 pruebas Node y recorrido Playwright sobre carga, instrumentos, visor, reinicio, móvil y pasajes.

PostgreSQL local está integrado mediante la PR #19. El repositorio y las migraciones están preparados para revisión; todavía no se guarda desde la API ni existe proveedor LLM. El audio actual ya usa muestras General MIDI para instrumentos afinados y síntesis para percusión. La resistencia actual es una aproximación por compases. Los hallazgos se agrupan como críticos, pendiente del detector separado.

La corrección del audio del clarinete, el pasaje completo y los controles compartidos están integrados en la PR #20. Las siguientes PR retoman el plan musical y de persistencia.

## Entregas

Los números 01–25 identifican pasos del plan, no números de GitHub. El paso 04 está preparado para la siguiente PR, después de la #20.

| Entrega | Objetivo | Estado |
|---|---|---|
| 01 | Especificación consolidada | Integrada: PR #17 |
| 02 | Baseline reproducible | Integrada: PR #18; 15 casos, 10 nombres y audio |
| 03 | PostgreSQL en desarrollo | Integrado en PR #19: Compose, healthcheck y volumen |
| 04 | Migraciones y repositorio de análisis | Preparado para revisión: SQLAlchemy, Alembic y pruebas PostgreSQL |
| 05 | Guardado desde el análisis | Pendiente |
| 06 | Catálogo canónico | Pendiente |
| 07 | Metadatos del parser | Pendiente |
| 08 | Resolver determinista | Pendiente |
| 09 | Confirmación humana | Pendiente |
| 10 | Tiempos y ataques musicales | Pendiente |
| 11 | Características locales | Pendiente |
| 12 | Políticas de dificultad | Pendiente |
| 13 | Grados 1–6 | Pendiente |
| 14 | Detector de criticidad | Pendiente |
| 15 | Prioridad y presupuesto de ensayo | Pendiente |
| 16 | Evidencias en interfaz | Pendiente |
| 17 | Persistencia de feedback | Pendiente |
| 18 | Formulario de valoración | Pendiente |
| 19 | Herramienta de evaluación | Pendiente |
| 20 | Puerto IA y fake/demo | Pendiente |
| 21 | Adaptador LangChain | Pendiente |
| 22 | Revisión independiente | Pendiente |
| 23 | Caché y trazabilidad | Pendiente |
| 24 | Comparación experimental | Pendiente |
| 25 | Estrategia híbrida experimental | Pendiente |

## Criterios de aceptación

1. Especificaciones enlazadas y distinción entre previsto e implementado.
2. Baseline regenerable con casos sintéticos y candidatos a error sin etiquetas expertas inventadas.
3. Arranque PostgreSQL, healthcheck y volumen, sin credenciales reales versionadas.
4. Migración desde base vacía, persistencia transaccional y pruebas PostgreSQL reales.
5. Análisis guardado con ID y versiones, conservado tras reiniciar.
6–9. Alias multilingües, variantes, metadatos, UNKNOWN y confirmación humana coherente con BandFit/audio.
10–12. Tiempos y ataques correctos en voces/acordes/ligaduras, tempo local, descansos y perfiles configurables.
13. Escalas y rúbrica explícitas; API y frontend adaptados conjuntamente.
14–15. Detector independiente, cero críticos y presupuesto de ensayo respetado.
16–19. Evidencias, feedback por análisis/pasaje/versiones y evaluación reproducible por obra, sin leakage.
20–25. Salidas IA validadas, demo identificada, fallback, versiones, caché y comparación sin anchoring ni resultados inventados. El híbrido sigue siendo experimental.

## Más adelante

PR independientes de autenticación, autorización y despliegue PostgreSQL gestionado, con backup/restauración. Audio: interfaz del renderer actual, eventos expresivos y muestras opcionales tras comprobar licencia; no sacrificar la evaluación musical.

## Mapa de impacto

| Módulo | Carpeta | Componentes | Cambio previsto |
|---|---|---|---|
| Parser/modelo | backend/parsers, backend/domain | parse_musicxml, ScorePart, ScoreNote | Identidad instrumental, transposición, tiempo y ataques |
| Análisis | backend/analyzers | dificultad, perfiles, ensayo | Dificultad local, criticidad y prioridad separadas |
| Aplicación/infraestructura | backend/application, backend/infrastructure | Nuevos puertos/repositorios | Persistencia, IA y caché sin dependencias externas en dominio |
| Presentación | backend/app | /analyze, frontend | IDs, evidencias, escalas y feedback |
| Evaluación | evaluation | Casos, etiquetas y exportación | Baseline, métricas y comparación reproducible |
