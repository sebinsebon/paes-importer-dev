# Implementación PAESSED 0.2.0

## Entrega operativa

Contrato general M1 con cuatro ejes y 16 subejes, questions[].curriculum, clasificación por contenido del agente y evidencia ligada a hashes. Nuevos productores 0.2.0; lectura histórica 0.1.0; contenedor paessed-package 0.1.0. La Skill no clasifica semánticamente por reglas numéricas ni copia etiquetas TESLA.

| Tareas | Estado |
|---|---|
| C1/C2/C3 | Catálogo, contrato y validadores implementados; cuatro flujos documentados y probados con casos sintéticos, según capacidades reales del host |
| C4a/C4b | Lectores, persistencia, renderer, edición y exportación implementados en paesseduiux |
| S1/S2/S3/S4 | Evidencia localizada, transporte seguro, validación contextual y calidad propagada implementados |
| S5/S6/S7 | Lectura independiente congelada, inspector visual e instrucciones implementados |
| O1/O2 | Recibos de uso, tiempos CLI, recuperación granular y transacciones implementados |
| O3 | Lotes por complejidad e índices/hash de contexto implementados; ablations y ahorro pendientes de medición |
| G1/G4 | Expediente privado compatible y comparador implementados |
| G2/G3 | Evidencia y adjudicación TESLA reutilizadas; ocho explicaciones provisionales revisadas en consumidor local. Gold pendiente de identificar y contrastar el consumidor final |
| O4 | Evaluador implementado; corpus independiente, conjunto sellado y campañas reales pendientes |
| O5 | Protocolo de evaluación OCR/CAS documentado; incorporación al runtime deliberadamente no activada |

## Operación

Entrar por SKILL.md y el flujo correspondiente. Mapear option_labels y regiones observadas; cualquier mapping_pending impide declarar cobertura completa. Lotes requieren curriculum_provenance para clasificaciones definidas. Cotejos 0.2 identifican field_paths y campos cubiertos por cada evidencia.

Para revisión con pauta: route --subagents --review-all o --review-question ID. verify prepare crea paquetes source-reading sin la transcripción, clave ni explicación productora. verify commit-reading --batch ID --response ARCHIVO congela lectura y revela el candidato. Respuestas impresas dentro de la fuente pueden impedir cegamiento real; la ausencia de metadatos del productor no garantiza independencia de la fuente.

record-usage registra recibos reales por event_id; datos ausentes permanecen null. batch-plan propone lotes sin truncar contexto. Estas herramientas no reducen modelo, pasadas ni evidencia automáticamente.

## Evidencia y límites

La suite es sintética y no acredita exactitud sobre PDFs reales. La revisión de código pasó controles independientes de especificación e integridad. El build de producción web terminó correctamente. El expediente TESLA preserva originales y certificación pendiente; estados heredados reviewed/verified no equivalen a certificación.

Consultar BENCHMARKS.md y benchmark-protocol.md para curación, repetición y métricas. No se afirma ahorro, accuracy ni certificación Gold. No se realizaron importaciones reales de IA ni publicación/despliegue; cambios conservados sin commits.

## Cierre técnico del 2026-10-16

Release `1.2.0-portable`, protocolo `0.3.0`: 121 archivos verificados. Nuevas publicaciones directas y consolidadas exigen final 0.2.0; los lectores conservan 0.1.0. El manifiesto contenedor sigue en 0.1.0.

`adapt-draft --run RUN --draft ARCHIVO` incorpora draft v1 validado a una selección completa intacta, por hash/páginas de fuente y número original. Conserva el original, evidencia y procedencia; tablas, contextos, regiones múltiples y alternativas visuales llegan como propuestas pendientes. Catálogo, recursos y candidato se actualizan en una transacción recuperable. El host todavía debe leer, cotejar, clasificar, resolver y revisar conforme al flujo elegido. El validador v1 está incluido y atribuido, sin dependencia del checkout del extractor.

Verificación final: `python -B -m unittest discover -s tests -v`, 137 pruebas, 136 aprobadas y una omitida por privilegios Windows de symlink; junction y portabilidad aprobadas. Las ocho pruebas nuevas del adaptador incluyen conversión desde bundle extraído en carpeta con espacios/acentos, publicación posterior, recursos conservados tras nuevos crops e ingest, coordenadas exactas, fallos atómicos y bloqueo de emisión histórica. Log local excluido del bundle: `tmp/contract-020-suite-final.log`.

Contrato canónico consolidado bajo `contrato/0.2.0` del espacio PAESSED, con hashes y comprobación de divergencias. TESLA rc3 conserva SHA-256 `bb677d871da4a1d27ecaae1d944ee01327bddfeb5d36101b1f99faa12888824a`; el estado vigente y la evidencia están en su expediente canónico. El consumidor local añade revisión optativa de explicaciones provisionales sin modificar corrección, estados ni datos importados; pasó pruebas sintéticas de navegador, recursos/exportación, TypeScript y build de producción. No se ha acreditado paridad con el consumidor final elegido por el propietario, ni emitido certificado Gold.
