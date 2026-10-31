---
name: scoremaster-scorelint
description: Desarrollar métricas, reglas, dificultad y criticidad deterministas de ScoreLint en ScoreMasterAI; usar para calibración musical y regresiones del motor.
---

# Motor ScoreLint

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md` y `backend/`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md` y `CONTRIBUTING.md`. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Lee `docs/DIFICULTAD.md`, `evaluation/README.md` y los módulos afectados de `backend/analyzers/`, `backend/rules/` y `backend/domain/models.py`.

## Procedimiento

- Define la magnitud musical, unidad, ventana temporal y evidencia antes del algoritmo. Separa extracción de datos, métricas, políticas de dificultad y findings; mantén el dominio independiente de proveedores IA.
- Distingue dificultad técnica, criticidad contextual y prioridad de ensayo. Al implementar el detector independiente, permite cero críticos; pertenecer al Top N no basta.
- Comprueba la escala real de API y UI. El plan prevé grados enteros 1–6 e índice interno 0–10; el baseline conserva escalas legacy 1–5/0–5. No cambies etiquetas sin transformar y versionar el contrato completo.
- Usa tempo local y unidad de pulso; evita penalizar dos veces velocidad y densidad. Distingue ataques de notas ligadas y simultáneas, y picos aislados de registros sostenidos.
- Trata SL005 actual como continuidad por compases, no fatiga fisiológica. SL002 identifica registro agudo. Comprueba el catálogo antes de asignar códigos nuevos.
- No ajustes pesos para arreglar una sola obra. Explica la motivación musical y compara casos sencillos, difíciles y limítrofes. Los umbrales de las especificaciones son propuestas, no valores validados.

## Verificación

Construye casos sintéticos con resultados justificables y prueba límites. Ejecuta los tests musicales afectados con `python -m pytest` y `python -m evaluation.baseline`. No regeneres el baseline para hacer desaparecer una regresión; si evoluciona el motor, conserva una comparación reproducible con el legacy. Informa de los cambios esperados y de las limitaciones musicales.
