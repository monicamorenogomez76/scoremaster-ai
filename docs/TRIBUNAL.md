# Guía para el tribunal

Recorrido de unos cinco minutos por ScoreMasterAI y qué mirar en cada paso.

## Acceso

- **Demo publicada:** https://scoremaster-iz4j.onrender.com
- **Cuenta:** `demo@scoremaster.local`. La contraseña se entrega aparte y no está en el repositorio.
- **Primer acceso:** el plan gratuito de Render duerme el servicio sin uso, así que puede tardar alrededor
  de un minuto. Conviene abrirlo un rato antes.
- **Sin Internet o sin la demo publicada:** `docker compose up --build` levanta lo mismo en
  http://127.0.0.1:8000 con la contraseña `scoremaster-demo` (ver el [README](../README.md)).

La cuenta demo arranca con tres obras originales (CC0) ya analizadas, una banda, un concierto con su
serie de ensayos y una campaña de valoración en borrador.

## Recorrido

| # | Dónde | Qué hacer | Qué mirar |
|---|---|---|---|
| 1 | **Resumen** | Leer la pantalla de inicio | Próximo concierto, ensayo de hoy con su agenda por bloques y prioridades por sección: lo que necesita el director para la próxima sesión |
| 2 | **Repertorio → Marcha de la plaza → Dificultad** | Pulsar «Explicar la dificultad» | Grado 4 calculado por ScoreLint y explicación con su fuente visible («Modo demo · sin IA» o «Gemini»). Los pasajes que cita son botones que abren la partitura |
| 3 | **Dificultad → árbol → «Ver pasaje»** | Abrir un pasaje crítico y pulsar reproducir | Notación de esa parte, audio en sonido real y compás marcado mientras suena |
| 4 | **Dificultad → Grado publicado** | Ver la tarjeta | El grado de una editorial se escribe a mano con su fuente y se compara con ScoreLint. La aplicación no lo busca ni se lo pide a la IA |
| 5 | **Mi banda** | Ver la plantilla de la banda activa | Adecuación de la obra abierta: instrumentos que faltan o partes sin intérprete |
| 6 | **Conciertos → Planificación** | Abrir el concierto de demostración | Serie de ensayos por fases hasta el ensayo general, con bloques por línea común, sección y tutti |
| 7 | **Ensayos → «¿Por qué este plan?»** | Pedir la explicación de un ensayo | Razones citando bloques concretos, comprobados contra la agenda guardada |
| 8 | **Valoraciones** | Abrir la campaña | Pasajes con la predicción de ScoreLint (solo la ve la directora), invitaciones a músicos y valoración independiente con IA, que no ve la predicción |
| 9 | **Repertorio → Añadir obra** | Subir [`demo/para-subir/pasodoble-de-las-fiestas.mxl`](../demo/para-subir/pasodoble-de-las-fiestas.mxl) | El recorrido completo con una obra nueva. En el plan gratuito, leerla puede tardar uno o dos minutos la primera vez |
| 10 | **Configuración → Tema** | Elegir «Oscuro» | Paleta propia en los dos temas; la partitura conserva el papel blanco |

## Qué se defiende

- **Datos → algoritmos → reglas → IA.** La dificultad la calcula ScoreLint de forma determinista: el mismo
  archivo da siempre el mismo resultado. La IA solo explica, con evidencias acotadas, salida validada y
  citas comprobadas. Sin clave, o ante un fallo, responde una demo que nunca se presenta como IA.
- **Evaluación experimental.** Se comparan ScoreLint (A), un LLM sin la predicción (B), un híbrido
  preregistrado (C) y los músicos (D). El informe se genera desde la exportación anónima de la campaña
  ([evaluation/README.md](../evaluation/README.md)).
- **Seguridad.** Medidas de OWASP aplicadas desde el diseño ([SECURITY.md](SECURITY.md)): cada dato
  pertenece a su usuario y una obra ajena responde 404.
- **Calidad.** TDD, unas 720 pruebas Python con PostgreSQL real, pruebas de Node, recorridos Playwright y
  auditoría de dependencias en cada pull request.

## Si algo no va como se espera

- **Tarda mucho en abrir:** el servicio estaba dormido. Esperar un minuto y recargar.
- **Un pasaje tarda en sonar la primera vez:** el servidor está preparando el audio de la obra, y la
  pantalla dice cuánto lleva.
- **En Safari avanza el tiempo pero no se oye nada:** cerrar Safari con ⌘Q y volver a abrirlo.
- **«Modo demo» en vez de Gemini:** la clave no está configurada o se ha agotado el cupo gratuito del día.
  La interfaz dice el motivo.
