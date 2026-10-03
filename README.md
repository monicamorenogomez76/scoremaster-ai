
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

El flujo de trabajo y las pautas de cambios están en [CONTRIBUTING.md](CONTRIBUTING.md).
[AGENTS.md](AGENTS.md) asigna cada tipo de tarea a una skill del asistente de
`skills/`. Las partituras comerciales para pruebas manuales van en
`test-scores/local/`, que no se versiona.

## Estado

El MVP incluye análisis determinista de dificultad, compatibilidad de plantilla,
plan de ensayo y un cuadro de mando por familias, instrumentos y pasajes críticos.

La interfaz está construida con React y Vite: acceso demo, navegación, carga y
análisis, resumen, dificultad, plantilla, plan de ensayo, visores, audio y vídeos.
Ver [arquitectura y arranque del frontend](frontend/README.md). Para ejecutar con
Python, compilar primero con `npm --prefix frontend ci` y
`npm --prefix frontend run build`; Docker lo hace durante la construcción.

La interfaz ofrece navegación por vistas y una entrada de demostración. No hay
autenticación real ni persistencia de cuentas: la sesión y la plantilla son locales
al navegador y temporales.

El aviso de registro agudo utiliza SL002 (antes SL005), según el catálogo
de reglas del proyecto. Mantiene su peso de dos puntos en el análisis.

ScoreLint incluye SL005 para ocho o más compases activos sin silencios. Es una
aproximación de continuidad por compases, no una estimación fisiológica de fatiga.
Cualquier silencio explícito o compás vacío interrumpe el bloque.

## Partitura y vídeos

