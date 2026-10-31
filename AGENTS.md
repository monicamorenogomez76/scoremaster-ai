# Guía de trabajo — ScoreMasterAI / ScoreLint

## Selección de skills y responsabilidades

Antes de abordar una tarea, identifica su objetivo y lee el `SKILL.md` local
correspondiente en la tabla. Usa las copias de `skills/` de este repositorio como
referencia del proyecto, aunque exista una instalación global de la misma skill.
Las rutas son relativas a la carpeta que contiene este `AGENTS.md`.

| Tipo de tarea | Skill responsable | Responsabilidad y límites |
|---|---|---|
| Lectura MusicXML/MXL e identidad instrumental | [scoremaster-musicxml](skills/scoremaster-musicxml/SKILL.md) | Parser, metadatos, transposición, tiempos, aliases y confirmación de instrumentos. Conserva la información necesaria para los consumidores. |
| Motor determinista de análisis | [scoremaster-scorelint](skills/scoremaster-scorelint/SKILL.md) | Métricas, reglas, findings, dificultad, escalas y criticidad; pruebas y regresiones del algoritmo. |
| Adecuación a la banda y planificación | [scoremaster-bandfit-rehearsal](skills/scoremaster-bandfit-rehearsal/SKILL.md) | Cobertura de partes, disponibilidad, necesidades de intérpretes, prioridades y presupuesto de ensayo. |
| Integración de IA | [scoremaster-ai-layer](skills/scoremaster-ai-layer/SKILL.md) | Puertos y proveedores, prompts, salida estructurada, demo/fake, fallback, caché y trazabilidad. No sustituye hechos musicales por inferencias. |
| Frontend, notación y reproducción | [scoremaster-ui-audio](skills/scoremaster-ui-audio/SKILL.md) | Interfaz, accesibilidad, visor, estado de sesión y audio. React en `frontend/`, compilado a `backend/app/static/frontend/` y servido por FastAPI. |
| API, datos e infraestructura de ejecución | [scoremaster-api-persistence](skills/scoremaster-api-persistence/SKILL.md) | Contratos HTTP, uploads, repositorios, transacciones, PostgreSQL, Alembic y Docker. |
| Evaluación y evidencia para el TFM | [scoremaster-evaluation](skills/scoremaster-evaluation/SKILL.md) | Baseline, benchmark, protocolo de feedback, métricas, comparación de métodos y resultados reproducibles. |
| Revisión del criterio musical | [scoremaster-musical-reviewer](skills/scoremaster-musical-reviewer/SKILL.md) | Validez musical de reglas y resultados, contexto instrumental y recomendaciones con evidencias por parte y compás. No constituye validación humana del benchmark. |

## Cómo aplicar esta distribución

- Selecciona una skill principal por objetivo y añade otras solo cuando la tarea
  atraviese sus responsabilidades. Lee únicamente sus referencias pertinentes;
  no cargues todas las skills para cada cambio.
- Una skill aporta instrucciones que aplica el asistente. Esta distribución no
  requiere crear subagentes ni ampliar el alcance de la petición.
- Para corregir una regla musical, usa `scoremaster-scorelint`; añade
  `scoremaster-musical-reviewer` si hay que revisar su fundamento musical y
  `scoremaster-evaluation` si hay que medir su efecto sobre el benchmark.
- Para corregir instrumentos, empieza por `scoremaster-musicxml` y consulta las
  skills de BandFit o audio cuando sus consumidores resulten afectados.
- Para generar planes mediante LLM, combina `scoremaster-ai-layer` con
  `scoremaster-bandfit-rehearsal`: el proveedor genera una propuesta y el dominio
  valida referencias, disponibilidad y presupuesto.
- Mantén los controles de seguridad aplicables en cualquier implementación.
  Activa las dos skills especializadas de seguridad conforme a las condiciones
  explícitas de la tabla; una edición ordinaria no inicia una auditoría completa
  ni un modelo de amenazas.
