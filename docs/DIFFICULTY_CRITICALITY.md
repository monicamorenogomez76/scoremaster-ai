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

### difficulty-v2: sin sobrevalorar (revisión de la autora, 2026-10-14)

Con obras reales, ScoreLint daba uno o dos grados de más: *Persis* (Hosay), 6 frente al Grade 4 de su
editorial, y la autora veía sobrevaloradas las demás obras probadas. Las causas eran de cálculo, no de las
obras, y se corrigen solo en la escala actual (la escala heredada del baseline no cambia):

| Antes | difficulty-v2 | Motivo |
|---|---|---|
| Densidad en ataques por pulso escrito y un único tempo, el más rápido de la obra | **Notas por segundo con el tempo de cada compás**; desaparece la dimensión de tempo aparte | «Los pasajes con muchas notas a velocidad lenta son fáciles o menos difíciles» (la autora). La velocidad ya no se cuenta dos veces |
| El compás más denso de la parte | **Percentil 75** de los compases, frente a una referencia 2,5 veces la anterior | Un compás rápido no hace difícil una parte entera; los picos son tarea de los pasajes críticos |
| La resistencia llegaba al máximo con 7–8 compases sin descanso | Referencia tres veces mayor (unos 24 compases) | Tocar 16 compases seguidos es lo normal en banda, también en grado 2 |
| Corneta y fliscorno sin perfil (caían en uno genérico) | Perfil de trompeta | Metal en Si♭ con la tesitura y la técnica de la trompeta |
| Grado de la obra = máximo de todas las familias | **Máximo de viento madera, viento metal y cuerda**; percusión, sección rítmica, teclado y partes sin identificar conservan su grado, mostrado aparte con «no cuenta para el grado de la obra» | Una caja en corcheas convertía *Persis* en un 6. Si una obra es solo percusión, la percusión sigue dando su grado |

El resultado declara `algorithm_version: difficulty-v2`, que también guarda la tabla `analyses` y la
predicción de cada pasaje de campaña (`versions.difficulty`). Al arrancar, el servidor analiza de nuevo las
obras cuyo último análisis es de una versión anterior, con su misma banda, minutos e instrumentos
confirmados; el análisis anterior queda como historial.

| Obra | Antes | difficulty-v2 | Grado publicado de este archivo |
|---|---|---|---|
| Persis | 6 | 4 | Grade 4 (Curnow Music): **única referencia válida** |
| March of the Toys (arr. Cao Ziyi) | 4 | 4 | Ninguno (ver abajo) |
| In a Persian Market (reducción para conjunto) | 4 | 3 | Ninguno (ver abajo) |
| Oregon Trail II (Eric Speier) | 5 | 3 | Ninguno (ver abajo) |
| Coral para principiantes (demo) | 2 | 1 | Escrito para principiantes |

**Referencias descartadas (2026-10-14).** Los grados encontrados en internet para tres de estas obras son
de *otras ediciones*, y no sirven para calibrar, igual que *Spania* y *Above and Beyond* (partes «Voice»
sin instrumento):

- el Grade 2 de «Oregon Trail» es de *The Oregon Trail* de Michael Story (Alfred, Belwin Young Band), otra
  obra;
- el Grade 2 / ≈3 de la marcha del *Cascanueces* es de los arreglos de Michael Story (Alfred) y Paul Hanna;
  el de Cao Ziyi, para banda completa con requinto y cuatro trompas, no publica grado;
- el Grade 4 de *In a Persian Market* es de los arreglos para banda completa de Takahashi y de
  Saurer/Tailor (Marc Reift); el archivo es una reducción para conjunto pequeño, todo doblado y con un único
  tempo («maestoso» 90).

Antes de descartarlas se midió si alguna dimensión nueva acercaba esos archivos a esos grados. Ninguna lo
hacía: con los datos del archivo, *Oregon Trail II* es más exigente que la reducción de *In a Persian
Market* en notas por segundo de los pasajes rápidos (14,9 frente a 12,0), notas fuera de la tonalidad (47 %,
con modulación a cinco sostenidos, frente a 23 %), síncopas (10 % frente a 0 %) y compases sin otra parte que
la doble (28 % frente a 0 %). Ajustar ScoreLint a esos grados sería ajustarlo a otras partituras.

