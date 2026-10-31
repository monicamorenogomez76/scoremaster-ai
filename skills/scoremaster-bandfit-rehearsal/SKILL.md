---
name: scoremaster-bandfit-rehearsal
description: Modificar compatibilidad de plantilla BandFit y planificación de ensayos de ScoreMasterAI; usar para cobertura instrumental, disponibilidad, prioridad y presupuesto de tiempo.
---

# BandFit y planificación de ensayos

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md`, `backend/` y `docs/IMPLEMENTATION_ROADMAP.md`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md`, `CONTRIBUTING.md` y el plan aprobado; este último resuelve las discrepancias entre especificaciones de evolución. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Inspecciona `backend/analyzers/band_fit.py`, `band_fit_by_measure.py` y `rehearsal_plan.py` dentro de `backend/analyzers/`, sus pruebas y `docs/IMPLEMENTATION_ROADMAP.md`.

## Procedimiento

- Compara identidades instrumentales coherentes con el parser. Distingue instrumento, parte independiente y número de intérpretes; una coincidencia de familia no garantiza cobertura.
- Calcula necesidades locales por compás o pasaje cuando existan datos. No afirmes independencia de voces ni simultaneidad de percusionistas sin evidencia suficiente.
- El ensayo es de conjunto: un pasaje común es el que varias partes tocan igual en estructura (misma línea en su tonalidad u octava, o mismo ritmo). Primero líneas comunes, después subsecciones de ensayo (`rehearsal_group`) y un tutti final; no planifiques por instrumento aislado. Consulta `docs/DIFFICULTY_CRITICALITY.md`.
- Separa dificultad de la prioridad para la plantilla disponible. Justifica cada bloque mediante pasajes existentes, findings y disponibilidad; presenta alternativas como recomendaciones, no reorquestación validada.
- Define la política de presupuesto y redondeo: minutos no negativos y suma de todos los bloques, incluidos calentamiento y transiciones, menor o igual al tiempo disponible. Contempla presupuestos cortos y ausencia de pasajes prioritarios.
- El baseline registra un plan legacy que puede exceder 15 minutos. Corrige el planificador con una regresión explícita, sin reescribir la captura histórica para ocultarlo.
- Si se añade IA al planificador, valida instrumentos, referencias y presupuesto en código y conserva un plan determinista cuando falle el proveedor.

## Verificación

Ejecuta `python -m pytest backend/test/test_band_fit.py backend/test/test_band_fit_by_measure.py backend/test/test_rehearsal_plan.py`. Añade casos de partes sin cubrir, instrumentos ambiguos y presupuesto limitado según el cambio. Verifica en la UI que cobertura y prioridades usan la misma plantilla que el análisis.
