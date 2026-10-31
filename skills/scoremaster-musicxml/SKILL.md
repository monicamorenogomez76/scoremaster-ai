---
name: scoremaster-musicxml
description: Modificar el parser MusicXML/MXL y la identificación instrumental de ScoreMasterAI; usar para metadatos, transposición, tiempos, aliases y confirmación de instrumentos.
---

# MusicXML e identidad instrumental

## Contexto y alcance

Localiza la raíz de ScoreMasterAI por `AGENTS.md` y `backend/`. Todas las rutas siguientes parten de esa raíz. Lee `AGENTS.md` y `CONTRIBUTING.md`. Comprueba el código actual: los documentos de propuesta no prueban que una función exista.

Trabaja únicamente en la petición activa. Antes de cambiar comportamiento, presenta objetivo, criterios de aceptación y un mapa breve de módulo, archivo, componente y cambio. Conserva los cambios locales ajenos. Explica las decisiones relevantes y actualiza solo la documentación afectada. Estas instrucciones no autorizan publicar, desplegar ni integrar cambios por sí solas.

## Archivos de referencia

Inspecciona `backend/parsers/musicxml_parser.py`, `backend/domain/models.py`, `backend/parsers/playback.py` y `backend/domain/instrument_catalog.py`. Sigue los consumidores en BandFit, dificultad y audio antes de alterar el modelo.

## Procedimiento

- Conserva nombre original, identidad canónica, variante, transposición y número de parte como conceptos distintos cuando evoluciones el modelo. No presupongas que esos campos ya existen.
- Prioriza metadatos estructurados disponibles y aliases específicos. Evita coincidencias por substring: English Horn no es Horn; Bass Clarinet no es clarinete soprano. No borres tokens de afinación al normalizar.
- Conserva UNKNOWN ante datos insuficientes. Una parte Voice no justifica adivinar su instrumento. La confirmación humana modifica la copia de sesión y no el archivo original.
- Distingue altura escrita y de concierto; documenta cuál utiliza cada consumidor. Preserva voces, acordes, silencios, ligaduras, offsets y unidad de pulso al extraer tiempos. Un acorde no equivale a varios ataques sucesivos.
- El resolver de instrumentos es determinista: no añadas embeddings ni un fallback LLM para resolver un alias sencillo.
- En entradas XML/MXL, revisa entidades externas, rutas de ZIP y límites de tamaño comprimido y expandido; conserva los límites vigentes y respuestas controladas ante archivos inválidos.

## Verificación

Añade fixtures sintéticos para el caso afectado y regresiones de instrumentos ambiguos, transposición o tiempos según corresponda. Ejecuta `python -m pytest backend/test/test_musicxml_parser.py` y las pruebas de consumidores afectados. Incluye `backend/test/test_playback.py` cuando cambien alturas o tiempos. Usa solo material con derechos claros para nuevas fixtures públicas.
