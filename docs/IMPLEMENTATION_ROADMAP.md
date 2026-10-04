# Plan aprobado y estado de implementación

## Decisiones que prevalecen

- PostgreSQL en desarrollo y producción; SQLAlchemy, Alembic y repositorios independientes del dominio.
- Grados visibles enteros 1–6 y rúbrica propia documentada, sin afirmar certificación oficial. Índice técnico interno 0–10; transformación explícita. Actualmente la aplicación sigue usando grados 1–5 e índice 0–5 hasta la entrega 13.
- Nivel objetivo por defecto intermedio, separado del grado editorial estimado.
- Separar Difficulty, Criticality y RehearsalPriority. Un análisis puede devolver cero críticos.
- Los ensayos son de conjunto: un pasaje común es el que varias partes tocan igual en estructura —misma línea (mismo ritmo e intervalos, cada una en su tonalidad u octava) o mismo ritmo—, aunque sean de familias distintas. En cada pasaje se ensaya primero cada línea común, después las subsecciones con lo que queda (flautas, dobles cañas, clarinetes, saxofones, metales agudos, graves —con fagot, clarinete bajo y saxo barítono—, percusión, cuerda y rítmica) y al final un tutti para juntar (decisiones de la autora, 2026-10-04).
- Primera entrega: base musical fiable. Después revisión estructurada LLM y evaluación híbrida; sin chatbot, RAG ni agentes autónomos.
- Persistir resultados estructurados y feedback, no partituras originales ni bancos de audio.
- Evaluación local inicialmente; autenticación y autorización antes de publicar historial multiusuario.
- Un objetivo por PR, pruebas y documentación. Integración secuencial mediante squash.

## Baseline integrado

Las PR #11–#16 están integradas. La PR #5 se cerró porque su densidad rítmica y agrupación ya estaban incorporadas. Comprobaciones: 62 pruebas Python, 5 pruebas Node y recorrido Playwright sobre carga, instrumentos, visor, reinicio, móvil y pasajes.

PostgreSQL local está integrado mediante la PR #19. El repositorio y las migraciones están integrados en la PR #21. El guardado desde la API está integrado en la PR #22; todavía no existe proveedor LLM. El audio actual ya usa muestras General MIDI para instrumentos afinados y síntesis para percusión. La resistencia actual es una aproximación por compases. Los hallazgos se agrupan como críticos, pendiente del detector separado.

La corrección del audio del clarinete, el pasaje completo y los controles compartidos están integrados en la PR #20. Las siguientes PR retoman el plan musical y de persistencia.

## Entregas

Los números 01–25 identifican pasos del plan, no números de GitHub. Los pasos 04 y 05 están integrados en las PR #21 y #22. La transición a React está integrada (PR #23, #25 y #26) y GitHub Actions valida cada PR antes del paso 06.

| Entrega | Objetivo | Estado |
|---|---|---|
| 01 | Especificación consolidada | Integrada: PR #17 |
| 02 | Baseline reproducible | Integrada: PR #18; 15 casos, 10 nombres y audio |
| 03 | PostgreSQL en desarrollo | Integrado en PR #19: Compose, healthcheck y volumen |
| 04 | Migraciones y repositorio de análisis | Integrado: PR #21; SQLAlchemy, Alembic y pruebas PostgreSQL |
| 05 | Guardado desde el análisis | Integrado: PR #22; ID, resultados y configuración persistidos |
| 06 | Catálogo canónico | Integrado: PR #28 |
| 07 | Metadatos del parser | Integrado: PR #29 |
| 08 | Resolver determinista | Integrado: resolver (PR #30), dificultad (PR #31), sección rítmica (PR #32) y timbre (PR #33); BandFit con el paso 09 |
| 09 | Confirmación humana | Integrado: PR #42; confirmación en «Mi banda» y BandFit por instrumento |
| 10 | Tiempos y ataques musicales | Pendiente |
| 11 | Características locales | Pendiente |
| 12 | Políticas de dificultad | Pendiente |
| 13 | Grados 1–6 | Pendiente |
| 14 | Detector de criticidad | Integrado: frases (PR #40), detector con señal de velocidad (PR #41) y cadencias armónicas (PR #43) |
| 15 | Prioridad, pasajes comunes y presupuesto de ensayo de conjunto | Integrado: PR #37, calendario (PR #38) y similitud de estructura (PR #39) |
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
14. Detector independiente y cero críticos posible.
15. Ensayo de conjunto: pasajes comunes por similitud de estructura (misma línea en cualquier tonalidad u octava, o mismo ritmo), bloques de línea común seguidos de subsecciones de ensayo con las partes restantes y tutti final; cada bloque indica partes, compases, minutos y motivos; suma de bloques ≤ tiempo disponible; cero pasajes produce solo un tutti; el planificador legacy queda congelado para el baseline.
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

## Transición a React antes del paso 06

Tres PR independientes, revisadas antes del commit:

| PR de transición | Alcance | Estado |
|---|---|---|
| React 1 | Build reproducible, carga/análisis, asignaciones, estados y cancelación | Integrada: PR #23 |
| React 2 | Dashboard, dificultad, BandFit, ensayo y navegación | Integrada: PR #25 |
| React 3 | Visores, vídeos y reproducción; retirada del adaptador temporal | Integrada: PR #26 |

Se conserva el diseño y se verifica cada recorrido con Playwright. La primera
PR monta React en el formulario mediante un adaptador temporal para las vistas
existentes. [Detalles y arranque](../frontend/README.md). No modifica los algoritmos
musicales ni el esquema de PostgreSQL.
