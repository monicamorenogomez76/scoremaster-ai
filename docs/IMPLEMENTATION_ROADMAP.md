# Plan aprobado y estado de implementación

## Decisiones que prevalecen

- PostgreSQL en desarrollo y producción; SQLAlchemy, Alembic y repositorios independientes del dominio.
- Grados visibles enteros 1–6 y rúbrica documentada, alineada desde 2026-10-13 con la escala Grade 1–6 de las editoriales como equivalencia orientativa, sin afirmar certificación oficial. Índice técnico interno 0–10; transformación explícita. Integrado en el paso 13: índice = 2 × puntuación anterior, seis tramos iguales y `scale` en el resultado; el baseline conserva 1–5/0–5. Desde difficulty-v3 (2026-10-25) el grado sigue las guías de grados de las editoriales (American Band College como base, FJH para afinar, UIL solo como confirmación) y el índice queda como medida técnica.
- Nivel objetivo por defecto intermedio, separado del grado editorial estimado.
- Separar Difficulty, Criticality y RehearsalPriority. Un análisis puede devolver cero críticos.
- Los ensayos son de conjunto: un pasaje común es el que varias partes tocan igual en estructura —misma línea (mismo ritmo e intervalos, cada una en su tonalidad u octava) o mismo ritmo—, aunque sean de familias distintas. En cada pasaje se ensaya primero cada línea común, después las subsecciones con lo que queda (flautas, dobles cañas, clarinetes, saxofones, metales agudos, graves —con fagot, clarinete bajo y saxo barítono—, percusión, cuerda y rítmica) y al final un tutti para juntar (decisiones del 2026-10-04).
- Primera entrega: base musical fiable. Después revisión estructurada LLM y evaluación híbrida. Asistente conversacional solo con evidencias validadas (partes, compases, hallazgos, plan y diario) y demo identificada sin API key; sin RAG ni agentes autónomos (decisión del 2026-10-04).
- Persistir resultados estructurados y feedback. El MusicXML original se guarda privado de su usuario y se borra con la obra o la cuenta; no se guardan bancos de audio (decisión del 2026-10-04).
- Cuentas con email y contraseña (Google opcional), sesiones en servidor y CSRF; cada dato pertenece a un usuario y se autoriza en el servidor (decisión del 2026-10-04).
- Un objetivo por PR, pruebas y documentación. Integración secuencial mediante squash.

## Baseline integrado

Las PR #11–#16 están integradas. La PR #5 se cerró porque su densidad rítmica y agrupación ya estaban incorporadas. Comprobaciones: 62 pruebas Python, 5 pruebas Node y recorrido Playwright sobre carga, instrumentos, visor, reinicio, móvil y pasajes.

PostgreSQL local está integrado mediante la PR #19. El repositorio y las migraciones están integrados en la PR #21. El guardado desde la API está integrado en la PR #22; todavía no existe proveedor LLM. El audio actual ya usa muestras General MIDI para instrumentos afinados y síntesis para percusión. La resistencia actual es una aproximación por compases. Los hallazgos se agrupan como críticos, pendiente del detector separado.

La corrección del audio del clarinete, el pasaje completo y los controles compartidos están integrados en la PR #20. Las siguientes PR retoman el plan musical y de persistencia.

## Entregas

Los números 01–25 identifican pasos del plan, no números de GitHub. Los pasos 04 y 05 están integrados en las PR #21 y #22. La transición a React está integrada (PR #23, #25 y #26) y GitHub Actions valida cada PR antes del paso 06.

