# Interfaces de intercambio

Los ejemplos son ficticios. Los scripts no detectan semánticamente preguntas o correspondencia: el anfitrión produce estas entradas a partir de las fuentes reales y documenta la observación.

## selection.json

~~~json
{"title":"Ensayo M1 identificado en portada","observed_question_count":1,"observation":"Una pregunta localizada visualmente","expected_questions":[{"id":"exam-q1","source_id":"exam","number":"1","page":2,"option_labels":["A","B"],"regions":[{"page":2,"bbox":[20,40,500,650]}],"content_inventory":[{"field":"stem","type":"math","count":1,"symbols":["m","n"],"regions":[{"page":2,"bbox":[40,60,450,100]}]},{"field":"options/A","type":"image","count":1,"regions":[{"page":2,"bbox":[40,150,250,310]}]},{"field":"options/B","type":"image","count":1,"regions":[{"page":2,"bbox":[40,340,250,500]}]}]}]}
~~~

IDs seguros y únicos; número como string, página física desde 1. El total observado debe coincidir con el mapa. Las preguntas solo pertenecen a exam. El título es observado; la raíz del candidato usa scope full. Registrar option_labels en el orden observado y regiones de cada pregunta, incluyendo páginas adicionales; no deducir alternativas faltantes del número esperado. option_labels es obligatorio salvo mapping_pending:true explícito. Si la fuente no permite observarlas, conservar mapping_pending:true, contenido unresolved y cobertura parcial. No usar el flag para aprobar una pregunta resuelta sin sus alternativas observadas. field_regions por dimensión permite asociar regiones concretas a los cotejos.

`content_inventory` es obligatorio al mapear nuevas ejecuciones, salvo mapping_pending. Se observa desde el PDF antes de transcribir y queda congelado fuera de final.json. Cada entrada agrupa field (`stem` u `options/ETIQUETA`) y type (`image`, `table`, `math`), con count mínimo positivo y regiones de fuente. Para math, symbols opcional enumera variables de una letra que deben aparecer en bloques matemáticos de ese campo. Las figuras deben quedar contenidas por un recurso de ese campo, en su fuente y página. `[]` declara ausencia de estructuras observadas, nunca un inventario omitido. El inventario reduce omisiones; su declaración no prueba lectura fiel.

Un bloque unresolved explícito conserva el campo pendiente cuando falta evidencia legible. No satisface una entrega completa con pauta; los otros flujos pueden conservarlo en un paquete parcial.

## key.json

~~~json
{"exam_sha256":"HASH_REAL_DEL_EXAMEN", "match":{"status":"matched","reason":"Identidad y numeración contrastadas","evidence":[{"source_id":"solution","page":1,"observation":"Identificación del mismo ensayo"}]},"entries":[{"question_id":"exam-q1","label":"B","source_id":"solution","page":2,"observation":"Fila 1 de la pauta","has_explanation":false}]}
~~~

Con pauta integrada, source_id es exam. Registra únicamente entradas legibles y asociadas; duplicados, preguntas inexistentes, páginas inválidas y asociación no matched se rechazan. Una pauta parcial es válida. has_explanation=true permite procedencia solution para una explicación tomada de esa página. Si la justificación está en otra página, registra esa página en la entrada y describe dónde aparece también la respuesta.

Si la respuesta/desarrollo ocupa varias páginas, añade `pages:[2,3]` a la entrada, incluyendo su `page` principal. Se validan páginas físicas distintas y la vista incluye todas ellas; los cotejos de respuesta/explicación pueden citar las páginas registradas de esa fuente.

## batch.json

~~~json
{"run_id":"ID_REAL", "questions":["PREGUNTAS_COMPLETAS_SEGUN_CONTRATO"], "explanation_provenance":{"exam-q1":{"origin":"solution","source_id":"solution","page":2}},"curriculum_provenance":{"exam-q1":{"reason":"Requiere operar con racionales","evidence":[{"source_id":"exam","page":2,"observation":"Cociente de variables enteras"}]}}}
~~~

questions contiene objetos del [contrato](../shared/references/content-contract.md), no los strings ilustrativos. Cada explicación no vacía requiere procedencia; las propuestas de IA usan model, incluso con respuesta de pauta. Fidelidad pending, respuesta/explanation provisional o missing. Las respuestas de pauta se vinculan determinísticamente a la entrada congelada al ingerir; no necesitan una solución independiente para importarse.

## crops.json

~~~json
[{"id":"grafico-q1","source_id":"exam","page":2,"bbox":[40,100,300,260],"role":"asset"}]
~~~

Puntos PDF, origen superior izquierdo y orientación visible. Conservar figura completa, unidades y etiquetas; para alternativas visuales, asociar cada una a su etiqueta. Los bloques image referencian el id del recurso. Un crop de auditoría usa role evidence; no se incorpora al paquete por defecto. IDs nuevos; no sobrescribir recursos con distinta geometría.

