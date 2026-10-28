> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Instrument Resolution Design

## Estado de implementación

**Paso 06 integrado en código (catálogo canónico):** `backend/domain/instrument_catalog.json`
contiene 48 identidades con sección, familia, variante, transposición, etiquetas y
aliases en español, inglés e italiano. `backend/domain/instrument_catalog.py` normaliza
el nombre (minúsculas, acentos, `♭`/`flat` → `b`, puntuación), separa los números de
parte (`2`, `II`, `2nd`, `1 & 2`, `1/2`) y busca el alias **exacto**: no hay coincidencia
por substring ni difusa. Lo que no está en el catálogo es `UNKNOWN`.

Decisiones musicales, para contexto de banda:

- «Clarinet»/«Clarinete» sin afinación es clarinete en Si♭ (en orquesta podría ser en La).
- «Trumpet»/«Trompeta» es en Si♭; «Horn»/«Trompa» es la trompa en Fa, otro instrumento.
- «Baritone»/«Barítono» a secas es el saxofón barítono; «Baritone Horn» es el bombardino barítono.
- «Requinto» es el clarinete en Mi♭.
- El bajo eléctrico y las guitarras eléctrica y acústica forman la **sección rítmica**, con pesos
  de dificultad neutros (los de «Otros») hasta poder calibrarlos; la batería sigue en percusión.
  «Guitar»/«Guitarra» sin tipo queda `UNKNOWN` (catálogo `instrument-catalog-v2`).
- «Trombone 3» es un trombón tenor; una parte compartida «Trombone 3 & Bass Trombone»
  queda `UNKNOWN` para confirmación humana. «Cymbal» a secas también.

**Paso 07 integrado en código (metadatos del parser):** cada `ScorePart` conserva en
`metadata` (`PartMetadata`) lo que declara el MusicXML, sin interpretarlo: `part_id`,
nombre original con espacios normalizados, abreviatura, `instrument-name`,
`instrument-sound`, programas y canales MIDI tal como aparecen (1–128 y 1–16), la primera
`<transpose>` (`chromatic`, `diatonic`, `octave-change`) y el número de pentagrama cuando
music21 divide una parte de varios pentagramas. Se lee directamente del XML con
ElementTree; el parser rechaza documentos con `<!ENTITY>` y acepta `.mxl` aunque el
archivo tenga extensión `.musicxml`. Los cambios de transposición posteriores al
primer `<transpose>` todavía no se modelan.

**Paso 08, primera parte (resolver determinista):** `backend/domain/instrument_resolver.py`
combina el nombre de la parte y los `instrument-name` declarados. Si coinciden: `resolved`,
fuente `MUSICXML`, 0.97. Solo el nombre: `resolved`, `ALIAS`, 0.90. Solo el metadato:
`review`, `MUSICXML`, 0.75. Si discrepan: `conflict`, sin identidad y con ambos
candidatos. Sin pruebas: `unknown`. Varios `instrument-name` que nombran instrumentos
distintos (kits de percusión) no cuentan; el programa MIDI no se usa. Los umbrales
(0.90 aceptación, 0.70 revisión) son iniciales y deben calibrarse. `/analyze` devuelve
`instruments` con identidad, estado, fuente, confianza y evidencias. BandFit, la
dificultad y el audio todavía usan el nombre de la parte: es la segunda parte del paso 08.
La dificultad por instrumento ya usa la identidad resuelta: la familia es la sección del
catálogo y el perfil es el existente para esa identidad (`PROFILE_BY_CANONICAL_ID`), sin
perfiles nuevos. Las partes sin identidad mantienen la clasificación anterior por nombre,
y el baseline legacy sigue idéntico. El audio también la usa: cada identidad del catálogo declara su `sound` General MIDI
(`instrument-catalog-v3`; la percusión sin altura no tiene, la sintetiza el reproductor),
`/playback` devuelve `canonical_id` y `sound` por pista y el reproductor prioriza `sound`
sobre el programa MIDI y el nombre. BandFit (agrupar por identidad cambia la plantilla de
la interfaz) queda para el paso 09.
Con las partituras locales: 75 partes `resolved`, 2 `review`, 35 `unknown` (partes
«Voice») y ningún conflicto ni clasificación incorrecta.

Con las partituras locales de prueba (no versionadas), 49 de 52 nombres se resuelven
y ninguno se clasifica incorrectamente. Todavía no lo consumen BandFit, la dificultad
ni el audio: eso corresponde al resolver determinista (paso 08).

