> Especificación de evolución: no describe funcionalidades ya implementadas. Las decisiones aprobadas de [IMPLEMENTATION_ROADMAP.md](IMPLEMENTATION_ROADMAP.md) prevalecen en escala, persistencia y secuencia.

# Engineering Principles — Clean Architecture, SOLID, Security and UX

## Objetivo

Estas reglas son requisitos transversales de MaestroAI / ScoreLint. No son mejoras opcionales.

Toda nueva funcionalidad debe respetar:

- Clean Architecture;
- principios SOLID;
- seguridad basada en OWASP;
- UX orientada a músicos/directores;
- accesibilidad y diseño responsive;
- testabilidad;
- mantenibilidad;
- observabilidad sin exponer información sensible.

---

# 1. Clean Architecture

La arquitectura debe preservar dependencias hacia dentro.

Dirección conceptual:

```text
Presentation / API / UI
          ↓
Application / Use Cases
          ↓
Domain
          ↑
Infrastructure implements ports
```

## Domain

Debe contener conocimiento de negocio/musical independiente de frameworks:

- entidades/VOs musicales;
- reglas de dificultad;
- criticidad;
- canonical instruments;
- BandFit concepts;
- tipos de resultados;
- políticas puras cuando corresponda.

El dominio NO debe depender directamente de:

- FastAPI;
- React;
- LangChain;
- proveedor LLM;
- ORM;
- HTTP;
- filesystem;
- proveedor de audio;
- base de datos.

## Application

Debe orquestar casos de uso:

- AnalyzeScore;
- ResolveInstrument;
- ReviewDifficulty;
- GenerateRehearsalPlan;
- SubmitExpertFeedback;
- RenderAudio;
- etc.

Debe depender de puertos/interfaces para infraestructura.

## Infrastructure

Implementa:

- parser/adapters externos cuando aplique;
- persistence;
- LLM providers;
- LangChain adapters;
- embedding providers;
- cache;
- sample/audio renderer;
- filesystem;
- email/auth providers;
- external APIs.

## Presentation

Incluye:

- FastAPI/controllers;
- DTOs;
- frontend;
- mapping request/response;
- validación superficial de entrada.

No debe contener reglas musicales complejas.

## Regla

Antes de crear un nuevo servicio, comprobar si pertenece realmente a:
- Domain;
- Application;
- Infrastructure;
- Presentation.

Evitar `utils` genéricos que oculten responsabilidades.

---

# 2. SOLID

## S — Single Responsibility

Cada componente debe tener una razón principal para cambiar.

Ejemplo correcto:

```text
DifficultyEngine
CriticalPassageDetector
InstrumentResolver
DifficultyReviewer
```

Evitar una clase tipo:

```text
ScoreService
```

que parsea, calcula dificultad, llama al LLM, guarda BD y genera audio.

## O — Open/Closed

Nuevos:
- proveedores LLM;
- algoritmos de dificultad;
- resolvers;
- audio renderers;

deben poder añadirse con extensiones/adapters sin modificar el núcleo de forma invasiva.

## L — Liskov Substitution

Implementaciones de ports/providers deben respetar contrato.

Ejemplo:
- DemoAIProvider;
- RealAIProvider;
- FakeAIProvider;

deben poder sustituirse sin alterar comportamiento esperado del caso de uso.

## I — Interface Segregation

Preferir interfaces pequeñas:

```text
ChatModelProvider
EmbeddingProvider
AudioRenderer
InstrumentAliasRepository
ExpertFeedbackRepository
```

Evitar una interfaz `IAIService` gigantesca.

## D — Dependency Inversion

Application/Domain dependen de abstracciones.

Infrastructure implementa esas abstracciones.

LangChain NO debe propagarse por todo el código.

---

# 3. Seguridad — OWASP

La seguridad es un requisito funcional.

Aplicar controles coherentes con el riesgo del proyecto y con prácticas OWASP.

## Autenticación y autorización

- passwords nunca en texto plano;
- hashing fuerte mediante librería estándar/aprobada;
- rate limiting donde proceda;
- protección contra brute force;
- autorización server-side;
- no confiar en roles/claims recibidos únicamente del cliente;
- sesiones/tokens con expiración;
- cookies seguras si se utilizan;
- CSRF protection cuando aplique al mecanismo de sesión.

## Secrets

Nunca versionar:

- API keys;
- passwords;
- OAuth secrets;
- JWT signing secrets;
- credentials.

Usar:
- environment variables;
- `.env.example` sin secretos;
- secret storage del entorno de despliegue.

## Input validation

Validar todos los inputs del usuario:

- MusicXML;
- nombres de fichero;
- configuración de banda;
- feedback;
- prompts/inputs libres;
- IDs;
- parámetros API.

Usar allowlists y tipos fuertes cuando sea posible.

## File uploads

Especialmente importante para MusicXML:

- limitar tamaño;
- validar extensión y MIME cuando sea útil;
- tratar el fichero como contenido no confiable;
- evitar path traversal;
- nombres internos generados por el servidor;
- no ejecutar contenido;
- límites de tiempo/memoria;
- borrar temporales;
- impedir XXE/XML External Entity;
- desactivar resolución de entidades externas en parsers XML;
- evitar XML bombs / entity expansion;
- límites de profundidad/tamaño si la librería lo permite.

## Injection

- ORM/queries parametrizadas;
- no concatenar SQL;
- escapar/sanitizar en la capa adecuada;
- evitar command injection en renderers externos;
- nunca interpolar rutas/comandos shell sin control.