- Las instrucciones del usuario prevalecen sobre las guías de las skills.
  Consulta `CONTRIBUTING.md` y `docs/IMPLEMENTATION_ROADMAP.md` para el flujo de
  trabajo y las decisiones aprobadas. Una skill no autoriza por sí misma publicar,
  desplegar, integrar cambios o contactar servicios externos.
- Ejecuta las comprobaciones pertinentes de las skills seleccionadas y comunica
  lo modificado, lo verificado y las limitaciones. En cambios exclusivamente
  documentales, revisa contenido y enlaces sin crear pruebas artificiales.

## Lectura del contexto inicial

El contexto siguiente conserva los objetivos y propuestas originales del TFM.
Para decisiones que hayan evolucionado (stack, escalas, persistencia y secuencia),
prevalece `docs/IMPLEMENTATION_ROADMAP.md`; para conocer lo implementado, comprueba
el código, las pruebas y el README actual. La migración a React sigue las PR de
transición del plan aprobado; consulta `frontend/README.md` para su estado.

# CONTEXTO INICIAL — TFM MAESTROAI / SCORELINT

Estoy desarrollando mi TFM del Máster de Desarrollo con IA de BigSchool.

Tengo aproximadamente 6 semanas para desarrollar el proyecto.

Mi perfil profesional:
- Aproximadamente 20 años de experiencia en desarrollo de software.
- Actualmente trabajo como responsable de desarrollo de un WMS/SGA empresarial.
- Experiencia fuerte en:
  - arquitectura de software;
  - análisis funcional;
  - C#/.NET;
  - Java;
  - SQL Server;
  - APIs;
  - integraciones ERP/WMS;
  - sistemas legacy;
  - diseño y mantenimiento de aplicaciones empresariales.
- También soy música y participo activamente en una banda de música.
- Quiero que el TFM combine mi perfil técnico con mi conocimiento musical.
- El proyecto debe poder publicarse completamente en un repositorio público y no debe contener código, estructuras, datos ni reglas propietarias de mi empresa.

## OBJETIVO DEL TFM

Quiero construir una aplicación real destinada a usuarios finales, principalmente:

- directores de banda;
- profesores de música;
- músicos;
- escuelas/conservatorios;
- bandas y sociedades musicales.

El producto se llamará provisionalmente:

# MaestroAI

MaestroAI será un asistente inteligente para ayudar a un director de banda a:

1. analizar la dificultad de una partitura;
2. comprobar si una obra se adapta a la plantilla real de su banda;
3. planificar cómo ensayar la obra.

El motor técnico de análisis de partituras se llamará:

# ScoreLint

La filosofía de ScoreLint es similar a un linter o analizador estático de código, pero aplicado a partituras musicales.

Ejemplo conceptual:

ESLint / SonarQube -> código fuente
ScoreLint          -> partituras musicales

La idea no es pedirle directamente a un LLM que “entienda” una partitura.

Debe existir primero un análisis musical determinista y reproducible.

La IA generativa se utilizará posteriormente para:
- explicar los resultados;
- generar recomendaciones;
- generar estrategias de estudio;
- generar planes de ensayo.

## ARQUITECTURA FUNCIONAL

La arquitectura conceptual será:

MusicXML
   |
   v
Score Parser
   |
   v
Modelo musical interno
   |
   v
Score Analysis Engine
   |
   +--> Rhythm Analyzer
   +--> Range Analyzer
   +--> Tempo Analyzer
   +--> Interval Analyzer
   +--> Articulation Analyzer
   +--> Endurance Analyzer
   +--> Instrumentation Analyzer
   |
   v
Difficulty Engine
   |
   v
Rule Engine / Findings
   |
   +-------------------+--------------------+
   |                   |                    |
   v                   v                    v
ScoreLint           BandFit             RehearsalAI
   |                   |                    |
   +-------------------+--------------------+
                       |
                       v
                   MaestroAI
                       |
                       v
              Explicaciones mediante IA


## MÓDULO 1 — SCORELINT

ScoreLint debe analizar una partitura MusicXML.

Primera versión:
- NO PDF.
- NO OCR.
- NO análisis de fotografías.
- NO audio.
- NO reconocimiento de interpretación.
- NO entrenamiento de modelos propios.

