> Propuesta para el README cuando las funcionalidades estén implementadas; consultar el [plan aprobado](../IMPLEMENTATION_ROADMAP.md).

# Cambios recomendados para README.md

NO reemplazar el README actual. Integrar estas secciones donde encajen.

## Añadir a arquitectura

```text
MusicXML
   ↓
ScoreLint deterministic analysis
   ↓
Candidate passages
   ↓
Optional AI review
   ↓
Hybrid assessment
   ↓
MaestroAI
```

Aclarar:

- El LLM no sustituye al análisis MusicXML.
- La aplicación puede funcionar sin API key mediante el modo documentado.
- Los resultados IA pueden estar deshabilitados/fallback.
- Instrument normalization utiliza un pipeline híbrido.

## Añadir a funcionalidades

- Multilingual instrument normalization.
- Difficulty by target level.
- Critical passage detection separated from difficulty.
- Evidence/explainability.
- Optional LLM difficulty review.
- Human expert feedback.
- Sample-based audio si ya está implementado.

## Añadir a IA

Explicar brevemente:

```text
Deterministic ScoreLint
+
semantic embeddings
+
optional LLM review
+
human feedback
```

No afirmar que un modelo "aprende" de usuarios si solo se guardan aliases o feedback.

## Añadir a evaluación

Describir:
- expert-labelled benchmark;
- heuristic vs LLM vs hybrid;
- métricas reales una vez ejecutado.

No incluir números inventados.
