# Interfaces de intercambio

Los ejemplos son ficticios. Los scripts no detectan semánticamente preguntas o correspondencia: el anfitrión produce estas entradas a partir de las fuentes reales y documenta la observación.

## selection.json

~~~json
{"title":"Ensayo M1 identificado en portada","observed_question_count":2,"observation":"Dos preguntas localizadas visualmente", "expected_questions":[{"id":"exam-q1","source_id":"exam","number":"1","page":2,"option_labels":["A","B","C","D"]},{"id":"exam-q2","source_id":"exam","number":"2","page":3,"option_labels":["A","B","C","D"]}]}
~~~

IDs seguros y únicos; número como string, página física desde 1. El total observado debe coincidir con el mapa. Las preguntas solo pertenecen a exam. El título es observado; la raíz del candidato usa scope full. Registrar option_labels en el orden observado y regiones de cada pregunta, incluyendo páginas adicionales; no deducir alternativas faltantes del número esperado. option_labels es obligatorio salvo mapping_pending:true explícito. Si la fuente no permite observarlas, conservar mapping_pending:true, contenido unresolved y cobertura parcial. No usar el flag para aprobar una pregunta resuelta sin sus alternativas observadas. field_regions por dimensión permite asociar regiones concretas a los cotejos.

## key.json

~~~json
{"exam_sha256":"HASH_REAL_DEL_EXAMEN", "match":{"status":"matched","reason":"Identidad y numeración contrastadas","evidence":[{"source_id":"solution","page":1,"observation":"Identificación del mismo ensayo"}]},"entries":[{"question_id":"exam-q1","label":"B","source_id":"solution","page":2,"observation":"Fila 1 de la pauta","has_explanation":false}]}
~~~

Con pauta integrada, source_id es exam. Registra únicamente entradas legibles y asociadas; duplicados, preguntas inexistentes, páginas inválidas y asociación no matched se rechazan. Una pauta parcial es válida. has_explanation=true permite procedencia solution para una explicación tomada de esa página. Si la justificación está en otra página, registra esa página en la entrada y describe dónde aparece también la respuesta.

## batch.json

~~~json
{"run_id":"ID_REAL", "questions":["PREGUNTAS_COMPLETAS_SEGUN_CONTRATO"], "explanation_provenance":{"exam-q1":{"origin":"model"},"exam-q2":{"origin":"solution","source_id":"solution","page":2}}}
~~~

questions contiene objetos del [contrato](../shared/references/content-contract.md), no los strings ilustrativos. Cada explicación no vacía requiere procedencia; las propuestas de IA usan model, incluso con respuesta de pauta. Fidelidad pending, respuesta/explanation provisional o missing. Las respuestas de pauta se vinculan determinísticamente a la entrada congelada al ingerir; no necesitan una solución independiente para importarse.

## crops.json

~~~json
[{"id":"grafico-q1","source_id":"exam","page":2,"bbox":[40,100,300,260],"role":"asset"}]
~~~

Puntos PDF, origen superior izquierdo y orientación visible. Conservar figura completa, unidades y etiquetas; para alternativas visuales, asociar cada una a su etiqueta. Los bloques image referencian el id del recurso. Un crop de auditoría usa role evidence; no se incorpora al paquete por defecto. IDs nuevos; no sobrescribir recursos con distinta geometría.

## cotejo.json

Usa check-template para hashes de versión. La raíz contiene run_id, independent=false, session_id del productor y questions. Cada fila: id, content_sha256, solution_sha256 y checks con stem/options/assets_math/answer/explanation/consistency. Cada check: status pass/fail/unresolved, reason, field_paths y evidence [{id,sha256,observation,fields}] de imágenes enumeradas en el candidato. Copiar field_paths de la plantilla; cada cita.fields nombra las rutas que esa imagen realmente cubre. La unión de citas debe cubrir exactamente las rutas requeridas: opciones por etiqueta, fórmulas/figuras/tablas por ruta. Un hash de portada o una imagen de otra pregunta no bastan. La fuente de la pauta/solución se comprueba por separado para answer/explanation. No describe revisión independiente.

## Estados y metadatos

Nuevos finales usan schema_version 0.2.0; se conserva lectura histórica de 0.1.0. run añade host, processing_mode (answer-key/mixed/solve/partial-pending), review_mode (self/independent) y answer_key_sha256. El ledger de ejecución conserva destino real, sugerencia de descarga, procedencia de explicaciones y subconjunto de auditoría.

source_ref de una respuesta de pauta apunta a .work/base/answer-key-map.json#ID. La evidencia y los informes permanecen en el directorio de ejecución; el ZIP autónomo contiene el contenido renderizable y hashes de recursos, no promete llevar toda la auditoría. Para compartir trazabilidad, compartir expresamente los informes necesarios por separado.

El cotejo del productor mantiene estados provisionales/pending. reviewed/verified exige informe independiente, evidencia y decisiones vinculadas. No son equivalentes a una pauta oficial o acierto garantizado. Si hay discrepancia con pauta, conserva su origen y la incidencia; no la sustituuyas silenciosamente.


## Contrato curricular 0.2.0

