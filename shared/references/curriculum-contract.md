# Contrato curricular general M1

Los nuevos final.json usan schema_version 0.2.0. Cada pregunta incluye curriculum con exactamente eje, subeje y en_temario (si, no o dudoso). El catálogo curriculum-m1.json define cuatro ejes y 16 subejes; es común a todos los ensayos M1. La referencia curricular es el temario oficial enlazado en el catálogo, no la taxonomía de un ensayo particular.

## Clasificación por el anfitrión

Después de leer enunciado, alternativas y figuras, identificar el conocimiento central necesario; distinguir herramientas incidentales. Elegir un par canónico del catálogo. Determinar pertenencia contrastando el requisito con el temario oficial: estar dentro de un subeje no garantiza si. Si exige contenidos excluidos o fuera de alcance, usar no; si falta evidencia o hay ambigüedad de alcance, usar dudoso y explicar la causa. Nunca inferir desde número, posición, pauta o etiquetas de otro ensayo. No copiar TESLA-taxonomy.json a otras importaciones.

Cada response incluye curriculum_provenance por ID clasificado: reason no vacía y evidence con source_id, page y observation no vacía. La página debe estar en regions de esa pregunta. Estas razones son declaraciones del anfitrión, no pruebas autenticadas de comprensión. El ledger curriculum-ledger.json registra razón, evidencia, estado y hashes del contenido, clasificación y catálogo.

Un candidato sin clasificación usa {"eje":null,"subeje":null,"en_temario":"dudoso"} y la incidencia CURRICULUM_PENDING. Ambos campos deben quedar null juntos. Una clasificación definida no conserva CURRICULUM_PENDING. Una importación curricularmente completa no tiene pares null. Un dudoso clasificado requiere una razón que identifique la ambigüedad y permanece visible.

Cambiar enunciado u opciones invalida la revisión curricular; cambiar sólo currículo no invalida revisiones matemáticas. El content_hash histórico permanece idéntico: curriculum_hash es una vinculación separada. El catálogo activo se registra por hash para reproducibilidad; no hay habilidad ni versionado curricular.

## Compatibilidad

Los lectores aceptan finales 0.1.0 y 0.2.0. Los históricos no se rellenan al abrirse. El contenedor .paessed/ZIP y manifest.json mantienen paessed-package/0.1.0. Activar lectores compatibles antes de productores nuevos. Un run antiguo debe usar su release congelado; no se promete reanudarlo con una instalación nueva.
