> Backlog previsto; consultar el [plan aprobado](../IMPLEMENTATION_ROADMAP.md).

# Implementation Task — AI Evolution

## Contexto

MaestroAI ya está construido.

Esta tarea NO consiste en crear una aplicación nueva.

Consiste en evolucionar el sistema existente resolviendo problemas observados durante pruebas reales.

## Scope

Implementar de forma incremental:

1. Instrument Resolution.
2. Difficulty / Criticality separation.
3. LangChain AI layer.
4. Hybrid Difficulty.
5. Expert Feedback foundation.
6. Explainability/confidence.
7. Audio architecture improvement si el core anterior queda estable.

---

# EPIC 1 — Instrument Resolution

## Story 1.1 — Canonical ontology

Crear/adaptar catálogo canónico.

Acceptance criteria:
- IDs estables.
- Alias no codificados solo en `if/else`.
- No colapsar variantes incompatibles.
- Tests.

## Story 1.2 — Metadata-first resolution

Acceptance criteria:
- MusicXML metadata tiene prioridad cuando es suficientemente explícita.
- Part name se usa como evidencia, no como único dato.
- Transposition se conserva.

## Story 1.3 — Alias matching

Acceptance criteria:
- español e inglés;
- soporte inicial italiano cuando ya existan casos;
- abbreviations;
- part number parsing;
- specific alias wins over generic substring.

## Story 1.4 — Embedding resolver

Acceptance criteria:
- solo entra si alias/metadata no bastan;
- top-k candidates;
- configurable threshold;
- in-memory/cache;
- no remote vector DB.

## Story 1.5 — LLM fallback

Acceptance criteria:
- catálogo cerrado;
- structured output;
- UNKNOWN;
- confidence;
- timeout/fallback.

## Story 1.6 — User confirmation

Acceptance criteria:
- baja confianza no se acepta silenciosamente;
- puede corregirse;
- diseño preparado para guardar alias confirmado.

---

# EPIC 2 — Difficulty

## Story 2.1 — Baseline tests

Antes de refactor:
- capturar falsos positivos actuales;
- capturar ejemplos fáciles;
- capturar ejemplos difíciles.

## Story 2.2 — noteRate

Acceptance criteria:
- ritmo y tempo dejan de contarse ciegamente dos veces;
- feature documentada;
- tests slow vs fast.

## Story 2.3 — target level

Acceptance criteria:
- dificultad depende del nivel objetivo;
- defaults compatibles con comportamiento actual;
- UI/API no se rompe.

## Story 2.4 — family profiles

MVP:
- woodwind;
- brass;
- percussion.

Acceptance criteria:
- configuración;
- tests;
- posibilidad de overrides futuros.

---

# EPIC 3 — Critical Passage Detector

## Story 3.1 — Responsibility separation

Acceptance criteria:
- Difficulty no marca crítico.
- Detector independiente.
- Cero críticos permitido.

## Story 3.2 — Absolute threshold

Configurable.

## Story 3.3 — Relative percentile

Configurable por part/instrument context.

## Story 3.4 — Prominence

Acceptance criteria:
- picos locales reales;
- plateau bajo no crítico;
- tests.

## Story 3.5 — Persistence

Acceptance criteria:
- evitar micro-picos irrelevantes;
- usar unidad temporal/beat disponible.

## Story 3.6 — UX levels

```text
NORMAL
ATTENTION
DIFFICULT
CRITICAL
```

No forzar los Top N a critical.

---

# EPIC 4 — LangChain

## Story 4.1 — Integration boundary

Acceptance criteria:
- LangChain queda en infraestructura;
- dominio no importa directamente componentes LangChain si se puede evitar;
- provider interface existente se conserva/adapta.

## Story 4.2 — Structured outputs

Pydantic/schema para:
- instrument resolution;
- difficulty review;
- rehearsal plan.

## Story 4.3 — Cache

Acceptance criteria:
- key versioned;
- cache hit test;
- prompt/model change invalidates.

## Story 4.4 — Failure fallback

Acceptance criteria:
- API failure no rompe análisis;
- deterministic result shown;
- status indicates AI review unavailable.

---

# EPIC 5 — Hybrid Difficulty

## Story 5.1 — Independent LLM assessment

No enviar heuristicDifficulty al LLM en benchmark mode.

## Story 5.2 — Store three values

```text
heuristic
llm
hybrid
```

cuando LLM esté disponible.

## Story 5.3 — Disagreement

Configurable threshold.

Acceptance criteria:
- detect;
- log;
- explain internally.

## Story 5.4 — Hybrid strategy

Configuración preparada para evaluar:
- weighted;
- confidence weighted;
- bounded correction.

No fijar estrategia final sin benchmark.

---

# EPIC 6 — Expert Feedback

## Story 6.1 — Feedback persistence

Guardar:
- difficulty;
- critical;
- optional rehearsal priority/comment.

## Story 6.2 — Feedback UI

Debe ser rápida y no bloquear uso normal.

## Story 6.3 — Evaluation export

Poder exportar/consultar datos necesarios para calcular métricas.

No exponer datos privados innecesarios.

---

# EPIC 7 — Explainability

## Story 7.1 — Evidence

Mostrar "¿Por qué?":

- tempo;
- note rate;
- range;
- rest ratio;
- endurance;
- relevant features.

## Story 7.2 — Confidence

Mostrar:
- alta;
- media;
- baja;
o equivalente UX.

## Story 7.3 — Abstention

No inventar:
- instrumento;
- IA;
- criticidad.

---

# EPIC 8 — Audio

Implementar solo si EPIC 1–7 están estables.

## Story 8.1 — Renderer interface
## Story 8.2 — Sample-backed renderer
## Story 8.3 — Dynamic/articulation mapping
## Story 8.4 — Optional asset installer

---

# Migration / Compatibility

- Migraciones de BD idempotentes según stack actual.
- Defaults para datos existentes.
- APIs actuales compatibles cuando sea razonable.
- Frontend debe manejar ausencia de campos AI nuevos.

---

# Tests required

Como mínimo:

## Instruments
- multilingual exact aliases;
- ambiguous;
- English Horn trap;
- unknown;
- low confidence.

## Difficulty
- tempo interaction;
- range isolated vs sustained;
- family differences;
- target level.

## Criticality
- easy work returns zero critical;
- real peak;
- low plateau;
- short spike;
- sustained difficult passage.

## AI
- schema validation;
- fallback;
- cache;
- prompt version;
- provider unavailable.

## Feedback
- persistence;
- export/access.

---

# Definition of Done

No cerrar esta tarea hasta que:

- tests pasen;
- falsos positivos iniciales se hayan re-evaluado;
- instrument resolution tenga tests;
- zero-critical sea posible;
- LLM failure tenga fallback;
- model/prompt/features versions queden trazables;
- docs se actualicen.
