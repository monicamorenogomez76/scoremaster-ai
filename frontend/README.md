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

- `UploadWorkspace.jsx`: formulario, asignaciones y estado accesible de carga/error.
- `useScoreAnalysis.js`: selección, solicitudes, cancelación y descarte de respuestas
  anteriores. Mantiene la plantilla inicial de una plaza por parte del flujo legacy.
- `instrument-session.js`: modifica una copia temporal del XML; conserva el archivo
  seleccionado y la instrumentación no identificada cuando no hay confirmación.
- `main.jsx`: monta una raíz React para la carga.
- `index.html` y `styles.css`: mantienen el diseño y la estructura de las vistas.

El [montaje parcial de React](https://react.dev/reference/react-dom/client/createRoot#rendering-a-page-partially-built-with-react)
permite esta transición. `legacy-workspace.js` es un adaptador temporal para
dashboard, navegación, plantilla, ensayo, vídeos y visores. React no manipula su
DOM y el adaptador no modifica el formulario gestionado por React. Los botones
de recalcular delegan sus solicitudes al controlador React.

Quedan dos PR: dashboard y después visores/audio. No se considera terminado el
frontend React hasta eliminar el adaptador y migrar esas vistas. Las reglas del
backend, PostgreSQL y el renderer de audio mantienen su implementación actual.

## Verificación

Compilar antes de ejecutar las pruebas Python que consultan `/`. Con Uvicorn en
8006 y Playwright/Chromium instalados según el README principal:

```sh
SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/react-upload.e2e.mjs
SCOREMASTER_URL=http://127.0.0.1:8006 PLAYWRIGHT_MODULE=/tmp/scoremaster-browser-tests/node_modules/playwright node backend/test/frontend/workflow.e2e.mjs
node --test backend/test/frontend/*.test.mjs
```

El recorrido React usa únicamente una partitura sintética; simula fallos 503,
respuestas no JSON y una respuesta tardía tras cancelar. El recorrido compartido
comprueba asignación, reinicio, móvil, pasaje completo y guía de reproducción.
