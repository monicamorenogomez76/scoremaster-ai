> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Realistic Audio Plan

## Estado

Implementado: reproducción híbrida en el navegador. Los instrumentos con grabaciones reales
de tonejs-instruments (VSCO 2 CE, Karoryfer, Iowa) usan esas muestras, con la grabación más
cercana a cada nota y transposición de smplr; el resto usa el banco General MIDI MusyngKite,
que también actúa como respaldo si las grabaciones no se descargan. Pendientes: dinámicas,
articulaciones y un renderer desacoplado. Ver «Créditos de sonido» en el README.

Valoración de la autora (2026-10-04): la reproducción mejora pero todavía no es buena;
se aplaza. Candidatos para retomarlo: dinámicas y articulaciones del MusicXML, envolventes
y release por instrumento, reverberación ligera, más capas de velocidad y bibliotecas
con más muestras por instrumento (University of Iowa, VSCO 2 CE completo).
Batería: los golpes simultáneos (`PercussionChord`) ya se reproducen, pero music21 no conserva
el instrumento del kit de cada golpe y todos usan la tecla del primer instrumento de la parte
(en Oregon Trail, bombo). Mapear cada `<instrument id>` a su `midi-unpitched` es una mejora pendiente.

Regresión de sonido: `backend/test/frontend/recorded-sample.e2e.mjs` renderiza el clarinete
grabado con smplr real y falla si el resultado es silencio (smplr 1.1.0 reproduce en
silencio los mapas `buffers` simples; se usa un preset con `pitch` y `keyRange`).

## 1. Problema

La reproducción actual puede sonar demasiado MIDI / General MIDI.

MIDI no es necesariamente el problema: puede conservarse como representación intermedia.

La mejora principal debe estar en el motor de rendering y en las muestras.

## 2. Objetivo

```text
MusicXML
   ↓
Performance events / MIDI
   ↓
Sample-based renderer
   ↓
WAV/stream
```

Mantener el renderer desacoplado del análisis.

## 3. Arquitectura

Crear/adaptar una abstracción equivalente a:

```text
AudioRenderer
├── ExistingRenderer
└── SampledAudioRenderer
```

y un componente equivalente a:

```text
PerformanceEventMapper
```

que traduzca MusicXML a eventos expresivos:

```text
pitch
start
duration
velocity/dynamic
articulation
instrument
```

## 4. Samples

Preferir:
- sample libraries legalmente compatibles;
- SFZ u otro formato abierto/automatizable;
- descarga opcional.

No incluir grandes bancos de samples en Git por defecto.

Preferir:

```text
assets-manifest
+
download/install script
```

Antes de elegir una librería:
- verificar licencia;
- verificar redistribución;
- documentar attribution si aplica.

## 5. Expresión

Si el MusicXML lo permite mapear:

- pp/p/mp/mf/f/ff;
- crescendo;
- diminuendo;
- staccato;
- tenuto;
- accent;
- slur;
- fermata.

No implementar articulaciones que el banco no soporte fingiendo que existen.

## 6. Humanization

Si se añade:
- pequeñas variaciones de timing;
- pequeñas variaciones dinámicas;
- release;
- phrase shaping.

Debe ser:
- sutil;
- reproducible.

Usar seed determinista si se introduce aleatoriedad.

## 7. Post-processing

Opcional:
- reverb ligera;
- gain normalization.

No dedicar al audio un esfuerzo que comprometa la evaluación de dificultad.

## 8. Prioridad

El audio es recomendable pero secundario respecto a:

1. correctness;
2. instrument resolution;
3. difficulty/criticality;
4. evaluation.

## 9. Tests

Tests posibles:
- instrument mapping -> correct sample program;
- dynamics mapping;
- articulation mapping;
- deterministic event generation;
- fallback if sample unavailable.

No es necesario testear "suena bonito" automáticamente.