Toda nueva importación M1 incorpora questions[].curriculum = {eje, subeje, en_temario}. Clasificar automáticamente cada pregunta por su contenido usando los cuatro ejes y 16 subejes de shared/references/curriculum-m1.json; consultar shared/references/curriculum-contract.md para pertenencia, evidencia y pendientes. No copiar la taxonomía de TESLA ni inferir desde numeración. Cada lote añade curriculum_provenance[id] con reason y evidence [{source_id,page,observation}]. Clasificar también preguntas sin pauta o cuya resolución experimental se rechazó. Conservar la incertidumbre como dudoso; un par null requiere CURRICULUM_PENDING y entrega curricular parcial. Los lectores admiten finales históricos 0.1.0 sin inventar clasificación; el manifiesto del paquete sigue en 0.1.0.


## Transporte JSON PowerShell

El contenido se escribe mediante un serializador UTF-8 y luego se transporta como bytes, sin interpolarlo en comandos. Usar scripts/write_json.ps1 -InputPath ARCHIVO -OutputPath DESTINO -WorkspaceRoot CARPETA_SELECCIONADA, o run.ps1 -JsonInputPath ARCHIVO -JsonOutputPath DESTINO -WorkspaceRoot CARPETA_SELECCIONADA. El workspace puede ser la carpeta de ejecución seleccionada por el usuario fuera del checkout. Si se omite, se usa el checkout. Requiere padre existente, rechaza enlaces, raíz del sistema, escape del workspace, JSON inválido y sobrescritura. No realiza una importación ni modifica el archivo origen.

## Plan de lotes y recuperación

`batch-plan --run RUN --batch-size 5 --max-characters 24000` devuelve batches, question_index y page_index sin modificar la ejecución. Cada lote conserva IDs, fuentes, páginas, assets y hashes de contenido/contexto/catálogo. El límite de caracteres serializados es un presupuesto de transporte, no una estimación de tokens. Una pregunta que excede el presupuesto permanece íntegra y sola; no cortar fórmulas, tablas o figuras.

`ingest` devuelve accepted, rejected (con motivo) y unchanged por pregunta. Conservar las aceptadas; regenerar únicamente las rechazadas. Un reenvío idéntico conserva estados y razones vigentes. Máximo tres intentos por pregunta dentro del presupuesto disponible; después ampliar evidencia, dejar pending/unresolved explícito o registrar fail. No repetir lotes aprobados para aparentar reparación.

## Lectura ciega 0.2.0

La verificación comienza con input.json de stage source-reading y reading-template.json. Completar únicamente id/source_id/number/regions/stem/options/evidence y reviewer identificado. No añadir answer, explanation ni decisiones del productor. `verify commit-reading --run VERIFICATION --batch batch-01 --response lectura.json` congela lectura y hashes antes de generar el paquete de comparison y report-template.json. El informe posterior debe conservar reading_sha256 y el mismo reviewer; la independencia continúa siendo una declaración, no aislamiento autenticado.

## Selección independiente de revisión

`route --run RUN --subagents --review-all` selecciona todas las preguntas para revisión independiente CLI, incluso si tienen pauta. Para un subconjunto usar `--review-question ID` repetido. Ambos modos de selección son excluyentes y requieren capacidades/contexto independientes; el modo web no simula agentes. Sin selección explícita se conserva el subconjunto por resolver existente. Resolver y revisar son decisiones separadas; las claves de pauta permanecen vinculadas y los conflictos se documentan.

## Medidas de proveedor

`record-usage --run RUN --response uso.json` acepta `{run_id, events:[{event_id, usage_source, input_tokens, output_tokens, cost, currency, duration_seconds}]}`. usage_source identifica el recibo o medición real. Cada evento corresponde a una llamada, sin agregados superpuestos. Mantener null para medidas no expuestas; currency es obligatorio cuando cost está medido. El mismo event_id con datos idénticos es idempotente; datos diferentes con el mismo ID se rechazan. No duplicar llamadas de agentes en una suma del coordinador. Los totales incompletos permanecen null, con subtotales conocidos separados.

## draft.json v1 del extractor previo

Después de `prepare`, `map` y `route`, una ejecución puede incorporar una extracción v1 existente:

~~~text
python -B scripts/importer.py adapt-draft --run RUN --draft /ruta/draft.json
~~~

El adaptador exige un candidato mapeado todavía intacto y cubrir exactamente la selección congelada completa. Valida el draft y sus recursos, vincula por SHA-256 exacto y número de páginas de fuente, y por número original de pregunta. Comprueba toda la conversión antes de aplicar cambios: asociaciones ambiguas o estructuras sin conversión segura fallan atómicamente y explican el bloqueo. Conserva copia del draft, recursos y evidencia de procedencia en `.work`, fuera del paquete final. Los contextos compartidos representables se incorporan a cada pregunta que los referencia conservando su procedencia. Los gráficos conservan su `source_bbox` y origen superior izquierdo al asociarse con el recorte de fuente; no se invierte el eje vertical ni se inventa geometría.

`complete` y `structural_fidelity.status=verified` son estados del extractor, no aprobación independiente. La conversión no los promueve a `reviewed` o `verified`. Respuestas, explicaciones y currículo no demostrados permanecen pendientes; el anfitrión debe completarlos mediante `ingest`, lectura registrada, cotejos y la auditoría que exija `route`. Conservar el draft interno no sustituye el `.paessed` 0.2.0 final.
