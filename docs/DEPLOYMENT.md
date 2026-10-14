# Despliegue en Render

La aplicación se publica en [Render](https://render.com) con la **misma imagen Docker** que
`docker compose up` y un PostgreSQL gestionado (decisión de la autora, 2026-10-07; Vercel y Netlify
no ejecutan el backend: Netlify no admite funciones Python y en Vercel music21 queda al límite de
tamaño, sin Docker ni memoria entre peticiones). La configuración está en [`render.yaml`](../render.yaml).

## Pasos (una sola vez)

1. Crear una cuenta en Render e iniciar sesión con GitHub.
2. **New → Blueprint** y elegir el repositorio `scoremaster-ai` (autorizar el acceso de Render al
   repositorio, que es privado).
3. Render lee `render.yaml` y propone la base de datos `scoremaster-db` y el servicio web
   `scoremaster` en Frankfurt. Pide los valores marcados como secretos:
   - `DEMO_SEED_CONTENT=1` (ya en `render.yaml`): si la cuenta demo no tiene obras, al arrancar se crean las
     tres obras de `demo/`, una banda, un concierto con sus ensayos y una campaña en borrador. Una cuenta demo
     que ya tiene obras no se toca, con una excepción: si todas sus obras son versiones anteriores de las de
     `demo/` y nadie ha valorado aún su campaña, se vacía y se crea de nuevo con las actuales.
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
- La base de datos solo admite conexiones de los servicios de Render (`ipAllowList: []`).
- El registro de cuentas está abierto: cada usuario solo ve sus propios datos y los intentos de
  acceso están limitados. Ningún secreto está en el repositorio.

## Plan gratuito (elegido): limitaciones

| Limitación | Consecuencia | Qué hacer |
|---|---|---|
| El servicio se duerme tras 15 min sin uso | El primer acceso tarda alrededor de un minuto | Abrir la aplicación un rato antes de una demostración |
| 512 MB de memoria | Leer una obra grande con music21 usa ~330-450 MB en su pico | El servidor lee una sola obra a la vez (análisis, audio y propuestas); si Render reinicia el servicio con obras muy grandes, subir a un plan de pago |
| CPU muy limitada | Leer una obra grande con music21 tarda unos 3 minutos (*Persis*, simulado con 0,1 CPU) | Cada obra se lee **una sola vez**: su modelo musical y su audio se guardan en la tabla `prepared_works` y sobreviven a reinicios y despliegues. Al analizar una obra se guarda su modelo; su audio se prepara en segundo plano. Al arrancar, el servidor prepara en segundo plano las obras que falten (tras el primer despliegue, unos minutos). Si se pide un pasaje antes, el navegador muestra cuánto lleva preparándose y espera hasta 15 minutos. Con la obra preparada, un pasaje suena en ~2 s, una propuesta de ensayo tarda ~13 s y la planificación de un concierto ~22 s |
| La base de datos gratuita caduca a los 30 días | Se perderían las cuentas, obras y valoraciones | Exportar las valoraciones y hacer copia antes (ver abajo), o pasar la base de datos a un plan de pago (~6 $/mes; precios en render.com/pricing) |

Para cambiar de plan basta con editar `plan:` en `render.yaml` (o hacerlo desde el panel de Render).

## Copia de seguridad y restauración

La base de datos gratuita **caduca a los 30 días de crearse** (creada hacia el 2026-10-07: caduca hacia el
**6 de noviembre**). Hay que copiarla **tras cerrar la campaña de valoración y, en todo caso, antes del
5 de noviembre**. Los scripts usan la imagen `postgres:17` de Docker (la versión de Render): no hay que
instalar PostgreSQL. La URL se lee de `DATABASE_URL_EXTERNAL` o se pide sin mostrarla, para que no quede
en el historial; las copias van a `backups/`, que no se versiona porque contienen datos personales.

**Copiar**

1. Render → base de datos `scoremaster-db` → **Access Control** → añadir tu IP (la página la sugiere).
2. **Connections → External Database URL** → copiarla.
3. En la raíz del repositorio: `scripts/backup_db.sh` y pegar la URL cuando la pida. Imprime las filas
   copiadas (usuarios, obras, análisis, ensayos, conciertos, campañas, valoraciones y valoraciones del LLM).
4. Quitar tu IP de **Access Control**.
5. Exportar además cada campaña desde «Valoraciones → Exportar resultados» y guardar el JSON en
   `evaluation/exports/` (no se versiona): es lo que usa el informe del paso 24.

**Restaurar** (en una base nueva de Render, o en la de Compose para comprobar la copia)

1. Crear la base nueva (Render: *New → PostgreSQL*, o recrear el Blueprint) y permitir tu IP.
2. `scripts/restore_db.sh backups/<archivo>.dump` con la URL de la base nueva. Imprime las mismas filas,
   para compararlas con las de la copia.
3. En el servicio web, cambiar `DATABASE_URL` a la base nueva (Render la enlaza sola si se recrea el
   Blueprint). Al arrancar, `alembic upgrade head` no tiene nada que hacer: la versión viaja con la copia.

Comprobado en local (2026-10-13): copia de la base de Compose y restauración en una base vacía con las
mismas filas en todas las tablas y la misma versión de migraciones (`0011`).

**Alternativa de pago**: pasar la base a un plan de pago (~6 $/mes, precios en render.com/pricing) evita la
caducidad; se cambia `plan:` en `render.yaml` o desde el panel.