Cada pasaje crítico ofrece una única acción «Ver pasaje». Su visor incluye
«Reproducir» y «Detener» para escuchar únicamente esa parte con
muestras General MIDI mediante [smplr](https://github.com/danigb/smplr), versión
1.1.0. «Detener» y cerrar la partitura interrumpen el audio. La reproducción usa
altura de concierto, acordes, silencios, ligaduras y cambios de tempo del
MusicXML; sin tempo se indica el valor por defecto de negra = 120. Se reproduce
el rango escrito una vez, sin desarrollar repeticiones ni aplicar expresividad.
Los timbres son aproximados; bombardino usa tuba y clarinetes graves usan
clarinete. Si no se reconoce el timbre se usa piano y se indica en pantalla.
La percusión reconocida usa sonidos sintetizados aproximados; se avisa cuando
una parte sin altura no se puede interpretar.

El navegador necesita Internet para descargar el módulo y las muestras; la
partitura no se envía al proveedor de sonidos. El endpoint `/playback` procesa
temporalmente el archivo y limita la subida a 8 MB, el contenido descomprimido a
20 MB, el pasaje a 10 000 eventos y el conjunto a 150 000 eventos.

Los pasajes críticos se pueden abrir como notación MusicXML renderizada en el
navegador mediante [OpenSheetMusicDisplay](https://opensheetmusicdisplay.org/).
El archivo original se conserva en el navegador solo durante la sesión de
análisis y no se persiste en el servidor.

En «Analizar partitura», después de completar el análisis, la partitura aparece en un visor
grande incrustado, con todas las voces, páginas de cuatro compases, zoom y pantalla
completa. Incluye reproducción del conjunto, pausa, detener, posición, velocidad
y volumen. La página se ajusta al ancho y al alto disponibles, con controles
mediante iconos y una opción para volver al ajuste automático. «Nueva partitura»
limpia el análisis, el visor y el audio; elegir otro archivo también reinicia la sesión.
Si el MusicXML contiene partes genéricas como «Voice», se permite asignar sus
instrumentos antes del análisis. Esta asignación modifica una copia temporal de
la sesión, conservando el archivo original. No se deducen instrumentos cuando
el archivo no los identifica. El visor y los sonidos muestran «Cargando…» durante su preparación;
la carga del audio se puede cancelar con Detener. El audio se programa por pequeñas
ventanas de tiempo para evitar preparar todos los sonidos simultáneamente.

La búsqueda integrada de vídeos usa YouTube Data API v3. Para activar resultados
reproducibles dentro de la aplicación, configura `YOUTUBE_API_KEY` como variable
de entorno del servidor. La clave nunca debe incluirse en el HTML, enviarse al
navegador ni versionarse. Sin ella, se muestra una búsqueda directa en YouTube y
se permite pegar un enlace para reproducirlo en la aplicación.

La plantilla de banda se inicializa con una plaza por cada parte de la obra
cargada, usando la instrumentación de Persis como referencia inicial. Los cambios
son temporales durante la sesión; todavía no se guardan por usuario.

### Pruebas de interfaz

Las pruebas unitarias del reproductor y el visor se ejecutan con
`node --test backend/test/frontend/*.test.mjs`. El recorrido real de carga,
análisis, ajuste de página, reinicio y asignación de instrumentos usa Playwright
con Chromium y partituras sintéticas. Con el servidor local activo:

```sh
npm install --prefix /tmp/scoremaster-browser-tests @playwright/test
/tmp/scoremaster-browser-tests/node_modules/.bin/playwright install chromium
PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/workflow.e2e.mjs
PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/dashboard.e2e.mjs
```

Por defecto usa `http://127.0.0.1:8005`; puede cambiarse con `SCOREMASTER_URL`.
La descarga del visor necesita conexión a Internet.

### Integración continua

GitHub Actions ([`.github/workflows/ci.yml`](.github/workflows/ci.yml)) se ejecuta en
cada pull request y en cada push a `main`, con permisos de solo lectura:

- **tests**: build del frontend, pruebas unitarias de Node y pytest con PostgreSQL 17
  real (`TEST_DATABASE_URL`), de modo que las pruebas de persistencia no se omiten.
- **e2e**: migra la base, arranca Uvicorn y ejecuta los recorridos Playwright de carga,
  visores y panel con Chromium. Las muestras de sonido se sustituyen; el visor
  OpenSheetMusicDisplay se descarga de su CDN.
- **docker**: valida `docker-compose.yml` y construye la imagen de producción.

La base de PostgreSQL del CI es temporal y usa credenciales desechables definidas
en el propio workflow; no requiere secretos del repositorio.

### Diseño de la interfaz

La interfaz usa un logo SVG propio, una paleta azul/violeta, superficies claras,
controles con iconos y gráficos de grado por familia sobre una escala explícita
de 1 a 5. Los valores también aparecen como texto. Las acciones principales y
secundarias se distinguen visualmente, el foco del teclado permanece visible y
los controles del reproductor tienen áreas de 44 × 44 píxeles. Se respeta la
preferencia de movimiento reducido.

El diseño se orienta por [WCAG 2.2](https://www.w3.org/TR/WCAG22/) y
[Material Design 3](https://m3.material.io/). Playwright comprueba escritorio y
móvil, ausencia de desbordamiento horizontal, el tamaño del botón de reproducción
y el foco al navegar con Tab. Esto no constituye una auditoría completa de
conformidad WCAG.

## Evolución aprobada

El [plan de PR pequeñas](docs/IMPLEMENTATION_ROADMAP.md) y las
[especificaciones](docs/README.md) describen lo previsto. PostgreSQL y el guardado de análisis ya están implementados. Grados 1–6,
feedback y revisión LLM siguen previstos.

El [baseline reproducible](evaluation/README.md) captura el comportamiento legacy
antes de cambiar sus reglas: `python -m evaluation.baseline`.

El [arranque de PostgreSQL](docs/POSTGRESQL.md) requiere `.env` y conserva los
datos en un volumen. Aplicar las migraciones antes de analizar: cada análisis
correcto se guarda y devuelve `analysis_id`. El archivo original y el audio no se
guardan; todavía no existe historial público ni vinculación a cuentas.
