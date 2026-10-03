> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Plan de evolución IA — MaestroAI / ScoreLint

## Objetivo

Evolucionar el MaestroAI ya construido desde un sistema principalmente heurístico hacia una arquitectura híbrida, explicable y evaluable:

```text
MusicXML
   ↓
Modelo musical
   ↓
Feature extraction
   ↓
Heurísticas y reglas
   ↓
Selección de candidatos
   ↓
LLM / semantic review cuando aporte valor
   ↓
Hybrid Assessment
   ↓
Feedback humano
   ↓
Evaluación
```

## Problemas actuales que motivan la evolución

### Instrumentos
Los nombres de instrumento procedentes de MusicXML no son homogéneos.

Ejemplos:
- Clarinet
- Bb Clarinet
- Clarinet in B-flat
- Clarinete
- Clarinete en Sib
- Clarinetto
- Horn
- French Horn
- Trompa
- Corno

El sistema necesita comprender equivalencias sin perder variantes importantes.

### Dificultad
El score heurístico puede sobreestimar pasajes musicalmente sencillos.

La suma independiente de factores puede no representar interacciones reales.

### Pasajes críticos
Un pasaje difícil y un pasaje crítico no son lo mismo.

El fragmento más difícil de una obra fácil no debe convertirse automáticamente en crítico.

### Audio
La reproducción actual puede sonar demasiado General MIDI / sintética.

### Evaluación
Los ajustes no deben hacerse únicamente "a ojo". Se necesita un dataset de referencia etiquetado por músicos.

---

# Objetivos funcionales

## A. Instrument resolution

Crear una identidad canónica musical independiente del idioma.

Debe preservar:

- section;
- family;
- instrument;
- variant;
- transposition;
- part number.

Debe devolver:
- resultado;
- confianza;
- fuente de resolución;
- necesidad de revisión humana.

## B. Difficulty

Mantener una medida continua de dificultad.

La dificultad debe considerar:
- instrumento;
- nivel objetivo;
- ritmo;
- tempo;
- note/event rate;
- tesitura;
- intervalos;
- articulación;
- resistencia;
- dinámica;
- interacción entre factores.

## C. Criticality

Crear una decisión distinta de Difficulty.

Un pasaje crítico requiere suficiente evidencia.

Debe permitirse:
- cero pasajes críticos;
- pasajes "attention";
- pasajes "difficult";
- pasajes "critical".

## D. Rehearsal Priority

No confundir:
- difficulty;
- criticality;
- rehearsal priority.

La prioridad de ensayo puede incorporar:
- dificultad;
- criticidad;
- BandFit;
- disponibilidad de músicos;
- relevancia;
- duración disponible.

## E. LLM reviewer

El LLM debe evaluar contexto musical estructurado.

No debe sustituir a:
- MusicXML parser;
- feature extraction;
- validaciones;
- reglas deterministas.

## F. Feedback experto

Permitir recoger valoraciones humanas para:
- calibrar;
- medir;
- comparar;
- detectar sesgos del algoritmo.

---

# Arquitectura objetivo

```text
                    MusicXML
                       │
                       ▼
                 Score Parser
                       │
                       ▼
              Canonical Music Model
                       │
          ┌────────────┴────────────┐
          ▼                         ▼
 Instrument Resolver         Feature Extractors
          │                         │
          └────────────┬────────────┘
                       ▼
              Heuristic Analysis
                       │
                       ▼
              Candidate Selection
                       │
                       ▼
              LLM Musical Reviewer
                       │
                       ▼
               Hybrid Assessment
          ┌────────────┼──────────────┐
          ▼            ▼              ▼
     Difficulty    Criticality   Rehearsal Priority
          │            │              │
          └────────────┴──────────────┘
                       ▼
                 MaestroAI UX
                       │
                       ▼
                 Expert Feedback
```

---

# Priorización

## MVP / obligatorio

- InstrumentResolver canónico.
- Alias multilingüe.
- Metadata MusicXML.
- Separar dificultad/criticality.
- Cero críticos permitido.
- Thresholds configurables.
- Note rate.
- Perfiles al menos por familia:
  - woodwind;
  - brass;
  - percussion.
- Ensemble/player level.
- Tests de regresión.
- Dataset inicial de evaluación.

## Recomendable

- embeddings;
- fallback LLM;
- LLM DifficultyReviewer;
- HybridDifficulty;
- confidence;
- abstention;
- expert feedback;
- prompt/model/features versioning;
- cache.

## Opcional

- aprendizaje de aliases confirmados;
- logistic/ordinal regression como baseline;
- disagreement analyzer;
- expert/debug view;
- sampled audio más avanzado.

## Futuro

- model training con dataset grande;
- audio de interpretación;
- OCR/PDF;
- automatic orchestration;
- adaptive rehearsal learning.

---

# Principios de calidad

## Un resultado debe ser trazable

Ejemplo conceptual:

```json
{
  "finalDifficulty": 5.8,
  "heuristicDifficulty": 6.4,
  "llmDifficulty": 5.4,
  "critical": false,
  "rehearsalPriority": 4.9,
  "confidence": 0.88,
  "algorithmVersion": "difficulty-2.0",
  "featuresVersion": "features-2.0",
  "promptVersion": "difficulty-review-v1",
  "model": "provider/model",
  "evidence": {}
}
```

No es obligatorio conservar exactamente este contrato.

## No forzar certeza

Si no hay evidencia suficiente:
- UNKNOWN;
- needsHumanReview;
- low confidence.

## No forzar críticos

Un análisis correcto puede devolver:
- 0 critical;
- varios attention/difficult.

---

# Resultado esperado para el TFM

Poder comparar con datos reales:

```text
Heuristic
vs
LLM
vs
Hybrid
vs
Expert
```

y responder con métricas a preguntas como:

- ¿reduce el modelo híbrido los falsos positivos?
- ¿qué método correlaciona mejor con músicos?
- ¿el sistema identifica correctamente instrumentos heterogéneos?
- ¿la confianza está bien calibrada?
