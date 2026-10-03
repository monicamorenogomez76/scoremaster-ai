> Borrador de changelog: usar solo cuando cada funcionalidad esté implementada; consultar el [plan aprobado](../IMPLEMENTATION_ROADMAP.md).

# Entrada sugerida para CHANGE / CHANGELOG

Usar SOLO cuando la funcionalidad esté implementada.

## Unreleased

### Added
- Canonical multilingual instrument resolution with confidence and fallback.
- Semantic instrument matching and optional LLM resolution.
- Target-level-aware musical difficulty assessment.
- Optional LLM-based difficulty review with structured output.
- Human expert feedback foundation.
- AI prompt/model/features version tracking.
- Evidence and confidence information for musical assessments.

### Changed
- Difficulty and critical passage detection are now separate concepts.
- Critical passages are no longer forced from a fixed Top-N.
- Rhythm/tempo interaction uses effective note/event rate where applicable.
- Criticality considers absolute difficulty, relative prominence and persistence.
- LLM failures fall back to deterministic ScoreLint analysis.

### Fixed
- Reduced false critical-passage positives in easy scores.
- Improved recognition of instrument names across languages and abbreviations.
- Prevented generic `horn` matching from incorrectly absorbing `English Horn`.

### Planned / Optional
- Sample-based realistic audio renderer.
- Extended instrument-specific difficulty profiles.
- Statistical calibration from the expert-labelled dataset.
