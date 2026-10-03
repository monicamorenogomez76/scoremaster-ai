> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# CODEX_START_HERE.md

## Objetivo

Implementar la siguiente evolución de **MaestroAI / ScoreLint** sobre el proyecto YA existente, sin reconstruirlo desde cero:

1. Normalización robusta y multilingüe de instrumentos.
2. Separación real entre dificultad y criticidad.
3. Revisión de dificultad mediante LLM sin sustituir el análisis determinista.
4. Arquitectura híbrida `Heurística + LLM + validación experta`.
5. Uso controlado de LangChain para LLM, embeddings y salida estructurada.
6. Feedback de músicos y benchmark de evaluación.
7. Explicabilidad, confianza, abstención y trazabilidad.
8. Audio más realista mediante samples.
9. Cache y versionado de prompts/modelos/features.

La especificación detallada está repartida en los documentos enlazados al final de este archivo.

---

# INSTRUCCIÓN PRINCIPAL PARA CODEX

Trabaja directamente sobre el repositorio real.

## Antes de modificar código

Inspecciona y documenta brevemente la implementación existente de:

- parser MusicXML;
- modelo de dominio musical;
- identificación/clasificación de instrumentos;
- cálculo de dificultad;
- cálculo por instrumento y pasaje;
- detección de pasajes críticos;
- análisis de ritmo;
- tempo;
- tesitura/range;
- intervalos;
- articulaciones;
- endurance/resistencia;
- BandFit;
- RehearsalAI;
- integración actual con LLM;
- providers de IA;
- generación/reproducción de audio;
- DTOs/API;
- frontend relacionado;
- persistencia;
- tests.

No asumas que los nombres propuestos en estos documentos existen.

No crees una arquitectura paralela si ya hay componentes equivalentes.

## Entrega primero un mapa de impacto

Antes de implementar, responde con:

| Módulo | Carpeta | Archivo/Clase | Método/Componente | Cambio previsto |
|---|---|---|---|---|

Después continúa con la implementación.

## Reglas

- Cambios incrementales.
- Mantener compatibilidad con la aplicación actual.
- Evitar breaking changes innecesarios.
- No eliminar funcionalidad existente que siga siendo válida.
- No introducir dependencias pesadas sin justificar.
- Tests para cada cambio de comportamiento.
- No usar un LLM como única fuente de verdad musical.
- Toda salida del LLM que alimente lógica debe ser estructurada y validada.
- Si la IA falla, la aplicación debe conservar un comportamiento funcional determinista.
- El modo demo/offline actual debe seguir funcionando.
- No incluir assets con licencias incompatibles con un repositorio público.
- Actualizar documentación al finalizar.

---

# ORDEN DE IMPLEMENTACIÓN

Implementar en este orden. No saltar a una fase posterior si la anterior no está estable.

## Fase 0 — Baseline

1. Ejecutar tests.
2. Guardar comportamiento actual de ejemplos representativos.
3. Identificar al menos:
   - 5 nombres de instrumentos que actualmente se clasifican mal o de forma inconsistente;
   - 5 falsos positivos de pasajes críticos;
   - 3 casos de dificultad claramente sobreestimada;
   - 1 ejemplo de audio actual.
4. Crear tests de regresión antes de cambiar comportamiento cuando sea posible.

## Fase 1 — InstrumentResolver

Implementar:
- ontología/catálogo canónico;
- normalización textual;
- uso prioritario de metadatos MusicXML;
- aliases;
- matching semántico por embeddings;
- fallback LLM;
- confidence;
- UNKNOWN/abstention;
- confirmación humana;
- persistencia opcional de alias confirmados.

Especificación:
`docs/INSTRUMENT_RESOLUTION.md`

## Fase 2 — Difficulty / Criticality

Separar:
- `Difficulty`
- `Criticality`
- `RehearsalPriority`

