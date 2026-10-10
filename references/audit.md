# Auditoría CLI independiente

Solo para independent_question_ids de la ruta. Pauta completa no necesita esta etapa. Con pauta parcial, el resto permanece importado con procedencia de pauta y autorrevisión.

~~~text
python -B scripts/importer.py baseline --run RUN
python -B scripts/importer.py verify prepare --run RUN --session-id SESION_COORDINADOR_REAL
~~~

RUN apunta a la producción base. baseline valida lectura, cobertura, cotejos y paquete; el control queda en .work/base. La verificación queda en .work/verification. No se publica aún el resultado.

Cada lote tiene hasta diez preguntas del subconjunto, input.json, report-template.json, páginas fuente necesarias y recursos del lote. Delegar en agentes con contexto nuevo, sin heredar historial. Entregar únicamente su paquete de lote y estas instrucciones/contrato; no PDF completo, otros lotes ni respuestas externas. Hasta tres agentes simultáneos cuando se pueda. La limitación es de protocolo, no una afirmación de aislamiento de archivos.

Cada agente resuelve desde la evidencia antes de contrastar la propuesta y escribe report.json desde la plantilla. Conserva contenido correcto. Seis checks: stem/options/assets_math/answer/explanation/consistency. Cada juicio pass/error necesita motivo y evidence [{path,sha256,observation}]; falta de evidencia queda unresolved. Registra reviewer real, fresh_context=true solo si corresponde, solución independiente, changes con field/before/after/reason/evidence y post_checks. Campos modificables: stem/options/regions/answer/explanation/issues. No cambia identidad, fuente ni recursos inventados. Aplica [fidelidad estructural](../shared/references/content-contract.md).

Si falta contexto visual, solicitar una ampliación concreta al coordinador:

~~~text
python -B scripts/importer.py verify add-evidence --run VERIFICATION --batch batch-01 --requests evidencia.json
~~~

requests es [{id,question_id,page,bbox,role,reason}]; bbox puede omitirse para página completa. Ejecutar antes del informe final; vuelve a generar el template/hash y conserva historia. Nunca reenviar el PDF completo por comodidad.

~~~text
python -B scripts/importer.py verify check --run VERIFICATION
python -B scripts/importer.py verify decisions --run VERIFICATION
~~~

Completar decisions-template.json como decisions.json. El coordinador identifica una sesión distinta a los verificadores y decide cada cambio con accept true/false, motivo, hash del informe y evidencia citada. Revisa realmente la fuente; no acepta todo automáticamente. Cambios dudosos se rechazan y quedan pendientes.

~~~text
python -B scripts/importer.py verify consolidate --run VERIFICATION --decisions decisions.json
~~~

Aplica solo cambios aceptados y publica el resultado en la raíz de ejecución. Promueve reviewed/verified únicamente cuando pasan las comprobaciones posteriores, las correcciones fueron aceptadas y la solución independiente coincide. Mantiene baseline exacto, informes y decisiones. La comparación matemática externa no forma parte de esta etapa.

Conserva coordinator-usage.json si hay medidas reales disponibles; null si no existen. scope coordinator_only o verification_including_agents evita doble conteo. La plantilla enumera campos. No volver a consolidar, sobrescribir informes o modificar una producción empaquetada. Una nueva revisión exige nueva ejecución. Reanudar awaiting_reviews consiste en conservar informes previos y completar faltantes después de check; no hay agente autónomo en Python.
