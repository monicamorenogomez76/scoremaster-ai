> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# LLM / LangChain Architecture

## 1. Objetivo

Utilizar LangChain como infraestructura de IA sin convertir el proyecto en una aplicación dependiente de LangChain.

## 2. Usos aprobados

LangChain puede utilizarse para:

- chat model abstraction;
- embeddings abstraction;
- prompt templates;
- structured output;
- provider switching;
- retry/fallback si simplifica la integración.

## 3. Fuera de alcance actual

No introducir ahora:

- LangGraph;
- agentes autónomos;
- multi-agent;
- RAG;
- vector DB remota;
- conversational memory;
- fine-tuning.

Estas tecnologías deben añadirse solo si resuelven una necesidad real.

---

# 4. AI services

Conceptualmente:

```text
AI Layer
├── InstrumentSemanticResolver
├── InstrumentLlmResolver
├── DifficultyReviewer
└── RehearsalPlanner
```

Adaptar nombres a arquitectura existente.

## InstrumentSemanticResolver

Entrada:
- normalized name;
- aliases/canonical catalogue.

Salida:
- top candidates;
- similarity;
- confidence.

Para el catálogo pequeño:
- embeddings en memoria/cache;
- no vector DB.

## InstrumentLlmResolver

Solo fallback.

Entrada:
- original name;
- normalized name;
- MusicXML metadata;
- top semantic candidates;
- allowed catalogue.

Debe elegir:
- canonical id permitido;
- UNKNOWN.

Salida estructurada.

## DifficultyReviewer

Entrada:
- instrument canonical data;
- target level;
- structured features.

Para benchmark independiente:
- NO incluir heuristic score.

Salida estructurada:

```json
{
  "difficulty": 5.8,
  "confidence": 0.87,
  "mainFactors": [],
  "reason": "..."
}
```

## RehearsalPlanner

Entrada:
- final difficulty;
- criticality;
- rehearsal priority;
- BandFit;
- available musicians;
- duration;
- passages.

Salida estructurada con bloques temporales y justificación.

---

# 5. Provider abstraction

No acoplar dominio directamente a LangChain.

Mantener interfaz/aplicación propia equivalente a:

```text
ChatModelProvider
EmbeddingProvider
```

o adaptarse a abstracciones existentes.

Esto permite:
- provider real;
- demo provider;
- testing fake;
- cambio futuro de proveedor.

LangChain debe quedar detrás de infraestructura.

---

# 6. Structured output

Toda respuesta usada por lógica debe validarse con schemas/Pydantic.

No hacer:

```text
response = llm(...)
parse manually with regex
```

Preferir:
- schema;
- enum;
- bounded numeric values;
- explicit UNKNOWN.

Validar:
- difficulty 0..10;
- confidence 0..1;
- canonical IDs existentes.

---

# 7. Prompt versioning

Cada prompt debe tener un identificador estable:

```text
instrument-resolution-v1
difficulty-review-v1
rehearsal-plan-v1
```

Persistir con resultados cuando proceda:

```text
promptVersion
model
provider
featuresVersion
algorithmVersion
```

No es necesario persistir el prompt completo en cada registro.

---

# 8. Cache

Evitar llamadas repetidas.

Clave conceptual:

```text
hash(
  normalizedInput
  + structuredFeatures
  + targetLevel
  + model
  + promptVersion
  + featuresVersion
)
```

La cache debe invalidarse cuando cambia:
- prompt;
- modelo;
- features;
- input.

No cachear errores como respuestas válidas.

---

# 9. Failure policy

Si LLM no responde:
- timeout;
- API error;
- invalid schema;
- rate limit;

el sistema debe:

1. registrar error;
2. usar análisis determinista;
3. marcar que no hubo revisión IA;
4. seguir mostrando resultado al usuario.

No bloquear ScoreLint.

---

# 10. Demo provider

Debe continuar existiendo un modo determinista sin API key.

Nunca presentarlo como respuesta real de IA.

La UI/documentación debe identificarlo.

---

# 11. Embeddings

Usar embeddings para:
- semantic instrument name matching.

No usarlos para:
- dificultad musical completa;
- pasajes críticos;
- búsquedas que ya resuelve el dominio.

Almacenar catálogo precomputado/cacheado cuando sea viable.

---

# 12. Observability

Loggear sin datos sensibles:

- operation type;
- model/provider;
- duration;
- cache hit/miss;
- success/fallback;
- prompt version;
- token usage si está disponible;
- validation failure.

No loggear:
- API keys;
- secretos;
- información innecesariamente sensible.

---

# 13. Tests

Crear fakes/mocks.

Tests mínimos:
- valid structured response;
- invalid schema;
- timeout;
- fallback;
- cache hit;
- prompt version invalidation;
- UNKNOWN instrument;
- out-of-range difficulty rejected.