Queda pendiente: **los tramos índice → grado siguen siendo seis tramos iguales provisionales**, y no se
tocan con una sola referencia válida. Calibrarlos exige obras cuyo archivo sea la edición que publica el
grado (o con el grado de un experto sobre ese archivo); hasta entonces, la evaluación con músicos y los
grados publicados que registre la directora (con su fuente) son los que miden cuánto se desvía ScoreLint.
Tonalidad, cromatismo, ritmo (tresillos, síncopas) y exposición de las partes son candidatos razonables a
nuevas dimensiones, pero se añadirán solo cuando haya referencias con las que comprobar que mejoran.

### difficulty-v3: el grado sigue las guías de las editoriales (decisión de la autora, 2026-10-25)

Tras difficulty-v2 faltaba una referencia experta: solo *Persis* tenía un grado publicado que correspondía a
su archivo. La autora aportó las guías con las que las editoriales gradúan obras de banda, y ScoreLint pasa a
seguirlas. **Cada criterio da un grado mínimo y la obra tiene el grado de su criterio más exigente**, en lugar
de promediar dimensiones y repartir el índice en tramos iguales.

**Fuentes y jerarquía** (elegida por la autora):

| Fuente | Uso |
|---|---|
| *American Band College Music Grading Chart* (revisada en 2000), grados 1–5 | **Base**: compás, armadura, tempo, figuras, ritmo, dinámicas, articulación, adornos, duración y tesituras escritas por instrumento |
| *FJH Music Company, Series Guidelines* (revisadas en 2004), grados 0,5–6 | Afina los grados bajos (5/4 y 6/4 limitados en grado 2) y confirma la escritura (el clarinete de grado 1 no pasa del cambio de registro) |
| UIL Texas, criterios de lectura a primera vista (2022) | Solo confirma la progresión de armaduras, compases y ritmos: sus niveles son de lectura a primera vista y la propia UIL no los equipara a grados |
| UIL Texas, *Prescribed Music List* | Catálogo de obras con un grado asignado por un comité: fuente de grados publicados para comparar con ScoreLint |

Los documentos son de sus editores: en el repositorio solo están sus criterios (`backend/domain/grade_rubric.py`).

**Criterios** (`backend/analyzers/rubric_grade.py`):

- De la obra: armadura de concierto (G1 hasta 3 ♭ y Do; G2 4 ♭; G3 5 ♭; G4 de 1 ♯ a 6 ♭; G5 cualquiera),
  compás (simples G1; 6/8 G2, y 5/4 y 6/4 según FJH; 9/8 y 12/8 G3; 3/8, 5/8 y 7/8 G4; otros G5), cambios de
  tonalidad y de compás (0 → G1, 1–2 → G2, 3–5 → G3, 6 o más → G4), tempo marcado (G1 72–120, G2 hasta 132,
  G3 56–144, G4 44–168, G5 hasta 208), duración (G1 hasta 3 min, G2 5, G3 7, G4 más) y dinámicas (p y f G1;
  mp y mf G2; pp, ff, sfz y fp G3; ppp y fff G4).
- De cada parte: tesitura por instrumento y grado, figura más breve (corcheas G1, semicorcheas G2, fusas G3),
  tresillos (G2), síncopas (de corchea en compás simple G2, en compás compuesto G3, de semicorchea G5),
  articulaciones (staccato y acento G1, legato G2, tenuto G3, otras G4), adornos (trino G2; grupeto y
  mordente G4) y notas de adorno (sueltas G2, de 2 o 3 G3).
- **Uso limitado**: un rasgo de una parte cuenta si aparece en al menos el 5 % de sus compases con notas y en
  más de un compás; una dinámica, si aparece en más de un compás. Las notas de final de curso (redondas de la
  tabla) se aceptan en su grado si son como mucho el 5 % de las notas de la parte. Un salto a una nota fuera de
  la tesitura sí sube el grado, como advierte FJH.
- Como en v2, el grado de la obra sale de viento madera, viento metal y cuerda (cada familia, por el percentil
  80 de sus partes); la percusión y la sección rítmica se muestran aparte. Una obra solo de percusión conserva
  el grado de v2, porque las guías gradúan la percusión solo por sus instrumentos. Por encima de las tesituras
  del grado 5 la parte es de grado 6.
- El índice técnico y sus dimensiones (v2) se siguen calculando para los pasajes críticos y las explicaciones.
  Cada pasaje de campaña (método A) se gradúa con la misma rúbrica sobre sus compases.

**Tesituras escritas** (fagot, trombón/bombardino y tuba en clave de fa, comparadas por su sonido real;
entre paréntesis, la de final de curso). Leídas de la tabla del American Band College midiendo la posición de
las notas y revisadas con la autora el 2026-10-25:

