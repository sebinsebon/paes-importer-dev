# Operación común

El agente lee e interpreta las fuentes; los scripts preparan, validan y empaquetan. Resuelve herramientas y referencias desde la carpeta de SKILL.md. Python 3.12+, Node.js 18+ y [dependencias instaladas](../README.md#instalación) son requisitos del anfitrión.

## Preparar y observar

1. Comprueba lectura visual real, recortes, ejecución, validación y entrega de archivos. Escribe capabilities.json con pdf_visual, crop, execute, zip, validate y observation. No declares comprensión por disponer de un renderizador.
2. En web usa una carpeta temporal y adjunta los archivos, sin preguntar ubicación. En CLI utiliza el destino indicado o pregunta. No sobrescribas ejecuciones.
3. Ejecuta prepare; devuelve output y RUN (output/.work/base):

~~~text
python -B scripts/importer.py prepare --exam ENSAYO.pdf --solution SOLUCIONARIO.pdf --host cli --client CLIENTE --session-id SESION_REAL --destination custom --output-root RUTA_ABSOLUTA --capabilities capabilities.json
~~~

Ajusta host y destino al flujo. Omite --solution si no existe o está integrado; modelo/esfuerzo no observables quedan desconocidos. prepare genera páginas e imágenes candidatas, sin transcribir preguntas. Los gráficos vectoriales y sus rótulos suelen requerir recorte explícito.

Lee todas las páginas. Construye selection.json con identidad, numeración, páginas, regiones, etiquetas de alternativas y **content_inventory** observado: imágenes, tablas y matemática por enunciado/opción, incluyendo variables y límites completos de figuras. Usa [] únicamente si ese campo no necesita estructuras. No derives el inventario del JSON transcrito.

Si hay pauta, coteja su asociación y cobertura. key.json registra letras y páginas de las justificaciones; una pauta parcial conserva solo las entradas documentadas.

~~~text
python -B scripts/importer.py map --run RUN --selection selection.json
python -B scripts/importer.py route --run RUN --answer-key key.json
python -B scripts/importer.py record-input --run RUN --response direct-input.json
~~~

Omite --answer-key sin pauta. Completa direct-input.template.json con páginas realmente leídas y modo native_pdf o page_images_fallback. Una declaración de lectura no prueba comprensión. El flujo web sin pauta completa solicita consentimiento antes de congelar route.

## Transcribir por lotes

Usa las [interfaces](interfaces.md) y [ejemplos de representación](representation.md). Produce hasta cinco preguntas por lote, reduciendo a una o dos para figuras, tablas o varias páginas. Conserva el orden original y todas las alternativas.

- Ensayo: enunciado, tablas, figuras, etiquetas y opciones. Una imagen por alternativa gráfica, en su opción.
- Solucionario correspondiente: respuesta y desarrollo. Transcribe pasos útiles como prosa y math.latex; usa imágenes para diagramas necesarios. No añadas capturas de todas las soluciones junto con su transcripción.
- Matemática: incluye variables aisladas como m/n en bloques math en línea cuando sean símbolos matemáticos. Revisa signos, exponentes, índices, fracciones, unidades y precios. No conviertas automáticamente letras de la prosa.
- Currículo: clasifica cada pregunta por su contenido usando el [catálogo y contrato M1](../shared/references/curriculum-contract.md). Añade curriculum_provenance con razón y evidencia; conserva incertidumbre.

~~~text
python -B scripts/importer.py crops --run RUN --requests crops.json
python -B scripts/importer.py ingest --run RUN --response batch.json
~~~

Las cajas usan puntos PDF, origen superior izquierdo y orientación visible. Si mides sobre una página PNG completa de W×H píxeles, convierte x con ancho_pdf/W e y con alto_pdf/H. No uses coordenadas de una miniatura o imagen desplazada como si fueran del PDF. Incluye vértices, rótulos, flechas y unidades; evita texto o figuras vecinas. No añadas un margen fijo que invada otra opción. Para corregir geometría utiliza un ID nuevo y actualiza la referencia.

Conserva accepted/unchanged; repara solo rejected. Máximo tres intentos por pregunta; después amplía la evidencia o registra el bloqueo. Las explicaciones tomadas de la pauta llevan origin solution; las redactadas por IA, model. El origen de la respuesta se vincula automáticamente a la pauta.

## Comparar antes de entregar

~~~text
python -B scripts/importer.py review --run RUN
python -B scripts/importer.py check-template --run RUN
python -B scripts/importer.py record-check --run RUN --response cotejo.json
~~~

**Abre el HTML devuelto por review.** Compara cada pregunta renderizada y cada recorte con su página, incluyendo solucionario. Naranja delimita preguntas; rojo, recortes; azul, estructuras observadas. Comprueba figuras completas sin contenido vecino y la ubicación de cada opción. Si no puedes abrir el HTML, inspecciona las imágenes con tus herramientas y renderiza el contenido estructurado con el renderer incluido; no declares cotejo visual basándote solo en JSON.

Completa los seis cotejos de la plantilla con pass/fail/unresolved, evidencia localizada y observaciones reales. Conserva render_review, que vincula la vista a los hashes actuales de contenido y recursos. Generar la vista no equivale a revisarla. Tras cambiar contenido o recursos, genera review de nuevo y renueva los cotejos afectados; los de preguntas intactas siguen vinculados a su vista original.

Con pauta completa, resuelve fallos y pendientes antes de empaquetar. Si falta evidencia, conserva la ejecución e informa que está incompleta. En otros flujos se conservan pendientes explícitos, incluyendo respuestas cuya resolución se rechazó.

~~~text
python -B scripts/importer.py validate --run RUN
python -B scripts/importer.py pack --run RUN
python -B scripts/importer.py inspect --package ARCHIVO.paessed
~~~

Si route exige revisión independiente, usa [auditoría](audit.md) antes de publicar. La autorrevisión mantiene pending/provisional; no crea estados reviewed/verified.

Entrega .paessed con final.json 0.2.0, manifest.json 0.1.0 y recursos usados; ZIP con bytes idénticos. Las vistas, PDFs y trazas permanecen fuera. Informa cobertura, procedencia y pendientes.

## Reanudar y herramientas opcionales

`resume --run RUN` comprueba fuentes, release y configuración; no reanuda trabajo de IA automáticamente. `fail --run RUN --reason MOTIVO` conserva una ejecución fallida. Para otra release abre una ejecución nueva.

Consulta [herramientas avanzadas](advanced.md) solo para transporte PowerShell, planificación de lotes, extracción draft v1, revisión independiente o mediciones de proveedor.