## XSS

Frontend:
- no renderizar HTML generado por LLM sin sanitización;
- tratar explicaciones IA como texto;
- sanitizar Markdown/HTML si se permite rich text.

## Error handling

El usuario no debe ver:
- stack traces;
- secrets;
- connection strings;
- paths internos;
- prompts privados;
- detalles de infraestructura.

Registrar internamente un correlation/request id.

## Dependencies

- versiones fijadas de dependencias cuando sea apropiado;
- dependency scanning;
- revisar vulnerabilidades;
- no añadir librerías sin necesidad real.

## Logging

Nunca registrar:
- passwords;
- tokens;
- API keys;
- cookies/session IDs completas;
- MusicXML completo si no es necesario;
- información personal innecesaria.

## AI/LLM security

Todo contenido externo, incluido MusicXML/texto, es input no confiable.

Proteger frente a:
- prompt injection;
- instrucciones incrustadas en nombres/descripciones;
- salida LLM fuera de schema;
- tool calls no autorizadas;
- fuga de system prompts/secrets;
- consumo excesivo/costes.

Reglas:
- el LLM no obtiene acceso arbitrario a filesystem/DB;
- allowlist de acciones;
- structured output;
- límites de tokens;
- timeouts;
- retries limitados;
- circuit breaker/fallback cuando corresponda.

## Security tests

Incluir como mínimo tests para:
- upload inválido;
- XML malicioso/XXE según parser;
- oversized input;
- invalid auth;
- authorization;
- LLM invalid schema;
- prompt-like malicious instrument name;
- path traversal;
- secrets no incluidos en responses.

---

# 4. UX

La aplicación está dirigida a músicos, profesores y directores, no a desarrolladores.

## Principios

### Claridad

Responder visualmente a:

1. ¿Qué dificultad tiene?
2. ¿Qué partes requieren atención?
3. ¿Encaja con mi banda?
4. ¿Qué debería ensayar?
5. ¿Por qué el sistema dice eso?

### Progressive disclosure

Vista principal:
- lenguaje musical;
- visualmente limpia;
- pocos conceptos.

Detalles técnicos:
- solo bajo "Ver detalles" / "¿Por qué?".

### No alarmar

No mostrar `CRITICAL` indiscriminadamente.

Diferenciar:

```text
Normal
Atención
Difícil
Crítico
```

Si no hay críticos:

```text
No se han detectado pasajes críticos
```

es un resultado válido y positivo.

### Confidence

No mostrar falsa certeza.

Ejemplos UX:

```text
Confianza alta
Confianza media
Revisión recomendada
```

No hace falta mostrar `0.873564` al usuario normal.

### Human correction

Cuando un instrumento es dudoso:
- mostrar nombre original;
- propuesta;
- alternativas;
- posibilidad de confirmar/corregir.

La corrección debe ser rápida.

### Loading

Operaciones LLM/audio pueden tardar.

Mostrar:
- estado;
- progreso razonable;
- qué se está haciendo;
- opción de continuar usando análisis determinista si IA falla.

### Errors

Mensajes accionables:

Malo:
```text
500 Internal Server Error
```

Bueno:
```text
No hemos podido leer esta partitura MusicXML.
Comprueba que el archivo es válido o prueba a exportarlo de nuevo desde tu editor de partituras.
```

### Responsive

Priorizar:
- desktop/laptop para análisis;
- tablet usable;
- móvil al menos para consulta básica.

### Accessibility

- contraste suficiente;
- navegación por teclado;
- labels;
- focus visible;
- no depender solo del color;
- iconos acompañados de texto cuando sea relevante;
- estructura semántica;
- soporte para lectores de pantalla cuando sea viable.

### Internationalization

UI:
- castellano;
- inglés.

No incrustar strings de UI directamente si ya existe sistema i18n.

---

# 5. Performance UX

No realizar una llamada LLM por cada nota/compás si puede evitarse.

Usar:

```text
deterministic filtering
↓
candidate selection
↓
LLM only where useful
```

Objetivos:
- primera respuesta determinista rápida;
- enriquecimiento IA posterior si tarda;
- cache para resultados repetidos.

---

# 6. Testing strategy

## Unit
- domain rules;
- difficulty features;
- instrument resolution;
- criticality.

## Application
- use cases;
- orchestration;
- fallback.

## Integration
- DB;
- parser;
- LangChain adapters;
- audio renderer.

## API
- validation;
- auth;
- permissions;
- errors.

## Frontend
- flows principales;
- accessibility básico;
- error/loading states.

## E2E
Como mínimo:
1. login;
2. subir MusicXML;
3. analizar;
4. revisar instrumento ambiguo;
5. visualizar dificultad;
6. generar/consultar plan;
7. enviar feedback.

---

# 7. Code quality

- type hints;
- linting;
- formatter;
- tests;
- dependency boundaries;
- nombres de dominio claros;
- evitar duplicación;
- funciones pequeñas cuando mejore legibilidad;
- comments explican "por qué", no repiten el código.

No aplicar patrones por moda.

Clean Architecture y SOLID sirven para reducir acoplamiento y mejorar testabilidad, no para multiplicar capas sin valor.

---

# 8. Definition of Done adicional

Una funcionalidad no está terminada si:

- rompe boundaries de arquitectura sin justificación;
- no tiene tests;
- no valida inputs;
- expone datos sensibles;
- genera UX confusa;
- no contempla error/fallback;
- depende directamente de proveedor externo desde dominio;
- añade deuda técnica evitable.
