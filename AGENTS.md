# Guía de trabajo — ScoreMasterAI / ScoreLint

## Selección de skills y responsabilidades

Antes de abordar una tarea, identifica su objetivo y lee el `SKILL.md` local
correspondiente en la tabla. Usa las copias de `skills/` de este repositorio como
referencia del proyecto, aunque exista una instalación global de la misma skill.
Las rutas son relativas a la carpeta que contiene este `AGENTS.md`.

| Tipo de tarea | Skill responsable | Responsabilidad y límites |
|---|---|---|
| Lectura MusicXML/MXL e identidad instrumental | [scoremaster-musicxml](skills/scoremaster-musicxml/SKILL.md) | Parser, metadatos, transposición, tiempos, aliases y confirmación de instrumentos. Conserva la información necesaria para los consumidores. |
| Motor determinista de análisis | [scoremaster-scorelint](skills/scoremaster-scorelint/SKILL.md) | Métricas, reglas, findings, dificultad, escalas y criticidad; pruebas y regresiones del algoritmo. |
| Adecuación a la banda y planificación | [scoremaster-bandfit-rehearsal](skills/scoremaster-bandfit-rehearsal/SKILL.md) | Cobertura de partes, disponibilidad, necesidades de intérpretes, prioridades y presupuesto de ensayo. |
| Integración de IA | [scoremaster-ai-layer](skills/scoremaster-ai-layer/SKILL.md) | Puertos y proveedores, prompts, salida estructurada, demo/fake, fallback, caché y trazabilidad. No sustituye hechos musicales por inferencias. |
| Frontend, notación y reproducción | [scoremaster-ui-audio](skills/scoremaster-ui-audio/SKILL.md) | Interfaz, accesibilidad, visor, estado de sesión y audio. React en `frontend/`, compilado a `backend/app/static/frontend/` y servido por FastAPI. |
| API, datos e infraestructura de ejecución | [scoremaster-api-persistence](skills/scoremaster-api-persistence/SKILL.md) | Contratos HTTP, uploads, repositorios, transacciones, PostgreSQL, Alembic y Docker. |
| Evaluación y evidencia experimental | [scoremaster-evaluation](skills/scoremaster-evaluation/SKILL.md) | Baseline, benchmark, protocolo de feedback, métricas, comparación de métodos y resultados reproducibles. |
| Revisión del criterio musical | [scoremaster-musical-reviewer](skills/scoremaster-musical-reviewer/SKILL.md) | Validez musical de reglas y resultados, contexto instrumental y recomendaciones con evidencias por parte y compás. No constituye validación humana del benchmark. |

## Cómo aplicar esta distribución

- Selecciona una skill principal por objetivo y añade otras solo cuando la tarea
  atraviese sus responsabilidades. Lee únicamente sus referencias pertinentes;
  no cargues todas las skills para cada cambio.
- Una skill aporta instrucciones que aplica el asistente. Esta distribución no
  requiere crear subagentes ni ampliar el alcance de la petición.
- Para corregir una regla musical, usa `scoremaster-scorelint`; añade
  `scoremaster-musical-reviewer` si hay que revisar su fundamento musical y
  `scoremaster-evaluation` si hay que medir su efecto sobre el benchmark.
- Para corregir instrumentos, empieza por `scoremaster-musicxml` y consulta las
  skills de BandFit o audio cuando sus consumidores resulten afectados.
- Para generar planes mediante LLM, combina `scoremaster-ai-layer` con
  `scoremaster-bandfit-rehearsal`: el proveedor genera una propuesta y el dominio
  valida referencias, disponibilidad y presupuesto.
- Mantén los controles de seguridad aplicables en cualquier implementación
  (ver `docs/SECURITY.md`).
- Las instrucciones del usuario prevalecen sobre las guías de las skills.
  Consulta `CONTRIBUTING.md` y `docs/IMPLEMENTATION_ROADMAP.md` para el flujo de
  trabajo y las decisiones aprobadas. Una skill no autoriza por sí misma publicar,
  desplegar, integrar cambios o contactar servicios externos.
- Ejecuta las comprobaciones pertinentes de las skills seleccionadas y comunica
  lo modificado, lo verificado y las limitaciones. En cambios exclusivamente
  documentales, revisa contenido y enlaces sin crear pruebas artificiales.
