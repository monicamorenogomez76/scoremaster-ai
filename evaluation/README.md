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
escalas legacy 1–5/0–5 explícitas (`scale='legacy'`); la aplicación usa grados 1–6 e índice 0–10 desde el paso 13. El dataset de benchmark será independiente de
estas regresiones y agrupará por obra para evitar leakage.

# Informe de una campaña de valoración (paso 19)

Desde la raíz, con el JSON que se descarga en «Valoraciones» → Exportar:

```sh
python -m evaluation.campaign_report exportacion.json                       # tabla en pantalla
python -m evaluation.campaign_report exportacion.json --min-ratings 2 \
    --markdown informe.md --json informe.json                               # guarda ambos
python -m evaluation.campaign_report exportacion.json --level profesional --level docente
```

Protocolo, fijado antes de ver resultados:

- La unidad es el pasaje propuesto (una parte, 4–12 compases) con la predicción que ScoreLint guardó
  al crear la campaña; los músicos nunca la vieron.
- Dificultad de los músicos: mediana de sus grados 1–6. Se compara con el grado predicho (MAE, RMSE,
  sesgo, Spearman con rangos promedio, acierto exacto y a ±1 grado). Sesgo positivo: ScoreLint puntúa
  más difícil.
- Criticidad: mayoría de los evaluadores. Un empate queda sin veredicto, fuera de precisión, recall,
  F1 y F0.5, y se cuenta aparte. F0.5 pondera más la precisión porque interesa evitar falsos positivos.
- Los pasajes con menos valoraciones que `--min-ratings` (1 por defecto) quedan fuera y se cuentan.
  `--level` limita el informe a evaluadores con esa experiencia.
- El desacuerdo se informa (diferencia media entre dos evaluadores, rango medio y criticidad unánime)
  en lugar de ocultarlo con la mediana. La concordancia más allá del azar se mide con el alfa de
  Krippendorff, que admite cualquier número de evaluadores por pasaje: ordinal para el grado y nominal
  para la criticidad. Con α ≥ 0.80 la referencia es fiable; entre 0.67 y 0.80, provisional.
- Cada método se mide también como un evaluador más: su alfa con los músicos junto al de los músicos
  solos, en los mismos pasajes (dos o más valoraciones y predicción del método).
- El alfa, el MAE y el Spearman de cada método llevan un intervalo de confianza del 95 % por bootstrap
  de pasajes (1000 remuestreos, percentiles, semilla 19), de modo que el informe sigue siendo reproducible. Los desgloses por obra permiten ver si una sola obra domina.
- Una métrica sin denominador, o Spearman con menos de tres pasajes o sin variación, aparece como «—».
- El informe registra su versión, el sha256 de la exportación y las versiones de escala, detector y
  muestra de las predicciones. Con la misma exportación produce siempre el mismo resultado.

No se calibra nada con estos datos: si más adelante se ajustan umbrales, la partición debe hacerse por
obra para evitar leakage. Las exportaciones contienen valoraciones de personas reales: guárdalas en `evaluation/exports/`, que Git ignora.

## Métodos comparados (paso 24)

| Método | Qué es |
|---|---|
| A · Heurística (ScoreLint) | La predicción guardada al crear la campaña |
| B · LLM | La valoración independiente de «Valorar con IA» (paso 22), una fila por proveedor, modelo y prompt |
| C · Híbrido | **Regla preregistrada el 2026-10-13, antes de recibir valoraciones**: grado = media de A y B redondeando hacia arriba los medios puntos; crítico solo si A y B coinciden. No se ajusta a los datos |
| D · Músicos | La referencia: mediana de sus grados y criticidad por mayoría |

El informe da dos tablas: cada método sobre todos los pasajes que predijo y, la comparación justa, todos
sobre **los mismos pasajes** (los que tienen predicción de todos los métodos).

Al final, la sección «Grado de la obra: ScoreLint frente a las editoriales» compara el grado de ScoreLint de
cada obra con la media de los grados publicados que registró la directora (diferencia, MAE, sesgo y
Spearman con tres obras o más). Sin grados registrados, lo dice.
