# Interfaces de intercambio

Los ejemplos son ficticios. Los scripts no detectan semánticamente preguntas o correspondencia: el anfitrión produce estas entradas a partir de las fuentes reales y documenta la observación.

## selection.json

~~~json
{"title":"Ensayo M1 identificado en portada","observed_question_count":2,"observation":"Dos preguntas localizadas visualmente", "expected_questions":[{"id":"exam-q1","source_id":"exam","number":"1","page":2},{"id":"exam-q2","source_id":"exam","number":"2","page":3}]}
~~~

IDs seguros y únicos; número como string, página física desde 1. El total observado debe coincidir con el mapa. Las preguntas solo pertenecen a exam. El título es observado; la raíz del candidato usa scope full.

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

Usa check-template para hashes de versión. La raíz contiene run_id, independent=false, session_id del productor y questions. Cada fila: id, content_sha256, solution_sha256 y checks con stem/options/assets_math/answer/explanation/consistency. Cada check: status pass/unresolved, reason y evidence [{id,sha256,observation}] de imágenes enumeradas en el candidato. No describe revisión independiente.

## Estados y metadatos

Se conserva schema_version 0.1.0. run añade host, processing_mode (answer-key/mixed/solve/partial-pending), review_mode (self/independent) y answer_key_sha256. El ledger de ejecución conserva destino real, sugerencia de descarga, procedencia de explicaciones y subconjunto de auditoría.

source_ref de una respuesta de pauta apunta a .work/base/answer-key-map.json#ID. La evidencia y los informes permanecen en el directorio de ejecución; el ZIP autónomo contiene el contenido renderizable y hashes de recursos, no promete llevar toda la auditoría. Para compartir trazabilidad, compartir expresamente los informes necesarios por separado.

El cotejo del productor mantiene estados provisionales/pending. reviewed/verified exige informe independiente, evidencia y decisiones vinculadas. No son equivalentes a una pauta oficial o acierto garantizado. Si hay discrepancia con pauta, conserva su origen y la incidencia; no la sustituuyas silenciosamente.
