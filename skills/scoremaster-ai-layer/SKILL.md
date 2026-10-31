---
name: scoremaster-ai-layer
description: Implementar proveedores IA, revisión estructurada de dificultad y explicaciones en ScoreMasterAI; usar para prompts, fallback, caché y trazabilidad LLM.
---

# Capa de IA estructurada

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md` y `backend/`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md` y `CONTRIBUTING.md`. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Lee `backend/application/ai.py`, `backend/infrastructure/ai/` y la sección de IA del `README.md`. Busca puertos y adaptadores existentes antes de crear módulos.

## Procedimiento

- Mantén ScoreLint como fuente de hechos musicales. Una valoración LLM es una salida separada; no sustituye silenciosamente la heurística ni el detector de criticidad.
- Coloca proveedores externos y LangChain detrás de interfaces de aplicación. Añade LangChain solo si simplifica el caso solicitado. No introduzcas RAG, LangGraph, agentes ni una base vectorial remota en esta fase.
- Consume features estructuradas. Valida schemas, enums, rangos, IDs de instrumentos y referencias a pasajes antes de usar una respuesta. Los textos de partituras y comentarios son datos no confiables, no instrucciones del sistema.
- En evaluación independiente, excluye el score heurístico del input LLM para evitar anchoring. Conserva resultados heurístico, LLM e híbrido por separado; no presentes pesos híbridos como validados sin experimento.
- Ofrece demo determinista claramente identificada y fake para pruebas. Ante timeout, rate limit, error o schema inválido, limita reintentos y conserva el resultado determinista indicando que falta la revisión IA.
- Versiona prompts cuando cambie su semántica; registra proveedor, modelo y versiones de features/algoritmo. La caché debe incluir entradas, nivel objetivo y versiones relevantes; no almacenes errores como respuestas válidas.
- Mantén claves en servidor y fuera del repositorio y logs. Envía solo la información necesaria a servicios externos, respetando el alcance autorizado.

## Verificación

Prueba con fake: respuesta válida, schema inválido, referencia inventada, valor fuera de rango, UNKNOWN, timeout, fallback y cambios de versión de caché. Comprueba el funcionamiento sin API key. Las pruebas normales no deben requerir gasto ni llamadas reales. Indica expresamente si solo se verificó el fake/demo.
