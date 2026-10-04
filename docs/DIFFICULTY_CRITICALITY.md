> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Difficulty, Criticality and Rehearsal Priority

## 1. Principio

No son el mismo concepto:

```text
Difficulty != Criticality != RehearsalPriority
```

### Difficulty
¿Qué dificultad técnica representa el fragmento para un intérprete objetivo?

### Criticality
¿Existe suficiente evidencia para considerar el fragmento excepcionalmente problemático?

### Rehearsal Priority
¿Cuánto tiempo/prioridad merece en el ensayo dadas las circunstancias?

### Ensayo de conjunto y pasajes comunes

Decisión de la autora (2026-10-04): los ensayos son de conjunto. La prioridad no se calcula
por instrumento aislado, sino por **pasaje común**:

- **Coincidencia en compases**: los mismos compases son difíciles para varias partes a la vez.
- **Material compartido**: partes que tocan lo mismo (unísono u octavas en altura real, o el
  mismo ritmo), aunque sean de familias distintas. La altura escrita se convierte a real con la
  transposición declarada en el MusicXML.

Organización del ensayo:

- **Bloques seccionales**, uno por sección (madera, metal, percusión, cuerda, sección rítmica,
  teclas) y pasaje común, con las partes implicadas, los compases y los motivos.
- **Un tutti final para juntar** los pasajes que implican a varias secciones o que comparten
  material entre secciones.
- La suma de bloques no supera el tiempo disponible; si no caben todos, se descartan los de
  menor prioridad indicándolo. Sin pasajes, el plan es un único tutti.

Implementación (paso 15): `backend/analyzers/rehearsal_passages.py` agrupa los pasajes críticos
desde el de mayor prioridad; absorbe siempre los contenidos en él y solo crece mientras el pasaje
no supere 16 compases. El material compartido compara cada parte crítica con todas las demás en
altura real. `backend/analyzers/rehearsal_plan.py` reserva el 25 % (mínimo 5 min) para el tutti y
reparte el resto en proporción a la prioridad con un mínimo de 5 min por bloque. Limitación: los
pasajes muy largos vienen del detector de criticidad actual (paso 14 pendiente). El planificador
anterior queda congelado en `evaluation/legacy_rehearsal.py` para el baseline.

---

# 2. Difficulty

Mantener score continuo, idealmente 0-10.

Debe estar contextualizado por:

- instrumento;
- variant;
- transposition cuando sea relevante;
- target level.

Niveles iniciales:

```text
BEGINNER
ELEMENTARY
INTERMEDIATE
ADVANCED
PROFESSIONAL
```

## Features

Revisar/extraer:

- tempo;
- meter;
- note/event rate;
- shortest duration;
- rhythmic entropy/complexity si ya existe;
- syncopation;
- tuplets;
- range;
- comfortable-range load;
- high/low register load;
- interval size/distribution;
- large leap frequency;
- articulation changes;
- dynamics;
- continuous playing duration;
- rest ratio;
- density;
- instrument changes para percussion.

No es obligatorio implementar todas si el proyecto actual no las soporta.

---

# 3. Evitar doble conteo Rhythm + Tempo

Revisar si:

```text
RhythmDifficulty + TempoDifficulty
```

penaliza dos veces el mismo fenómeno.

Añadir una feature integrada como:

```text
noteRate / eventRate = note attacks per second
```

o equivalente.

Ejemplo:

- semicorcheas a 60 bpm != semicorcheas a 160 bpm.

El modelo debe reflejarlo.

---

# 4. Interaction effects

No tratar todos los factores como independientes.

Ejemplos:

```text
high register
×
ff
×
long continuous duration
×
few rests
```

puede ser especialmente exigente para brass.

```text
fast note rate
×
large leaps
×
register crossing
```

puede elevar dificultad en woodwind.

Estas interacciones pueden evaluarse:
- por reglas;
- por perfiles;
- por LLM reviewer.

---

# 5. Instrument Difficulty Profiles

MVP:

```text
WOODWIND
BRASS
PERCUSSION
```

