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

Decisiones de la autora (2026-10-04): los ensayos son de conjunto y un **pasaje común** es el que
varias partes tocan igual en **estructura**, cada una en su tonalidad: por ejemplo, bombardino,
trombón y saxo tenor con la misma línea. Cuenta como «lo mismo»:

- **Misma línea**: mismo ritmo y mismos intervalos melódicos, en cualquier tonalidad u octava
  (altura real con la transposición del MusicXML); tolera pequeñas diferencias.
- **Mismo ritmo** con notas distintas.

Organización de cada pasaje (los pasajes se ordenan por prioridad):

1. **Líneas comunes**: un bloque por grupo de partes que tocan lo mismo, aunque mezclen familias;
   incluye a todos los que tocan la línea aunque solo una parte se haya marcado como difícil.
2. **Subsecciones** con las partes difíciles restantes: flautas, dobles cañas, clarinetes,
   saxofones, metales agudos (trompetas, cornetas, fliscornos, trompas), **graves** (trombones,
   bombardino, tuba, más fagot, clarinete bajo y saxo barítono), percusión, cuerda y rítmica.
3. **Un tutti final** que junta los pasajes con líneas comunes o con varias subsecciones.

Cada bloque abarca solo los compases en que tocan sus instrumentos: se recortan los silencios
iniciales y finales, y un silencio de una frase completa (8 compases) lo divide en dos bloques.

La suma de bloques no supera el tiempo disponible; si no caben todos, se descartan los de menor
prioridad indicándolo. Sin pasajes, el plan es un único tutti.

Implementación: `backend/analyzers/rehearsal_passages.py` agrupa los pasajes críticos solapados
(absorbe siempre los contenidos y limita el crecimiento a 16 compases) y `find_common_lines`
compara compás a compás todas las partes: comparten material si coinciden en al menos el 75 % de
los compases en que tocan; es «misma línea» si además el 85 % de los intervalos de cada compás
coinciden (las notas sostenidas solo cuentan como ritmo). La subsección sale de
`rehearsal_group` del catálogo. `backend/analyzers/rehearsal_plan.py` reserva el 25 % (mínimo
5 min) para el tutti y reparte el resto en proporción a la prioridad (mínimo 5 min por bloque).
La vista incluye un calendario interactivo que abre la partitura de cada bloque con sus
instrumentos. Limitación: los pasajes muy largos vienen del detector de criticidad actual
(paso 14 pendiente). El planificador anterior queda congelado en `evaluation/legacy_rehearsal.py`.

### Agenda propuesta para un ensayo de varias obras (2026-10-05)

A petición de la autora, la aplicación propone la agenda de un ensayo guardado
(`backend/analyzers/rehearsal_proposal.py`, `POST /rehearsals/proposal`): un **calentamiento** de
toda la banda con el 15 % del tiempo (mínimo 5 min); el resto se reparte entre las obras **en
proporción a su grado**, con un mínimo de 10 min por obra y en el orden elegido por el director;
las obras que no caben se indican en lugar de comprimirse. Cada obra recibe el plan de ensayo de
conjunto anterior con su tiempo, y **cada bloque indica su obra y sus compases**. Las obras se
vuelven a leer desde su MusicXML guardado con los instrumentos confirmados en su último análisis.
La propuesta no se guarda: el director la revisa y ajusta en el editor. Estos repartos son reglas
iniciales, no valores calibrados; el asistente IA (F2b) podrá ajustarlos a petición.

### Serie de ensayos de un concierto (2026-10-06)

