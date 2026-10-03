# Guía de desarrollo

## Flujo de trabajo

- Mantener main estable.
- Crear una rama por tarea: docs/, feat/ o fix/.
- Realizar commits pequeños con mensajes descriptivos.
- Abrir una pull request para integrar cambios en main.
- Revisar los cambios y ejecutar las comprobaciones aplicables.
- Integrar mediante Squash and merge y eliminar la rama terminada.

## Antes de implementar

1. Definir el objetivo y los criterios de aceptación.
2. Diseñar el modelo y las reglas necesarias.
3. Identificar riesgos de seguridad y controles OWASP.
4. Definir los casos de prueba.
5. Implementar y verificar.
6. Actualizar la documentación correspondiente.

## Arquitectura y calidad

- Aplicar Clean Architecture y principios SOLID sin sobreingeniería.
- Mantener el dominio independiente de frameworks y proveedores externos.
- Separar datos musicales, algoritmos, reglas e IA generativa.
- Calcular la dificultad mediante reglas reproducibles.
- Mantener secretos y datos privados fuera del repositorio.

## Pruebas

- Tests unitarios para métricas y reglas musicales.
- Tests de integración para parser, API y persistencia.
- Tests de seguridad para permisos y entradas no confiables.
- Tests de extremo a extremo para los recorridos principales.
- Cada corrección de un defecto debe incluir, cuando sea viable,
  una prueba que evite su reaparición.
- Las pruebas aplicables deben pasar antes de integrar una PR.
- Los cambios exclusivamente documentales requieren revisión de contenido,
  sin crear tests artificiales.

## Documentación

Actualizar la documentación junto con cada cambio de comportamiento,
configuración o arquitectura. Distinguir lo previsto de lo implementado
y verificado.

## Desarrollo guiado

- Explicar el objetivo de cada paso y los comandos antes de ejecutarlos.
- Indicar la herramienta, la carpeta de trabajo y el resultado esperado.
- Aprovechar la experiencia en C#/.NET, Java y SQL para explicar conceptos nuevos.
- No dar por conocidos macOS, VS Code, Python, Node.js ni Docker.
- Alternar tareas guiadas realizadas por la autora con tareas delegadas al asistente.
- Reservar oportunidades para comprender el código, escribir pruebas y revisar PRs.
- Documentar las decisiones y sus motivos para preparar la defensa del TFM.

## Cambios en el análisis musical

Todo cambio que afecte a dificultad, criticidad, identificación de instrumentos,
BandFit o prioridad de ensayo debe incluir:

- una prueba de regresión;
- la motivación musical del cambio;
- el impacto esperado sobre el baseline de `evaluation/`.

No ajustar pesos para corregir un único ejemplo sin comprobar regresiones.

## Cambios en la capa de IA

Todo cambio de prompt o de modelo debe:

- incrementar la versión del prompt cuando cambie su significado;
- conservar la salida estructurada y su validación;
- incluir pruebas con un proveedor fake;
- mantener el resultado determinista como alternativa.

No introducir proveedores directamente en el dominio.

## Aliases de instrumentos

Los nuevos aliases deben corresponder a un identificador canónico existente,
incluir una prueba y no crear falsos positivos por coincidencia parcial
(por ejemplo, English Horn no es Horn).

## Evaluación

No editar manualmente resultados experimentales. Los resultados publicados
deben poder regenerarse desde el dataset y las herramientas de `evaluation/`.

## Partituras y documentos privados

Solo se versionan partituras sintéticas, propias, de dominio público o con
licencia compatible. Las partituras comerciales usadas para pruebas manuales
se guardan en `test-scores/local/`, que Git ignora.
