# Visor y guía de reproducción

El visor del pasaje representa todo el rango elegido, con desplazamiento interno
para leerlo sin reducir las notas ni dividirlo en grupos de cuatro compases.
El rango 70–114 incluye 45 compases cuando la numeración es consecutiva.

La partitura completa conserva páginas de hasta cuatro compases con todas las
voces, indicador de página y controles de navegación. Ajustar al ancho conserva
un tamaño mínimo legible; el resto de las voces se consulta desplazándose dentro
del visor. En pantallas pequeñas también puede haber desplazamiento horizontal.

Durante la reproducción, un marcador violeta destaca el compás actual. El reloj
procede de los mismos tiempos musicales que el audio, incluyendo cambios de
velocidad y saltos de posición. En la partitura completa, la página cambia para
seguir la reproducción. En el pasaje, el marcador desplaza el visor hasta el
compás actual. Detener elimina el marcador.

La notación conserva las alturas escritas del MusicXML. El audio usa sonido real,
aplicando la transposición que contiene el archivo (por ejemplo, Si♭ suena un tono
por debajo de lo escrito). La guía indica compases, no cada nota individual.

## Verificación

`node --test backend/test/frontend/*.test.mjs` comprueba el reloj, cambios de
velocidad, saltos y el tamaño de la partitura.

`backend/test/test_playback.py` comprueba tiempos relativos al inicio del pasaje,
notas, acordes, silencios, ligaduras y transposición.

`backend/test/frontend/workflow.e2e.mjs` verifica con Playwright un pasaje sintético
de 45 compases, marcador y saltos, el cambio automático de página, reinicio y
reemplazo de archivo. El proveedor de muestras se sustituye en esta prueba; no
se trata de una valoración auditiva del timbre.

Las comprobaciones locales con partituras aportadas por el usuario no añaden
esos archivos al repositorio.

## Corte del audio

El renderer programa una salida de hasta 8 ms dentro de la duración escrita,
para terminar cada muestra al final de la nota. El valor predeterminado del motor
smplr 1.1.0 añade 300 ms después de la duración y provocaba superposiciones
perceptibles en pasajes rápidos. El cambio no modifica las alturas ni los ataques.

`backend/test/frontend/audio-release.e2e.mjs` usa el motor smplr 1.1.0 real con
una muestra sinusoidal sintética y OfflineAudioContext. Comprueba que el código
anterior conserva señal durante el silencio y que el corregido termina exactamente
al final de la nota. Requiere Playwright y acceso al módulo CDN; opcionalmente
`SMPLR_MODULE_FILE` permite usar una copia local del módulo público.

## Regresión de timbre del clarinete

Los puntos de bucle externos de FluidR3_GM producían un cambio de tono dentro de
la muestra MP3 D4 del clarinete: aproximadamente 294 Hz antes del bucle y 140 Hz
al entrar en él. Había un solo ataque programado, pero el sonido cambiaba dentro
de la nota. Se desactiva `loadLoopData` y se envía `loop: false` a cada evento.

`backend/test/frontend/clarinet-sample.e2e.mjs` verifica este defecto con smplr real,
la muestra pública real y OfflineAudioContext; no utiliza partituras comerciales.
El caso corregido mantiene aproximadamente 294 Hz durante la nota. Las variables
`SMPLR_MODULE_FILE`, `CLARINET_SAMPLE_FILE` y `CLARINET_LOOPS_FILE` permiten ejecutar
la comprobación con copias locales de esos recursos públicos.

Sin bucles, una nota más larga que la muestra disponible puede perder sostén.
Un renderer futuro deberá resolverlo con bucles validados o muestras adecuadas,
sin volver a activar los puntos externos defectuosos.

## Ventana del pasaje

La ventana usa casi toda la pantalla. Solo el área de notación tiene desplazamiento;
cabecera, cierre y controles permanecen visibles. El pasaje conserva todo el rango,
sin paginación ni reducción automática para meter todas las notas en una pantalla.
Los dos visores comparten estilos de botones y controles: reproducción/pausa,
detener, reloj, posición, velocidad, volumen, pantalla completa, zoom y ajuste al ancho.
La ventana puede cerrarse con el icono accesible de cierre o con Escape.
