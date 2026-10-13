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
   - `DEMO_USER_PASSWORD`: contraseña del usuario demo (mínimo 10 caracteres). **No** reutilizar
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

## Copia de seguridad

Desde el panel de la base de datos, **Connections → External Database URL** (habilitar temporalmente
el acceso externo para tu IP en *Access Control*) y, en tu Mac:

```sh
pg_dump "<External Database URL>" --format=custom --file=scoremaster-$(date +%F).dump
```

Para restaurar en otra base de datos: `pg_restore --clean --no-owner -d "<URL destino>" archivo.dump`.
