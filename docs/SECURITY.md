# Seguridad (OWASP)

Medidas aplicadas en el MVP y ampliaciones pendientes. Referencias: OWASP Top 10 y las guías de
la skill `security-best-practices` para FastAPI y React.

## Aplicadas

| Riesgo OWASP | Medida | Dónde |
|---|---|---|
| A07 Fallos de identificación y autenticación | Contraseñas con Argon2id; mínimo 10 caracteres; el mismo error y el mismo coste para un email desconocido y una contraseña errónea; 5 intentos fallidos por email y dirección cada 15 minutos | `backend/application/auth.py` |
| A07 Recuperación de la contraseña | Enlace de un solo uso por correo: token aleatorio de 256 bits, del que la base guarda solo el SHA-256. Caduca en 30 minutos y solo vale el último de cada cuenta. Al usarlo cambia la contraseña, se cierran todas las sesiones y se abre una nueva. La respuesta es la misma para cualquier email, y el correo se envía después de responder, para que el tiempo tampoco revele si existe la cuenta. Como mucho 3 enlaces por hora por email. El token viaja en el fragmento (`/#reset=…`), que el navegador nunca envía a un servidor, y la aplicación lo quita de la barra de direcciones. El enlace usa `APP_BASE_URL`, nunca la cabecera `Host`. La cuenta demo nunca recibe enlace | `auth.py`, `auth_routes.py`, `backend/infrastructure/mailer.py` |
| A07 Sesiones | Token aleatorio de 256 bits en cookie `HttpOnly`, `SameSite=Lax` y `Secure` en producción; la base guarda solo su SHA-256; caducidad de 7 días; cierre de sesión en servidor | `auth.py`, `backend/app/auth_routes.py` |
| A01 Control de acceso | Las rutas de análisis, audio, notación y vídeos exigen sesión (`authenticated_user`); la autorización se decide en el servidor | `backend/app/dependencies.py`, `main.py` |
| A01 Autorización por objeto (IDOR) | Obras, archivos, análisis, bandas, conciertos, ensayos, campañas y grados publicados se consultan siempre filtrando por el usuario; un objeto ajeno responde 404 igual que uno inexistente; borrado en cascada con la obra o la cuenta. Un músico invitado solo ve los pasajes de la campaña a la que le invitaron y sus propias valoraciones, nunca la predicción de ScoreLint ni las valoraciones, emails o número de los demás |
| A01 Rol de administración | Crear y gestionar campañas, ver los emails de los invitados, sus resultados y la exportación, y pedir la valoración con IA es solo de las cuentas de `ADMIN_EMAILS`; las demás reciben 403 al crear y 404 en una campaña. La cuenta demo, de contraseña pública, nunca es administradora: la semilla lo es solo mientras crea su campaña de ejemplo. Como el registro no verifica el email, la cuenta administradora debe registrarse antes de añadirla a la variable | `backend/app/dependencies.py` (`is_admin`), `evaluation_routes.py`, `demo_content.py` | `backend/infrastructure/*_repository.py`, `backend/app/*_routes.py` |
| Datos personales y copyright | El MusicXML subido es privado de su usuario, no se publica y se puede borrar; la descarga lleva `Content-Disposition: attachment` y un nombre saneado | `library_routes.py` |
| CSRF | Token por sesión en la cabecera `X-CSRF-Token` para toda petición que cambia datos, y rechazo de peticiones con `Origin` de otro sitio | `dependencies.py`, middleware `security` |
| Google (opcional) | OIDC con `state` y PKCE S256; ID token verificado (firma, emisor y audiencia); un email no verificado nunca se vincula a una cuenta existente | `auth_routes.py` |
| A03 Inyección | SQLAlchemy con consultas parametrizadas; el parser rechaza `<!ENTITY>`; sin ejecución de comandos | `infrastructure/`, `main.py` |
| A04/A05 Diseño y configuración | Subidas de 8 MB como máximo y 20 MB descomprimidas; parámetros acotados (`band_profile`, minutos, confirmaciones); documentación interactiva de la API desactivada con `APP_ENV=production` | `main.py` |
| XSS y cabeceras | CSP restringida a los CDN del visor, el audio y los vídeos (`script-src 'self' cdn.jsdelivr.net unpkg.com`), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy`, `X-Frame-Options`; React escapa el contenido. Los enlaces que escribe el usuario (fuente de un grado publicado) solo admiten `http(s)`, nunca `javascript:` ni `data:`, y se abren con `rel="noopener noreferrer"` | middleware `security`, `library_routes.py`, `DifficultyView.jsx` |
| A09 Registro | Eventos de registro, login correcto o fallido, Google y logout en `audit_events`, sin contraseñas ni tokens | `account_repository.py` |
| Secretos | Variables de entorno; `.env` fuera del repositorio; credenciales de prueba solo para la demo local | `.env.example`, `docker-compose.yml` |
| A02 Transporte | HTTPS en Render y `Strict-Transport-Security` (`max-age=31536000; includeSubDomains`) solo en producción, para no bloquear `http://localhost`. La conexión con la base de Neon exige TLS (`sslmode=require` y `channel_binding=require` en su URL, que es un secreto de Render) | `render.yaml`, middleware `security`, `backend/infrastructure/database.py` |
| A06 Componentes vulnerables | `pip-audit` y `npm audit` en cada PR; el 2026-10-13 detectaron fallos en starlette, python-multipart, authlib y langchain-core, corregidos actualizando (FastAPI 0.143, Starlette 1.8, Authlib 1.8, LangChain 1.6) y Python 3.12 en todos los entornos | `.github/workflows/ci.yml`, `requirements.txt` |
| IA (OWASP LLM Top 10) | Las evidencias y las notas o preguntas del usuario van como datos en el mensaje humano, nunca como reglas; salida estructurada validada y citas comprobadas contra las evidencias; a la IA solo llegan datos derivados del análisis (nunca la partitura, emails ni nombres); la clave vive en el servidor y nunca llega al log ni al navegador; cupo controlado con pausas, caché y pausa al agotarse | `backend/application/*explanation*.py`, `backend/infrastructure/ai/` |
| Lectura de PDF | El lector corre en GitHub Actions, en el repositorio **privado** del lector (`scoremaster-omr`). Render lo lanza con un token *fine-grained* que solo sirve para ese repositorio (Contents: write). Cada lectura lleva un **token de un solo uso** (la base guarda solo su SHA-256), que el lector usa para descargar los PDF y devolver el resultado, y que se anula al recibirlo. Las rutas del lector (`/omr/imports/…`) solo responden con ese token. Los PDF se borran de la base al recibir el resultado y de la máquina de GitHub al terminar. El trabajo llega al lector por el archivo del evento de GitHub, nunca por una variable del paso (GitHub las muestra en el registro) ni escrito en un comando, y el token se enmascara en su registro. Límites: 20 MB por PDF, 40 archivos y 80 páginas. Las obras leídas de PDF no entran en la evaluación con músicos | `backend/app/pdf_routes.py`, `backend/infrastructure/omr_dispatcher.py`, `omr/` |
| Copias de seguridad | Scripts probados de copia y restauración de PostgreSQL; las copias no se versionan | `scripts/backup_db.sh`, `scripts/restore_db.sh` |
| Datos de la evaluación | Los músicos valoran con su propia cuenta y solo se les piden nivel e instrumento; la exportación los nombra «Evaluador n», sin email ni nombre | `evaluation_repository.py` |
| Preferencias del dispositivo | Tamaño del texto y tema se guardan en `localStorage` del navegador, sin datos personales, y la aplicación funciona si el almacenamiento está bloqueado | `frontend/src/settings.js` |

