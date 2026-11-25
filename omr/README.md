# ScoreMaster OMR

Lector de PDF de [ScoreMaster](../../../scoremaster-ai): convierte el guion o las particellas de una obra para banda en
**MusicXML**, con GitHub Actions y sin servidor propio.

Este repositorio contiene solo el *workflow*. El código está en la carpeta `omr/` del repositorio de ScoreMaster y se
descarga de su rama `main` en cada lectura, así que se actualiza solo.

## Por qué existe

Leer una partitura con un modelo de visión necesita entre 2 y 4,5 GB de memoria, y ScoreMaster funciona en un servidor de
512 MB. GitHub ofrece a los repositorios públicos máquinas de 4 procesadores y 16 GB sin gastar minutos: ScoreMaster pide una,
le entrega el PDF y recibe la obra.

## Cómo funciona

```text
 ScoreMaster                         GitHub Actions (este repositorio)
 ───────────                         ─────────────────────────────────
 PDF subido ──── read-pdf ─────────▶ 4 máquinas a la vez
             (token de un solo uso)   │ descargan el código y el PDF
                                      │ leen las páginas (copista-2m)
 avance  ◀────────────────────────────┤ releen las dudosas (copista-28m)
                                      │ unen páginas y partes (music21)
 MusicXML, modelo y audio ◀───────────┘ corrigen y preparan la obra
```

1. **Aviso.** ScoreMaster envía el evento `read-pdf` con un token que solo sirve para esa lectura.
2. **Lectura.** La primera máquina lee todas las páginas con copista-2m, cuatro a la vez.
3. **Segunda lectura.** Las páginas que salen con menos pentagramas o con compases de más se releen con copista-28m, más lento
   y preciso. Las otras tres máquinas adelantan ese trabajo.
4. **Unión.** Las páginas de un guion se unen pentagrama a pentagrama. Los instrumentos se reconocen por el texto del margen o
   por OCR, con el catálogo de ScoreMaster.
5. **Guion y particellas.** Si el PDF trae ambos, la obra sale del guion y cada particella sirve para comprobarlo: los compases
   en los que no coinciden se entregan como dudosos, para que los revise el director.
6. **Correcciones.** Compases con la duración de su cifra, transposición de cada instrumento, armaduras que faltan, claves
   confundidas y alteraciones que la página no escribe. Las claves y esas alteraciones solo se cambian si lo que toca el
   resto de la banda lo demuestra.
7. **Entrega.** La obra vuelve con su modelo y su audio ya preparados.

## Qué contiene

| Archivo | Para qué |
|---|---|
| `.github/workflows/read-pdf.yml` | El trabajo: máquinas, versiones fijadas y lectura |
| `NOTICE` | Créditos y licencias de copisteria y copista |
| `LICENSE` | Licencia MIT de ScoreMaster |

El código, en el repositorio de ScoreMaster:

| Módulo | Para qué |
|---|---|
| `omr/worker.py` | Recibe el trabajo, lee las páginas, reparte entre máquinas y entrega |
| `omr/merge.py` | Une páginas y particellas, y las compara con el guion |
| `omr/margin.py` | Lee los nombres del margen con su posición |
| `omr/started.py` | Avisa de que la lectura ha empezado |
| `backend/parsers/` | Corrige y prepara la obra leída |
| `backend/domain/` | El catálogo de instrumentos |

## Límites

| | |
|---|---|
| Tamaño | 20 MB por PDF |
| Cantidad | 40 archivos y 160 páginas por obra |
| Tiempo | 60 minutos por lectura; 5 por página |
| A la vez | una lectura; la siguiente espera |

El arranque tarda uno o dos minutos. Lo demás depende del número de páginas y de cuántas haya que releer.

**Lo que lee mejor:** PDF exportados de un editor de partituras, con guion. **Lo que lee peor:** escaneos antiguos, particellas
sin guion (nada permite comprobar que van a la par), tresillos densos y notas pequeñas de guía. Una obra leída de un PDF es un
borrador: su grado es provisional y hay que revisarla.

## Privacidad y seguridad

Este repositorio es público y su registro también, así que:

- **El registro no dice qué obra se lee.** Numera archivos y partes, y de un error da el lugar y el tipo, sin su mensaje.
- **Los PDF no se guardan aquí.** No pasan por el registro ni se publican como *artifacts*; la máquina se destruye al terminar y
  ScoreMaster borra los PDF al recibir el resultado.
- **No hay secretos en el repositorio.** El token de cada lectura es de un solo uso, va enmascarado y se anula al acabar.
- **Nadie de fuera puede lanzar una lectura.** El evento `read-pdf` exige un token con permiso de escritura en este repositorio.
- **Versiones fijadas.** copisteria, los pesos de los modelos y PyTorch van a una versión exacta.

## Ponerlo en marcha

No se usa a mano: lo lanza ScoreMaster. Para una instalación propia, la guía está en `docs/DEPLOYMENT.md` del repositorio de
ScoreMaster («Lector de PDF»). En resumen:

1. Crear un repositorio público vacío.
2. Ejecutar `scripts/deploy_omr_worker.sh <usuario>/<repositorio>` desde ScoreMaster. Solo hay que repetirlo si cambian el
   *workflow* o este README, que se edita en `omr/README.md`.
3. Crear un token *fine-grained* limitado a ese repositorio (*Contents: Read and write*).
4. Definir `OMR_GITHUB_REPO` y `OMR_GITHUB_TOKEN` en el servidor. Sin ellos, la app no ofrece subir PDF.

## Si algo falla

| Qué se ve | Qué mirar |
|---|---|
| La lectura no empieza | La caducidad del token y que el *workflow* esté en la rama `main` |
| Falla una de las máquinas 1 a 3 | Nada: la primera lee lo que no llegue |
| Páginas «sin música» | Portadas o páginas de texto: se saltan |
| Se queda en «uniendo la obra» | Está releyendo páginas; avisa cada 5 minutos |

## Créditos y licencia

- [copisteria](https://github.com/kobimusic/copisteria), [copista-2m](https://huggingface.co/kobimusic/copista-2m) y
  [copista-28m](https://huggingface.co/kobimusic/copista-28m), de KobiMusic (Apache 2.0), sin modificar. Más detalle en `NOTICE`.
- [music21](https://www.music21.org/) para unir y preparar las obras.
- El código de ScoreMaster se publica con licencia MIT.