MusicXML será el formato oficial de entrada del MVP.

Debe extraer información como:

- instrumentos;
- partes;
- compases;
- notas;
- silencios;
- tempo;
- cambios de tempo;
- compás;
- tesitura;
- duración de notas;
- densidad rítmica;
- intervalos;
- dinámicas;
- articulaciones;
- períodos prolongados sin descanso;
- registro utilizado;
- información necesaria para analizar percusión.

ScoreLint calculará dificultad por:

- obra;
- instrumento;
- sección/pasaje;
- rango de compases.

Las dimensiones iniciales de dificultad serán:

1. Rhythm Complexity
2. Tempo Complexity
3. Range Difficulty
4. Interval Complexity
5. Articulation Complexity
6. Endurance

Ejemplo:

Clarinet 1
Measures 47-54

Difficulty: 8.6 / 10

Rhythm:       9.1
Tempo:        8.8
Range:        7.3
Intervals:    7.6
Articulation: 8.0
Endurance:    5.2


La dificultad NO debe ser decidida directamente por un LLM.

Debe calcularse mediante métricas, reglas y algoritmos reproducibles.

Después la IA podrá interpretar el resultado.


## SCORELINT RULES

Además del Difficulty Score quiero tener un sistema de findings parecido a SonarQube.

Ejemplos:

SL001 - Note outside recommended range
SL002 - Extended high-register passage
SL003 - High rhythmic density
SL004 - Large intervals at high tempo
SL005 - Long passage without rest
SL006 - Complex articulation pattern

Cada finding debería poder tener:

- código;
- severidad;
- instrumento;
- compases;
- descripción;
- datos que justifican la detección;
- contribución a la dificultad.


## MÓDULO 2 — BANDFIT

BandFit analizará si una determinada partitura se adapta a la plantilla real de una banda.

El usuario podrá crear el perfil de su banda.

Ejemplo:

Flute:           3
Oboe:            0
Bassoon:         0
Clarinet:       11
Bass Clarinet:   1
Alto Sax:        2
Tenor Sax:       1
Baritone Sax:    1
Horn:            2
Trumpet:         4
Trombone:        3
Euphonium:       2
Tuba:            2
Percussionists:  4

BandFit comparará:

PARTITURA
    vs
PLANTILLA REAL

Y podrá detectar problemas como:

- instrumentos necesarios que no existen en la banda;
- partes independientes sin instrumentista;
- número insuficiente de intérpretes;
- problemas de plantilla de percusión;
- posibles duplicaciones;
- voces especialmente relevantes que quedan descubiertas.

Ejemplo:

Band compatibility: 82 %

CRITICAL
Oboe unavailable.
23 measures contain an independent oboe line.

WARNING
Score requires four horn parts.
Available horn players: 2.

CRITICAL
Five percussionists are simultaneously required
between measures 127-142.
Available: 4.

En el MVP NO quiero realizar una reorquestación automática completa.

Se pueden sugerir alternativas, pero deben presentarse como recomendaciones y no como una reorquestación musical automáticamente válida.


## MÓDULO 3 — REHEARSALAI

RehearsalAI utilizará:

- Difficulty Score de ScoreLint;
- pasajes críticos;
- resultados de BandFit;
- plantilla disponible;
- duración del ensayo.

Opcionalmente podrá tener en cuenta:
- músicos ausentes ese día.

Ejemplo:

Duración del ensayo: 90 minutos.

Resultado:

10 min
Calentamiento y afinación

15 min
Clarinetes
Compases 47-54
Difficulty 8.6

12 min
Metales
Compases 82-91
Difficulty 8.2

15 min
Conjunto
Compases 47-54

...

También debe poder justificar por qué prioriza determinados fragmentos.

Ejemplo:

“No se recomienda dedicar hoy tiempo a los compases 112-128 porque la voz de oboe es estructural y no hay oboe disponible.”

En futuras versiones podría incluir:
- histórico de ensayos;
- proximidad de conciertos;
- resultados de ensayos anteriores;
- múltiples obras;
- optimización completa del tiempo de ensayo.

