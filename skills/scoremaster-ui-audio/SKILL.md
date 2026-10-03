---
name: scoremaster-ui-audio
description: Editar la interfaz, el visor de partituras y la reproducción de ScoreMasterAI; usar para dashboard, navegación, accesibilidad, OpenSheetMusicDisplay y audio.
---

# Interfaz, visor y audio

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md`, `backend/` y `docs/IMPLEMENTATION_ROADMAP.md`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md`, `CONTRIBUTING.md` y el plan aprobado; este último resuelve las discrepancias entre especificaciones de evolución. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes para la defensa del TFM y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Revisa `backend/app/static/index.html`, `score-view.js`, `playback.js` y `playback-guide.js` en esa carpeta; `backend/parsers/playback.py`, `README.md`, `docs/SCORE_VIEWER.md` y `docs/REALISTIC_AUDIO.md` según el cambio.

## Procedimiento

- Trabaja sobre la interfaz real HTML/JavaScript servida por FastAPI. React aparece en la propuesta inicial: no migres el frontend por una edición de UX.
- Explica dificultad, adecuación a la banda y ensayo en lenguaje de músico. Mantén escalas visibles, evidencias accesibles y modo demo reconocible; no representes una sesión local como autenticación real.
- Conserva el archivo original durante la sesión y aplica asignaciones instrumentales a una copia. Nueva partitura y cambio de archivo deben limpiar análisis, visor y audio anteriores.
- Respeta el ciclo de audio: carga cancelable, reproducción, pausa, detener y cierre. Evita eventos duplicados y callbacks obsoletos al cambiar de obra o cerrar el visor.
- Conserva altura de concierto, cambios de tempo, acordes y ligaduras del reproductor. Muestra defaults y timbres aproximados. No reescribas el motor analítico para cambiar samples.
- Mantén claves de YouTube en servidor. La carga de samples y del visor puede necesitar red; la partitura no debe enviarse al proveedor de sonidos.
- Verifica teclado, foco visible, controles con nombre accesible, móvil, zoom y ausencia de desbordamiento. Los valores importantes deben ser legibles sin depender solo del color.

## Verificación

Ejecuta `node --test backend/test/frontend/*.test.mjs`. Para cambios de flujo usa `backend/test/frontend/workflow.e2e.mjs` con servidor local y las instrucciones de `README.md`; revisa escritorio y móvil. Para eventos musicales añade `python -m pytest backend/test/test_playback.py`. Informa de las comprobaciones visuales o auditivas realmente hechas y de las bloqueadas por red o entorno.
