# Obras de la cuenta demo

Las tres obras de esta carpeta son **composiciones originales generadas por reglas** con
`scripts/generate_demo_scores.py` para este repositorio. Se publican con licencia **CC0 1.0**
(dominio público): se pueden usar, copiar y modificar sin pedir permiso ni citar.

| Archivo | Obra | Qué muestra en ScoreLint |
|---|---|---|
| `marcha-de-la-plaza.musicxml` | Marcha de la plaza | Marcha en 2/4 con un tramo exigente: escalas en semicorcheas, trompetas agudas y saltos en el saxo alto |
| `andante-y-danza.musicxml` | Andante y danza | Andante lírico que pasa a un allegro con síncopas, tresillos, saltos y una línea de saxo tenor sin descanso |
| `coral-para-principiantes.musicxml` | Coral para principiantes | Notas largas y tesitura estrecha: el contraste de una obra fácil |

Para regenerarlas: `python scripts/generate_demo_scores.py`. El resultado es idéntico en cada ejecución salvo la
fecha de codificación que escribe music21; una prueba comprueba que estos archivos coinciden con el generador.

No se incluyen transcripciones de obras de dominio público: no se encontró ninguna en MusicXML con una
licencia que permita redistribuirla (2026-10-14). Las marchas de Sousa que publica la Banda de los
Marines de EE. UU. son de dominio público pero están en PDF; se podrían convertir con Audiveris (opcional).