Pero esto NO es obligatorio para el MVP.


## MAESTROAI — CAPA GENERATIVA

MaestroAI utilizará un LLM.

El LLM no debe utilizarse como fuente de verdad de los datos musicales.

Debe recibir información previamente calculada por ScoreLint.

Ejemplo:

{
  "instrument": "Clarinet 1",
  "measures": "47-54",
  "tempo": 152,
  "difficulty": 8.6,
  "rhythm": 9.1,
  "range": 7.3,
  "intervals": 7.6,
  "endurance": 5.2
}

A partir de esos datos podrá explicar:

“El principal factor de dificultad de este fragmento es la combinación de semicorcheas a tempo elevado con frecuentes cambios de registro...”

Debe evitar inventar información no derivada del análisis.

Siempre que sea posible, las explicaciones de IA deben estar respaldadas por evidencias estructuradas.


## PRINCIPIO FUNDAMENTAL DE DISEÑO

Separar:

1. DATOS
2. ALGORITMOS
3. REGLAS
4. IA GENERATIVA

Flujo deseado:

MusicXML
    ↓
Datos musicales
    ↓
Algoritmos
    ↓
Reglas
    ↓
Resultados objetivos
    ↓
LLM
    ↓
Explicación para el usuario

NO:

MusicXML
    ↓
LLM
    ↓
“Esto parece difícil”


## SEGURIDAD Y OWASP

El proyecto debe incorporar la mentalidad OWASP desde el inicio, no como una capa añadida al final.

Se debe considerar al menos el OWASP Top 10 para una aplicación web con autenticación, subida de archivos y acceso a datos de usuarios.

En particular:

- autenticación y autorización seguras;
- control de acceso basado en roles y permisos mínimos;
- validación estricta de entrada, especialmente en uploads de MusicXML y formularios;
- prevención de inyección SQL, NoSQL y command injection;
- protección frente a XSS y CSRF;
- gestión segura de secretos y variables de entorno;
- uso de HTTPS en producción;
- cabeceras de seguridad y configuración segura del servidor;
- auditoría y logging de eventos relevantes;
- limitación de tamaño y tipo de archivos subidos;
- revisión y actualización de dependencias para evitar vulnerabilidades conocidas;
- principio de seguridad por defecto en la infraestructura y la configuración del despliegue.

Para este TFM, el requisito mínimo será que el diseño y la implementación del backend, API y frontend tengan en cuenta estos principios y que la solución no introduzca riesgos de seguridad evidentes.

En la entrega final se debe documentar qué medidas OWASP se han aplicado y cuáles quedan como ampliación futura si el proyecto se desarrolla más allá del MVP.

## USUARIO FINAL

La aplicación debe estar diseñada como producto para usuarios finales.

No quiero una simple herramienta de línea de comandos como interfaz principal.

Debe existir una aplicación web usable.

Flujo ideal:

1. El usuario inicia sesión.
2. Configura su banda.
3. Sube una partitura MusicXML.
4. MaestroAI analiza la obra.
5. Ve:
   - dificultad global;
   - dificultad por instrumento;
   - pasajes críticos;
   - findings;
   - adecuación a la plantilla;
   - recomendaciones.
6. Puede generar un plan de ensayo.


## EXPERIENCIA DE USUARIO

La pantalla de análisis debería responder fundamentalmente a tres preguntas:

1. ¿Qué dificultad tiene esta obra?
2. ¿Encaja con mi banda?
3. ¿Cómo debería ensayarla?

No quiero que la interfaz se convierta en una herramienta extremadamente técnica.

El usuario final es músico/director, no desarrollador.


## STACK PROPUESTO

Backend:
- Python
- FastAPI
- music21
- Pydantic

Frontend:
- React

Persistencia:
- PostgreSQL o SQLite para desarrollo, según complejidad final.

IA:
- proveedor LLM externo mediante API.

Arquitectura:
- frontend separado;
- API;
- dominio;
- parser MusicXML;
- analizadores;
- Difficulty Engine;
- Rule Engine;
- BandFit;
- RehearsalAI;
- abstracción del proveedor LLM.

