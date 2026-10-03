> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Instrument Resolution Design

## Estado de implementación

**Paso 06 integrado en código (catálogo canónico):** `backend/domain/instrument_catalog.json`
contiene 46 identidades con sección, familia, variante, transposición, etiquetas y
aliases en español, inglés e italiano. `backend/domain/instrument_catalog.py` normaliza
el nombre (minúsculas, acentos, `♭`/`flat` → `b`, puntuación), separa los números de
parte (`2`, `II`, `2nd`, `1 & 2`, `1/2`) y busca el alias **exacto**: no hay coincidencia
por substring ni difusa. Lo que no está en el catálogo es `UNKNOWN`.

Decisiones musicales de la autora, para contexto de banda:

- «Clarinet»/«Clarinete» sin afinación es clarinete en Si♭ (en orquesta podría ser en La).
- «Trumpet»/«Trompeta» es en Si♭; «Horn»/«Trompa» es la trompa en Fa, otro instrumento.
- «Baritone»/«Barítono» a secas es el saxofón barítono; «Baritone Horn» es el bombardino barítono.
- «Requinto» es el clarinete en Mi♭.
- «Trombone 3» es un trombón tenor; una parte compartida «Trombone 3 & Bass Trombone»
  queda `UNKNOWN` para confirmación humana. «Cymbal» a secas también.

Con las partituras locales de prueba (no versionadas), 49 de 52 nombres se resuelven
y ninguno se clasifica incorrectamente. Todavía no lo consumen BandFit, la dificultad
ni el audio: eso corresponde al resolver determinista (paso 08).

## 1. Problema

MusicXML no garantiza una nomenclatura única de instrumentos.

La identidad musical no debe depender del texto visible de `part-name`.

## 2. Modelo canónico

Representar, cuando sea posible:

```text
section
family
instrument
variant
transposition
partNumber
```

Ejemplo:

```json
{
  "section": "woodwind",
  "family": "clarinet",
  "instrument": "clarinet",
  "variant": "soprano",
  "transposition": "bb",
  "partNumber": 1
}
```

Otro ejemplo:

```json
{
  "section": "woodwind",
  "family": "clarinet",
  "instrument": "clarinet",
  "variant": "bass",
  "transposition": "bb"
}
```

## 3. Regla importante

No perder información al normalizar.

Estos conceptos NO deben colapsarse sin más:

- Bb Clarinet vs A Clarinet;
- Bb Clarinet vs Bass Clarinet;
- Horn vs English Horn;
- Trumpet vs Cornet vs Flugelhorn;
- Bassoon vs Contrabassoon.

## 4. Pipeline de resolución

### Paso 1 — Metadata MusicXML

Usar primero información estructurada disponible, según soporte real del parser:

- score-part;
- score-instrument;
- instrument-name;
- instrument-sound;
- MIDI instrument/program;
- transpose;
- chromatic transpose;
- octave change;
- otras pistas existentes.

Los nombres exactos deben adaptarse a la librería/modelo actual.

### Paso 2 — Text normalization

Normalizar:
- lowercase;
- espacios;
- puntuación;
- diacríticos cuando sea apropiado;
- `♭`, `b`, `flat`;
- `♯`, `#`, `sharp`;
- ordinales;
- números de parte.

No eliminar tokens musicalmente relevantes:
- bb;
- eb;
- a;
- f;
- bass;
- alto;
- tenor;
- baritone;
- contrabass;
- piccolo.

### Paso 3 — Alias catalog

Mantener catálogo configurable fuera de lógica imperativa.

Ejemplo conceptual:

```yaml
clarinet.bb:
  section: woodwind
  family: clarinet
  instrument: clarinet
  variant: soprano
  transposition: bb
  aliases:
    - clarinet in bb
    - bb clarinet
    - b-flat clarinet
    - clarinete en sib
    - clarinete sib
    - clarinetto in sib
```

### Paso 4 — Semantic embeddings

Si alias/metadata no resuelven:

1. generar embedding del nombre normalizado;
2. comparar con descripciones/aliases del catálogo;
3. obtener top candidates;
4. aceptar SOLO con umbral de confianza suficientemente alto;
5. si existe ambigüedad, continuar a LLM.

Para el tamaño actual del catálogo:
- mantener embeddings en memoria o cache;
- NO introducir vector DB remota.

### Paso 5 — LLM fallback

Enviar:
- nombre original;
- nombre normalizado;
- metadata MusicXML relevante;
- top candidates;
- catálogo permitido.

El LLM debe:
- elegir solo una identidad del catálogo;
- o devolver UNKNOWN.

Salida estructurada.

Ejemplo conceptual:

```json
{
  "canonicalId": "clarinet.bass.bb",
  "confidence": 0.94,
  "reason": "..."
}
```

### Paso 6 — Human confirmation

Si confidence < threshold:

```text
Instrumento no identificado con suficiente confianza
Nombre original: "Bajo 2"

Opciones:
- Bass Clarinet
- Bassoon
- Baritone Saxophone
- Euphonium
- Tuba
- Otro
```

La UI debe permitir confirmar/corregir.

### Paso 7 — Progressive Knowledge Capture

Si el usuario confirma una resolución:
- persistir alias si la arquitectura lo permite;
- asociar al catálogo canónico;
- resolver determinísticamente la próxima vez.

No modificar automáticamente el catálogo global sin validación.

---

# 5. Confidence y source

Guardar al menos:

```text
source:
- MUSICXML
- ALIAS
- SEMANTIC
- LLM
- USER
- UNKNOWN
```

y:

```text
confidence: 0..1
```

Los thresholds deben estar en configuración.

Ejemplo inicial, NO definitivo:

```text
>= 0.90 -> auto accept
0.70..0.90 -> accept with warning/review option
< 0.70 -> human confirmation
```

Calibrarlos con datos.

---

# 6. Matching específico primero

Evitar matching ingenuo por substring.

Ejemplo peligroso:

```text
"English Horn"
```

no debe resolverse como:

```text
Horn / Trompa
```

Los aliases más específicos tienen prioridad.

Añadir tests explícitos.

---

# 7. Tests mínimos

Cubrir en español, inglés e italiano cuando sea útil:

- Clarinet
- Clarinet in Bb
- Bb Clarinet
- B-flat Clarinet
- Clarinete
- Clarinete Sib
- Clarinete en Si bemol
- Clarinetto
- Bass Clarinet
- Clarinete bajo
- Horn
- French Horn
- Horn in F
- Trompa
- Trompa en Fa
- Corno
- English Horn
- Corno inglés
- Alto Sax
- Alto Saxophone in Eb
- Saxofón alto
- Trumpet
- Cornet
- Flugelhorn
- Euphonium
- Baritone Horn

Añadir también:
- nombres abreviados;
- numeración de partes;
- desconocidos;
- nombres ambiguos.

---

# 8. Criterio de éxito

Medir:
- exact accuracy;
- top-k accuracy para semantic resolver;
- unresolved rate;
- false automatic resolution rate;
- confidence.

La prioridad es evitar clasificaciones automáticas incorrectas.
