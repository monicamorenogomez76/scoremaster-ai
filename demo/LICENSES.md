# Obras de la cuenta demo

Las tres obras de esta carpeta son **composiciones originales** de este repositorio, escritas con
`scripts/generate_demo_scores.py`. Se publican con licencia **CC0 1.0** (dominio público): se pueden usar,
copiar y modificar sin pedir permiso ni citar.

Cada obra parte de una progresión armónica funcional y de melodías escritas a mano cuyas notas en parte fuerte
pertenecen al acorde. El bajo y las voces interiores los elige un armonizador a cuatro voces:
- sin quintas ni octavas paralelas;
- con los acordes completos y la sensible sin doblar;
- con las séptimas resueltas por grado descendente.

Después se reparten entre los instrumentos dentro de su tesitura. Las pruebas de `backend/test/test_demo_scores.py`
comprueban esas reglas, las tesituras, el final en la tónica y los grados que da ScoreLint.

| Archivo | Obra | Forma y lo que muestra en ScoreLint |
|---|---|---|
| `marcha-de-la-plaza.musicxml` | Marcha de la plaza | Marcha en Si♭ (2/4). Introducción, primera parte, trío en Mi♭, interludio en do menor (metales graves contra escalas de las maderas) y trío *grandioso* con un adorno en semicorcheas. **Grado 4**, con pasajes críticos en flauta, oboe y clarinete |
| `andante-y-danza.musicxml` | Andante y danza | Andante en Mi♭ en frases de cuatro compases y danza en do menor (3/4, *Allegro vivo*) con arpegios, saltos y una línea de saxo tenor sin descanso. **Grado 4**, con pasajes críticos |
| `coral-para-principiantes.musicxml` | Coral para principiantes | Coral a cuatro voces en Mi♭ de ocho compases, tocado por las maderas, los metales y el tutti, con respiración al final de cada frase. **Grado 2**, sin pasajes críticos |

## Obra para subir en directo

`para-subir/pasodoble-de-las-fiestas.mxl` (también CC0) **no se carga** en la cuenta demo: está para subirla durante la
demostración y enseñar todo el recorrido, desde «Añadir obra» hasta el análisis, la banda, el ensayo y los pasajes. Es
MusicXML comprimido (`.mxl`), el formato que exportan MuseScore, Finale o Sibelius.

| Archivo | Obra | Forma y lo que muestra en ScoreLint |
|---|---|---|
| `para-subir/pasodoble-de-las-fiestas.mxl` | Pasodoble de las fiestas | Pasodoble (2/4, ♩=100): introducción en fanfarria, primera parte en fa menor con el ritmo de corchea con puntillo y semicorchea, segunda parte en La♭ mayor, trío en Re♭ con la «canción» en bombardino y saxos, y final *ff* con las trompetas. Las voces se turnan para descansar. **Grado 4**: ScoreLint pesa el *oom-pah* continuo como densidad y resistencia |

Para regenerarlas: `python scripts/generate_demo_scores.py`. El resultado es idéntico en cada ejecución salvo la
fecha de codificación que escribe music21; una prueba comprueba que estos archivos coinciden con el generador.

No se incluyen transcripciones de obras de dominio público: no se encontró ninguna en MusicXML con una
licencia que permita redistribuirla (2026-10-14). Las marchas de Sousa que publica la Banda de los
Marines de EE. UU. son de dominio público pero están en PDF; se podrían convertir con un lector óptico de partituras (opcional).
