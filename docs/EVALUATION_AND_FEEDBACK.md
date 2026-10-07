> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Evaluation and Expert Feedback

## Implementado: campañas de valoración (pasos 16–18, decisiones de la autora, 2026-10-07)

- **Campaña** de la directora con título e instrucciones; estados borrador → abierta → cerrada.
- **Pasajes propuestos** (`backend/analyzers/evaluation_sample.py`): muestra reproducible de sus obras,
  ~40 % críticos y ~60 % no críticos repartidos por grados y obras; cada pasaje es una parte de
  4–12 compases y guarda la **predicción de ScoreLint para ese fragmento** (grado 1–6, índice 0–10,
  crítico, hallazgos y versiones de escala, detector y muestra). El orden se baraja de forma
  determinista para que los críticos no se agrupen. En borrador se pueden quitar pasajes.
- **Invitación por email**: el músico entra con su cuenta y ve la campaña (no en borrador); indica
  nivel de experiencia (estudiante, amateur, profesional, docente) e instrumento principal; puede
  abrir la obra completa; **nunca ve la predicción**.
- **Valoración**: dificultad 1–6 (misma rúbrica), crítico sí/no, prioridad de ensayo 1–5 y comentario
  opcional; editable mientras la campaña está abierta.
- **Exportación** para el paso 19: pasajes con su predicción y todas las valoraciones, con los
  evaluadores como «Evaluador n» (sin email ni nombre).
- **Pantalla de la directora** (menú «Valoraciones», `frontend/src/EvaluationView.jsx`): crear la campaña
  con sus obras analizadas y el número de pasajes (avisa si las obras dan menos), revisar cada pasaje con
  la predicción de ScoreLint, verlo y escucharlo en la partitura, quitarlo en borrador, invitar músicos
  por email y ver su avance, abrir (con confirmación), cerrar y exportar los resultados en JSON.
- **Pantalla del músico** (el mismo menú, «Te han invitado a valorar»): indica su experiencia e
  instrumento, y valora los pasajes uno a uno tras verlos y escucharlos (o ver su parte en toda la
  obra), con la rúbrica de grados de `docs/DIFFICULTY_CRITICALITY.md`; cada valoración se guarda al
  pasar al siguiente y puede seguir otro día. Con la campaña cerrada solo puede consultarlas.
- Datos mínimos: email de la cuenta, nivel e instrumento. API: `/evaluations` (ver
  `backend/app/evaluation_routes.py`); tablas de la migración `0009_evaluations`.

## 1. Objetivo

No ajustar ScoreLint únicamente mediante intuición.

Crear un benchmark que permita evaluar:

1. instrument normalization;
2. difficulty estimation;
3. critical passage detection;
4. hybrid AI contribution.

---

# 2. Expert feedback

Permitir que músicos/directores valoren pasajes.

Mínimo:

```text
HumanDifficulty
Critical: yes/no
```

Recomendado:

```text
RehearsalPriority
OptionalComment
ExperienceLevel
Instrument
```

Evitar pedir información personal no necesaria.

---

# 3. Difficulty scale

Elegir UNA escala en UI y dataset.

Recomendación para precisión:

```text
1..10
```

o, si se prefiere simplicidad:

```text
1..5
```

No mezclar escalas sin transformación explícita.

---

# 4. Dataset inicial

Objetivo inicial:

```text
50–80 passages
```

Ideal:
- fáciles;
- medios;
- difíciles;
- críticos claros;
- casos ambiguos.

Si es posible:
- 3 valoraciones humanas por pasaje.

Incluir:
- varias familias instrumentales;
- distintos tempi;
- distintos registros;
- ritmos variados;
- pasajes con y sin descanso.

---

# 5. Evitar leakage

Si posteriormente se entrena/calibra un modelo:

No repartir fragmentos de la misma obra arbitrariamente entre train/test si eso facilita memorizar características de la obra.

Preferir split por:
- score/work;
- o source group.

---

# 6. Experimentos

## A — Heuristic

```text
features -> heuristicDifficulty
```

## B — LLM independent

```text
features -> LLM
```

El LLM no recibe heuristicDifficulty.

## C — Hybrid

```text
heuristic + llm -> hybrid
```

## D — Expert

Ground truth mediante agregación humana.

---

# 7. Métricas Difficulty

Recomendadas:
- MAE;
- Spearman correlation;
- opcionalmente RMSE;
- error por familia instrumental;
- error por nivel.

Si hay múltiples expertos:
- reportar dispersión;
- considerar agreement/inter-rater statistic si el tamaño de muestra lo permite.

---

# 8. Métricas Criticality

Usar:
- Precision;
- Recall;
- F1;
- F0.5.

En este proyecto interesa especialmente reducir falsos positivos.

Por tanto F0.5 es útil al ponderar más Precision.

Una posible política:

```text
buscar primero una precisión mínima aceptable
y después maximizar recall
```

No fijar el valor final antes de observar datos.

---

# 9. Instrument Resolution Metrics

Medir:
- accuracy;
- unresolved rate;
- false auto-resolution rate;
- semantic top-3 accuracy;
- accuracy por idioma;
- accuracy por source.

Comparar:

```text
Alias only
Semantic
LLM
Hybrid
```

---

# 10. Feedback data model

Conceptualmente:

```json
{
  "analysisId": "...",
  "passageId": "...",
  "instrumentId": "...",
  "humanDifficulty": 5,
  "critical": false,
  "rehearsalPriority": 4,
  "comment": "...",
  "createdAt": "..."
}
```

Adaptar al modelo existente.

No almacenar más información de usuario de la necesaria.

---

# 11. Versioning

Cada evaluación automática debe poder asociarse con:

```text
algorithmVersion
featuresVersion
promptVersion
provider/model
```

Sin ello no se pueden comparar experimentos de forma reproducible.

---

# 12. Golden Dataset

Crear una carpeta o recurso equivalente:

```text
evaluation/
  manifest.*
  labels.*
  README.md
```

No incluir partituras protegidas si la licencia no lo permite.

Puede contener:
- partituras sintéticas;
- obras propias;
- dominio público;
- features preextraídas si conviene.

---

# 13. Informe TFM

Generar tabla:

```text
Method      MAE    Spearman    Critical Precision    Recall    F0.5
Heuristic   ...
LLM         ...
Hybrid      ...
```

Los valores deben provenir de la evaluación real.

Nunca inventar resultados.
