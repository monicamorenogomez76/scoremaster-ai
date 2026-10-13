# Seguridad (OWASP)

Medidas aplicadas en el MVP y ampliaciones pendientes. Referencias: OWASP Top 10 y las guías de
la skill `security-best-practices` para FastAPI y React.

## Aplicadas

| Riesgo OWASP | Medida | Dónde |
|---|---|---|
| A07 Fallos de identificación y autenticación | Contraseñas con Argon2id; mínimo 10 caracteres; el mismo error y el mismo coste para un email desconocido y una contraseña errónea; 5 intentos fallidos por email y dirección cada 15 minutos | `backend/application/auth.py` |
| A07 Sesiones | Token aleatorio de 256 bits en cookie `HttpOnly`, `SameSite=Lax` y `Secure` en producción; la base guarda solo su SHA-256; caducidad de 7 días; cierre de sesión en servidor | `auth.py`, `backend/app/auth_routes.py` |
| A01 Control de acceso | Las rutas de análisis, audio, notación y vídeos exigen sesión (`authenticated_user`); la autorización se decide en el servidor | `backend/app/dependencies.py`, `main.py` |
| A01 Autorización por objeto (IDOR) | Obras, archivos, análisis y plantilla se consultan siempre filtrando por el usuario; una obra ajena responde 404 igual que una inexistente; borrado en cascada | `library_repository.py`, `library_routes.py` |
| Datos personales y copyright | El MusicXML subido es privado de su usuario, no se publica y se puede borrar; la descarga lleva `Content-Disposition: attachment` y un nombre saneado | `library_routes.py` |
| CSRF | Token por sesión en la cabecera `X-CSRF-Token` para toda petición que cambia datos, y rechazo de peticiones con `Origin` de otro sitio | `dependencies.py`, middleware `security` |
| Google (opcional) | OIDC con `state` y PKCE S256; ID token verificado (firma, emisor y audiencia); un email no verificado nunca se vincula a una cuenta existente | `auth_routes.py` |
| A03 Inyección | SQLAlchemy con consultas parametrizadas; el parser rechaza `<!ENTITY>`; sin ejecución de comandos | `infrastructure/`, `main.py` |
| A04/A05 Diseño y configuración | Subidas de 8 MB como máximo y 20 MB descomprimidas; parámetros acotados (`band_profile`, minutos, confirmaciones); documentación interactiva de la API desactivada con `APP_ENV=production` | `main.py` |
| XSS y cabeceras | CSP restringida a los CDN del visor, el audio y los vídeos (`script-src 'self' cdn.jsdelivr.net unpkg.com`), `frame-ancestors 'none'`, `nosniff`, `Referrer-Policy`, `X-Frame-Options`; React escapa el contenido | middleware `security` |
| A09 Registro | Eventos de registro, login correcto o fallido, Google y logout en `audit_events`, sin contraseñas ni tokens | `account_repository.py` |
| Secretos | Variables de entorno; `.env` fuera del repositorio; credenciales de prueba solo para la demo local | `.env.example`, `docker-compose.yml` |
| A02 Transporte | HTTPS en Render y `Strict-Transport-Security` (`max-age=31536000; includeSubDomains`) solo en producción, para no bloquear `http://localhost` | `render.yaml`, middleware `security` |
| A06 Componentes vulnerables | `pip-audit` y `npm audit` en cada PR; el 2026-10-13 detectaron fallos en starlette, python-multipart, authlib y langchain-core, corregidos actualizando (FastAPI 0.143, Starlette 1.8, Authlib 1.8, LangChain 1.6) y Python 3.12 en todos los entornos | `.github/workflows/ci.yml`, `requirements.txt` |
| IA (OWASP LLM Top 10) | Las evidencias y las notas o preguntas del usuario van como datos en el mensaje humano, nunca como reglas; salida estructurada validada y citas comprobadas contra las evidencias; a la IA solo llegan datos derivados del análisis (nunca la partitura, emails ni nombres); la clave vive en el servidor y nunca llega al log ni al navegador; cupo controlado con pausas, caché y pausa al agotarse | `backend/application/*explanation*.py`, `backend/infrastructure/ai/` |
| Copias de seguridad | Scripts probados de copia y restauración de PostgreSQL; las copias no se versionan | `scripts/backup_db.sh`, `scripts/restore_db.sh` |

## Pendientes (ampliación futura)

- Límite de intentos compartido entre procesos (hoy en memoria, válido con un solo proceso).
- Verificación de email y recuperación de contraseña con un servidor de correo.
- Roles (por ejemplo, director y músico) más allá de las invitaciones a campañas.
- TLS obligatorio hacia PostgreSQL fuera de la red privada de Render y copias automáticas (plan de pago).
- `style-src 'unsafe-inline'` en la CSP, que hoy necesitan el visor y React.