Decisiones de la autora (`backend/analyzers/concert_plan.py`, `POST /concerts/{id}/plan`): las
fechas salen del **patrón semanal** del concierto (días, hora y duración desde una fecha de inicio
hasta la víspera). La serie avanza **por fases**: el primer tercio, lectura y pasajes (25 % de
tutti); los intermedios, pasajes e integración (40 %); el penúltimo, integración (60 %), y el último
es el **ensayo general**: calentamiento y **pasada completa** de cada obra en orden de concierto,
con tiempo proporcional a su duración estimada. La **revisión del director** rectifica el plan: un
pasaje pendiente pesa ×2, uno mejorable ×1,5 y uno resuelto ×0,25, y la obra con pendientes recibe
más tiempo (×1,5; mejorable ×1,25; todo resuelto ×0,75). Una obra que no cabe en un ensayo va la
primera en el siguiente. Solo se replanifican los ensayos futuros, sin revisar y no fijados; la
propuesta no se guarda hasta que el director la revisa (`PUT /concerts/{id}/rehearsals`). Son
reglas iniciales para calibrar con el uso.

---

# 2. Difficulty

Mantener score continuo, idealmente 0-10.

## Escala visible (paso 13, decisiones de la autora, 2026-10-05)

`backend/domain/difficulty_scale.py`. El **índice técnico** 0–10 es 2 × la puntuación anterior
0–5 (transformación explícita que conserva el orden entre partes; las dimensiones se escalan
igual). El **grado** 1–6 sale de seis tramos iguales del índice, hasta que la evaluación con
músicos los calibre:

| Grado | Índice | Equivale a | Rúbrica (alineada con las editoriales, 2026-10-13) |
|---|---|---|---|
| 1 Muy fácil | 0 – 1,66 | Grade 1 | Primer año de instrumento: negras, blancas y redondas en compases simples, con tesitura reducida |
| 2 Fácil | 1,67 – 3,33 | Grade 2 | Unos dos años de práctica: corcheas, puntillos, síncopas y tresillos sencillos, primeros compases compuestos |
| 3 Intermedio | 3,34 – 4,99 | Grade 3 | Tres o cuatro años de práctica: síncopas frecuentes, cambios de compás y tesitura media o amplia |
| 4 Intermedio avanzado | 5 – 6,66 | Grade 4 | Cuatro a seis años de práctica: ritmos exigentes, tonalidades y compases menos habituales, pasajes técnicos |
| 5 Avanzado | 6,67 – 8,33 | Grade 5 | Siete a nueve años de práctica: ritmos muy exigentes, compases cambiantes o asimétricos, toda la tesitura y escritura virtuosística |
| 6 Profesional | 8,34 – 10 | Grade 6 | Nivel profesional o superior: extremadamente difícil en todos los aspectos |

Decisión de la autora (2026-10-13): los nombres y descripciones se alinean con la escala **Grade 1–6** que
usan la mayoría de editoriales de música para banda, para poder comparar con los grados publicados. No hay
una escala única entre editoriales (J.W. Pepper, por ejemplo, usa letras de Beginning a Advanced), así que
la equivalencia es **orientativa**; el cálculo del grado no cambia y los tramos se calibrarán con la
evaluación. Antes la rúbrica describía la agrupación (escuela de música, banda juvenil, banda amateur…).

No es una certificación oficial. El grado de familia es el del percentil 80
de sus instrumentos y el de la obra, el máximo de las familias. El resultado declara
`scale = {version: 2, grades: 6, technical_index_max: 10}`; un análisis guardado sin `scale` se
puntuó 1–5 y la interfaz lo muestra como «escala anterior». El baseline se captura con
`scale="legacy"`. En las obras locales la mediana de las partes es 5,2 (grado 4).

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

Implementación (paso 14): `backend/analyzers/criticality.py`, configurable con `CriticalityPolicy`.
Puntuación local por compás = pesos de las reglas que lo marcan (SL005 no suma: es evidencia de
persistencia). Un compás es candidato con puntuación ≥ 5 (absoluto) o si está en el percentil 85 de
su parte y supera en 2 la mediana de los 4 compases a cada lado (relativo y destacado). Los
candidatos consecutivos forman un núcleo, que exige al menos 4 tiempos y 2 reglas distintas. El
núcleo se amplía a las frases completas que toca (`phrases.py`), así que un pasaje nunca corta una
frase. Señal de velocidad (decisión de la autora, 2026-10-04): un compás tocado a
≥ 8 notas por segundo al tempo escrito (semicorcheas desde negra = 120) es candidato por sí solo, y un
núcleo formado solo por esos compases es crítico con un único tipo de aviso si dura ≥ 4 tiempos.
Los umbrales generales se mantienen hasta la evaluación con músicos; las frases largas que amplían
los pasajes (hasta 54 c. en Persis) son aceptadas por la autora. Puede haber cero críticos. Los valores son iniciales y deben calibrarse con la evaluación.
El detector anterior queda como `critical_detector="legacy"` solo para el baseline.

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