Infraestructura:
- Docker;
- Docker Compose;
- GitHub;
- GitHub Actions;
- tests automáticos.

El profesor debe poder clonar el repositorio público y arrancar el proyecto con el mínimo número posible de pasos, idealmente:

docker compose up


## IA Y REPRODUCIBILIDAD

La aplicación debe poder ejecutarse aunque el usuario que clone el repositorio no tenga una API key.

Debe existir:

- provider real opcional mediante API/free tier;
- modo demo local determinista claramente identificado.

Si existe API key:
-> utilizar proveedor real.

Si NO existe:
-> utilizar DemoAIProvider.

Nunca debe parecer que el modo demo es IA real.

Debe indicarse claramente en la interfaz.


## AUTENTICACIÓN

El MVP puede soportar:

- email/password;
- Google Login opcional.

Google Login no debe ser requisito para arrancar el proyecto.

Si no existen credenciales Google:
-> esa opción debe quedar desactivada limpiamente.

La aplicación debe seguir siendo completamente utilizable con email/password.

Para validación de correo/recuperación de contraseña puede utilizarse un servidor de correo local de desarrollo en lugar de correo real.


## IDIOMAS

Primera versión:

- castellano;
- inglés.

La arquitectura debe permitir añadir nuevos idiomas en el futuro.


## DATOS Y COPYRIGHT

El repositorio será público.

NO almacenar:

- partituras comerciales protegidas sin autorización;
- documentos propietarios;
- material de mi empresa;
- datos privados.

Para pruebas utilizar:

- MusicXML creado específicamente para tests;
- partituras propias;
- obras de dominio público;
- contenidos con licencia compatible.

Se pueden crear partituras sintéticas destinadas a probar casos concretos:

easy.musicxml
high-register.musicxml
complex-rhythm.musicxml
large-intervals.musicxml
endurance.musicxml


## EVALUACIÓN DEL TFM

No quiero limitar el TFM a “he construido una aplicación”.

Debe existir evaluación experimental.

Posible pregunta de investigación:

“¿Puede un sistema híbrido basado en análisis musical determinista e inteligencia artificial generativa asistir a un director de banda en la evaluación de dificultad, adecuación del repertorio y planificación del ensayo?”

Para ScoreLint:

crear un benchmark con fragmentos musicales.

Expertos/músicos podrán evaluar:

1 = muy fácil
...
5 = muy difícil

ScoreLint producirá:

0-10

Comparar ambos resultados.

Métricas posibles:

- correlación;
- MAE;
- precision;
- recall;
- F1;
- capacidad de detectar pasajes considerados difíciles.

También interesa comparar:

A) análisis basado únicamente en LLM;
B) ScoreLint determinista;
C) ScoreLint + MaestroAI.

La evaluación deberá decidirse de manera rigurosa cuando se diseñe el benchmark.


## ALCANCE DEL MVP

P0 — OBLIGATORIO

- proyecto ejecutable;
- Docker Compose;
- carga MusicXML;
- parser;
- modelo musical;
- detección de instrumentos;
- análisis de notas/compases;
- Rhythm Analyzer;
- Range Analyzer;
- Tempo Analyzer;
- Interval Analyzer;
- Difficulty Engine;
- detección de pasajes críticos;
- findings ScoreLint;
- frontend básico usable.

P1 — TFM COMPLETO

- Articulation Analyzer;
- Endurance Analyzer;
- configuración de banda;
- BandFit;
- IA para explicación;
- RehearsalAI;
- autenticación;
- tests;
- evaluación experimental.

P2 — SOLO SI HAY TIEMPO

- músicos ausentes en el ensayo;
- múltiples obras;
- histórico de análisis;
- comparación de obras;
- mejora visual de dashboard;
- exportación de informe.

FUERA DE ALCANCE / FUTURO

- OCR;
- PDF;
- reconocimiento de partituras mediante imagen;
- análisis de audio;
- detección de afinación;
- evaluación de grabaciones;
- reconocimiento de interpretación;
- reorquestación automática;
- composición automática;
- entrenamiento de modelos propios;
- generación automática de particellas.