| Entrega | Objetivo | Estado |
|---|---|---|
| 01 | Especificación consolidada | Integrada: PR #17 |
| 02 | Baseline reproducible | Integrada: PR #18; 15 casos, 10 nombres y audio |
| 03 | PostgreSQL en desarrollo | Integrado en PR #19: Compose, healthcheck y volumen |
| 04 | Migraciones y repositorio de análisis | Integrado: PR #21; SQLAlchemy, Alembic y pruebas PostgreSQL |
| 05 | Guardado desde el análisis | Integrado: PR #22; ID, resultados y configuración persistidos |
| 06 | Catálogo canónico | Integrado: PR #28 |
| 07 | Metadatos del parser | Integrado: PR #29 |
| 08 | Resolver determinista | Integrado: resolver (PR #30), dificultad (PR #31), sección rítmica (PR #32) y timbre (PR #33); BandFit con el paso 09 |
| 09 | Confirmación humana | Integrado: PR #42; confirmación en «Mi banda» y BandFit por instrumento |
| 10 | Tiempos y ataques musicales | Integrado: PR #48; acordes, ligaduras, voces y adornos |
| 11 | Características locales | Fuera de la entrega: las dimensiones actuales bastan para la evaluación |
| 12 | Políticas de dificultad | Fuera de la entrega: los tramos se calibrarán con las valoraciones de los músicos |
| 13 | Grados 1–6 | Integrado: PR #49 |
| 14 | Detector de criticidad | Integrado: frases (PR #40), detector con señal de velocidad (PR #41) y cadencias armónicas (PR #43) |
| 15 | Prioridad, pasajes comunes y presupuesto de ensayo de conjunto | Integrado: PR #37, calendario (PR #38) y similitud de estructura (PR #39) |
| 16 | Evidencias en interfaz | Integrado: campañas con la predicción de cada pasaje (PR #70, #74) |
| 17 | Persistencia de feedback | Integrado: PR #70 (migración 0009) |
| 18 | Formulario de valoración | Integrado: PR #76 |
| 19 | Herramienta de evaluación | Integrado: informe de una campaña exportada con MAE, Spearman, precisión, recall, F0.5 y acuerdo entre evaluadores (PR #80) |
| 20 | Puerto IA y fake/demo | Integrado: PR #77 (explicar la dificultad) y #78 (explicar el ensayo) |
| 21 | Adaptador LangChain | Integrado: Gemini con salida estructurada y respaldo a la demo (PR #79, #81); verificado en Render con `gemini-3.8-flash` (2026-10-13) |
| 22 | Revisión independiente | Integrado: método B, Gemini valora cada pasaje de la campaña con medidas y notas, sin la predicción de ScoreLint (PR #84, #86) |
| 23 | Caché y trazabilidad | Integrado: explicaciones válidas guardadas por evidencias, proveedor, modelo y versiones; valoraciones del método B guardadas con lo enviado (PR #87) |
| 24 | Comparación experimental | Integrado: híbrido C preregistrado el 2026-10-13 y comparación de los métodos sobre los mismos pasajes (PR #90); grado de cada obra frente al de las editoriales (PR #105). Resultados cuando respondan los músicos |
| 25 | Estrategia híbrida experimental | Fuera de la entrega: el híbrido preregistrado (paso 24) no se ajusta a los datos |

## Ampliación aprobada (2026-10-04)

Plan detallado: cuentas, biblioteca, sustitutos, conciertos y diario, asistente con evidencias,
nivel por sección y coordinación del conjunto. Una PR por fase, con TDD.

| Fase | Objetivo | Estado |
|---|---|---|
| A1 | Cuentas y sesión (email/contraseña, Google opcional, CSRF, cabeceras, límites de subida) | Integrado: PR #45 |
| A2 | Biblioteca de obras y banda por usuario (MusicXML privado y borrable) | Integrado: PR #46 |
| A3 | Sustitutos de instrumento (tabla revisable, tesitura y músicos libres) | Futuro |
| A4 | Conciertos y calendario de ensayos con varias obras | Integrado: PR #58–#61 y #65 |
| A5 | Diario de ensayos (pendiente/resuelto, notas y propuestas confirmadas) | Integrado: revisión por bloque y replanificación (PR #58–#61) |
| A6 | Asistente conversacional con evidencias (demo y proveedor real) | En parte: explicaciones de la dificultad y del plan (pasos 20–21); la pregunta libre queda opcional |
| A7 | Nivel por sección en la banda | Integrado: PR #63–#64 (varias bandas con plantilla fija); aún no lo usa el planificador |
| A8 | Dificultad de coordinación del conjunto | Futuro |

## Orden de trabajo acordado (2026-10-05)

Se priorizan la IA y la evaluación experimental, obligatorias para el TFM, sobre la ampliación:

1. Paso 10: la base de las métricas se corrige antes de medir.
2. Paso 13 (y 11–12 si lo requiere): escala fijada antes de pedir valoraciones.
3. Paso 20: puerto IA y demo identificada sin API key.
4. Pasos 16–18: evidencias y formulario; los músicos necesitan días para responder.
5. Pasos 19 y 21–24: evaluación, adaptador LLM y comparación.

Las fases A3–A8 y el paso 25 se abordan solo si queda margen tras el paso 24.

## Propuesta de interfaz (2026-10-05)

Navegación propuesta: Resumen · Repertorio · Mi banda · Ensayos · Asistente IA · Configuración,
con blanco frío, grafito y azul eléctrico (sustituidos el 2026-10-26 por la identidad «Sala de conciertos»,
más abajo). Un ensayo puede trabajar varias obras y cada bloque de
su agenda indica la obra que se trabaja.

| Fase | Objetivo | Estado |
|---|---|---|
| F1 | Estado de preparación, prioridades, Resumen, Repertorio y detalle de obra | Integrado: PR #51 y #52 |
| F2a | Ensayos guardados: varias obras, agenda por bloques editable y «Ensayo de hoy»; Configuración básica | Integrado: PR #53–#57; Configuración con tamaño del texto y tema (PR #100) |
| F2b | Asistente IA (paso 20): conversación sobre el ensayo y explicación del plan, con modo demo identificado; el panel solo vuelve con lo que aporte la IA | Explicación del plan integrada («¿Por qué este plan?», PR #78); la conversación queda opcional |
| — | Evaluación (pasos 16–18) | Integrado: PR #70, #74 y #76 |
| C1–C4 | Calendario de conciertos (2026-10-06): programa, patrón semanal, serie por fases hasta el ensayo general, revisión por bloque y replanificación | Integrado: PR #58–#62 y #65 (navegación a los pasajes y siguiente paso en el Resumen) |
| F3 | Observaciones de ensayo y cierre: «Prioridades por sección» con las notas del último ensayo | Adelantado en C4: lo pendiente de la última revisión |

## Despliegue adelantado (2026-10-07)

Para que los músicos valoren con cuenta propia, la aplicación se publica en Render antes de la
evaluación (plan gratuito): ver [DEPLOYMENT.md](DEPLOYMENT.md).

## Plan de cierre (2026-10-13 – 2026-11-07)

Entrega prevista el 7 de noviembre; desde el 2026-10-28 no hay plazo fijo y se entrega cuando el trabajo se dé por cerrado. Decisiones: híbrido C preregistrado y obras de demostración propias.

| # | PR del plan | Prioridad | Estado |
|---|---|---|---|
| 1 | Copia y restauración de la base de Render | Imprescindible | Integrado: PR #88 y #91; copia real verificada el 2026-10-14 |
| 2 | Seguridad rápida (HSTS, auditoría de dependencias) | Imprescindible | Integrado: PR #89 |
| 3 | Paso 24: híbrido C y comparación | Imprescindible | Integrado: PR #90 |
| 4 | Demo lista para el tribunal | Recomendable | Integrado: PR #93 y #95; obras reescritas con reglas de armonía (PR #97, #104) y pasodoble para subir en directo (PR #106) |
| 5 | Grados de editoriales por obra | Recomendable | Integrado: PR #105 |
| 6 | Pregunta libre a la IA | Opcional | Pendiente, solo si queda tiempo |
| 7 | Interfaz en inglés: selector en Configuración (o el idioma del navegador), guardado en el dispositivo; el texto en español es la clave de su traducción (2026-10-30) | Opcional | Integrado: PR #150 (base, acceso, menú y Configuración), PR #151 (Resumen y los textos compartidos de grados, ensayos y conciertos), PR #152 (Repertorio: obras, añadir obra y PDF, dificultad y grados publicados), PR #153 (visores de partitura y de pasaje, reproducción y grabaciones), PR #154 (Mi banda y Configuración › Instrumentos), PR #155 (Conciertos), PR #156 (Ensayos), PR #157 (Valoraciones), PR #158 (errores del servidor, nombres de instrumentos y correo de recuperación) PR #159 (motivos del grado) y PR #160 (explicaciones de la demo y de Gemini en el idioma de la interfaz) |
| 8 | Documentación de entrega | Imprescindible | Integrado: PR #107 (README, guía para el tribunal, seguridad, estados y licencia MIT) |

Mejoras integradas durante el cierre: lectura del título de `<movement-title>` (PR #92), base de estilos única (PR #98), tipografía Inter (PR #99; sustituida por Bricolage Grotesque y Outfit en la PR #118), modo oscuro (PR #100), sombras, transiciones y Resumen en cuadrícula (PR #101), equilibrio de volumen entre instrumentos (PR #102) y pentagramas del pasaje en partes de varios pentagramas (PR #103).

Opcional después de la entrega: búsqueda automática del grado publicado de una obra, como sugerencia que confirma la directora y solo cuando la página encontrada contiene título, compositor y grado (decisión del 2026-10-14).

## Decisiones del 14 al 27 de octubre

| Decisión | Estado |
|---|---|
| difficulty-v2: densidad a la velocidad de cada compás y percusión fuera del grado de la obra | Integrado: PR #108 |
| Las obras con grado de otra edición no sirven para calibrar (solo *Persis* es referencia válida) | Integrado: PR #109 |
| Solo las cuentas de `ADMIN_EMAILS` gestionan campañas y ven emails y resultados; la demo valora como un músico | Integrado: PR #110 |
| La página se revalida tras cada despliegue | Integrado: PR #111 |
| La base pasa a Neon, que no caduca; la aplicación sigue en Render | Integrado: PR #112 |
| difficulty-v3: el grado sigue las guías de grados de las editoriales y explica qué criterio lo fija | Integrado: PR #113 (lectura de armadura, compás, tresillos, dinámicas, articulaciones y adornos) y PR #114 (rúbrica) |
| difficulty-v4: la tabla de la Federación Galega de Bandas de Música prevalece sobre la del American Band College donde difieren (Do mayor sigue en grado 1); ninguna obra de referencia cambia de grado (2026-10-27) | Integrado: PR #124 |
| difficulty-v5: las tesituras también son las de la tabla gallega (barítono y trombón bajo aparte), con las notas de final de curso del ABC en el grado 1 y las columnas 3,5 y 4,5 en el grado inferior; *Persis* sigue en 4 y la Marcha de la demo pasa a 4 (2026-10-27) | Integrado: PR #129 |
| Segunda opinión con un modelo de pesos abiertos para el método B, junto a Gemini (Hugging Face o Vercel AI Gateway) | Pendiente de decidir cómo pagar la API |
| Lectura de PDF: copista-2m en GitHub Actions, en el repositorio privado del lector (`scoremaster-omr`; Hugging Face ya no ejecuta código gratis); partitura general o particellas, grado provisional y fuera de la evaluación. Prueba de viabilidad: copista-2m frente a copista-28m y Audiveris 5.11 con PDF digitales con MusicXML de referencia; oemer y PDF2Muse descartados (2026-10-27) | Integrado: PR #130 (lector) y PR #131 (subida desde la aplicación) |
| Catálogo de instrumentos: nombres en siete idiomas y tonalidad escrita de cualquier forma; después, todo el catálogo en la base de datos, con edición de la administración en Configuración. Siguen los nombres aprendidos por cuenta, los instrumentos desconocidos preguntados (nombre, familia y tonalidad) y el lector de PDF con el catálogo (2026-10-28) | Integrado: PR #138 (idiomas), PR #139 (catálogo en la base), PR #140 (nombres aprendidos e instrumentos propios), PR #141 (el lector de PDF con el catálogo; la partitura general completa la particella ilegible) y PR #146 (lo confirmado por una cuenta sale propuesto en las demás y la administración lo pasa al catálogo común) |
| Obras leídas de PDF: copista escribe las notas en la tonalidad de cada instrumento pero sin `<transpose>`; ScoreMaster añade la transposición, ajusta cada compás a su compás y toma de la banda la armadura que el lector no vio. Las obras ya guardadas se reparan al arrancar, sin volver a leer el PDF (2026-10-29) | Integrado: PR #142 (transposición), PR #143 (obras guardadas), PR #144 (compases) y PR #145 (armaduras) |
| En las particellas, copista se salta los silencios de varios compases y cada parte empieza en un sitio distinto. Solución acordada: leer también la partitura general y alinear cada particella con su pentagrama, insertando los compases que faltan (2026-10-29) | Aparcado hasta que vuelvan los minutos de GitHub Actions del repositorio privado del lector |
| El repositorio de ScoreMaster es público: la CI no gasta minutos de Actions y el lector ya no necesita `SCOREMASTER_READ_TOKEN` (2026-10-29) | Hecho |
| Recuperación de la contraseña por correo: enlace de un solo uso que caduca en 30 minutos, enviado con Brevo (plan gratuito, remitente verificado sin dominio propio); en local, el enlace sale en la consola (2026-10-29) | Integrado: PR #149 |
| Verificación del email al registrarse: en producción, la administración y las invitaciones exigen el email confirmado (2026-10-30) | Integrado: PR #162 |
| Python 3.14 | Después del cierre (2026-10-28) |
| Alojar la aplicación en Vercel | Aplazado a después de la entrega (ver [DEPLOYMENT.md](DEPLOYMENT.md)) |
| Modelos de Hugging Face para la dificultad o bancos de sonido | Descartados: los de dificultad son de piano y no explicables; no hay bancos de viento con licencia clara |

### Diseño y cuadro de mando (2026-10-26 y 27)

| Decisión | Estado |
|---|---|
| El menú pasa a una barra superior y el contenido ocupa todo el ancho; en pantallas estrechas se pliega tras «Menú» | Integrado: PR #116 |
| WCAG 2.1 A y AA como requisito legal: auditoría con axe-core en todas las pantallas (claro, oscuro y móvil) dentro de la CI | Integrado: PR #121 |
| Identidad «Sala de conciertos»: paleta con contraste AA, Bricolage Grotesque y Outfit, botones de acción en píldora y logo de los arcos de la banda | Integrado: PR #118 |
| Cuadro de mando de la directora: «Dónde trabajar» por familias y el programa del próximo concierto con su grado | Integrado: PR #119 |
| La pantalla de acceso sigue la paleta, con el plano de la banda y el logo | Integrado: PR #120 |
| «Cobertura hasta el concierto»: ensayos hechos y, por obra, tiempo ensayado y pasajes resueltos | Integrado: PR #122 |
| authlib 1.9.1 por seis vulnerabilidades publicadas | Integrado: PR #125 |
| El día del concierto el Resumen dice «Hoy» una vez | Integrado: PR #126 |
| El icono de la pestaña lleva versión para que el navegador muestre el logo nuevo | Integrado: PR #127 |

## Mejoras propuestas (2026-10-25)

Propuesta para reforzar la parte de IA generativa y la evaluación. Cada mejora es una PR y se aborda
en este orden cuando se aprueben; se puede elegir un subconjunto. Siguen
valiendo las reglas de siempre: ScoreLint es la única fuente de hechos musicales, el método B no
recibe la predicción de ScoreLint y nada se ajusta con las valoraciones de los músicos.

| # | Mejora | Qué aporta | Requisitos previos | Esfuerzo | Estado |
|---|---|---|---|---|---|
| M1 | Cierre de la entrega: enlaces a vídeo y diapositivas, credenciales de prueba coherentes en README y [TRIBUNAL.md](TRIBUNAL.md), insignia de CI y sección «Resultados y limitaciones» con `evaluation.campaign_report` sobre la exportación real (sin inventar cifras) | Requisitos de BigSchool y resultados medidos | URL del vídeo y de las diapositivas y exportación de la campaña (el repositorio ya es público) | ½ día | Pendiente |
| M2 | Partituras en PDF con OMR (ver la sección [Opcional: partituras en PDF](#opcional-partituras-en-pdf-con-audiveris-decisión-del-2026-10-06)) | Función nueva con un modelo de Hugging Face | 3–4 PDF de prueba: una particella, una partitura de banda y un escaneo | 4–5 días | Integrado con copista-2m en GitHub Actions (PR #130, #131, #141–#145); falta alinear las particellas con la partitura general (aparcado) |
| M3 | Comparación de modelos para el método B (`evaluation/model_comparison.py`): error frente a los músicos, respuestas inválidas, citas rechazadas, latencia, tokens, coste y autoconsistencia por modelo | Justifica la elección del modelo con datos | Exportación de la campaña | 1–2 días | Pendiente; el modelo de pesos abiertos depende de la decisión sobre la API |
| M4 | Pruebas de inyección de prompts con MusicXML hostil (títulos, partes, letras) y apartado OWASP Top 10 para LLM en [SECURITY.md](SECURITY.md) | Seguridad de la capa de IA demostrada con pruebas | Nada | ½–1 día | Integrado (2026-10-29) |
| M5 | Panel de uso de la IA para `ADMIN_EMAILS`: llamadas por modelo, tokens, coste estimado, aciertos de caché, latencia y rechazos por motivo, sin guardar textos de usuarios | Control de la IA en producción | Nada | 1 día | Integrado: PR #161 (Configuración › Uso de la IA; tabla `ai_usage` sin textos ni cuentas) |
| M6 | Pregunta libre con *function calling* sobre funciones de solo lectura (obras, BandFit, pasajes, ensayos), con citas comprobadas | Demo; es el punto 6 del plan de cierre | Nada | 3 días | Opcional |

Descartado de forma razonada, como trabajo futuro de la memoria: entrenar o ajustar un LLM propio (con
pocas valoraciones se evaluaría con los mismos datos con los que aprende y rompería el preregistro del
híbrido C), RAG con pgvector, ejercicios generados por la IA y localizar pasajes en las grabaciones
de YouTube con Gemini.

## Criterios de aceptación

1. Especificaciones enlazadas y distinción entre previsto e implementado.
2. Baseline regenerable con casos sintéticos y candidatos a error sin etiquetas expertas inventadas.
3. Arranque PostgreSQL, healthcheck y volumen, sin credenciales reales versionadas.
4. Migración desde base vacía, persistencia transaccional y pruebas PostgreSQL reales.
5. Análisis guardado con ID y versiones, conservado tras reiniciar.
6–9. Alias multilingües, variantes, metadatos, UNKNOWN y confirmación humana coherente con BandFit/audio.
10–12. Tiempos y ataques correctos en voces/acordes/ligaduras, tempo local, descansos y perfiles configurables.
13. Escalas y rúbrica explícitas; API y frontend adaptados conjuntamente.
14. Detector independiente y cero críticos posible.
15. Ensayo de conjunto: pasajes comunes por similitud de estructura (misma línea en cualquier tonalidad u octava, o mismo ritmo), bloques de línea común seguidos de subsecciones de ensayo con las partes restantes y tutti final; cada bloque indica partes, compases, minutos y motivos; suma de bloques ≤ tiempo disponible; cero pasajes produce solo un tutti; el planificador legacy queda congelado para el baseline.
16–19. Evidencias, feedback por análisis/pasaje/versiones y evaluación reproducible por obra, sin leakage.
20–25. Salidas IA validadas, demo identificada, fallback, versiones, caché y comparación sin anchoring ni resultados inventados. El híbrido sigue siendo experimental.

## Opcional: partituras en PDF con Audiveris (decisión del 2026-10-06)

> Integrado (2026-10-27): subir PDF en la aplicación publicada. Lo lee copista-2m en GitHub
> Actions, en el repositorio privado del lector (`scoremaster-omr`, ver [DEPLOYMENT.md](DEPLOYMENT.md)), con grado provisional y fuera del
> benchmark y de la evaluación. Lo que sigue es el plan original.

> Actualización (2026-10-25): la candidata pasa a ser copista-2m, un modelo abierto de Hugging Face (Apache 2.0,
> funciona en CPU y devuelve MusicXML), con la misma prueba de viabilidad previa y solo en Docker local. Las
> condiciones de abajo siguen valiendo salvo las de licencia de Audiveris.

Importar PDF y convertirlos a MusicXML con Audiveris (OMR) queda como **opcional**, después de
integrar lo pendiente y lanzar la evaluación (pasos 16–18). Amplía el alcance inicial, que excluía
PDF y OCR. Condiciones si se aborda:

- **O1, prueba de viabilidad (1 día):** imagen con Java 21, Audiveris en modo de línea de comandos
  y Tesseract; convertir 2–3 PDF propios o de dominio público y medir tiempo y aciertos antes de
  decidir O2–O4.
- **O2–O4 (unos 3 días):** servicio `omr` en contenedor aparte, tras un perfil de Compose (el
  arranque normal sigue ligero), sin red, con usuario sin privilegios, límites de CPU, memoria,
  tamaño, páginas y tiempo; conversión asíncrona por trabajos; el MusicXML resultante pasa las
  validaciones de siempre y la obra queda marcada como «leída de PDF», con aviso de revisión y
  confirmación de instrumentos. Las obras leídas de PDF no entran en el benchmark.
- **Licencia:** Audiveris es AGPL-3.0: usarlo sin modificar, en su contenedor, y enlazar su código
  fuente. Antes, decidir la licencia del proyecto (el repositorio aún no tiene `LICENSE`).

## Más adelante

PR independientes de autenticación, autorización y despliegue PostgreSQL gestionado, con backup/restauración. Audio: interfaz del renderer actual, eventos expresivos y muestras opcionales tras comprobar licencia; no sacrificar la evaluación musical.

## Mapa de impacto

| Módulo | Carpeta | Componentes | Cambio previsto |
|---|---|---|---|
| Parser/modelo | backend/parsers, backend/domain | parse_musicxml, ScorePart, ScoreNote | Identidad instrumental, transposición, tiempo y ataques |
| Análisis | backend/analyzers | dificultad, perfiles, ensayo | Dificultad local, criticidad y prioridad separadas |
| Aplicación/infraestructura | backend/application, backend/infrastructure | Nuevos puertos/repositorios | Persistencia, IA y caché sin dependencias externas en dominio |
| Presentación | backend/app | /analyze, frontend | IDs, evidencias, escalas y feedback |
| Evaluación | evaluation | Casos, etiquetas y exportación | Baseline, métricas y comparación reproducible |

## Transición a React antes del paso 06

Tres PR independientes, revisadas antes del commit:

| PR de transición | Alcance | Estado |
|---|---|---|
| React 1 | Build reproducible, carga/análisis, asignaciones, estados y cancelación | Integrada: PR #23 |
| React 2 | Dashboard, dificultad, BandFit, ensayo y navegación | Integrada: PR #25 |
| React 3 | Visores, vídeos y reproducción; retirada del adaptador temporal | Integrada: PR #26 |

Se conserva el diseño y se verifica cada recorrido con Playwright. La primera
PR monta React en el formulario mediante un adaptador temporal para las vistas
existentes. [Detalles y arranque](../frontend/README.md). No modifica los algoritmos
musicales ni el esquema de PostgreSQL.