## Frases melódicas (criterios de la autora, 2026-10-04)

Los pasajes críticos y los bloques de ensayo **nunca cortan una frase melódica**; una frase
larga se mantiene entera. `backend/analyzers/phrases.py` detecta los límites sumando pistas, sin
que ninguna decida sola:

| Criterio de la autora | Implementación | Peso |
|---|---|---|
| Pausas relevantes | Silencio ≥ 1,5 × la nota típica de la frase, ≥ corchea y destacado frente a los silencios vecinos (un silencio breve o recurrente es del motivo o del acompañamiento) | 2 |
| Alargamiento al final | Nota ≥ 2 × la típica anterior; sola no corta, con pausa o reinicio sí | 1 (+1 con pausa) |
| Indicaciones escritas | Respiración, cesura y calderón, leídos del MusicXML | 2 |
| Reinicio de un motivo | Reaparece el patrón inicial de la frase (ritmo e intervalos) | 1 |
| Contexto métrico | La frase incluye el compás de su primera nota: la anacrusa va con su frase | — |
| Relación entre partes | Los bloques de ensayo se amplían a las frases de todos sus instrumentos | — |
| Cadencia o reposo armónico | `harmony.py`: todas las partes en sonido real; tonalidad por zonas (±4 c., perfiles de Krumhansl, también su relativa). Auténtica: V (bajo en dominante y sensible) → I (bajo en tónica) en tiempo fuerte; semicadencia: llegada a V sostenida ≥ 2 tiempos que no resuelve. La melodía en la tónica no basta | 1 a la nota que suena en la llegada |
| Cambio de patrón | No corta: puede ser solo una subdivisión | — |

Hay límite cuando la suma llega a 2: la cadencia cierra con nota alargada o con pausa, y sola no
corta las partes que siguen moviéndose (decisiones de la autora, 2026-10-04). Sin transposiciones
declaradas (partes «Voice» de un PDF) la armonía no es fiable y no se detectan cadencias; de los
acordes dentro de un pentagrama la armonía usa todavía solo la nota superior. Los fragmentos separados por límites débiles se unen en
frases de **4 u 8 compases** (decisión de la autora): la frase se cierra al llegar a 4 o a 8, y de
5 a 7 solo se une el siguiente fragmento si completa exactamente 8. Un silencio de un compás entero
o una marca escrita es un límite fuerte que nunca se une. El parser conserva la posición de cada
nota en el compás, la duración del compás y las marcas escritas.

## Tiempos y ataques (paso 10, decisiones de la autora, 2026-10-05)

El parser conserva voz, ligadura, nota de adorno y todas las notas de cada acorde
(`ScoreNote.voice`, `tie`, `is_grace`, `chord_pitches`; `pitch` es la nota superior).
`backend/domain/timing.py` fija qué es un ataque para todos los consumidores:

- Un acorde es un solo ataque; la continuación o el final de una ligadura no es ataque.
- Una nota de adorno es un ataque más, aunque no ocupe tiempo.
- Cada voz de un pentagrama es un músico: un compás es tan denso como su voz más activa y su
  duración es la escrita, no la suma de las voces.
- Los intervalos se miden a lo largo de cada voz (nota superior de los acordes), nunca entre voces;
  el rango incluye todas las notas de los acordes.

Lo usan SL003, SL004, el rango, la dificultad por instrumento y la señal de velocidad de la
criticidad. El baseline sintético no cambia (no tiene acordes, voces ni ligaduras). En las obras
locales, las partes divisi escritas como acordes suben de grado y las notas ligadas dejan de contar
como densidad. El tempo local y los descansos quedan para el paso 11.

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