## PLAN DE 6 SEMANAS

SEMANA 1
- arquitectura;
- setup repositorio;
- Docker;
- MusicXML;
- parser;
- modelo de dominio;
- primeras partituras sintéticas.

Objetivo:
leer una partitura correctamente.

SEMANA 2
- Rhythm Analyzer;
- Range Analyzer;
- Tempo Analyzer;
- Interval Analyzer;
- tests.

Objetivo:
scorelint analyze score.musicxml
debe producir primeras métricas.

SEMANA 3
- Difficulty Engine;
- reglas ScoreLint;
- pasajes críticos;
- API;
- primera interfaz.

Objetivo:
tener un TFM técnicamente defendible aunque no esté acabado visualmente.

SEMANA 4
- BandFit;
- MaestroAI;
- explicaciones;
- RehearsalAI.

SEMANA 5
- frontend;
- UX;
- autenticación si procede;
- dataset de evaluación;
- pruebas con usuarios/músicos.

SEMANA 6
- evaluación;
- corrección de bugs;
- tests;
- documentación;
- README;
- despliegue;
- slides;
- vídeo;
- preparación defensa.

REGLA:
Al terminar la semana 3 debe existir ya un MVP funcional.


## ESTRUCTURA ORIENTATIVA DEL REPOSITORIO

maestroai/
|
+-- backend/
|   +-- api/
|   +-- domain/
|   +-- parsers/
|   +-- analyzers/
|   |   +-- rhythm/
|   |   +-- range/
|   |   +-- tempo/
|   |   +-- intervals/
|   |   +-- articulation/
|   |   +-- endurance/
|   +-- difficulty/
|   +-- rules/
|   +-- bandfit/
|   +-- rehearsal/
|   +-- ai/
|   +-- infrastructure/
|
+-- frontend/
|
+-- tests/
|
+-- test-scores/
|
+-- docs/
|
+-- docker-compose.yml
+-- README.md
+-- LICENSE


## CRITERIOS DE DESARROLLO

Quiero que las decisiones técnicas prioricen:

1. terminar correctamente el TFM en aproximadamente 6 semanas;
2. arquitectura limpia pero sin sobreingeniería;
3. código mantenible;
4. tests;
5. reproducibilidad;
6. repositorio público profesional;
7. buena experiencia de usuario;
8. explicabilidad de los resultados;
9. evitar dependencia innecesaria del LLM;
10. una demo final muy visual.

Cuando haya que elegir entre una arquitectura más sofisticada y terminar un MVP sólido, priorizar el MVP.


## REQUISITOS DE ENTREGA DEL TFM

El proyecto debe considerar desde el principio que la entrega requiere, entre otros elementos:

- README completo;
- descripción del proyecto;
- stack tecnológico;
- instrucciones de instalación y ejecución;
- estructura del proyecto;
- funcionalidades;
- credenciales de prueba si existe login;
- código fuente en GitHub;
- preferentemente repositorio público;
- despliegue/publicación cuando sea posible;
- slides;
- vídeo explicativo mostrando la pantalla.

Por tanto, documentación, reproducibilidad y facilidad de ejecución forman parte del proyecto y no deben dejarse únicamente para el último día.


## FORMA DE TRABAJAR EN ESTE CHAT

A partir de este contexto quiero desarrollar MaestroAI de manera incremental.

Antes de implementar una característica:
1. definir claramente el objetivo;
2. decidir modelo de dominio;
3. decidir algoritmo/reglas;
4. definir tests;
5. implementar.

No quiero añadir funcionalidades simplemente porque sean llamativas si comprometen las seis semanas.

Cuando propongas una ampliación, clasificarla como:
- MVP;
- recomendable;
- opcional;
- futuro.

Cuando propongas cambios de código, indicar claramente:
- proyecto/módulo;
- carpeta;
- archivo/clase;
- método o componente afectado.

El objetivo es terminar con un producto real, usable, público, reproducible y técnicamente defendible como TFM.
