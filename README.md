
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

## Arranque rápido y credenciales de prueba

```sh
cp .env.example .env        # credenciales locales de ejemplo
docker compose up --build   # migra la base, crea el usuario demo y sirve en http://127.0.0.1:8000
```

| Usuario de prueba | Contraseña |
|---|---|
| `demo@scoremaster.local` | `scoremaster-demo` |

También se puede crear una cuenta desde la pantalla de acceso. «Entrar con Google»
solo aparece si `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET` están configurados; sin
ellos la aplicación funciona igual con email y contraseña. Las medidas de seguridad
aplicadas y pendientes están en [docs/SECURITY.md](docs/SECURITY.md).

## Estado

El MVP incluye análisis determinista de dificultad, compatibilidad de plantilla,
plan de ensayo y un cuadro de mando por familias, instrumentos y pasajes críticos.

La interfaz está construida con React y Vite: acceso demo, navegación, carga y
análisis, resumen, dificultad, plantilla, plan de ensayo, visores, audio y vídeos.
Ver [arquitectura y arranque del frontend](frontend/README.md). Para ejecutar con
Python, compilar primero con `npm --prefix frontend ci` y
`npm --prefix frontend run build`; Docker lo hace durante la construcción.

La aplicación exige iniciar sesión (email y contraseña, Google opcional). Cada obra
analizada se guarda en «Mis obras» con su último análisis, y la plantilla de la banda
se conserva por usuario.

La navegación sigue la propuesta de interfaz de la autora (2026-10-05):

- **Resumen**: próximo ensayo, obras en preparación y prioridades por sección (de momento, los
  pasajes críticos de las obras en preparación, marcados con origen «Análisis»).
- **Repertorio**: buscador, «Añadir obra» y, por obra, estado de preparación (independiente de la
  dificultad) y estado del análisis. El detalle de una obra tiene las pestañas **Partitura**,
  **Dificultad** y **Grabaciones**.
- **Mi banda**.
- **Ensayos**: ensayos guardados (fecha, hora, duración, lugar, objetivos y varias obras) con una
  agenda de bloques editable; cada bloque indica la obra que se trabaja. El Resumen muestra el
  ensayo de hoy o el próximo. Debajo sigue el plan calculado de la obra abierta.
- El asistente IA se incorporará como panel contextual.

Estilo: blanco frío, grafito y azul eléctrico (`#365CFF`) con la fuente Inter incluida en el build,
sin peticiones a servicios de fuentes externos.

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
El archivo original se guarda en «Mis obras», visible solo para su propietario, y
se puede reabrir o eliminar (con sus análisis) en cualquier momento.

En «Repertorio», después de completar el análisis, la partitura aparece en un visor
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

La plantilla de banda tiene una fila por instrumento y empieza con los músicos que
pide la obra (uno por voz; la percusión, en percusionistas). «Actualizar análisis»
guarda la plantilla del usuario, que se aplica a las siguientes obras.

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

Por defecto usa `http://127.0.0.1:8005`; puede cambiarse con `SCOREMASTER_URL`. Los recorridos
entran con el usuario demo (`python -m backend.app.seed_demo` con `DEMO_USER_EMAIL` y
`DEMO_USER_PASSWORD`); `SCOREMASTER_USER` y `SCOREMASTER_PASSWORD` permiten usar otro.
La descarga del visor necesita conexión a Internet.

### Créditos de sonido

La reproducción usa [smplr](https://github.com/danigb/smplr) (MIT) con dos fuentes de
muestras, que se descargan de sus CDN durante la reproducción y no se incluyen ni se
modifican en este repositorio:

- **Grabaciones reales** de [tonejs-instruments](https://github.com/nbrosowsky/tonejs-instruments)
  (Nicholaus Brosowsky; commit fijado `622c2f1`), para fagot, clarinete, flauta, trompa,
  saxofón alto y tenor, trombón, trompeta, tuba, contrabajo, bajo y guitarras, arpa,
  xilófono y piano. Según su `sample-source-info.txt` proceden de
  [VSCO 2 Community Edition](https://versilian-studios.com/vsco-community/) (CC0),
  [Karoryfer Samples](https://shop.karoryfer.com/pages/free-samples) (CC0) y las muestras de la
  University of Iowa (uso sin restricciones). El clarinete no tiene fuente declarada; sus notas
  coinciden con el clarinete de VSCO 2 CE.
- **General MIDI MusyngKite** del paquete
  [midi-js-soundfonts](https://github.com/gleitz/midi-js-soundfonts) de Benjamin Gleitzman
  ([CC BY-SA 3.0](https://creativecommons.org/licenses/by-sa/3.0/)) para el resto de
  instrumentos y como respaldo si las grabaciones no se pueden descargar.

La percusión sin altura se sintetiza en el navegador.

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

La interfaz usa un logo SVG propio, la paleta blanco frío, grafito y azul eléctrico, superficies claras,
controles con iconos y gráficos de grado por familia sobre una escala explícita
de 1 a 6, con el nivel de la rúbrica (Iniciación … Superior). Los valores también aparecen como texto. Las acciones principales y
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
correcto se guarda en la biblioteca del usuario y devuelve `analysis_id` y `work_id`.
El audio no se guarda y no hay historiales públicos: cada obra es privada.
