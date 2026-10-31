---
name: scoremaster-evaluation
description: Preparar benchmark, feedback experto y resultados experimentales de ScoreMasterAI; usar para comparar heurística, LLM e híbrido y documentar evidencia reproducible.
---

# Evaluación experimental

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md` y `backend/`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md` y `CONTRIBUTING.md`. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Lee `evaluation/README.md`, `evaluation/baseline.py`, `evaluation/campaign_report.py` y `docs/DIFICULTAD.md`.

## Procedimiento

- Distingue baseline de comportamiento, tests de regresión y benchmark etiquetado por expertos. El baseline legacy no es verdad musical; los candidatos a falsos positivos no son errores confirmados.
- Usa un manifiesto explícito de archivos con procedencia y licencia verificadas. No recorras automáticamente `test-scores/`: contiene partituras locales cuya presencia no autoriza publicación o uso en un dataset público.
- Define unidad de evaluación, escala, transformación, protocolo de etiquetado y tratamiento de desacuerdos antes de medir. La escala es de grados 1–6 (`docs/DIFICULTAD.md`).
- Separa particiones por obra o grupo de origen. No ajustes umbrales con el conjunto reservado para evaluación; registra configuración y versiones.
- Compara heurística, LLM independiente e híbrido bajo condiciones equivalentes. El LLM independiente no recibe el score heurístico. Identifica resultados demo/fake y no los presentes como evaluaciones de un modelo real.
- Mide MAE y Spearman para dificultad; precisión, recall y F1/F0.5 para criticidad; resolución correcta, abstención y falsos automáticos para instrumentos según el experimento. Explica denominadores, datos ausentes, muestras pequeñas y métricas no definidas.
- Asocia feedback a análisis, pasaje y versiones, recogiendo solo datos personales necesarios. Conserva dispersión entre expertos en lugar de ocultarla mediante una media.
- Genera tablas desde datos y scripts; no edites resultados manualmente ni inventes etiquetas, validación experta o cifras.

## Verificación y entrega

Comprueba `python -m evaluation.baseline` para reproducibilidad legacy; `--update` solo corresponde a una actualización deliberada y justificada de esa captura. Para un experimento nuevo proporciona comando, manifiesto, configuración, versiones y artefactos regenerables. En los informes distingue implementado, comprobado, limitaciones y futuro; evita afirmar superioridad del híbrido sin evidencia.
