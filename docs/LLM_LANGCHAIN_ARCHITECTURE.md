> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# LLM / LangChain Architecture

## Implementado: puerto IA y demo (paso 20, decisiones del 2026-10-07)

- **Puerto** `backend/application/ai.py`: `ExplanationProvider` con `ProviderInfo` (`demo` o `llm`,
  proveedor y modelo) y `ProviderFailure` (timeout, rate_limit, error). El dominio no conoce ningún
  proveedor concreto. Proveedor real elegido para el paso 21: **Google Gemini** (nivel gratuito).
- **Primer uso: explicar la dificultad de una obra** (`backend/application/difficulty_explanation.py`,
  `GET /works/{id}/explanation`, pestaña Dificultad). Evidencias `difficulty-evidence-v1` construidas
  solo con el análisis guardado (grado y rúbrica, familias, 8 instrumentos más difíciles con sus
  dimensiones y hallazgos, 8 pasajes críticos con identificador `P1…`, tempo y duración). Salida
  validada con Pydantic: resumen, 1–4 factores con dimensión de un enum, instrumentos y pasajes citados
  —que deben existir en las evidencias— y consejo de estudio. Prompt `difficulty-explanation-v1`.
- **Fallback**: ante timeout, límite, error o respuesta inválida se registra el motivo (sin datos
  personales) y responde la demo, indicando por qué en la interfaz.
- **Demo** `backend/infrastructure/ai/demo_provider.py`: reglas deterministas sobre las mismas
  evidencias; la interfaz la identifica siempre como «Modo demo · … sin IA».
- **Segundo uso: «¿Por qué este plan?»** en cada ensayo guardado (`backend/application/rehearsal_explanation.py`,
  `GET /rehearsals/{id}/explanation`). Evidencias `rehearsal-evidence-v1`: fecha, duración, fase y
  concierto (días que faltan), bloques `B1…` con su tipo, obra, partes, compases, objetivo y los pasajes
  críticos del análisis que tocan, grado de cada obra y lo que la última revisión dejó pendiente o
  mejorable. Las notas de la directora viajan como datos, nunca como instrucciones. Salida: resumen,
  1–6 motivos que citan bloques existentes y un consejo para dirigirlo. Prompt `rehearsal-explanation-v1`.
- Lo común (pedir, validar, respaldo y trazabilidad) está en `backend/application/explanations.py`.
- **Adaptador Gemini con LangChain (paso 21)** `backend/infrastructure/ai/gemini_provider.py`:
  `ChatGoogleGenerativeAI` (`langchain-google-genai` 2.1, `langchain-core` 0.3) con `with_structured_output`
  y los mismos esquemas Pydantic que valida el servidor, temperatura 0, límite de 60 s (`GEMINI_TIMEOUT_SECONDS`) y un reintento.
  Los fallos se clasifican en timeout, rate_limit o error y responde la demo. Prompts versionados en
  `backend/infrastructure/ai/prompts.py`: reglas como mensaje de sistema y evidencias como datos en el
  mensaje humano. Se activa con `GEMINI_API_KEY` (modelo en `GEMINI_MODEL`, por defecto
  `gemini-3.8-flash`); LangChain se importa solo al usarlo (~70 MB que un servidor sin clave no gasta).
  Las pruebas usan un modelo simulado: nunca llaman a Google.
- **Caché (paso 23)**: con el cupo gratuito de `gemini-3.8-flash` (5 peticiones por minuto y 20 al día en la
  cuenta del proyecto), cada explicación válida de la IA se guarda en `ai_explanations` (migración 0011) con
  la clave sha256 de las evidencias exactas, el proveedor, el modelo y la versión del prompt; repetirla no
  gasta cupo y la interfaz lo dice. Cambiar cualquiera de esas piezas (reanalizar, otro modelo, otro prompt)
  vuelve a preguntar. Nunca se guardan errores, respaldos ni el demo; una entrada que ya no valida se pide de
  nuevo. Las valoraciones del método B se guardan con lo enviado en `evaluation_llm_reviews` (paso 22).
- **Primera respuesta real (2026-10-13, `gemini-3.8-flash`, *Persis Overture*)**: fiel a las evidencias
  (grado, instrumentos y los pasajes de cada factor coinciden con sus hallazgos), pero escribía nombres de
  parte en inglés («Concert Snare Drum») e identificadores internos («como P3, P4 y P5»). **Prompts v2**
  (`difficulty-explanation-v2`, `rehearsal-explanation-v2`): nombres en castellano en el texto e
  identificadores solo en las citas. Además, una salvaguarda determinista sustituye en el texto cualquier
  `P…`/`B…` por instrumento y compases o por el bloque, y los nombres MusicXML por su etiqueta.

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