**Paso 09 (confirmación humana y BandFit por instrumento):** las partes `unknown`, `conflict` y
`review` se confirman en «Mi banda» con un desplegable del catálogo (`GET /instruments/catalog`;
primero la propuesta y los candidatos). `/analyze` recibe `instrument_overrides` (nombre de parte →
identidad del catálogo, validada) y el parser añade `PartMetadata.confirmed_id`: el resolver la usa
antes que cualquier evidencia, con fuente `USER` y confianza 1.0, así que la dificultad, los grupos
de ensayo y BandFit la aplican. Las confirmaciones se guardan en la configuración del análisis.
BandFit agrupa por identidad (decisiones del 2026-10-04): un músico por voz
(«Clarinet 1 & 2» cuenta dos; los pentagramas de una parte de viento son sus voces y los de un
teclado, un solo músico) y la percusión como percusionistas en total, uno por parte. Las partes sin
confirmar se listan aparte y no cuentan en el porcentaje. Queda para más adelante: recordar alias
confirmados (captura progresiva), percusionistas simultáneos por compás y aplicar la confirmación
al audio de `/playback` (el diálogo previo de partes «Voice» sigue cubriendo ese caso).

**Nombres en siete idiomas (2026-10-28, `instrument-catalog-v5`, `instrument-resolver-v2`):** el catálogo reconoce
los nombres en castellano, valenciano y catalán, inglés, alemán, italiano, francés y gallego, con sus abreviaturas. La
tonalidad escrita de cualquier forma («in Bb», «in B b», «B♭», «Sib», «Si bemol», el alemán «in B» y «Es», «Mib», «en
Fa», «Do») se convierte en una sola marca al final del nombre. Un nombre de la familia con tonalidad da la identidad de
esa tonalidad («Klarinette in A» es el clarinete en La). Bombardino, tuba y trombones se aceptan en cualquier
tonalidad. Cualquier otra tonalidad queda sin reconocer («Trompa en Mib»).

**Catálogo en la base de datos (2026-10-28):** los instrumentos y todos sus nombres están en las tablas `instruments`
e `instrument_names` (migración `0015_instrument_catalog`). El archivo JSON queda como semilla de la migración y como
catálogo de las pruebas sin base.
- **Al arrancar**, el servidor lee el catálogo común y se lo entrega al dominio (`use_catalog`). El dominio no conoce
  la base.
- **La versión del catálogo** es la de la semilla mientras el contenido sea el mismo. Cualquier nombre o instrumento
  añadido o quitado la cambia (`instrument-catalog-v5+<huella>`), y las obras se analizan de nuevo en el siguiente
  arranque.
- **La administración** (`ADMIN_EMAILS`) gestiona el catálogo en Configuración › Instrumentos: busca un instrumento,
  añade o quita los nombres con los que aparece en las partituras y crea instrumentos comunes con familia, sección,
  tonalidad, sonido y grupo de ensayo.
- **Un nombre nunca nombra dos instrumentos:** se rechaza (409) si el catálogo ya lo reconoce, incluso con su
  tonalidad. La base lo garantiza con un índice único sobre el nombre normalizado.

**Nombres aprendidos e instrumentos propios (2026-10-28):** lo que una cuenta confirma se aprende para sus siguientes
obras.
- **Cómo se aprende:** el nombre de la parte, normalizado y sin números de parte, se guarda en `instrument_names`
  con el `owner_id` de la cuenta. Así, si «Fiscornio 1» se confirma como fliscorno, «Fiscornio 3» sale reconocido en
  la obra siguiente, también si viene de un PDF. La configuración del análisis guarda lo aplicado como confirmación.
- **Prioridad del catálogo común:** lo aprendido solo nombra las partes que el catálogo común no reconoce; nunca
  cambia un nombre que el catálogo ya conoce.
- **Instrumentos propios:** si el instrumento no está en el catálogo, «Mi banda» ofrece «Otro instrumento…». Pide el
  nombre, la familia, la tonalidad, el sonido y el grupo de ensayo, y crea un instrumento propio de la cuenta
  (`own.<id>`) que aprende el nombre de la parte. Cuenta en BandFit y en la plantilla, y en el grado, con el perfil
  genérico de su familia.
- **Aislamiento entre cuentas:** lo aprendido y los instrumentos propios de una cuenta no llegan a ninguna otra.
  Confirmar el instrumento propio de otra cuenta se rechaza (400).

Queda para más adelante que el audio de `/playback` use las confirmaciones, como ya pasaba con las confirmaciones del
paso 09.

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