Revisar:
- doble penalización ritmo + tempo;
- uso de note/event rate;
- tesitura;
- resistencia;
- perfiles por familia instrumental;
- nivel del intérprete/banda;
- prominencia local;
- persistencia temporal;
- umbrales configurables;
- posibilidad de cero pasajes críticos.

Especificación:
`docs/DIFFICULTY_CRITICALITY.md`

## Fase 3 — AI layer con LangChain

Usar LangChain SOLO donde aporte valor:

- abstracción de chat model;
- embeddings;
- prompts;
- structured output;
- retry/fallback si ya encaja con arquitectura existente.

No introducir por ahora:
- LangGraph;
- agentes autónomos;
- RAG;
- vector DB externa.

Implementar:
- `Instrument LLM Fallback`;
- `DifficultyReviewer`;
- `RehearsalPlanner` estructurado;
- cache;
- prompt versioning;
- model/version metadata.

Especificación:
`docs/LLM_LANGCHAIN_ARCHITECTURE.md`

## Fase 4 — Hybrid Assessment

Comparar de forma independiente:

- Heuristic Difficulty;
- LLM Difficulty;
- Hybrid Difficulty.

Para evaluación, el LLM NO debe conocer inicialmente el score heurístico para evitar anchoring.

Añadir detección de desacuerdo significativo.

Ejemplo:

```text
Heuristic = 8.2
LLM       = 5.1
Difference = 3.1
```

Debe quedar trazabilidad de:
- resultados;
- evidencias;
- versión de algoritmo;
- versión de features;
- modelo;
- prompt.

## Fase 5 — Expert Feedback + benchmark

Añadir capacidad para recoger:

- dificultad humana;
- crítico sí/no;
- opcionalmente prioridad de ensayo;
- comentario.

Crear dataset evaluable.

Especificación:
`docs/EVALUATION_AND_FEEDBACK.md`

## Fase 6 — Audio realista

No reescribir el análisis musical para resolver el audio.

Mantener MusicXML/MIDI/eventos como representación si ya funciona.

Añadir un renderer basado en samples detrás de una interfaz.

Especificación:
`docs/REALISTIC_AUDIO.md`

## Fase 7 — UX / explicabilidad

La UI debe mostrar:

- resultado simple para el director/músico;
- botón o panel "¿Por qué?";
- evidencias;
- confianza;
- aviso cuando existe baja confianza;
- cero críticos cuando corresponda;
- diferencia entre "pasaje crítico" y "pasaje que merece atención".

---

# CRITERIO DE FINALIZACIÓN

Antes de dar la tarea por terminada:

1. Ejecutar tests.
2. Mostrar tests añadidos/modificados.
3. Documentar falsos positivos corregidos.
4. Mostrar al menos un caso UNKNOWN/low-confidence de instrumento.
5. Mostrar al menos una obra/pasaje sin críticos.
6. Mostrar comparación Heuristic / LLM / Hybrid.
7. Verificar fallback si el proveedor LLM no está disponible.
8. Verificar que el proyecto sigue arrancando con el mecanismo documentado actual.
9. Actualizar README/CHANGE/CONTRIBUTING solo donde proceda.

## Informe final de Codex

Termina con:

### Archivos modificados
...

### Cambios funcionales
...

### Tests ejecutados
...

### Resultados
...

### Decisiones técnicas
...

### Riesgos / trabajo pendiente
...

---

# Documentos a leer

1. `AGENTS.md`
2. `PLAN_MAESTROAI_AI_EVOLUTION.md`
3. `docs/INSTRUMENT_RESOLUTION.md`
4. `docs/DIFFICULTY_CRITICALITY.md`
5. `docs/LLM_LANGCHAIN_ARCHITECTURE.md`
6. `docs/EVALUATION_AND_FEEDBACK.md`
7. `docs/REALISTIC_AUDIO.md`
8. `docs/tasks/IMPLEMENT_AI_EVOLUTION.md`

No implementar a partir de un único documento aislado: respetar las decisiones del conjunto.
