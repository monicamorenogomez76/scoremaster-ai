# Dificultad y pasajes críticos

ScoreLint calcula la dificultad de forma determinista: el mismo archivo da siempre el mismo resultado. La IA solo
explica ese resultado. No es una certificación oficial.

Son tres preguntas distintas:

- **Dificultad:** ¿qué exige la obra, cada familia y cada parte a quien la toca?
- **Criticidad:** ¿hay pasajes con evidencia suficiente para considerarlos especialmente problemáticos? Una obra
  puede no tener ninguno.
- **Prioridad de ensayo:** ¿cuánto tiempo merece cada pasaje, según la banda, la revisión del último ensayo y el
  concierto?

## Escala

El grado va de 1 a 6 y se alinea con la escala *Grade 1–6* que usan la mayoría de editoriales de música para banda.
La equivalencia es orientativa, porque no hay una escala única entre editoriales.

| Grado | Equivale a | Rúbrica |
|---|---|---|
| 1 Muy fácil | Grade 1 | Primer año de instrumento: negras, blancas y redondas en compases simples, con tesitura reducida |
| 2 Fácil | Grade 2 | Unos dos años de práctica: corcheas, puntillos, síncopas y tresillos sencillos, primeros compases compuestos |
| 3 Intermedio | Grade 3 | Tres o cuatro años: síncopas frecuentes, cambios de compás y tesitura media o amplia |
| 4 Intermedio avanzado | Grade 4 | Cuatro a seis años: ritmos exigentes, tonalidades y compases menos habituales, pasajes técnicos |
| 5 Avanzado | Grade 5 | Siete a nueve años: ritmos muy exigentes, compases cambiantes o asimétricos, toda la tesitura |
| 6 Profesional | Grade 6 | Nivel profesional: extremadamente difícil en todos los aspectos |

## Cómo se calcula el grado

Cada criterio de las guías de graduación da un grado mínimo, y **una parte tiene el grado de su criterio más
exigente** (`backend/analyzers/rubric_grade.py`, con los criterios como datos en `backend/domain/grade_rubric.py`).

| Fuente | Uso |
|---|---|
| *Táboa de niveis de dificultade*, Federación Galega de Bandas de Música | Primera referencia: compases, armaduras, tempos, dinámicas, articulación, grupos irregulares y tesituras por instrumento |
| *American Band College Music Grading Chart* | Lo que la tabla gallega no trae: duración de la obra, número de cambios de tonalidad y de compás, y notas de final de curso del grado 1 |
| *FJH Music Company, Series Guidelines* | Afina los grados bajos |

Los documentos son de sus editores; en el repositorio solo están sus criterios.

- **De la obra:** armadura de concierto, compás, cambios de tonalidad y de compás, tempo marcado, duración y
  dinámicas.
- **De cada parte:** tesitura escrita de su instrumento, figura más breve, tresillos y otros grupos irregulares,
  síncopas, articulaciones y adornos.
- **Uso limitado:** un rasgo de una parte solo cuenta si aparece en al menos el 5 % de sus compases con notas y en más
  de un compás. Unas pocas notas de final de curso (hasta el 5 % de la parte) no suben el grado.
- **Familias y obra:** cada familia toma el percentil 80 de sus partes. La obra toma el máximo entre los criterios de
  toda la obra y las familias de viento madera, viento metal y cuerda. La percusión y la sección rítmica se muestran
  aparte.

Además, un **índice técnico** de 0 a 10 por dimensión (ritmo, tempo, tesitura, intervalos, resistencia…) sirve para
localizar los pasajes críticos y para las explicaciones.

## Grados de las obras de la demo

| Obra | Grado |
|---|---|
| Coral para principiantes | 2 |
| Marcha de la plaza | 4 |
| Andante y danza | 4 |
| Pasodoble de las fiestas (para subir) | 4 |

## Pasajes críticos

`backend/analyzers/criticality.py`. Un compás es candidato si:

- su puntuación local, la suma de los pesos de las reglas que lo marcan, llega a 5;
- o está en el percentil 85 de su parte y supera en 2 la mediana de los cuatro compases a cada lado;
- o se toca a 8 notas por segundo o más al tempo escrito.

Los candidatos seguidos forman un núcleo, que necesita al menos 4 tiempos y 2 reglas distintas, o solo la señal de
velocidad. El pasaje se amplía hasta las frases completas que toca, así que nunca corta una frase.

## Grados publicados

En la pestaña Dificultad se puede registrar **a mano** el grado que publica una editorial o un catálogo, con su
fuente. La aplicación no lo busca ni se lo pide a la IA, que podría inventarlo.

| Escala publicada | Equivalencia |
|---|---|
| Grade 0,5 a 6 | El mismo número, con sus medios grados; Grade 0,5 cuenta como 1 |
| J.W. Pepper | VE = 1, E = 2, ME = 3, M = 4, MA = 5, A = 6 |

Varias fuentes de una obra se promedian. El informe de una campaña (`evaluation/campaign_report.py`) compara obra a
obra el grado de ScoreLint con esa media.
