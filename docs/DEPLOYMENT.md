# Despliegue

| Pieza | Servicio | Plan |
|---|---|---|
| Aplicación (FastAPI + React) | [Render](https://render.com), servicio web `scoremaster` en Frankfurt, con la misma imagen Docker que `docker compose up`. Configuración en [`render.yaml`](../render.yaml) | Gratuito |
| Base de datos | PostgreSQL 18 en [Neon](https://neon.com), AWS Europe Central 1 (Frankfurt) | Gratuito |
| Lector de PDF | GitHub Actions en el repositorio público `scoremaster-omr` | Gratuito (sin tope de minutos en un repositorio público) |
| Correo (recuperación de contraseña y confirmación del email) | [Brevo](https://www.brevo.com), API transaccional | Gratuito (300 correos al día) |
| IA | Gemini (Google AI Studio) | Gratuito |

URL pública: https://scoremaster-iz4j.onrender.com. Cada integración en `main` se despliega sola (`autoDeploy`).
Al arrancar, el contenedor aplica las migraciones (`alembic upgrade head`) y crea o actualiza la cuenta demo.

## Crear el servicio en Render

1. En Render, iniciar sesión con GitHub y elegir **New → Blueprint** con el repositorio `scoremaster-ai`.
2. Render lee `render.yaml` y propone el servicio `scoremaster`. Pide los valores marcados como secretos
   (`sync: false`), que nunca están en el repositorio:

| Variable | Valor |
|---|---|
| `DATABASE_URL` | Cadena de conexión **directa** de Neon, tal cual la da Neon (con `sslmode=require`). Ver «Base de datos en Neon» |
| `DEMO_USER_PASSWORD` | Contraseña de la cuenta demo (mínimo 10 caracteres). En cada arranque la cuenta toma esta contraseña y, si cambió, se cierran sus sesiones. No reutilizar la de desarrollo; se comparte solo con quien vaya a probar la demo |
| `ADMIN_EMAILS` | Emails de las cuentas administradoras, separados por comas. Solo ellas crean campañas de valoración y ven los emails y resultados de los músicos. La cuenta tiene que haber confirmado su email. Nunca la cuenta demo |
| `BREVO_API_KEY`, `MAIL_FROM`, `APP_BASE_URL` | Opcionales, las tres o ninguna. Ver «Correo con Brevo» |
| `GEMINI_API_KEY` | Opcional. Ver «IA con Gemini» |
| `OMR_GITHUB_REPO`, `OMR_GITHUB_TOKEN` | Opcionales. Ver «Lector de PDF» |
| `YOUTUBE_API_KEY` | Opcional. Ver «Búsqueda en YouTube» |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_REDIRECT_URI` | Opcionales: acceso con Google. Vacías, no se ofrece |

Fijadas en `render.yaml`: `APP_ENV=production`, `DEMO_USER_EMAIL=demo@scoremaster.local` y `DEMO_SEED_CONTENT=1`.
Con esta última, si la cuenta demo no tiene obras, al arrancar se crean las tres obras de `demo/`, una banda, un
concierto con sus ensayos y una campaña abierta a la que la demo está invitada. Una cuenta demo con obras no se toca,
salvo que todas sean versiones anteriores de las de `demo/` y nadie haya valorado su campaña: entonces se crea de nuevo.

3. **Apply**. La primera construcción tarda varios minutos.

### Correo con Brevo

1. Crear una cuenta gratuita en Brevo.
2. En *Senders*, añadir y verificar el email remitente. No hace falta un dominio propio.
3. En *SMTP & API › API keys*, crear una clave de API (empieza por `xkeysib-`) y ponerla en `BREVO_API_KEY`.
4. `MAIL_FROM`: el remitente verificado, por ejemplo `ScoreMaster <correo@ejemplo.org>`.
5. `APP_BASE_URL`: `https://scoremaster-iz4j.onrender.com`.

Los enlaces de los correos se construyen con `APP_BASE_URL`, nunca con la cabecera `Host`, para que una petición
manipulada no pueda hacerlos apuntar a otro sitio. Sin las tres variables, la pantalla de acceso no ofrece «¿Has
olvidado la contraseña?» y una cuenta nueva no puede confirmar su email, así que no podría administrar ni recibir
invitaciones: conviene configurarlas antes de crear las cuentas de `ADMIN_EMAILS`.

### IA con Gemini

`GEMINI_API_KEY` se crea gratis en https://aistudio.google.com/apikey. Con ella, «¿Por qué esta dificultad?» y «¿Por
qué este plan?» las redacta Gemini; sin ella responde la demo, identificada como tal.

| Variable | Uso |
|---|---|
| `GEMINI_MODEL` | Modelo de las explicaciones y de las preguntas a la obra y al repertorio (por defecto `gemini-3.8-flash`). Cada pregunta libre gasta dos peticiones: una para elegir los datos y otra para responder; las sugeridas no gastan ninguna |
| `GEMINI_REVIEW_MODEL` | Modelo solo para «Valorar con IA» (método B), por ejemplo `gemini-3.5-flash-lite`: 15 peticiones por minuto y 500 al día, frente a 5 y 20 de `gemini-3.8-flash` |
| `GEMINI_ANALYSIS_MODEL` | Modelo solo para «Redactar el comentario» del análisis musical (por defecto `gemini-3.8-flash`, aunque `GEMINI_MODEL` sea otro): es el texto más largo y se guarda en caché |
| `GEMINI_REQUESTS_PER_MINUTE` | Pausa entre peticiones (5 por defecto) |
| `GEMINI_PRICE_INPUT_PER_MTOK`, `GEMINI_PRICE_OUTPUT_PER_MTOK` | Opcionales: precio por millón de tokens, para el coste estimado del panel «Uso de la IA» |

En el nivel gratuito Google puede usar lo enviado para mejorar sus productos. Solo se envían datos derivados del
análisis (grados, dimensiones, compases, bloques), nunca la partitura, emails ni nombres.

### Búsqueda en YouTube

La clave la usa el servidor, no el navegador. En Google Cloud, en la clave: *Restricciones de API* → solo «YouTube Data
API v3»; *Restricciones de aplicación* → **Ninguna** (con «Sitios web» Google rechaza las llamadas del servidor, y el
plan gratuito de Render no tiene IP fija). Si la búsqueda falla, los logs de Render dicen el motivo, nunca la clave.

## Seguridad en producción

- `APP_ENV=production`: cookies `Secure`, HSTS y sin documentación interactiva de la API. Render sirve HTTPS y uvicorn
  confía en sus cabeceras de proxy (`--proxy-headers`).
- El contenedor se ejecuta con un usuario sin privilegios.
- La conexión con Neon va cifrada (`sslmode=require` y `channel_binding=require`); la URL es un secreto de Render.
- El registro de cuentas está abierto: cada usuario solo ve sus datos y los intentos de acceso están limitados. La
  administración y las invitaciones exigen el email confirmado.
- Ningún secreto está en el repositorio. Más detalle en [SECURITY.md](SECURITY.md).

## Limitaciones del plan gratuito

| Limitación | Consecuencia | Qué hacer |
|---|---|---|
| Render duerme el servicio tras 15 min sin uso | El primer acceso tardaba alrededor de un minuto | El *workflow* `despertar.yml` pide `/health` cada 10 minutos desde este repositorio, que es público y no gasta minutos de Actions; las 750 horas al mes del plan cubren un servicio siempre encendido. GitHub puede retrasar unos minutos una ejecución programada y la desactiva tras 60 días sin actividad en el repositorio: si vuelve a dormirse, se reactiva en Actions › Despertar Render |
| 512 MB de memoria | Leer una obra grande con music21 usa ~330-450 MB en su pico | El lector termina la obra en GitHub y la envía comprimida (12 MB son 347 KB). Las obras pendientes al arrancar se leen en un proceso aparte, por turnos con las lecturas de PDF: si no le toca, el lector recibe 503 antes de enviar nada y reintenta unos 19 minutos. Al recibir una lectura, las pendientes siguen en el próximo arranque. Con obras muy grandes, subir de plan |
| CPU muy limitada | Leer una obra grande con music21 tarda unos 3 minutos | Cada obra se lee una sola vez: su modelo musical y su audio se guardan en la tabla `prepared_works` y sobreviven a reinicios y despliegues. Al arrancar se preparan en segundo plano las que falten. Si se pide un pasaje antes, el navegador muestra el avance y espera hasta 15 minutos. Con la obra preparada, un pasaje suena en ~2 s, una propuesta de ensayo tarda ~13 s y la planificación de un concierto ~22 s |
| Neon suspende la base tras 5 min sin uso | La primera consulta espera a que despierte (el servidor espera hasta 10 s al conectar) | Nada: se reanuda sola. El plan da 1 GB y 100 horas de cómputo al mes |

Para cambiar de plan basta con editar `plan:` en `render.yaml` o hacerlo desde el panel de Render.

## Base de datos en Neon

1. Crear un proyecto con **PostgreSQL 18** (los scripts también copian y restauran una base 17) en **AWS Europe Central 1 (Frankfurt)**, la región del servicio de Render.
2. **Connect** → desactivar *Connection pooling* y copiar la cadena **directa**
   (`postgresql://…neon.tech/…?sslmode=require&channel_binding=require`). Las migraciones de Alembic y el pool de
   SQLAlchemy necesitan la conexión directa.
3. Ponerla en `DATABASE_URL` del servicio de Render.

Neon guarda 6 horas de historial para volver a un momento anterior desde su panel.

## Copia de seguridad y restauración

Los scripts usan la imagen `postgres:18` de Docker, que copia y restaura bases 17 y 18: no hay que instalar PostgreSQL. La URL se lee de
`DATABASE_URL_EXTERNAL` o se pide sin mostrarla, para que no quede en el historial del terminal. Las copias van a
`backups/`, que no se versiona porque contienen datos personales.

**Copiar** (sobre todo tras cerrar una campaña de valoración)

1. En Neon, **Connect** → cadena directa.
2. En la raíz del repositorio, `scripts/backup_db.sh` y pegar la URL. Imprime las filas copiadas de cada tabla.
3. Exportar además cada campaña desde «Valoraciones → Exportar resultados» y guardar el JSON en `evaluation/exports/`
   (no se versiona): es lo que lee `python -m evaluation.campaign_report`.

**Restaurar** (en Neon, en otra base vacía o en la de Compose para comprobar la copia)

1. `scripts/restore_db.sh backups/<archivo>.dump` con la URL de destino. Imprime las mismas filas, para compararlas.
2. Si es una base nueva, cambiar `DATABASE_URL` en Render. Al arrancar no hay migraciones que aplicar: la versión
   viaja con la copia.

## Lector de PDF

Render no puede leer PDF: copista-2m necesita 2–4,5 GB de memoria. El lector (`omr/`) corre en **GitHub Actions**, en
el repositorio público `scoremaster-omr`, en las máquinas estándar de GitHub para repositorios públicos (4 CPU y 16 GB), que no
gastan minutos.

**Qué se ve en público.** Solo el *workflow*, sin secretos, y el registro de cada lectura. El registro nunca dice qué obra se
leyó: numera los archivos y las partes («Archivo 1, página 3 sin música», «Parte 15: 19 compases de silencio recuperados») y,
si algo falla, da dónde y de qué tipo fue el error, sin su mensaje. Los nombres de archivos y partes, el título y los motivos de
error solo llegan a ScoreMaster. Los PDF no se guardan como artefactos ni pasan por el registro, y el token de un solo uso va
enmascarado. Nadie de fuera puede lanzar una lectura: el evento `read-pdf` solo lo envía el token de Render.

**Cómo funciona**

1. Al subir un PDF, Render lo guarda y lanza en ese repositorio el evento `read-pdf` con un **token de un solo uso**
   para esa importación.
2. El *workflow* descarga de la rama `main` de ScoreMaster el código del lector (`omr/`), el catálogo de instrumentos
   (`backend/domain`) y lo que prepara las obras (`backend/parsers`); así se actualiza solo. Pide a ScoreMaster el catálogo de la base y los nombres que la cuenta ya
   confirmó, descarga los PDF con el token, lee las páginas con copista-2m y devuelve el avance y el MusicXML de la
   obra, o por qué falló. Las páginas de partitura que salen con menos pentagramas que las demás, o con dos compases más que la mayoría, se releen con copista-28m (hasta 40 por archivo o partitura, y sus pesos, 115 MB, solo se descargan entonces).
   Cada lectura usa **cuatro máquinas** a la vez: la primera lee la obra entera y la envía; las otras tres releen antes con
   copista-28m su parte de las páginas que parecen de partitura y las dejan en ScoreMaster con el mismo token (nunca en
   GitHub, cuyos registros y *artifacts* son públicos). La primera toma de allí las que necesita; si en 5 minutos no
   llega ninguna más, relee ella las que falten. Con «1812» (40 páginas de partitura en A3, de 24 a 31 pentagramas que
   copista-2m deja en 13), releerlas una tras otra costaba media hora.
3. Antes de devolver la obra, el lector pregunta a ScoreMaster cómo quedará el MusicXML definitivo (`/final`), lo lee con
   music21 y envía el modelo y el audio ya preparados junto con el resultado. Así Render no pasa minutos leyéndola con su
   décima de CPU. Render solo lo guarda si corresponde a esos mismos bytes y a sus versiones, se puede abrir y no había nada guardado; en
   cualquier otro caso, o si el lector no pudo prepararla, Render lee la obra como una subida normal. Lo preparado solo
   funciona con el *workflow* actual: hay que volver a ejecutar `scripts/deploy_omr_worker.sh` cuando cambia.
4. La máquina de GitHub se destruye al terminar, y Render borra los PDF al recibir el resultado.

**Crear el repositorio del lector** (una vez)

1. En GitHub, **New repository** → `scoremaster-omr`, **Public**, sin README.
2. Desde ScoreMaster, con `gh` autenticado: `scripts/deploy_omr_worker.sh <usuario>/scoremaster-omr`. Copia solo el
   *workflow*, sin secretos. Solo hay que repetirlo si cambia `omr/workflow/read-pdf.yml`.
3. **Settings → Developer settings → Personal access tokens → Fine-grained tokens → Generate new token**:
   - **Repository access:** *Only select repositories* → `scoremaster-omr`;
   - **Permissions → Contents: Read and write** (lo exige `repository_dispatch`);
   - con caducidad; al caducar, se genera otro y se actualiza en Render.

   Ese token solo puede lanzar el lector.
4. En Render, `OMR_GITHUB_REPO` = `<usuario>/scoremaster-omr` y `OMR_GITHUB_TOKEN` = el token. Sin ellos, la opción de
   subir PDF no aparece.

**Límites**

- Hasta 20 MB por PDF, 40 archivos y 160 páginas por obra (unos 30 minutos de lectura en el peor caso; el trabajo tiene 60).
- Una lectura a la vez; la siguiente espera.
- Cada lectura tarda 1–2 minutos en arrancar la máquina, más unos segundos por página. Las páginas se leen de cuatro en cuatro, un proceso de copista por procesador (`OMR_PAGE_WORKERS` lo cambia): «Arabian Dances», 112 páginas, pasó de 444 s a 275 s con cuatro procesadores. Si un proceso se queda sin memoria, las páginas que faltan se leen de una en una.
- Si Render se está reiniciando al terminar la lectura (un despliegue, o dormido en el plan gratuito), el lector espera y reintenta hasta unos 9 minutos, sin perder lo leído. El avance que no se puede enviar se omite.
- Tras la última página, el lector avisa cada 5 minutos de que está releyendo y uniendo la obra, y la app lo dice;
  ScoreMaster da por perdida una lectura que pasa 30 minutos sin avisar.
- El modelo grande lee en un proceso aparte con todos los procesadores de la máquina; el registro dice cuánto tardó.
- El registro de cada lectura (pestaña **Actions** del repositorio del lector) no muestra el token ni las partituras.

**Correcciones al recibir la lectura**

- **Guion primero:** si el PDF trae guion, la obra sale siempre del guion, con su estructura de compases y páginas. Cada
  particella se empareja con su pentagrama (por nombre si el guion lo trae, y por ritmo en conjunto: un pentagrama solo
  comparte particellas del mismo instrumento o de su mismo ritmo) y se compara compás a compás por ritmo. Donde guion y
  particella coinciden, se queda el guion; donde no, se toma el compás de la particella, que se lee mejor, y queda como
  dudoso. El registro dice la coincidencia y cuántos compases dudosos hay, y el lector envía esos compases con la obra:
  la pestaña Partitura los muestra por parte («Dudas del lector de PDF»), cada pasaje se abre para compararlo con el PDF
  y la parte se marca como revisada (se guarda en `works.reading_doubts`, migración 0027). Sin guion, la obra sale de
  las particellas y no hay dudas.
- **Páginas partidas:** copista parte a veces una página del guion en bloques: ve menos pentagramas y repite los
  compases. Si una página tiene menos pentagramas y casi el doble de compases que las demás, se toma como mal leída
  aunque el margen no lo diga, y se queda con sus compases reales (sin los vacíos y dividida entre los bloques), que se
  rellenan con las particellas.
- **Páginas con un pentagrama de menos:** si a una página del guion solo le falta un pentagrama, no se silencia: se
  coloca por clave y armadura y solo ese pentagrama queda en silencio. En «Arabian Dances», copista leyó 23 de 24
  pentagramas en seis páginas, y silenciarlas enteras dejaba a toda la banda callada 26 compases. Con más pentagramas de
  menos, la página se sigue silenciando.
- **Primera página del guion:** copisteria toma una página con una sola imagen incrustada por un escaneo y lee esa
  imagen. En la primera página del guion de «Arabian Dances», esa imagen era el código QR del pie (90 × 61 píxeles) y la
  página salía sin pentagramas. Si la imagen mide menos de 1000 píxeles de lado, el lector dibuja la página entera a
  300 ppp y lee esa (`page_image`).
- **Silencios con su compás:** los silencios de una página silenciada o de un pentagrama que falta en una página llevan
  la cifra de compás de esa página. Sin ella, music21 los escribía en 4/4 y dos compases de 4/2 se convertían en tres.
- **Nombres al lado de cada pentagrama:** en un guion, un nombre del margen suele abarcar varios pentagramas bajo una
  llave («Fls.» con «1» y «2» al lado de un pentagrama compartido; «Cls.» con «1» al lado de un pentagrama y «2 3» al
  lado del siguiente). El lector lee las palabras del margen con su posición (`pdftotext -bbox`, `omr/margin.py`): cada
  clave marca un pentagrama, cada línea de nombre va al pentagrama más cercano, uno sin nombre propio toma el de su
  llave, y los números, al pentagrama que tienen al lado. Si todos se reconocen en el catálogo, el guion se nombra así
  («Cls. 2 3» es el clarinete con las partes 2 y 3), y cada particella se empareja con el pentagrama que comparte
  («Flute 1» con «Fls. 1 2»).
- **Guion de banda en un solo sistema** («1812», 30 pentagramas en A3): las barras de compás se cortan entre familias, y
  copisteria tomaba maderas, metales y percusión (13 + 11 + 6 pentagramas) por tres sistemas seguidos, como compases
  nuevos de 13 partes. Si el margen tiene un nombre distinto junto a casi cada pentagrama (faltan como mucho 3), el
  lector le dice a copisteria que son un solo sistema y apunta en cada pentagrama leído el nombre más cercano por su
  altura. Las páginas se unen por esos nombres: copisteria pierde a veces los pentagramas de percusión de una línea, y por
  clave y armadura tres clarinetes o cuatro trompetas son iguales. La referencia es la página más ancha con nombres; una
  con más pentagramas que ella está mal leída y se relee con copista-28m, que gana si nombra sus pentagramas.
- **Iniciales sueltas:** la fuente de «1812» imprime la mayúscula de cada nombre aparte («F l. 1», «H n. 1», «B sn.»).
  Una mayúscula de texto pequeño pegada (menos del 15 % de su altura) a un resto en minúscula o a un punto se une a él
  («Fl. 1»), en el texto de la página y en sus palabras con posición. El catálogo conoce también «Chim.» (campanas
  tubulares).
- **Nombres repetidos:** si los nombres del margen del guion se repiten (los nombres largos ocupan dos líneas y las
  percusiones listan sus instrumentos), no son uno por pentagrama y no se usan. Los pentagramas se nombran entonces con
  las particellas.
- **Escritura de la obra:** si music21 falla al retocar la notación (una figura imposible o un error al completar
  tresillos), la obra se escribe tal como se leyó, con las figuras imposibles corregidas y las notas demasiado largas
  partidas en figuras que MusicXML puede escribir.

- **Tempo:** copista no lee las indicaciones de tempo, y sin ellas la obra sonaba a negra = 120. El lector toma la
  primera que encuentra en el texto del PDF («Marxa Mora q = 50»: en las fuentes de Finale y Sibelius, q es la negra,
  h la blanca y e la corchea) y la escribe al principio de la obra. Sin tempo escrito, no inventa ninguno. En una página
  digital, cada indicación con metrónomo («E Allegro giusto (q = 132)») va al compás que tiene debajo: copisteria sabe
  dónde empieza cada compás del primer pentagrama y el texto, dónde empieza la indicación («1812» tiene catorce). Solo
  cuando ninguna página la sitúa, se usa la primera del texto al principio.
- **Silencios de varios compases:** copista se salta los silencios de varios compases de las particellas, así que cada
  una empezaba antes que las demás. Si las particellas salen con distinto número de compases, el lector lee también las
  páginas de la partitura general, alinea cada particella compás a compás con el pentagrama de ritmo más parecido
  (`omr/merge.py`, `fill_lost_rests`) y convierte en silencio los compases que perdió. Lo que leyó de la particella no se
  cambia ni se quita; una particella completa o que no se parece a ningún pentagrama se queda como se leyó.
- **Páginas de la partitura con menos pentagramas:** cada pentagrama de la partitura toma el nombre impreso a su lado
  en el margen («Perc. 2»), que se lee junto a su clave en el texto del PDF. Una página con menos pentagramas que la
  completa, como la sección de percusión impresa sola de «Arabian Dances», se coloca por esos nombres; si no los trae,
  por la clave y la armadura, como antes. Si esa sección ocupa varios sistemas por página (en «Arabian Dances», los
  compases 95 a 147 en dos páginas), tiene muchos más compases que una página normal y un margen tan largo como el del
  guion, pero no se toma por una página mal leída: su margen solo nombra los pentagramas leídos, sistema tras sistema
  (las líneas de notas que se cuelan en el margen no cuentan como nombres).
  La partitura conserva los nombres, y cada particella se alinea primero con el
  pentagrama de su nombre («Percussion 2» con «Perc. 2») y, si no hay ninguno, por el ritmo. Una particella en clave de
  percusión solo se alinea con pentagramas de percusión.
- **Percusión de varios instrumentos:** si el PDF trae la página de plantilla («Instrumentation»), el lector toma qué
  instrumentos toca cada particella de percusión («Percussion 1: Marimba, Low Tom…») y cuántos músicos necesita
  («Percussion 2 — 2 players»), y los escribe en la obra: un `<score-instrument>` por instrumento y un `<player>` por
  músico (MusicXML 4.0). ScoreMaster reconoce «Percussion», «Perc.» o «Percusión» como percusión, BandFit cuenta esos
  músicos y cada nota suena como un golpe según su línea, nunca como piano. Sin la página, nada cambia. Un papel que nombra varios instrumentos («Plato suspendido y triángulo», «Percusión 1 (Caja, Bombo)») es un solo papel de percusión, con un músico salvo que el PDF indique otra cosa o que dos de esos instrumentos suenen a la vez («Bombo y platos» en los mismos compases son dos). Una batería siempre es un músico, y los acordes de un instrumento con altura, como la marimba, no cuentan.
- **Guion escaneado:** el OCR de un escaneado escribe nombres como «Oboe» junto a los pentagramas, y parecía una particella. Si al leer no aparece ninguna, las páginas apartadas se leen y la obra sale del guion completo, con cada página en su orden.
- **Nombres en un guion escaneado:** el margen de la primera página de música suele traer todos los nombres. Si tiene uno por pentagrama, cada uno se corrige solo de los deslices típicos del OCR («B'Trumpetl») y únicamente si el catálogo lo reconoce exactamente; si no, se queda como está escrito para confirmarlo en Mi banda. «Baritone» después de un metal es el bombardino, no el saxo. Si copista ve menos pentagramas que líneas tiene el margen (dos o más de menos), sus notas no se colocan: los compases de esa página se quedan en silencio y el registro lo dice. Como esas páginas se leen con compases de más, la obra puede tener más compases que el PDF.
- **Particellas escaneadas sin texto:** un PDF escaneado sin capa de texto (por ejemplo, particellas grabadas hace un siglo) no dice qué instrumento hay en cada página. El lector lee con OCR (tesseract, instalado en el flujo) la franja superior de cada página, donde va el nombre de la particella, y conserva la posición de las palabras para separar el nombre de lo que tiene al lado. Cada particella empieza en la página que trae los créditos («arr. by…») y toma el nombre que da la mayoría de sus páginas, corregido de los deslices típicos del OCR en ordinales («457» es 1st, «38D» es 3rd) y bemoles («B>» o «Bd» es B♭, «Kb» es E♭). En esas páginas copista lee cada línea como un sistema propio: antes juntaba las líneas de una particella en un sistema de varios pentagramas con compases inventados y la página parecía de un guion. Estos PDF se suben con «Detectar solo»; con «Particellas», cada archivo es una sola particella.
- **Particellas de varias páginas:** el nombre de cada particella se lee en la cabecera de la página, no entre los
  pentagramas, donde aparecen las entradas de otros instrumentos. Las páginas que empiezan por «Título - nombre» siguen a
  la particella anterior cuando el nombre la abrevia con su mismo número («Fl. 1» de «Flute 1», «Hn. 1» de «F Horn 1»);
  una primera página siempre empieza particella. Una página que nombra varios instrumentos entre dos páginas de
  particella, como la percusión, es de esa particella y no de la partitura general.
- **Instrumentos:** las particellas y los pentagramas de la partitura general se nombran con el catálogo (78
  instrumentos, con los de las bandas de concierto, las españolas y las brass bands, la percusión habitual y las
  abreviaturas de las particellas). El número de parte puede ir antes de la tonalidad («Trompa 1ª en Fa», «Clarinete 1
  Sib»), y «T.C.» o «B.C.» solo indican la clave. Si una particella no se puede leer, toma su pentagrama de la partitura
  general.
- **Transposición:** copista lee las notas tal como están impresas, pero no escribe `<transpose>`. ScoreMaster añade
  la de cada instrumento que reconoce (`backend/parsers/pdf_transpositions.py`). Las particellas siempre se
  transponen; un guion en Do no, si su texto lo dice («Score in C», «Guion en Do», «sonidos reales») o si sus armaduras
  lo indican. Algunos nombres no bastan y deciden la clave y la armadura, comparada con la de los instrumentos que
  suenan como se escriben:
  - **«Baritone»** a secas es el saxofón barítono, salvo que esté en clave de fa (los saxofones nunca se escriben en
    ella) o que su armadura tenga dos quintas más que esos instrumentos (Si♭; el saxo, en Mi♭, tiene tres). Entonces es
    el bombardino.
  - **Las tubas en clave de sol** de las ediciones británicas y europeas («Tuba in E♭ (T.C.)», «Eb Bass», «Bb Bass»)
    suenan una octava y una sexta más graves si están en Mi♭ y dos octavas y una segunda si están en Si♭. La
    tonalidad sale del nombre o, si no la trae, de la armadura (tres quintas más es Mi♭, y dos, Si♭).
- **Compases:** cada compás toma la duración de su compás (`backend/parsers/pdf_measures.py`). Si se pasa, se quita
  primero el silencio de compás entero leído junto a otras notas y después lo que sobrepasa la barra; si se queda
  corto, se completa con silencio (antes de las notas en el primer compás, que es una anacrusa).
- **Armaduras:** la tonalidad de cada compás es la que comparten la mayoría de las partes no transpositoras (al menos
  dos). Una parte transpuesta que no lleve esa tonalidad más el intervalo de su instrumento la toma
  (`fix_key_signatures`); sus alteraciones impresas se respetan hasta la barra.
