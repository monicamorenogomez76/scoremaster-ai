# Despliegue en Render con la base en Neon

La aplicación se publica en [Render](https://render.com) con la **misma imagen Docker** que
`docker compose up` (decisión de la autora, 2026-10-07). La configuración está en [`render.yaml`](../render.yaml).
Desde el 2026-10-25 los datos están en el PostgreSQL gratuito de [Neon](https://neon.com), que no caduca;
la base gratuita de Render caducaba a los 30 días (ver «Base de datos en Neon»).

## Pasos (una sola vez)

1. Crear una cuenta en Render e iniciar sesión con GitHub.
2. **New → Blueprint** y elegir el repositorio `scoremaster-ai` (autorizar el acceso de Render al
   repositorio, que es privado).
3. Render lee `render.yaml` y propone el servicio web `scoremaster` en Frankfurt (y la base `scoremaster-db`,
   que solo se conserva hasta comprobar el paso a Neon). Pide los valores marcados como secretos:
   - `DATABASE_URL`: la cadena de conexión **directa** de Neon, tal cual la da Neon (incluye
     `sslmode=require`). Ver «Base de datos en Neon».
   - `DEMO_SEED_CONTENT=1` (ya en `render.yaml`): si la cuenta demo no tiene obras, al arrancar se crean las
     tres obras de `demo/`, una banda, un concierto con sus ensayos y una campaña abierta a la que la demo está
     invitada. Una cuenta demo
     que ya tiene obras no se toca, con una excepción: si todas sus obras son versiones anteriores de las de
     `demo/` y nadie ha valorado aún su campaña, se vacía y se crea de nuevo con las actuales.
   - `ADMIN_EMAILS`: email de las cuentas administradoras, separados por comas (la de la autora). Solo ellas
     crean campañas de valoración y ven los emails y resultados de los músicos. Registrar antes la cuenta: el
     registro no verifica el email. Nunca la cuenta demo.
   - `DEMO_USER_PASSWORD`: contraseña del usuario demo. En cada arranque la cuenta demo toma esta contraseña
     (si cambió, se actualiza y se cierran sus sesiones abiertas): para cambiarla basta con editar la variable. Mínimo 10 caracteres. **No** reutilizar
     la de desarrollo; compartirla solo con el tribunal o los evaluadores.
   - `YOUTUBE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`:
     opcionales; vacíos desactivan esas funciones.
   - `GEMINI_API_KEY` (opcional): las explicaciones «¿Por qué esta dificultad?» y «¿Por qué este plan?»
     las redacta Gemini; sin ella responde la demo identificada. Se crea gratis en
     https://aistudio.google.com/apikey. `GEMINI_MODEL` cambia el modelo (por defecto `gemini-3.8-flash`).
     `GEMINI_REVIEW_MODEL` elige otro modelo solo para «Valorar con IA» (método B), por ejemplo
     `gemini-3.5-flash-lite` (en la cuenta de la autora, 15 peticiones/minuto y 500/día, frente a 5 y 20 de
     `gemini-3.8-flash`); `GEMINI_REQUESTS_PER_MINUTE` (5 por defecto) ajusta la pausa entre peticiones.
     En el nivel gratuito Google puede usar lo enviado para mejorar sus productos: solo se envían datos
     derivados del análisis (grados, dimensiones, compases, bloques), nunca la partitura, emails ni nombres.
   - La clave de YouTube la usa **el servidor**, no el navegador. En Google Cloud, en la clave:
     *Restricciones de API* → solo «YouTube Data API v3» (activada en el proyecto); *Restricciones
     de aplicación* → **Ninguna**. Con «Sitios web (referentes HTTP)», Google rechaza las llamadas
     del servidor (`API_KEY_HTTP_REFERRER_BLOCKED`), y el plan gratuito de Render no tiene IP fija para
     restringir por dirección. Si la búsqueda falla, los logs de Render dicen el motivo
     («YouTube rechazó la búsqueda: HTTP 403, motivo: …»), nunca la clave.
4. **Apply**. La primera construcción tarda varios minutos. Al arrancar, el contenedor aplica las
   migraciones y crea el usuario demo. La URL pública es `https://scoremaster-….onrender.com`.
5. Cada integración en `main` se despliega sola (`autoDeploy`).

## Seguridad en producción

- `APP_ENV=production`: cookies `Secure`, sin documentación interactiva de la API. Render sirve
  HTTPS y uvicorn confía en sus cabeceras de proxy (`--proxy-headers`).
- El contenedor se ejecuta con un usuario sin privilegios.
- La conexión con Neon va cifrada (`sslmode=require` en su URL) y protegida por usuario y contraseña; la URL
  es un secreto de Render y nunca está en el repositorio.
- El registro de cuentas está abierto: cada usuario solo ve sus propios datos y los intentos de
  acceso están limitados. Ningún secreto está en el repositorio.

## Plan gratuito (elegido): limitaciones

| Limitación | Consecuencia | Qué hacer |
|---|---|---|
| El servicio se duerme tras 15 min sin uso | El primer acceso tarda alrededor de un minuto | Abrir la aplicación un rato antes de una demostración |
| 512 MB de memoria | Leer una obra grande con music21 usa ~330-450 MB en su pico | El servidor lee una sola obra a la vez (análisis, audio y propuestas); si Render reinicia el servicio con obras muy grandes, subir a un plan de pago |
| CPU muy limitada | Leer una obra grande con music21 tarda unos 3 minutos (*Persis*, simulado con 0,1 CPU) | Cada obra se lee **una sola vez**: su modelo musical y su audio se guardan en la tabla `prepared_works` y sobreviven a reinicios y despliegues. Al analizar una obra se guarda su modelo; su audio se prepara en segundo plano. Al arrancar, el servidor prepara en segundo plano las obras que falten (tras el primer despliegue, unos minutos). Si se pide un pasaje antes, el navegador muestra cuánto lleva preparándose y espera hasta 15 minutos. Con la obra preparada, un pasaje suena en ~2 s, una propuesta de ensayo tarda ~13 s y la planificación de un concierto ~22 s |
| La base de Neon se suspende tras 5 min sin uso | La primera consulta tras una pausa espera a que despierte (el servidor espera hasta 10 s al conectar) | Nada: se reanuda sola. El plan gratuito de Neon da 1 GB por proyecto y 100 horas de cómputo al mes, de sobra para el TFM |

Para cambiar de plan basta con editar `plan:` en `render.yaml` (o hacerlo desde el panel de Render).

## Base de datos en Neon

La base gratuita de Render **caduca a los 30 días** (la del TFM, creada hacia el 2026-10-07, hacia el 6 de
noviembre). El 2026-10-25 la autora decidió pasar los datos a Neon, cuyo plan gratuito no caduca, sin mover
la aplicación ni cambiar su URL.

**Crear la base** (una vez)

1. Crear una cuenta en Neon y un proyecto con **PostgreSQL 17** en **AWS Europe Central 1 (Frankfurt)**, la
   región del servicio de Render.
2. **Connect** → desactivar *Connection pooling* y copiar la cadena **directa**
   (`postgresql://…neon.tech/…?sslmode=require&channel_binding=require`). Las migraciones de Alembic y el
   pool de SQLAlchemy necesitan la conexión directa.

**Pasar los datos de Render a Neon** (sin valoraciones en curso)

1. Copiar la base de Render como en «Copia de seguridad y restauración» (pasos 1–4).
2. `scripts/restore_db.sh backups/<archivo>.dump` con la URL de Neon. Las filas que imprime deben coincidir
   con las de la copia.
3. Render → servicio `scoremaster` → **Environment** → `DATABASE_URL` = la URL de Neon → **Save, rebuild,
   and deploy**. Al arrancar, `alembic upgrade head` no tiene nada que hacer: la versión viaja con la copia.
4. Comprobar que se entra con una cuenta y con la demo, que están las obras y que suena un pasaje.

Cuando todo funcione, la base `scoremaster-db` se quita de `render.yaml` (otra PR) y la de Render caduca sola.

## Copia de seguridad y restauración

Hay que copiar la base **tras cerrar la campaña de valoración**. Los scripts usan la imagen `postgres:17` de
Docker (la versión de Render y de Neon): no hay que instalar PostgreSQL. La URL se lee de
`DATABASE_URL_EXTERNAL` o se pide sin mostrarla, para que no quede en el historial; las copias van a
`backups/`, que no se versiona porque contienen datos personales.

**Copiar**

1. La URL de la base:
   - Neon: **Connect** → cadena directa.
   - Render (solo para el paso a Neon): base `scoremaster-db` → **Access Control** → añadir tu IP (la página
     la sugiere) → **Connections → External Database URL**.
2. En la raíz del repositorio: `scripts/backup_db.sh` y pegar la URL cuando la pida. Imprime las filas
   copiadas (usuarios, obras, análisis, ensayos, conciertos, campañas, valoraciones y valoraciones del LLM).
3. En Render, quitar tu IP de **Access Control**.
4. Exportar además cada campaña desde «Valoraciones → Exportar resultados» y guardar el JSON en
   `evaluation/exports/` (no se versiona): es lo que usa el informe del paso 24.

**Restaurar** (en Neon, en otra base nueva o en la de Compose para comprobar la copia)

1. `scripts/restore_db.sh backups/<archivo>.dump` con la URL de la base de destino. Imprime las mismas filas,
   para compararlas con las de la copia.
2. En el servicio web, cambiar `DATABASE_URL` a esa base. Al arrancar, `alembic upgrade head` no tiene nada
   que hacer: la versión viaja con la copia.

Neon guarda además 6 horas de historial para volver a un momento anterior desde su panel.

Comprobado en local (2026-10-13): copia de la base de Compose y restauración en una base vacía con las
mismas filas en todas las tablas y la misma versión de migraciones (`0011`).

## Lector de PDF (Space privado de Hugging Face)

Render no puede leer PDF: copista-2m necesita 2–4,5 GB de memoria. El lector (`omr/`) corre en un **Space Docker
privado** de la cuenta de Hugging Face de la autora, en el hardware gratuito (2 CPU y 16 GB). Solo Render lo llama
(decisión de la autora, 2026-10-27).

**Crear el Space (una vez, con la cuenta de la autora):**

1. En Hugging Face: **New Space** → nombre `scoremaster-omr`, SDK **Docker** (plantilla en blanco), hardware
   **CPU basic** (gratis), visibilidad **Private**.
2. En el Space, **Settings → Variables and secrets → New secret**: `OMR_TOKEN`, con un valor largo y aleatorio
   (por ejemplo, la salida de `openssl rand -hex 32`). No se escribe en ningún archivo ni en el chat.
3. En tu equipo, `hf auth login` con un token de **escritura** de tu cuenta, y desde el repositorio:
   `scripts/deploy_omr_space.sh <usuario>/scoremaster-omr`. Hugging Face construye la imagen en unos 10 minutos
   (el registro está en la pestaña **Logs** del Space).
4. Crea otro token de tu cuenta, de **solo lectura** (Settings → Access Tokens, tipo *Read*): es el que deja
   entrar a Render en el Space privado.

**En Render** (Environment), tres secretos:

| Variable | Valor |
|---|---|
| `OMR_SERVICE_URL` | `https://<usuario>-scoremaster-omr.hf.space` |
| `OMR_SERVICE_TOKEN` | El mismo valor que `OMR_TOKEN` del Space |
| `OMR_HF_TOKEN` | El token de solo lectura del paso 4 |

Sin ellos, la opción de subir PDF no aparece.

**Cómo funciona y límites:**
- Cada página se lee por separado y el Space une las páginas en una obra; Render consulta el avance mientras la
  directora espera.
- Hasta 20 MB por PDF, 40 archivos y 80 páginas por obra.
- Los PDF se borran al terminar y el resultado se olvida en cuanto Render lo recoge, o una hora después.
- **Se duerme a las 48 horas sin uso:** la primera lectura después tarda 2–3 minutos más en despertarlo.
- Para actualizar el lector basta con volver a ejecutar `scripts/deploy_omr_space.sh`.

## Trabajo futuro: Vercel

Valorado el 2026-10-25 y aplazado hasta después de la entrega. Vercel ejecuta FastAPI como funciones: más
memoria (2 GB) y una CPU entera, y no se duerme como Render, pero cada petición dura como máximo 5 minutos,
el trabajo tras responder no es fiable y las tareas programadas del plan gratuito son diarias. Habría que
adaptar:

- **Audio de un pasaje:** prepararlo dentro de la petición en lugar de responder 202 y seguir en segundo plano.
- **«Valorar con IA» de una campaña:** por tandas, una por petición; cada valoración ya se guarda al momento.
- **Preparación y nuevo análisis al arrancar:** una tarea programada diaria (protegida con `CRON_SECRET`) o al
  abrir cada obra.
- **Migraciones y cuenta demo:** en la construcción, nunca desde las versiones de prueba de cada rama.

La base de Neon serviría igual.
