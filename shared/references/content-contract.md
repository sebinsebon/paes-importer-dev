# Contrato de contenido portable

Schema autoritativo: ../schemas/final.schema.json. Formato paessed-benchmark, schema_version 0.1.0, pipeline pdf-direct. El nombre histórico se conserva por compatibilidad; esta importación no es un benchmark de precisión. Compatible con el lector local, sin acreditar integración con PAESSED Web.

Raíz: format/schema_version/pipeline/run/exam/sources/questions/assets/evidence. No añadir campos a preguntas. run admite metadatos del modo. sources contiene ID, nombre, SHA-256, page_count y role exam/solution; nunca PDF ni ruta local.

Pregunta: id/source_id/number/regions/stem/options/answer/explanation/fidelity/issues. IDs únicos; números strings. exam.expected_questions fija cobertura exacta, incluso con preguntas pendientes.

Bloques: text {text}, math {latex,display}, image {asset_id,alt}, table {rows}, unresolved {reason}. Alternativas label A..Z y blocks; no asumir cuatro o cinco alternativas.

Regiones: página física desde 1, bbox [x0,y0,x1,y1] en puntos PDF, origen superior izquierdo y orientación visible. Preguntas de varias páginas tienen varias regiones. Recursos PNG: id/path/sha256/mime/source_id/page/bbox. Rutas POSIX relativas assets/ o evidence/, sin enlaces ni .. . Una figura de enunciado/alternativa pertenece al PDF de la pregunta; la justificación puede proceder de solution. No atribuir recortes de otro PDF al ensayo.

## Fidelidad estructural obligatoria

- Tablas mediante table.rows: filas ordenadas, celdas de bloques, encabezados, columnas, unidades y posición. No usar tablas Markdown ni aplanarlas a prosa.
- Matemática mediante math.latex sin delimitadores $, $$, \(...\), \[...\]. display=false en línea y true para una expresión separada. text es prosa literal, sin comandos LaTeX. En JSON decodificado, cada comando KaTeX comienza con una barra invertida; dos barras antes de `sqrt` o `frac` indican doble escape erróneo. No aplanar exponentes, radicales o fracciones: una imagen no sustituye al bloque matemático.
- Fórmulas renderizables en KaTeX local, trust=false y sin macros privadas.
- Si el contrato no expresa una estructura esencial (p. ej. celdas combinadas), conservar imagen fiel y registrar limitación en issues. Sin evidencia legible, usar unresolved; no inventar.
- En alternativas gráficas, cada opción debe referenciar su propia imagen o estructura equivalente; un mosaico en stem acompañado por opciones genéricas no basta. Preservar símbolo y cifras de moneda; si una transformación pierde parte de `$11 000`, cotejar de nuevo el PDF, nunca inferir.
- Aprobar estructura no demuestra fidelidad visual ni corrección matemática. Revisar gráficos y etiquetas contra las páginas, no solo alt text.

## Estados

answer: label nullable, status missing/provisional/verified, origin none/model/answer-key, source_ref nullable. missing implica label null y origin none. Pauta vinculada tiene origin answer-key y referencia a la entrada congelada; permanece provisional sin revisión independiente.

explanation: blocks y status missing/provisional/verified. Vacía implica missing. El ledger separado conserva procedencia model/solution por pregunta. Una explicación generada con una respuesta de pauta sigue siendo propuesta de IA.

fidelity: status pending/reviewed/rejected y review_ref. El productor ingiere pending/provisional; record-check documenta autorrevisión sin promover estados. reviewed/verified exige revisión independiente, evidencia, hashes de versión y decisiones. No significa verdad matemática ni pauta oficial.

Cambiar contenido o solución invalida su cotejo. Conservar originales y versiones. Paquetes pendientes son válidos si cumplen estructura, cobertura y recursos; declarar dudas. No codificar contenido por número ni usar otras corridas como pauta.
