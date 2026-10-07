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
| 512 MB de memoria | Analizar una obra grande y preparar un tutti usa ~450 MB | `PLAYBACK_SCORES_KEPT=1`; si Render reinicia el servicio con obras muy grandes, subir a un plan de pago |
| La base de datos gratuita caduca a los 30 días | Se perderían las cuentas, obras y valoraciones | Exportar las valoraciones y hacer copia antes (ver abajo), o pasar la base de datos a un plan de pago (~6 $/mes; precios en render.com/pricing) |

Para cambiar de plan basta con editar `plan:` en `render.yaml` (o hacerlo desde el panel de Render).

## Copia de seguridad

Desde el panel de la base de datos, **Connections → External Database URL** (habilitar temporalmente
el acceso externo para tu IP en *Access Control*) y, en tu Mac:

```sh
pg_dump "<External Database URL>" --format=custom --file=scoremaster-$(date +%F).dump
```

Para restaurar en otra base de datos: `pg_restore --clean --no-owner -d "<URL destino>" archivo.dump`.
