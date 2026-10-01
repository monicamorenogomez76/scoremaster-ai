
# ScoreMasterAI

Asistente para directores de banda que analiza partituras,
comprueba su adecuación a la plantilla y ayuda a planificar ensayos.

Proyecto de TFM del Máster de Desarrollo con IA de BigSchool.

## Funcionalidades previstas

- Análisis de partituras en formato MusicXML.
- Estimación reproducible de dificultad mediante ScoreLint.
- Comprobación de la plantilla de la banda mediante BandFit.
- Planificación de ensayos y explicaciones asistidas por IA.

## Principios de desarrollo

- Clean Architecture y principios SOLID, evitando sobreingeniería.
- Seguridad basada en OWASP desde el diseño.
- Separación entre datos musicales, algoritmos, reglas e IA generativa.
- Pruebas automáticas y ejecución reproducible.
- Documentación actualizada con cada cambio.
- Ejecución sin API key mediante un modo demo identificado claramente.

## Estado

El MVP incluye análisis determinista de dificultad, compatibilidad de plantilla,
plan de ensayo y un cuadro de mando por familias, instrumentos y pasajes críticos.

La interfaz ofrece navegación por vistas y una entrada de demostración. No hay
autenticación real ni persistencia de cuentas: la sesión y la plantilla son locales
al navegador y temporales.

El aviso de registro agudo utiliza SL002 (antes SL005), según el catálogo
de reglas del proyecto. Mantiene su peso de dos puntos en el análisis.

## Partitura y vídeos

Cada pasaje crítico ofrece «Escuchar» para reproducir únicamente esa parte con
muestras General MIDI mediante [smplr](https://github.com/danigb/smplr), versión
1.1.0. «Detener» y cerrar la partitura interrumpen el audio. La reproducción usa
altura de concierto, acordes, silencios, ligaduras y cambios de tempo del
MusicXML; sin tempo se indica el valor por defecto de negra = 120. Se reproduce
el rango escrito una vez, sin desarrollar repeticiones ni aplicar expresividad.
Los timbres son aproximados; bombardino usa tuba y clarinetes graves usan
clarinete. Si no se reconoce el timbre se usa piano y se indica en pantalla.
La percusión sin altura todavía no se reproduce y se avisa si se omite.

El navegador necesita Internet para descargar el módulo y las muestras; la
partitura no se envía al proveedor de sonidos. El endpoint `/playback` procesa
temporalmente el archivo y limita la subida a 8 MB, el contenido descomprimido a
20 MB y el pasaje a 10 000 notas.

Los pasajes críticos se pueden abrir como notación MusicXML renderizada en el
navegador mediante [OpenSheetMusicDisplay](https://opensheetmusicdisplay.org/).
El archivo original se conserva en el navegador solo durante la sesión de
análisis y no se persiste en el servidor.

La búsqueda integrada de vídeos usa YouTube Data API v3. Para activar resultados
reproducibles dentro de la aplicación, configura `YOUTUBE_API_KEY` como variable
de entorno del servidor. La clave nunca debe incluirse en el HTML, enviarse al
navegador ni versionarse. Sin ella, se muestra una búsqueda directa en YouTube y
se permite pegar un enlace para reproducirlo en la aplicación.

La plantilla de banda se inicializa con una plaza por cada parte de la obra
cargada, usando la instrumentación de Persis como referencia inicial. Los cambios
son temporales durante la sesión; todavía no se guardan por usuario.