| Instrumento | G1 | G2 | G3 | G4 | G5 |
|---|---|---|---|---|---|
| Flauta (y flautín) | Fa4–Do6 (Re6) | Re4–Fa6 | Do4–Sol6 | Do4–Si♭6 | Do4–Do7 |
| Oboe | Fa4–Si♭5 | Si♭3–Do6 | Si♭3–Do6 | Si♭3–Re6 | Si♭3–Re6 |
| Fagot | Mi2–Fa3 (Do4) | Re2–Fa4 | Si♭1–Sol4 | Si♭1–Si♭4 | Si♭1–Si♭4 |
| Clarinete (y requinto) | Sol3–Si♭4 (Mi3–Sol5) | Mi3–Do6 (Re6) | Mi3–Fa6 | Mi3–Sol6 | Mi3–Sol6 |
| Clarinete alto y bajo | Sol3–Si♭4 (Mi3–Sol5) | Mi3–Sol5 (Si5) | Mi3–Do6 | Mi3–Sol6 | Mi3–Sol6 |
| Saxofones | Mi4–Sol5 (Si5) | Do4–Re6 | Si3–Mi6 | Si♭3–Fa6 | Si♭3–Fa6 |
| Trompeta, corneta y fliscorno | Si♭3–Do5 (Mi5) | La3–Fa5 | Fa♯3–Sol5 | Fa♯3–Do6 | Fa♯3–Do6 |
| Trompa | Do4–Do5 (Fa3–Mi♭5) | Fa3–Fa5 | Fa3–Sol5 | Do3–La5 | Fa2–Do6 |
| Trombón y bombardino | Si♭2–Re4 | Fa2–Mi♭4 | Fa2–Fa4 | Mi2–La4 | Mi2–Si♭4 |
| Tuba | Si♭1–Re3 | Mi1–Re3 | Mi1–Fa3 | Mi1–Sol3 | Mi1–Si♭3 |

**Resultado con obras reales** (en local, 2026-10-25):

| Obra | difficulty-v2 | difficulty-v3 | Lo que fija el grado |
|---|---|---|---|
| Persis | 4 | **4** (Grade 4 de su editorial) | 16 cambios de compás, tempos de 48 a 132, unos 8 minutos y fusas en flautas y clarinetes |
| Coral para principiantes (demo) | 1 | 2 | mf en varios compases y la tuba hasta Sol1 |
| Marcha de la plaza (demo) | 4 | 3 | La trompa hasta Fa♯5 y el tenuto del trombón |
| Andante y danza (demo) | 3 | 4 | Negra = 160 en la danza y la tuba hasta Sol3 |
| March of the Toys (arr. Cao Ziyi) | 4 | 5 | Flautas hasta Si6 |
| Oregon Trail II | 3 | 5 | Modulación a 5 ♯ durante un cuarto de la obra |

Limitaciones: los umbrales de cambios de compás, del uso limitado y de las articulaciones «otras» son una
lectura razonable de las guías, no cifras suyas; un vals marcado a negra = 192 cuenta como tempo de grado 5
aunque se dirija a un tiempo por compás. Lo valida la evaluación con músicos.

### Grados publicados de una obra (PR 5 del plan de cierre, 2026-10-14)

En la pestaña Dificultad, la directora puede **registrar a mano** el grado que publica una editorial o un
catálogo, con su fuente y, si quiere, el enlace y la fecha de consulta. La aplicación no lo busca ni se lo
pide a un LLM, que podría inventarlo. Se guarda la etiqueta original y su valor en la escala 1–6:

| Escala publicada | Equivalencia |
|---|---|
| Grade 0,5 a 6 (la mayoría de editoriales) | El mismo número, con sus medios grados. Grade 0,5 cuenta como 1 |
| J.W. Pepper | VE (muy fácil) = 1, E = 2, ME = 3, M = 4, MA = 5, A (avanzado) = 6 |

`difficulty_scale.external_grade` hace la conversión. Varias fuentes de una obra se promedian. El informe de
la campaña (`evaluation/campaign_report.py`) compara obra a obra el grado de ScoreLint con esa media: diferencia,
MAE, sesgo y Spearman (este último, con tres obras o más). Con pocas obras es una muestra pequeña: orienta, no
valida la escala.

No es una certificación oficial. El grado de familia es el del percentil 80
de sus instrumentos y el de la obra, el máximo de viento madera, viento metal y cuerda
(difficulty-v2; antes, de todas las familias). El resultado declara
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
