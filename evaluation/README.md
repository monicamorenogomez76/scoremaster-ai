# Baseline musical

`baseline-v1.json` registra el motor previo a su evolución, no una verdad musical.
Se puede reproducir desde la raíz con `python -m evaluation.baseline`.
Para regenerarlo intencionadamente: `python -m evaluation.baseline --update`.
No actualizarlo para ocultar regresiones. Se congelará el código legacy al evolucionar
el motor, de modo que este baseline siga reproducible sin imponer sus defectos al motor nuevo.

Los análisis usan el detector de pasajes críticos anterior (`critical_detector="legacy"`) y el
planificador congelado, para que la captura siga siendo la del motor previo.
El audio se compara con las claves de pista originales; `canonical_id` y `sound`, añadidos
con el resolver de instrumentos, no forman parte de esta captura legacy.

Incluye cinco MusicXML sintéticos ya versionados, diez casos de dominio generados,
nombres instrumentales y eventos de audio. La lista de archivos es explícita: nunca
recorre las partituras comerciales locales. No hay etiquetas humanas ni resultados LLM.

## Casos que requieren revisión

- Alias españoles/italianos: Clarinete, Clarinete bajo, Trompa, Corno inglés,
  Saxofón alto y Clarinetto. Sus salidas actuales se registran para comparar el resolver.
- Posibles críticos excesivos: escalas por grados conjuntos a 60/160, notas
  sostenidas en 8/16 compases y registros sostenidos. Son candidatos a revisión,
  no cinco falsos positivos confirmados por expertos.
- Posible sobreestimación: tempo rápido ajeno al fragmento (`fast-elsewhere`),
  registro aislado y notas repetidas. No se etiqueta subjetivamente su dificultad.
- `high_density.musicxml` con presupuesto 15 registra el plan previo, incluso
  si excede sus minutos: ese defecto debe corregirse en el planificador, no en la captura.

Los futuros expertos aportarán grados 1–6 y criticidad. La captura mantiene las
escalas legacy 1–5/0–5 explícitas. El dataset de benchmark será independiente de
estas regresiones y agrupará por obra para evitar leakage.
