# Referencia Gold: mantenimiento y certificación

La referencia se conserva fuera del bundle y Git, bajo tmp/gold/. El paquete original y los PDF del usuario son entradas de solo lectura. La taxonomía externa es una anotación del ensayo, nunca el clasificador general ni una regla de numeración.

## Inventario y paquete derivado

Desde el checkout, con el Python local y -B:

~~~powershell
.venv/Scripts/python.exe -B scripts/gold.py --package RUTA/package_corregido.zip --taxonomy RUTA/TESLA-taxonomy.json
.venv/Scripts/python.exe -B scripts/gold.py --package RUTA/package_corregido.zip --taxonomy RUTA/TESLA-taxonomy.json --source RUTA/ensayo.pdf --source RUTA/solucionario.pdf --output tmp/gold/nuevo-expediente
~~~

La primera orden solo lee y devuelve inventario, hashes, cobertura y estados heredados. La segunda exige un directorio nuevo dentro de tmp/: valida en memoria una copia compatible antes de escribirla, conserva final.json sin alteración, recalcula el manifiesto, entrega ZIP y .paessed idénticos y separa los archivos extras de auditoría en original-extras/. Rechaza rutas enlazadas, salidas existentes, archivos ZIP ambiguos y hashes incorrectos.

inventory.json y certification.json conservan status: pending. Ningún estado reviewed/verified heredado ni validación estructural acredita revisión independiente, exactitud matemática o presentación web. El resultado derivative_validation es una lectura técnica del formato, no la certificación.

## Adjudicación necesaria

Cada pregunta requiere cotejo de enunciado, cada alternativa, fórmulas, tablas, unidades y recursos esenciales contra su región PDF. Revisar clave contra pauta y explicación contra matemática con dominio y supuestos explícitos. Revisar currículo con el catálogo común y adjudicar discrepancias con la anotación externa.

El expediente de adjudicación debe contener pregunta, dimensión, hashes de referencia y fuente, región/evidencia, observación, revisor, sesión, fecha y decisión. Una segunda revisión independiente debe registrar sus diferencias antes de conocer las decisiones del productor. Las ambigüedades del original se preservan y documentan; no se reescribe el PDF ni se declara unicidad sin sustento. Las incidencias conocidas de la auditoría deben quedar adjudicadas, no ignoradas al validar el contenedor.

Antes de certificar: comprobar las 65 preguntas en el renderer final y en el consumidor web real, con aplicación/commit/navegador; hacer persistencia y recorrido de exportación/reimportación. Si faltan revisores o la aplicación desplegada difiere de la local, la certificación permanece pendiente. Mantener un certificado ligado al SHA-256 del paquete de referencia y el alcance exacto de revisión; no heredar una certificación después de editar el contenido.

## Comparador

~~~powershell
.venv/Scripts/python.exe -B scripts/compare_gold.py --gold tmp/gold/referencia/package.zip --candidate RUTA/importacion.paessed --gold-taxonomy RUTA/TESLA-taxonomy.json --output tmp/comparison.json
~~~

El comparador verifica el inventario/hash de ZIP y .paessed, o lee un final.json. Para identidades distintas admite --id-map con un objeto Gold-ID: candidate-ID. Sin mapa usa exactamente source_id y number; no usa posición, contenido parecido ni rangos TESLA. Una correspondencia explícita debe ser uno a uno. Las fuentes y sus hashes se comparan por separado.

Reporta cobertura y diferencias por enunciado, texto, matemática, opciones/orden, tablas, clave, explicación, visual y curriculum. Conserva diferencia literal y una normalización limitada a espacios de text; nunca normaliza operadores, números o unidades para ocultar diferencias. El cambio de un hash de imagen señala revisión visual, no demuestra cambio de significado. Explicaciones distintas requieren una rúbrica humana/independiente: corrección, dominio, suficiencia y coherencia con la clave. La igualdad tampoco acredita una explicación original correcta.

El resultado siempre conserva certification: not_performed y semantic_correctness: not_proven. Una clasificación ausente en el contrato antiguo se informa como unavailable; --gold-taxonomy anota solo la referencia en memoria. No copia esa taxonomía al candidato.

## Evidencia disponible

Se preparó un expediente privado compatible del candidato TESLA con 65 preguntas y 18 assets. Se separó audit/revision_por_pregunta.json, sin editar el original. El estado de certificación permanece pendiente. Las pruebas de implementación de estas herramientas son ficticias y no dependen de los archivos TESLA.

## Inspector fuente/resultado

~~~powershell
.venv/Scripts/python.exe -B scripts/render_review.py --candidate tmp/gold/referencia/package.paessed --source exam=RUTA/ensayo.pdf --source solution=RUTA/solucionario.pdf --output tmp/gold/review-nuevo
~~~

Suministrar cada ID de fuente declarado exactamente una vez; omitir solution si el paquete no la declara. El inspector captura bytes inmutables y exige hashes y cantidades de páginas coincidentes antes de crear la salida. Renderiza cada página necesaria una sola vez y la vincula a las preguntas, con sus regiones superpuestas junto al contenido estructurado. Incluye KaTeX y fuentes locales, tablas y figuras, sin red ni copia de PDFs. La salida requiere directorio nuevo bajo tmp/. Abrir index.html para cotejar; review-inventory.json conserva hashes de entrada y renders. La generación no certifica revisión visual, exactitud o independencia: permanecen pendientes.
