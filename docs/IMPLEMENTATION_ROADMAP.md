# Plan aprobado y estado de implementación

## Decisiones que prevalecen

- PostgreSQL en desarrollo y producción; SQLAlchemy, Alembic y repositorios independientes del dominio.
- Grados visibles enteros 1–6 y rúbrica propia documentada, sin afirmar certificación oficial. Índice técnico interno 0–10; transformación explícita. Integrado en el paso 13: índice = 2 × puntuación anterior, seis tramos iguales y `scale` en el resultado; el baseline conserva 1–5/0–5.
- Nivel objetivo por defecto intermedio, separado del grado editorial estimado.
- Separar Difficulty, Criticality y RehearsalPriority. Un análisis puede devolver cero críticos.
- Los ensayos son de conjunto: un pasaje común es el que varias partes tocan igual en estructura —misma línea (mismo ritmo e intervalos, cada una en su tonalidad u octava) o mismo ritmo—, aunque sean de familias distintas. En cada pasaje se ensaya primero cada línea común, después las subsecciones con lo que queda (flautas, dobles cañas, clarinetes, saxofones, metales agudos, graves —con fagot, clarinete bajo y saxo barítono—, percusión, cuerda y rítmica) y al final un tutti para juntar (decisiones de la autora, 2026-10-04).
- Primera entrega: base musical fiable. Después revisión estructurada LLM y evaluación híbrida. Asistente conversacional solo con evidencias validadas (partes, compases, hallazgos, plan y diario) y demo identificada sin API key; sin RAG ni agentes autónomos (decisión de la autora, 2026-10-04).
- Persistir resultados estructurados y feedback. El MusicXML original se guarda privado de su usuario y se borra con la obra o la cuenta; no se guardan bancos de audio (decisión de la autora, 2026-10-04).
- Cuentas con email y contraseña (Google opcional), sesiones en servidor y CSRF; cada dato pertenece a un usuario y se autoriza en el servidor (decisión de la autora, 2026-10-04).
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
| 10 | Tiempos y ataques musicales | Integrado: PR #48; acordes, ligaduras, voces y adornos |
| 11 | Características locales | Pendiente |
| 12 | Políticas de dificultad | Pendiente |
| 13 | Grados 1–6 | Integrado: PR #49 |
| 14 | Detector de criticidad | Integrado: frases (PR #40), detector con señal de velocidad (PR #41) y cadencias armónicas (PR #43) |
| 15 | Prioridad, pasajes comunes y presupuesto de ensayo de conjunto | Integrado: PR #37, calendario (PR #38) y similitud de estructura (PR #39) |
| 16 | Evidencias en interfaz | Integrado: campañas con la predicción de cada pasaje (PR #70, #74) |
| 17 | Persistencia de feedback | Integrado: PR #70 (migración 0009) |
| 18 | Formulario de valoración | Integrado: PR #76 |
| 19 | Herramienta de evaluación | En revisión: informe de una campaña exportada con MAE, Spearman, precisión, recall, F0.5 y acuerdo entre evaluadores |
| 20 | Puerto IA y fake/demo | En revisión: puerto, demo identificada y «¿Por qué esta dificultad?» de la obra |
| 21 | Adaptador LangChain | Pendiente |
| 22 | Revisión independiente | Pendiente |
| 23 | Caché y trazabilidad | Pendiente |
| 24 | Comparación experimental | Pendiente |
| 25 | Estrategia híbrida experimental | Pendiente |

## Ampliación aprobada (2026-10-04)

Plan detallado: cuentas, biblioteca, sustitutos, conciertos y diario, asistente con evidencias,
nivel por sección y coordinación del conjunto. Una PR por fase, con TDD.

| Fase | Objetivo | Estado |
|---|---|---|
| A1 | Cuentas y sesión (email/contraseña, Google opcional, CSRF, cabeceras, límites de subida) | Integrado: PR #45 |
| A2 | Biblioteca de obras y banda por usuario (MusicXML privado y borrable) | Integrado: PR #46 |
| A3 | Sustitutos de instrumento (tabla revisable, tesitura y músicos libres) | Pendiente |
| A4 | Conciertos y calendario de ensayos con varias obras | Integrado: PR #58–#61 y #65 |
| A5 | Diario de ensayos (pendiente/resuelto, notas y propuestas confirmadas) | Integrado: revisión por bloque y replanificación (PR #58–#61) |
| A6 | Asistente conversacional con evidencias (demo y proveedor real) | Pendiente |
| A7 | Nivel por sección en la banda | Integrado: PR #63–#64 (varias bandas con plantilla fija); aún no lo usa el planificador |
| A8 | Dificultad de coordinación del conjunto | Pendiente |

## Orden de trabajo acordado (2026-10-05)

Se priorizan la IA y la evaluación experimental, obligatorias para el TFM, sobre la ampliación:

1. Paso 10: la base de las métricas se corrige antes de medir.
2. Paso 13 (y 11–12 si lo requiere): escala fijada antes de pedir valoraciones.
3. Paso 20: puerto IA y demo identificada sin API key.
4. Pasos 16–18: evidencias y formulario; los músicos necesitan días para responder.
5. Pasos 19 y 21–24: evaluación, adaptador LLM y comparación.

Las fases A3–A8 y el paso 25 se abordan solo si queda margen tras el paso 24.

## Propuesta de interfaz (2026-10-05)

Navegación de la autora: Resumen · Repertorio · Mi banda · Ensayos · Asistente IA · Configuración,
con blanco frío, grafito y azul eléctrico. Un ensayo puede trabajar varias obras y cada bloque de
su agenda indica la obra que se trabaja (decisiones de la autora).

| Fase | Objetivo | Estado |
|---|---|---|
| F1 | Estado de preparación, prioridades, Resumen, Repertorio y detalle de obra | Integrado: PR #51 y #52 |
| F2a | Ensayos guardados: varias obras, agenda por bloques editable y «Ensayo de hoy»; Configuración básica | Integrado: PR #53–#57; Configuración en revisión |
| F2b | Asistente IA (paso 20): conversación sobre el ensayo y explicación del plan, con modo demo identificado; el panel solo vuelve con lo que aporte la IA | Pendiente |
| — | Evaluación (pasos 16–18) | Pendiente, antes de F3 |
| C1–C4 | Calendario de conciertos (2026-10-06): programa, patrón semanal, serie por fases hasta el ensayo general, revisión por bloque y replanificación | Integrado: PR #58–#62 y #65 (navegación a los pasajes y siguiente paso en el Resumen) |
| F3 | Observaciones de ensayo y cierre: «Prioridades por sección» con las notas del último ensayo | Adelantado en C4: lo pendiente de la última revisión |

## Despliegue adelantado (2026-10-07)

Para que los músicos valoren con cuenta propia, la aplicación se publica en Render antes de la
evaluación (plan gratuito, decisión de la autora): ver [DEPLOYMENT.md](DEPLOYMENT.md).

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

## Opcional: partituras en PDF con Audiveris (decisión de la autora, 2026-10-06)

Importar PDF y convertirlos a MusicXML con Audiveris (OMR) queda como **opcional**, después de
integrar lo pendiente y lanzar la evaluación (pasos 16–18). Amplía el alcance inicial, que excluía
PDF y OCR. Condiciones si se aborda:

- **O1, prueba de viabilidad (1 día):** imagen con Java 21, Audiveris en modo de línea de comandos
  y Tesseract; convertir 2–3 PDF propios o de dominio público y medir tiempo y aciertos antes de
  decidir O2–O4.
- **O2–O4 (unos 3 días):** servicio `omr` en contenedor aparte, tras un perfil de Compose (el
  arranque normal sigue ligero), sin red, con usuario sin privilegios, límites de CPU, memoria,
  tamaño, páginas y tiempo; conversión asíncrona por trabajos; el MusicXML resultante pasa las
  validaciones de siempre y la obra queda marcada como «leída de PDF», con aviso de revisión y
  confirmación de instrumentos. Las obras leídas de PDF no entran en el benchmark.
- **Licencia:** Audiveris es AGPL-3.0: usarlo sin modificar, en su contenedor, y enlazar su código
  fuente. Antes, decidir la licencia del proyecto (el repositorio aún no tiene `LICENSE`).

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
