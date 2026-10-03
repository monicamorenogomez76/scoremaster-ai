# Frontend React — migración incremental

React 19.3.0 y Vite 8.3.2, con versiones exactas y `package-lock.json`. Node
20.19+ o 22.12+; Docker construye con Node 24. React y ReactDOM se empaquetan
localmente: no se descargan desde un CDN durante la consulta.

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

## Qué está migrado

- `App.jsx`: sesión demo, vista activa, resultado del análisis, plantilla y duración.
  La sesión demo es una comodidad local en `sessionStorage`, no autenticación.
- `AppShell.jsx`: barra lateral, menú móvil, cabecera y vistas.
- `OverviewView.jsx`, `DifficultyView.jsx`, `BandView.jsx`, `RehearsalView.jsx`:
  resumen, explorador familia → instrumento → pasaje, BandFit y plan de ensayo.
  «Actualizar análisis» y «Recalcular ensayo» recalculan sin abandonar la vista.
- `UploadWorkspace.jsx` y `useScoreAnalysis.js`: formulario, asignaciones,
  solicitudes, cancelación y descarte de respuestas anteriores.
- `labels.js`: textos en castellano de instrumentos, familias, findings, BandFit y
  ensayo; funciones puras con pruebas en `backend/test/frontend/labels.test.mjs`.
- `instrument-session.js`: modifica una copia temporal del XML; conserva el archivo
  seleccionado y la instrumentación no identificada cuando no hay confirmación.

`legacy-workspace.js` es el adaptador temporal para el visor completo, el diálogo
del pasaje con su audio y la búsqueda de vídeos. Sus nodos se declaran en
`index.html` dentro de `#legacy-nodes`; `AppShell` los mueve a la vista de análisis
y React nunca renderiza sus hijos. El adaptador ya no modifica vistas de React.

Queda una PR: visores, audio y vídeos. No se considera terminado el frontend React
hasta eliminar el adaptador. Las reglas del backend, PostgreSQL y el renderer de
audio mantienen su implementación actual.

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