En una página PNG completa de tamaño W×H, `x_pdf = x_pixel * ancho_pdf / W`, `y_pdf = y_pixel * alto_pdf / H`. Consulta ancho/alto y rotación en catalog.json; no mezcles coordenadas de miniaturas con puntos PDF. Verifica el recorte en `review` antes de dar pass.

## review

`review --run RUN` genera una carpeta nueva bajo `.work/base/reviews/` con HTML local, renderer, KaTeX, páginas de fuente, cajas de pregunta/recorte/inventario y recursos usados. Incluye las páginas de pauta y explicación registradas aunque no haya imágenes del solucionario. Devuelve html y render_review; abre la vista y compara cada pregunta completa.

`render-reviews.json` guarda referencias a vistas; cada fila de check-template incorpora render_review `{path,sha256}`. Conserva ese campo al registrar cotejos. Sus hashes vinculan contenido, solución, imágenes y archivos de la vista. Una edición exige generar una vista nueva y renovar los cotejos afectados. El HTML, las fuentes y las constancias quedan fuera del paquete. Esta operación no acredita que alguien abrió la vista.

## cotejo.json

Usa check-template para hashes de versión. La raíz contiene run_id, independent=false, session_id del productor y questions. Cada fila: id, content_sha256, solution_sha256 y checks con stem/options/assets_math/answer/explanation/consistency. Cada check: status pass/fail/unresolved, reason, field_paths y evidence [{id,sha256,observation,fields}] de imágenes enumeradas en el candidato. Copiar field_paths de la plantilla; cada cita.fields nombra las rutas que esa imagen realmente cubre. La unión de citas debe cubrir exactamente las rutas requeridas: opciones por etiqueta, fórmulas/figuras/tablas por ruta. Un hash de portada o una imagen de otra pregunta no bastan. La fuente de la pauta/solución se comprueba por separado para answer/explanation. No describe revisión independiente.

Con pauta completa, validate/pack rechazan cotejos fallidos o pendientes, contenido sin resolver, respuestas/explicaciones faltantes y mapeo/currículo incompletos. Una respuesta provisional con cotejo completo sigue siendo publicable; no exige ni inventa verified. Los otros flujos conservan paquetes parciales explícitos.

## Estados y metadatos

Nuevos finales usan schema_version 0.2.0; se conserva lectura histórica de 0.1.0. run añade host, processing_mode (answer-key/mixed/solve/partial-pending), review_mode (self/independent) y answer_key_sha256. El ledger de ejecución conserva destino real, sugerencia de descarga, procedencia de explicaciones y subconjunto de auditoría.

source_ref de una respuesta de pauta apunta a .work/base/answer-key-map.json#ID. La evidencia y los informes permanecen en el directorio de ejecución; el ZIP autónomo contiene el contenido renderizable y hashes de recursos, no promete llevar toda la auditoría. Para compartir trazabilidad, compartir expresamente los informes necesarios por separado.

El cotejo del productor mantiene estados provisionales/pending. reviewed/verified exige informe independiente, evidencia y decisiones vinculadas. No son equivalentes a una pauta oficial o acierto garantizado. Si hay discrepancia con pauta, conserva su origen y la incidencia; no la sustituuyas silenciosamente.


## Contrato curricular 0.2.0

Toda nueva importación M1 incorpora questions[].curriculum = {eje, subeje, en_temario}. Clasificar automáticamente cada pregunta por su contenido usando los cuatro ejes y 16 subejes de shared/references/curriculum-m1.json; consultar shared/references/curriculum-contract.md para pertenencia, evidencia y pendientes. No copiar la taxonomía de TESLA ni inferir desde numeración. Cada lote añade curriculum_provenance[id] con reason y evidence [{source_id,page,observation}]. Clasificar también preguntas sin pauta o cuya resolución experimental se rechazó. Conservar la incertidumbre como dudoso; un par null requiere CURRICULUM_PENDING y entrega curricular parcial. Los lectores admiten finales históricos 0.1.0 sin inventar clasificación; el manifiesto del paquete sigue en 0.1.0.



## Transporte JSON PowerShell

Consulta [esta interfaz opcional](advanced.md#transporte-json-powershell).

## Plan de lotes y recuperación

Consulta [esta interfaz opcional](advanced.md#plan-de-lotes-y-recuperación).

## Lectura ciega 0.2.0

Consulta [esta interfaz opcional](advanced.md#lectura-ciega-0.2.0).

## Selección independiente de revisión

Consulta [esta interfaz opcional](advanced.md#selección-independiente-de-revisión).

## Medidas de proveedor

Consulta [esta interfaz opcional](advanced.md#medidas-de-proveedor).

## draft.json v1 del extractor previo

Consulta [esta interfaz opcional](advanced.md#draftjson-v1-del-extractor-previo).
