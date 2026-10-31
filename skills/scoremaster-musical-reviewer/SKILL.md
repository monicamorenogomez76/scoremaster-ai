---
name: scoremaster-musical-reviewer
description: Revisar la validez musical de análisis, reglas y recomendaciones de ScoreMasterAI para banda; usar al evaluar dificultad instrumental, criticidad, orquestación y prioridades de ensayo con evidencias de partitura. No sustituye la implementación del parser ni la evaluación humana del TFM.
---

# Revisión musical de ScoreMasterAI

## Alcance y contexto

Aplica criterio de análisis musical y dirección de banda a la pregunta concreta. Revisa resultados y supuestos; no cambies algoritmos ni umbrales por una petición de opinión. Si se solicita implementación, presenta primero el cambio musical y los casos de regresión necesarios.

Localiza el repositorio por `AGENTS.md` y `backend/`. Lee las instrucciones del proyecto. Consulta `docs/DIFICULTAD.md` o `evaluation/README.md` solo según el caso. Verifica en código y datos las funciones realmente disponibles.

## Evidencias antes de conclusiones

- Identifica obra, versión o hash, parte, rango de compases y nivel objetivo disponible. Distingue numeración escrita de índice interno, anacrusas y compases repetidos cuando afecten a la localización.
- Usa MusicXML y datos extraídos para hechos observables. Revisa el fragmento original si el modelo interno ha descartado información necesaria; si no está disponible, declara la limitación.
- Separa hecho medido, interpretación musical e hipótesis pendiente de validación. Un número de confianza generado por IA no es una probabilidad calibrada.
- Distingue altura escrita y de concierto, instrumento transpositor y variante. Indica la convención de octavas cuando cites notas. No deduzcas instrumento, digitación, articulación o respiración ausentes en los datos.
- Comprueba tempo local y figura de referencia, métrica, voces, acordes, ligaduras, silencios y duración real de la ventana antes de interpretar densidad o continuidad.

## Criterios de revisión

Selecciona las dimensiones relevantes sin convertir esta lista en una puntuación automática:

| Dimensión | Pregunta musical | Evidencia o límite |
|---|---|---|
| Ritmo y tempo | ¿La dificultad procede de velocidad, subdivisión, síncopa, cambios métricos o independencia de voces? | Ataques y patrones locales; no contar alturas simultáneas como ataques sucesivos ni duplicar ritmo y tempo. |
| Tesitura y registro | ¿Es una nota extrema aislada o una exposición sostenida para ese instrumento y nivel? | Alturas, duración y contexto; rango posible y registro cómodo no son equivalentes. |
| Intervalos y técnica | ¿Los saltos y cambios de registro crean una exigencia real en este contexto? | Secuencia, dirección, velocidad y articulación; los semitonos por sí solos no describen digitación o ejecución. |
| Articulación | ¿Hay patrones, cambios o ataques que condicionan la ejecución? | Marcas explícitas y tempo; distingue ligadura de prolongación y de fraseo. |
| Continuidad y descanso | ¿Qué oportunidades de descanso están escritas y cuánto dura la actividad? | Duración, silencios, registro y dinámica cuando existan; la continuidad no demuestra fatiga fisiológica. |
| Coordinación del conjunto | ¿Hay entradas expuestas, líneas independientes o coordinación rítmica relevante? | Relación entre partes; no afirmar protagonismo por volumen de notas o nombre del instrumento. |
| Percusión | ¿Las líneas simultáneas y cambios de instrumento permiten estimar necesidades de intérpretes? | Distribución y tiempos disponibles; partes, instrumentos e intérpretes no son cantidades intercambiables. |

Para madera, metal y percusión, formula hipótesis específicas apoyadas en datos. No asignes rangos cómodos universales: dependen de instrumento, variante, nivel y contexto. Si un límite técnico concreto requiere respaldo, consulta fuentes primarias o pedagógicas identificables y cita edición o URL; no inventes bibliografía ni autoridad experta.

## Dificultad, criticidad y ensayo

- Distingue dificultad técnica del pasaje, criticidad en su contexto y prioridad para la plantilla y el tiempo disponibles. Permite una obra sin pasajes críticos.
- No confundas grado editorial estimado con nivel de los intérpretes. Consulta la escala implementada: el plan prevé grados 1–6 e índice interno 0–10, mientras el baseline conserva escalas legacy. No conviertas valores sin una transformación explícita.
- Contrasta el hallazgo con pasajes cercanos y un caso sencillo de control. Antes de recomendar un cambio de regla, describe al menos un contraejemplo donde ese cambio podría fallar.
- Formula sugerencias de ensayo vinculadas a la causa observada, a partes y compases concretos. No inventes tempos óptimos, duraciones, ausencias o capacidades del grupo. Los bloques temporales deben caber en el presupuesto si se pide un plan.
- Las alternativas de cobertura instrumental son propuestas que requieren revisión musical; no presentes sustituciones de timbre, transposición o tesitura como reorquestación automáticamente válida.

## Entrega de la revisión

Da primero una conclusión breve. Para cada observación relevante indica parte y compases, evidencia, interpretación, efecto práctico y datos faltantes. Cuando se revise una regla, añade su posible falso positivo o negativo y el caso sintético que permitiría comprobarlo.

Una revisión realizada con esta skill es una valoración asistida, no una etiqueta aportada por un músico experto. No incorpores sus conclusiones como ground truth del benchmark ni atribuyas validación humana inexistente. Mantén separados resultados heurísticos, revisión IA y feedback humano; en experimentos de revisión independiente evita mostrar al LLM el score heurístico inicial.

Para evaluar casos, utiliza partituras sintéticas o material autorizado. La presencia de una partitura comercial en `test-scores/` no autoriza redistribuirla ni incorporarla al dataset público.