Permitir overrides específicos después.

### Woodwind
Priorizar según datos disponibles:
- note rate;
- register changes;
- range;
- interval patterns;
- articulation;
- endurance.

### Brass
Priorizar:
- register;
- duration;
- rest ratio;
- dynamics;
- endurance;
- interval changes.

### Percussion
Priorizar:
- rhythm;
- coordination;
- instrument changes;
- density;
- simultaneous requirements cuando aplique.

Los pesos deben ser configurables.

---

# 6. LLM Difficulty Reviewer

El LLM recibe FEATURES estructuradas.

Durante experimentación independiente NO recibe el score heurístico.

Debe devolver structured output:

```json
{
  "difficulty": 5.8,
  "confidence": 0.87,
  "mainFactors": [
    {"factor": "note_rate", "impact": "medium"},
    {"factor": "range", "impact": "low"}
  ],
  "reason": "..."
}
```

No usar `critical=true/false` como sustituto del detector determinista.

Puede emitir una valoración separada de rehearsal priority.

---

# 7. Hybrid Difficulty

Mantener:

```text
heuristicDifficulty
llmDifficulty
finalDifficulty
```

No fijar definitivamente pesos tipo 40/60 sin evaluación.

La estrategia híbrida debe ser configurable.

Opciones a experimentar:

- weighted average;
- confidence-weighted;
- LLM only for ambiguous/candidate cases;
- heuristic base + bounded LLM correction.

---

# 8. CriticalPassageDetector

Debe ser responsabilidad separada.

Un pasaje NO es crítico solo por estar en el Top N.

Debe poder devolver cero críticos.

## Señales mínimas

### A. Absolute threshold
Ejemplo inicial:

```text
difficulty >= 6.5
```

Configurable.

### B. Relative percentile
Ejemplo:

```text
percentile >= 85
```

Dentro de la misma parte/instrumento.

Configurable.

### C. Local prominence
El pasaje debe destacar respecto a su contexto.

Ejemplo relevante:

```text
4.2
4.5
7.9
4.7
4.3
```

Ejemplo no crítico:

```text
4.8
5.0
5.2
5.3
5.1
```

### D. Persistence / minimum duration
Evitar marcar como crítico un pico de duración irrelevante.

Usar:
- tiempo;
- beats;
- o ventana existente correctamente normalizada.

### E. Evidence
Requerir:
- varios factores relevantes;
- o una regla crítica específica.

---

# 9. Windowing

Revisar si el análisis actual opera únicamente por número fijo de compases.

Dos compases pueden representar duraciones muy distintas.

Si es viable:
- calcular internamente con beats o segundos;
- presentar externamente medidas/compases.

No reescribir todo el pipeline si el coste supera el beneficio del TFM.

---

# 10. Estados UX

Evitar que todo sea "critical".

Usar conceptos:

```text
NORMAL
ATTENTION
DIFFICULT
CRITICAL
```

Y separar:

```text
"Pasajes críticos"
```

de:

```text
"Pasajes que pueden requerir atención"
```

---

# 11. Disagreement Analysis

Si:

```text
abs(heuristic - llm) >= configurable threshold
```

marcar:

```text
HIGH_DISAGREEMENT
```

Mostrar internamente:
- factores que elevan heurística;
- factores mencionados por LLM;
- expert feedback si existe.

Esto sirve para depurar el algoritmo.

---

# 12. Tests

Añadir casos controlados:

- easy scale at slow tempo;
- easy scale at fast tempo;
- high register isolated note;
- sustained high register;
- repeated notes;
- stepwise sixteenths;
- wide leaps;
- long no-rest brass passage;
- complex syncopation;
- easy work with NO critical passages.

Regression test obligatorio:
> una obra sencilla puede devolver 0 críticos.

---

# 13. Configuración

Thresholds y pesos fuera de código rígido cuando sea razonable:

```text
difficulty thresholds
critical threshold
percentile
prominence
minimum duration
disagreement threshold
family profile weights
```

Documentar defaults.
