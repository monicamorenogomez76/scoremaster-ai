
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

ScoreLint detecta densidad rítmica (SL003), intervalos amplios (SL004), registro
agudo (SL002) y bloques de ocho o más compases activos sin silencios (SL005).
Estos últimos aparecen entre los pasajes críticos y aportan dos puntos al
indicador de avisos. El análisis de continuidad se comparte con la dimensión
de resistencia de la dificultad por instrumento.

La resistencia es una aproximación por compases: cualquier silencio explícito
o compás vacío corta el bloque. No estima fatiga física, duración en segundos,
respiraciones ni descansos entre voces simultáneas. SL002 sustituye al antiguo
código SL005 del aviso de registro agudo para seguir el catálogo del proyecto.

Para ejecutar las pruebas desde la carpeta del proyecto:
`python -m pytest -q` (con las dependencias de `requirements.txt` instaladas).

## Partitura y vídeos

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
