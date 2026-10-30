# Despliegue en Render con la base en Neon

La aplicación se publica en [Render](https://render.com) con la **misma imagen Docker** que
`docker compose up` (decisión del 2026-10-07). La configuración está en [`render.yaml`](../render.yaml).
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
   - `ADMIN_EMAILS`: email de las cuentas administradoras, separados por comas. Solo ellas
     crean campañas de valoración y ven los emails y resultados de los músicos. En producción, la cuenta tiene que
     haber confirmado su email: al registrarse recibe un enlace, y las cuentas anteriores al 2026-10-30 se dan por
     confirmadas. Nunca la cuenta demo.
   - `DEMO_USER_PASSWORD`: contraseña del usuario demo. En cada arranque la cuenta demo toma esta contraseña
     (si cambió, se actualiza y se cierran sus sesiones abiertas): para cambiarla basta con editar la variable. Mínimo 10 caracteres. **No** reutilizar
     la de desarrollo; compartirla solo con el tribunal o los evaluadores.
   - `YOUTUBE_API_KEY`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI`:
     opcionales; vacíos desactivan esas funciones.
   - `BREVO_API_KEY`, `MAIL_FROM`, `APP_BASE_URL` (opcionales, las tres o ninguna): recuperación de la
     contraseña por correo. Pasos:
     1. Crear una cuenta gratuita en https://www.brevo.com (300 correos al día).
     2. En *Senders*, añadir y verificar el email remitente. No hace falta tener un dominio propio.
     3. En *SMTP & API › API keys*, crear una clave y ponerla en `BREVO_API_KEY`.
     4. Poner en `MAIL_FROM` el remitente, por ejemplo `ScoreMaster <correo@ejemplo.org>`.
     5. Poner en `APP_BASE_URL` la dirección pública, `https://scoremaster-iz4j.onrender.com`.

     El enlace se construye con `APP_BASE_URL`, nunca con la cabecera `Host`: una petición manipulada podría hacerlo
     apuntar a otro sitio. Sin las tres variables, la pantalla de acceso no ofrece «¿Has olvidado la contraseña?».
   - `GEMINI_API_KEY` (opcional): las explicaciones «¿Por qué esta dificultad?» y «¿Por qué este plan?»
     las redacta Gemini; sin ella responde la demo identificada. Se crea gratis en
     https://aistudio.google.com/apikey. `GEMINI_MODEL` cambia el modelo (por defecto `gemini-3.8-flash`).
     `GEMINI_REVIEW_MODEL` elige otro modelo solo para «Valorar con IA» (método B), por ejemplo
     `gemini-3.5-flash-lite` (en la cuenta del proyecto, 15 peticiones/minuto y 500/día, frente a 5 y 20 de
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
noviembre). El 2026-10-25 se decidió pasar los datos a Neon, cuyo plan gratuito no caduca, sin mover
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

## Lector de PDF (GitHub Actions en un repositorio privado)

Render no puede leer PDF: copista-2m necesita 2–4,5 GB de memoria. Hugging Face ya solo permite gratis los Spaces
estáticos, así que el lector (`omr/`) corre en **GitHub Actions**, en el **repositorio privado** del lector (`scoremaster-omr`):
2.000 minutos gratis al mes en máquinas de 7 GB, sin tarjeta (decisión del 2026-10-27).

**Cómo funciona:**
1. La directora sube el PDF; Render lo guarda y lanza en ese repositorio el evento `read-pdf`, con un **token de un
   solo uso** para esa importación.
2. El *workflow* descarga los PDF de Render con ese token, lee las páginas con copista-2m y devuelve a Render el avance
   y el MusicXML de la obra (o por qué falló).
3. La máquina de GitHub se destruye al terminar, y Render borra los PDF al recibir el resultado.

**Crear el repositorio del lector (una vez, con tu cuenta de GitHub):**

1. En GitHub, **New repository** → nombre `scoremaster-omr`, **Private**, sin README.
2. Desde el repositorio de ScoreMaster, con `gh` ya autenticado:
   `scripts/deploy_omr_worker.sh <usuario>/scoremaster-omr`. Copia solo el *workflow*; no lleva secretos. El código del
   lector (`omr/`) no se copia: el *workflow* lo descarga de la rama main de ScoreMaster en cada lectura, junto con el
   catálogo de instrumentos (`backend/domain`). Así se actualiza solo, como la aplicación en Render.
3. En GitHub, **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**:
   - **Repository access:** *Only select repositories* → `scoremaster-omr`;
   - **Permissions → Repository permissions → Contents: Read and write** (lo exige `repository_dispatch`);
   - caducidad hasta después de la entrega.

   Ese token solo puede lanzar el lector; no da acceso a nada más.
4. **Mientras el repositorio de ScoreMaster sea privado**, el lector necesita permiso para descargar su código: otro
   token *fine-grained* con **Repository access:** *Only select repositories* → `scoremaster-ai` y **Contents: Read-only**.
   Se guarda en el repositorio del lector, en **Settings → Secrets and variables → Actions → New repository secret**,
   con el nombre `SCOREMASTER_READ_TOKEN`. Cuando ScoreMaster sea público, deja de hacer falta.

**En Render** (Environment), dos secretos:

| Variable | Valor |
|---|---|
| `OMR_GITHUB_REPO` | `<usuario>/scoremaster-omr` |
| `OMR_GITHUB_TOKEN` | El token del paso 3 |

Sin ellos, la opción de subir PDF no aparece.

**Límites:**
- Hasta 20 MB por PDF, 40 archivos y 80 páginas por obra.
- Una lectura a la vez; la siguiente espera.
- Cada lectura tarda 1–2 minutos en arrancar la máquina, más unos segundos por página.
- El lector se actualiza solo al fusionar en main. `scripts/deploy_omr_worker.sh` solo hace falta si cambia
  `omr/workflow/read-pdf.yml`.
- El registro de cada lectura (pestaña **Actions** del repositorio privado) no muestra el token ni las partituras.
- **Catálogo de instrumentos (2026-10-28):** el lector pide a ScoreMaster el catálogo de la base y los nombres que la
  cuenta confirmó antes. Con ellos nombra las particellas y los pentagramas de la partitura general. Si una particella
  no se puede leer, toma su pentagrama de la partitura general. Con un *workflow* anterior, que solo descarga `omr/`,
  el lector usa su lista corta de instrumentos.
- **Transposición (2026-10-29):** copista lee las notas tal como están impresas, en la tonalidad de cada instrumento,
  pero no escribe `<transpose>`. Al recibir la obra, ScoreMaster añade la transposición de cada instrumento que
  reconoce (`backend/parsers/pdf_transpositions.py`). Las particellas siempre se transponen. Un guion en Do no se
  transpone si su texto lo dice («Score in C», «Guion en Do», «sonidos reales») o si sus armaduras lo indican: en un
  guion transpuesto el clarinete en Si♭ lleva dos sostenidos más que la flauta, y en uno en Do llevan la misma. Las
  obras leídas antes de este cambio la reciben al arrancar el servidor, sin volver a leer el PDF
  (`repair_pdf_works`), y se analizan de nuevo; sus notas quedan como estaban escritas.
- **Compases (2026-10-29):** copista a veces lee un compás demasiado largo o corto: un silencio de compás entero
  seguido de notas, o un grupo de fusas un poco largo. Cada uno retrasaba o adelantaba el resto de su parte frente a la
  banda: en «Paco el barba», la mitad de las partes iban de una a dieciséis negras fuera de tiempo. Al recibir la
  lectura, cada compás toma la duración de su compás (`backend/parsers/pdf_measures.py`). Si un compás se pasa, se
  quita primero el silencio de compás entero leído junto a otras notas y después lo que sobrepasa la barra. Si se
  queda corto, se completa con silencio (antes de las notas en el primer compás, que es una anacrusa). Las obras
  guardadas antes se reparan igual al arrancar el servidor, sin volver a leer el PDF.
- **Armaduras (2026-10-29):** copista puede no leer la armadura de una página: en «Paco el barba», seis partes en Si♭
  leyeron la primera sin sus dos sostenidos y sonaban Fa y Do donde el PDF tiene Fa♯ y Do♯. La tonalidad de la obra
  en cada compás es la que comparten la mayoría de las partes no transpositoras (al menos dos). Una parte transpuesta
  debe llevar esa tonalidad más el intervalo de su instrumento. Si no la lleva, toma esa armadura
  (`fix_key_signatures`), y sus notas sin alteración impresa se escriben en ella. Las alteraciones impresas se leyeron
  bien y se respetan hasta la barra, y una nota ligada conserva la altura de la que continúa. Sin al menos dos
  partes de referencia no se cambia nada.

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