## IA: OWASP Top 10 para LLM (2025)

La capa de IA sigue el principio del proyecto: ScoreLint, determinista, es la única fuente de hechos musicales, y el
LLM solo explica o da una opinión independiente. Las pruebas de `backend/test/test_ai_prompt_injection.py` (M4,
2026-10-29) suben una partitura hostil, con órdenes para la IA en el título, en el nombre de la parte y en la letra, y
comprueban cada medida marcada con «probado».

| Riesgo | Medida | Dónde |
|---|---|---|
| LLM01 Inyección de prompts | Las reglas van solas en el mensaje de sistema y las evidencias, como JSON, en el mensaje humano, con el aviso «datos, no instrucciones»; los tres prompts lo repiten (probado). El texto del archivo o del usuario (título, nombres de parte, conciertos, bloques, notas del ensayo) llega sin caracteres de control ni marcas de dirección, en una línea y acotado: 120 caracteres, 240 el objetivo de un bloque y 300 las notas del ensayo (probado). La letra de la partitura nunca llega a la IA (probado) | `backend/domain/text.py`, `backend/infrastructure/ai/prompts.py`, `gemini_provider.py` |
| LLM02 Revelación de información sensible | A la IA solo llegan datos derivados del análisis: nunca la partitura, emails, nombres de cuentas ni la clave. La clave vive en el servidor y no aparece en el registro. El método B no recibe la predicción de ScoreLint (probado) | `*_explanation.py`, `backend/analyzers/passage_features.py` |
| LLM03 Cadena de suministro | Modelo de un proveedor (Gemini) por API; LangChain fijado en `requirements.txt` y auditado con `pip-audit` en cada PR | `requirements.txt`, `ci.yml` |
| LLM04 Envenenamiento de datos o del modelo | No se entrena ni se ajusta ningún modelo; el híbrido C está preregistrado y no se ajusta con las valoraciones de los músicos | `docs/EVALUATION_AND_FEEDBACK.md` |
| LLM05 Manejo inadecuado de la salida | Respuesta estructurada validada con Pydantic, con longitudes máximas. Cada pasaje, bloque o instrumento citado se comprueba contra las evidencias: una respuesta que obedece una orden inyectada y cita lo que no existe se descarta, y responde la demo con el motivo (probado). La interfaz muestra la salida como texto, nunca como HTML (probado: ningún componente usa `innerHTML`) | `explanations.py`, `*_explanation.py`, `frontend/src` |
| LLM06 Agencia excesiva | La IA no tiene herramientas ni *function calling*: no lee la base ni cambia nada, solo devuelve texto validado | `backend/infrastructure/ai/` |
| LLM07 Filtración del prompt de sistema | Los prompts no contienen secretos ni datos de cuentas; están versionados en el repositorio público | `prompts.py` |
| LLM08 Debilidades de vectores y *embeddings* | No hay RAG ni base vectorial (descartado de forma razonada en el roadmap) | — |
| LLM09 Desinformación | El grado, los pasajes y el plan los calcula ScoreLint y se muestran aparte de la explicación; la explicación dice qué modelo la escribió y la demo nunca se presenta como IA. Riesgo residual: una frase del texto puede describir mal un dato; las citas se comprueban, pero no cada afirmación | `DifficultyView.jsx`, `explanations.py` |
| LLM10 Consumo sin límite | Evidencias acotadas (8 instrumentos, 8 pasajes, 6 motivos; una partitura hostil no pasa de 12 000 caracteres, probado). Límite de peticiones por minuto (`GEMINI_REQUESTS_PER_MINUTE`), tiempo máximo por llamada, caché de respuestas válidas y pausa al agotarse el cupo | `gemini_provider.py`, `backend/infrastructure/explanation_cache.py` |

Al escribir estas pruebas apareció un fallo: con un título de miles de caracteres, la demo de respaldo superaba el
máximo de su propio resumen y la petición fallaba. El título acotado lo evita.

## Pendientes (ampliación futura)

- Límite de intentos compartido entre procesos (hoy en memoria, válido con un solo proceso).
- Verificación del email al registrarse (la recuperación de la contraseña por correo ya está hecha).
- Roles (por ejemplo, director y músico) más allá de las invitaciones a campañas.
- Copias automáticas más allá de las 6 horas de historial del plan gratuito de Neon (hoy, copias manuales con `scripts/backup_db.sh`).
- `style-src 'unsafe-inline'` en la CSP, que hoy necesitan el visor y React.
