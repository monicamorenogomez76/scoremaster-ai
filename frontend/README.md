# Frontend React

React 19.3.0 y Vite 8.3.2, con versiones exactas y `package-lock.json`. Node
20.19+ o 22.12+; Docker construye con Node 24. React, ReactDOM y el motor de
reproducción se empaquetan localmente. El motor de notación OpenSheetMusicDisplay
1.9.2 y las muestras smplr/FluidR3_GM se descargan de sus CDN públicos; la partitura
nunca se envía a esos proveedores.

## Arranque

Desde la raíz, con Node instalado:

```sh
npm --prefix frontend ci
npm --prefix frontend run build
```

El build escribe exclusivamente en `backend/app/static/frontend/`, ignorado por
Git. FastAPI sirve su `index.html` y los assets mediante `/static/frontend/`.
Configurar PostgreSQL y las migraciones según [la guía](../docs/POSTGRESQL.md),
después arrancar Uvicorn. Si no hay build, `/` devuelve 503 con instrucciones.
Para desarrollo puede usarse `npm --prefix frontend run watch` y recargar el
navegador tras cada cambio. Esta primera entrega no incorpora un servidor HMR.

Docker compila el frontend en una etapa Node y copia solo el build a la etapa
Python; no necesita Node instalado en el equipo ni en la imagen final. El contexto
excluye dependencias locales, credenciales y partituras de prueba.

## Estructura

- `App.jsx`: sesión demo, vista activa, resultado del análisis, plantilla y duración.
  La sesión demo es una comodidad local en `sessionStorage`, no autenticación.
- `AppShell.jsx`, `View.jsx`, `LoginScreen.jsx`: barra lateral, menú móvil, cabecera y vistas.
- `OverviewView.jsx`, `DifficultyView.jsx`, `BandView.jsx`, `RehearsalView.jsx`:
  resumen, explorador familia → instrumento → pasaje, BandFit y plan de ensayo.
- `UploadWorkspace.jsx` y `useScoreAnalysis.js`: formulario, asignaciones,
  solicitudes, cancelación y descarte de respuestas anteriores.
- `labels.js`: textos en castellano de instrumentos, familias, findings, BandFit y ensayo.
- `schedule.js` y `RehearsalView.jsx`: calendario del ensayo. Cada bloque ocupa el ancho de sus
  minutos desde la hora de inicio, con un color por sección; al pulsarlo se abre la partitura en
  sus compases solo con sus instrumentos (toda la banda en el tutti, con un botón por pasaje) y
  se pueden escuchar juntos (`/playback` acepta varios `instruments`).
- `instrument-session.js`: modifica una copia temporal del XML; conserva el archivo
  seleccionado y la instrumentación no identificada cuando no hay confirmación.
- `score/`: visores y audio.
  - `score-session.js`: archivo seleccionado y su MusicXML, descargado una vez por archivo.
  - `FullScoreViewer.jsx` y `full-score-renderer.js`: partitura completa en páginas de
    cuatro compases. React dibuja los controles; el renderer solo gestiona la notación
    OpenSheetMusicDisplay dentro de su contenedor.
  - `PassageDialog.jsx`: pasaje completo de un instrumento con desplazamiento interno.
  - `useTransport.js` y `TransportBar.jsx`: ciclo de reproducción y controles comunes a
    ambos visores. La posición y el volumen usan listeners nativos para no volver a
    renderizar 20 veces por segundo.
  - `playback.js`, `playback-guide.js`, `musicxml-passage.js`: motor de audio, guía de
    compás y extracción de pasajes, sin dependencias de React.
- `videos/`: búsqueda de vídeos a través del servidor e inserción con
  `youtube-nocookie.com`. Solo se admiten identificadores y enlaces de YouTube válidos.

`window.scoremasterWorkspace` es un acceso de diagnóstico para las pruebas de
navegador: permite cargar partituras y pasajes sintéticos. No amplía permisos: solo
actúa sobre la sesión local del navegador.

## Verificación

Compilar antes de ejecutar las pruebas Python que consultan `/`. Con Uvicorn en
8006 y Playwright/Chromium instalados según el README principal:

```sh
SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/react-upload.e2e.mjs
SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/workflow.e2e.mjs
SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/dashboard.e2e.mjs
node --test backend/test/frontend/*.test.mjs
```

El recorrido React usa únicamente una partitura sintética; simula fallos 503,
respuestas no JSON y una respuesta tardía tras cancelar. El recorrido compartido
comprueba asignación, reinicio, móvil, pasaje completo y guía de reproducción. El
recorrido del dashboard comprueba sesión demo, recálculo de BandFit y ensayo,
explorador de dificultad, menú móvil y salida de la demo.
